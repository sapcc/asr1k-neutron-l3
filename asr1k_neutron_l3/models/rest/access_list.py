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

from asr1k_neutron_l3.models.rest.rest_base import RestBase
from asr1k_neutron_l3.models.rest.rest_base import execute_on_pair

class ACLConstants(object):
    EXTENDED = "Cisco-IOS-XE-acl:extended"
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


class AccessList(RestBase):
    LIST_KEY = ACLConstants.EXTENDED

    list_path = "/Cisco-IOS-XE-native:native/ip/access-list"
    item_path = "{}/{}".format(list_path, ACLConstants.EXTENDED)

    @classmethod
    def __parameters__(cls):
        return [
            {"key": "name", "id": True},
            {'key': 'rules','yang-key':"access-list-seq-rule", 'type':ACLRule,'default': []}
        ]

    def __init__(self, **kwargs):
        super(AccessList, self).__init__(**kwargs)

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
        super(AccessList, self).delete(context=context)
        super(AccessList, self).update(context=context)


class ACLRule(RestBase):
    LIST_KEY = ACLConstants.ACL_RULE
    list_path = "/Cisco-IOS-XE-native:native/ip/access-list/extended={access_list}"
    item_path = "{}/{}".format(list_path, ACLConstants.ACL_RULE)

    @classmethod
    def __parameters__(cls):
        return [
            {"key": "sequence", "id": True},
            {'key': 'access_list','validate':False,'default':""},
            {'key': 'ace_rule','type':ACERule},

        ]

    @classmethod
    def get(cls, access_list,id):
        item_path = ACLRule.item_path.format(**{'access_list': access_list})
        return super(ACLRule,cls).get(id,item_path=item_path)

    def __init__(self, **kwargs):
        super(ACLRule, self).__init__(**kwargs)

        self.list_path = ACLRule.list_path.format(**{'access_list': urllib.quote(self.access_list)})
        self.item_path = ACLRule.item_path.format(**{'access_list': urllib.quote(self.access_list)})

    def to_child_dict(self):
        entry = OrderedDict()
        entry[ACLConstants.SEQUENCE] = self.id

        entry[ACLConstants.ACE_RULE] = self.ace_rule.to_child_dict()

        return entry

    def to_dict(self):

        result = OrderedDict()
        result[ACLConstants.ACL_RULE] = self.to_child_dict()

        return dict(result)


class ACERule(RestBase):
    LIST_KEY = ACLConstants.ACE_RULE
    list_path = "/Cisco-IOS-XE-native:native/ip/access-list/extended={access_list}/access-list-seq-rule={acl_sequence}"
    item_path = "{}/{}".format(list_path, ACLConstants.ACE_RULE)

    @classmethod
    def __parameters__(cls):
        return [

            {'key': 'access_list', 'validate': False,'default':""},
            {'key': 'acl_rule', 'validate':False,'default':""},
            {'key': 'action','id':True},
            {'key': 'protocol'},
            {'key': 'any','default':[None]},
            {'key': 'ipv4_address'},
            {'key': 'mask'},
            {'key': 'dst_any', 'default':[None]},
            {'key': 'dest_ipv4_address'},
            {'key': 'dest_mask'}

        ]

    @classmethod
    def get(cls, access_list,acl_rule,id):
        item_path = ACERule.item_path.format(**{'access_list': access_list,'acl_sequence':acl_rule})
        return super(ACERule,cls).get(id,item_path=item_path)

    def __init__(self, **kwargs):
        super(ACERule, self).__init__( **kwargs)

        self.list_path = ACERule.list_path.format(**{'access_list': urllib.quote(self.access_list),'acl_sequence':self.acl_rule})
        self.item_path = ACERule.item_path.format(**{'access_list': urllib.quote(self.access_list),'acl_sequence':self.acl_rule})

    def to_child_dict(self):
        ace_rule = OrderedDict()
        ace_rule[ACLConstants.ACTION] = self.action
        ace_rule[ACLConstants.PROTOCOL] = self.protocol

        if self.ipv4_address is None:
            ace_rule[ACLConstants.ANY] = "[null]"
        else:
            ace_rule[ACLConstants.SOURCE_IP] = self.ipv4_address
            ace_rule[ACLConstants.SOURCE_MASK] = self.mask

        if self.dest_ipv4_address is None:
            ace_rule[ACLConstants.DST_ANY] = "[null]"
        else:
            ace_rule[ACLConstants.DEST_IP] = self.dest_ipv4_address
            ace_rule[ACLConstants.DEST_MASK] = self.dest_mask

        return ace_rule

    def to_dict(self):

        result = OrderedDict()
        result[ACLConstants.ACE_RULE] = self.to_child_dict()

        return dict(result)