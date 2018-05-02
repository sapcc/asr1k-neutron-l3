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
from asr1k_neutron_l3.common import utils

class RouteMapConstants(object):
    ROUTE_MAP = 'route-map'
    ROUTE_MAP_SEQ = "route-map-without-order-seq"

    NAME = "name"
    ORDERING_SEQ = "seq_no"
    OPERATION = "operation"
    SET = "set"
    EXTCOMMUNITY='extcommunity'
    RT = 'rt'
    RANGE = 'range'
    ADDITIVE = 'additive'
    MATCH = "match"
    IP = "ip"
    NEXT_HOP = "next-hop"
    ADDRESS = "address"
    ASN = "asn-nn"
    PREFIX_LIST = "prefix-list"
    ACCESS_LIST = "access-list"


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
            {'key': 'seq', 'yang-key':'route-map-without-order-seq','type':[MapSequence],'default':[]},
        ]

    def __init__(self,**kwargs):
        super(RouteMap, self).__init__(**kwargs)
        self.ncc = nc_route_map.RouteMap(self)
        self.force_delete = False

    @property
    def neutron_router_id(self):
        if self.name is not None and (self.name.startswith('ext-') or self.name.startswith('pbr-')):
            return utils.vrf_id_to_uuid(self.name[4:])


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


    @classmethod
    def remove_wrapper(cls,dict):
        dict = super(RouteMap, cls)._remove_base_wrapper(dict)
        return dict





    def to_delete_dict(self):
        result = OrderedDict()

        map = OrderedDict()

        map[RouteMapConstants.NAME] = self.name
        result[self.ITEM_KEY] = map

        return dict(result)

    @execute_on_pair()
    def delete(self,context=None,method=NC_OPERATION.DELETE):
        if super(RouteMap, self)._internal_exists(context) or self.force_delete:
            self.ncc.delete(context)
            # result = super(RouteMap, self)._delete(context=context,method=method)
            # print result



    @execute_on_pair()
    def update(self,context=None):

        return super(RouteMap, self)._update(context=context,method=NC_OPERATION.PUT)


class MapSequence(NyBase):

    LIST_KEY = RouteMapConstants.ROUTE_MAP
    ITEM_KEY = RouteMapConstants.ROUTE_MAP_SEQ

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'seq_no','yang-key':'seq_no','id':True},
            {'key': 'operation'},
            {'key': 'asn','yang-key':'asn-nn','yang-path':'set/extcommunity/rt','type':[str]},
            {'key': 'next_hop', 'yang-key': 'address', 'yang-path': 'set/ip/next-hop/address'},
            {'key': 'prefix_list', 'yang-key':'prefix-list','yang-path':'match/ip/address'},
            {'key': 'access_list', 'yang-key': 'access-list', 'yang-path': 'match/ip/address'},
        ]

    def __init__(self,**kwargs):
        super(MapSequence, self).__init__(**kwargs)
        if self.asn is not None and not isinstance(self.asn,list):
            self.asn = [self.asn]

        self.enable_bgp =  kwargs.get('enable_bgp',False)

    def to_dict(self):

        seq = OrderedDict()
        seq[RouteMapConstants.ORDERING_SEQ] = self.seq_no

        seq[RouteMapConstants.OPERATION] = self.operation

        if bool(self.asn):
            seq[RouteMapConstants.SET] = {RouteMapConstants.EXTCOMMUNITY:{RouteMapConstants.RT:{RouteMapConstants.ASN:self.asn}}}

        if self.next_hop is not None:
            seq[RouteMapConstants.SET] = {
                RouteMapConstants.IP: {RouteMapConstants.NEXT_HOP:{RouteMapConstants.ADDRESS:self.next_hop}}}

        if self.prefix_list is not None:
            seq[RouteMapConstants.MATCH] = {RouteMapConstants.IP: {RouteMapConstants.ADDRESS: {
                                                                               RouteMapConstants.PREFIX_LIST: self.prefix_list}}}

        if self.access_list is not None:
            seq[RouteMapConstants.MATCH] = {RouteMapConstants.IP: {RouteMapConstants.ADDRESS: {
                                                                               RouteMapConstants.ACCESS_LIST: self.access_list}}}

        seq[xml_utils.NS] = xml_utils.NS_CISCO_ROUTE_MAP


        return seq


    def to_delete_dict(self):

        seq = OrderedDict()
        seq[RouteMapConstants.ORDERING_SEQ] = self.seq_no

        seq[RouteMapConstants.OPERATION] = self.operation

        seq[xml_utils.NS] = xml_utils.NS_CISCO_ROUTE_MAP


        return seq
