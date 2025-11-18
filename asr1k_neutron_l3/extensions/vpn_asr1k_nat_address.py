# Copyright 2025 SAP SE
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

from neutron_lib.api import converters
from neutron_lib.api.definitions import vpn
from neutron_lib.api import extensions as api_extensions
from neutron_lib import constants
from neutron_lib.db import resource_extend


class ApiDef:
    ALIAS = 'vpn-asr1k-nat-address'
    IS_SHIM_EXTENSION = False
    IS_STANDARD_ATTR_EXTENSION = False
    NAME = 'VPNaaS NAT address (asr1k flavor)'
    DESCRIPTION = "Specify NAT address for an IPSec Site Connection if needed"
    UPDATED_TIMESTAMP = "2025-11-05T08:00:00-00:00"
    API_PREFIX = '/vpn'

    RESOURCE_ATTRIBUTE_MAP = {
        vpn.IPSEC_SITE_CONNECTIONS: {
            # internal cidr v4
            'peer_nat_address_v4': {
                'allow_post': True, 'allow_put': True,
                'default': constants.ATTR_NOT_SPECIFIED,
                'convert_to': converters.convert_ip_to_canonical_format,
                'validate': {'type:ip_address_or_none': None},
                'is_visible': True,
            },
        },
    }

    SUB_RESOURCE_ATTRIBUTE_MAP = {}
    ACTION_MAP = {}
    ACTION_STATUS = {}
    REQUIRED_EXTENSIONS = [
        vpn.ALIAS,
    ]
    OPTIONAL_EXTENSIONS = []


@resource_extend.has_resource_extenders
class Vpn_asr1k_nat_address(api_extensions.APIExtensionDescriptor):
    api_definition = ApiDef

    @resource_extend.extends([vpn.IPSEC_SITE_CONNECTIONS])
    def add_internal_tunnel_ips(result_dict, db):
        if db.nat_address:
            nat_address = db.nat_address.address
        else:
            nat_address = None
        result_dict['peer_nat_address_v4'] = nat_address

        return result_dict
