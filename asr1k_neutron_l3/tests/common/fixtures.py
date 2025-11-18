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

from unittest import mock

from neutron.db import address_scope_db
from neutron.db.models.segment import NetworkSegment
from neutron.db import models_v2
from neutron.extensions import address_scope as ext_address_scope
from neutron.extensions import l3
from neutron_lib import constants as nl_const
from neutron_lib import context
from neutron_lib.db import api as db_api
from neutron_lib.plugins import constants as plugin_constants
from neutron_lib.plugins import directory
from neutron.plugins.ml2 import models as ml2_models
from neutron.scheduler import l3_agent_scheduler
from neutron.services.flavors import flavors_plugin
from neutron.tests.common import helpers
from neutron.tests.unit.extensions import test_l3, test_address_scope
from neutron_vpnaas.extensions import vpnaas as ext_vpnaas
from oslo_config import cfg
from oslo_serialization import jsonutils
from oslo_utils import uuidutils

from asr1k_neutron_l3.common import asr1k_constants
from asr1k_neutron_l3.common import config as asr1k_config
from asr1k_neutron_l3.models.asr1k_pair import ASR1KPair, FakeASR1KContext
from asr1k_neutron_l3.models.neutron.l3.router import Router
from asr1k_neutron_l3.plugins.db import asr1k_db
from asr1k_neutron_l3.plugins.l3.service_plugins.l3_extension_adapter import ASR1KPluginBase
from asr1k_neutron_l3.tests.common.vpnaas import ASR1KVPNaaSMixin
from asr1k_neutron_l3.tests.common.flavor import FlavorSchedulingMixin


DB_VPN_PLUGIN_KLASS = "neutron_vpnaas.services.vpn.asr1k_plugin.VPNASR1KDriverPlugin"


class FakeASR1KPair:
    def __init__(self):
        self.config = cfg.CONF
        self.contexts = [
            FakeASR1KContext(),
            FakeASR1KContext(),
        ]


class ASR1KTestL3NatIntPlugin(test_l3.TestL3NatIntPlugin, address_scope_db.AddressScopeDbMixin):
    supported_extension_aliases = test_l3.TestL3NatIntPlugin.supported_extension_aliases + [
        'availability_zone', 'agent', 'address-scope', 'flavors', 'vpnaas',
    ]


class ASR1KTestExtensionManager:
    def get_resources(self):
        return (l3.L3.get_resources() +
                ext_address_scope.Address_scope.get_resources() +
                ext_vpnaas.Vpnaas.get_resources())

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []


