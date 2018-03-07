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

from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase,xml_utils,execute_on_pair,NC_OPERATION
from asr1k_neutron_l3.models.netconf_legacy import route_map as nc_route_map

class RouteMapConstants(object):
    ROUTE_MAP = 'route-map'
    ROUTE_MAP_SEQ = "route-map-seq"

    NAME = "name"
    ORDERING_SEQ = "ordering-seq"
    OPERATION = "operation"
    SET = "set"
    EXTCOMMUNITY='extcommunity'
    RT = 'rt'
    RANGE = 'range'
    ADDITIVE = 'additive'
    MATCH = "match"
    IP = "ip"
    ADDRESS = "address"
    ASN = "asn-nn"
    PREFIX_LIST = "prefix-list"


class RouteMap(NyBase):
    ID_FILTER = """
                <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native" xmlns:ios-route-map="http://cisco.com/ns/yang/Cisco-IOS-XE-route-map">
                    <route-map>
                            <name>{id}</name>
                    </route-map>
                </native>            
             """

    LIST_KEY = None
    ITEM_KEY = RouteMapConstants.ROUTE_MAP

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'name','id':True},
            {'key': 'seq', 'yang-key':'route-map-seq','type':[MapSequence],'default':[]},
        ]

    def __init__(self,**kwargs):
        super(RouteMap, self).__init__(**kwargs)
        self.ncc = nc_route_map.RouteMap(self)

    def to_dict(self):


        result = OrderedDict()

        map = OrderedDict()

        map[RouteMapConstants.NAME] = self.name
        map[RouteMapConstants.ROUTE_MAP_SEQ] = []
        for item in self.seq:
            if item is not None:
                map[RouteMapConstants.ROUTE_MAP_SEQ].append(item.to_dict())

        result[self.ITEM_KEY] = map

        return dict(result)


    def to_delete_dict(self):
        result = OrderedDict()

        map = OrderedDict()

        map[RouteMapConstants.NAME] = self.name
        result[self.ITEM_KEY] = map

        return dict(result)

    @execute_on_pair()
    def delete(self,context=None,method=NC_OPERATION.REMOVE):

        self.ncc.delete(context)
        #result = super(DynamicNat, self).delete(context=context)




class MapSequence(NyBase):

    LIST_KEY = RouteMapConstants.ROUTE_MAP
    ITEM_KEY = RouteMapConstants.ROUTE_MAP_SEQ

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'ordering_seq','id':True,'yang-key':'ordering-seq'},
            {'key': 'operation'},
            {'key': 'asn','yang-key':'asn-nn','yang-path':'set/extcommunity/rt','type':[str]},
            {'key': 'prefix_list', 'yang-key':'prefix-list','yang-path':'match/ip/address'},
        ]

    def __init__(self,**kwargs):
        super(MapSequence, self).__init__(**kwargs)
        if self.asn is not None and not isinstance(self.asn,list):
            self.asn = [self.asn]

        self.disable_bgp =  kwargs.get('disable_bgp',True)

    def to_dict(self):

        seq = OrderedDict()
        seq[RouteMapConstants.ORDERING_SEQ] = self.ordering_seq

        seq[RouteMapConstants.OPERATION] = self.operation


        if not self.disable_bgp:
            seq[RouteMapConstants.SET] = {RouteMapConstants.EXTCOMMUNITY:{RouteMapConstants.RT:{RouteMapConstants.ASN:self.asn}}}

        if self.prefix_list is not None:
            seq[RouteMapConstants.MATCH] = {RouteMapConstants.IP: {RouteMapConstants.ADDRESS: {
                                                                               RouteMapConstants.PREFIX_LIST: self.prefix_list}}}

        seq[xml_utils.NS] = xml_utils.NS_CISCO_ROUTE_MAP


        return seq
