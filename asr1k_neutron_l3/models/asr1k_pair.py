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

from oslo_log import log as logging
from oslo_config import cfg
from asr1k_neutron_l3.common import config as asr1k_config

LOG = logging.getLogger(__name__)


class ASR1KContext(object):

    def __init__(self,name, host, http_port, legacy_port,yang_port, nc_timeout, username, password, protocol='https', insecure=True,
                 headers={}, preflights=[]):
        self.protocol = protocol
        self.name = name
        self.host = host
        self.http_port = http_port
        self.legacy_port = legacy_port
        self.yang_port = yang_port
        self.nc_timeout = nc_timeout
        self.username = username
        self.password = password
        self.insecure = insecure
        self.headers = headers
        self.headers['content-type'] = headers.get('content-type', "application/yang-data+json")
        self.headers['accept'] = headers.get('accept', "application/yang-data+json")
        self.alive = False
        self.enabled = True
        self.preflights = preflights

class ASR1KPair(object):

    __instance = None

    def __new__(cls):
        if ASR1KPair.__instance is None:
            ASR1KPair.__instance = object.__new__(cls)
            ASR1KPair.__instance.__setup()

        return ASR1KPair.__instance


    def __setup(self):


        self.config = cfg.CONF
        self.contexts = []

        device_config = asr1k_config.create_device_pair_dictionary()

        for device_name in device_config.keys():
            config = device_config.get(device_name)

            self.contexts.append(ASR1KContext(device_name,config.get('host'), config.get('http_port',self.config.asr1k_devices.http_port), config.get('legacy_port',self.config.asr1k_devices.legacy_port),config.get('yang_port',self.config.asr1k_devices.yang_port),
                                              int(config.get('nc_timeout',self.config.asr1k_devices.nc_timeout)), config.get('user_name'),
                                              config.get('password'),
                                              protocol=config.get('protocol',self.config.asr1k_devices.protocol), insecure=True, preflights=self.config.asr1k.preflights))
