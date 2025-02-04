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

    def test_router_with_dapnet_v4(self):
        with self.address_scope(name="the-open-sea") as addr_scope, \
                self.subnetpool(["10.100.0.0/22"], name="yellow-legged-gull",
                                address_scope_id=addr_scope['address_scope']['id'],
                                tenant_id=uuidutils.generate_uuid(), admin=True) as sn_pool, \
                self.subnet(cidr="10.100.1.0/24", subnetpool_id=sn_pool['subnetpool']['id']) as s_ext, \
                self.subnet(cidr="10.100.2.0/24", subnetpool_id=sn_pool['subnetpool']['id']) as s_dap, \
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
                            ip_version=6) as s_ext, \
                self.subnet(cidr="2001:db8:101:11b2::/64", subnetpool_id=sn_pool['subnetpool']['id'],
                            ip_version=6) as s_dap, \
                self.subnet(cidr="fd00:1234:5678::/64", ip_version=6) as s_int:
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
