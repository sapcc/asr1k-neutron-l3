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

from asr1k_neutron_l3.models.neutron.l3 import base
from asr1k_neutron_l3.models.netconf_yang import l3_interface
from asr1k_neutron_l3.models.netconf_yang import nat as l3_nat
from asr1k_neutron_l3.plugins.common import utils


LOG = logging.getLogger(__name__)


class BaseNAT(base.Base):

    def __init__(self, router_id, gateway_interface, redundancy=None, mapping_id=None):
        super(BaseNAT, self).__init__()

        self.router_id = utils.uuid_to_vrf_id(router_id)
        self.gateway_interface = gateway_interface
        self.mapping_id = mapping_id
        self.redundancy = redundancy

        if self.redundancy is None:
            self.redundancy = 1


class DynamicNAT(BaseNAT):

    def __init__(self, router_id, gateway_interface=None,interfaces=[], redundancy=None, mapping_id=None):
        super(DynamicNAT, self).__init__(router_id, gateway_interface,redundancy, mapping_id)


        self.interfaces = interfaces

        self.id = utils.vrf_to_access_list_id(self.router_id)

    @property
    def _rest_definition(self):
        pool = l3_nat.NatPool(id=self.router_id, start_address=self.gateway_interface.ip_address.address,end_address=self.gateway_interface.ip_address.address,netmask=self.gateway_interface.ip_address.mask)
        nat = l3_nat.DynamicNat(id=self.id, vrf=self.router_id, redundancy=self.redundancy,
                                          mapping_id=self.mapping_id, overload=True)
        return pool,nat


    def valid(self):
        device_pool,device_nat = self.get()
        pool, nat = self._rest_definition

        return pool == device_pool and nat == device_nat


    def get(self):
        pool =  l3_nat.NatPool.get(self.router_id)
        nat = l3_nat.DynamicNat.get(self.id)

        return pool,nat


    def update(self):
        pool, nat = self._rest_definition

        pool.update()
        nat.update()


    def delete(self):
        pool, nat = self._rest_definition

        # for interface in self.interfaces:
        #     interface.disable_nat()

        nat.delete()
        pool.delete()

        # for interface in self.interfaces:
        #     interface.enable_nat()




class FloatingIp(BaseNAT):

    @classmethod
    def clean_floating_ips(cls, router):
        result = []
        vrf = router.vrf.name
        fips = router.floating_ips

        ids = []
        for fip in fips:
            ids.append(fip.id)

        nat_entries = l3_nat.StaticNat.get_all(filter={l3_nat.NATConstants.VRF: vrf})

        for nat_entry in nat_entries:
            if not nat_entry.id in ids:
                fip = FloatingIp(vrf,
                                 {'fixed_ip_address': nat_entry.local_ip, 'floating_ip_address': nat_entry.global_ip},
                                 router.gateway_interface)
                fip.delete()

        return result

    def __init__(self, router_id, floating_ip, gateway_interface, redundancy=None, mapping_id=None):
        super(FloatingIp, self).__init__(router_id, gateway_interface, redundancy, mapping_id)

        self.floating_ip = floating_ip
        self.local_ip = floating_ip.get("fixed_ip_address")
        self.global_ip = floating_ip.get("floating_ip_address")
        self.global_ip_mask = gateway_interface.ip_address.mask
        self.bridge_domain = gateway_interface.bridge_domain
        self.id = "{},{}".format(self.local_ip, self.global_ip)

    def _rest_definition(self):
        static_nat = l3_nat.StaticNat(vrf=self.router_id, local_ip=self.local_ip, global_ip=self.global_ip,
                                        mask=self.global_ip_mask, bridge_domain=self.bridge_domain,
                                        redundancy=self.redundancy, mapping_id=self.mapping_id)
        secondary_ip = l3_interface.BDISecondaryIpAddress(bridge_domain=self.bridge_domain, address=self.global_ip,mask=self.global_ip_mask)



        return static_nat,secondary_ip

    def valid(self):
        device_nat,device_secondary = self.get()
        static_nat, secondary_ip = self._rest_definition()

        return static_nat == device_nat and secondary_ip == device_secondary

    def get(self):
        static_nat =  l3_nat.StaticNat.get(self.local_ip,self.global_ip)
        secondary_ip = l3_interface.BDISecondaryIpAddress.get(self.bridge_domain,self.global_ip)

        return static_nat,secondary_ip

    def update(self):
        static_nat,secondary_ip = self._rest_definition()

        return secondary_ip.update(), static_nat.update()

    def delete(self):
        static_nat, secondary_ip = self._rest_definition()

        return secondary_ip.delete(), static_nat.delete()
