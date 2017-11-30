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

from networking_cisco import backwards_compatibility as bc
from neutron.api.rpc.agentnotifiers import l3_rpc_agent_api
from neutron.common import constants as n_const
from neutron.common import rpc as n_rpc
from neutron.common import topics
from neutron.db import l3_db
from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging
from oslo_utils import importutils

from asr1k_neutron_l3.plugins.l3.rpc import rpc_api
from asr1k_neutron_l3.plugins.l3.service_plugins import l3_extension_adapter

LOG = logging.getLogger(__name__)


class ASR1KRouterPlugin(l3_extension_adapter.ASR1KPluginBase):
    supported_extension_aliases = ["router",
                                   "extraroute",
                                   "l3_agent_scheduler",
                                   "router_availability_zone"]

    def __init__(self):
        self.router_scheduler = importutils.import_object(cfg.CONF.router_scheduler_driver)

        # self.l3_rpc_notifier=ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        self.start_periodic_l3_agent_status_check()
        l3_db.subscribe()
        self.start_rpc_listeners()

    @log_helpers.log_method_call
    def start_rpc_listeners(self):
        # RPC support
        self.topic = topics.L3PLUGIN
        self.conn = n_rpc.create_connection()
        self.agent_notifiers.update(
            {n_const.AGENT_TYPE_L3: l3_rpc_agent_api.L3AgentNotifyAPI()})
        self.endpoints = [rpc_api.ASR1KRpcAPI()]
        self.conn.create_consumer(self.topic, self.endpoints,
                                  fanout=False)
        return self.conn.consume_in_threads()

    def get_plugin_type(self):
        return bc.constants.L3

    def get_plugin_description(self):
        return ("ASR1K Router Service Plugin for basic L3 forwarding"
                " between (L2) Neutron networks and access to external"
                " networks via a NAT gateway.")