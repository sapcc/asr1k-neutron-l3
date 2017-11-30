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


import six
from neutron.db import agents_db
from neutron.db import agentschedulers_db
from neutron.db import l3_agentschedulers_db
from neutron.extensions import agent as n_agent
from neutron.extensions import l3agentscheduler
from neutron.extensions import router_availability_zone as router_az
from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from asr1k_neutron_l3.plugins.common import asr1k_constants as constants

LOG = logging.getLogger(__name__)


class ASR1KAgentSchedulerDbMixin(l3_agentschedulers_db.L3AgentSchedulerDbMixin):
    """Mixin class to add l3 agent scheduler extension to plugins
    using the l3 agent for routing.
    """

    @log_helpers.log_method_call
    def validate_agent_router_combination(self, context, agent, router):
        """Validate if the router can be correctly assigned to the agent.

        :raises: RouterL3AgentMismatch if attempting to assign DVR router
          to legacy agent.
        :raises: InvalidL3Agent if attempting to assign router to an
          unsuitable agent (disabled, type != L3, incompatible configuration)
        :raises: DVRL3CannotAssignToDvrAgent if attempting to assign a
          router to an agent in 'dvr' mode.
        """
        if agent['agent_type'] != constants.AGENT_TYPE_ASR1K_L3:
            raise l3agentscheduler.InvalidL3Agent(id=agent['id'])

        agent_mode = self._get_agent_mode(agent)

        is_suitable_agent = (
                agentschedulers_db.services_available(agent['admin_state_up']) and
                self.get_l3_agent_candidates(context, router,
                                             [agent],
                                             ignore_admin_state=True))
        if not is_suitable_agent:
            raise l3agentscheduler.InvalidL3Agent(id=agent['id'])

    @log_helpers.log_method_call
    def list_router_ids_on_host(self, context, host, router_ids=None):
        try:
            agent = self._get_agent_by_type_and_host(
                context, constants.AGENT_TYPE_ASR1K_L3, host)
        except n_agent.AgentNotFoundByTypeHost:
            return []

        if not agentschedulers_db.services_available(agent.admin_state_up):
            return []
        return self._get_router_ids_for_agent(context, agent, router_ids)

    @log_helpers.log_method_call
    def list_active_sync_routers_on_active_l3_agent(
            self, context, host, router_ids):

        try:
            agent = self._get_agent_by_type_and_host(
                context, constants.AGENT_TYPE_ASR1K_L3, host)
        except n_agent.AgentNotFoundByTypeHost:
            return []

        if not agentschedulers_db.services_available(agent.admin_state_up):
            LOG.debug("Agent has its services disabled. Returning "
                      "no active routers. Agent: %s", agent)
            return []
        scheduled_router_ids = self._get_router_ids_for_agent(
            context, agent, router_ids)
        diff = set(router_ids or []) - set(scheduled_router_ids or [])
        if diff:
            LOG.debug("Agent requested router IDs not scheduled to it. "
                      "Scheduled: %(sched)s. Unscheduled: %(diff)s. "
                      "Agent: %(agent)s.",
                      {'sched': scheduled_router_ids, 'diff': diff,
                       'agent': agent})
        if scheduled_router_ids:
            return self._get_active_l3_agent_routers_sync_data(
                context, host, agent, scheduled_router_ids)
        return []

    @log_helpers.log_method_call
    def get_l3_agents(self, context, active=None, filters=None):
        query = context.session.query(agents_db.Agent)

        # n_const.AGENT_TYPE_L3

        query = query.filter(
            agents_db.Agent.agent_type == constants.AGENT_TYPE_ASR1K_L3)
        if active is not None:
            query = (query.filter(agents_db.Agent.admin_state_up == active))
        if filters:
            for key, value in six.iteritems(filters):
                column = getattr(agents_db.Agent, key, None)
                if column:
                    if not value:
                        return []
                    query = query.filter(column.in_(value))

        return [l3_agent for l3_agent in query]


class AZASR1KL3AgentSchedulerDbMixin(ASR1KAgentSchedulerDbMixin,
                                     router_az.RouterAvailabilityZonePluginBase):
    """Mixin class to add availability_zone supported l3 agent scheduler."""

    @log_helpers.log_method_call
    def get_router_availability_zones(self, router):
        return list({agent.availability_zone for agent in router.l3_agents})
