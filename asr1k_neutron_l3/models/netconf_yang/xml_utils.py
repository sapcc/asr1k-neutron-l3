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

import json

import xmltodict
from collections import OrderedDict
from oslo_log import log as logging

ENCODING = '<?xml version="1.0" encoding="utf-8"?>'
OPERATION = '@operation'

NS = '@xmlns'
NS_NETCONF_BASE = 'urn:ietf:params:xml:ns:netconf:base:1.0'
NS_CISCO_NATIVE = 'http://cisco.com/ns/yang/Cisco-IOS-XE-native'
NS_CISCO_ETHERNET = 'http://cisco.com/ns/yang/Cisco-IOS-XE-ethernet'
NS_CISCO_NAT = "http://cisco.com/ns/yang/Cisco-IOS-XE-nat"
NS_CISCO_ACL = 'http://cisco.com/ns/yang/Cisco-IOS-XE-acl'
NS_CISCO_BGP = 'http://cisco.com/ns/yang/Cisco-IOS-XE-bgp'
NS_CISCO_ROUTE_MAP = 'http://cisco.com/ns/yang/Cisco-IOS-XE-route-map'
NS_CISCO_EFP_OPER = 'http://cisco.com/ns/yang/Cisco-IOS-XE-efp-oper'
NS_CISCO_ARP = 'http://cisco.com/ns/yang/Cisco-IOS-XE-arp'
NS_CISCO_BRIDGE_DOMAIN = 'http://cisco.com/ns/yang/Cisco-IOS-XE-bridge-domain'
NS_CISCO_NTP = 'http://cisco.com/ns/yang/Cisco-IOS-XE-ntp'
NS_CISCO_ARP_OPER = 'http://cisco.com/ns/yang/Cisco-IOS-XE-arp-oper'
NS_IETF_INTERFACE = "urn:ietf:params:xml:ns:yang:ietf-interfaces"
NS_CISCO_POLICY = "http://cisco.com/ns/yang/Cisco-IOS-XE-policy"
NS_CISCO_ZONE = "http://cisco.com/ns/yang/Cisco-IOS-XE-zone"

RPC_REPLY = 'rpc-reply'
CONFIG = 'config'
DATA = 'data'
IOS_NATIVE = 'native'
CLI_CONFIG = 'cli-config-data'

LOG = logging.getLogger(__name__)


class JsonDict(dict):
    def __str__(self):
        return json.dumps(self, sort_keys=False)


class XMLUtils(object):
    namespaces = {
        NS_NETCONF_BASE: None,
        NS_CISCO_NATIVE: None,
        NS_CISCO_ETHERNET: None,
        NS_CISCO_NAT: None,
        NS_CISCO_ACL: None,
        NS_CISCO_BGP: None,
        NS_CISCO_ROUTE_MAP: None,
        NS_CISCO_EFP_OPER: None,
        NS_CISCO_ARP: None,
        NS_IETF_INTERFACE: None,
        NS_CISCO_BRIDGE_DOMAIN: None,
        NS_CISCO_NTP: None,
        NS_CISCO_ARP_OPER: None,
        NS_CISCO_POLICY: None,
        NS_CISCO_ZONE: None,
    }

    @classmethod
    def to_raw_json(cls, xml):
        return xmltodict.parse(xml, process_namespaces=True, namespaces=cls.namespaces, namespace_separator=' ')

    @classmethod
    def to_json(cls, xml, context):
        result = cls.to_raw_json(xml)
        result = cls.remove_wrapper(result, context)

        return cls._to_plain_json(result)

    @classmethod
    def _to_plain_json(cls, dict):
        return json.loads(json.dumps(dict))

    @classmethod
    def remove_wrapper(cls, dict, context):
        dict = cls._remove_base_wrapper(dict, context)
        if dict is None:
            return
        if cls.LIST_KEY is not None:
            dict = dict.get(cls.LIST_KEY, dict)
        return dict

    @classmethod
    def _remove_base_wrapper(cls, dict, context):
        if dict is None:
            return

        dict = dict.get(RPC_REPLY, dict)
        dict = dict.get(DATA, dict)
        if dict is None:
            return
        dict = dict.get(IOS_NATIVE, dict)

        return dict

    def _wrapper_preamble(self, dict, context):
        if self.LIST_KEY is not None:
            dict = {self.LIST_KEY: dict}

        return dict

    def add_wrapper(self, dict, operation, context):
        if operation and operation != 'override':
            if isinstance(dict, list):
                for item in dict:
                    item[self.get_item_key(context)][OPERATION] = operation

            elif isinstance(dict[self.get_item_key(context)], list):
                for item in dict[self.get_item_key(context)]:
                    item[OPERATION] = operation
            else:
                dict[self.get_item_key(context)][OPERATION] = operation

        dict = self._wrapper_preamble(dict, context)
        dict[NS] = NS_CISCO_NATIVE

        result = OrderedDict()
        result[IOS_NATIVE] = dict
        result[NS] = NS_NETCONF_BASE

        dict = {CONFIG: result}

        return dict

    def to_delete_dict(self, context):
        return self.to_dict(context)

    def to_xml(self, context, json=None, operation=None):
        if json is None:
            json = self.to_dict(context)

        j = self.add_wrapper(json, operation, context)

        xml = xmltodict.unparse(j)
        xml = xml.replace(ENCODING, "")

        return xml
