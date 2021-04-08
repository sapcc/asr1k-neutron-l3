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

from oslo_log import helpers as log_helpers
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

from neutron.api.rpc.agentnotifiers import l3_rpc_agent_api
from neutron_lib.agent import topics
from neutron_lib.plugins import constants as plugin_constants
from neutron_lib.plugins import directory


class ASR1KAgentNotifyAPI(l3_rpc_agent_api.L3AgentNotifyAPI):
    # @log_helpers.log_method_call
    # def routers_updated(self, context, router_ids, operation=None, data=None,
    #                     shuffle_agents=False, schedule_routers=True):
    #     if router_ids:
    #         self._notification(context, 'routers_updated', router_ids,
    #                            operation, shuffle_agents, schedule_routers)

    @log_helpers.log_method_call
    def router_sync(self, context, router_id):
        if router_id:
            return self._agent_rpc(context, 'router_sync', router_id=router_id)

    @log_helpers.log_method_call
    def router_validate(self, context, router_id):
        if router_id:
            return self._agent_rpc(context, 'router_validate', router_id=router_id)

    @log_helpers.log_method_call
    def router_teardown(self, context, router_id):
        if router_id:
            return self._agent_rpc(context, 'router_teardown', router_id=router_id)

    @log_helpers.log_method_call
    def network_sync(self, context, network_id):
        return self._network_rpc(context, network_id, 'network_sync')

    @log_helpers.log_method_call
    def network_validate(self, context, network_id):
        return self._network_rpc(context, network_id, 'network_validate')

    def _network_rpc(self, context, network_id, method):
        if network_id:
            result = {}
            admin_context = context if context.is_admin else context.elevated()
            plugin = directory.get_plugin(plugin_constants.L3)
            hosts = plugin.get_hosts_for_network(admin_context, network_id)
            if hosts:
                for host in hosts:
                    agent_result = self._agent_rpc(context, method, host=host, network_id=network_id)
                    if agent_result:
                        result[host] = agent_result
                return result
            else:
                raise Exception("No devices found hosting network")

    @log_helpers.log_method_call
    def interface_statistics(self, context, router_id):
        if router_id:
            return self._agent_rpc(context, 'interface_statistics', router_id=router_id)

    @log_helpers.log_method_call
    def show_orphans(self, context, host):
        return self._agent_rpc(context, 'show_orphans', host=host)

    @log_helpers.log_method_call
    def delete_orphans(self, context, host):
        return self._agent_rpc(context, 'delete_orphans', host=host)

    @log_helpers.log_method_call
    def list_devices(self, context, host):
        return self._agent_rpc(context, 'list_devices', host=host)

    @log_helpers.log_method_call
    def show_device(self, context, host, device_id):
        return self._agent_rpc(context, 'show_device', host=host, device_id=device_id)

    @log_helpers.log_method_call
    def agent_init_config(self, context, host, router_info):
        return self._agent_rpc(context, 'agent_init_config', host=host, router_info=router_info)

    @log_helpers.log_method_call
    def _agent_rpc(self, context, method, router_id=None, host=None, device_id=None, router_info=None, network_id=None):
        """Notify changed routers to hosting l3 agents."""
        adminContext = context if context.is_admin else context.elevated()
        plugin = directory.get_plugin(plugin_constants.L3)
        if router_id is not None:
            host = plugin.get_host_for_router(adminContext, router_id)

        if host is None:
            raise Exception('No agent can be determined')

        LOG.debug('Notify agent at %(topic)s.%(host)s the message '
                  '%(method)s',
                  {'topic': topics.L3_AGENT,
                   'host': host,
                   'method': method})
        cctxt = self.client.prepare(topic=topics.L3_AGENT,
                                    server=host,
                                    version='1.1')
        kwargs = {}
        if router_id is not None:
            kwargs['router_id'] = router_id
        if device_id is not None:
            kwargs['device_id'] = device_id
        if router_info is not None:
            kwargs['router_info'] = router_info
        if network_id is not None:
            kwargs['network_id'] = network_id
        return cctxt.call(context, method, **kwargs)
