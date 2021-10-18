# Copyright 2017 SAP SE
#
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from neutron.scheduler import l3_agent_scheduler
from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from asr1k_neutron_l3.common import asr1k_constants as asr1k_const

LOG = logging.getLogger(__name__)


class SimpleASR1KScheduler(l3_agent_scheduler.AZLeastRoutersScheduler):

    @log_helpers.log_method_call
    def schedule(self, plugin, context, router_id, candidates=None, hints=None):
        return self._schedule_router(
            plugin, context, router_id, candidates=candidates)

    @log_helpers.log_method_call
    def _get_candidates(self, plugin, context, sync_router):
        """Return L3 agents where a router could be scheduled."""
        with context.session.begin(subtransactions=True):

            current_l3_agents = plugin.get_l3_agents_hosting_routers(
                context, [sync_router['id']], admin_state_up=True)
            if current_l3_agents:
                LOG.debug('Router %(router_id)s has already been hosted '
                          'by L3 agent %(agent_id)s',
                          {'router_id': sync_router['id'],
                           'agent_id': current_l3_agents[0]['id']})
                return []

            orig_candidates = plugin.get_l3_agents(context, active=True)

            # router creation with az hint: only schedule on agent with appropriate AZ
            # router creation without az hint: only schedule on agent with no AZ
            az_hints = orig_az_hints = self._get_az_hints(sync_router)
            if not az_hints or az_hints[0] in asr1k_const.NO_AZ_LIST:
                az_hints = asr1k_const.NO_AZ_LIST
            candidates = [c for c in orig_candidates if c.availability_zone in az_hints]

            if not candidates and orig_az_hints and cfg.CONF.asr1k.ignore_invalid_az_hint_for_router:
                LOG.warning("No candidate found for router %s with az hint %s, reverting to original candidate list %s",
                            sync_router['id'], az_hints, orig_candidates)
                candidates = orig_candidates

            if not candidates:
                LOG.warning('No active L3 agents found for router %s (az hints were %s)',
                            sync_router['id'], orig_az_hints)
                return []

            LOG.info("Found following candidates for router %s: %s",
                     sync_router['id'], ", ".join(c.host for c in candidates))

            return candidates

    def _choose_router_agent(self, plugin, context, candidates):
        candidate_ids = [candidate['id'] for candidate in candidates]
        chosen_agent = plugin.get_l3_agent_with_min_routers(
            context, candidate_ids)
        return chosen_agent

    def _choose_router_agents_for_ha(self, plugin, context, candidates):
        """Choose agents from candidates based on a specific policy."""
        pass
