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

import urllib
from collections import OrderedDict

from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase,execute_on_pair
from asr1k_neutron_l3.models.netconf_yang import xml_utils
from asr1k_neutron_l3.common import utils

class ACLConstants(object):
    ACCESS_LIST = "access-list"
    EXTENDED = "extended"
    NAME = "name"
    ACL_RULE = "access-list-seq-rule"
    SEQUENCE = "sequence"
    ACE_RULE = "ace-rule"
    ACTION = 'action'
    PROTOCOL = 'protocol'
    IP = 'ip'
    PERMIT = 'permit'
    DENY = 'deny'
    ANY = 'any'
    DST_ANY = 'dst-any'
    SOURCE_IP = 'ipv4-address'
    SOURCE_MASK ='mask'
    DEST_IP = 'dest-ipv4-address'
    DEST_MASK ='dest-mask'


class AccessList(NyBase):
    ID_FILTER = """
                    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native" xmlns:ios-acl="http://cisco.com/ns/yang/Cisco-IOS-XE-acl">
                        <ip>
                          <access-list>
                            <ios-acl:extended>
                                <ios-acl:name>{name}</ios-acl:name>
                            </ios-acl:extended>
                          </access-list>
                        </ip>
                    </native>
                """

    LIST_KEY = ACLConstants.ACCESS_LIST
    ITEM_KEY = ACLConstants.EXTENDED


    @classmethod
    def __parameters__(cls):
        return [
            {"key": "name", "id": True},
            {'key': 'rules','yang-key':"access-list-seq-rule", 'type':[ACLRule],'default': []}
        ]

    @classmethod
    def get_primary_filter(cls,**kwargs):
        return cls.ID_FILTER.format(**{'name': kwargs.get('name')})


    @classmethod
    def remove_wrapper(cls,dict):
        dict = super(AccessList, cls)._remove_base_wrapper(dict)

        if dict is not None:
            dict = dict.get(ACLConstants.IP,dict)
            dict = dict.get(cls.LIST_KEY, dict)

        return dict

    def _wrapper_preamble(self,dict):
        result = {}
        dict[self.ITEM_KEY][xml_utils.NS] = xml_utils.NS_CISCO_ACL
        result[self.LIST_KEY] = dict
        result = {ACLConstants.IP: result}
        return result


    def __init__(self, **kwargs):
        super(AccessList, self).__init__(**kwargs)

    @property
    def neutron_router_id(self):
        if self.name is not None and (self.name.startswith('NAT-') or self.name.startswith('PBR-')):
            return utils.vrf_id_to_uuid(self.name[4:])

    def add_rule(self, rule):
        self.rules.append(rule)

    def to_dict(self):
        entry = OrderedDict()
        entry[ACLConstants.NAME] = self.name
        # entry[ACLConstants.ACL_RULE]=self.rules
        entry[ACLConstants.ACL_RULE] = []
        for rule in self.rules:
            entry[ACLConstants.ACL_RULE].append(rule.to_child_dict())

        result = OrderedDict()
        result[ACLConstants.EXTENDED] = entry

        return dict(result)

    @execute_on_pair()
    def update(self,context=None):
        #we need to check if the ACL needs to be updated, if it does selectively delete,
        # because we can't easily update individual rules
        if len(self._internal_validate(context=context)) > 0:
            super(AccessList, self)._delete(context=context)

        return super(AccessList, self)._update(context=context)


class ACLRule(NyBase):
    LIST_KEY = ACLConstants.ACL_RULE

    @classmethod
    def __parameters__(cls):
        return [
            {"key": "sequence", "id": True},
            {'key': 'access_list','validate':False,'primary_key':True,'default':""},
            {'key': 'ace_rule','type':[ACERule]},

        ]

    def __init__(self, **kwargs):
        super(ACLRule, self).__init__(**kwargs)

    def to_child_dict(self):
        entry = OrderedDict()
        entry[ACLConstants.SEQUENCE] = self.id



        entry[ACLConstants.ACE_RULE] = []

        for ace_rule in self.ace_rule:
            entry[ACLConstants.ACE_RULE].append(ace_rule.to_child_dict())


        return entry

    def to_dict(self):

        result = OrderedDict()
        result[ACLConstants.ACL_RULE] = self.to_child_dict()

        return dict(result)


class ACERule(NyBase):
    LIST_KEY = ACLConstants.ACE_RULE

    @classmethod
    def __parameters__(cls):
        return [

            {'key': 'access_list', 'validate': False,'default':""},
            {'key': 'acl_rule', 'validate':False,'default':""},
            {'key': 'action','id':True},
            {'key': 'protocol'},
            {'key': 'any','default':None},
            {'key': 'ipv4_address'},
            {'key': 'mask'},
            {'key': 'dst_any', 'default':None},
            {'key': 'dest_ipv4_address'},
            {'key': 'dest_mask'}

        ]


    def __init__(self, **kwargs):
        super(ACERule, self).__init__( **kwargs)

    def to_child_dict(self):
        ace_rule = OrderedDict()
        ace_rule[ACLConstants.ACTION] = self.action
        ace_rule[ACLConstants.PROTOCOL] = self.protocol

        if self.ipv4_address is None:
            ace_rule[ACLConstants.ANY] = ""
        else:
            ace_rule[ACLConstants.SOURCE_IP] = self.ipv4_address
            ace_rule[ACLConstants.SOURCE_MASK] = self.mask

        if self.dest_ipv4_address is None:
            ace_rule[ACLConstants.DST_ANY] = ""
        else:
            ace_rule[ACLConstants.DEST_IP] = self.dest_ipv4_address
            ace_rule[ACLConstants.DEST_MASK] = self.dest_mask

        return ace_rule

    def to_dict(self):

        result = OrderedDict()
        result[ACLConstants.ACE_RULE] = self.to_child_dict()

        return dict(result)