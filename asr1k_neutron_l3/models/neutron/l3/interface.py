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

from asr1k_neutron_l3.models import types
from asr1k_neutron_l3.models.neutron.l3 import base
from asr1k_neutron_l3.models.rest import l3_interface
from asr1k_neutron_l3.plugins.common import utils

LOG = logging.getLogger(__name__)


class Interface(base.Base):

    def __init__(self, router_id, router_port, extra_atts):
        super(Interface, self).__init__()

        self.router_id = router_id
        self.router_port = router_port
        self.extra_atts = extra_atts
        self.id = self.router_port.get('id')
        self.bridge_domain = extra_atts.get('bridge_domain')
        self.vrf = utils.uuid_to_vrf_id(self.router_id)
        self._primary_subnet_id = None
        self.ip_address = self._ip_address()
        self.secondary_ip_addresses = []
        self.primary_subnet = self._primary_subnet()
        self.primary_gateway_ip = None
        if self.primary_subnet:
            self.primary_gateway_ip = self.primary_subnet.get('gateway_ip')

        self.mac_address = utils.to_cisco_mac(self.router_port.get('mac_address'))
        self.mtu = self.router_port.get('mtu')

    def update(self):
        pass

    def add_secondary_ip_address(self, ip_address, netmask):
        self.secondary_ip_addresses.append(types.Address(ip_address, netmask))

    def _ip_address(self):
        if self.router_port.get('fixed_ips'):
            n_fixed_ip = next(iter(self.router_port.get('fixed_ips')), None)

            self._primary_subnet_id = n_fixed_ip.get('subnet_id')

            return types.IpAddress(n_fixed_ip.get('ip_address'), n_fixed_ip.get('prefixlen'))

    def _primary_subnet(self):
        for subnet in self.router_port.get('subnets', []):
            if subnet.get('id') == self._primary_subnet_id:
                return subnet


class GatewayInterface(Interface):

    def __init__(self, router_id, router_port, extra_atts):
        super(GatewayInterface, self).__init__(router_id, router_port, extra_atts)

    @base.excute_on_pair
    def update(self, context=None):
        for context in self.contexts:
            bdi = l3_interface.BdiInterface(context, name=self.bridge_domain, description=self.router_id,
                                            mac_address=self.mac_address, mtu=self.mtu, vrf=self.vrf,
                                            ip_address=self.ip_address,
                                            secondary_ip_addresses=self.secondary_ip_addresses, nat_mode="outside",
                                            redundancy_group=None)
            bdi.update()


class InternalInterface(Interface):

    def __init__(self, router_id, router_port, extra_atts):
        super(InternalInterface, self).__init__(router_id, router_port, extra_atts)

    @base.excute_on_pair
    def update(self, context=None):
        bdi = l3_interface.BdiInterface(context, name=self.bridge_domain, description=self.router_id,
                                        mac_address=self.mac_address, mtu=self.mtu, vrf=self.vrf,
                                        ip_address=self.ip_address, secondary_ip_addresses=self.secondary_ip_addresses,
                                        nat_mode="inside", redundancy_group=None)
        bdi.update()


class OrphanedInterface(Interface):

    def __init__(self, router_id, router_port, extra_atts):
        super(OrphanedInterface, self).__init__(router_id, router_port, extra_atts)

    @base.excute_on_pair
    def update(self, context=None):
        # this is going to be a delete we need to remove the intrerface, nat pool and dynamic nat entry
        bdi_interface = l3_interface.BdiInterface.get(context, self.bridge_domain)
        if bdi_interface is not None:
            bdi_interface.delete()
