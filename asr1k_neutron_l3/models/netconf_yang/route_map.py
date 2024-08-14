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

from asr1k_neutron_l3.models.netconf_yang import xml_utils
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair, NC_OPERATION, YANG_TYPE
from asr1k_neutron_l3.common import utils


class RouteMapConstants(object):
    ROUTE_MAP = 'route-map'
    ROUTE_MAP_SEQ = "route-map-without-order-seq"

    NAME = "name"
    ORDERING_SEQ = "seq_no"
    OPERATION = "operation"
    SET = "set"
    EXTCOMMUNITY = 'extcommunity'
    COMMUNITY = 'community'
    COMMUNITY_WELL_KNOWN = 'community-well-known'
    COMMUNITY_LIST = 'community-list'
    RT = 'rt'
    RANGE = 'range'
    ADDITIVE = 'additive'
    MATCH = "match"
    IP = "ip"
    FORCE = "force"
    NEXT_HOP = "next-hop"
    NEXT_HOP_ADDR = "next-hop-addr"
    ADDRESS = "address"
    ASN = "asn-nn"
    PREFIX_LIST = "prefix-list"
    ACCESS_LIST = "access-list"
    PRECEDENCE = "precedence"
    PRECEDENCE_FIELDS = "precedence-fields"


class RouteMap(NyBase):
    ID_FILTER = """
            <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                    xmlns:ios-route-map="http://cisco.com/ns/yang/Cisco-IOS-XE-route-map">
                <route-map>
                    <name>{id}</name>
                </route-map>
            </native>
    """

    GET_ALL_STUB = """
            <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
              <route-map>
                <name/>
              </route-map>
            </native>
    """

    LIST_KEY = None
    ITEM_KEY = RouteMapConstants.ROUTE_MAP

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'name', 'id': True},
            {'key': 'seq', 'yang-key': 'route-map-without-order-seq', 'type': [MapSequence], 'default': []},
        ]

    def __init__(self, **kwargs):
        super(RouteMap, self).__init__(**kwargs)
        self.force_delete = False

    @property
    def neutron_router_id(self):
        if self.name is not None and (self.name.startswith('exp-') or self.name.startswith('pbr-')):
            return utils.vrf_id_to_uuid(self.name[4:])

    def to_dict(self, context):
        result = OrderedDict()

        map = OrderedDict()

        map[RouteMapConstants.NAME] = self.name
        map[RouteMapConstants.ROUTE_MAP_SEQ] = []
        for item in self.seq:
            if item is not None and not (context.version_min_17_3 and item.drop_on_17_3):
                map[RouteMapConstants.ROUTE_MAP_SEQ].append(item.to_dict(context=context))

        result[self.ITEM_KEY] = map

        return dict(result)

    def to_delete_dict(self, context):
        result = OrderedDict()

        map = OrderedDict()

        map[RouteMapConstants.NAME] = self.name
        result[self.ITEM_KEY] = map

        return dict(result)

    @execute_on_pair()
    def update(self, context):
        return super(RouteMap, self)._update(context=context, method=NC_OPERATION.PUT)


