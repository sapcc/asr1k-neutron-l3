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
    cfg.IntOpt('port', default=(443), help=('')),
    cfg.IntOpt('nc_port', default=(22), help=('')),
    cfg.IntOpt('nc_timeout', default=(5), help=('')),
    cfg.StrOpt('user_name', default=('admin'), help=('')),
    cfg.StrOpt('password', default=('secret'), help=('')),
    cfg.StrOpt('external_interface', default=('Port-channel1'), help=('')),
    cfg.StrOpt('loopback_external_interface', default=('Port-channel2'), help=('')),
    cfg.StrOpt('loopback_internal_interface', default=('Port-channel3'), help=(''))

]