@mock.patch.object(asr1k_db.DBPlugin, 'get_network_port_count_per_agent', new=mock.Mock(return_value={'fake-agent': 0}))
class RouterWithSyncDataTestCase(test_address_scope.AddressScopeTestCase,
                                 test_l3.L3BaseForIntTests, test_l3.L3NatTestCaseMixin,
                                 FlavorSchedulingMixin, ASR1KVPNaaSMixin):
    def setUp(self):
        l3_plugin = 'asr1k_l3_routing'
        service_plugins = {'l3_plugin_name': l3_plugin, 'vpnaas': DB_VPN_PLUGIN_KLASS}

        self.node_driver = "asr1k_neutron_l3.neutron.services.service_providers.asr1k_router.ASR1KRouterDriver"
        vpn_driver = 'asr1k_neutron_l3.neutron.services.service_drivers.asr1k.vpnaas_driver.ASR1KIPSecVPNaaSDriver'
        cfg.CONF.set_override('service_provider', [f'L3_ROUTER_NAT:asr1k:{self.node_driver}:default',
                                                   f'VPN:cisco_ipsec:{vpn_driver}:default'],
                              group='service_providers')
        cfg.CONF.set_override("router_scheduler_driver",
                              "asr1k_neutron_l3.plugins.l3.schedulers.simple_asr1k_scheduler.SimpleASR1KScheduler")

        # NOTE(seba): we're currently using our own fake test plugin and then for specific
        #             calls we're using an instance of the ASR1KPluginBase to get certain data -
        #             maybe we can improve this and use our real plugin some day
        plugin = ('asr1k_neutron_l3.tests.common.fixtures.ASR1KTestL3NatIntPlugin')
        self.ext_mgr = ASR1KTestExtensionManager()

        super().setUp(plugin=plugin, service_plugins=service_plugins, ext_mgr=self.ext_mgr)

        self.plugin = ASR1KPluginBase()
        self.db = asr1k_db.get_db_plugin()

        directory.add_plugin(plugin_constants.FLAVORS, flavors_plugin.FlavorsPlugin())
        self.fp = directory.get_plugin(plugin_constants.FLAVORS)

        self.default_host = 'asr1k-agent-314159'
        self.default_physnet = 'np2653589'
        self.agent = self.register_asr1k_l3_agent(host=self.default_host, az='nova')

        # for device setup
        asr1k_config.register_common_opts()
        asr1k_config.register_l3_opts()

        ASR1KPair._ASR1KPair__instance = FakeASR1KPair()
        self.asr1k_ctx = FakeASR1KContext()

        self.address_scope_rts = {}

    def register_asr1k_l3_agent(self, host, az):
        internal_only = True
        agent_mode = nl_const.L3_AGENT_MODE_LEGACY
        agent = helpers._get_l3_agent_dict(host, agent_mode, internal_only, az)
        agent['agent_type'] = asr1k_constants.AGENT_TYPE_ASR1K_L3
        return helpers._register_agent(agent)

    def register_address_scope_rt(self, name, rt):
        self.address_scope_rts[name] = rt

    @db_api.CONTEXT_WRITER
    def _make_network_segment(self, context, network_id, physical_network, network_type='vlan', segment_id=None):
        """Find or create a network segment

        Search for a network segment with the given physnet/network_id/network_type. If it exists,
        return it, else create it. This mimics the behavior of Neutron's TypeDrivers, but without
        it and the ml2 drivers needing to be instanciated (and could be replaced with that one day).
        """
        segments = context.session.query(NetworkSegment).filter_by(physical_network=physical_network,
                                                                   network_id=network_id,
                                                                   network_type=network_type).all()
        if segments:
            # segment already exists, returning it
            return segments[0]

        # need to allocate a new segment one
        if not segment_id:
            # find a vlan id
            all_segments = context.session.query(NetworkSegment).filter_by(physical_network=physical_network,
                                                                           network_type=network_type).all()
            all_seg_ids = {seg.segmentation_id for seg in all_segments}
            for segment_id in range(1000, 3000):
                if segment_id not in all_seg_ids:
                    break
            else:
                raise ValueError("Segments exhausted in tests, didn't expect that to ever happen!")

        netseg = NetworkSegment(id=uuidutils.generate_uuid(), network_id=network_id, segmentation_id=segment_id,
                                physical_network=physical_network, network_type=network_type)
        context.session.add(netseg)

        return netseg

    @db_api.CONTEXT_WRITER
    def _make_port_binding(self, context, port_id, host, network_id, physical_network, vlan_id=None):
        # NOTE(seba): we technically don't need the top level segment, but as most stuff in our infra is hierarchically
        #             port bound, we'll just create it, as usual
        vxlan_netseg = self._make_network_segment(context, network_id, physical_network, 'vxlan')
        vlan_netseg = self._make_network_segment(context, network_id, physical_network, 'vlan', vlan_id)

        pb = ml2_models.PortBinding(port_id=port_id, host=host, vif_type='test')
        context.session.add(pb)

        pbl = [
            ml2_models.PortBindingLevel(port_id=port_id, segment_id=vxlan_netseg.id, host=host,
                                        driver='asr1k-ml2', level=0),
            ml2_models.PortBindingLevel(port_id=port_id, segment_id=vlan_netseg.id, host=host,
                                        driver='asr1k-ml2', level=1),
        ]
        context.session.add(*pbl)

        return vlan_netseg

    def _add_subnet_to_router(self, router_id, subnet, vlan_id=None, ia_kwargs={}):
        """Add subnet to router, including a port binding"""
        network_id = subnet['subnet']['network_id']
        with self.port(subnet=subnet, device_owner="network:router_interface") as port:
            port_id = port['port']['id']
            self._router_interface_action('add', router_id, None, port_id, as_admin=True, **ia_kwargs)

            ctx = context.get_admin_context()
            netseg = self._make_port_binding(ctx, port['port']['id'], self.default_host, network_id,
                                             self.default_physnet, vlan_id)
            port_obj = {'id': port['port']['id'], 'binding:host_id': self.default_host}
            asr1k_db.ExtraAttsDb.ensure(router_id, port_obj, netseg, clean_old=True)

    def make_router_extended(self, admin_state_up=True, tenant_id=None, external_gateway_info=None,
                             ext_subnet=None, int_subnets=None, **kwargs):
        """Create a router with an agent binding and portbindings for provided subnets"""
        if not tenant_id:
            tenant_id = uuidutils.generate_uuid()

        # external subnet shortcut
        if ext_subnet:
            if external_gateway_info:
                raise ValueError("Test cannot have ext_subnet and external_gateway_info")
            external_gateway_info = {'network_id': ext_subnet['subnet']['network_id']}

        # create router
        ctx = context.get_admin_context()
        with mock.patch.object(asr1k_db.DBPlugin, 'get_network_port_count_per_agent',
                               return_value={'fake-agent': 0}):
            with self.router(as_admin=True, admin_state_up=admin_state_up, tenant_id=tenant_id,
                             external_gateway_info=external_gateway_info, **kwargs) as router:
                pass

        # create agent binding
        scheduler = l3_agent_scheduler.ChanceScheduler()
        scheduler.bind_router(self.plugin, ctx, router['router']['id'], self.agent.id)
        l3_notifier = self.plugin.agent_notifiers[nl_const.AGENT_TYPE_L3]
        with mock.patch.object(l3_notifier.client, 'prepare', return_value=l3_notifier.client), \
                mock.patch.object(l3_notifier.client, 'call'):
            self.plugin.add_router_to_l3_agent(ctx, self.agent.id, router['router']['id'])

        # handle external gateway prt bindings + extra atts
        if external_gateway_info:
            with db_api.CONTEXT_WRITER.using(ctx):
                port = ctx.session.query(models_v2.Port).filter_by(device_id=router['router']['id'],
                                                                   device_owner='network:router_gateway').first()
                netseg = self._make_port_binding(ctx, port.id, self.default_host, port.network_id,
                                                 self.default_physnet)

                # _add_subnet_to_router() ensures ExtraAtts, _make_port_binding() does not
                port_obj = {'id': port.id, 'binding:host_id': self.default_host}
                asr1k_db.ExtraAttsDb.ensure(router['router']['id'], port_obj, netseg, clean_old=True)

        # handle internal subnets
        if int_subnets:
            for int_subnet in int_subnets:
                self._add_subnet_to_router(router['router']['id'], int_subnet)

        return router

    def _get_sync_data(self, router_id):
        """Get sync data of a router similar to what the asr1k agent gets"""
        ctx = context.get_admin_context()
        sync_data = self.plugin.get_sync_data(ctx, [router_id])[0]

        # convert sync-data models to primitives, as it is done when transferring data per RPC
        sync_data = jsonutils.to_primitive(sync_data, convert_instances=True)

        # simulate rpc serialization / deserialization
        # this implicitly converts int dict keys to str - which makes a different for the address_scope dict
        sync_data = jsonutils.loads(jsonutils.dumps(sync_data))

        # get and add address scope config (similar to utils.get_address_scope_config())
        scopes = {}
        for scope in self.db.get_address_scopes(ctx, filters={"name": list(self.address_scope_rts)}):
            scopes[scope['id']] = self.address_scope_rts[scope['name']]
        sync_data[asr1k_constants.ADDRESS_SCOPE_CONFIG] = scopes

        return sync_data

    def _get_ny_router(self, router_id):
        sync_data = self._get_sync_data(router_id)
        dev_router = Router(sync_data)

        return dev_router
