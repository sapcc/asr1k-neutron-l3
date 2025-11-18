# Copyright 2025 SAP SE
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

import ipaddress
import itertools
import random

import netaddr
from neutron_vpnaas.services.vpn.service_drivers import base_ipsec, ipsec_validator
from neutron_vpnaas.services.vpn.common import constants as v_const
from neutron_lib.callbacks import events
from neutron_lib.callbacks import registry
from neutron_lib.callbacks import resources
from neutron_lib.callbacks import priority_group
from neutron_lib import constants as nl_const
from neutron_lib.db import api as db_api
from neutron_lib.db import resource_extend
from oslo_config import cfg
from oslo_log import log as logging

from asr1k_neutron_l3.plugins.db import asr1k_db
from asr1k_neutron_l3.common import asr1k_constants as asr1k_const
from asr1k_neutron_l3.common.asr1k_exceptions import DeprecatedAPIField
from asr1k_neutron_l3.common.asr1k_exceptions import DuplicateEndpointsBetweenIPSecSiteConnections
from asr1k_neutron_l3.common.asr1k_exceptions import EndpointGroupTooLarge
from asr1k_neutron_l3.common.asr1k_exceptions import ExtraRoutesDisallowedOnVPNaaSRouter
from asr1k_neutron_l3.common.asr1k_exceptions import InvalidInternalSubnetOnVPNaasRouter
from asr1k_neutron_l3.common.asr1k_exceptions import InvalidVPNaaSInternalTunnelIps
from asr1k_neutron_l3.common.asr1k_exceptions import InvalidVPNaaSIPSecSiteConnectionConfig
from asr1k_neutron_l3.common.asr1k_exceptions import MultipleVPNServicesOnRouterDisallowed
from asr1k_neutron_l3.common.asr1k_exceptions import PeerNatAddressMustBeIPv4
from asr1k_neutron_l3.common.asr1k_exceptions import RouterIsNotVPNaaSFlavor
from asr1k_neutron_l3.common.cache_utils import get_cache


LOG = logging.getLogger(__name__)

# BSI information taken out of TR-02102-3
# device support + BSI approved, aes-{128,256} map to cbc
DEVICE_SUPPORTED_CIPHERS = ['aes-128', 'aes-256', 'aes-128-gcm-16', 'aes-256-gcm-16']

# device supports 14 as well, but BSI does not recommend it
DEVICE_SUPPORTED_DH_GROUPS = [f'group{n}' for n in (15, 16, 19, 20, 21)]

# BSI + device approved auth algos
DEVICE_SUPPORTED_AUTH_ALGOS = ['sha256', 'sha384', 'sha512']


def to_net(net):
    return ipaddress.ip_network(net, strict=False)


