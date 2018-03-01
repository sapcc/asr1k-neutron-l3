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

from oslo_config import cfg
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


DEVICE_OPTS = [
    cfg.ListOpt('host', default=('10.0.0.1'), help=('')),
    cfg.StrOpt('protocol', default=('https'), help=('')),
    cfg.IntOpt('http_port', default=(443), help=('')),
    cfg.IntOpt('yang_port', default=(830), help=('')),
    cfg.IntOpt('legacy_port', default=(22), help=('')),
    cfg.IntOpt('nc_timeout', default=(30), help=('')),
    cfg.StrOpt('user_name', default=('admin'), help=('')),
    cfg.StrOpt('password', default=('secret'), help=('')),



]

ASR1K_OPTS = [
    cfg.StrOpt('monitor', default=('asr1k_neutron_l3.common.prometheus_monitor.PrometheusMonitor'), help=('')),
]

ASR1K_L3_OPTS = [

    cfg.IntOpt('fabric_asn', default=(65192), help=('')),
    cfg.IntOpt('max_requeue_attempts', default=(10), help=(''))
]

ASR1K_L2_OPTS = [
    cfg.BoolOpt('sync_active', default=True, help=_("Activate regular config sync")),
    cfg.IntOpt('sync_interval', default=60, help=_("Polling interval for sync task")),
    cfg.IntOpt('sync_chunk_size', default=10,help=_("Number of ports to process in on poll")),
    cfg.StrOpt('external_interface', default=('Port-channel1'), help=('')),
    cfg.StrOpt('loopback_external_interface', default=('Port-channel2'), help=('')),
    cfg.StrOpt('loopback_internal_interface', default=('Port-channel3'), help=(''))
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