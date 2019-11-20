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
from asr1k_neutron_l3.common.asr1k_exceptions import VersionInfoNotAvailable

LOG = logging.getLogger(__name__)


class FakeASR1KContext(object):
    """Fake ASR1K context, to be used where no context can be found

    This context can be used where no device is available, but a version decision needs to be
    made, e.g. in a __str__ method. It pins the version checks to a specific version to produce
    stable results
    """
    version_min_1612 = True
    use_bdvif = False
    bd_iftype = "BD-VIF"


class ASR1KContext(object):
    version_min_1612 = property(lambda self: self._get_version_attr('_version_min_1612'))

    def __init__(self, name, host, yang_port, nc_timeout, username, password, use_bdvif, insecure=True,
                 headers={}):
        self.name = name
        self.host = host
        self.yang_port = yang_port
        self.nc_timeout = nc_timeout
        self.username = username
        self.password = password
        self._use_bdvif = use_bdvif
        self.insecure = insecure
        self.headers = headers
        self.headers['content-type'] = headers.get('content-type', "application/yang-data+json")
        self.headers['accept'] = headers.get('accept', "application/yang-data+json")
        self.alive = False
        self.enabled = True
        self._got_version_info = False

    def __repr__(self):
        return "<{} of {} at {}>".format(self.__class__.__name__, self.host, hex(id(self)))

    def _collect_version_info(self):
        """Collect firmware version info by YANG version and maybe other means"""
        from asr1k_neutron_l3.models.connection import ConnectionManager

        with ConnectionManager(context=self) as connection:
            # ASR 16.12 has at least this version for the YANG native model
            self._version_min_1612 = connection.check_capability(module="Cisco-IOS-XE-native",
                                                                 min_revision="2019-07-01")

        self._got_version_info = True

    def _get_version_attr(self, attr_name):
        if not self._got_version_info:
            self._collect_version_info()
        if not hasattr(self, attr_name):
            raise VersionInfoNotAvailable(host=self.context.host, entity=attr_name)
        return getattr(self, attr_name)

    @property
    def use_bdvif(self):
        return self.version_min_1612 and self._use_bdvif

    @property
    def bd_iftype(self):
        return "BD-VIF" if self.use_bdvif else "BDI"


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

            asr1kctx = ASR1KContext(device_name, config.get('host'),
                                    config.get('yang_port', self.config.asr1k_devices.yang_port),
                                    int(config.get('nc_timeout', self.config.asr1k_devices.nc_timeout)),
                                    config.get('user_name'), config.get('password'), config.get('use_bdvif'),
                                    insecure=True)

            self.contexts.append(asr1kctx)
