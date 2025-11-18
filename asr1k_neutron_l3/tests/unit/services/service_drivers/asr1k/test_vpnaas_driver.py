# Copyright 2025 SAP SE
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

import ipaddress
from unittest import mock

from neutron_lib import context
from neutron_lib.callbacks.exceptions import CallbackFailure
from neutron_lib.plugins import directory
from neutron.common import cache_utils as cache
from neutron.extensions import tagging
from neutron.services.tag import tag_plugin
from oslo_config import cfg

from asr1k_neutron_l3.plugins.l3.rpc import ask1k_l3_notifier as asr1k_l3_notifier
from asr1k_neutron_l3.tests.common.fixtures import RouterWithSyncDataTestCase

class TestRouterClassWithVPN(RouterWithSyncDataTestCase):
    def setUp(self):
        super().setUp()
        cfg.CONF.set_override('disconnected_subnets_mode', True, group='vpnaas')
        self.register_address_scope_rt("the-open-sea", "65123:101")
        self.vpn_driver = directory.get_plugin('VPN').drivers['cisco_ipsec']

        ctx = context.get_admin_context()
        self.vpnaas_flavor_id = self._make_flavor(ctx, "vpnaas-falaaaaavor",
                                                  profiles=[{'metainfo': self._make_meta(req=["vpnaas"])}])

        directory.add_plugin(tagging.TAG_PLUGIN_TYPE, tag_plugin.TagPlugin())

        # caching config
        cache.register_oslo_configs(cfg.CONF)
        cfg.CONF.set_override('enabled', True, group='cache')
        cfg.CONF.set_override('backend', 'oslo_cache.dict', group='cache')

    def _make_vpn_ready_router(self):
        with self.subnet(cidr="10.100.1.0/24") as s_ext:
            self._set_net_external(s_ext['subnet']['network_id'])
            return self.make_router_extended(name="r1", ext_subnet=s_ext, int_subnets=[],
                                             flavor_id=self.vpnaas_flavor_id)

    def test_no_internal_networks_on_vpnaas_router(self):
        router = self._make_vpn_ready_router()
        with self.subnet(cidr="10.200.1.0/24") as s1:
            self._add_subnet_to_router(router['router']['id'], s1, ia_kwargs={"expected_code": 409})

    def test_vpnservice_only_on_vpnaas_router(self):
        with self.subnet(cidr="10.100.1.0/24") as s_ext:
            self._set_net_external(s_ext['subnet']['network_id'])
            router = self.make_router_extended(name="r1", ext_subnet=s_ext, int_subnets=[])
            vpn1 = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
            self.assertIn("NeutronError", vpn1)
            self.assertEqual("RouterIsNotVPNaaSFlavor", vpn1["NeutronError"]["type"])

    def test_only_one_vpnservice_per_router(self):
        router = self._make_vpn_ready_router()
        vpn1 = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        self.assertIn("vpnservice", vpn1)
        vpn2 = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        self.assertEqual("MultipleVPNServicesOnRouterDisallowed", vpn2['NeutronError']['type'])
        self.assertIn(vpn1['vpnservice']['id'], vpn2['NeutronError']['message'])

    def test_router_with_cipher_checks(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)

        sc_objs = self._make_sitecon_related_objs(ike_args={"ike_version": "v1"})
        broken_args = [
            # ike policy
            ("IKE Policy", "auth algorithm", {"ike_args": {"auth_algorithm": "sha1"}}),
            ("IKE Policy", "encryption", {"ike_args": {"encryption_algorithm": "aes-128-ctr"}}),
            ("IKE Policy", "version", {"ike_args": {"ike_version": "v1"}}),
            ("IKE Policy", "DH group", {"ike_args": {"pfs": "group2"}}),

            # ipsec policy
            ("IPSec Policy", "auth algorithm", {"ipsec_args": {"auth_algorithm": "sha1"}}),
            ("IPSec Policy", "encryption", {"ipsec_args": {"encryption_algorithm": "aes-128-ctr"}}),
            ("IPSec Policy", "transform protocol", {"ipsec_args": {"transform_protocol": "ah"}}),
            ("IPSec Policy", "DH group", {"ipsec_args": {"pfs": "group2"}}),
        ]

        for invalid_obj, invalid_key, obj_kwargs in broken_args:
            sc_objs = self._make_sitecon_related_objs(**obj_kwargs)
            sitecon = self._create_ipsec_site_connection("json",
                vpnservice_id=vpn["vpnservice"]["id"],
                **sc_objs,
            )
            self.assertIn("NeutronError", sitecon)
            msg = sitecon["NeutronError"]["message"]
            self.assertIn(f"invalid {invalid_obj}:", msg)
            self.assertIn(f"{invalid_key} value", msg)

    def test_endpoint_group_limit(self):
        cfg.CONF.set_override('vpnaas_endpoint_group_max_eps', 10, group='asr1k_l3')
        epg_ok = self._create_endpoint_group("json", name="meow", type="cidr",
                                             endpoints=[f"10.200.{n}.0/24" for n in range(10)])
        self.assertIn('endpoint_group', epg_ok)

        epg_fail = self._create_endpoint_group("json", name="meow", type="cidr",
                                               endpoints=[f"10.200.{n}.0/24" for n in range(11)])
        self.assertEqual("EndpointGroupTooLarge", epg_fail['NeutronError']['type'])

    def test_tunnel_ips_autoalloc(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        sc_objs = self._make_sitecon_related_objs()
        sitecon = self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            **sc_objs,
        )
        all_v4 = ipaddress.ip_network("0.0.0.0/0")
        all_v6 = ipaddress.ip_network("::/0")
        sitecon = sitecon['ipsec_site_connection']
        self.assertTrue(ipaddress.ip_network(sitecon['int_local_cidr_v4'], strict=False).overlaps(all_v4))
        self.assertTrue(ipaddress.ip_network(sitecon['int_local_cidr_v6'], strict=False).overlaps(all_v6))
        self.assertIn(ipaddress.ip_address(sitecon['int_peer_address_v4']), all_v4)
        self.assertIn(ipaddress.ip_address(sitecon['int_peer_address_v6']), all_v6)

    def test_tunnel_ips_specified(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        sc_objs = self._make_sitecon_related_objs()
        sitecon = self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            int_local_cidr_v4="169.254.23.41/30",
            int_peer_address_v4="169.254.23.42",
            int_local_cidr_v6="fd03:1415:9265:3589:0:0:0000:1/126",
            int_peer_address_v6="fd03:1415:9265:3589::2",
            **sc_objs,
        )
        sitecon = sitecon['ipsec_site_connection']
        self.assertEqual(sitecon['int_local_cidr_v4'], "169.254.23.41/30")
        self.assertEqual(sitecon['int_peer_address_v4'], "169.254.23.42")
        self.assertEqual(sitecon['int_local_cidr_v6'], "fd03:1415:9265:3589::1/126")
        self.assertEqual(sitecon['int_peer_address_v6'], "fd03:1415:9265:3589::2")

    def test_tunnel_ips_specified_wrong_af(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        sc_objs = self._make_sitecon_related_objs()

        test_args = [
            ("local cidr v4", "fd04::1/126", "169.254.23.42", "fd03::1/126", "fd03::2"),
            ("peer address v4", "169.254.23.41/30", "fd04::2", "fd03::1/126", "fd03::2"),
            ("local cidr v6", "169.254.23.41/30", "169.254.23.42", "169.254.0.1/24", "fd03::2"),
            ("peer address v6", "169.254.23.41/30", "169.254.23.42", "fd03::1/126", "169.254.0.2"),
        ]
        for msg_part, int_local_cidr_v4, int_peer_address_v4, int_local_cidr_v6, int_peer_address_v6 in test_args:
            sitecon = self._create_ipsec_site_connection("json",
                vpnservice_id=vpn["vpnservice"]["id"],
                int_local_cidr_v4=int_local_cidr_v4,
                int_peer_address_v4=int_peer_address_v4,
                int_local_cidr_v6=int_local_cidr_v6,
                int_peer_address_v6=int_peer_address_v6,
                **sc_objs,
            )
            self.assertEqual("InvalidVPNaaSInternalTunnelIps", sitecon["NeutronError"]["type"])
            self.assertIn(f"Invalid address family for internal {msg_part}", sitecon["NeutronError"]["message"])

    def test_tunnel_ips_autoalloc_failures(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        sc_objs = self._make_sitecon_related_objs()

        test_data = [
            # disallow specifying only one of these (always need to appear in pairs)
            {"int_local_cidr_v4": "12.12.12.1/24"},
            {"int_peer_address_v4": "12.12.12.1"},
            {"int_local_cidr_v6": "2001::1/128"},
            {"int_peer_address_v6": "2001::1"},

            # same local and peer address
            {"int_local_cidr_v4": "12.12.12.1/24", "int_peer_address_v4": "12.12.12.1"},
            {"int_local_cidr_v6": "2001::1/128", "int_peer_address_v6": "2001::1"},
        ]
        for td in test_data:
            sitecon = self._create_ipsec_site_connection("json",
                vpnservice_id=vpn["vpnservice"]["id"],
                **(sc_objs | td),
            )
            self.assertIn("NeutronError", sitecon, f"Testdata is {td}")
            self.assertEqual("InvalidVPNaaSInternalTunnelIps", sitecon["NeutronError"]["type"])

    def test_tunnel_ips_fail_on_overlap_between_connections(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            int_local_cidr_v4="169.254.23.41/30",
            int_peer_address_v4="169.254.23.42",
            int_local_cidr_v6="fd03:1415:9265:3589:0:0:0000:1/126",
            int_peer_address_v6="fd03:1415:9265:3589::2",
            **self._make_sitecon_related_objs(),
        )

        sitecon2 = self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            int_local_cidr_v4="169.254.23.41/30",
            int_peer_address_v4="169.254.23.42",
            **self._make_sitecon_related_objs(peer_eps=["3.141.59.26/24"]),
        )
        self.assertIn("NeutronError", sitecon2)
        self.assertEqual("InvalidVPNaaSInternalTunnelIps", sitecon2["NeutronError"]["type"])

    def test_sitecon_peers_dont_have_duplicate_endpoints(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            int_local_cidr_v4="169.254.23.41/30",
            int_peer_address_v4="169.254.23.42",
            **self._make_sitecon_related_objs(peer_eps=["193.175.214.0/24"]),
        )

        # same endpoint disallowed
        sitecon = self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            **self._make_sitecon_related_objs(peer_eps=["193.175.214.0/24"]),
        )
        self.assertIn("NeutronError", sitecon)
        self.assertEqual("DuplicateEndpointsBetweenIPSecSiteConnections", sitecon["NeutronError"]["type"])

        # subnet is allowed
        sitecon = self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            **self._make_sitecon_related_objs(peer_eps=["193.175.214.0/25"]),
        )
        self.assertNotIn("NeutronError", sitecon)

        # overlap with other endpoint is disallowed
        sitecon = self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            **self._make_sitecon_related_objs(peer_eps=["169.254.23.42/32"]),
        )
        self.assertIn("NeutronError", sitecon)
        self.assertEqual("DuplicateEndpointsBetweenIPSecSiteConnections", sitecon["NeutronError"]["type"])

    def test_peer_nat_address_present(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        sc_objs = self._make_sitecon_related_objs()
        sitecon = self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            peer_nat_address_v4='1.2.3.4',
            **sc_objs,
        )
        self.assertEqual("1.2.3.4", sitecon['ipsec_site_connection']['peer_nat_address_v4'])

    def test_peer_nat_address_disallow_ipv6(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        sc_objs = self._make_sitecon_related_objs()
        sitecon = self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            peer_nat_address_v4='fd12:3456::1',
            **sc_objs,
        )
        self.assertIn("NeutronError", sitecon)
        self.assertEqual("PeerNatAddressMustBeIPv4", sitecon['NeutronError']['type'])

    def test_extraroutes_on_vpnaas_router_fail(self):
        router = self._make_vpn_ready_router()
        self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)

        ctx = context.get_admin_context()
        ext_ip = router['router']['external_gateway_info']['external_fixed_ips'][0]['ip_address']
        ext_ip = ipaddress.ip_address(ext_ip) + 1
        route_def = {"router": {'routes': [{'destination': "193.175.214.0/24", "nexthop": str(ext_ip)}]}}
        self.assertRaisesRegex(CallbackFailure, "Extra routes are disallowed on VPNaaS flavored routers",
                               self.plugin.add_extraroutes, ctx, router['router']['id'], route_def)

    def test_extraroutes_on_non_vpnaas_still_works(self):
        with self.subnet(cidr="10.100.1.0/24") as s_ext:
            self._set_net_external(s_ext['subnet']['network_id'])
            router = self.make_router_extended(name="r1", ext_subnet=s_ext, int_subnets=[])

        ctx = context.get_admin_context()
        ext_ip = router['router']['external_gateway_info']['external_fixed_ips'][0]['ip_address']
        ext_ip = ipaddress.ip_address(ext_ip) + 1
        route_def = {"router": {'routes': [{'destination': "193.175.214.0/24", "nexthop": str(ext_ip)}]}}
        ret = self.plugin.add_extraroutes(ctx, router['router']['id'], route_def)
        self.assertEqual(1, len(ret['router']['routes']))

    def test_tunnel_id_alloc_dealloc(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        sc_objs = self._make_sitecon_related_objs()
        sitecon = self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            **sc_objs,
        )
        ctx = context.get_admin_context()
        ids = self.db.get_vpn_tunnel_ids(ctx, ipsec_site_connection_ids=[sitecon['ipsec_site_connection']['id']])
        self.assertEqual(1, len(ids))
        req = self.new_delete_request(
            'ipsec-site-connections',
            sitecon['ipsec_site_connection']['id']
        )
        res = req.get_response(self.api)
        self.assertEqual(res.status_int, 204)

        ids = self.db.get_vpn_tunnel_ids(ctx, ipsec_site_connection_ids=[sitecon['ipsec_site_connection']['id']])
        self.assertEqual(0, len(ids))

    def test_ipsec_site_connection_notify_on_delete(self):
        router = self._make_vpn_ready_router()
        vpn = self._create_vpnservice("json", "vpn1", True, router['router']['id'], None, as_admin=True)
        sc_objs = self._make_sitecon_related_objs()
        sitecon = self._create_ipsec_site_connection("json",
            vpnservice_id=vpn["vpnservice"]["id"],
            **sc_objs,
        )
        ctx = context.get_admin_context()
        ids = self.db.get_vpn_tunnel_ids(ctx, ipsec_site_connection_ids=[sitecon['ipsec_site_connection']['id']])
        self.assertEqual(1, len(ids))
        req = self.new_delete_request(
            'ipsec-site-connections',
            sitecon['ipsec_site_connection']['id']
        )
        with mock.patch.object(asr1k_l3_notifier.ASR1KAgentNotifyAPI, 'delete_tunnel_interface') as mock_dti:
            res = req.get_response(self.api)
            self.assertEqual(res.status_int, 204)
            mock_dti.assert_called_once_with(mock.ANY, self.agent.host, ids[0]['number'])
