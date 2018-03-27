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
NS_IETF_INTERFACE = "urn:ietf:params:xml:ns:yang:ietf-interfaces"


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

    namespaces  = {
        NS_NETCONF_BASE:None,
        NS_CISCO_NATIVE:None,
        NS_CISCO_ETHERNET:None,
        NS_CISCO_NAT: None,
        NS_CISCO_ACL: None,
        NS_CISCO_BGP: None,
        NS_CISCO_ROUTE_MAP: None,
        NS_CISCO_EFP_OPER: None,
        NS_IETF_INTERFACE: None
    }



    @classmethod
    def to_json(cls,xml):
        result = xmltodict.parse(xml,process_namespaces=True,namespaces=cls.namespaces)

        result = cls.remove_wrapper(result)

        return cls._to_plain_json(result)

    @classmethod
    def _to_plain_json(cls,dict):
        return json.loads(json.dumps(dict))

    @classmethod
    def remove_wrapper(cls,dict):
        dict = cls._remove_base_wrapper(dict)
        if dict is None:
            return
        dict = dict.get(cls.LIST_KEY, dict)
        return dict

    @classmethod
    def _remove_base_wrapper(cls,dict):


        dict = dict.get(RPC_REPLY,dict)
        dict = dict.get(DATA, dict)
        if dict is None:
            return
        dict = dict.get(IOS_NATIVE, dict)


        return dict


    def _wrapper_preamble(self,dict):
        if self.LIST_KEY is not None:
            dict = {self.LIST_KEY: dict}

        return dict

    def add_wrapper(self,dict,operation):
        if operation:
            if isinstance( dict[self.ITEM_KEY],list):
                for item in dict[self.ITEM_KEY]:
                    item[OPERATION] = operation
            else:
                dict[self.ITEM_KEY][OPERATION] = operation

        dict = self._wrapper_preamble(dict)

        dict[NS]=NS_CISCO_NATIVE

        result = OrderedDict()
        result[IOS_NATIVE]=dict

        dict = {CONFIG: result}
        return dict

    def to_delete_dict(self):
        return self.to_dict();

    def to_xml(self,json=None, operation=None):

        if json is None:
            json = self.to_dict()

        j = self.add_wrapper(json, operation)

        xml = xmltodict.unparse(j)
        xml = xml.replace(ENCODING,"")

        return xml