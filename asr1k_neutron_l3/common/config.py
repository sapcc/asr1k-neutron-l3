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

from oslo_log import log as logging
from oslo_config import cfg
from neutron.common import cache_utils
from neutron.conf.agent import common
from neutron.conf import service
from neutron_lib._i18n import _

LOG = logging.getLogger(__name__)


DEVICE_OPTS = [
    cfg.StrOpt('host', default='10.0.0.1', help='Host for netconf-YANG'),
    cfg.IntOpt('yang_port', default=830, help='Port for netconf-YANG, default 830'),
    cfg.IntOpt('nc_timeout', default=5, help='Netconf-YANG timeout, default 5s'),
    cfg.StrOpt('user_name', default='admin', help='Netconf-YANG User'),
    cfg.StrOpt('password', default='secret', help='Netconf-YANG Password'),
    cfg.BoolOpt('use_bdvif', default=True, help='Use BD-VIF when supported by device firmware'),
]

ASR1K_OPTS = [
    cfg.BoolOpt('init_mode', default=False, help=_("Activate initialization mode")),
    cfg.BoolOpt('save_config', default=True, help=_("Periodically sasve configuration")),
    cfg.IntOpt('connection_max_age', default=(3600), help=('')),
    cfg.BoolOpt('clean_orphans', default=True, help=_("Activate regular orphan cleanup")),

    cfg.IntOpt('clean_orphan_interval', default=(120), help=_("Interval for regular orphan cleanup")),

    cfg.BoolOpt('trace_all_yang_calls', default=False, help=_("Log all YANG xml calls, including how long they took")),
    cfg.BoolOpt('trace_yang_call_failures', default=False,
                help=_("Log all failed YANG xml calls, including how long they took")),

    cfg.BoolOpt('ignore_invalid_az_hint_for_router', default=False,
                help="Router AZ hints will not be validated. This means that an AZ hint is accepted even if no asr1k "
                     "agent is present with this AZ. This will also disable proper scheduling. ALL routers will "
                     "be scheduled to any router of the driver's liking if no candidate with a matching AZ hint "
                     "is present."),
    cfg.BoolOpt('ignore_router_network_az_hint_mismatch', default=False,
                help="Do not abort operation if router and network AZ hint do not match."),
]

ASR1K_L3_OPTS = [
    cfg.IntOpt('yang_connection_pool_size', default=(5), help=('')),
    cfg.IntOpt('fabric_asn', default=(65192), help=('')),
    cfg.IntOpt('max_requeue_attempts', default=(10), help=('')),
    cfg.BoolOpt('sync_active', default=True, help=_("Activate regular config sync")),
    cfg.IntOpt('sync_interval', default=60, help=_("Polling interval for sync task")),
    cfg.IntOpt('sync_chunk_size', default=10, help=_("Number of ports to process in on poll")),
    cfg.IntOpt('sync_until_queue_size', default=50,
               help=_("Maximum size of RouterProcessingQueue for syncing routers. The driver will queue router updates "
                      "until sync_chunk_size is hit AND there are more than sync_until_queue_size entires in the "
                      "processing queue.")),
    cfg.IntOpt('queue_timeout', default=60,
               help=_("Timeout for blocking of get on queue, waiting for item to puched onto queue")),
    cfg.IntOpt('update_timeout', default=120, help=_("Timeout for for one process routers update iteration")),
    cfg.IntOpt('threadpool_maxsize', default=5,
               help=_("Size of thread pool used in router updates, needs to be "
                      "balanced against ASR SSH connection limits")),
    cfg.IntOpt('clean_delta', default=(30), help=('')),
    cfg.IntOpt('max_config_save_interval', default=900,
               help=_('Maximum interval in which the device config should be saved. Only triggers if a complete '
                      'router sync loop takes longer than this interval.')),
    cfg.BoolOpt('stateless_nat', default=True,
                help=_("Enable stateless nat for floating if the device supports it")),
    cfg.StrOpt('dapnet_rm_prefix', default='RM-DAP-CCLOUD',
               help="Route-Map prefix for Directly Accessible Private Networks (DAPNets)"),
    cfg.StrOpt('dapnet_network_rm', default='RM-DAP',
               help="Route-Map to apply to all DAPNet BGP network statements"),
    cfg.StrOpt('dapnet_extra_routes_rm', default='RM-DAP-EXTRA-ROUTES',
               help="Route-Map to apply to all BGP network statements for extra routes that are contained in a DAPNet"),
    # FIXME: move defaults away from here
    cfg.ListOpt('dapn_extra_routes_communities', default=["65126", "4268097541"],
                help="Communities to assign to DAPNet extraroutes (via redistribute statement)"),
    cfg.IntOpt('external_iface_arp_timeout', default=1800,
               help="Set ARP timeout for the external interface of a router. Set to 0 to not set this attribute"),
    cfg.IntOpt('internal_iface_arp_timeout', default=0,
               help="Set ARP timeout for the external interface of a router. Disabled by default"),
    cfg.BoolOpt('enable_arp_cleaning', default=True, help="Run ARP cleaning sync to remove stale macs of floating ips"),
    cfg.IntOpt('arp_cleaning_interval', default=120, help="Interval for ARP cleaning"),
]

