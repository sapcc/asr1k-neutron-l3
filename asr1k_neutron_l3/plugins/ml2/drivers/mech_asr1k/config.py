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
from neutron_lib._i18n import _


asr_opts = [
    cfg.ListOpt('physical_networks', default=None,
                help=_("List of pyhsical networks the driver should use to"
                       "indentify the segment to use (if not specified"
                       "driver will use first segment in the list)")),
]

cfg.CONF.register_opts(asr_opts, "ml2_asr1k")
