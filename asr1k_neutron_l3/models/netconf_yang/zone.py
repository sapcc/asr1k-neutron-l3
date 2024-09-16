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

from asr1k_neutron_l3.common.asr1k_constants import FWAAS_ZONE_PREFIX
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase
from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.models.netconf_yang import xml_utils


class ZoneConstants():
    ZONE = 'zone'
    SECURITY = 'security'
    ID = 'id'


class Zone(NyBase):
    ID_FILTER = """
                <native>
                    <zone>
                        <security xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-zone">
                            <id>{id}</id>
                        </security>
                    </zone>
                </native>
                """

    GET_ALL_STUB = """
                <native>
                    <zone>
                        <security xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-zone">
                        </security>
                    </zone>
                </native>
                """

    LIST_KEY = ZoneConstants.ZONE
    ITEM_KEY = ZoneConstants.SECURITY

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'id', 'id': True}
        ]

    @property
    def neutron_router_id(self):
        if self.id and self.id.startswith(FWAAS_ZONE_PREFIX):
            return utils.vrf_id_to_uuid(self.id[len(FWAAS_ZONE_PREFIX):])

    def is_orphan(self, all_routers_with_external_policies, *args, **kwargs):
        if self.neutron_router_id:
            return self.neutron_router_id not in all_routers_with_external_policies
        return False

    def to_dict(self, context):
        content = OrderedDict()
        content[xml_utils.NS] = xml_utils.NS_CISCO_ZONE
        content[ZoneConstants.ID] = self.id
        return {self.ITEM_KEY: content}