ASR1K_L2_OPTS = [
    cfg.IntOpt('yang_connection_pool_size', default=(5), help=('')),
    cfg.BoolOpt('sync_active', default=True, help=_("Activate regular config sync")),
    cfg.IntOpt('sync_interval', default=60, help=_("Polling interval for sync task")),
    cfg.IntOpt('sync_chunk_size', default=10, help=_("Number of ports to process in on poll")),
    cfg.StrOpt('external_interface', default=('1'), help=('')),
    cfg.StrOpt('loopback_external_interface', default=('2'), help=('')),
    cfg.StrOpt('loopback_internal_interface', default=('3'), help=('')),
    cfg.IntOpt('bdvif_bd_limit', default=100, help='Hardware limit of BD-VIF per Bridge Domain'),
]

AGENT_STATE_OPTS = [
    cfg.FloatOpt('report_interval', default=30,
                 help=_('Seconds between nodes reporting state to server; '
                        'should be less than agent_down_time, best if it '
                        'is half or less than agent_down_time.')),
    cfg.BoolOpt('log_agent_heartbeats', default=False,
                help=_('Log agent heartbeats')),
    cfg.BoolOpt('scheduling_disabled', default=False,
                help="No new routers will be scheduled on this L3 agent."),
]


def create_device_pair_dictionary():
    device_dict = {}
    for section in cfg.CONF.list_all_sections():
        if section.startswith("asr1k_device:"):
            _, device_name = section.split(":", 2)
            cfg.CONF.register_opts(DEVICE_OPTS, section)
            device_dict[device_name] = getattr(cfg.CONF, section)

    if len(device_dict.keys()) > 2:
        LOG.warning("More than 2 devices were configured, only the first two will be used ")

    if len(device_dict.keys()) == 0:
        raise Exception("No devices were configured. Please review asr1k configuration file. ")

    return device_dict


def _get_specific_config(name):
    for conf_file in cfg.CONF.config_file:
        parser = cfg.ConfigParser(conf_file, {})
        parser.parse()
        if parser.sections.get(name):
            return parser.sections[name]

    return {}


def create_address_scope_dict():
    address_scope_dict = {}
    conf = _get_specific_config('asr1k-address-scopes')
    for key, value in conf.items():
        address_scope_dict[key] = value[0]

    return address_scope_dict


def register_common_opts():
    cfg.CONF.register_opts(ASR1K_OPTS, "asr1k")
    cfg.CONF.register_opts(AGENT_STATE_OPTS, 'AGENT')
    common.register_availability_zone_opts_helper(cfg.CONF)
    cache_utils.register_oslo_configs(cfg.CONF)


def register_l3_opts():
    cfg.CONF.register_opts(ASR1K_L3_OPTS, "asr1k_l3")
    cfg.CONF.register_opts(ASR1K_L2_OPTS, "asr1k_l2")
    common.register_interface_opts()
    common.register_interface_driver_opts_helper(cfg.CONF)


def register_l2_opts():
    cfg.CONF.register_opts(ASR1K_L2_OPTS, "asr1k_l2")
    cfg.CONF.register_opts(service.RPC_EXTRA_OPTS)

    cfg.CONF.asr1k.yang_connection_pool_size = cfg.CONF.asr1k_l2.yang_connection_pool_size
