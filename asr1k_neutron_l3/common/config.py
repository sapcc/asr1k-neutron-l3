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

DEVICE_OPTS = [
    cfg.ListOpt('hosts', default=('10.0.0.1'), help=('')),
    cfg.StrOpt('protocol', default=('https'), help=('')),
    cfg.IntOpt('http_port', default=(443), help=('')),
    cfg.IntOpt('yang_port', default=(830), help=('')),
    cfg.IntOpt('legacy_port', default=(22), help=('')),
    cfg.IntOpt('nc_timeout', default=(5), help=('')),
    cfg.StrOpt('user_name', default=('admin'), help=('')),
    cfg.StrOpt('password', default=('secret'), help=('')),
    cfg.StrOpt('external_interface', default=('Port-channel1'), help=('')),
    cfg.StrOpt('loopback_external_interface', default=('Port-channel2'), help=('')),
    cfg.StrOpt('loopback_internal_interface', default=('Port-channel3'), help=(''))


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

]



def _get_specific_config(name):
    """retrieve config in the format [<label>:<key>]."""
    conf_dict = {}
    multi_parser = cfg.MultiConfigParser()
    multi_parser.read(cfg.CONF.config_file)
    for parsed_file in multi_parser.parsed:
        for parsed_item in parsed_file.keys():
            if parsed_item == name:
                conf_dict = parsed_file[parsed_item].items()
    return conf_dict


def create_address_scope_dict():
    address_scope_dict = {}
    conf = _get_specific_config('asr1k-address-scopes')
    for key, value in conf:
        address_scope_dict[key] = value[0]

    return address_scope_dict