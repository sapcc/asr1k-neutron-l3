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

from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase,execute_on_pair
from asr1k_neutron_l3.models.netconf_yang import xml_utils


class BGPConstants(object):
    ROUTER = 'router'
    BGP = "bgp"

    ID = "id"
    ADDRESS_FAMILY = "address-family"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    WITH_VRF = "with-vrf"
    AF_NAME = "af-name"
    NAME = "name"
    VRF = "vrf"
    REDISTRIBUTE = "redistribute"
    CONNECTED = "connected"
    STATIC = "static"
    UNICAST = "unicast"


class AddressFamiliy(NyBase):
    ID_FILTER = """
                  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native" xmlns:ios-bgp="http://cisco.com/ns/yang/Cisco-IOS-XE-bgp">
                    <router>
                      <ios-bgp:bgp>
                        <ios-bgp:id>{fabric_asn}</ios-bgp:id>
                        <address-family>
                            <with-vrf>
                                <ipv4>
                                    <vrf>
                                    <name>{id}</name>
                                    </vrf>
                                </ipv4>
                            </with-vrf>                                                            
                        </address-family>
                      </ios-bgp:bgp>
                    </router>
                  </native>         
             """

    LIST_KEY = BGPConstants.IPV4
    ITEM_KEY = BGPConstants.VRF

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'asn'},
            {'key': 'id'}
        ]

    @classmethod
    def get_primary_filter(cls,**kwargs):
        return cls.ID_FILTER.format(**{'id': kwargs.get('id'),'fabric_asn':kwargs.get('asn')})

    @classmethod
    @execute_on_pair(return_raw=True)
    def get(cls,asn,id, context=None):
        return super(AddressFamiliy, cls)._get(id=id, asn=asn,context=context)

    @classmethod
    @execute_on_pair(return_raw=True)
    def exists(cls, asn,id, context=None):
        return super(AddressFamiliy, cls)._exists(id=id, asn=asn, context=context)

    @classmethod
    def remove_wrapper(cls,dict):
        dict = super(AddressFamiliy, cls)._remove_base_wrapper(dict)
        if dict is not None:
            dict = dict.get(BGPConstants.ROUTER,dict)
            dict = dict.get(BGPConstants.BGP, dict)
            dict = dict.get(BGPConstants.ADDRESS_FAMILY, dict)
            dict = dict.get(BGPConstants.WITH_VRF, dict)
            dict = dict.get(BGPConstants.IPV4, dict)

        return dict

    def _wrapper_preamble(self,dict):
        dict[BGPConstants.AF_NAME]= BGPConstants.UNICAST
        result = {}
        result[self.LIST_KEY] = dict
        result = {BGPConstants.WITH_VRF:result}

        bgp = OrderedDict()
        bgp[BGPConstants.ID] = self.asn
        bgp[BGPConstants.ADDRESS_FAMILY]= result
        bgp[xml_utils.NS]=xml_utils.NS_CISCO_BGP
        result = {BGPConstants.BGP: bgp,}
        result = {BGPConstants.ROUTER: result}
        return result



    def __init__(self,**kwargs):
        super(AddressFamiliy, self).__init__(**kwargs)





    def to_dict(self):

        vrf = OrderedDict()
        vrf[BGPConstants.NAME] = self.id
        vrf[BGPConstants.REDISTRIBUTE] = {BGPConstants.CONNECTED:'',BGPConstants.STATIC:''}

        result = OrderedDict()

        result[BGPConstants.VRF] = vrf

        return dict(result)


