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

import json
from unittest import mock

from neutron_lib import context
from neutron_lib.plugins import constants as plugin_constants
from neutron_lib.plugins import directory
from neutron.quota import resource_registry
from neutron.services.flavors import flavors_plugin
from neutron.tests.unit.extensions import test_l3
from oslo_config import cfg
from oslo_utils import uuidutils

from asr1k_neutron_l3.plugins.db import asr1k_db


@mock.patch.object(asr1k_db.DBPlugin, 'get_network_port_count_per_agent', new=mock.Mock(return_value={'fake-agent': 0}))
class TestASR1kRouterScheduling(test_l3.L3BaseForIntTests, test_l3.L3NatTestCaseMixin):
    def setUp(self):
        l3_plugin = 'asr1k_l3_routing'
        service_plugins = {'l3_plugin_name': l3_plugin}
        plugin = ('asr1k_neutron_l3.tests.common.fixtures.ASR1KTestL3NatIntPlugin')
        self.node_driver = "asr1k_neutron_l3.neutron.services.service_providers.asr1k_router.ASR1KRouterDriver"
        cfg.CONF.set_override('service_provider',
                              [f'L3_ROUTER_NAT:asr1k:{self.node_driver}:default'], group='service_providers')
        cfg.CONF.set_override("router_scheduler_driver",
                              "asr1k_neutron_l3.plugins.l3.schedulers.simple_asr1k_scheduler.SimpleASR1KScheduler")
        super().setUp(plugin=plugin, service_plugins=service_plugins)

        directory.add_plugin(plugin_constants.FLAVORS, flavors_plugin.FlavorsPlugin())

        self.db = asr1k_db.get_db_plugin()
        self.fp = directory.get_plugin(plugin_constants.FLAVORS)


    def _make_flavor(self, ctx, flavor_name, profiles=None, description='', service_type='L3_ROUTER_NAT', enabled=True):
        flavor_def = {'flavor': {
            'name': flavor_name,
            'description': description,
            'service_type': service_type,
            'enabled': enabled,
        }}
        flavor = self.fp.create_flavor(ctx, flavor_def)

        if profiles:
            for profile in profiles:
                sp = self._make_service_profile(ctx, **profile)
                self.fp.create_flavor_service_profile(ctx, {'service_profile': sp}, flavor['id'])
        return flavor['id']

    def _make_service_profile(self, ctx, metainfo, driver=None, enabled=True, description=''):
        sp_def = {'service_profile': {
            'driver': driver or self.node_driver,
            'enabled': enabled,
            'metainfo': metainfo,
            'description': description,
        }}
        return self.fp.create_service_profile(ctx, sp_def)

    def test_quota_registered_for_flavor(self):
        ctx = context.get_admin_context()
        self._make_flavor(ctx, "quota-flavor", profiles=[{'metainfo': json.dumps({"req_quota": True})}])
        self.assertFalse(bool(resource_registry.get_resource("routers_flavor_quota-flavor")))
        l3_plugin = directory.get_plugin("L3_ROUTER_NAT")
        l3_plugin.register_quotas_for_flavors(ctx)
        self.assertTrue(bool(resource_registry.get_resource("routers_flavor_quota-flavor")))

    def test_create_router_with_flavor_quota_missing(self):
        cfg.CONF.set_override('default_quota', 0, group='QUOTAS')
        ctx = context.get_admin_context()
        f_quota = self._make_flavor(ctx, "quota-flavor", profiles=[{'metainfo': json.dumps({"req_quota": True})}])
        l3_plugin = directory.get_plugin("L3_ROUTER_NAT")
        l3_plugin.register_quotas_for_flavors(ctx)

        with self.router(name="no-fries-for-the-gull", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                         flavor_id=f_quota) as r:
            self.assertIn("NeutronError", r)
            self.assertEqual("OverQuota", r["NeutronError"]["type"])

    def test_create_router_with_flavor_quota_autoregister_and_still_missing(self):
        cfg.CONF.set_override('default_quota', 0, group='QUOTAS')
        ctx = context.get_admin_context()
        f_quota = self._make_flavor(ctx, "quota-flavor", profiles=[{'metainfo': json.dumps({"req_quota": True})}])

        with self.router(name="no-fries-for-the-gull", admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                         flavor_id=f_quota) as r:
            self.assertIn("NeutronError", r)
            self.assertEqual("OverQuota", r["NeutronError"]["type"])

    def test_create_router_with_flavor_quota_available(self):
        cfg.CONF.set_override('default_quota', 10, group='QUOTAS')
        ctx = context.get_admin_context()
        f_quota = self._make_flavor(ctx, "quota-flavor", profiles=[{'metainfo': json.dumps({"req_quota": True})}])
        l3_plugin = directory.get_plugin("L3_ROUTER_NAT")
        l3_plugin.register_quotas_for_flavors(ctx)
        quota_res = resource_registry.get_resource("routers_flavor_quota-flavor")

        project_id = uuidutils.generate_uuid()
        self.assertEqual(0, quota_res.count(ctx, l3_plugin, project_id))
        with self.router(name="no-fries-for-the-gull", admin_state_up=True, tenant_id=project_id,
                         flavor_id=f_quota) as r:
            self.assertIn("router", r)
        self.assertEqual(1, quota_res.count(ctx, l3_plugin, project_id))
