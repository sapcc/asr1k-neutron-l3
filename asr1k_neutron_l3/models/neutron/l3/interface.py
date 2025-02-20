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
import netaddr
from oslo_config import cfg
from oslo_log import log as logging

from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.models.neutron.l3 import base
from asr1k_neutron_l3.models.neutron.l3.firewall import Zone
from asr1k_neutron_l3.models.netconf_yang.l3_interface import BDInterface, BDPrimaryIpAddress, BDSecondaryIpAddress, \
    BDIpv6Address, TrafficFilter
from asr1k_neutron_l3.models.netconf_yang.l3_interface_state import BDInterfaceState

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

    def get_internal_networks(self, ip_version):
        cidrs = []
        for interface in self.internal_interfaces:
            for subnet in interface.subnets:
                if subnet.get('cidr') and utils.get_ip_version(subnet['cidr']) == ip_version:
                    cidrs.append(subnet['cidr'])
        cidrs.sort()
        return cidrs

    def get_internal_networks_v4(self):
        return self.get_internal_networks(4)

    def get_internal_networks_v6(self):
        return self.get_internal_networks(6)

    def get_external_networks(self, ip_version):
        if not self.gateway_interface:
            return []

        return [subnet['cidr']
                for subnet in self.gateway_interface.subnets
                if subnet.get('cidr') and utils.get_ip_version(subnet['cidr']) == ip_version]

    def get_external_networks_v4(self):
        return self.get_external_networks(4)

    def get_external_networks_v6(self):
        return self.get_external_networks(6)

    def get_routable_networks(self, ip_version):
        if not self.gateway_interface:
            return []

        # routable networks are networks for which the subnet's subnet pool address scope
        # matches the address scope of the external gateway
        scope_key = {4: "address_scope_v4", 6: "address_scope_v6"}[ip_version]

        gw_scope_id = getattr(self.gateway_interface, scope_key, None)
        if not gw_scope_id:
            return []

        subnets = []
        for interface in self.internal_interfaces:
            for subnet in interface.subnets:
                if subnet['address_scope_id'] == gw_scope_id and utils.get_ip_version(subnet['cidr']) == ip_version:
                    subnets.append(subnet['cidr'])

        return subnets

    def get_routable_networks_v4(self):
        return self.get_routable_networks(4)

    def get_routable_networks_v6(self):
        return self.get_routable_networks(6)


class Interface(base.Base):
    def __init__(self, router_id, router_port, extra_atts):
        super().__init__()

        self.router_port = router_port
        self.id = self.router_port.get('id')
        self.router_id = router_id
        self.vrf = utils.uuid_to_vrf_id(self.router_id)
        self.extra_atts = extra_atts
        self.bridge_domain = utils.to_bridge_domain(extra_atts.get('second_dot1q'))

        self._primary_v4_subnet_id = None
        self._primary_v6_subnet_id = None
        self.gateway_ip_v4 = None
        self.gateway_ip_v6 = None
        self.address_scope_v4 = router_port.get('address_scopes', {}).get('4')
        self.address_scope_v6 = router_port.get('address_scopes', {}).get('6')
        self.secondary_ip_addresses = []  # NOTE(seba): I don't think this is being used
        self.ipv4_address = self._ipv4_address()
        self.ipv6_addresses = self._ipv6_addresses()
        self._set_gateway_ips()

        self.mac_address = utils.to_cisco_mac(self.router_port.get('mac_address'))
        self.mtu = self.router_port.get('mtu')

        self.has_stateful_firewall = False

    def add_secondary_ip_address(self, ip_address, netmask):
        self.secondary_ip_addresses.append(BDSecondaryIpAddress(address=ip_address,
                                           mask=utils.to_netmask(netmask)))

    def _ipv4_address(self):
        for n_fixed_ip in self.router_port.get('fixed_ips', []):
            if utils.get_ip_version(n_fixed_ip['ip_address']) == 4:
                self._primary_v4_subnet_id = n_fixed_ip.get('subnet_id')
                return BDPrimaryIpAddress(address=n_fixed_ip.get('ip_address'),
                                          mask=utils.to_netmask(n_fixed_ip.get('prefixlen')))
        return None

    def _ipv6_addresses(self):
        ipv6_addrs = []
        for n_fixed_ip in self.router_port.get('fixed_ips', []):
            if utils.get_ip_version(n_fixed_ip['ip_address']) == 6:
                self._primary_v6_subnet_id = n_fixed_ip.get('subnet_id')
                ipv6_addrs.append(BDIpv6Address(prefix=f"{n_fixed_ip['ip_address']}/{n_fixed_ip['prefixlen']}"))
        return ipv6_addrs

    def _set_gateway_ips(self):
        for subnet in self.router_port.get('subnets', []):
            if subnet['id'] == self._primary_v4_subnet_id:
                self.gateway_ip_v4 = subnet['gateway_ip']
            elif subnet['id'] == self._primary_v6_subnet_id:
                self.gateway_ip_v6 = subnet['gateway_ip']

    @property
    def subnets(self):
        return self.router_port.get('subnets', [])

    def get_state(self):
        state = BDInterfaceState.get(id=self.bridge_domain)

        result = {}
        if state is not None:
            result = state.to_dict()

        return result

    def get(self):
        return BDInterface.get(self.bridge_domain)

    def delete(self):
        vbi = BDInterface(name=self.bridge_domain, vrf=self.vrf)
        return vbi.delete()


