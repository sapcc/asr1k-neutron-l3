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

from asr1k_neutron_l3.models.netconf import l3_interface as nc_l3_interface
from asr1k_neutron_l3.models.rest.rest_base import RestBase
from asr1k_neutron_l3.models.rest.rest_base import execute_on_pair
from asr1k_neutron_l3.models.wsma import l3_interface as wsma_l3_interface
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class L3Constants(object):
    BDI_INTERFACE = "Cisco-IOS-XE-native:BDI"

    ID = "id"
    NAME = "name"
    DESCRIPTION = "description"
    MAC_ADDRESS = "mac-address"
    MTU = "mtu"
    IP = "ip"
    ADDRESS = "address"
    PRIMARY = "primary"
    SECONDARY = "Cisco-IOS-XE-native:secondary"
    MASK = "mask"
    VRF = "vrf"
    FORWARDING = "forwarding"
    SHUTDOWN = "shutdown"
    NAT = "nat"
    NAT_MODE_INSIDE = "inside"
    NAT_MODE_OUTSIDE = "outside"


class BdiInterface(RestBase):
    LIST_KEY = L3Constants.BDI_INTERFACE

    list_path = "/Cisco-IOS-XE-native:native/interface"
    item_path = "{}/{}".format(list_path, L3Constants.BDI_INTERFACE)

    @classmethod
    def __parameters__(cls):
        # secondary IPs will be validated in NAT
        # NAT mode should be validated when supported in yang models - no point using netconf for now
        return [
            {"key": "name", "id": True},
            {'key': 'description'},
            {'key': 'mac_address'},
            {'key': 'mtu', 'default': 1500},
            {'key': 'vrf','yang-path':'vrf','yang-key':"forwarding"},
            {'key': 'ip_address','yang-path':'ip/address','yang-key':"primary",'type':BDIPrimaryIpAddress},
            {'key': 'secondary_ip_addresses','yang-path':'ip/address','yang-key':"secondary",'type':BDISecondaryIpAddress, 'default': [], 'validate':False},
            {'key': 'nat_mode', 'default': 'outside', 'validate':False},
            {'key': 'redundancy_group'},
            {'key': 'shutdown'},

        ]

    def __init__(self, **kwargs):
        super(BdiInterface, self).__init__(**kwargs)
        self.name = str(self.name)
        self.ncc = nc_l3_interface.BDIInterface(self)
        self.wsma = wsma_l3_interface.BDIInterface(self)

    @execute_on_pair()
    def update(self,context=None):
        result = super(BdiInterface, self).update(context=context)
        self.ncc.update(context)
        # self.wsma.create(context)

        return result

    def to_dict(self):
        bdi = OrderedDict()
        bdi[L3Constants.NAME] = self.name
        bdi[L3Constants.DESCRIPTION] = self.description
        bdi[L3Constants.MAC_ADDRESS] = self.mac_address
        bdi[L3Constants.MTU] = self.mtu
        if self.shutdown:
            bdi[L3Constants.SHUTDOWN] = "[null]"

        ip = OrderedDict()
        ip[L3Constants.ADDRESS] = OrderedDict()
        ip[L3Constants.ADDRESS][L3Constants.PRIMARY] = OrderedDict()
        ip[L3Constants.ADDRESS][L3Constants.PRIMARY][L3Constants.ADDRESS] = self.ip_address.address
        ip[L3Constants.ADDRESS][L3Constants.PRIMARY][L3Constants.MASK] = self.ip_address.mask

        vrf = OrderedDict()
        vrf[L3Constants.FORWARDING] = self.vrf

        bdi[L3Constants.IP] = ip
        bdi[L3Constants.VRF] = vrf

        result = OrderedDict()
        result[L3Constants.BDI_INTERFACE] = bdi

        return dict(result)






class BDIPrimaryIpAddress(RestBase):
    LIST_KEY = L3Constants.PRIMARY

    list_path = "/Cisco-IOS-XE-native:native/interface/BDI={bridge_domain}/ip/address"
    item_path = "{}/{}".format(list_path, L3Constants.PRIMARY)

    @classmethod
    def __parameters__(cls):
        return [
            {"key": 'address', 'id': True},
            {'key': 'mask'},

        ]

    @classmethod
    def get(cls, bridge_domain,id):
        item_path = BDIPrimaryIpAddress.item_path.format(**{'bridge_domain': bridge_domain})
        return super(BDIPrimaryIpAddress,cls).get(id,item_path=item_path)

    def __init__(self, **kwargs):
        super(BDIPrimaryIpAddress, self).__init__(**kwargs)
        self.bridge_domain = kwargs.get('bridge_domain')
        self.list_path = BDIPrimaryIpAddress.list_path.format(**{'bridge_domain': self.bridge_domain})
        self.item_path = BDIPrimaryIpAddress.item_path.format(**{'bridge_domain': self.bridge_domain})

    def to_dict(self):
        ip = OrderedDict()
        primary = OrderedDict()
        primary[L3Constants.ADDRESS] = self.address
        primary[L3Constants.MASK] = self.mask
        ip[L3Constants.PRIMARY] = primary

        return ip


class BDISecondaryIpAddress(RestBase):
    LIST_KEY = L3Constants.SECONDARY

    list_path = "/Cisco-IOS-XE-native:native/interface/BDI={bridge_domain}/ip/address"
    item_path = "{}/{}".format(list_path, L3Constants.SECONDARY)



    @classmethod
    def __parameters__(cls):
        return [
            {"key": 'address', 'id': True},
            {'key': 'mask'},
            {'key': 'secondary','default':True}

        ]

    @classmethod
    def get(cls, bridge_domain,id):
        item_path = BDISecondaryIpAddress.item_path.format(**{'bridge_domain': bridge_domain})
        return super(BDISecondaryIpAddress,cls).get(id,item_path=item_path)


    def __init__(self, **kwargs):
        super(BDISecondaryIpAddress, self).__init__(**kwargs)
        self.bridge_domain = kwargs.get('bridge_domain')
        self.list_path = BDISecondaryIpAddress.list_path.format(**{'bridge_domain': self.bridge_domain})
        self.item_path = BDISecondaryIpAddress.item_path.format(**{'bridge_domain': self.bridge_domain})

    def to_dict(self):
        ip = OrderedDict()
        secondary = OrderedDict()
        secondary[L3Constants.ADDRESS] = self.address
        secondary[L3Constants.MASK] = self.mask
        if self.secondary:
            secondary['secondary'] = "[null]"
        ip[L3Constants.SECONDARY] = secondary

        return ip
