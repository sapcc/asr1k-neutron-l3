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
from asr1k_neutron_l3.common import utils


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

        self.specific_acl= True

        # due to https://github.com/sapcc/asr1k-neutron-l3/issues/15 always use
        # a vrf specific NAT ACL for now

        # if gateway_interface is not None:
        #     for interface in self.interfaces.internal_interfaces:
        #         if interface.address_scope == gateway_interface.address_scope:
        #             self.specific_acl = True
        #             break

        # if self.specific_acl:
        #     self.id = utils.vrf_to_access_list_id(self.router_id)
        #     self.old_id = 'nat-all'
        # else:
        #     self.old_id = utils.vrf_to_access_list_id(self.router_id)
        #     self.id = 'nat-all'

        self.id = utils.vrf_to_access_list_id(self.router_id)


    @property
    def _rest_definition(self):

        gateway_ip, gateway_netmask,bridge_domain = [None, None,None]

        if self.gateway_interface is not None:
            bridge_domain  = self.gateway_interface.bridge_domain

        nat = l3_nat.DynamicNat(id=self.id, vrf=self.router_id,bridge_domain=bridge_domain, redundancy=self.redundancy,
                                          mapping_id=self.mapping_id, overload=True)

        # old_nat = l3_nat.DynamicNat(id=self.old_id, vrf=self.router_id,bridge_domain=bridge_domain, redundancy=self.redundancy,
        #                                   mapping_id=self.mapping_id, overload=True)


        return nat


    # def diff(self):
    #
    #     nat = self._rest_definition
    #     return nat.diff()
    #
    # def get(self):
    #     nat = l3_nat.DynamicNat.get(self.id)
    #
    #     return nat
    #
    # def update(self):
    #     nat = self._rest_definition
    #
    #     # old_nat.delete()
    #     nat.update()
    #
    # def delete(self):
    #     nat = self._rest_definition
    #     # old_nat.delete()
    #     nat.delete()


class FloatingIpList(BaseNAT):

    def __init__(self, router_id):
        self.router_id = utils.uuid_to_vrf_id(router_id)
        self.floating_ips = []
        self.count = 0
    @property
    def _rest_definition(self):
        rest_static_nats = []
        for floating_ip in self.floating_ips:
            rest_static_nats.append(floating_ip._rest_definition)

        return l3_nat.StaticNatList(vrf=self.router_id, static_nats=sorted(rest_static_nats, key=lambda static_nat: static_nat.local_ip))

    def append(self, floating_ip):
        self.floating_ips.append(floating_ip)


    def get(self):
        return l3_nat.StaticNatList.get(self.router_id)

    def delete(self):
        return l3_nat.StaticNatList(vrf=self.router_id).delete()

    def update(self):


        return super(FloatingIpList,self).update()


    def __iter__(self):
        return self

    def next(self):
        self.count += 1
        if self.count >= len(self.floating_ips):
            raise StopIteration

        return self.floating_ips[-1]


class FloatingIp(BaseNAT):

    # @classmethod
    # def clean_floating_ips(cls, router):
    #     result = []
    #     vrf = router.vrf.name
    #     fips = router.floating_ips
    #
    #     ids = []
    #     for fip in fips:
    #         ids.append(fip.id)
    #
    #     nat_entries = l3_nat.StaticNat.get_all(filter={l3_nat.NATConstants.VRF: vrf})
    #
    #     for nat_entry in nat_entries:
    #         if not nat_entry.id in ids:
    #             fip = FloatingIp(vrf,
    #                              {'fixed_ip_address': nat_entry.local_ip, 'floating_ip_address': nat_entry.global_ip},
    #                              router.gateway_interface)
    #             fip.delete()
    #
    #     return result

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
        # secondary_ip = l3_interface.BDISecondaryIpAddress.get(self.bridge_domain,self.global_ip)

        # return static_nat,secondary_ip

        return static_nat

