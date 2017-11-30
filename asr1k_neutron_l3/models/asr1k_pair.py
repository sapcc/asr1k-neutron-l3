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

LOG = logging.getLogger(__name__)


class ASR1KContext(object):

    def __init__(self, host, port, nc_port, nc_timeout, username, password, protocol='https', insecure=False,
                 headers={}):
        self.protocol = protocol
        self.host = host
        self.port = port
        self.nc_port = nc_port
        self.nc_timeout = nc_timeout
        self.username = username
        self.password = password
        self.insecure = insecure
        self.headers = headers
        self.headers['content-type'] = headers.get('content-type', "application/yang-data+json")
        self.headers['accept'] = headers.get('accept', "application/yang-data+json")


class ASR1KPair(object):

    def __new__(cls, config=None):

        if not hasattr(cls, 'instance'):
            cls.instance = super(ASR1KPair, cls).__new__(cls, config=None)

        return cls.instance

    def __init__(self, config=None):
        if config is not None:
            self.config = config
        self.contexts = []
        for host in self.config.asr1k_devices.hosts:
            self.contexts.append(ASR1KContext(host, self.config.asr1k_devices.port, self.config.asr1k_devices.nc_port,
                                              self.config.asr1k_devices.nc_timeout, self.config.asr1k_devices.user_name,
                                              self.config.asr1k_devices.password,
                                              protocol=self.config.asr1k_devices.protocol, insecure=True))
