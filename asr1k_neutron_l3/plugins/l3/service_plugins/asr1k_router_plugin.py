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

from neutron_lib.agent import topics
from neutron_lib import constants as n_const
from neutron_lib.plugins import constants as plugin_constants
from neutron_lib import rpc as n_rpc
from neutron_lib.services import base
from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging
from oslo_utils import importutils

import asr1k_neutron_l3
from asr1k_neutron_l3.common import config as asr1k_config
from asr1k_neutron_l3.plugins.l3.rpc import rpc_api
from asr1k_neutron_l3.plugins.l3.rpc import ask1k_l3_notifier
from asr1k_neutron_l3.plugins.l3.service_plugins import l3_extension_adapter

LOG = logging.getLogger(__name__)


class ASR1KRouterPlugin(l3_extension_adapter.ASR1KPluginBase, base.ServicePluginBase):
    supported_extension_aliases = ["router",
                                   "extraroute",
                                   "l3_agent_scheduler",
                                   "router_availability_zone",
                                   "asr1k_operations"]

    def __init__(self):
        super(ASR1KRouterPlugin, self).__init__()

        basepath = asr1k_neutron_l3.__path__[0]

        ext_paths = [basepath + '/extensions']
        cp = cfg.CONF.api_extensions_path
        to_add = ""
        for ext_path in ext_paths:
            if cp.find(ext_path) == -1:
                to_add += ':' + ext_path
        if to_add != "":
            cfg.CONF.set_override('api_extensions_path', cp + to_add)

        self.router_scheduler = importutils.import_object(cfg.CONF.router_scheduler_driver)

        asr1k_config.register_l2_opts()
        asr1k_config.register_l3_opts()

        self.add_periodic_l3_agent_status_check()

    @log_helpers.log_method_call
    def start_rpc_listeners(self):
        # RPC support
        self.topic = topics.L3PLUGIN
        self.conn = n_rpc.Connection()
        self.agent_notifiers.update(
            {n_const.AGENT_TYPE_L3: ask1k_l3_notifier.ASR1KAgentNotifyAPI()})
        self.endpoints = [rpc_api.ASR1KRpcAPI()]
        self.conn.create_consumer(self.topic, self.endpoints,
                                  fanout=False)
        return self.conn.consume_in_threads()

    @classmethod
    def get_plugin_type(cls):
        return plugin_constants.L3

    @classmethod
    def get_plugin_description(cls):
        return ("ASR1K Router Service Plugin for basic L3 forwarding"
                " between (L2) Neutron networks and access to external"
                " networks via a NAT gateway.")

    def get_number_of_agents_for_scheduling(self, context):
        """Return number of agents on which the router will be scheduled."""
        return 1
