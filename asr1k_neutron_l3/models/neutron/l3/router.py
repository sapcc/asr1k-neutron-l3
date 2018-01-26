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

from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from asr1k_neutron_l3.models import asr1k_pair
from asr1k_neutron_l3.models.neutron.l3 import access_list
from asr1k_neutron_l3.models.neutron.l3 import interface as l3_interface
from asr1k_neutron_l3.models.neutron.l3 import nat
from asr1k_neutron_l3.models.neutron.l3 import route
from asr1k_neutron_l3.models.neutron.l3 import vrf
from asr1k_neutron_l3.models.neutron.l3.base import Base
from asr1k_neutron_l3.plugins.common import asr1k_constants as constants
from asr1k_neutron_l3.plugins.common import utils
from asr1k_neutron_l3.plugins.common.instrument import instrument

LOG = logging.getLogger(__name__)


class Router(Base):

    @classmethod
    def purge(cls, router_id):

        # floating ips
        # static nat
        # routes
        # bdi
        # ACL
        # VRF
        neutron_vrf = vrf.Vrf(router_id)
        neutron_vrf.purge()

    def __init__(self, router_info):
        super(Router, self).__init__()

        self.contexts = asr1k_pair.ASR1KPair().contexts
        self.config = asr1k_pair.ASR1KPair()
        self.router_info = router_info
        self.extra_atts = router_info.get(constants.ASR1K_EXTRA_ATTS_KEY, {})
        self.gateway_interface = None
        self.router_id = self.router_info.get('id')
        self.interfaces = self._build_interfaces()
        self.routes = self._build_routes()
        self.enable_snat = False
        if router_info.get('external_gateway_info') is not None:
            self.enable_snat = router_info.get('external_gateway_info', {}).get('enable_snat', False)

        description = self.router_info.get('description')

        if len(description) == 0:
            description = self.router_id

        self.vrf = vrf.Vrf(self.router_info.get('id'), description)

        self.dynamic_nat = self._build_dynamic_nat()

        self.floating_ips = self._build_floating_ips()

        self.nat_acl = self._build_nat_acl()

    def _build_interfaces(self):
        interfaces = l3_interface.InterfaceList()

        gw_port = self.router_info.get('gw_port')
        if gw_port is not None:
            self.gateway_interface = l3_interface.GatewayInterface(self.router_id, gw_port,
                                                                   self._port_extra_atts(gw_port))
            interfaces.append(self.gateway_interface)

        inf_ports = self.router_info.get('_interfaces', [])
        if inf_ports is not None:
            for inf_port in inf_ports:
                interfaces.append(
                    l3_interface.InternalInterface(self.router_id, inf_port, self._port_extra_atts(inf_port)))

        for port_id in utils.calculate_deleted_ports(self.router_info):
            port = {'id': port_id}
            interfaces.append(l3_interface.OrphanedInterface(self.router_id, port, self._port_extra_atts(port)))

        return interfaces

    def _build_routes(self):
        routes = route.RouteCollection(self.router_id)
        primary_route = self._primary_route()
        if primary_route is not None and self._route_has_connected_interface(primary_route):
            routes.append(primary_route)

        for l3_route in self.router_info.get('routes'):
            ip, netmask = utils.from_cidr(l3_route.get('destination'))

            r = route.Route(self.router_id, ip, netmask, l3_route.get('nexthop'))
            if self._route_has_connected_interface(r):
                routes.append(r)

        return routes

    def _build_nat_acl(self):
        acl = access_list.AccessList("NAT-{}".format(utils.uuid_to_vrf_id(self.router_id)))

        # Check address scope and deny any where internal interface matches externel
        gateway = self.interfaces.gateway_interface
        if gateway is not None:
            for interface in self.interfaces.internal_interfaces:
                if interface.address_scope == gateway.address_scope:
                    subnet = interface.primary_subnet

                    if subnet.get('cidr') is not None:
                        ip, netmask = utils.from_cidr(subnet.get('cidr'))
                        wildcard = utils.to_wildcard_mask(netmask)
                        rule = access_list.Rule(action='deny',source=ip,source_mask=wildcard)
                        acl.append_rule(rule)

        acl.append_rule(access_list.Rule())
        return acl

    def _route_has_connected_interface(self, l3_route):

        gw_port = self.router_info.get('gw_port', None)
        if gw_port is not None:

            for subnet in gw_port.get('subnets'):
                if utils.ip_in_network(l3_route.nexthop, subnet.get('cidr')):
                    return True

        int_ports = self.router_info.get('_interfaces', [])

        for int_port in int_ports:
            for subnet in int_port.get('subnets', []):
                if utils.ip_in_network(l3_route.nexthop, subnet.get('cidr')):
                    return True

        return False

    def _build_dynamic_nat(self):
        return nat.DynamicNAT(self.router_id, self.gateway_interface, self.interfaces.all_interfaces)

    def _build_floating_ips(self):
        floating_ips = []
        for floating_ip in self.router_info.get('_floatingips', []):
            floating_ips.append(nat.FloatingIp(self.router_id, floating_ip, self.gateway_interface))

        return floating_ips

    def _primary_route(self):

        if self.gateway_interface is not None and self.gateway_interface.primary_gateway_ip is not None:
            return route.Route(self.router_id, "0.0.0.0", "0.0.0.0", self.gateway_interface.primary_gateway_ip)

    def _port_extra_atts(self, port):
        return self.extra_atts.get(port.get('id'))


    def create(self):
        self.update()

    @instrument()
    def update(self):

        vrf_result = self.vrf.update()

        for interface in self.interfaces.all_interfaces:
            interface_result = interface.update()
        if self.nat_acl:
            if self.enable_snat and self.gateway_interface is not None:
                self.nat_acl.update()
            else:
                self.nat_acl.delete()
        if self.enable_snat and self.gateway_interface is not None:
            self.dynamic_nat.update()
        else:
            self.dynamic_nat.delete()

            # Clean up static nat
        self.routes.update()
        nat.FloatingIp.clean_floating_ips(self)

        for floating_ip in self.floating_ips:
            floating_ip.update()

    @instrument()
    def delete(self):

        for floating_ip in self.floating_ips:
            floating_ip.delete()

        nat.FloatingIp.clean_floating_ips(self)

        self.routes.delete()
        self.dynamic_nat.delete()
        self.nat_acl.delete()

        for interface in self.interfaces.all_interfaces:
            interface_result = interface.delete()

        self.vrf.delete()

    @instrument()
    def valid(self):
        print(self.vrf.valid())
        print(self.routes.valid())
        print(self.dynamic_nat.valid())
        for floating_ip in self.floating_ips:
            print(floating_ip.valid())

        for interface in self.interfaces.internal_interfaces:
            print(interface.valid())

        if self.interfaces.gateway_interface:
            print(self.interfaces.gateway_interface.valid())

        print (self.nat_acl.valid())