class MapSequence(NyBase):
    LIST_KEY = RouteMapConstants.ROUTE_MAP
    ITEM_KEY = RouteMapConstants.ROUTE_MAP_SEQ

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'seq_no', 'yang-key': 'seq_no', 'id': True},
            {'key': 'operation'},
            {'key': 'asn', 'yang-key': 'asn-nn', 'yang-path': 'set/extcommunity/rt', 'type': [str]},
            {'key': 'next_hop', 'yang-key': 'address', 'yang-path': 'set/ip/next-hop/next-hop-addr'},
            {'key': 'force', 'yang-path': 'set/ip/next-hop/next-hop-addr', 'default': False,
             'yang-type': YANG_TYPE.EMPTY},
            {'key': 'prefix_list', 'yang-key': 'prefix-list', 'yang-path': 'match/ip/address'},
            {'key': 'access_list', 'yang-key': 'access-list', 'yang-path': 'match/ip/address'},
            {'key': 'ip_precedence', 'yang-path': 'set/ip/precedence', 'yang-key': 'precedence-fields'},
            {'key': 'community_list', 'yang-key': 'community-list', 'yang-path': 'set/community/community-well-known',
             'default': []},
            {'key': 'drop_on_17_3', 'default': False},
        ]

    def __init__(self, **kwargs):
        super(MapSequence, self).__init__(**kwargs)
        if self.asn is not None and not isinstance(self.asn, list):
            self.asn = [self.asn]

        self.enable_bgp = kwargs.get('enable_bgp', False)

    @classmethod
    def from_json(cls, json, context, *args, **kwargs):
        if context.version_min_17_3:
            nh = (json.get(RouteMapConstants.SET, {})
                      .get(RouteMapConstants.IP, {})
                      .get(RouteMapConstants.NEXT_HOP, {}))
            if nh:
                addrs = nh[RouteMapConstants.ADDRESS]
                nh[RouteMapConstants.NEXT_HOP_ADDR] = {RouteMapConstants.ADDRESS: addrs[0]}
                if addrs[-1] == 'force':
                    nh[RouteMapConstants.NEXT_HOP_ADDR][RouteMapConstants.FORCE] = None

        return super(MapSequence, cls).from_json(json, context, *args, **kwargs)

    def to_dict(self, context):
        seq = OrderedDict()
        seq[RouteMapConstants.ORDERING_SEQ] = self.seq_no
        seq[RouteMapConstants.OPERATION] = self.operation

        if self.asn:
            seq.setdefault(RouteMapConstants.SET, {})
            seq[RouteMapConstants.SET][RouteMapConstants.EXTCOMMUNITY] = {
                RouteMapConstants.RT: {RouteMapConstants.ASN: self.asn},
            }

        if self.next_hop is not None:
            seq.setdefault(RouteMapConstants.SET, {})
            if context.version_min_17_3:
                seq[RouteMapConstants.SET][RouteMapConstants.IP] = {
                    RouteMapConstants.NEXT_HOP: {RouteMapConstants.ADDRESS: [self.next_hop]},
                }
                if self.force:
                    # it looks like the force flag is now part of the address list in 17.3+
                    seq[RouteMapConstants.SET][RouteMapConstants.IP][RouteMapConstants.NEXT_HOP][
                        RouteMapConstants.ADDRESS].append(RouteMapConstants.FORCE)
            else:
                seq[RouteMapConstants.SET][RouteMapConstants.IP] = {
                    RouteMapConstants.NEXT_HOP: {
                        RouteMapConstants.NEXT_HOP_ADDR: {
                            RouteMapConstants.ADDRESS: self.next_hop}}}
                if self.force:
                    seq[RouteMapConstants.SET][RouteMapConstants.IP][RouteMapConstants.NEXT_HOP][
                        RouteMapConstants.NEXT_HOP_ADDR][RouteMapConstants.FORCE] = ""

        if self.prefix_list is not None:
            seq[RouteMapConstants.MATCH] = {
                RouteMapConstants.IP: {RouteMapConstants.ADDRESS: {RouteMapConstants.PREFIX_LIST: self.prefix_list}}}

        if self.access_list is not None:
            seq[RouteMapConstants.MATCH] = {
                RouteMapConstants.IP: {RouteMapConstants.ADDRESS: {RouteMapConstants.ACCESS_LIST: self.access_list}}}
        if self.ip_precedence:
            seq.setdefault(RouteMapConstants.SET, {})
            if RouteMapConstants.IP not in seq[RouteMapConstants.SET]:
                seq[RouteMapConstants.SET][RouteMapConstants.IP] = {}
            seq[RouteMapConstants.SET][RouteMapConstants.IP][RouteMapConstants.PRECEDENCE] = {
                RouteMapConstants.PRECEDENCE_FIELDS: self.ip_precedence,
            }
        if self.community_list:
            seq.setdefault(RouteMapConstants.SET, {})
            seq[RouteMapConstants.SET][RouteMapConstants.COMMUNITY] = {
                RouteMapConstants.COMMUNITY_WELL_KNOWN: {
                    RouteMapConstants.COMMUNITY_LIST: self.community_list,
                },
            }
        seq[xml_utils.NS] = xml_utils.NS_CISCO_ROUTE_MAP

        return seq

    def to_delete_dict(self, context):
        seq = OrderedDict()
        seq[RouteMapConstants.ORDERING_SEQ] = self.seq_no
        seq[RouteMapConstants.OPERATION] = self.operation
        seq[xml_utils.NS] = xml_utils.NS_CISCO_ROUTE_MAP

        return seq
