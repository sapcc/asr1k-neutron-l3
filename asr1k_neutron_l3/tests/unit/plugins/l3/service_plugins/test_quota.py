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
from neutron_lib.plugins import directory
from neutron.quota import resource_registry
from oslo_config import cfg
from oslo_utils import uuidutils

from asr1k_neutron_l3.plugins.db import asr1k_db
from asr1k_neutron_l3.tests.common.fixtures import RouterWithSyncDataTestCase


@mock.patch.object(asr1k_db.DBPlugin, 'get_network_port_count_per_agent', new=mock.Mock(return_value={'fake-agent': 0}))
class TestASR1kRouterScheduling(RouterWithSyncDataTestCase):
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