@resource_extend.has_resource_extenders
@registry.has_registry_receivers
class ASR1KIPSecVPNaaSDriver(base_ipsec.BaseIPsecVPNDriver):
    INT_IPV4_NET = ipaddress.ip_network("169.254.0.0/16")
    INT_IPV6_NET = ipaddress.ip_network("fd00::/8")

    def __init__(self, service_plugin):
        self.l3db = asr1k_db.get_db_plugin()
        super().__init__(service_plugin, ASR1KIpsecVpnValidator(self))

    def create_rpc_conn(self):
        self.agent_rpc = ASR1KIPSecVPNaaSNotifier()

    def create_ipsec_site_connection(self, context, ipsec_site_connection):
        self._notify_router_for_ipsec_site_connection(context, ipsec_site_connection['vpnservice_id'])

    def delete_ipsec_site_connection(self, context, ipsec_site_connection):
        # this is handled via an AFTER_DELETE hook
        pass

    def update_ipsec_site_connection(self, context, old_ipsec_site_connection, ipsec_site_connection):
        self._notify_router_for_ipsec_site_connection(context, ipsec_site_connection['vpnservice_id'])

    def _notify_router_for_ipsec_site_connection(self, context, vpnservice_id):
        vpn = self.service_plugin.get_vpnservice(context, vpnservice_id)
        LOG.info("IPSec site connection of VPN service %s changed - updating router %s",
                 vpnservice_id, vpn['router_id'])
        self.l3_plugin.notify_routers_updated(context, [vpn['router_id']])

    @registry.receives(v_const.IPSEC_SITE_CONNECTION, [events.AFTER_CREATE])
    def allocate_tunnel_ids(self, resource, event, trigger, payload):
        context = payload.context
        vpnservice_id = payload.states[-1]['vpnservice_id']
        vpnservice = self.service_plugin.get_vpnservice(context, vpnservice_id)

        self.l3_plugin.ensure_vpn_tunnel_ids(context, vpnservice['router_id'])

    @registry.receives(v_const.IPSEC_SITE_CONNECTION, [events.BEFORE_DELETE])
    def _delete_ipsec_site_connection_cache_tunnel_ids(self, resource, event, trigger, payload):
        context = payload.context
        sitecon_id = payload.resource_id
        cache = get_cache()
        if not cache:
            return

        tun_ids = self.l3db.get_vpn_tunnel_ids(context, ipsec_site_connection_ids=[sitecon_id])
        cache.set(f"delete-{sitecon_id}-tun-info", tun_ids)

    @registry.receives(v_const.IPSEC_SITE_CONNECTION, [events.AFTER_DELETE])
    def _delete_ipsec_site_connection_send_tunnel_send_notify(self, resource, event, trigger, payload):
        context = payload.context
        sitecon_id = payload.resource_id
        cache = get_cache()
        if not cache:
            return
        tun_ids = cache.get(f"delete-{sitecon_id}-tun-info")
        if not tun_ids:
            LOG.warning("No tunnel ids found in cache while deleting ipsec site connection %s",
                        sitecon_id)

        for tun_id in tun_ids:
            LOG.debug("Sending tunnel interface delete for Tunnel%s to host %s for connection %s",
                      tun_id['number'], tun_id['agent_host'], tun_id['ipsec_site_connection_id'])
            self.l3_plugin.notify_delete_tunnel_interface(context, tun_id['agent_host'], tun_id['number'])

    @registry.receives(v_const.IPSEC_SITE_CONNECTION, [events.PRECOMMIT_CREATE, events.PRECOMMIT_UPDATE])
    def _disallow_setting_peer_cidrs_on_ipsec_site_connection(self, resource, event, trigger, payload):
        sitecon_req = payload.request_body
        if sitecon_req.get('peer_cidrs'):
            raise DeprecatedAPIField(obj_name="IPSec site connection", deprecated_field="peer_cidrs")

    @registry.receives(v_const.IPSEC_SITE_CONNECTION, [events.PRECOMMIT_CREATE, events.PRECOMMIT_UPDATE],
                       priority=priority_group.PRIORITY_ROUTER_EXTENDED_ATTRIBUTE)
    def _handle_and_validate_nat_address(self, resource, event, trigger, payload):
        context = payload.context
        ipsec_sitecon_id = payload.resource_id
        ipsec_sitecon_req = payload.request_body

        if ipsec_sitecon_req.get('peer_nat_address_v4', nl_const.ATTR_NOT_SPECIFIED) == nl_const.ATTR_NOT_SPECIFIED:
            return

        nat_addr = ipsec_sitecon_req['peer_nat_address_v4']
        if nat_addr is not None:
            if ipaddress.ip_address(nat_addr).version != 4:
                raise PeerNatAddressMustBeIPv4()
            self.l3db.create_or_update_vpn_peer_nat_address(context, ipsec_sitecon_id, nat_addr)
        else:
            self.l3db.delete_vpn_peer_nat_address(context, ipsec_sitecon_id)

    @registry.receives(v_const.IPSEC_SITE_CONNECTION, [events.PRECOMMIT_CREATE, events.PRECOMMIT_UPDATE],
                       priority=priority_group.PRIORITY_ROUTER_EXTENDED_ATTRIBUTE)
    def _handle_and_validate_internal_tunnel_ips(self, resource, event, trigger, payload):
        keys = ['local_cidr_v4', 'peer_address_v4', 'local_cidr_v6', 'peer_address_v6']
        context = payload.context
        ipsec_sitecon_id = payload.resource_id
        ipsec_sitecon_req = payload.request_body
        ipsec_sitecon_new = payload.states[-1]
        tun_ips = {key: ipsec_sitecon_req[f"int_{key}"]
                   for key in keys
                   if ipsec_sitecon_req.get(f"int_{key}", nl_const.ATTR_NOT_SPECIFIED) != nl_const.ATTR_NOT_SPECIFIED}
        request_contains_ips = bool(tun_ips)
        for key in keys:
            if key in tun_ips:
                # make sure address family fits
                addr = ipaddress.ip_interface(tun_ips[key])
                req_af = key[-1]
                if str(addr.version) != req_af:
                    key_name = key.replace("_", " ")
                    reason = (f"Invalid address family for internal {key_name}: Required v{req_af}, but "
                              f"{tun_ips[key]} is of address family v{addr.version}")
                    raise InvalidVPNaaSInternalTunnelIps(reason=reason)
            else:
                tun_ips[key] = None

        if not all(tun_ips.get(key) for key in keys) and event == events.PRECOMMIT_UPDATE:
            # fetch from db
            data = self.l3db.get_vpn_internal_tunnel_ips(context, [ipsec_sitecon_id])[0]
            for key in keys:
                if not tun_ips.get(key):
                    tun_ips[key] = data[key]

        if all(tun_ips[key] for key in keys) and not request_contains_ips:
            # no tunnel ips changed in request --> early return
            return


        vpnservice_id = ipsec_sitecon_new['vpnservice_id']
        tun_ips = self._autoallocate_int_tun_ips(context, tun_ips, vpnservice_id)
        self.l3db.create_or_update_vpn_internal_tunnel_ips(context, ipsec_sitecon_id,
                                                           tun_ips['local_cidr_v4'], tun_ips['peer_address_v4'],
                                                           tun_ips['local_cidr_v6'], tun_ips['peer_address_v6'])

        self.validate_internal_tunnel_ips(context, vpnservice_id)

    def _autoallocate_int_tun_ips(self, context, tun_ips, vpnservice_id):
        all_vpn_tun_ips = None
        for ip_ver, def_subnet, def_prefixlen in ((4, self.INT_IPV4_NET, 30),  (6, self.INT_IPV6_NET, 126)):
            net_key = f"local_cidr_v{ip_ver}"
            ip_key = f"peer_address_v{ip_ver}"

            # no auto alloc needed if both are specified
            if tun_ips[net_key] and tun_ips[ip_key]:
                continue

            if tun_ips[net_key] or tun_ips[ip_key]:
                reason = (f"Cannot auto-allocate internal tunnel subnet for IPv{ip_ver}, you need to specify "
                          "either no local/remote address or both.")
                raise InvalidVPNaaSInternalTunnelIps(reason=reason)

            # time to allocate
            # allocation algorithm:
            #   1. use the default pool for the AF
            #   2. remove all already used IPs from it (local and peer)
            #   3. filter for all remaining subnets that are big enough
            #   4. randomly select a pool (considering their size as weight)
            #   5. select subnet that is big enough from it (/30 or /126 --> 4 ips)
            #   6. assign the first ip to us, second to peer (as we like ourselves very much)
            if not all_vpn_tun_ips:
                all_vpn_tun_ips = self.l3db.get_vpn_internal_tunnel_ips(context, vpnservice_id=vpnservice_id)

            ipset = netaddr.IPSet(netaddr.IPNetwork(str(def_subnet)))
            for entry in all_vpn_tun_ips:
                ipset.remove(entry[net_key])
                ipset.remove(entry[ip_key])

            pools = [p for p in ipset.iter_cidrs() if p.prefixlen <= def_prefixlen]
            pool = random.choices(pools, weights=[p.size for p in pools])[0]
            sn_offset = random.randint(0, pool.size - 1)
            sn_offset -= sn_offset % 4  # honor subnet borders
            net_ip = pool.ip + sn_offset
            tun_ips[net_key] = f"{net_ip + 1}/{def_prefixlen}"
            tun_ips[ip_key] = f"{net_ip + 2}"

        # tun_ips is a reference, but sometimes it confuses people less this way
        return tun_ips

    def validate_internal_tunnel_ips(self, context, vpnservice_id):
        tun_ips = self.l3db.get_vpn_internal_tunnel_ips(context, vpnservice_id=vpnservice_id)

        for tun_ip in tun_ips:
            tun_ip['local_cidr_v4'] = ipaddress.ip_interface(tun_ip['local_cidr_v4'])
            tun_ip['local_cidr_v6'] = ipaddress.ip_interface(tun_ip['local_cidr_v6'])
            tun_ip['peer_address_v4'] = ipaddress.ip_address(tun_ip['peer_address_v4'])
            tun_ip['peer_address_v6'] = ipaddress.ip_address(tun_ip['peer_address_v6'])

            for ip_ver, max_prefix_len_for_net_addr in ((4, 31), (6, 127)):
                local_net = tun_ip[f'local_cidr_v{ip_ver}']
                peer_ip = tun_ip[f'peer_address_v{ip_ver}']

                if local_net.network.prefixlen < max_prefix_len_for_net_addr:
                    # for everything with more than two IP addresses we're not allowing network/broadcast addresses
                    if local_net.ip in (local_net.network.network_address, local_net.network.broadcast_address):
                        reason = (f"Cannot use network- or broadcast address {local_net.ip} as "
                                  f"local internal tunnel ip for network {local_net.network}")
                        raise InvalidVPNaaSInternalTunnelIps(reason=reason)

                if local_net.ip == peer_ip:
                    reason = f"Internal local ip {local_net.ip} overlaps with peer ip {peer_ip}"
                    raise InvalidVPNaaSInternalTunnelIps(reason=reason)

        for ips_a, ips_b in itertools.combinations(tun_ips, 2):
            for ip_ver in (4, 6):
                net_key = f"local_cidr_v{ip_ver}"
                ip_key = f"peer_address_v{ip_ver}"

                net_a = ips_a[net_key]
                net_b = ips_b[net_key]
                ip_a = ips_a[ip_key]
                ip_b = ips_b[ip_key]

                # overlapping networks
                if net_a.network.overlaps(net_b.network):
                    reason = (f"Local subnet {net_a} of {ips_a['ipsec_site_connection_id']} "
                              f"and {net_b} of {ips_b['ipsec_site_connection_id']} overlap")
                    raise InvalidVPNaaSInternalTunnelIps(reason=reason)

                # overlapping peer ips
                if ip_a == ip_b:
                    reason = (f"Peer address {ip_a} cannot be used by two peers, it is used by "
                              f"{ips_a['ipsec_site_connection_id']} and {ips_b['ipsec_site_connection_id']}")
                    raise InvalidVPNaaSInternalTunnelIps(reason=reason)

                # overlapping local and remote peer
                if net_a.ip == ip_b or net_b.ip == ip_a:
                    reason = (f"IPSec Site Connection {ips_a['ipsec_site_connection_id']} and "
                              f"{ips_b['ipsec_site_connection_id']} have overlapping local/peer IPs")
                    raise InvalidVPNaaSInternalTunnelIps(reason=reason)

    @registry.receives(v_const.IPSEC_SITE_CONNECTION, [events.PRECOMMIT_CREATE, events.PRECOMMIT_UPDATE])
    def _ensure_ipsec_site_connections_peer_endpoints_dont_overlap(self, resource, event, trigger, payload):
        context = payload.context
        vpnservice_id = payload.states[-1]['vpnservice_id']
        all_sitecons = self.service_plugin.get_ipsec_site_connections(context,
                                                                      filters={"vpnservice_id": [vpnservice_id]})
        sitecon = [sc for sc in all_sitecons if sc['id'] == payload.states[-1]['id']][0]
        peer_cidrs = set(self.service_plugin.get_endpoint_group(context, sitecon['peer_ep_group_id'])['endpoints'])
        for other_sitecon in all_sitecons:
            if sitecon['id'] == other_sitecon['id']:
                continue
            other_peer_cidrs = set(self.service_plugin.get_endpoint_group(context,
                                                                          other_sitecon['peer_ep_group_id'])['endpoints'])
            other_peer_cidrs.add(f"{other_sitecon['int_peer_address_v4']}/32")
            other_peer_cidrs.add(f"{other_sitecon['int_peer_address_v6']}/128")

            if prefixes := peer_cidrs & other_peer_cidrs:
                raise DuplicateEndpointsBetweenIPSecSiteConnections(
                        ipsec_site_connection_id=sitecon['id'],
                        other_ipsec_site_connection_id=other_sitecon['id'],
                        prefixes=", ".join(prefixes))


