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


class BDIInterface(ncc_base.NccBase):

    @retry_on_failure()
    def update(self, context):
        self.enable_nat(context)

    def disable_nat(self, context):
        try:
            config = ADD_NAT_TO_BDI.format(**{'id': self.base.id, 'nat_mode': self.base.nat_mode})
            self._edit_running_config(context, config, 'REMOVE_NAT_FROM_BDI')
        finally:
            if self._ncc_connection is not None:
                self._ncc_connection.close_session()


    def enable_nat(self, context):
        try:
            config = ADD_NAT_TO_BDI.format(**{'id': self.base.id, 'nat_mode': self.base.nat_mode})
            self._edit_running_config(context, config, 'ADD_NAT_TO_BDI')
        finally:
            if self._ncc_connection is not None:
                self._ncc_connection.close_session()


ADD_NAT_TO_BDI = """
<config>
        <cli-config-data>
            <cmd>interface BDI{id}</cmd>
            <cmd>ip nat {nat_mode}</cmd>
            <cmd>no shutdown</cmd>
        </cli-config-data>
</config>
"""

REMOVE_NAT_FROM_BDI = """
<config>
        <cli-config-data>
            <cmd>interface BDI{id}</cmd>
            <cmd>no ip nat {nat_mode}</cmd>
            <cmd>no shutdown</cmd>
        </cli-config-data>
</config>
"""
