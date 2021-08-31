# Copyright 2021 SAP SE
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

from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase
from asr1k_neutron_l3.models.netconf_yang import xml_utils


class ClassMapConstants:
    POLICY = 'policy'
    CLASS_MAP = 'class-map'

    NAME = 'name'
    TYPE = 'type'
    PREMATCH = 'prematch'
    MATCH = 'match'

    ACCESS_GROUP = 'access-group'
    ACCESS_GROUP_NAME = 'name'


class ClassMap(NyBase):
    ID_FILTER = """
                <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                    <policy>
                        <class-map xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-policy">
                            <name>{id}</name>
                        </class-map>
                    </policy>
                </native>
                """

    GET_ALL_STUB = """
                <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                    <policy>
                        <class-map xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-policy">
                        </class-map>
                    </policy>
                </native>
                """

    LIST_KEY = None
    ITEM_KEY = ClassMapConstants.CLASS_MAP

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'id', 'id': True, 'yang-key': 'name'},
            {'key': 'type'},
            {'key': 'prematch'},
            {'key': 'acl_id', 'yang-key': 'name', 'yang-path': 'match/access-group'}
        ]

    @classmethod
    def remove_wrapper(cls, content, context):
        content = super()._remove_base_wrapper(content, context)
        if content is None:
            return
        return content.get(ClassMapConstants.POLICY, None)

    def _wrapper_preamble(self, content, context):
        policy = {}
        policy[ClassMapConstants.POLICY] = content
        return policy

    def to_dict(self, context):
        _C = ClassMapConstants
        content = {}

        content[xml_utils.NS] = xml_utils.NS_CISCO_POLICY
        content[_C.NAME] = self.id
        content[_C.TYPE] = self.type
        content[_C.PREMATCH] = self.prematch
        content[_C.MATCH] = {}
        content[_C.MATCH][_C.ACCESS_GROUP] = {}
        content[_C.MATCH][_C.ACCESS_GROUP][_C.ACCESS_GROUP_NAME] = self.acl_id

        return {self.ITEM_KEY: content}
