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

from asr1k_neutron_l3.models.netconf_legacy import ncc_base
from asr1k_neutron_l3.models.netconf_yang.ny_base import retry_on_failure

class RouteMap(ncc_base.NccBase):

    @retry_on_failure()
    def delete(self, context):
        config = CLEAR_ROUTE_MAP.format(**{'name':self.base.name})
        self._edit_running_config(context, config, 'CLEAR_ROUTE_MAP')


CLEAR_ROUTE_MAP = """
<config>
        <cli-config-data>
            <cmd>no route-map {name} </cmd>
        </cli-config-data>
</config>
"""

