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

import time

from oslo_log import log as logging
from oslo_config import cfg

from asr1k_neutron_l3.common import config as asr1k_config
from asr1k_neutron_l3.common.asr1k_exceptions import VersionInfoNotAvailable
from asr1k_neutron_l3.models.netconf_yang import xml_utils

LOG = logging.getLogger(__name__)


class ASR1KContextBase(object):
    @property
    def use_bdvif(self):
        return self.version_min_17_3

    @property
    def bd_iftype(self):
        return "BD-VIF" if self.use_bdvif else "BDI"


class FakeASR1KContext(ASR1KContextBase):
    """Fake ASR1K context, to be used where no context can be found

    This context can be used where no device is available, but a version decision needs to be
    made, e.g. in a __str__ method. It pins the version checks to a specific version to produce
    stable results
    """

    def __init__(self, version_min_17_3=True, version_min_17_6=True, version_min_17_13=True, version_min_17_15=True,
                 has_stateless_nat=True):
        self.version_min_17_3 = version_min_17_3
        self.version_min_17_6 = version_min_17_6
        self.version_min_17_13 = version_min_17_13
        self.version_min_17_15 = version_min_17_15
        self._has_stateless_nat = has_stateless_nat

    @property
    def has_stateless_nat(self):
        return self._has_stateless_nat


class ASR1KContext(ASR1KContextBase):
    version_min_17_3 = property(lambda self: self._get_version_attr('_version_min_17_3'))
    version_min_17_6 = property(lambda self: self._get_version_attr('_version_min_17_6'))
    version_min_17_13 = property(lambda self: self._get_version_attr('_version_min_17_13'))
    version_min_17_15 = property(lambda self: self._get_version_attr('_version_min_17_15'))
    has_stateless_nat = property(lambda self: self._get_version_attr('_has_stateless_nat'))

    def __init__(self, name, host, yang_port, nc_timeout, username, password, use_bdvif, insecure=True,
                 force_bdi=False, headers={}):
        self.name = name
        self.host = host
        self.yang_port = yang_port
        self.nc_timeout = nc_timeout
        self.username = username
        self.password = password
        self._use_bdvif = use_bdvif
        self.insecure = insecure
        self.force_bdi = force_bdi
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
            # newer images don't advertise all their capabilities, so we need to check the version
            ver_xml_data = connection.xpath_get("native/version")
            ver_data = xml_utils.XMLUtils.to_raw_json(ver_xml_data.xml)
            try:
                ver = ver_data['rpc-reply']['data']['native']['version'].split(".")
            except KeyError as e:
                LOG.error("Tried to fetch version for host %s, but couldn't parse the response: %s", self.host, e)
                raise VersionInfoNotAvailable(host=self.host, entity="native/version")

            # "parse" version
            def _to_int_if_possible(d):
                try:
                    return int(d)
                except ValueError:
                    return d

            ver = tuple(_to_int_if_possible(d) for d in ver)

            self._version_min_17_3 = ver >= (17, 3)
            self._version_min_17_6 = ver >= (17, 6)
            self._version_min_17_13 = ver >= (17, 13)
            self._version_min_17_15 = ver >= (17, 15)
            self._has_stateless_nat = ver >= (17, 4)

        self._got_version_info = True

    def _get_version_attr(self, attr_name):
        if not self._got_version_info:
            self._collect_version_info()
        if not hasattr(self, attr_name):
            raise VersionInfoNotAvailable(host=self.context.host, entity=attr_name)
        return getattr(self, attr_name)

    def wait_alive(self):
        timed_out = time.time() + self.nc_timeout
        last_log = time.time()
        while time.time() < timed_out:
            if self.alive:
                return True
            if last_log + 10 <= time.time():
                last_log = time.time()
                LOG.info("Still waiting for yang to come alive on %s", self.host)
            time.sleep(1)
        return False

    @property
    def use_bdvif(self):
        return self.version_min_17_3 and self._use_bdvif and not self.force_bdi

    def mark_alive(self, alive):
        if not alive:
            LOG.debug("Device %s marked as dead, resetting version info", self.host)
            self._got_version_info = False
        self.alive = alive


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

        for device_name, config in device_config.items():
            asr1kctx = ASR1KContext(device_name, config.host, config.yang_port, config.nc_timeout,
                                    config.user_name, config.password, config.use_bdvif,
                                    insecure=True)

            self.contexts.append(asr1kctx)
