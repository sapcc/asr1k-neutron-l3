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


class ACLConstants(object):
    EXTENDED = "Cisco-IOS-XE-acl:extended"
    NAME = "name"
    RULE = "access-list-seq-rule"
    SEQUENCE = "sequence"
    ACE_RULE = "ace-rule"
    ACTION = 'action'
    PROTOCOL = 'protocol'
    IP = 'ip'
    PERMIT = 'permit'
    DENY = 'deny'
    ANY = 'any'
    DST_ANY = 'dst-any'


class AccessList(RestBase):
    LIST_KEY = ACLConstants.EXTENDED

    list_path = "/Cisco-IOS-XE-native:native/ip/access-list"
    item_path = "{}/{}".format(list_path, ACLConstants.EXTENDED)

    @classmethod
    def __parameters__(cls):
        return [
            {"key": "name", "id": True},
            {'key': 'rules', 'default': []}
        ]

    def __init__(self, context, **kwargs):
        super(AccessList, self).__init__(context, **kwargs)

    def add_rule(self, rule):
        self.rules.append(rule)

    def to_dict(self):
        entry = OrderedDict()
        entry[ACLConstants.NAME] = self.name
        # entry[ACLConstants.RULE]=self.rules
        entry[ACLConstants.RULE] = []
        for rule in self.rules:
            entry[ACLConstants.RULE].append(rule.to_child_dict())

        result = OrderedDict()
        result[ACLConstants.EXTENDED] = entry

        return dict(result)


class ACLRule(RestBase):
    list_path = "/Cisco-IOS-XE-native:native/ip/access-list/extended={access_list}"
    item_path = list_path + "/access-list-seq-rule"

    def __parameters__(self):
        return [
            {"key": "sequence", "id": True},
            {'key': 'access_list', 'mandatory': True},
            {'key': 'action'},
            {'key': 'protocol'},
            {'key': 'source'},
            {'key': 'destination'}

        ]

    def __init__(self, context, **kwargs):
        super(ACLRule, self).__init__(context, **kwargs)

        self.list_path = ACLRule.list_path.format(**{'access_list': urllib.quote(self.access_list)})
        self.item_path = ACLRule.item_path.format(**{'access_list': urllib.quote(self.access_list)})

    def to_child_dict(self):
        entry = OrderedDict()
        entry[ACLConstants.SEQUENCE] = self.id
        entry[ACLConstants.ACE_RULE] = OrderedDict()
        entry[ACLConstants.ACE_RULE][ACLConstants.ACTION] = self.action
        entry[ACLConstants.ACE_RULE][ACLConstants.PROTOCOL] = self.protocol

        if self.source == ACLConstants.ANY:
            entry[ACLConstants.ACE_RULE][ACLConstants.ANY] = "[null]"
        else:
            pass

        if self.destination == ACLConstants.ANY:
            entry[ACLConstants.ACE_RULE][ACLConstants.DST_ANY] = "[null]"
        else:
            pass

        return entry

    def to_dict(self):

        result = OrderedDict()
        result[ACLConstants.RULE] = self.to_child_dict()

        return dict(result)
