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

from collections import OrderedDict

from asr1k_neutron_l3.models.netconf_yang import xml_utils
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, YANG_TYPE, NC_OPERATION




class ServicePolicyConstants():
    POLICY = 'policy'
    POLICY_MAP = 'policy-map'

    NAME = 'name'
    TYPE = 'type'
    CLASS = 'class'


class ServicePolicy(NyBase):
    ID_FILTER = """
                <native>
                    <policy>
                        <policy-map xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-policy">
                            <name>{id}</name>
                        </policy-map>
                    </policy>
                </native>
                """

    GET_ALL_STUB = """
                <native>
                    <policy>
                        <policy-map xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-policy">
                        </policy-map>
                    </policy>
                </native>
                """

    LIST_KEY = None
    ITEM_KEY = ServicePolicyConstants.POLICY_MAP

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'id', 'id': True, 'yang-key': 'name'},
            {'key': 'type'},
            {'key': 'classes', 'yang-key': 'class', 'type': [ServicePolicyClass]}
        ]

    @classmethod
    def remove_wrapper(cls, content, context):
        content = cls._remove_base_wrapper(content, context)
        if content is None:
            return
        return content.get(ServicePolicyConstants.POLICY, None)

    def _wrapper_preamble(self, content, context):
        return {ServicePolicyConstants.POLICY: content}

    def to_dict(self, context):
        _C = ServicePolicyConstants
        content = OrderedDict()

        content[xml_utils.NS] = xml_utils.NS_CISCO_POLICY
        # On update, YANG might have a different state of the order of class-maps than the CLI, hence we do a PUT
        content[xml_utils.OPERATION] = NC_OPERATION.PUT
        content[_C.NAME] = self.id
        content[_C.TYPE] = self.type
        if len(self.classes) > 0:
            content[_C.CLASS] = list()
            for class_ in self.classes:
                content[_C.CLASS].append(class_.to_dict(context))

        return {self.ITEM_KEY: content}


class ServicePolicyClassConstants():
    NAME = 'name'
    TYPE = 'type'
    POLICY = 'policy'
    POLICY_ACTION = 'action'
    POLICY_LOG = 'log'


class ServicePolicyClass(NyBase):

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'id', 'id': True, 'yang-key': 'name'},
            {'key': 'type', 'default': None},
            {'key': 'policy_action', 'yang-path': 'policy', 'yang-key': 'action'},
            {'key': 'log', 'yang-path': 'policy', 'yang-key': 'log', 'yang-type': YANG_TYPE.EMPTY, 'default': False}
        ]

    def to_dict(self, context):
        _C = ServicePolicyClassConstants
        class_ = OrderedDict()
        class_[_C.NAME] = self.id
        if self.type:
            class_[_C.TYPE] = self.type
        class_[_C.POLICY] = OrderedDict()
        class_[_C.POLICY][_C.POLICY_ACTION] = self.policy_action
        if self.log:
            class_[_C.POLICY][_C.POLICY_LOG] = ''

        return class_
