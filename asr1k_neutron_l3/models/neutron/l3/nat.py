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
from oslo_config import cfg
from asr1k_neutron_l3.models.neutron.l3 import base
from asr1k_neutron_l3.models.netconf_yang import arp as l3_arp
from asr1k_neutron_l3.models.netconf_yang import nat as l3_nat
from asr1k_neutron_l3.common import utils,asr1k_constants


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

class NATPool(base.Base):
    def __init__(self, router_id, gateway_interface=None):
        super(NATPool, self).__init__()
        self.router_id = utils.uuid_to_vrf_id(router_id)
        self.gateway_interface = gateway_interface

    @property
    def _rest_definition(self):
        nat_ip = None
        gateway_netmask=None
        if self.gateway_interface is not None:
            nat_ip = self.gateway_interface.nat_address
            gateway_netmask = self.gateway_interface.ip_address.mask

        return  l3_nat.NatPool(id=self.router_id, start_address=nat_ip, end_address=nat_ip,
                                  netmask=gateway_netmask)
class DynamicNAT(BaseNAT):

    def __init__(self, router_id, gateway_interface=None,interfaces=[], redundancy=None, mapping_id=None, mode=asr1k_constants.SNAT_MODE_POOL):
        super(DynamicNAT, self).__init__(router_id, gateway_interface,redundancy, mapping_id)


        self.interfaces = interfaces

        self.specific_acl= True
        self.mode = mode

        self.id = utils.vrf_to_access_list_id(self.router_id)


    @property
    def _rest_definition(self):

        bridge_domain=None
        if self.gateway_interface is not None:
            bridge_domain  = self.gateway_interface.bridge_domain

        if self.mode == asr1k_constants.SNAT_MODE_POOL:
            return l3_nat.PoolDynamicNat(id=self.id, vrf=self.router_id, pool=self.router_id, bridge_domain=bridge_domain,
                                     redundancy=self.redundancy,
                                     mapping_id=self.mapping_id, overload=True)

        elif self.mode == asr1k_constants.SNAT_MODE_INTERFACE:
            return l3_nat.InterfaceDynamicNat(id=self.id, vrf=self.router_id, pool=self.router_id, bridge_domain=bridge_domain,
                                     redundancy=self.redundancy,
                                     mapping_id=self.mapping_id, overload=True)



class NatList(BaseNAT):
    yang_model = None


    def __init__(self, router_id):
        self.router_id = utils.uuid_to_vrf_id(router_id)
        self.items = []
        self.count = 0

    def append(self, item):
        self.items.append(item)


    def get(self):
        if self.yang_model is not None:
            return self.yang_model.get(self.router_id)

    def delete(self):
        if self.yang_model is not None:
            return self.yang_model(vrf=self.router_id).delete()

    def update(self):
        return super(NatList,self).update()


    def __iter__(self):
        return self

    def next(self):
        self.count += 1
        if self.count >= len(self.items):
            raise StopIteration

        return self.items[-1]


class FloatingIpList(NatList):

    yang_model = l3_nat.StaticNatList

    @property
    def _rest_definition(self):
        rest_static_nats = []
        for floating_ip in self.items:
            rest_static_nats.append(floating_ip._rest_definition)

        return l3_nat.StaticNatList(vrf=self.router_id, static_nats=rest_static_nats)


class ArpList(NatList):
    yang_model = l3_arp.VrfArpList

    @property
    def _rest_definition(self):
        rest_arps = []
        for arp in self.items:
            rest_arps.append(arp._rest_definition)

        return l3_arp.VrfArpList(vrf=self.router_id, arp_entry=rest_arps)


class FloatingIp(BaseNAT):

    def __init__(self, router_id, floating_ip, gateway_interface, redundancy=None, mapping_id=None):
        super(FloatingIp, self).__init__(router_id, gateway_interface, redundancy, mapping_id)

        self.floating_ip = floating_ip
        self.local_ip = floating_ip.get("fixed_ip_address")
        self.global_ip = floating_ip.get("floating_ip_address")
        self.global_ip_mask = gateway_interface.ip_address.mask
        self.bridge_domain = gateway_interface.bridge_domain
        self.id = "{},{}".format(self.local_ip, self.global_ip)
        self.mapping_id = utils.uuid_to_mapping_id(self.floating_ip.get('id'))
        self.mac_address = None
        if self.gateway_interface:
            self.mac_address = self.gateway_interface.mac_address
        self._rest_definition = l3_nat.StaticNat(vrf=self.router_id, local_ip=self.local_ip, global_ip=self.global_ip,
                                        mask=self.global_ip_mask, bridge_domain=self.bridge_domain,
                                        redundancy=self.redundancy, mapping_id=self.mapping_id,mac_address=self.mac_address,match_in_vrf=True)


    def get(self):
        static_nat =  l3_nat.StaticNat.get(self.local_ip,self.global_ip)
        return static_nat


class ArpEntry(BaseNAT):

    def __init__(self, router_id, floating_ip, gateway_interface):
        super(ArpEntry, self).__init__(router_id, gateway_interface)

        self.ip = floating_ip.get("floating_ip_address")
        self.id = self.ip
        self.mac_address = None
        if self.gateway_interface:
            self.mac_address = self.gateway_interface.mac_address

        self._rest_definition = l3_arp.ArpEntry(vrf=self.router_id, ip=self.ip, hardware_address=self.mac_address)


    def get(self):
        arp_entry =  l3_arp.ArpEntry.get(self.vrf,self.ip)

        return arp_entry


