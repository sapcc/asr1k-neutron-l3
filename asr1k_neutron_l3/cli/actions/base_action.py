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

import socket

from oslo_config import cfg
from oslo_log import log as logging
from neutron.common import config as common_config
from neutron.common import topics
from neutron.agent.common import config
from neutron import context as n_context
from asr1k_neutron_l3.plugins.common import config as asr1k_config
from asr1k_neutron_l3.plugins.l3.agents.asr1k_l3_agent import L3PluginApi
from asr1k_neutron_l3.models import asr1k_pair

# from neutron.common import eventlet_utils
#
# eventlet_utils.monkey_patch()

LOG = logging.getLogger(__name__)


class BaseAction(object):

    def __init__(self, namespace):

        self.router_id = namespace.router_id
        self.config_files = namespace.config
        self.confirm = namespace.confirm
        #cfg.CONF(default_config_files=self.config_files)
        self.conf = cfg.CONF
        self.conf.register_opts(asr1k_config.DEVICE_OPTS, "asr1k_devices")
        self.host = socket.gethostname()
        common_config.init(("--config-file " + s for s in self.config_files),default_config_files=self.config_files)
        config.setup_logging()
        self.asr1k_pair = asr1k_pair.ASR1KPair(self.conf)
        self.plugin_rpc = L3PluginApi(topics.L3PLUGIN, self.host)
        self.context = n_context.get_admin_context_without_session()


    def get_router_info(self):
        routers = self.plugin_rpc.get_routers(self.context, [self.router_id])

        if routers:
            return  routers[0]