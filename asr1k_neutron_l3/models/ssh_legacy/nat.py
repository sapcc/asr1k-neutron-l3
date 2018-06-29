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
import re
import  time
from oslo_log import log as logging
from asr1k_neutron_l3.models.ssh_legacy import ssh_base
from asr1k_neutron_l3.models.netconf_yang.ny_base import retry_on_failure

LOG = logging.getLogger(__name__)

ARP_REGEX = "^Internet(.*)-(.*)ARPA"
ARP_MATCH = "Internet{}-{}ARPA"
EXISTS_TIMEOUT = 0.5

class StaticNatList(ssh_base.SSHBase):

    @retry_on_failure()
    def update(self, context):

        if bool(self.base.static_nats):
            config = []
            existing = self._get_existing(context)

            for nat in self.base.static_nats:
                if ARP_MATCH.format(nat.global_ip,nat.mac_address) not in existing:
                    config.append("arp vrf {} {} {}  ARPA alias".format(nat.vrf,nat.global_ip, nat.mac_address))

            for entry in existing:

                if entry not in self.get_neutron_nats():
                    match = re.match(ARP_REGEX,entry)
                    if match is not None:
                        ip = match.group(1)
                        mac = match.group(2)
                        LOG.warning("Found stale ARP entry for {} {} > {} it will be removed from device {}".format(nat.vrf, ip, mac,context.host))
                        config.append("no arp vrf {} {} {}  ARPA alias".format(nat.vrf, ip, mac))

            if bool(config):
                self._edit_running_config(context, config, 'UPDATE_ARP_LIST')
                self._check_result(context,self.base.static_nats, exists=True)

    @retry_on_failure()
    def delete(self, context):
        if bool(self.base.static_nats):
            config= []

            existing = self._get_existing(context)
            for nat in self.base.static_nats:
                if self.ARP_MATCH.format(nat.global_ip, nat.mac_address) in existing:
                    config.append("no arp vrf {} {} {}  ARPA alias".format(nat.vrf,nat.global_ip, nat.mac_address))

            if bool(config):
                self._edit_running_config(context, config, 'DELETE_ARP_LIST')
                self._check_result(context,self.base.static_nats,exists=False)

    def get_neutron_nats(self):
        result = []
        for nat in self.base.static_nats:
            result.append(ARP_MATCH.format(nat.global_ip, nat.mac_address))
        return result

    def _get_existing(self,context):
        existing = self.execute(context, "show arp vrf {} alias | inc Internet".format(self.base.vrf))
        result = []
        if existing is not None:
            for entry in existing:
                result.append(entry.replace(' ',''))
        LOG.debug("VRF {} has {}/{} ARP entries configured on {}".format(self.base.vrf,len(existing),len(self.base.static_nats),context.host))

        return result

    def _check_result(self,context,config,exists=True):
        start = time.time()
        while True:
            if time.time()-start > EXISTS_TIMEOUT:
                LOG.debug("Failed to validate SSH result")
                break
            if exists :
                if self._all_exist(context,config):
                    return True
            else:
                if self._all_missing(context,config):
                    return True

        return False


    def _all_exist(self,context,config):
        on_device = self._check_on_device(context,config)

        return len(on_device) == len(config)

    def _all_missing(self,context, config):
        on_device = self._check_on_device(context,config)

        return len(on_device) == 0

    def _check_on_device(self,context,config):
        on_device = []
        config = config

        existing = self._get_existing(context)
        for nat in config:
           if ARP_MATCH.format(nat.global_ip, nat.mac_address) in existing:
               on_device.append(nat)

        return on_device







class StaticNat(ssh_base.SSHBase):

    @retry_on_failure()
    def delete(self, context):
        existing = self._get_existing(context)
        if ARP_MATCH.format(self.base.global_ip, self.base.mac_address) in existing:
            config = [member.format(**{'vrf': self.base.vrf,'global_ip':self.base.global_ip,'mac_address':self.base.mac_address}) for member in DELETE_ARP]
            self._edit_running_config(context, config, 'DELETE_ARP')

    @retry_on_failure()
    def update(self, context):
        existing = self._get_existing(context)
        if ARP_MATCH.format(self.base.global_ip, self.base.mac_address) not in existing:
            config = [member.format(**{'vrf': self.base.vrf,'global_ip':self.base.global_ip,'mac_address':self.base.mac_address}) for member in UPDATE_ARP]
            self._edit_running_config(context, config, 'UPDATE_ARP')

    def _get_existing(self,context):
        existing = self.execute(context, "show arp vrf {} alias | inc Internet".format(self.base.vrf))
        result = []
        for entry in existing:
            result.append(entry.replace(' ',''))
        return result

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
