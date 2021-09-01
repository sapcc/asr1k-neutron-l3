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

from typing import List

from oslo_log import log as logging

from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.models.neutron.l3 import base
from asr1k_neutron_l3.models.neutron.l3 import access_list
from asr1k_neutron_l3.models.netconf_yang.class_map import ClassMap as ncClassMap
from asr1k_neutron_l3.models.netconf_yang.service_policy import ServicePolicy as ncServicePolicy
from asr1k_neutron_l3.models.netconf_yang.service_policy import ServicePolicyClass as ncServicePolicyClass
from asr1k_neutron_l3.models.netconf_yang.zone import Zone as ncZone
from asr1k_neutron_l3.models.netconf_yang.zone_pair import ZonePair as ncZonePair

LOG = logging.getLogger(__name__)


class FirewallPolicyObject(base.Base):

    PREFIX = None

    @classmethod
    def get_id_by_policy_id(cls, policy_id: str) -> str:
        if not cls.PREFIX:
            raise NotImplementedError("Class derived from 'FirewallPolicyObject' must define static var 'PREFIX'")
        return f"{cls.PREFIX}{policy_id}"

    def __init__(self, policy_id: str):
        self.policy_id = policy_id
        self.id = self.get_id_by_policy_id(self.policy_id)
        super().__init__()


class AccessList(access_list.AccessList, FirewallPolicyObject):

    PREFIX = "ACL-FWAAS-"
    ACTIONS = {
            'allow': 'permit',
            'deny': 'deny',
            'reject': 'deny',
    }

    def __init__(self, policy_id: str, rules: List[dict]):
        self.policy_id = policy_id
        super().__init__(self.get_id_by_policy_id(policy_id))
        for rule in rules:
            if not rule['enabled']:
                # Disabled rules are not programmed
                continue
            if rule['ip_version'] != 4:
                # For the time being, only IPv4 is supported, skip anything else.
                continue

            rule_args = {
                'action': self.ACTIONS[rule['action']],
                'protocol': rule['protocol']
            }

            # check if there is an IP address/CIDR for each direction
            # if so do the whole mask, wildcard dance
            for direction in ('source', 'destination'):
                if rule[f'{direction}_ip_address'] is not None:
                    if '/' in rule[direction + '_ip_address']:
                        rule_args[direction], mask = utils.from_cidr(rule[direction + '_ip_address'])
                        rule_args[direction + '_mask'] = utils.to_wildcard_mask(mask)
                    else:
                        rule_args[direction] = rule[direction + '_ip_address']
                if rule[direction + '_port']:
                    # unpack the port ranges
                    rule_args[direction + '_port_range'] = tuple(rule[direction + '_port'].split(':'))
            self.rules.append(access_list.Rule(**rule_args))


class ClassMap(FirewallPolicyObject):
    PREFIX = "CM-FWAAS-"

    @property
    def _rest_definition(self):
        return ncClassMap(id=self.id, acl_id=AccessList.get_id_by_policy_id(self.policy_id),
                          type='inspect', prematch='match-all')


class ServicePolicy(FirewallPolicyObject):
    PREFIX = "SP-FWAAS-"

    @property
    def _rest_definition(self):
        classes = [
            ncServicePolicyClass(id=ClassMap.get_id_by_policy_id(self.policy_id),
                                 type='inspect', policy_action='inspect'),
            ncServicePolicyClass(id='class-default', policy_action='drop', log=True)
        ]
        return ncServicePolicy(id=self.id, type='inspect', classes=classes)


class FirewallZoneObject(base.Base):

    PREFIX = None

    @classmethod
    def get_id_by_router_id(cls, router_id: str) -> str:
        if not cls.PREFIX:
            raise NotImplementedError("Class derived from 'FirewallZoneObject' must define static var 'PREFIX'")
        return "{}{}".format(cls.PREFIX, utils.uuid_to_vrf_id(router_id))

    @classmethod
    def get_id_by_vrf(cls, vrf: str) -> str:
        return cls.get_id_by_router_id(utils.vrf_id_to_uuid(vrf))

    def __init__(self, router_id: str):
        self.router_id = router_id
        self.id = self.get_id_by_router_id(self.router_id)
        super().__init__()


class Zone(FirewallZoneObject):

    PREFIX = 'ZN-FWAAS-'

    @property
    def _rest_definition(self):
        return ncZone(id=self.id)


class ZonePair(FirewallZoneObject):

    PREFIX = 'ZP-FWAAS-'
    DEFAULT_ALLOW_INSPECT_POLICY = ServicePolicy.PREFIX + "ALLOW-INSPECT"

    def __init__(self, router_id: str, source: str, destination: str, policy_id: str):
        super().__init__(router_id)
        self.source = source
        self.destination = destination
        self.policy_id = policy_id

    @property
    def service_policy(self):
        if self.policy_id:
            return ServicePolicy.get_id_by_policy_id(self.policy_id)
        return self.DEFAULT_ALLOW_INSPECT_POLICY

    @property
    def _rest_definition(self):
        return ncZonePair(id=self.id, source=self.source, destination=self.destination,
                        service_policy=self.service_policy)


class ZonePairExtEgress(ZonePair):

    PREFIX = ZonePair.PREFIX + 'EXT-EGRESS-'

    def __init__(self, router_id: str, policy_id: str):
        self.source = 'default'
        self.destination = Zone.get_id_by_router_id(router_id)
        super().__init__(router_id, self.source, self.destination, policy_id)


class ZonePairExtIngress(ZonePair):

    PREFIX = ZonePair.PREFIX + 'EXT-INGRESS-'

    def __init__(self, router_id: str, policy_id: str):
        self.source = Zone.get_id_by_router_id(router_id)
        self.destination = 'default'
        super().__init__(router_id, self.source, self.destination, policy_id)
