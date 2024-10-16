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

MAX_CONNECTIONS = 10

AGENT_TYPE_ASR1K_L3 = 'ASR1K L3 Agent'
AGENT_BINARY_ASR1K_L3 = 'asr1k-neutron-l3-agent'
AGENT_TYPE_ASR1K_ML2 = 'ASR1K ML2 Agent'

ASR1K_TOPIC = 'asr1k'

ASR1K_EXTRA_ATTS_KEY = 'asr1k_extra_atts'
ASR1K_ROUTER_ATTS_KEY = 'asr1k_router_atts'
REQUEUES_KEY = 'requeues'

ADDRESS_SCOPE_CONFIG = 'address_scope_config'

ROUTER_STATE_ERROR = 'ERROR'

SNAT_MODE_POOL = 'pool'
SNAT_MODE_INTERFACE = 'interface'

NO_AZ_LIST = (None, 'nova')

TAG_DEFAULT_ROUTE_OVERWRITE = 'custom-default-route'
TAG_SKIP_MONITORING = 'skip-monitoring'


# cannot import from neutron_fwaas.common.fwaas_constants as it might not be installed
FWAAS_SERVICE_PLUGIN = 'firewall_v2'

FWAAS_ACL_PREFIX = "ACL-FWAAS-"
FWAAS_CLASS_MAP_PREFIX = "CM-FWAAS-"
FWAAS_SERVICE_POLICY_PREFIX = "SP-FWAAS-"
FWAAS_ZONE_PREFIX = 'ZN-FWAAS-'
FWAAS_ZONE_PAIR_PREFIX = 'ZP-FWAAS-'
FWAAS_ZONE_PAIR_EXT_EGRESS_PREFIX = FWAAS_ZONE_PAIR_PREFIX + 'EXT-EGRESS-'
FWAAS_ZONE_PAIR_EXT_INGRESS_PREFIX = FWAAS_ZONE_PAIR_PREFIX + 'EXT-INGRESS-'
FWAAS_DEFAULT_PARAMETER_MAP = "PAM-FWAAS-POLICE-VRF"
FWAAS_DEFAULT_ALLOW_INSPECT_POLICY = FWAAS_SERVICE_POLICY_PREFIX + "ALLOW-INSPECT"