class GatewayInterface(Interface):

    def __init__(self, router_id, router_port, extra_atts, dynamic_nat_pool):
        self.dynamic_nat_pool = dynamic_nat_pool
        super().__init__(router_id, router_port, extra_atts)

        # annotate details about the router to the interface description so this can be picked up by SNMP

    @property
    def _rest_definition(self):
        description = (f'type:gw;router:{self.router_id};network:{self.router_port["network_id"]};'
                       f'subnet:{self._primary_v4_subnet_id or self._primary_v6_subnet_id}')

        interface_args = dict(name=self.bridge_domain, description=description,
                              mac_address=self.mac_address, mtu=self.mtu, vrf=self.vrf,
                              ip_address=self.ipv4_address, ipv6_addresses=self.ipv6_addresses,
                              secondary_ip_addresses=self.secondary_ip_addresses, nat_outside=True,
                              redundancy_group=None, route_map='EXT-TOS', access_group_out='EXT-TOS',
                              ntp_disable=True, arp_timeout=cfg.CONF.asr1k_l3.external_iface_arp_timeout)

        if self.ipv6_addresses:
            interface_args['policy_map_v6'] = 'RM-EXT-TOS-V6'
            interface_args['traffic_filters_v6'] = [TrafficFilter(direction="out", access_list="ACL-EXT-TOS-V6")]

        if self.has_stateful_firewall:
            interface_args['redundancy_group'] = 1
            interface_args['redundancy_group_decrement'] = 1
            interface_args['rii'] = self.bridge_domain
            interface_args['zone'] = Zone.get_id_by_vrf(self.vrf)

        return BDInterface(**interface_args)

    def _ipv4_address(self):
        # NOTE(seba): this method is only here to find the IPs not part of the dynamic nat pool
        if self.dynamic_nat_pool is None or not self.router_port.get('fixed_ips'):
            return super()._ipv4_address()

        ips, _ = self.dynamic_nat_pool.split("/")
        start_ip, end_ip = ips.split("-")
        ip_pool = netaddr.IPSet(netaddr.IPRange(start_ip, end_ip))
        for n_fixed_ip in self.router_port['fixed_ips']:
            # filter out v6
            if utils.get_ip_version(n_fixed_ip['ip_address']) != 4:
                continue

            if n_fixed_ip['ip_address'] not in ip_pool:
                break
        else:
            LOG.error("VRF %s gateway interface has no IP that is not part of dynamic NAT pool %s, "
                      "not configuring primary IP",
                      self.vrf, self.dynamic_nat_pool)
            return None

        self._primary_v4_subnet_id = n_fixed_ip.get('subnet_id')

        return BDPrimaryIpAddress(address=n_fixed_ip['ip_address'],
                                  mask=utils.to_netmask(n_fixed_ip.get('prefixlen')))


class InternalInterface(Interface):
    def __init__(self, router_id, router_port, extra_atts, ingress_acl=None, egress_acl=None):
        super().__init__(router_id, router_port, extra_atts)
        self.ingress_acl = ingress_acl
        self.egress_acl = egress_acl

    @property
    def _rest_definition(self):
        # annotate details about the router to the interface description so this can be picked up by SNMP
        description = (f'type:internal;project:{self.router_port["project_id"]};router:{self.router_id};'
                       f'network:{self.router_port["network_id"]};'
                       f'subnet:{self._primary_v4_subnet_id or self._primary_v6_subnet_id}')

        interface_args = dict(name=self.bridge_domain, description=description,
                              mac_address=self.mac_address, mtu=self.mtu, vrf=self.vrf,
                              ip_address=self.ipv4_address, ipv6_addresses=self.ipv6_addresses,
                              secondary_ip_addresses=self.secondary_ip_addresses,
                              nat_inside=True, redundancy_group=None, route_map="pbr-{}".format(self.vrf),
                              ntp_disable=True,
                              arp_timeout=cfg.CONF.asr1k_l3.internal_iface_arp_timeout,
                              access_group_out=self.egress_acl,
                              access_group_in=self.ingress_acl)

        if self.has_stateful_firewall:
            interface_args['redundancy_group'] = 1
            interface_args['redundancy_group_decrement'] = 1
            interface_args['rii'] = self.bridge_domain

        return BDInterface(**interface_args)


class OrphanedInterface(Interface):

    def __init__(self, router_id, router_port, extra_atts):
        super().__init__(router_id, router_port, extra_atts)

    def update(self):
        return self.delete()
