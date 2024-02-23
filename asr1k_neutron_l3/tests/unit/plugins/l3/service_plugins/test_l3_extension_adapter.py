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

from unittest import mock

import netaddr
from neutron_lib import context
from neutron_lib.plugins import constants as plugin_constants
from neutron_lib.plugins import directory
from neutron.services.flavors import flavors_plugin
from neutron.tests.unit.extensions import test_l3
from oslo_utils import uuidutils

from asr1k_neutron_l3.plugins.db import asr1k_db
from asr1k_neutron_l3.plugins.l3.service_plugins.l3_extension_adapter import ASR1KPluginBase


class ASR1KTestL3NatIntPlugin(test_l3.TestL3NatIntPlugin):
    supported_extension_aliases = test_l3.TestL3NatIntPlugin.supported_extension_aliases + [
        'availability_zone', 'agent',
    ]


@mock.patch.object(asr1k_db.DBPlugin, 'get_network_port_count_per_agent', return_value={'fake-agent': 0})
class TestASR1kExtensionAdapter(test_l3.L3BaseForIntTests, test_l3.L3NatTestCaseMixin):
    def setUp(self):
        l3_plugin = 'asr1k_l3_routing'
        service_plugins = {'l3_plugin_name': l3_plugin}
        plugin = ('asr1k_neutron_l3.tests.unit.plugins.l3.service_plugins.'
                  'test_l3_extension_adapter.ASR1KTestL3NatIntPlugin')
        super().setUp(plugin=plugin, service_plugins=service_plugins)

        directory.add_plugin(plugin_constants.FLAVORS, flavors_plugin.FlavorsPlugin())

    def test_router_create(self, pc_mock):
        name = 'router1'
        tenant_id = uuidutils.generate_uuid()
        expected_value = [('name', name), ('tenant_id', tenant_id),
                          ('admin_state_up', True), ('status', 'ACTIVE'),
                          ('external_gateway_info', None)]
        with self.router(name=name, admin_state_up=True,
                         tenant_id=tenant_id) as router:
            for k, v in expected_value:
                self.assertEqual(v, router['router'][k])

    def test_router_create_with_extended_nat_pool(self, pc_mock):
        ctx = context.get_admin_context()

        with self.subnet(cidr="10.100.1.0/24") as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                             ]}) as router:
                db = asr1k_db.get_db_plugin()
                router_atts = db.get_router_att(ctx, router['router']['id'])
                self.assertEqual("10.100.1.2-10.100.1.5/24", router_atts.dynamic_nat_pool)

                expected_pool_ips = [f"10.100.1.{n}" for n in range(2, 6)]
                router_ips = [ip_def['ip_address']
                              for ip_def in router['router']['external_gateway_info']['external_fixed_ips']]
                router_ips.sort(key=lambda _ip: int(netaddr.IPAddress(_ip)))
                self.assertEqual(5, len(router_ips))
                self.assertEqual(expected_pool_ips, router_ips[:-1])

    def test_router_create_with_extended_nat_pool_with_specific_ips(self, pc_mock):
        ctx = context.get_admin_context()

        with self.subnet(cidr="10.100.1.0/24") as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'ip_address': "10.100.1.6"},
                                                        {'ip_address': "10.100.1.7"},
                                                        {'ip_address': "10.100.1.8"},
                                                        {'ip_address': "10.100.1.9"},
                                                        {'ip_address': "10.100.1.32"},
                             ]}) as router:
                db = asr1k_db.get_db_plugin()
                router_atts = db.get_router_att(ctx, router['router']['id'])
                self.assertEqual("10.100.1.6-10.100.1.9/24", router_atts.dynamic_nat_pool)

                expected_pool_ips = [f"10.100.1.{n}" for n in range(6, 10)] + ["10.100.1.32"]
                router_ips = [ip_def['ip_address']
                              for ip_def in router['router']['external_gateway_info']['external_fixed_ips']]
                router_ips.sort(key=lambda _ip: int(netaddr.IPAddress(_ip)))
                self.assertEqual(5, len(router_ips))
                self.assertEqual(expected_pool_ips, router_ips)

    def test_router_create_with_extended_nat_pool_with_specific_ips_unordered(self, pc_mock):
        ctx = context.get_admin_context()

        with self.subnet(cidr="10.100.1.0/24") as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'ip_address': "10.100.1.6"},
                                                        {'ip_address': "10.100.1.8"},
                                                        {'ip_address': "10.100.1.7"},
                                                        {'ip_address': "10.100.1.9"},
                                                        {'ip_address': "10.100.1.32"},
                             ]}) as router:
                db = asr1k_db.get_db_plugin()
                router_atts = db.get_router_att(ctx, router['router']['id'])
                self.assertEqual("10.100.1.6-10.100.1.9/24", router_atts.dynamic_nat_pool)

    def test_router_create_with_extended_nat_pool_with_specific_ips_with_one_ip_duplicated(self, pc_mock):
        with self.subnet(cidr="10.100.1.0/24") as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'ip_address': "10.100.1.6"},
                                                        {'ip_address': "10.100.1.7"},
                                                        {'ip_address': "10.100.1.8"},
                                                        {'ip_address': "10.100.1.9"},
                                                        {'ip_address': "10.100.1.7"},
                             ]}) as router:
                self.assertEqual("HTTPBadRequest",
                                 router["NeutronError"]["type"])
                self.assertIn("Duplicate IP address",
                              router["NeutronError"]["message"])

    def test_router_create_with_extended_nat_pool_with_specific_ips_except_for_router_ip(self, pc_mock):
        ctx = context.get_admin_context()

        with self.subnet(cidr="10.100.1.0/24") as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'ip_address': "10.100.1.6"},
                                                        {'ip_address': "10.100.1.7"},
                                                        {'ip_address': "10.100.1.8"},
                                                        {'ip_address': "10.100.1.9"},
                                                        {'subnet_id': s['subnet']['id']},
                             ]}) as router:
                db = asr1k_db.get_db_plugin()
                router_atts = db.get_router_att(ctx, router['router']['id'])
                self.assertEqual("10.100.1.6-10.100.1.9/24", router_atts.dynamic_nat_pool)

                expected_pool_ips = [f"10.100.1.{n}" for n in range(6, 10)]
                router_ips = [ip_def['ip_address']
                              for ip_def in router['router']['external_gateway_info']['external_fixed_ips']]
                router_ips.sort(key=lambda _ip: int(netaddr.IPAddress(_ip)))
                self.assertEqual(5, len(router_ips))
                self.assertEqual(expected_pool_ips, router_ips[:-1])

    def test_router_create_with_extended_nat_pool_non_consecutive_specified_nat_pool(self, pc_mock):
        with self.subnet(cidr="10.100.1.0/24") as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'ip_address': "10.100.1.5"},
                                                        {'ip_address': "10.100.1.6"},
                                                        {'ip_address': "10.100.1.8"},
                                                        {'ip_address': "10.100.1.9"},
                                                        {'subnet_id': s['subnet']['id']},
                             ]}) as router:
                self.assertEqual("DynamicNatPoolSpecifiedIpsNotConsecutivelyAscending",
                                 router["NeutronError"]["type"])
                self.assertIn("IP 10.100.1.6 and 10.100.1.8 don't follow each other", router["NeutronError"]["message"])

    def test_router_create_with_extended_nat_pool_mixed_specified_pool(self, pc_mock):
        with self.subnet(cidr="10.100.1.0/24") as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'ip_address': "10.100.1.6"},
                                                        {'ip_address': "10.100.1.8"},
                                                        {'ip_address': "10.100.1.7"},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                             ]}) as router:
                self.assertEqual("DynamicNatPoolIPDefinitionMixed",
                                 router["NeutronError"]["type"])

    def test_router_create_with_extended_nat_pool_two_subnets_found(self, pc_mock):
        with self.subnet(cidr="10.100.1.0/24") as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'subnet_id': uuidutils.generate_uuid()},
                                                        {'subnet_id': uuidutils.generate_uuid()},
                                                        {'subnet_id': s['subnet']['id']},
                             ]}) as router:
                self.assertEqual("DynamicNatPoolTwoSubnetsFound",
                                 router["NeutronError"]["type"])

    def test_router_create_with_extended_nat_pool_too_small(self, pc_mock):
        with self.subnet(cidr="10.100.1.0/24") as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                             ]}) as router:
                self.assertEqual("DynamicNatPoolNeedsToHaveAtLeastTwoIPs",
                                 router["NeutronError"]["type"])

    def test_router_create_with_extended_nat_pool_and_non_fitting_ips_specified(self, pc_mock):
        with self.subnet(cidr="10.100.1.0/24") as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'ip_address': "1.1.1.6"},
                                                        {'ip_address': "1.1.1.7"},
                                                        {'ip_address': "1.1.1.8"},
                                                        {'subnet_id': s['subnet']['id']},
                             ]}) as router:
                self.assertEqual("DynamicNatPoolGivenIPsDontBelongToNetwork",
                                 router["NeutronError"]["type"])

    def test_router_create_with_extended_nat_pool_exhausted(self, pc_mock):
        with self.subnet(cidr="10.100.1.0/27") as s:
            self._make_port("json", s['subnet']['network_id'], fixed_ips=[
                {'ip_address': '10.100.1.4'}, {'ip_address': '10.100.1.11'}, {'ip_address': '10.100.1.17'},
                {'ip_address': '10.100.1.24'}, {'ip_address': '10.100.1.29'}])
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                             ]}) as router:
                self.assertEqual("DynamicNatPoolExternalNetExhausted",
                                 router["NeutronError"]["type"])
                self.assertIn(f"Could not find 8 consecutive IP addresses in subnet {s['subnet']['id']}",
                              router["NeutronError"]["message"])

    def test_router_create_with_extended_nat_pool_exhausted_only_for_gw_ip(self, pc_mock):
        with self.subnet(cidr="10.100.1.0/28") as s:
            self._make_port("json", s['subnet']['network_id'], fixed_ips=[
                {'ip_address': f'10.100.1.{n}'} for n in range(2, 7)])
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                             ]}) as router:
                self.assertEqual("IpAddressGenerationFailure",
                                 router["NeutronError"]["type"])

    def test_router_create_with_extended_nat_pool_update_gateway(self, pc_mock):
        with self.subnet(cidr="10.100.1.0/24") as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                             ]}) as router:
                db = asr1k_db.get_db_plugin()
                ctx = context.get_admin_context()
                router_atts = db.get_router_att(ctx, router['router']['id'])
                self.assertEqual("10.100.1.2-10.100.1.5/24", router_atts.dynamic_nat_pool)

                with mock.patch.object(ASR1KPluginBase, 'ensure_default_route_skip_monitoring', autospec=True):
                    self._update('routers', router['router']['id'],
                                 {'router': {'external_gateway_info': {
                                     'network_id': s['subnet']['network_id'],
                                     'external_fixed_ips': [
                                         {'ip_address': "10.100.1.6"},
                                         {'ip_address': "10.100.1.7"},
                                         {'ip_address': "10.100.1.8"},
                                         {'subnet_id': s['subnet']['id']}]}}})

                ctx.session.expire_all()
                router_atts = db.get_router_att(ctx, router['router']['id'])
                self.assertEqual("10.100.1.6-10.100.1.8/24", router_atts.dynamic_nat_pool)

    def test_router_create_with_extended_nat_pool_remove_gateway(self, pc_mock):
        ctx = context.get_admin_context()

        with self.subnet(cidr="10.100.1.0/24") as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                             ]}) as router:
                db = asr1k_db.get_db_plugin()
                router_atts = db.get_router_att(ctx, router['router']['id'])
                router_atts = db.get_router_att(ctx, router['router']['id'])
                self.assertEqual("10.100.1.2-10.100.1.5/24", router_atts.dynamic_nat_pool)

                with mock.patch.object(ASR1KPluginBase, 'ensure_default_route_skip_monitoring', autospec=True):
                    upd_router = self._remove_external_gateway_from_router(router['router']['id'], None)

                ctx.session.expire_all()
                router_atts = db.get_router_att(ctx, router['router']['id'])
                self.assertIsNone(router_atts.dynamic_nat_pool)
                self.assertIsNone(upd_router['router']['external_gateway_info'])

    def test_router_create_with_extended_nat_pool_uses_smallest_segment(self, pc_mock):
        ctx = context.get_admin_context()

        with self.subnet(cidr="10.100.1.0/27") as s:
            self._make_port("json", s['subnet']['network_id'], fixed_ips=[
                {'ip_address': '10.100.1.24'}])
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                                                        {'subnet_id': s['subnet']['id']},
                             ]}) as router:

                db = asr1k_db.get_db_plugin()
                router_atts = db.get_router_att(ctx, router['router']['id'])
                self.assertEqual("10.100.1.25-10.100.1.28/27", router_atts.dynamic_nat_pool)
