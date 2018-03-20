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


class Vrf(ncc_base.NccBase):

    @retry_on_failure()
    def update(self, context):
        self.disable_bgp(context)

    def disable_bgp(self, context):
        try:
            config = CLEAR_RD.format(**{'id': self.base.id,'rd':self.base.rd})
            self._edit_running_config(context, config, 'CLEAR_RD')
        finally:
            if self._ncc_connection is not None:
                self._ncc_connection.close_session()


CLEAR_ROUTE_MAP = """
<config>
        <cli-config-data>
            <cmd>vrf definition {id}</cmd>
            <cmd>address-family ipv4</cmd>
            <cmd>no export map exp-{id}</cmd>
        </cli-config-data>
</config>

"""


CLEAR_RD = """
<config>
        <cli-config-data>
            <cmd>vrf definition {id}</cmd>
            <cmd>no rd {rd}</cmd>
        </cli-config-data>
</config>
"""


