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
from asr1k_neutron_l3.models.netconf_yang import l3_interface_state

from asr1k_neutron_l3.common import utils

LOG = logging.getLogger(__name__)


class InterfaceList(object):
    def __init__(self):
        self.internal_interfaces = []
        self.gateway_interface = None
        self.orphaned_interfaces = []

    def append(self, interface):
        if isinstance(interface, InternalInterface):
            self.internal_interfaces.append(interface)
        elif isinstance(interface, GatewayInterface):
            self.gateway_interface = interface
        elif isinstance(interface, OrphanedInterface):
            self.orphaned_interfaces.append(interface)
        else:
            LOG.warning("Attempt add unknown interface tye {} to interface list".format(interface.__class__.__name__))

    @property
    def all_interfaces(self):
        result = []

        if self.gateway_interface is not None:
            result.append(self.gateway_interface)

        return result + self.internal_interfaces + self.orphaned_interfaces


class Interface(base.Base):
    def __init__(self, router_id, router_port, extra_atts):
        super(Interface, self).__init__()

        self.router_id = router_id
        self.router_port = router_port
        self.extra_atts = extra_atts
        self.id = self.router_port.get('id')
        self.bridge_domain = utils.to_bridge_domain(extra_atts.get('second_dot1q'))
        self.vrf = utils.uuid_to_vrf_id(self.router_id)
        self._primary_subnet_id = None
        self.ip_address = self._ip_address()

        self.secondary_ip_addresses = []
        self.primary_subnet = self._primary_subnet()
        self.primary_gateway_ip = None
        if self.primary_subnet is not None:
            self.primary_gateway_ip = self.primary_subnet.get('gateway_ip')

        self.mac_address = utils.to_cisco_mac(self.router_port.get('mac_address'))
        self.mtu = self.router_port.get('mtu')
        self.address_scope = router_port.get('address_scopes', {}).get('4')

    def add_secondary_ip_address(self, ip_address, netmask):
        self.secondary_ip_addresses.append(l3_interface.BDISecondaryIpAddress(address=ip_address,
                                                                              mask=utils.to_netmask(netmask)))

    def _ip_address(self):
        if self.router_port.get('fixed_ips'):
            n_fixed_ip = next(iter(self.router_port.get('fixed_ips')), None)

            self._primary_subnet_id = n_fixed_ip.get('subnet_id')

            return l3_interface.BDIPrimaryIpAddress(address=n_fixed_ip.get('ip_address'),
                                                    mask=utils.to_netmask(n_fixed_ip.get('prefixlen')))

    def _primary_subnet(self):
        for subnet in self.router_port.get('subnets', []):
            if subnet.get('id') == self._primary_subnet_id:
                return subnet

    @property
    def subnets(self):
        return self.router_port.get('subnets', [])

    def get_state(self):
        state = l3_interface_state.BDIInterfaceState.get(id=self.bridge_domain)

        result = {}
        if state is not None:
            result = state.to_dict()

        return result

    def get(self):
        bdi = l3_interface.BDIInterface.get(self.bridge_domain)
        return bdi

    def delete(self):
        bdi_interface = l3_interface.BDIInterface(name=self.bridge_domain, vrf=self.vrf)
        return bdi_interface.delete()

    def disable_nat(self):
        bdi_interface = l3_interface.BDIInterface(name=self.bridge_domain)
        return bdi_interface.disable_nat()

    def enable_nat(self):
        bdi_interface = l3_interface.BDIInterface(name=self.bridge_domain)
        return bdi_interface.enable_nat()


class GatewayInterface(Interface):

    def __init__(self, router_id, router_port, extra_atts):
        super(GatewayInterface, self).__init__(router_id, router_port, extra_atts)

        self.nat_address = self._nat_address()

        self._rest_definition = l3_interface.BDIInterface(name=self.bridge_domain, description=self.router_id,
                                        mac_address=self.mac_address, mtu=self.mtu, vrf=self.vrf,
                                        ip_address=self.ip_address,
                                        secondary_ip_addresses=self.secondary_ip_addresses, nat_outside=True,
                                        redundancy_group=None, route_map='EXT-TOS', access_group_out='EXT-TOS')

    def _nat_address(self):
        ips = self.router_port.get('fixed_ips')
        if bool(ips):
            for ip in ips:
                address = ip.get('ip_address')

                if address != self.ip_address.address:
                    return address


class InternalInterface(Interface):
    def __init__(self, router_id, router_port, extra_atts):
        super(InternalInterface, self).__init__(router_id, router_port, extra_atts)
        self._rest_definition = l3_interface.BDIInterface(name=self.bridge_domain, description=self.router_id,
                                        mac_address=self.mac_address, mtu=self.mtu, vrf=self.vrf,
                                        ip_address=self.ip_address, secondary_ip_addresses=self.secondary_ip_addresses,
                                        nat_inside=True, redundancy_group=None, route_map="pbr-{}".format(self.vrf))


class OrphanedInterface(Interface):

    def __init__(self, router_id, router_port, extra_atts):
        super(OrphanedInterface, self).__init__(router_id, router_port, extra_atts)

    def update(self):
        return self.delete()
