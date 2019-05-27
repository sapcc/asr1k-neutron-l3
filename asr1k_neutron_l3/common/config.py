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
from neutron.conf.agent import common
from neutron_lib._i18n import _

LOG = logging.getLogger(__name__)


DEVICE_OPTS = [
    cfg.ListOpt('host', default=('10.0.0.1'), help=('')),
    cfg.IntOpt('yang_port', default=(830), help=('')),
    cfg.IntOpt('nc_timeout', default=(5), help=('')),
    cfg.StrOpt('user_name', default=('admin'), help=('')),
    cfg.StrOpt('password', default=('secret'), help=('')),
]

ASR1K_OPTS = [
    cfg.BoolOpt('init_mode', default=False, help=_("Activate initialization mode")),
    cfg.BoolOpt('save_config', default=True, help=_("Periodically sasve configuration")),
    cfg.IntOpt('connection_max_age', default=(3600), help=('')),
    cfg.BoolOpt('clean_orphans', default=True, help=_("Activate regular orphan cleanup")),

    cfg.IntOpt('clean_orphan_interval', default=(120), help=_("Interval for regular orphan cleanup")),

]

ASR1K_L3_OPTS = [
    cfg.IntOpt('yang_connection_pool_size', default=(5), help=('')),
    cfg.IntOpt('fabric_asn', default=(65192), help=('')),
    cfg.IntOpt('max_requeue_attempts', default=(10), help=('')),
    cfg.BoolOpt('sync_active', default=True, help=_("Activate regular config sync")),
    cfg.IntOpt('sync_interval', default=60, help=_("Polling interval for sync task")),
    cfg.IntOpt('sync_chunk_size', default=10, help=_("Number of ports to process in on poll")),
    cfg.IntOpt('queue_timeout', default=60, help=_("Timeout for blocking of get on queue, waiting for item to puched onto queue")),
    cfg.IntOpt('update_timeout', default=120, help=_("Timeout for for one process routers update iteration")),
    cfg.IntOpt('threadpool_maxsize', default=5, help=_("Size of thread pool used in router updates, needs to be balanced against ASR SSH connection limits")),
    cfg.StrOpt('snat_mode', default=('pool'), help=('Use pool or interface on dynamic NAT statement')),
    cfg.IntOpt('clean_delta', default=(30), help=(''))
]

ASR1K_L2_OPTS = [
    cfg.IntOpt('yang_connection_pool_size', default=(5), help=('')),
    cfg.BoolOpt('sync_active', default=True, help=_("Activate regular config sync")),
    cfg.IntOpt('sync_interval', default=60, help=_("Polling interval for sync task")),
    cfg.IntOpt('sync_chunk_size', default=10, help=_("Number of ports to process in on poll")),
    cfg.StrOpt('external_interface', default=('1'), help=('')),
    cfg.StrOpt('loopback_external_interface', default=('2'), help=('')),
    cfg.StrOpt('loopback_internal_interface', default=('3'), help=(''))
]

AGENT_STATE_OPTS = [
    cfg.FloatOpt('report_interval', default=30,
                 help=_('Seconds between nodes reporting state to server; '
                        'should be less than agent_down_time, best if it '
                        'is half or less than agent_down_time.')),
    cfg.BoolOpt('log_agent_heartbeats', default=False,
                help=_('Log agent heartbeats')),
]

AVAILABILITY_ZONE_OPTS = [
    # The default AZ name "nova" is selected to match the default
    # AZ name in Nova and Cinder.
    cfg.StrOpt('availability_zone', max_length=255, default='nova',
               help=_("Availability zone of this node")),
]


def _get_specific_config(name):
    """retrieve config in the format [<label>]."""
    conf_dict = {}
    multi_parser = cfg.MultiConfigParser()
    multi_parser.read(cfg.CONF.config_file)
    for parsed_file in multi_parser.parsed:
        for parsed_item in parsed_file.keys():
            if parsed_item == name:
                conf_dict = parsed_file[parsed_item].items()
    return conf_dict


def _get_group_config(prefix):
    """retrieve config in the format [<label>:<key>]."""
    conf_dict = {}
    multi_parser = cfg.MultiConfigParser()
    multi_parser.read(cfg.CONF.config_file)
    for parsed_file in multi_parser.parsed:
        for parsed_item in parsed_file.keys():
            if parsed_item.startswith(prefix):
                label, key = parsed_item.split(':')
                if label.lower() == prefix:
                    conf_dict[key] = parsed_file[parsed_item].items()
    return conf_dict


def create_device_pair_dictionary():
    device_dict = {}
    conf = _get_group_config('asr1k_device')
    for device_name in conf:
        device_dict[device_name] = {}
        for key, value in conf[device_name]:
            device_dict[device_name][key] = value[0]

    if len(device_dict.keys()) > 2:
        LOG.warning("More than 2 devices were configured, only the first two will be used ")

    if len(device_dict.keys()) == 0:
        raise Exception("No devices were configured. Please review asr1k configuration file. ")

    return device_dict


def create_address_scope_dict():
    address_scope_dict = {}
    conf = _get_specific_config('asr1k-address-scopes')
    for key, value in conf:
        address_scope_dict[key] = value[0]

    return address_scope_dict


def register_l3_opts():
    cfg.CONF.register_opts(DEVICE_OPTS, "asr1k_devices")
    cfg.CONF.register_opts(ASR1K_OPTS, "asr1k")
    cfg.CONF.register_opts(ASR1K_L3_OPTS, "asr1k_l3")
    cfg.CONF.register_opts(ASR1K_L2_OPTS, "asr1k_l2")
    cfg.CONF.register_opts(AGENT_STATE_OPTS, 'AGENT')
    cfg.CONF.register_opts(AVAILABILITY_ZONE_OPTS, 'AGENT')
    cfg.CONF.register_opts(common.EXT_NET_BRIDGE_OPTS)
    common.register_interface_opts()
    common.register_interface_driver_opts_helper(cfg.CONF)


def register_l2_opts():
    cfg.CONF.register_opts(AGENT_STATE_OPTS, 'AGENT')
    cfg.CONF.register_opts(DEVICE_OPTS, "asr1k_devices")
    cfg.CONF.register_opts(ASR1K_OPTS, "asr1k")
    cfg.CONF.register_opts(ASR1K_L2_OPTS, "asr1k_l2")

    cfg.CONF.asr1k.yang_connection_pool_size = cfg.CONF.asr1k_l2.yang_connection_pool_size
