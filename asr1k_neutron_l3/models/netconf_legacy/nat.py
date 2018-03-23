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

class StaticNat(ncc_base.NccBase):

    @retry_on_failure()
    def delete(self, context):
        config = DELETE_ARP.format(**{'vrf': self.base.vrf,'global_ip':self.base.global_ip,'mac_address':self.base.mac_address})
        self._edit_running_config(context, config, 'DELETE_ARP')

    @retry_on_failure()
    def update(self, context):
        config = UPDATE_ARP.format(**{'vrf': self.base.vrf,'global_ip':self.base.global_ip,'mac_address':self.base.mac_address})
        self._edit_running_config(context, config, 'UPDATE_ARP')



UPDATE_ARP = """
<config>
        <cli-config-data>
            <cmd>arp vrf {vrf} {global_ip} {mac_address}  ARPA alias</cmd>
        </cli-config-data>
</config>
"""

DELETE_ARP = """
<config>
        <cli-config-data>
            <cmd>no arp vrf {vrf} {global_ip} {mac_address} ARPA alias</cmd>
        </cli-config-data>
</config>
"""
