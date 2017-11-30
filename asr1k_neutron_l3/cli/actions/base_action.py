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

from neutron.common import config as common_config
from oslo_config import cfg
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class BaseAction(object):

    def __init__(self, namespace):
        print(namespace)
        self.router_id = namespace.router_id
        self.port_id = namespace.port_id
        self.config_files = namespace.config
        self.confirm = namespace.confirm
        self.conf = cfg.CONF
        # self.conf.register_opts(cfg_agent.OPTS, "cfg_agent")
        common_config.init("--config-file " + s for s in self.config_files)
        self.host = socket.gethostname()
