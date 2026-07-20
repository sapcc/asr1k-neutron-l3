# Copyright 2024 SAP SE
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from neutron_lib import context
from neutron_lib.plugins import directory
from oslo_config import cfg
from oslo_utils import uuidutils

from asr1k_neutron_l3.tests.common.fixtures import RouterWithSyncDataTestCase


class TestRouterClass(RouterWithSyncDataTestCase):
    def setUp(self):
        super().setUp()
        self.register_address_scope_rt("the-open-sea", "65123:101")

    def test_router_simple(self):
        with self.subnet(cidr="10.100.1.0/24") as s_ext, self.subnet(cidr="10.200.1.0/24") as s1:
            self._set_net_external(s_ext['subnet']['network_id'])
            router = self.make_router_extended(name="r1", ext_subnet=s_ext, int_subnets=[s1])
            dev_router = self._get_ny_router(router['router']['id'])

        self.assertEqual(router['router']['external_gateway_info']['external_fixed_ips'][0]['ip_address'],
                         dev_router.interfaces.gateway_interface._rest_definition.to_dict(
                         self.asr1k_ctx)['BD-VIF']['ip']['address']['primary']['address'])
        self.assertEqual(['10.100.1.0/24'], dev_router.interfaces.get_external_networks_v4())
        self.assertEqual(['10.200.1.0/24'], dev_router.interfaces.get_internal_networks_v4())
        self.assertEqual([], dev_router.interfaces.get_routable_networks_v4())
        self.assertFalse(dev_router.bgp_address_family[4].enable_bgp)
        self.assertFalse(dev_router.bgp_address_family[6].enable_bgp)
        self.assertIsNotNone(dev_router.vrf._rest_definition.address_family_ipv4)
        self.assertIsNone(dev_router.vrf._rest_definition.address_family_ipv6)
        self.assertTrue(dev_router.gateway_interface._rest_definition.nat_outside)
        self.assertIsNone(dev_router.gateway_interface._rest_definition.access_group_in)
        self.assertEqual("EXT-TOS", dev_router.gateway_interface._rest_definition.access_group_out)

    def test_router_with_dapnet_v4(self):
        with self.address_scope(name="the-open-sea") as addr_scope, \
                self.subnetpool(["10.100.0.0/22"], name="yellow-legged-gull",
                                address_scope_id=addr_scope['address_scope']['id'],
                                tenant_id=uuidutils.generate_uuid(), admin=True) as sn_pool, \
                self.subnet(cidr="10.100.1.0/24", subnetpool_id=sn_pool['subnetpool']['id'], as_admin=True) as s_ext, \
                self.subnet(cidr="10.100.2.0/24", subnetpool_id=sn_pool['subnetpool']['id'], as_admin=True) as s_dap, \
                self.subnet(cidr="10.200.0.0/24") as s_int:
            self._set_net_external(s_ext['subnet']['network_id'])
            router = self.make_router_extended(name="r1", ext_subnet=s_ext, int_subnets=[s_dap, s_int])
            dev_router = self._get_ny_router(router['router']['id'])

        self.assertEqual(['10.100.1.0/24'], dev_router.interfaces.get_external_networks_v4())
        self.assertEqual(['10.100.2.0/24', '10.200.0.0/24'], dev_router.interfaces.get_internal_networks_v4())
        self.assertEqual(['10.100.2.0/24'], dev_router.interfaces.get_routable_networks_v4())

        # bgp af
        self.assertTrue(dev_router.bgp_address_family[4].enable_bgp)
        self.assertFalse(dev_router.bgp_address_family[6].enable_bgp)
        bgp_af4_dict = dev_router.bgp_address_family[4]._rest_definition.to_dict(self.asr1k_ctx)
        self.assertEqual([{'number': '10.100.2.0', 'mask': '255.255.255.0', 'route-map': 'RM-DAP'},
                          {'number': '10.200.0.0', 'mask': '255.255.255.0'}],
                         bgp_af4_dict['vrf']['ipv4-unicast']['network']['with-mask'])

    def test_router_with_dapnet_v6(self):
        with self.address_scope(name="the-open-sea", ip_version=6) as addr_scope, \
                self.subnetpool(["2001:db8:101:1100::/56"], name="lesser-black-backed-gull",
                                address_scope_id=addr_scope['address_scope']['id'],
                                tenant_id=uuidutils.generate_uuid(), admin=True) as sn_pool, \
                self.subnet(cidr="2001:db8:101:11a1::/64", subnetpool_id=sn_pool['subnetpool']['id'],
                            ip_version=6, as_admin=True) as s_ext, \
                self.subnet(cidr="2001:db8:101:11b2::/64", subnetpool_id=sn_pool['subnetpool']['id'],
                            ip_version=6, as_admin=True) as s_dap, \
                self.subnet(cidr="fd00:1234:5678::/64", ip_version=6, as_admin=True) as s_int:
            self._set_net_external(s_ext['subnet']['network_id'])
            router = self.make_router_extended(name="r1", ext_subnet=s_ext, int_subnets=[s_dap, s_int])
            dev_router = self._get_ny_router(router['router']['id'])

        self.assertEqual(['2001:db8:101:11a1::/64'], dev_router.interfaces.get_external_networks_v6())
        self.assertEqual(['2001:db8:101:11b2::/64', 'fd00:1234:5678::/64'],
                         dev_router.interfaces.get_internal_networks_v6())
        self.assertEqual(['2001:db8:101:11b2::/64'], dev_router.interfaces.get_routable_networks_v6())

        # bgp af
        self.assertFalse(dev_router.bgp_address_family[4].enable_bgp)
        self.assertTrue(dev_router.bgp_address_family[6].enable_bgp)
        bgp_af6_dict = dev_router.bgp_address_family[6]._rest_definition.to_dict(self.asr1k_ctx)
        rm6_name = f"bgp-redistribute6-{dev_router.vrf.name}"
        self.assertEqual({'connected': {'route-map': rm6_name}, 'static': {'route-map': rm6_name}},
                         bgp_af6_dict['vrf']['ipv6-unicast']['redistribute-v6'])

        self.assertEqual(['2001:db8:101:11b2::/64', 'fd00:1234:5678::/64'],
                         [pl for pl in dev_router.prefix_lists if pl.name.startswith("internal6-")][0].prefixes)
        self.assertEqual(['2001:db8:101:11b2::/64'],
                         [pl for pl in dev_router.prefix_lists if pl.name.startswith("routable6-")][0].prefixes)

        pl_er6 = [pl for pl in dev_router.prefix_lists if pl.name.startswith("routable-extraroutes6-")][0]
        self.assertEqual(1, len(pl_er6._rest_definition.seq))
        self.assertEqual("deny", pl_er6._rest_definition.seq[0].action)

        self.assertIsNotNone(dev_router.vrf._rest_definition.address_family_ipv4)
        self.assertIsNotNone(dev_router.vrf._rest_definition.address_family_ipv6)


