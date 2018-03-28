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

from asr1k_neutron_l3.models import asr1k_pair
from asr1k_neutron_l3.models.neutron.l3 import access_list
from asr1k_neutron_l3.models.neutron.l3 import interface as l3_interface
from asr1k_neutron_l3.models.neutron.l3 import nat
from asr1k_neutron_l3.models.neutron.l3 import route
from asr1k_neutron_l3.models.neutron.l3 import vrf
from asr1k_neutron_l3.models.neutron.l3 import route_map
from asr1k_neutron_l3.models.neutron.l3 import bgp
from asr1k_neutron_l3.models.neutron.l3 import prefix
from asr1k_neutron_l3.models.neutron.l3.base import Base
from asr1k_neutron_l3.common import asr1k_constants as constants, utils
from asr1k_neutron_l3.common.instrument import instrument

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
        self.config = asr1k_pair.ASR1KPair().config
        self.router_info = router_info
        self.extra_atts = router_info.get(constants.ASR1K_EXTRA_ATTS_KEY, {})
        self.router_atts = router_info.get(constants.ASR1K_ROUTER_ATTS_KEY, {})
        self.gateway_interface = None
        self.router_id = self.router_info.get('id')
        self.interfaces = self._build_interfaces()
        self.routes = self._build_routes()
        self.enable_snat = False
        self.routeable_interface=False
        if router_info.get('external_gateway_info') is not None:
            self.enable_snat = router_info.get('external_gateway_info', {}).get('enable_snat', False)
            self.routeable_interface =  len(self.address_scope_matches()) > 0


        description = self.router_info.get('description')

        if len(description) == 0:
            description = self.router_id

        #TODO : get rt's from config for router
        address_scope_config = router_info.get(constants.ADDRESS_SCOPE_CONFIG,{})

        rt = None
        if self.gateway_interface is not None:
            rt = address_scope_config.get(self.gateway_interface.address_scope)

        self.vrf = vrf.Vrf(self.router_info.get('id'), description=description, asn=self.config.asr1k_l3.fabric_asn, rd=self.router_atts.get('rd'),routeable_interface=self.routeable_interface)



        self.route_map = route_map.RouteMap(self.router_info.get('id'), rt=rt,routeable_interface=self.routeable_interface)

        self.bgp_address_family = bgp.AddressFamily(self.router_info.get('id'),asn=self.config.asr1k_l3.fabric_asn,routeable_interface=self.routeable_interface)

        self.dynamic_nat = self._build_dynamic_nat()

        self.floating_ips = self._build_floating_ips()

        self.nat_acl = self._build_nat_acl()

        self.prefix_lists = self._build_prefix_lists()

    def address_scope_matches(self):
        result = []
        if self.gateway_interface is not None:
            for interface in self.interfaces.internal_interfaces:
                if interface.address_scope == self.gateway_interface.address_scope:
                    result.append(interface)
        return result

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
        acl = access_list.AccessList("NAT-{}".format(utils.uuid_to_vrf_id(self.router_id)), routeable_interfaces=self.address_scope_matches())


        # Check address scope and deny any where internal interface matches externel
        for interface in self.address_scope_matches():
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
        return nat.DynamicNAT(self.router_id, gateway_interface=self.gateway_interface, interfaces=self.interfaces)

    def _build_floating_ips(self):
        floating_ips = []
        for floating_ip in self.router_info.get('_floatingips', []):
            floating_ips.append(nat.FloatingIp(self.router_id, floating_ip, self.gateway_interface))

        return floating_ips


    def _build_prefix_lists(self):
        result = []

        # external interface
        result.append(prefix.ExtPrefix(router_id=self.router_id, gateway_interface=self.gateway_interface))

        no_snat_interfaces = self.address_scope_matches()

        result.append(prefix.SnatPrefix(router_id=self.router_id,gateway_interface=self.gateway_interface,internal_interfaces=no_snat_interfaces))

        return result

    def _primary_route(self):

        if self.gateway_interface is not None and self.gateway_interface.primary_gateway_ip is not None:
            return route.Route(self.router_id, "0.0.0.0", "0.0.0.0", self.gateway_interface.primary_gateway_ip)

    def _port_extra_atts(self, port):
        return self.extra_atts.get(port.get('id'),{})

    def create(self):
        self.update()

    @instrument()
    def update(self):
        results = []
        if self.gateway_interface is None and len(self.interfaces.internal_interfaces)==0:
            return self.delete()

        # Order is  important if as we switch from BGP <> non BGP
        # if self.routeable_interface:
        #     for prefix_list in self.prefix_lists:
        #         prefix_list.update()
        #     self.route_map.update()
        #     self.vrf.update()
        #     self.bgp_address_family.update()
        # else:
        #
        #     self.route_map.delete()
        #     for prefix_list in self.prefix_lists:
        #         prefix_list.delete()
        #     self.vrf.update()
        #     self.bgp_address_family.delete()

        for prefix_list in self.prefix_lists:
            prefix_list.update()
        self.route_map.update()
        self.vrf.update()

        if self.routeable_interface:
            self.bgp_address_family.update()
        else:
            self.bgp_address_family.delete()


        for interface in self.interfaces.all_interfaces:
            interface.update()


        if self.nat_acl:
            # if self.enable_snat and self.gateway_interface is not None:
            #     self.nat_acl.update()
            # else:
            #     self.nat_acl.delete()
            self.nat_acl.update()


        if  self.enable_snat and self.gateway_interface is not None:
            self.dynamic_nat.update()
        else:
            self.dynamic_nat.delete()


        self.routes.update()

        # Clean up static nat
        nat.FloatingIp.clean_floating_ips(self)

        for floating_ip in self.floating_ips:
            floating_ip.update()

    @instrument()
    def delete(self):

        # order is important here.

        for prefix_list in self.prefix_lists:
            prefix_list.delete()

        if len(self.prefix_lists) ==0:
            prefix.SnatPrefix(router_id=self.router_id).delete()
            prefix.ExtPrefix(router_id=self.router_id).delete()

        self.route_map.delete()

        for floating_ip in self.floating_ips:
            floating_ip.delete()

        nat.FloatingIp.clean_floating_ips(self)

        self.routes.delete()
        self.dynamic_nat.delete()
        self.nat_acl.delete()

        for interface in self.interfaces.all_interfaces:
            interface.delete()




        self.bgp_address_family.delete()

        self.vrf.delete()

    @instrument()
    def diff(self):
        diff_results = {}

        vrf_diff = self.vrf.diff()
        if not vrf_diff.valid:
            diff_results['vrf'] = vrf_diff.to_dict()

        bgp_diff = self.bgp_address_family.diff()

        if not bgp_diff.valid:
            diff_results['bgp'] = bgp_diff.to_dict()


        for prefix_list in self.prefix_lists:
            prefix_diff = prefix_list.diff()
            if not prefix_diff.valid:
                diff_results['prefix_list'] = prefix_diff.to_dict()


        rm_diff =self.route_map.diff()
        if not rm_diff.valid:
            diff_results['route_map'] = rm_diff.to_dict()

        route_diff = self.routes.diff()
        if not route_diff.valid:
            diff_results['route'] = route_diff.to_dict()

        dynamic_nat_diff = self.dynamic_nat.diff()
        if not dynamic_nat_diff.valid:
            diff_results['dynamic_nat'] = dynamic_nat_diff.to_dict()


        for floating_ip in self.floating_ips:
            floating_ip_diff = floating_ip.diff()
            if not floating_ip_diff.valid:
                diff_results['static_nat'] = floating_ip_diff.to_dict()

        for interface in self.interfaces.internal_interfaces:
            interface_diff = interface.diff()
            if not interface_diff.valid:
                diff_results['internal_interface'] = interface_diff.to_dict()

        if self.interfaces.gateway_interface:
            gateway_diff = self.interfaces.gateway_interface.diff()
            if not gateway_diff.valid:
                diff_results['gateway_interface'] = gateway_diff.to_dict()

        nat_acl_diff = self.nat_acl.diff()
        if not nat_acl_diff.valid:
            diff_results['nat_acl'] = nat_acl_diff.to_dict()


        return diff_results


