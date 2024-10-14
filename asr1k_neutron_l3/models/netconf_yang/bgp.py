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

from asr1k_neutron_l3.common.utils import from_cidr, to_cidr
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair, NC_OPERATION
from asr1k_neutron_l3.models.netconf_yang import xml_utils


class BGPConstants(object):
    ROUTER = 'router'
    BGP = "bgp"
    ASN = "asn"
    ID = "id"
    ADDRESS_FAMILY = "address-family"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    IPV4_UNICAST = "ipv4-unicast"
    WITH_VRF = "with-vrf"
    AF_NAME = "af-name"
    NAME = "name"
    VRF = "vrf"
    REDISTRIBUTE = "redistribute"
    REDISTRIBUTE_VRF = "redistribute-vrf"
    CONNECTED = "connected"
    STATIC = "static"
    UNICAST = "unicast"
    NETWORK = "network"
    WITH_MASK = "with-mask"
    NUMBER = "number"
    MASK = "mask"
    ROUTE_MAP = "route-map"


class AddressFamily(NyBase):
    ID_FILTER = """
        <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                  xmlns:ios-bgp="http://cisco.com/ns/yang/Cisco-IOS-XE-bgp">
            <router>
                <ios-bgp:bgp>
                    <ios-bgp:id>{asn}</ios-bgp:id>
                    <ios-bgp:address-family>
                        <ios-bgp:with-vrf>
                            <ios-bgp:ipv4>
                                <ios-bgp:af-name>unicast</ios-bgp:af-name>
                                <ios-bgp:vrf>
                                    <ios-bgp:name>{vrf}</ios-bgp:name>
                                </ios-bgp:vrf>
                            </ios-bgp:ipv4>
                        </ios-bgp:with-vrf>
                    </ios-bgp:address-family>
                </ios-bgp:bgp>
            </router>
        </native>
    """

    VRF_XPATH_FILTER = ("/native/router/bgp[id='{asn}']/address-family/with-vrf/"
                        "ipv4[af-name='unicast']/vrf[name='{vrf}']")
    LIST_KEY = BGPConstants.IPV4
    ITEM_KEY = BGPConstants.VRF

    @classmethod
    def get_for_vrf(cls, context, asn=None, vrf=None):
        return cls._get_all(context=context, xpath_filter=cls.VRF_XPATH_FILTER.format(asn=asn, vrf=vrf))

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'asn', 'id': True, 'yang-key': 'id'},
            {'key': 'vrf', 'yang-key': 'name'},
            {'key': 'networks_v4', 'yang-path': 'ipv4-unicast/network', 'yang-key': BGPConstants.WITH_MASK,
             'type': [Network], 'default': []},
        ]

    @classmethod
    def get_primary_filter(cls, **kwargs):
        return cls.ID_FILTER.format(asn=kwargs.get('asn'), vrf=kwargs.get('vrf'))

    @classmethod
    @execute_on_pair(return_raw=True)
    def get(cls, vrf, asn, context):
        return super(AddressFamily, cls)._get(vrf=vrf, asn=asn, context=context)

    @classmethod
    @execute_on_pair(return_raw=True)
    def exists(cls, vrf, asn, context):
        return super(AddressFamily, cls)._exists(vrf=vrf, asn=asn, context=context)

    @classmethod
    def remove_wrapper(cls, dict, context):
        dict = super(AddressFamily, cls)._remove_base_wrapper(dict, context)

        if dict is not None:
            dict = dict.get(BGPConstants.ROUTER, dict)
            dict = dict.get(BGPConstants.BGP, dict)
            asn = dict.get("id", None)
            dict = dict.get(BGPConstants.ADDRESS_FAMILY, dict)
            dict = dict.get(BGPConstants.WITH_VRF, dict)
            dict = dict.get(BGPConstants.IPV4, dict)

            if dict.get(BGPConstants.VRF, None) is not None:
                dict[BGPConstants.VRF]["id"] = asn
            else:
                dict[BGPConstants.VRF] = OrderedDict()
                dict[BGPConstants.VRF]["id"] = asn

        return dict

    def _wrapper_preamble(self, dict, context):
        af = OrderedDict()
        af[BGPConstants.AF_NAME] = BGPConstants.UNICAST
        af.update(dict)
        result = {}
        result[self.LIST_KEY] = af
        result = {BGPConstants.WITH_VRF: result}

        bgp = OrderedDict()
        bgp[BGPConstants.ID] = self.asn
        bgp[BGPConstants.ADDRESS_FAMILY] = result
        bgp[xml_utils.NS] = xml_utils.NS_CISCO_BGP
        result = {BGPConstants.BGP: bgp}
        result = {BGPConstants.ROUTER: result}
        return result

    def __init__(self, **kwargs):
        super(AddressFamily, self).__init__(**kwargs)

        self.enable_bgp = kwargs.get('enable_bgp', False)
        if self.asn is None:
            self.asn = kwargs.get("asn", None)

    def to_dict(self, context):
        result = OrderedDict()
        if self.vrf is not None:
            vrf = OrderedDict()
            vrf[BGPConstants.NAME] = self.vrf
            vrf[BGPConstants.IPV4_UNICAST] = {
                xml_utils.OPERATION: NC_OPERATION.PUT,
            }

            if self.networks_v4:
                vrf[BGPConstants.IPV4_UNICAST][BGPConstants.NETWORK] = {
                    BGPConstants.WITH_MASK: [
                        net.to_dict(context) for net in sorted(self.networks_v4, key=lambda x: (x.number, x.mask))
                    ]
                }
            result[BGPConstants.VRF] = vrf
        return dict(result)

    def to_delete_dict(self, context):
        result = OrderedDict()
        if self.vrf is not None:
            vrf = OrderedDict()
            vrf[BGPConstants.NAME] = self.vrf
            result[BGPConstants.VRF] = vrf

        return dict(result)

    def _delete_no_retry(self, context, *args, **kwargs):
        # only delete if present on device
        device_af = self._internal_get(context=context)
        if device_af and device_af.vrf:
            return super(AddressFamily, self)._delete_no_retry(context, *args, **kwargs)


class Network(NyBase):
    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'number'},
            {'key': 'mask'},
            {'key': 'route_map', 'yang-key': BGPConstants.ROUTE_MAP, 'default': None},
        ]

    @classmethod
    def from_cidr(cls, cidr, route_map=None):
        ip, netmask = from_cidr(cidr)
        return cls(number=ip, mask=netmask, route_map=route_map)

    @property
    def cidr(self):
        return to_cidr(self.number, str(self.mask))

    def to_dict(self, context):
        net = OrderedDict()
        net[BGPConstants.NUMBER] = self.number
        net[BGPConstants.MASK] = self.mask
        if self.route_map:
            net[BGPConstants.ROUTE_MAP] = self.route_map
        return net
