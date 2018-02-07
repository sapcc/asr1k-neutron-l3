import json

import xmltodict
from collections import OrderedDict

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

RPC_REPLY = 'rpc-reply'
CONFIG = 'config'
DATA = 'data'
IOS_NATIVE = 'native'
CLI_CONFIG = 'cli-config-data'


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
    }

    @classmethod
    def to_json(cls,xml):
        json = xmltodict.parse(xml,process_namespaces=True,namespaces=cls.namespaces)

        json = cls.remove_wrapper(json)

        return json

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

        print xml

        return xml