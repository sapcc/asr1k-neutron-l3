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

from collections import OrderedDict

from oslo_log import log as logging

from asr1k_neutron_l3.models.rest.rest_base import RestBase
from asr1k_neutron_l3.common import utils

LOG = logging.getLogger(__name__)


class NATConstants(object):
    POOL = "Cisco-IOS-XE-nat:pool"
    ID = "id"
    START_ADDRESS = "start-address"
    END_ADDRESS = "end-address"
    NETMASK = "netmask"

    LIST = "Cisco-IOS-XE-nat:list"
    SOURCE = "source"
    REDUNDANCY = "redundancy"
    MAPPING_ID = "mapping-id"
    VRF = "vrf"
    OVERLOAD = "overload"

    TRANSPORT_LIST = "Cisco-IOS-XE-nat:nat-static-transport-list"
    STATIC = "Cisco-IOS-XE-nat:static"

    LOCAL_IP = "local-ip"
    GLOBAL_IP = "global-ip"


class NatPool(RestBase):
    LIST_KEY = NATConstants.POOL

    list_path = "/Cisco-IOS-XE-native:native/ip/nat"
    item_path = "{}/{}".format(list_path, NATConstants.POOL)

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'id', 'mandatory': True},
            {'key': 'start_address'},
            {'key': 'end_address'},
            {'key': 'netmask'}
        ]

    def __init__(self, **kwargs):
        super(NatPool, self).__init__(**kwargs)

    def to_dict(self):
        pool = OrderedDict()
        pool[NATConstants.ID] = self.id

        pool[NATConstants.START_ADDRESS] = self.start_address
        pool[NATConstants.END_ADDRESS] = self.end_address
        pool[NATConstants.NETMASK] = self.netmask

        result = OrderedDict()
        result[NATConstants.POOL] = pool

        return dict(result)


class NatBase(RestBase):

    def __init__(self, **kwargs):
        super(NatBase, self).__init__(**kwargs)

        # if self.mapping_id is None:
        #     self.mapping_id = randint(1, 2147483647)


class DynamicNat(NatBase):
    LIST_KEY = NATConstants.LIST

    list_path = "/Cisco-IOS-XE-native:native/ip/nat/inside/source"
    item_path = "{}/{}".format(list_path, NATConstants.LIST)

    @classmethod
    def __parameters__(cls):
        return [
            {"key": "id", "mandatory": True},
            {'key': 'vrf'},
            {'key': 'redundancy'},
            {'key': 'mapping_id'},
            {'key': 'overload','default':False}
        ]

    def __init__(self, **kwargs):
        super(DynamicNat, self).__init__(**kwargs)
        self.mapping_id = utils.uuid_to_mapping_id(self.vrf)

    def to_dict(self):
        entry = OrderedDict()
        entry[NATConstants.ID] = self.id
        entry[NATConstants.POOL] = self.vrf
        entry[NATConstants.VRF] = self.vrf

        if self.redundancy is not None:
            entry[NATConstants.REDUNDANCY] = self.redundancy
            entry[NATConstants.MAPPING_ID] = self.mapping_id
        if self.overload:
            entry[NATConstants.OVERLOAD] = "[null]"

        result = OrderedDict()
        result[NATConstants.LIST] = []
        result[NATConstants.LIST].append(entry)

        return dict(result)


class StaticNat(NatBase):
    LIST_KEY = NATConstants.TRANSPORT_LIST

    list_path = "/Cisco-IOS-XE-native:native/ip/nat/inside/source/static"
    item_path = "{}/{}".format(list_path, NATConstants.TRANSPORT_LIST)

    @classmethod
    def __parameters__(cls):
        return [
            {"key": "local_ip", "mandatory": True},
            {"key": "global_ip", "mandatory": True},
            {'key': 'vrf'},
            {'key': 'redundancy'},
            {'key': 'mapping_id'}
        ]

    def __init__(self, **kwargs):
        super(StaticNat, self).__init__(**kwargs)
        self.bridge_domain = kwargs.get("bridge_domain")
        local_ip_as_int = utils.ip_to_int(self.local_ip)
        global_ip_as_int = utils.ip_to_int(self.local_ip)

        self.mapping_id = int(utils.uuid_to_mapping_id(self.vrf) + local_ip_as_int + global_ip_as_int)

    def __id_function__(self, id_field, **kwargs):
        self.id = "{},{}".format(self.local_ip, self.global_ip)

    def to_dict(self):
        entry = OrderedDict()
        entry[NATConstants.LOCAL_IP] = self.local_ip
        entry[NATConstants.GLOBAL_IP] = self.global_ip
        entry[NATConstants.VRF] = self.vrf

        if self.redundancy is not None:
            entry[NATConstants.REDUNDANCY] = self.redundancy
            entry[NATConstants.MAPPING_ID] = self.mapping_id

        result = OrderedDict()
        result[NATConstants.TRANSPORT_LIST] = entry

        return dict(result)
