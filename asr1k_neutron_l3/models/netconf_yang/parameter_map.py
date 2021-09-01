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

from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase
from asr1k_neutron_l3.models.netconf_yang import xml_utils


class ParameterMapConstants():
    PARAMETER_MAP = "parameter-map"
    TYPE = "type"
    INSPECT_GLOBAL = "inspect-global"
    INSPECT = "inspect"
    VRF = "vrf"
    ID = "id"
    NAME = "name"


class ParameterMapInspectGlobalVrf(NyBase):
    ID_FILTER = """
                <native>
                    <parameter-map>
                        <type>
                            <inspect-global xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-policy">
                                <inspect>
                                    <vrf>
                                        <id>{id}</id>
                                    </vrf>
                                </inspect>
                            </inspect-global>
                        </type>
                    </parameter-map>
                </native>
                """

    GET_ALL_STUB = """
                <native>
                    <parameter-map>
                        <type>
                            <inspect-global xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-policy">
                                <inspect>
                                    <vrf>
                                    </vrf>
                                </inspect>
                            </inspect-global>
                        </type>
                    </parameter-map>
                </native>
                """

    LIST_KEY = ParameterMapConstants.INSPECT
    ITEM_KEY = ParameterMapConstants.VRF

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'vrf', 'id': True, 'yang-key': 'id'},
            {'key': 'parameter_map', 'yang-key': 'name'}
        ]

    def _wrapper_preamble(self, content: dict, context) -> dict:
        content = super()._wrapper_preamble(content, context)
        _C = ParameterMapConstants

        paramerter_map = OrderedDict()
        paramerter_map[_C.PARAMETER_MAP] = OrderedDict()
        paramerter_map[_C.PARAMETER_MAP][_C.TYPE] = OrderedDict()
        paramerter_map[_C.PARAMETER_MAP][_C.TYPE][_C.INSPECT_GLOBAL] = OrderedDict()
        paramerter_map[_C.PARAMETER_MAP][_C.TYPE][_C.INSPECT_GLOBAL] = content
        paramerter_map[_C.PARAMETER_MAP][_C.TYPE][_C.INSPECT_GLOBAL][xml_utils.NS] = xml_utils.NS_CISCO_POLICY

        return paramerter_map

    @classmethod
    def remove_wrapper(cls, content: dict, context) -> dict:
        _C = ParameterMapConstants
        content = cls._remove_base_wrapper(content, context)

        unpack = [_C.PARAMETER_MAP, _C.TYPE, _C.INSPECT_GLOBAL, cls.LIST_KEY]
        if content:
            for item in unpack:
                content = content.get(item, {})

        if not content:
            return None

        return content

    @property
    def neutron_router_id(self):
        return utils.vrf_id_to_uuid(self.id)

    def is_orphan(self, all_router_ids, all_routers_with_external_policies):
        if self.neutron_router_id in all_routers_with_external_policies:
            return False

    def to_dict(self, context) -> dict:
        _C = ParameterMapConstants
        content = OrderedDict()

        content[_C.ID] = self.id
        content[_C.NAME] = self.parameter_map

        return {self.ITEM_KEY: content}
