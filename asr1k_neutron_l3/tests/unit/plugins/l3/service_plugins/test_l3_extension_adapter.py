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
        'availability_zone', 'agent', 'flavors',
    ]
    pass


class TestASR1kExtensionAdapter(test_l3.L3BaseForIntTests, test_l3.L3NatTestCaseMixin):
    def setUp(self):
        l3_plugin = 'asr1k_l3_routing'
        service_plugins = {'l3_plugin_name': l3_plugin}
        # plugin, default neutron.tests.unit.extensions.test_l3.TestL3NatIntPlugin
        # extmgr, default L3TestExtensionManager
        plugin = ('asr1k_neutron_l3.tests.unit.plugins.l3.service_plugins.'
                  'test_l3_extension_adapter.ASR1KTestL3NatIntPlugin')
        super().setUp(plugin=plugin, service_plugins=service_plugins)

        directory.add_plugin(plugin_constants.FLAVORS, flavors_plugin.FlavorsPlugin())

        # create test flavor
        ctx = context.get_admin_context()
        fp = directory.get_plugin(plugin_constants.FLAVORS)
        sp_def = {'service_profile': {
            'driver': 'neutron.services.l3_router.service_providers.single_node.SingleNodeDriver',
            'enabled': True,
            'metainfo': '{"dynamic-nat-ips": 4}',
            'description': 'Test dynamic nat flavor',
        }}
        # sp = flavor_plugin.create_service_profile(ctx, sp_def)
        sp = fp.create_service_profile(ctx, sp_def)
        flavor_def = {'flavor': {
            'name': 'xxl-router',
            'description': 'That is one big router for sure',
            'service_type': 'L3_ROUTER_NAT',
            'enabled': True,
        }}
        self.flavor = fp.create_flavor(ctx, flavor_def)
        fp.create_flavor_service_profile(ctx, {'service_profile': sp}, self.flavor['id'])

    def test_router_create(self):
        name = 'router1'
        tenant_id = uuidutils.generate_uuid()
        expected_value = [('name', name), ('tenant_id', tenant_id),
                          ('admin_state_up', True), ('status', 'ACTIVE'),
                          ('external_gateway_info', None)]
        with self.router(name=name, admin_state_up=True,
                         tenant_id=tenant_id) as router:
            for k, v in expected_value:
                self.assertEqual(v, router['router'][k])

    @mock.patch.object(ASR1KPluginBase, '_validate_gw_info',
                       side_effect=ASR1KPluginBase._validate_gw_info, autospec=True)
    def test_validate_gw_info_called(self, vgi_mock):
        name = 'router1'
        tenant_id = uuidutils.generate_uuid()
        with self.subnet() as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name=name, admin_state_up=True, tenant_id=tenant_id,
                             external_gateway_info={'network_id': s['subnet']['network_id']}) as router:
                print(router)
                self.assertEqual(name, router['router']['name'])
                vgi_mock.assert_called_once()

    def test_router_create_with_no_extnat_pool_and_multiple_ips(self):
        pass

    def test_router_create_with_no_extnat_pool_pool_ips_not_subsequent(self):
        pass

    def test_router_create_with_extended_nat_pool_and_flavor(self):
        ctx = context.get_admin_context()
        print(directory.get_plugin())
        print(directory.get_plugin().ipam)

        with self.subnet(cidr="10.100.1.0/24") as s:
            print("subnet", s)
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'subnet_id': uuidutils.generate_uuid()},
                                                        {'subnet_id': uuidutils.generate_uuid()},
                                                        {'subnet_id': uuidutils.generate_uuid()},
                                                        {'subnet_id': uuidutils.generate_uuid()},
                                                        {'subnet_id': uuidutils.generate_uuid()},
                              ]},
                                                    # 'external_fixed_ips': [{'ip_address': '0.0.0.0'}]},
                             flavor_id=self.flavor['id']) as router:
                print(router)
                self.assertEqual(self.flavor['id'], router['router']['flavor_id'])
                db = asr1k_db.get_db_plugin()
                router_atts = db.get_router_att(ctx, router['router']['id'])
                self.assertEqual(4, router_atts.nat_ip_count)
        assert False

    def test_router_create_with_extended_nat_pool(self):
        ctx = context.get_admin_context()

        with self.subnet(cidr="10.100.1.0/24") as s:
            self._set_net_external(s['subnet']['network_id'])
            with self.router(name="r1", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                             external_gateway_info={'network_id': s['subnet']['network_id'],
                                                    'external_fixed_ips': [
                                                        {'subnet_id': uuidutils.generate_uuid()},
                                                        {'subnet_id': uuidutils.generate_uuid()},
                                                        {'subnet_id': uuidutils.generate_uuid()},
                                                        {'subnet_id': uuidutils.generate_uuid()},
                                                        {'subnet_id': uuidutils.generate_uuid()},
                             ]}) as router:
                print(router)
                db = asr1k_db.get_db_plugin()
                router_atts = db.get_router_att(ctx, router['router']['id'])
                self.assertEqual(4, router_atts.nat_ip_count)
        assert False