class TestRouterClassWithVPN(RouterWithSyncDataTestCase):
    def setUp(self):
        super().setUp()
        cfg.CONF.set_override('disconnected_subnets_mode', True, group='vpnaas')
        self.register_address_scope_rt("the-open-sea", "65123:101")
        self.vpn_driver = directory.get_plugin('VPN').drivers['cisco_ipsec']

        ctx = context.get_admin_context()
        self.vpnaas_flavor_id = self._make_flavor(ctx, "vpnaas-falaaaaavor",
                                                  profiles=[{'metainfo': self._make_meta(req=["vpnaas"])}])

    def _make_vpn_ready_router(self):
        with self.subnet(cidr="10.100.1.0/24") as s_ext:
            self._set_net_external(s_ext['subnet']['network_id'])
            return self.make_router_extended(name="r1", ext_subnet=s_ext, int_subnets=[],
                                             flavor_id=self.vpnaas_flavor_id)

    def _find_entry(self, cls_name, entries, single=True, check_nonexistent=False):
        result = [e for e in entries if e.__class__.__name__ == cls_name]
        if check_nonexistent:
            self.assertEqual([], result)
            return None
        if single:
            self.assertEqual(1, len(result))
            return result[0]
        return result

    def test_router_with_vpn_tunnel_conf(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        sc_objs = self._make_sitecon_related_objs(ipsec_args={"encapsulation_mode": "tunnel"})
        self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            psk="supercilium",
            **sc_objs,
        )
        dev_router = self._get_ny_router(router['router']['id'])
        ipsec_ts = self._find_entry("IPSecTransformSet", dev_router.vpnaas_conf)._rest_definition
        self.assertIsNone(ipsec_ts.transport_choice)
        self.assertTrue(ipsec_ts.tunnel_choice)
        self.assertEqual(2, len(dev_router.routes[4].routes))
        self.assertEqual({"0.0.0.0", "193.175.214.0"}, {r.destination for r in dev_router.routes[4].routes})
        iface = self._find_entry("TunnelInterface", dev_router.vpnaas_conf)._rest_definition
        self.assertFalse(iface.shutdown)
        ike_keyring = self._find_entry("IKEv2Keyring", dev_router.vpnaas_conf)._rest_definition
        self.assertEqual("supercilium", ike_keyring.peers[0].psk)
        self.assertFalse(dev_router.gateway_interface._rest_definition.nat_outside)
        self.assertIsNone(dev_router.gateway_interface._rest_definition.access_group_in)
        self.assertEqual(f"ACL-NO-SPOOF-V4-{dev_router.router_id.replace('-', '')}",
                         dev_router.gateway_interface._rest_definition.access_group_out)

    def test_router_with_vpn_transport_conf(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        sc_objs = self._make_sitecon_related_objs(ipsec_args={"encapsulation_mode": "transport"},
                                                  local_eps=["10.100.1.0/24", "10.100.8.0/24"],
                                                  peer_eps=["193.175.214.0/24", "193.175.215.0/24"])
        self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            **sc_objs,
        )
        dev_router = self._get_ny_router(router['router']['id'])

        ipsec_ts = self._find_entry("IPSecTransformSet", dev_router.vpnaas_conf)._rest_definition
        self.assertTrue(ipsec_ts.transport_choice)
        self.assertIsNone(ipsec_ts.tunnel_choice)

        acl = self._find_entry("IPSecTransportAccessList", dev_router.vpnaas_conf)
        self.assertEqual({("10.100.1.0", "193.175.214.0"), ("10.100.1.0", "193.175.215.0"),
                          ("10.100.8.0", "193.175.214.0"), ("10.100.8.0", "193.175.215.0")},
                         {(r.source, r.destination) for r in acl.rules})

    def test_router_with_nat_ip(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        sc_objs = self._make_sitecon_related_objs(ipsec_args={"encapsulation_mode": "tunnel"})
        self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            peer_id="1.2.3.4",
            peer_nat_address_v4="5.6.7.8",
            **sc_objs,
        )
        dev_router = self._get_ny_router(router['router']['id'])
        ike_prof = self._find_entry("IKEv2Profile", dev_router.vpnaas_conf)._rest_definition
        self.assertEqual(2, len(ike_prof.remote_identities_v4))
        self.assertEqual([{"ipv4-address": "1.2.3.4", "ipv4-mask": "255.255.255.255"},
                          {"ipv4-address": "5.6.7.8", "ipv4-mask": "255.255.255.255"}],
                         [ri.to_dict(dev_router.contexts[0]) for ri in ike_prof.remote_identities_v4])

    def test_router_with_two_connections(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            **self._make_sitecon_related_objs(peer_eps=["193.175.214.0/24"], ike_args={"auth_algorithm": "sha256"})
        )
        self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            **self._make_sitecon_related_objs(peer_eps=["193.175.215.0/24"], ike_args={"auth_algorithm": "sha384"})
        )
        dev_router = self._get_ny_router(router['router']['id'])
        ike_pol = self._find_entry("IKEv2Policy", dev_router.vpnaas_conf)._rest_definition
        self.assertEqual(2, len(ike_pol.proposals))
        self.assertEqual(['aes-128_sha256_group15', 'aes-128_sha384_group15'], ike_pol.proposals)

    def test_router_int_peer_address_out_of_network(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        sc_objs = self._make_sitecon_related_objs()
        self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            int_local_cidr_v4="169.254.0.1/30",
            int_peer_address_v4="192.168.178.1",
            **sc_objs,
        )
        dev_router = self._get_ny_router(router['router']['id'])
        self.assertEqual(3, len(dev_router.routes[4].routes))
        self.assertEqual({"0.0.0.0", "192.168.178.1", "193.175.214.0"},
                         {r.destination for r in dev_router.routes[4].routes})
        for route in dev_router.routes[4].routes:
            if route.destination != "0.0.0.0":
                self.assertTrue(route.nexthop.startswith("Tunnel"))

    def test_router_sitecon_disabled_tunnel_shut(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        sc_objs = self._make_sitecon_related_objs()
        self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            admin_state_up=False,
            **sc_objs,
        )
        dev_router = self._get_ny_router(router['router']['id'])
        iface = self._find_entry("TunnelInterface", dev_router.vpnaas_conf)._rest_definition
        self.assertTrue(iface.shutdown)

    def test_router_with_aes_gcm(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            **self._make_sitecon_related_objs(peer_eps=["193.175.214.0/24"],
                                              ike_args={"encryption_algorithm": "aes-256-gcm-16",
                                                        "auth_algorithm": "sha512"},
                                              ipsec_args={"encryption_algorithm": "aes-256-gcm-16",
                                                          "auth_algorithm": "sha512"})
        )
        dev_router = self._get_ny_router(router['router']['id'])

        # make sure prf_$hash is set, but $hash is not
        ike_prop = self._find_entry("IKEv2Proposal", dev_router.vpnaas_conf)._rest_definition
        self.assertTrue(ike_prop.aes_gcm_256)
        self.assertTrue(ike_prop.prf_sha512)
        self.assertFalse(ike_prop.int_sha512)
        self.assertTrue(ike_prop.fifteen)
        self.assertIn('sha512', ike_prop.to_dict(context)['proposal']['prf'])

        ipsec_ts = self._find_entry("IPSecTransformSet", dev_router.vpnaas_conf)._rest_definition
        self.assertIsNone(ipsec_ts.esp_hmac)
