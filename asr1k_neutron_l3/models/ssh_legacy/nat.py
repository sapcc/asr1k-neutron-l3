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
from asr1k_neutron_l3.models.ssh_legacy import ssh_base
from asr1k_neutron_l3.models.netconf_yang.ny_base import retry_on_failure

LOG = logging.getLogger(__name__)

class StaticNatList(ssh_base.SSHBase):
    ARP_REGEX = "^Internet\s+{}\s+.\s+{}"

    @retry_on_failure()
    def update(self, context):
        if bool(self.base.static_nats):
            config = []
            matches=[]
            for nat in self.base.static_nats:
                matches.append(self.ARP_REGEX.format(nat.global_ip, nat.mac_address))
                config.append("arp vrf {} {} {}  ARPA alias".format(nat.vrf,nat.global_ip, nat.mac_address))
            if not self.exists(context, "show arp vrf {} alias | inc Internet".format(nat.vrf), matches, results=len(config)):
                self._edit_running_config(context, config, 'UPDATE_ARP_LIST')
        else:
            LOG.debug('Skipping ARP update, no NAT entries')

    @retry_on_failure()
    def delete(self, context):
        if bool(self.base.static_nats):
            config= []
            matches=[]

            for nat in self.base.static_nats:
                matches.append(self.ARP_REGEX.format(nat.global_ip, nat.mac_address))
                config.append("no arp vrf {} {} {}  ARPA alias".format(nat.vrf,nat.global_ip, nat.mac_address))

            if self.exists(context,"show arp vrf {} alias | inc Internet".format(nat.vrf),matches, results=len(config)):
                self._edit_running_config(context, config, 'DELETE_ARP_LIST')
        else:
            LOG.debug('Skipping ARP delete, no NAT entries')

class StaticNat(ssh_base.SSHBase):

    @retry_on_failure()
    def delete(self, context):
        config = [member.format(**{'vrf': self.base.vrf,'global_ip':self.base.global_ip,'mac_address':self.base.mac_address}) for member in DELETE_ARP]
        self._edit_running_config(context, config, 'DELETE_ARP')

    @retry_on_failure()
    def update(self, context):
        config = [member.format(**{'vrf': self.base.vrf,'global_ip':self.base.global_ip,'mac_address':self.base.mac_address}) for member in UPDATE_ARP]
        self._edit_running_config(context, config, 'UPDATE_ARP')


class DynamicNat(ssh_base.SSHBase):

    @retry_on_failure()
    def delete_interface(self, context):
        config = [member.format(**{'vrf': self.base.vrf,'bridge_domain':self.base.bridge_domain}) for member in DELETE_DYNAMIC_NAT_INTERFACE_FORCED]
        return self._edit_running_config(context, config, 'DELETE_DYNAMIC_NAT_INTERFACE_FORCED',accept_failure=True)

    @retry_on_failure()
    def delete_pool(self, context):
        config = [member.format(**{'vrf': self.base.vrf}) for member in DELETE_DYNAMIC_NAT_POOL_FORCED]
        return self._edit_running_config(context, config, 'DELETE_DYNAMIC_NAT_POOL_FORCED',accept_failure=True)



UPDATE_ARP = ["arp vrf {vrf} {global_ip} {mac_address}  ARPA alias"]
DELETE_ARP = ["no arp vrf {vrf} {global_ip} {mac_address} ARPA alias"]
DELETE_DYNAMIC_NAT_INTERFACE_FORCED = ["no ip nat inside source list NAT-{vrf} interface BDI{bridge_domain} vrf {vrf} overload forced"]
DELETE_DYNAMIC_NAT_POOL_FORCED = ["no ip nat inside source list NAT-{vrf} pool {vrf} vrf {vrf} overload forced"]
