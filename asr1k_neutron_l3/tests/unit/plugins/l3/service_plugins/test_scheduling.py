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

import json
from unittest import mock

from neutron_lib.agent import topics
from neutron_lib import context
from neutron_lib.plugins import constants as plugin_constants
from neutron_lib.plugins import directory
from neutron.services.flavors import flavors_plugin
from neutron.tests.unit.extensions import test_l3
from oslo_config import cfg
from oslo_utils import timeutils, uuidutils

from asr1k_neutron_l3.plugins.db import asr1k_db
from asr1k_neutron_l3.common import asr1k_constants as asr1k_const


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

    def _make_agent(self, host, configuration=None, az='nova'):
        if not configuration:
            configuration = {}
        agent = {
          'agent_type': asr1k_const.AGENT_TYPE_ASR1K_L3,
          'binary': 'asr1k-agent',
          'host': host,
          'topic': topics.L3_AGENT,
          'availability_zone': az,
          'configurations': configuration}

        admin_context = context.get_admin_context()
        self.db.create_or_update_agent(admin_context, agent, timeutils.utcnow())
        return self.db._get_agent_by_type_and_host(
          admin_context, agent['agent_type'], agent['host'])

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

    def _make_meta(self, req=None, opt=None):
        metainfo = []
        if req is not None:
            metainfo["req_traits"] = req
        if opt is not None:
            metainfo["opt_traits"] = opt

        return json.dumps(metainfo)

    def _make_agent(self, ctx, host, configuration=None, az='nova'):
        if not configuration:
            configuration = {}
        agent = {
          'agent_type': asr1k_const.AGENT_TYPE_ASR1K_L3,
          'binary': 'asr1k-agent',
          'host': host,
          'topic': topics.L3_AGENT,
          'availability_zone': az,
          'configurations': configuration}

        admin_context = context.get_admin_context()
        self.db.create_or_update_agent(admin_context, agent, timeutils.utcnow())
        return self.db._get_agent_by_type_and_host(
          admin_context, agent['agent_type'], agent['host']).id

    def _make_agent_with_traits(self, ctx, host, req_traits=None, opt_traits=None):
        c = {
            'req_traits': req_traits or [],
            'opt_traits': opt_traits or [],
        }

        return self._make_agent(ctx, host, configuration=c)

    def _make_meta(self, req=None, opt=None, quota=None):
        metainfo = {}
        if req is not None:
            metainfo["req_traits"] = req
        if opt is not None:
            metainfo["opt_traits"] = opt

        if quota is not None:
            metainfo["req_quota"] = quota

        return json.dumps(metainfo)

    def _make_flavored_router(self, ext_net_id, flavor_id, name="r1"):
        with self.router(name=name, admin_state_up=True, tenant_id=uuidutils.generate_uuid(),
                         external_gateway_info={'network_id': ext_net_id},
                         flavor_id=flavor_id) as r:
            self.assertNotIn('NeutronError', r, f"Could not create router: {r}")
            return r["router"]["id"]

    def _get_router_agent_set(self, ctx, router_ids):
        agent_ids = set()
        for router_id in router_ids:
            agents = self.db.get_l3_agents_hosting_routers(ctx, router_id)
            self.assertEqual(1, len(agents), "Router needs to be hosted by exactly one agent")
            agent_ids.add(agents[0].id)
        return agent_ids

    def test_get_metainfo_from_flavor_id(self):
        ctx = context.get_admin_context()
        l3_plugin = directory.get_plugin("L3_ROUTER_NAT")

        # req
        flav = self._make_flavor(ctx, "my-100g-device", profiles=[{'metainfo': self._make_meta(req=["100g"])}])
        self.assertEqual({"name": "my-100g-device", "req_quota": False, "req_traits": ["100g"], "opt_traits": []},
                         l3_plugin.get_metainfo_from_flavor_id(ctx, flav))

        # opt
        flav = self._make_flavor(ctx, "open-sea", profiles=[{'metainfo': self._make_meta(opt=["seagull"])}])
        self.assertEqual({"name": "open-sea", "req_quota": False, "req_traits": [], "opt_traits": ["seagull"]},
                         l3_plugin.get_metainfo_from_flavor_id(ctx, flav))

        # req and opt, multiple values and quota
        flav = self._make_flavor(ctx, "open-sea",
                                 profiles=[{'metainfo': self._make_meta(req=["100g", "oystercatcher"],
                                                                        opt=["seagull"], quota=True)}])
        self.assertEqual({"name": "open-sea", "req_quota": True,
                          "req_traits": ["100g", "oystercatcher"], "opt_traits": ["seagull"]},
                         l3_plugin.get_metainfo_from_flavor_id(ctx, flav))

        # multiple meta infos / service profiles
        flav = self._make_flavor(ctx, "open-sea",
                                 profiles=[{'metainfo': self._make_meta(req=["100g"],
                                                                        opt=["seagull"])},
                                           {'metainfo': self._make_meta(req=["oystercatcher"],
                                                                        opt=["gunnet"])}
                                                                        ])
        mi = l3_plugin.get_metainfo_from_flavor_id(ctx, flav)
        self.assertEqual({"100g", "oystercatcher"}, set(mi["req_traits"]))
        self.assertEqual({"seagull", "gunnet"}, set(mi["opt_traits"]))

    def test_get_metainfo_from_flavor_id_with_broken_service_profiles(self):
        ctx = context.get_admin_context()
        l3_plugin = directory.get_plugin("L3_ROUTER_NAT")

        # req
        profiles = [
            # wrong format
            {'metainfo': '["foo"]'},
            # broken json
            {'metainfo': '['},
            # missing key
            {'metainfo': '{"foo": 23}'},
            # working profile in the middle
            {'metainfo': '{"opt_traits": ["meow"]}'},
            # trait part with wrong format
            {'metainfo': '{"req_traits": "foo"}'},
            # trait with broken values in it
            {'metainfo': '{"req_traits": [123, {"foo": 23}, "100g", [1,2,3]]}'},
        ]
        flav = self._make_flavor(ctx, "broken-sea", profiles=profiles)
        self.assertEqual({"name": "broken-sea", "req_quota": False, "req_traits": ["100g"], "opt_traits": ["meow"]},
                         l3_plugin.get_metainfo_from_flavor_id(ctx, flav))


    def test_router_scheduled_on_right_agent_with_flavors(self):
        ctx = context.get_admin_context()

        # agents
        a_def = self._make_agent_with_traits(ctx, "asr1k-agent-01")
        a_100g = self._make_agent_with_traits(ctx, "asr1k-agent-02", req_traits=["100g"])
        a_weird = self._make_agent_with_traits(ctx, "asr1k-agent-03", opt_traits=["weird"])
        a_unsched1 = self._make_agent_with_traits(ctx, "asr1k-agent-04",
                                                  req_traits=[asr1k_const.TRAIT_SCHEDULING_DISABLED])
        a_unsched2 = self._make_agent(ctx, "asr1k-agent-05", configuration={"scheduling_disabled": True})

        # flavors
        f_common = self._make_flavor(ctx, "common-router", profiles=[{'metainfo': ''}])
        f_100g = self._make_flavor(ctx, "my-100g-device", profiles=[{'metainfo': self._make_meta(req=["100g"])}])
        f_weird_opt = self._make_flavor(ctx, "my-100g-device", profiles=[{'metainfo': self._make_meta(opt=["weird"])}])
        f_weird_req = self._make_flavor(ctx, "my-100g-device", profiles=[{'metainfo': self._make_meta(req=["weird"])}])
        f_unsched = self._make_flavor(ctx, "my-100g-device",
                                      profiles=[{'metainfo':
                                                self._make_meta(opt=[asr1k_const.TRAIT_SCHEDULING_DISABLED])}])

        with self.subnet(cidr="10.100.1.0/24") as s:
            ext_net_id = s['subnet']['network_id']
            self._set_net_external(ext_net_id)

            # no traits --> anywhere where no required trait is present
            routers_common = [
                self._make_flavored_router(ext_net_id, f_common),
                self._make_flavored_router(ext_net_id, f_common),
                self._make_flavored_router(ext_net_id, f_common),
                self._make_flavored_router(ext_net_id, None),
            ]
            self.assertEqual({a_def, a_weird}, self._get_router_agent_set(ctx, routers_common))

            # req 100g --> only where 100g is required or optional
            routers_100g = [
                self._make_flavored_router(ext_net_id, f_100g),
                self._make_flavored_router(ext_net_id, f_100g),
                self._make_flavored_router(ext_net_id, f_100g),
                self._make_flavored_router(ext_net_id, f_100g),
            ]
            self.assertEqual({a_100g}, self._get_router_agent_set(ctx, routers_100g))

            # opt weird --> normal or weird router
            routers_weird_opt = [
                self._make_flavored_router(ext_net_id, f_weird_opt),
                self._make_flavored_router(ext_net_id, f_weird_opt),
                self._make_flavored_router(ext_net_id, f_weird_opt),
                self._make_flavored_router(ext_net_id, f_weird_opt),
            ]
            self.assertEqual({a_def, a_weird}, self._get_router_agent_set(ctx, routers_weird_opt))

            # req weird --> only weird router
            routers_weird_req = [
                self._make_flavored_router(ext_net_id, f_weird_req),
                self._make_flavored_router(ext_net_id, f_weird_req),
                self._make_flavored_router(ext_net_id, f_weird_req),
                self._make_flavored_router(ext_net_id, f_weird_req),
            ]
            self.assertEqual({a_weird}, self._get_router_agent_set(ctx, routers_weird_req))

            # req unsched --> due to "least used" scheduling each "unschedulable router" should have at least one
            routers_unsched = [
                self._make_flavored_router(ext_net_id, f_unsched),
                self._make_flavored_router(ext_net_id, f_unsched),
                self._make_flavored_router(ext_net_id, f_unsched),
                self._make_flavored_router(ext_net_id, f_unsched),
                self._make_flavored_router(ext_net_id, f_unsched),
            ]
            self.assertEqual({a_unsched1, a_unsched2},
                             {a_unsched1, a_unsched2} & self._get_router_agent_set(ctx, routers_unsched))
