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
from asr1k_neutron_l3.models.rest import l3_interface
from asr1k_neutron_l3.models.rest import nat as rest_nat
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

    def __init__(self, router_id, gateway_interface=None, redundancy=None, mapping_id=None):
        super(DynamicNAT, self).__init__(router_id, gateway_interface, redundancy, mapping_id)

        self.id = utils.vrf_to_access_list_id(self.router_id)


    def update(self):
        nat_pool = rest_nat.NatPool(id=self.router_id, ip_address=self.gateway_interface.ip_address)
        dyanmic_nat = rest_nat.DynamicNat(id=self.id, vrf=self.router_id, redundancy=self.redundancy,
                                          mapping_id=self.mapping_id)

        nat_pool.update()
        dyanmic_nat.update()


    def delete(self):
        nat_pool = rest_nat.NatPool.get(self.router_id)
        dyanmic_nat = rest_nat.DynamicNat.get(self.id)

        if nat_pool is not None:
            nat_pool.delete()
        if dyanmic_nat is not None:
            dyanmic_nat.delete()


class FloatingIp(BaseNAT):

    @classmethod
    def clean_floating_ips(cls, router):
        result = []
        vrf = router.vrf.id
        fips = router.floating_ips

        ids = []
        for fip in fips:
            ids.append(fip.id)

        nat_entries = rest_nat.StaticNat.get_all(filters={rest_nat.NATConstants.VRF: vrf})

        LOG.debug(nat_entries)
        LOG.debug(ids)

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
        self.global_ip_mask = gateway_interface.ip_address.netmask
        self.bridge_domain = gateway_interface.bridge_domain
        self.id = "{},{}".format(self.local_ip, self.global_ip)

    def update(self):

        static_nat = rest_nat.StaticNat(vrf=self.router_id, local_ip=self.local_ip, global_ip=self.global_ip,
                                    global_ip_netmask=self.global_ip_mask, bridge_domain=self.bridge_domain,
                                    redundancy=self.redundancy, mapping_id=self.mapping_id)
        static_nat.update()

        secondary = l3_interface.BDISecondaryIpAddress(self.bridge_domain, address=self.global_ip,
                                                   mask=utils.to_netmask(self.global_ip_mask))
        return secondary.update(), static_nat.update()


    def delete(self):
        static_nat = rest_nat.StaticNat(vrf=self.router_id, local_ip=self.local_ip, global_ip=self.global_ip)


        secondary = l3_interface.BDISecondaryIpAddress(self.bridge_domain, address=self.global_ip)
        return secondary.delete(), static_nat.delete()
