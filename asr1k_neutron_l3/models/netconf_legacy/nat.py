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
from asr1k_neutron_l3.models.netconf_legacy import ncc_base
from asr1k_neutron_l3.models.netconf_yang.ny_base import retry_on_failure

LOG = logging.getLogger(__name__)

class StaticNatList(ncc_base.NccBase):

    @retry_on_failure()
    def update(self, context):
        if bool(self.base.static_nats):
            config = "<config><cli-config-data>"

            for nat in self.base.static_nats:
                config += "<cmd>arp vrf {} {} {}  ARPA alias</cmd>".format(nat.vrf,nat.global_ip, nat.mac_address)
            config += "</cli-config-data></config>"

            self._edit_running_config(context, config, 'UPDATE_ARP_LIST')
        else:
            LOG.debug('Skipping ARP update, no NAT entries')

    @retry_on_failure()
    def delete(self, context):
        if bool(self.base.static_nats):
            config = "<config><cli-config-data>"

            for nat in self.base.static_nats:
                config += "<cmd>no arp vrf {} {} {}  ARPA alias</cmd>".format(nat.vrf,nat.global_ip, nat.mac_address)
            config += "</cli-config-data></config>"

            self._edit_running_config(context, config, 'DELETE_ARP_LIST')
        else:
            LOG.debug('Skipping ARP delete, no NAT entries')

class StaticNat(ncc_base.NccBase):

    @retry_on_failure()
    def delete(self, context):
        config = DELETE_ARP.format(**{'vrf': self.base.vrf,'global_ip':self.base.global_ip,'mac_address':self.base.mac_address})
        self._edit_running_config(context, config, 'DELETE_ARP')

    @retry_on_failure()
    def update(self, context):
        config = UPDATE_ARP.format(**{'vrf': self.base.vrf,'global_ip':self.base.global_ip,'mac_address':self.base.mac_address})
        self._edit_running_config(context, config, 'UPDATE_ARP')


class DynamicNat(ncc_base.NccBase):

    @retry_on_failure()
    def delete(self, context):
        config = DELETE_DYNAMIC_NAT_FORCED.format(**{'vrf': self.base.vrf,'bridge_domain':self.base.bridge_domain})
        self._edit_running_config(context, config, 'DELETE_DYNAMIC_NAT_FORCED')


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


DELETE_DYNAMIC_NAT_FORCED = """
<config>
        <cli-config-data>
            <cmd>no ip nat inside source list NAT-{vrf} interface BDI{bridge_domain} vrf {vrf} overload forced</cmd>
        </cli-config-data>
</config>
"""
