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
import os

from oslo_log import log as logging
from oslo_config import cfg

from asr1k_neutron_l3.common import asr1k_constants as constants, utils
from asr1k_neutron_l3.common.prometheus_monitor import PrometheusMonitor
from asr1k_neutron_l3.models import asr1k_pair
from asr1k_neutron_l3.models.neutron.l3 import access_list
from asr1k_neutron_l3.models.neutron.l3.base import Base
from asr1k_neutron_l3.models.neutron.l3 import bgp
from asr1k_neutron_l3.models.neutron.l3 import interface as l3_interface
from asr1k_neutron_l3.models.neutron.l3 import nat
from asr1k_neutron_l3.models.neutron.l3 import prefix
from asr1k_neutron_l3.models.neutron.l3 import route
from asr1k_neutron_l3.models.neutron.l3 import route_map
from asr1k_neutron_l3.models.neutron.l3 import vrf

LOG = logging.getLogger(__name__)


class Router(Base):
    def __init__(self, router_info):
        super(Router, self).__init__()

        self.contexts = asr1k_pair.ASR1KPair().contexts
        self.config = asr1k_pair.ASR1KPair().config
        self.router_info = router_info
        self.extra_atts = router_info.get(constants.ASR1K_EXTRA_ATTS_KEY, {})
        self.router_atts = router_info.get(constants.ASR1K_ROUTER_ATTS_KEY, {})
        self.rt_import = self.router_info.get('rt_import')
        self.rt_export = self.router_info.get('rt_export')

        self.status = self.router_info.get('status')

        self.gateway_interface = None
        self.router_id = self.router_info.get('id')
        self.interfaces = self._build_interfaces()
        self.routes = self._build_routes()
        self.enable_snat = False
        self.routable_interface = False
        if router_info.get('external_gateway_info') is not None:
            self.enable_snat = router_info.get('external_gateway_info', {}).get('enable_snat', False)
            self.routable_interface = len(self.address_scope_matches()) > 0

        description = self.router_info.get('description')

        if description is None or len(description) == 0:
            description = "Router {}".format(self.router_id)

        # TODO : get rt's from config for router
        address_scope_config = router_info.get(constants.ADDRESS_SCOPE_CONFIG, {})

        rt = None
        global_vrf_id = None
        if self.gateway_interface is not None:
            if self.gateway_interface.address_scope in address_scope_config:
                rt = address_scope_config[self.gateway_interface.address_scope]
                global_vrf_id = self._to_global_vrf_id(rt)
            else:
                LOG.error("Router %s has a gateway interface, but no address scope was found in config"
                          "(address scope of router: %s, available scopes: %s",
                          self.router_id, self.gateway_interface.address_scope, list(address_scope_config.keys()))

        if not self.router_atts.get('rd'):
            LOG.error("Router %s has no rd attached, configuration is likely to fail!",
                      self.router_info.get('id'))

        self.vrf = vrf.Vrf(self.router_info.get('id'), description=description, asn=self.config.asr1k_l3.fabric_asn,
                           rd=self.router_atts.get('rd'), routable_interface=self.routable_interface,
                           rt_import=self.rt_import, rt_export=self.rt_export, global_vrf_id=global_vrf_id)

        self.nat_acl = self._build_nat_acl()
        self.pbr_acl = self._build_pbr_acl()

        self.route_map = route_map.RouteMap(self.router_info.get('id'), rt=rt,
                                            routable_interface=self.routable_interface)

        self.pbr_route_map = route_map.PBRRouteMap(self.router_info.get('id'), gateway_interface=self.gateway_interface)

        self.bgp_address_family = self._build_bgp_address_family()

        self.dynamic_nat = self._build_dynamic_nat()
        self.nat_pool = self._build_nat_pool()

        self.floating_ips = self._build_floating_ips()
        self.arp_entries = self._build_arp_entries()

        self.prefix_lists = self._build_prefix_lists()

    def _to_global_vrf_id(self, rt):
        # 65126:106 --> 6
        global_vrf_id = int(rt.split(":")[1]) - 100
        if global_vrf_id < 0:
            LOG.error("Global vrf id for rt %s was %s, needs to be >= 0! Continuing, but unlikely to succeed",
                      rt, global_vrf_id)
        return global_vrf_id

    def address_scope_matches(self):
        result = []
        if self.gateway_interface is not None:
            for interface in self.interfaces.internal_interfaces:
                if self.gateway_interface.address_scope is not None:
                    if interface.address_scope == self.gateway_interface.address_scope:
                        result.append(interface)
        result = sorted(result, key=lambda _iface: _iface.id)
        return result

    def get_routable_networks(self):
        return [iface.primary_subnet['cidr'] for iface in self.address_scope_matches()]

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

    def get_internal_cidrs(self):
        return [iface.primary_subnet['cidr'] for iface in self.interfaces.internal_interfaces]

    def _build_routes(self):
        routes = route.RouteCollection(self.router_id)

        # In case the customer sets a default route, we will restrain from programming the openstack primary route
        primary_overridden = False
        for l3_route in self.router_info.get('routes', []):
            ip, netmask = utils.from_cidr(l3_route.get('destination'))
            if netmask == '0.0.0.0':
                primary_overridden = True

            r = route.Route(self.router_id, ip, netmask, l3_route.get('nexthop'))
            if self._route_has_connected_interface(r):
                routes.append(r)

        primary_route = self._primary_route()
        if not primary_overridden and primary_route is not None and self._route_has_connected_interface(primary_route):
            routes.append(primary_route)

        return routes

    def _build_nat_acl(self):
        acl = access_list.AccessList("NAT-{}".format(utils.uuid_to_vrf_id(self.router_id)))

        # Check address scope and deny any where internal interface matches externel
        for interface in self.address_scope_matches():
            subnet = interface.primary_subnet

            if subnet is not None and subnet.get('cidr') is not None:
                ip, netmask = utils.from_cidr(subnet.get('cidr'))
                wildcard = utils.to_wildcard_mask(netmask)
                rule = access_list.Rule(action='deny', source=ip, source_mask=wildcard)
                acl.append_rule(rule)

        if not self.enable_snat:
            acl.append_rule(access_list.Rule(action='deny'))
        else:
            acl.append_rule(access_list.Rule())
        return acl

    def _build_pbr_acl(self):
        acl = access_list.AccessList("PBR-{}".format(utils.uuid_to_vrf_id(self.router_id)), drop_on_17_3=True)

        if self.gateway_interface:
            subnet = self.gateway_interface.primary_subnet

            if subnet.get('cidr') is not None:
                ip, netmask = utils.from_cidr(subnet.get('cidr'))
                wildcard = utils.to_wildcard_mask(netmask)
                rule = access_list.Rule(destination=ip, destination_mask=wildcard)
                acl.append_rule(rule)

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

    def _build_bgp_address_family(self):
        connected_cidrs = self.get_internal_cidrs()
        extra_routes = list()
        if self.router_info["bgpvpn_advertise_extra_routes"]:
            extra_routes = [x.cidr for x in self.routes.routes if x.cidr != "0.0.0.0/0"]

        return bgp.AddressFamily(self.router_info.get('id'), asn=self.config.asr1k_l3.fabric_asn,
                                 routable_interface=self.routable_interface,
                                 rt_export=self.rt_export, connected_cidrs=connected_cidrs,
                                 routable_networks=self.get_routable_networks(),
                                 extra_routes=extra_routes)

    def _build_dynamic_nat(self):
        pool_nat = nat.DynamicNAT(self.router_id, gateway_interface=self.gateway_interface,
                                  interfaces=self.interfaces, mode=constants.SNAT_MODE_POOL)
        interface_nat = nat.DynamicNAT(self.router_id, gateway_interface=self.gateway_interface,
                                       interfaces=self.interfaces, mode=constants.SNAT_MODE_INTERFACE)

        return {constants.SNAT_MODE_POOL: pool_nat, constants.SNAT_MODE_INTERFACE: interface_nat}

    def _build_nat_pool(self):
        return nat.NATPool(self.router_id, gateway_interface=self.gateway_interface)

    def _build_floating_ips(self):
        floating_ips = nat.FloatingIpList(self.router_id)
        for floating_ip in self.router_info.get('_floatingips', []):
            floating_ips.append(nat.FloatingIp(self.router_id, floating_ip, self.gateway_interface))

        return floating_ips

    def _build_arp_entries(self):
        arp_entries = nat.ArpList(self.router_id)
        for floating_ip in self.router_info.get('_floatingips', []):
            arp_entries.append(nat.ArpEntry(self.router_id, floating_ip, self.gateway_interface))

        return arp_entries

    def _build_prefix_lists(self):
        result = []

        # external interface
        result.append(prefix.ExtPrefix(router_id=self.router_id, gateway_interface=self.gateway_interface))

        no_snat_interfaces = self.address_scope_matches()

        result.append(prefix.SnatPrefix(router_id=self.router_id, gateway_interface=self.gateway_interface,
                                        internal_interfaces=no_snat_interfaces))

        result.append(prefix.RoutePrefix(router_id=self.router_id, gateway_interface=self.gateway_interface,
                                         internal_interfaces=no_snat_interfaces))

        return result

    def _primary_route(self):
        if self.gateway_interface is not None and self.gateway_interface.primary_gateway_ip is not None:
            return route.Route(self.router_id, "0.0.0.0", "0.0.0.0", self.gateway_interface.primary_gateway_ip)

    def _port_extra_atts(self, port):
        try:
            if self.extra_atts is not None:
                return self.extra_atts.get(port.get('id'), {})
            else:
                LOG.error("Cannot get  extra atts from {} for port {} on router {}"
                          "".format(self.extra_atts, port.get('id'), self.router_id))
                return {}
        except BaseException as e:

            raise e

    def create(self):
        with PrometheusMonitor().router_create_duration.time():
            result = self._update()

        return result

    def update(self):
        with PrometheusMonitor().router_update_duration.time():
            result = self._update()

        return result

    def delete(self):
        with PrometheusMonitor().router_delete_duration.time():
            result = self._delete()

            return result

    def _update(self):
        if self.gateway_interface is None and len(self.interfaces.internal_interfaces) == 0:
            return self.delete()

        results = []

        for prefix_list in self.prefix_lists:
            results.append(prefix_list.update())

        results.append(self.route_map.update())
        results.append(self.vrf.update())

        if self.gateway_interface is not None:
            results.append(self.pbr_route_map.update())
        else:
            results.append(self.pbr_route_map.delete())

        # results.append(self.bgp_address_family.update())

        if self.routable_interface or len(self.rt_export) > 0:
            results.append(self.bgp_address_family.update())
        else:
            results.append(self.bgp_address_family.delete())

        if self.nat_acl:
            results.append(self.nat_acl.update())

        if self.pbr_acl:
            results.append(self.pbr_acl.update())
        # Working assumption is that any NAT mode migration is completed

        results.append(self.routes.update())
        results.append(self.floating_ips.update())
        results.append(self.arp_entries.update())

        # process interface configuration before we configure nat
        for interface in self.interfaces.all_interfaces:
            if not isinstance(interface, l3_interface.OrphanedInterface):
                results.append(interface.update())

        # We don't remove NAT statement or pool if enabling/disabling snat - instead update ACL
        if self.gateway_interface is not None:
            if cfg.CONF.asr1k_l3.snat_mode == constants.SNAT_MODE_POOL:
                results.append(self.dynamic_nat[constants.SNAT_MODE_INTERFACE].delete())
                results.append(self.nat_pool.update())
                results.append(self.dynamic_nat[constants.SNAT_MODE_POOL].update())
            elif cfg.CONF.asr1k_l3.snat_mode == constants.SNAT_MODE_INTERFACE:
                results.append(self.dynamic_nat[constants.SNAT_MODE_POOL].delete())
                results.append(self.nat_pool.delete())
                results.append(self.dynamic_nat[constants.SNAT_MODE_INTERFACE].update())
        else:
            results.append(self.dynamic_nat[constants.SNAT_MODE_INTERFACE].delete())
            results.append(self.dynamic_nat[constants.SNAT_MODE_POOL].delete())
            results.append(self.nat_pool.delete())

        # process orphaned interfaces after nat configuration
        for interface in self.interfaces.all_interfaces:
            if isinstance(interface, l3_interface.OrphanedInterface):
                results.append(interface.update())

        return results

    def _ping(self):
        return os.system("ping -c 1 10.44.30.206")

    def _delete(self):
        results = []
        # order is important here.

        for prefix_list in self.prefix_lists:
            results.append(prefix_list.delete())

        if len(self.prefix_lists) == 0:
            results.append(prefix.SnatPrefix(router_id=self.router_id).delete())
            results.append(prefix.ExtPrefix(router_id=self.router_id).delete())
            results.append(prefix.RoutePrefix(router_id=self.router_id).delete())

        results.append(self.route_map.delete())
        results.append(self.floating_ips.delete())
        results.append(self.arp_entries.delete())
        results.append(self.routes.delete())

        for key in self.dynamic_nat.keys():
            results.append(self.dynamic_nat.get(key).delete())
        if cfg.CONF.asr1k_l3.snat_mode == constants.SNAT_MODE_POOL:
            results.append(self.nat_pool.delete())

        results.append(self.pbr_route_map.delete())
        results.append(self.nat_acl.delete())
        results.append(self.pbr_acl.delete())
        results.append(self.bgp_address_family.delete())

        for interface in self.interfaces.all_interfaces:
            results.append(interface.delete())

        results.append(self.vrf.delete())

        return results

    def diff(self):
        diff_results = {}

        vrf_diff = self.vrf.diff()
        if not vrf_diff.valid:
            diff_results['vrf'] = vrf_diff.to_dict()

        if self.routable_interface:
            bgp_diff = self.bgp_address_family.diff()

            if not bgp_diff.valid:
                diff_results['bgp'] = bgp_diff.to_dict()

        for prefix_list in self.prefix_lists:
            if prefix_list.internal_interfaces is not None and len(prefix_list.internal_interfaces) > 0:
                prefix_diff = prefix_list.diff()
                if not prefix_diff.valid:
                    diff_results['prefix_list'] = prefix_diff.to_dict()

        rm_diff = self.route_map.diff()
        if not rm_diff.valid:
            diff_results['route_map'] = rm_diff.to_dict()

        if self.gateway_interface:
            pbr_rm_diff = self.pbr_route_map.diff()
            if not pbr_rm_diff.valid:
                diff_results['pbr_route_map'] = pbr_rm_diff.to_dict()

        route_diff = self.routes.diff()
        if not route_diff.valid:
            diff_results['route'] = route_diff.to_dict()

        dynamic_nat_diff = self.dynamic_nat.get(cfg.CONF.asr1k_l3.snat_mode).diff()
        if not dynamic_nat_diff.valid:
            diff_results['dynamic_nat'] = dynamic_nat_diff.to_dict()

        if cfg.CONF.asr1k_l3.snat_mode == constants.SNAT_MODE_POOL:
            nat_pool_diff = self.nat_pool.diff()
            if not nat_pool_diff.valid:
                diff_results['nat_pool'] = nat_pool_diff.to_dict()

        floating_ips_diff = self.floating_ips.diff()
        if not floating_ips_diff.valid:
            diff_results['static_nat'] = floating_ips_diff.to_dict()

        arp_entries_diff = self.arp_entries.diff()
        if not arp_entries_diff.valid:
            diff_results['arp_entries'] = arp_entries_diff.to_dict()

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

    def init_config(self):
        result = []

        result.append(self.vrf.init_config())
        result.append('\n')
        if self.gateway_interface:
            result.append(self.gateway_interface.init_config())
            result.append('\n')

        for interface in self.interfaces.internal_interfaces:
            result.append(interface.init_config())
            result.append('\n')

        return ''.join(result)