class ASR1KIPSecVPNaaSNotifier:
    def vpnservice_updated(self, context, router_id, **kwargs):
        # handled via hooks (as we need to distinguish between a ipsec siteconnection delete and other operations)
        # we still need this class to implement a noop Notifier for the BaseIPsecVPNDriver
        pass


@registry.has_registry_receivers
class ASR1KIpsecVpnValidator(ipsec_validator.IpsecVpnValidator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.l3db = self.driver.l3db

    @db_api.CONTEXT_READER
    def _is_vpnaas_flavor(self, context, flavor_id):
        flavor_info = self.l3_plugin.get_metainfo_from_flavor_id(context, flavor_id)
        return asr1k_const.TRAIT_VPNAAS in (flavor_info["req_traits"] + flavor_info["opt_traits"])

    def _ensure_value(self, value, supported_values, obj_name, key_name):
        if value not in supported_values:
            raise InvalidVPNaaSIPSecSiteConnectionConfig(obj=obj_name, key=key_name, value=value,
                                                         supported_values=", ".join(supported_values))

    @db_api.CONTEXT_READER
    def validate_ipsec_site_connection(self, context, ipsec_sitecon):
        LOG.debug("validate_ipsec_site_connection() called for ipsec_sitecon: %s", ipsec_sitecon)

        # get and validate ikepolicy
        if 'ikepolicy_id' in ipsec_sitecon:
            ikepolicy = self.driver.service_plugin.get_ikepolicy(context, ipsec_sitecon['ikepolicy_id'])
            self._ensure_value(ikepolicy['auth_algorithm'], DEVICE_SUPPORTED_AUTH_ALGOS, "IKE Policy", "auth algorithm")
            self._ensure_value(ikepolicy['encryption_algorithm'], DEVICE_SUPPORTED_CIPHERS, "IKE Policy", "encryption")
            self._ensure_value(ikepolicy['ike_version'], ['v2'], "IKE Policy", "IKE version")
            self._ensure_value(ikepolicy['pfs'], DEVICE_SUPPORTED_DH_GROUPS, "IKE Policy", "DH group")

        # get and validate ipsecpolicy
        if 'ipsecpolicy_id' in ipsec_sitecon:
            ipsecpolicy = self.driver.service_plugin.get_ipsecpolicy(context, ipsec_sitecon['ipsecpolicy_id'])
            self._ensure_value(ipsecpolicy['auth_algorithm'], DEVICE_SUPPORTED_AUTH_ALGOS,
                               "IPSec Policy", "auth algorithm")
            self._ensure_value(ipsecpolicy['encryption_algorithm'], DEVICE_SUPPORTED_CIPHERS,
                               "IPSec Policy", "encryption")
            self._ensure_value(ipsecpolicy['transform_protocol'], ['esp'], "IPSec Policy", "transform protocol")
            self._ensure_value(ipsecpolicy['pfs'], DEVICE_SUPPORTED_DH_GROUPS, "IPSec Policy", "DH group")

    @registry.receives(v_const.VPNSERVICE, [events.PRECOMMIT_CREATE])
    def _ensure_vpnservice_only_on_vpnaas_router(self, resource, event, trigger, payload):
        context = payload.context
        vpn = payload.states[0]
        with db_api.CONTEXT_READER.using(context):
            router = self.l3_plugin.get_router(context, vpn['router_id'])
            if not router:
                return
            if not self._is_vpnaas_flavor(context, router['flavor_id']):
                raise RouterIsNotVPNaaSFlavor(router_id=vpn['router_id'])

    @registry.receives(v_const.VPNSERVICE, [events.PRECOMMIT_CREATE])
    def _ensure_only_one_vpnservice_per_router(self, resource, event, trigger, payload):
        context = payload.context
        vpn = payload.states[0]
        with db_api.CONTEXT_READER.using(context):
            all_vpns = self.driver.service_plugin.get_vpnservices(context, filters={'router_id': [vpn['router_id']]})
            vpn_db_ids = {v['id'] for v in all_vpns}
            if len(vpn_db_ids) > 1:
                other_vpn_id = [v['id'] for v in all_vpns if v['id'] != vpn['id']][0]
                raise MultipleVPNServicesOnRouterDisallowed(router_id=vpn['router_id'],
                                                            other_vpn_service_id=other_vpn_id)
            router = self.l3_plugin.get_router(context, vpn['router_id'])
            if not router:
                return
            if not self._is_vpnaas_flavor(context, router['flavor_id']):
                raise RouterIsNotVPNaaSFlavor(router_id=vpn['router_id'])

    @registry.receives(v_const.VPNSERVICE, [events.PRECOMMIT_CREATE])
    def _vpnservice_disallow_setting_subnet_id(self, resource, event, trigger, payload):
        vpn = payload.states[0]
        if vpn['subnet_id']:
            raise DeprecatedAPIField(obj_name="VPN service", deprecated_field="subnet_id")

    @registry.receives(resources.ROUTER_INTERFACE, [events.BEFORE_CREATE])
    def _ensure_vpnaas_router_has_no_internal_interfaces(self, resource, event, trigger, payload):
        context = payload.context
        router_db = payload.states[0]
        if not self._is_vpnaas_flavor(context, router_db.flavor_id):
            return

        raise InvalidInternalSubnetOnVPNaasRouter(router_id=router_db.id)

    @registry.receives(v_const.ENDPOINT_GROUP, [events.PRECOMMIT_CREATE, events.PRECOMMIT_UPDATE, events.AFTER_CREATE])
    def _ensure_endpoint_group_limit(self, resource, event, trigger, payload):
        # payload does not contain updated endpoint list --> we refetch the endpoing group
        epg = self.driver.service_plugin.get_endpoint_group(payload.context, payload.resource_id)
        if len(epg['endpoints']) > cfg.CONF.asr1k_l3.vpnaas_endpoint_group_max_eps:
            raise EndpointGroupTooLarge(epg_id=payload.resource_id, group_count=len(epg['endpoints']),
                                        limit=cfg.CONF.asr1k_l3.vpnaas_endpoint_group_max_eps)

    @registry.receives(resources.ROUTER, [events.PRECOMMIT_UPDATE])
    def _ensure_no_extra_route_on_vpnaas_router(self, resource, event, trigger, payload):
        if not (payload.request_body and payload.request_body.get('routes_added')):
            # no routes, nothing to check
            return

        context = payload.context
        router_db = payload.states[0]
        if not self._is_vpnaas_flavor(context, router_db['flavor_id']):
            return

        raise ExtraRoutesDisallowedOnVPNaaSRouter()
