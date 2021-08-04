# Copyright 2021 SAP SE
#
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from neutron_fwaas.services.firewall.service_drivers import driver_api
from neutron_lib import constants as nl_constants

from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from asr1k_neutron_l3.plugins.db import asr1k_db
from asr1k_neutron_l3.plugins.l3.rpc import ask1k_l3_notifier

LOG = logging.getLogger(__name__)


class ASR1KFWaaSDriver(driver_api.FirewallDriverDB):

    SUPPORTED_L3_PORTS = {nl_constants.DEVICE_OWNER_ROUTER_GW, nl_constants.DEVICE_OWNER_ROUTER_INTF}

    def __init__(self, *args, **kwargs):
        super(ASR1KFWaaSDriver, self).__init__(*args, **kwargs)
        self.asr1k_db = asr1k_db.get_db_plugin()
        self.notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

    def is_supported_l3_port(self, port):
        device_owner = port.get('device_owner', '')
        return device_owner in self.SUPPORTED_L3_PORTS

    @log_helpers.log_method_call
    def start_rpc_listener(self):
        LOG.debug("No rpc listener available atm, so not starting one")
        return []

    def _notify_asr1k_agent(self, entity, id, context, router_ids=None, fwg_policy_ids=None):
        if isinstance(fwg_policy_ids, list):
            # Policies (or ACLs in Cisco lingo) are shared between routers. To update them there are 2 options:
            #   1. to introduce a second sync queue exclusively for policy objects
            #   2. include them in the router sync, whenever a policy was updated exclusively make sure on each
            #      agent where the policy is configured, a router sync of at least one router using the policy
            #      was done.
            #  We decide for (2) as we can use the existing queues and programming means. Also adding a second
            #  processing queue adds dangers of race conditions.
            notification_directory = dict()
            for policy_id in fwg_policy_ids:
                # build a unique list of policies and agents with an router that contains the ACL
                # notification_directory = {(policy, agent) = router_id }
                notification_directory = {(policy_id, x.host): x.device_id
                                          for x in self.asr1k_db.get_routers_with_policy(context, policy_id=policy_id)}
            for (policy_id, agent), router_id in notification_directory.items():
                LOG.debug("%s %s has changed, policy %s associated. Notifying agent to call update on"
                          " router_id %s on agent %s", entity, id, policy_id, router_id, agent)
                if isinstance(router_ids, list):
                    if router_id not in router_ids:
                        router_ids.append(router_id)
                else:
                    router_ids = [router_id]
        if isinstance(router_ids, list):
            self.notifier.routers_updated(context, router_ids)
            LOG.debug("%s %s has port/policy associated that belongs to routers %s."
                      " Notifying asr1k agent.", entity, id, router_ids)

    # Firewal Group
    @log_helpers.log_method_call
    def create_firewall_group_postcommit(self, context, firewall_group):
        if not firewall_group['admin_state_up']:
            return
        if firewall_group['ingress_firewall_policy_id'] is None and firewall_group['egress_firewall_policy_id'] is None:
            LOG.debug("firewall_group %s has no policies attached. Doing nothing", firewall_group['id'])
            return
        if not firewall_group['ports']:
            LOG.debug("firewall_group %s has no ports attached. Doing nothing", firewall_group['id'])
            return
        ports = firewall_group['ports']
        router_ids = self.asr1k_db.get_router_ids_by_ports(context, ports)
        self._notify_asr1k_agent('firewall_group', firewall_group['id'], context, router_ids=router_ids)

    @log_helpers.log_method_call
    def update_firewall_group_postcommit(self, context, old_firewall_group, new_firewall_group):
        admin_state_changed = old_firewall_group['admin_state_up'] != new_firewall_group['admin_state_up']
        policies_changed = (
            old_firewall_group['ingress_firewall_policy_id'] != new_firewall_group['ingress_firewall_policy_id']
            or
            old_firewall_group['egress_firewall_policy_id'] != new_firewall_group['egress_firewall_policy_id'])

        updated_ports = set()
        # if any of the assigned policies changed (meaning subsequent rules etc...),
        # then update all ports, the old and the new ones
        if policies_changed or admin_state_changed:
            updated_ports.update(old_firewall_group['ports'])
            updated_ports.update(new_firewall_group['ports'])
        else:
            old_ports, new_ports = set(old_firewall_group['ports']), set(new_firewall_group['ports'])
            updated_ports = old_ports.symmetric_difference(new_ports)
        if len(updated_ports) == 0:
            return
        router_ids = self.asr1k_db.get_router_ids_by_ports(context, updated_ports)
        self._notify_asr1k_agent('firewall_group', new_firewall_group['id'], context, router_ids=router_ids)

    @log_helpers.log_method_call
    def delete_firewall_group_postcommit(self, context, firewall_group):
        if not firewall_group['admin_state_up']:
            return
        if not (firewall_group['ingress_firewall_policy_id'] or firewall_group['egress_firewall_policy_id']):
            LOG.debug("firewall_group %s has no policies attached. Doing nothing", firewall_group['id'])
            return
        if not firewall_group['ports']:
            LOG.debug("firewall_group %s has no ports attached. Doing nothing", firewall_group['id'])
            return
        router_ids = self.asr1k_db.get_router_ids_by_ports(context, firewall_group['ports'])
        self._notify_asr1k_agent('firewall_group', firewall_group['id'], context, router_ids=router_ids)

    # Firewall Policy
    # create hooks omitted as action needs only to be taken once a policy is bound to a port via a group
    # delete hooks omitted as policies cannot be deleted when they are bound to a firewall group
    @log_helpers.log_method_call
    def update_firewall_policy_postcommit(self, context, old_firewall_policy, new_firewall_policy):
        if old_firewall_policy['firewall_rules'] != new_firewall_policy['firewall_rules']:
            fwg_id = new_firewall_policy['id']
            self._notify_asr1k_agent('firewall_policy', fwg_id, context, fwg_policy_ids=[fwg_id])

    # Firewall Rule
    # create calls omitted as a firewall rules will not do anything as long it is not included
    # in a policy
    # delete calls omitted as a rule must first be removed from a policy
    @log_helpers.log_method_call
    def update_firewall_rule_postcommit(self, context, old_firewall_rule, new_firewall_rule):
        action_attributes = ['protocol', 'ip_version', 'source_ip_address', 'destination_ip_address',
                             'source_port', 'destination_port', 'action', 'enabled']

        if any(old_firewall_rule[attr] != new_firewall_rule[attr] for attr in action_attributes):
            policy_ids = set(self.asr1k_db.get_policies_with_rule(context, new_firewall_rule['id']))
            self._notify_asr1k_agent('firewall_rule', new_firewall_rule['id'], context, fwg_policy_ids=policy_ids)

    @log_helpers.log_method_call
    def insert_rule_postcommit(self, context, policy_id, rule_info):
        self._notify_asr1k_agent('firewall_policy', policy_id, context, fwg_policy_ids=[policy_id])

    @log_helpers.log_method_call
    def remove_rule_postcommit(self, context, policy_id, rule_info):
        self._notify_asr1k_agent('firewall_policy', policy_id, context, fwg_policy_ids=[policy_id])
