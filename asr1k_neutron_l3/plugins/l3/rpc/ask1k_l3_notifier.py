# Copyright 2017 SAP SE
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

import random

from oslo_log import helpers as log_helpers
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

from neutron.api.rpc.agentnotifiers import l3_rpc_agent_api
from neutron import manager
from neutron.common import constants
from neutron.common import utils
from neutron.common import topics
from neutron.plugins.common import constants as service_constants


class ASR1KAgentNotifyAPI(l3_rpc_agent_api.L3AgentNotifyAPI):

    @log_helpers.log_method_call
    def routers_updated(self, context, router_ids, operation=None, data=None,
                        shuffle_agents=False, schedule_routers=True):
        if router_ids:
            self._notification(context, 'routers_updated', router_ids,
                               operation, shuffle_agents, schedule_routers)

    @log_helpers.log_method_call
    def _agent_notification(self, context, method, router_ids, operation,
                            shuffle_agents):
        """Notify changed routers to hosting l3 agents."""
        adminContext = context if context.is_admin else context.elevated()
        plugin = manager.NeutronManager.get_service_plugins().get(
            service_constants.L3_ROUTER_NAT)
        for router_id in router_ids:
            hosts = plugin.get_hosts_to_notify(adminContext, router_id)
            if shuffle_agents:
                random.shuffle(hosts)
            for host in hosts:
                LOG.debug('Notify agent at %(topic)s.%(host)s the message '
                          '%(method)s',
                          {'topic': topics.L3_AGENT,
                           'host': host,
                           'method': method})
                cctxt = self.client.prepare(topic=topics.L3_AGENT,
                                            server=host,
                                            version='1.1')
                cctxt.cast(context, method, routers=[router_id], operation=operation)

    @log_helpers.log_method_call
    def _notification(self, context, method, router_ids, operation,
                      shuffle_agents, schedule_routers=True):

        """Notify all the agents that are hosting the routers."""
        plugin = manager.NeutronManager.get_service_plugins().get(
            service_constants.L3_ROUTER_NAT)
        if not plugin:
            LOG.error('No plugin for L3 routing registered. Cannot notify '
                      'agents with the message %s', method)
            return
        if utils.is_extension_supported(
                plugin, constants.L3_AGENT_SCHEDULER_EXT_ALIAS):
            adminContext = (context.is_admin and
                            context or context.elevated())
            if schedule_routers:
                plugin.schedule_routers(adminContext, router_ids)
            self._agent_notification(
                context, method, router_ids, operation, shuffle_agents)
        else:
            cctxt = self.client.prepare(fanout=True)
            cctxt.cast(context, method, routers=router_ids, operation=operation)
