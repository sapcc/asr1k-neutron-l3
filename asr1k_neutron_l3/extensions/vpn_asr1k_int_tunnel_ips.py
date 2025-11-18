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
    ALIAS = 'vpn-asr1k-int-tunnel-ips'
    IS_SHIM_EXTENSION = False
    IS_STANDARD_ATTR_EXTENSION = False
    NAME = 'VPNaaS Internal Tunnel IP Addresses (asr1k flavor)'
    DESCRIPTION = "Allow giving the tunnel an internal v4 and v6 prefix"
    UPDATED_TIMESTAMP = "2025-09-22T08:00:00-00:00"
    API_PREFIX = '/vpn'

    RESOURCE_ATTRIBUTE_MAP = {
        vpn.IPSEC_SITE_CONNECTIONS: {
            # internal cidr v4
            'int_local_cidr_v4': {
                'allow_post': True, 'allow_put': True,
                'default': constants.ATTR_NOT_SPECIFIED,
                'convert_to': converters.convert_cidr_to_canonical_format,
                'validate': {'type:subnet_or_none': None},
                'is_visible': True,
            },

            # remote ip v4
            'int_peer_address_v4': {
                'allow_post': True, 'allow_put': True,
                'default': constants.ATTR_NOT_SPECIFIED,
                'convert_to': converters.convert_ip_to_canonical_format,
                'validate': {'type:ip_address_or_none': None},
                'is_visible': True,
            },

            # internal cidr v6
            'int_local_cidr_v6': {
                'allow_post': True, 'allow_put': True,
                'default': constants.ATTR_NOT_SPECIFIED,
                'convert_to': converters.convert_cidr_to_canonical_format,
                'validate': {'type:subnet_or_none': None},
                'is_visible': True,
            },

            # remote ip v6
            'int_peer_address_v6': {
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
class Vpn_asr1k_int_tunnel_ips(api_extensions.APIExtensionDescriptor):
    api_definition = ApiDef

    @resource_extend.extends([vpn.IPSEC_SITE_CONNECTIONS])
    def add_internal_tunnel_ips(result_dict, db):
        if db.int_tunnel_ips:
            result_dict['int_local_cidr_v4'] = db.int_tunnel_ips.local_cidr_v4
            result_dict['int_peer_address_v4'] = db.int_tunnel_ips.peer_address_v4
            result_dict['int_local_cidr_v6'] = db.int_tunnel_ips.local_cidr_v6
            result_dict['int_peer_address_v6'] = db.int_tunnel_ips.peer_address_v6

        return result_dict
