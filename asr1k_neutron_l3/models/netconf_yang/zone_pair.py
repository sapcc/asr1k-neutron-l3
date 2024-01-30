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

from asr1k_neutron_l3.common.asr1k_constants import \
    FWAAS_ZONE_PAIR_EXT_INGRESS_PREFIX, FWAAS_ZONE_PAIR_EXT_EGRESS_PREFIX
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase
from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.models.netconf_yang import xml_utils


class ZonePairConstants():
    ZONE_PAIR = 'zone-pair'

    SECURITY = 'security'

    ID = 'id'
    SOURCE = 'source'
    DESTINATION = 'destination'

    SERVICE_POLICY = 'service-policy'
    TYPE = 'type'
    INSPECT = 'inspect'


class ZonePair(NyBase):
    ID_FILTER = """
                <native>
                    <zone-pair>
                        <security xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-zone">
                            <id>{id}</id>
                        </security>
                    </zone-pair>
                </native>
                """

    GET_ALL_STUB = """
                <native>
                    <zone-pair>
                        <security xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-zone">
                        </security>
                    </zone-pair>
                </native>
                """
    LIST_KEY = ZonePairConstants.ZONE_PAIR
    ITEM_KEY = ZonePairConstants.SECURITY

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'id', 'id': True},
            {'key': 'source', 'mandatory': True},
            {'key': 'destination', 'mandatory': True},
            {'key': 'service_policy', 'yang-key': 'inspect', 'yang-path': 'service-policy/type', 'mandatory': True}
        ]

    @property
    def neutron_router_id(self):
        if self.id is not None:
            for prefix in (FWAAS_ZONE_PAIR_EXT_EGRESS_PREFIX, FWAAS_ZONE_PAIR_EXT_INGRESS_PREFIX):
                if self.id.startswith(prefix):
                    return utils.vrf_id_to_uuid(self.id[len(prefix):])

    def is_orphan(self, all_routers_with_external_policies, *args, **kwargs):
        if self.neutron_router_id:
            return self.neutron_router_id not in all_routers_with_external_policies
        return False

    def to_dict(self, context):
        _C = ZonePairConstants
        content = OrderedDict()

        content[xml_utils.NS] = xml_utils.NS_CISCO_ZONE
        content[_C.ID] = self.id
        content[_C.SOURCE] = self.source
        content[_C.DESTINATION] = self.destination
        content[_C.SERVICE_POLICY] = {_C.TYPE: {_C.INSPECT: self.service_policy}}

        return {self.ITEM_KEY: content}

    def to_delete_dict(self, context):
        _C = ZonePairConstants
        content = OrderedDict()

        content[xml_utils.NS] = xml_utils.NS_CISCO_ZONE
        content[_C.ID] = self.id
        return {self.ITEM_KEY: content}
