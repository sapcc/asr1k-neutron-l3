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

from neutron_lib.agent import topics
from neutron_lib import context
from oslo_utils import timeutils

from asr1k_neutron_l3.common import asr1k_constants as asr1k_const

class FlavorSchedulingMixin:
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

        self.db.create_or_update_agent(ctx, agent, timeutils.utcnow())
        return self.db._get_agent_by_type_and_host(
          ctx, agent['agent_type'], agent['host']).id

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
