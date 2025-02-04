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
import os

from collections import defaultdict
from oslo_config import cfg
from oslo_log import log as logging

from asr1k_neutron_l3.common import asr1k_constants as constants, utils
from asr1k_neutron_l3.common.prometheus_monitor import PrometheusMonitor
from asr1k_neutron_l3.models import asr1k_pair
from asr1k_neutron_l3.models.neutron.l3 import access_list
from asr1k_neutron_l3.models.neutron.l3.base import Base
from asr1k_neutron_l3.models.neutron.l3 import bgp
from asr1k_neutron_l3.models.neutron.l3 import firewall
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
        self.router_id = self.router_info['id']
        self.interfaces = self._build_interfaces()
        self.routes = self._build_routes()
        self.enable_snat = False
        self.routable_interface = False
        if router_info.get('external_gateway_info') is not None:
            self.enable_snat = router_info.get('external_gateway_info', {}).get('enable_snat', False)
            self.routable_interface = bool(self.interfaces.get_routable_networks_v4() or
                                           self.interfaces.get_routable_networks_v6())

        description = self.router_info.get('description')
        if not description:
            description = f"Router {self.router_id}"

        # TODO : get rt's from config for router
        address_scope_config = router_info.get(constants.ADDRESS_SCOPE_CONFIG, {})

        self.rt = None
        self.global_vrf_id = None
        if self.gateway_interface is not None:
            # We excpect that the v4 and v6 adress scope is always from the same cloud VRF
            gw_address_scope = self.gateway_interface.address_scope_v4 or self.gateway_interface.address_scope_v6
            if gw_address_scope in address_scope_config:
                self.rt = address_scope_config[gw_address_scope]
                self.global_vrf_id = self._to_global_vrf_id(self.rt)
            elif gw_address_scope:
                LOG.error("Router %s has a gateway interface, but no address scope was found in config "
                          "(address scope of router: %s, available scopes: %s)",
                          self.router_id, gw_address_scope, list(address_scope_config.keys()))

        if not self.router_atts.get('rd'):
            LOG.error("Router %s has no rd attached, configuration is likely to fail!",
                      self.router_id)

        self.vrf = vrf.Vrf(self.router_id, description=description, asn=self.config.asr1k_l3.fabric_asn,
                           rd=self.router_atts.get('rd'), routable_interface=self.routable_interface,
                           rt_import=self.rt_import, rt_export=self.rt_export, global_vrf_id=self.global_vrf_id,
                           enable_ipv4=True, enable_ipv6=self.enable_ipv6)

        self.fwaas_conf, self.fwaas_external_policies = self._build_fwaas_conf()

        self.route_maps = self._build_route_maps()
        self.nat_acl = self._build_nat_acl()

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

    @property
    def enable_ipv4(self):
        return any(iface.ipv4_address for iface in self.interfaces.all_interfaces)

    @property
    def enable_ipv6(self):
        return any(iface.ipv6_addresses for iface in self.interfaces.all_interfaces)

    def _get_fwaas_acls_by_port(self):
        """
        This method retrieves the ACLs associated with each port for the router.

        Returns:
            dict: A dictionary mapping port IDs to ACLs. The structure of the dictionary is as follows:
                {
                    'port_id_1': {
                        'egress_acl': 'acl_1',
                        'ingress_acl': 'acl_2'
                    },
                    'port_id_2': {
                        'egress_acl': 'acl_1'
                    },
                    ...
                }
        """
        port_acl_map = defaultdict(dict)
        for policy_id, policy in self.router_info.get('fwaas_policies', {}).items():
            for egress_port in policy['egress_ports']:
                port_acl_map[egress_port]['egress_acl'] = firewall.AccessList.get_id_by_policy_id(policy_id)
            for ingress_port in policy['ingress_ports']:
                port_acl_map[ingress_port]['ingress_acl'] = firewall.AccessList.get_id_by_policy_id(policy_id)
        return port_acl_map

    def _build_interfaces(self):
        interfaces = l3_interface.InterfaceList()

        gw_port = self.router_info.get('gw_port')
        if gw_port is not None:
            self.gateway_interface = l3_interface.GatewayInterface(self.router_id, gw_port,
                                                                   self._port_extra_atts(gw_port),
                                                                   self.router_atts.get('dynamic_nat_pool'))
            interfaces.append(self.gateway_interface)

        inf_ports = self.router_info.get('_interfaces', [])

        fwaas_acls = self._get_fwaas_acls_by_port()
        for inf_port in inf_ports or []:
            interfaces.append(
                l3_interface.InternalInterface(self.router_id, inf_port, self._port_extra_atts(inf_port),
                                               **fwaas_acls[inf_port['id']]))

        for port_id in utils.calculate_deleted_ports(self.router_info):
            port = {'id': port_id}
            interfaces.append(l3_interface.OrphanedInterface(self.router_id, port, self._port_extra_atts(port)))

        return interfaces

    def _build_routes(self):
        routes = {
            4: route.RouteCollectionV4(self.router_id),
            6: route.RouteCollectionV6(self.router_id),
        }

        # In case the customer sets a default route, we will restrain from programming the openstack primary route
        primary_overridden = {4: False, 6: False}
        for l3_route in self.router_info.get('routes', []):
            ip_net = netaddr.IPNetwork(l3_route['destination'])
            if ip_net.prefixlen == 0:
                primary_overridden[ip_net.version] = True

            RouteClass = route.RouteV4 if ip_net.version == 4 else route.RouteV6
            r = RouteClass(self.router_id, str(ip_net), l3_route.get('nexthop'))

            if self._route_has_connected_interface(r):
                routes[ip_net.version].append(r)

        # handle default routes
        if self.gateway_interface is not None:
            if self.gateway_interface.gateway_ip_v4 and not primary_overridden[4]:
                primary_route = route.RouteV4(self.router_id, "0.0.0.0/0",
                                              self.gateway_interface.gateway_ip_v4)
                if self._route_has_connected_interface(primary_route):
                    routes[4].append(primary_route)

            if self.gateway_interface.gateway_ip_v6 and not primary_overridden[6]:
                primary_route = route.RouteV6(self.router_id, "::/0",
                                              self.gateway_interface.gateway_ip_v6)
                if self._route_has_connected_interface(primary_route):
                    routes[6].append(primary_route)

        return routes

    def _build_nat_acl(self):
        acl = access_list.AccessList(f"NAT-{utils.uuid_to_vrf_id(self.router_id)}")

        # Check address scope and deny any where internal interface matches external
        for network in self.interfaces.get_routable_networks_v4():
            ip, netmask = utils.from_cidr(network)
            wildcard = utils.to_wildcard_mask(netmask)
            rule = access_list.Rule(action='deny', source=ip, source_mask=wildcard)
            acl.append_rule(rule)

        if not self.enable_snat:
            acl.append_rule(access_list.Rule(action='deny'))
        else:
            acl.append_rule(access_list.Rule())
        return acl

    def _route_has_connected_interface(self, l3_route):
        all_networks = (
            self.interfaces.get_external_networks_v4() +
            self.interfaces.get_external_networks_v6() +
            self.interfaces.get_internal_networks_v4() +
            self.interfaces.get_internal_networks_v6()
        )
        return any(utils.ip_in_network(l3_route.nexthop, network) for network in all_networks)

    def _build_bgp_address_family(self):
        bgp_afs = {}
        for ip_version, BGPAddressFamily in ((4, bgp.AddressFamilyV4), (6, bgp.AddressFamilyV6)):
            if ip_version == 6 or ip_version == 4 and cfg.CONF.asr1k_l3.advertise_bgp_ipv4_routes_via_redistribute:
                # use redistribute static/connected
                networks = []
                routable_networks = []
                has_routable_interface = bool(self.interfaces.get_routable_networks(ip_version))
                redistribute_map = f"bgp-redistribute{ip_version}-{utils.uuid_to_vrf_id(self.router_id)}"
            else:
                # use network statements
                networks = self.interfaces.get_internal_networks(ip_version)
                routable_networks = self.interfaces.get_routable_networks(ip_version)
                has_routable_interface = bool(routable_networks)
                redistribute_map = None

            enable_af = self.enable_ipv4 if ip_version == 4 else self.enable_ipv6

            extra_routes = []
            if self.router_info["bgpvpn_advertise_extra_routes"]:
                extra_routes = [x.cidr for x in self.routes[ip_version].routes if x.cidr not in ("0.0.0.0/0", "::/0")]

            bgp_afs[ip_version] = BGPAddressFamily(
                vrf=utils.uuid_to_vrf_id(self.router_id),
                asn=self.config.asr1k_l3.fabric_asn, rt_export=self.rt_export,
                connected_cidrs=networks, extra_routes=extra_routes,
                routable_networks=routable_networks,
                has_routable_interface=has_routable_interface,
                redistribute_map=redistribute_map,
                enable_af=enable_af,
            )
        return bgp_afs

    def _build_dynamic_nat(self):
        pool_nat = nat.DynamicNAT(self.router_id, gateway_interface=self.gateway_interface,
                                  mode=constants.SNAT_MODE_POOL,
                                  mapping_id=utils.uuid_to_mapping_id(self.router_id))
        interface_nat = nat.DynamicNAT(self.router_id, gateway_interface=self.gateway_interface,
                                       mode=constants.SNAT_MODE_INTERFACE)

        return {constants.SNAT_MODE_POOL: pool_nat, constants.SNAT_MODE_INTERFACE: interface_nat}

    def _build_nat_pool(self):
        if self.router_atts.get("dynamic_nat_pool"):
            self.use_nat_pool = True

            # format: startip-endip/poolprefixlen
            ips, prefix = self.router_atts['dynamic_nat_pool'].split("/")
            start_ip, end_ip = ips.split("-")
            pool = nat.NATPool(self.router_id, start_address=start_ip, end_address=end_ip, prefix_length=prefix)
        else:
            self.use_nat_pool = False
            pool = nat.NATPool(self.router_id, start_address=None, end_address=None, prefix_length=None)
        return pool

    def _build_floating_ips(self):
        floating_ips = nat.FloatingIpList(self.router_id)
        for floating_ip in self.router_info.get('_floatingips', []):
            floating_ips.append(nat.FloatingIp(self.router_id, floating_ip, self.gateway_interface))

        return floating_ips

    def _build_arp_entries(self):
        arp_entries = nat.ArpList(self.router_id)
        for floating_ip in self.router_info.get('_floatingips', []):
            arp_entries.append(nat.ArpEntry(self.router_id, floating_ip.get("floating_ip_address"),
                               self.gateway_interface))

        if self.router_atts.get("dynamic_nat_pool"):
            ips, prefix = self.router_atts['dynamic_nat_pool'].split("/")
            start_ip, end_ip = ips.split("-")
            for ip in netaddr.IPSet(netaddr.IPRange(start_ip, end_ip)):
                arp_entries.append(nat.ArpEntry(self.router_id, str(ip), self.gateway_interface))

        return arp_entries

    def _build_prefix_lists(self):
        result = []

        # external interface
        result.append(prefix.ExtPrefixV4(router_id=self.router_id, prefixes=self.interfaces.get_external_networks_v4()))
        result.append(prefix.ExtPrefixV6(router_id=self.router_id, prefixes=self.interfaces.get_external_networks_v6()))

        result.append(prefix.SnatPrefix(router_id=self.router_id, prefixes=self.interfaces.get_routable_networks_v4()))

        result.append(prefix.RoutePrefixV4(router_id=self.router_id,
                                           prefixes=self.interfaces.get_routable_networks_v4()))
        result.append(prefix.RoutePrefixV6(router_id=self.router_id,
                                           prefixes=self.interfaces.get_routable_networks_v6()))

        # the new prefix lists
        #   routable -> all dapnets
        #   routable-extraroutes -> all extraroutes part of a dapnets
        #   internal -> everything internal
        #   extraroutes -> extraroutes that are not routable
        for ip_version, PrefixClass in ((4, prefix.BasePrefixV4), (6, prefix.BasePrefixV6)):
            if ip_version == 4 and not cfg.CONF.asr1k_l3.advertise_bgp_ipv4_routes_via_redistribute:
                # we don't need the lists for v4 if they're not being used
                # to avoid potential config locks, we won't configure them
                continue

            af_enabled = self.enable_ipv4 if ip_version == 4 else self.enable_ipv6
            routable_networks = self.interfaces.get_routable_networks(ip_version)
            internal_networks = self.interfaces.get_internal_networks(ip_version)
            routable_extraroutes = []
            internal_extraroutes = []
            for extraroute in self.routes[ip_version].routes:
                net = extraroute.cidr
                if net in ("0.0.0.0/0", "::/0"):
                    continue

                if any(utils.network_in_network(net, routable_network) for routable_network in routable_networks):
                    routable_extraroutes.append(net)
                else:
                    internal_extraroutes.append(net)

            result.extend([
                PrefixClass(f"routable{ip_version}", self.router_id, routable_networks, add_deny_if_empty=af_enabled),
                PrefixClass(f"routable-extraroutes{ip_version}", self.router_id, routable_extraroutes,
                            add_deny_if_empty=af_enabled),
                PrefixClass(f"internal{ip_version}", self.router_id, internal_networks, add_deny_if_empty=af_enabled),
                PrefixClass(f"internal-extraroutes{ip_version}", self.router_id, internal_extraroutes,
                            add_deny_if_empty=af_enabled),
            ])

        return result

    def _build_route_maps(self):
        extraroutes_rt = None
        if self.rt and ':' in self.rt:
            # 65126:106 --> 65126:1106
            asn, sf = self.rt.split(":", 1)
            extraroutes_rt = f"{asn}:1{sf}"

        route_maps = [
            # exp route-map
            route_map.RouteMap(self.router_id, rt=self.rt,
                               routable_interface=self.routable_interface, enable_ipv6=self.enable_ipv6),

            # pbr route-map
            route_map.PBRRouteMap(self.router_id,
                                  has_gateway_interface=bool(self.gateway_interface)),

            # redistribute routemaps
            route_map.RedistRouteMapV4(self.router_id, self.rt, extraroutes_rt,
                                       enabled=(self.enable_ipv4 and
                                                cfg.CONF.asr1k_l3.advertise_bgp_ipv4_routes_via_redistribute)),
            route_map.RedistRouteMapV6(self.router_id, self.rt, extraroutes_rt, enabled=self.enable_ipv6),
        ]

        return route_maps

    def _build_fwaas_conf(self):
        router_info = self.router_info

        fwaas_conf = []
        fwaas_external_policies = {'ingress': None, 'egress': None}
        for name, policy in router_info.get('fwaas_policies', {}).items():
            if self.gateway_interface and (self.gateway_interface.id in policy['ingress_ports']
                                           or self.gateway_interface.id in policy['egress_ports']):
                # This policy will be bound on a external interface, so we need to create
                # class-map and service-policy
                if self.gateway_interface.id in policy['ingress_ports']:
                    fwaas_external_policies['ingress'] = name
                if self.gateway_interface.id in policy['egress_ports']:
                    fwaas_external_policies['egress'] = name
                fwaas_conf.append(firewall.ClassMap(name))
                fwaas_conf.append(firewall.ServicePolicy(name))
            fwaas_conf.append(firewall.AccessList(name, policy['rules']))

        if fwaas_external_policies['ingress'] or fwaas_external_policies['egress']:
            # As there are external interfaces policies, we create zones and zone-pairs
            fwaas_conf.append(firewall.Zone(self.router_id))
            fwaas_conf.append(
                firewall.ZonePairExtEgress(self.router_id, fwaas_external_policies['egress']))
            fwaas_conf.append(
                firewall.ZonePairExtIngress(self.router_id, fwaas_external_policies['ingress']))
            # We also want to link the VRF to a policer so we limit VRFs (by boilerplate)
            fwaas_conf.append(firewall.FirewallVrfPolicer(self.router_id))
            # Mark all interfaces for stateful firewalling
            for interface in self.interfaces.all_interfaces:
                interface.has_stateful_firewall = True
        return fwaas_conf, fwaas_external_policies

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

        for rm in self.route_maps:
            results.append(rm.update())
        results.append(self.vrf.update())

        for ip_version in (4, 6):
            if self.bgp_address_family[ip_version].enable_bgp:
                results.append(self.bgp_address_family[ip_version].update())
            else:
                results.append(self.bgp_address_family[ip_version].delete())

        if self.nat_acl:
            results.append(self.nat_acl.update())

        # a router object will take care of creation of firewall acls and related objects,
        # it will also update firewall acls
        for obj in self.fwaas_conf:
            results.append(obj.update())

        # If there are no external policies, we can create dangling objects which will and call delete
        if not self.fwaas_external_policies['ingress'] and not self.fwaas_external_policies['egress']:
            results.append(firewall.ZonePairExtIngress(self.router_id).delete())
            results.append(firewall.ZonePairExtEgress(self.router_id).delete())
            results.append(firewall.FirewallVrfPolicer(self.router_id).delete())
            results.append(firewall.Zone(self.router_id).delete())

        # Working assumption is that any NAT mode migration is completed

        results.append(self.floating_ips.update())
        results.append(self.arp_entries.update())

        # process interface configuration before we configure nat
        for interface in self.interfaces.all_interfaces:
            if not isinstance(interface, l3_interface.OrphanedInterface):
                results.append(interface.update())

        results.append(self.routes[4].update())
        results.append(self.routes[6].update())

        if self.gateway_interface is not None:
            if self.use_nat_pool:
                results.append(self.dynamic_nat[constants.SNAT_MODE_INTERFACE].delete())
                results.append(self.nat_pool.update())
                results.append(self.dynamic_nat[constants.SNAT_MODE_POOL].update())
            else:
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
            results.append(prefix.ExtPrefixV4(router_id=self.router_id).delete())
            results.append(prefix.ExtPrefixV6(router_id=self.router_id).delete())
            results.append(prefix.RoutePrefix(router_id=self.router_id).delete())

        for rm in self.route_maps:
            results.append(rm.delete())
        results.append(self.floating_ips.delete())
        results.append(self.arp_entries.delete())
        results.append(self.routes[4].delete())
        results.append(self.routes[6].delete())

        for key in self.dynamic_nat.keys():
            results.append(self.dynamic_nat.get(key).delete())
        results.append(self.nat_pool.delete())

        results.append(self.nat_acl.delete())
        results.append(self.bgp_address_family[4].delete())
        results.append(self.bgp_address_family[6].delete())

        for interface in self.interfaces.all_interfaces:
            results.append(interface.delete())

        results.append(firewall.ZonePairExtIngress(self.router_id).delete())
        results.append(firewall.ZonePairExtEgress(self.router_id).delete())
        results.append(firewall.FirewallVrfPolicer(self.router_id).delete())
        results.append(firewall.Zone(self.router_id).delete())

        results.append(self.vrf.delete())

        # We do not delete fwaas acls here as the acl could
        # still be in use by an another router

        return results

    def diff(self):
        diff_results = {}

        vrf_diff = self.vrf.diff()
        if not vrf_diff.valid:
            diff_results['vrf'] = vrf_diff.to_dict()

        if self.routable_interface:
            for ip_version in (4, 6):
                bgp_diff = self.bgp_address_family[ip_version].diff()
                if not bgp_diff.valid:
                    diff_results[f'bgp_v{ip_version}'] = bgp_diff.to_dict()

        for prefix_list in self.prefix_lists:
            prefix_diff = prefix_list.diff()
            if not prefix_diff.valid:
                if 'prefix_list' not in diff_results:
                    diff_results['prefix_list'] = []
                diff_results['prefix_list'].append(prefix_diff.to_dict())

        for rm in self.route_maps:
            rm_diff = rm.diff()
            if not rm_diff.valid:
                diff_results[f'route_map-{rm.name}'] = rm_diff.to_dict()

        for ip_version in (4, 6):
            route_diff = self.routes[ip_version].diff()
            if not route_diff.valid:
                diff_results[f'route_v{ip_version}'] = route_diff.to_dict()

        # FIXME: this diff probably doesn't work for internal routers
        snat_mode = constants.SNAT_MODE_POOL if self.use_nat_pool else constants.SNAT_MODE_INTERFACE
        dynamic_nat_diff = self.dynamic_nat.get(snat_mode).diff()
        if not dynamic_nat_diff.valid:
            diff_results['dynamic_nat'] = dynamic_nat_diff.to_dict()

        if self.use_nat_pool:
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

        for obj in self.fwaas_conf:
            d = obj.diff()
            if not d.valid:
                diff_results[obj.id] = d.to_dict()

        if not self.fwaas_external_policies['ingress'] and not self.fwaas_external_policies['egress']:
            for obj in [firewall.ZonePairExtIngress(self.router_id),
                        firewall.ZonePairExtEgress(self.router_id),
                        firewall.FirewallVrfPolicer(self.router_id),
                        firewall.Zone(self.router_id)]:
                d = obj.diff(should_be_none=True)
                if not d.valid:
                    diff_results[obj.id] = d.to_dict()

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
