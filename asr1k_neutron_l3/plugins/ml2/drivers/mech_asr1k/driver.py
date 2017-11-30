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


from neutron import context as n_context
from neutron.common import rpc as n_rpc
from neutron.extensions import portbindings
from neutron.i18n import _LI
from neutron.plugins.common import constants as p_constants
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2.drivers import mech_agent
from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from asr1k_neutron_l3.plugins.common import asr1k_constants
from asr1k_neutron_l3.plugins.db import asr1k_db
from asr1k_neutron_l3.plugins.ml2.drivers.mech_asr1k import constants
from asr1k_neutron_l3.plugins.ml2.drivers.mech_asr1k import rpc_api

LOG = logging.getLogger(__name__)

cfg.CONF.import_group('ml2_asr1k',
                      'asr1k_neutron_l3.plugins.ml2.drivers.mech_asr1k.config')


class ASR1KMechanismDriver(mech_agent.SimpleAgentMechanismDriverBase):
    def __init__(self):
        LOG.info(_LI("ASR mechanism driver initializing..."))

        self.agent_type = asr1k_constants.AGENT_TYPE_ASR1K_ML2
        self.vif_type = constants.VIF_TYPE_ASR1K
        self.vif_details = {portbindings.CAP_PORT_FILTER: False}
        self.physical_networks = cfg.CONF.ml2_asr1k.physical_networks

        self.vif_details = {portbindings.CAP_PORT_FILTER: False,
                            portbindings.OVS_HYBRID_PLUG: False,
                            }
        self.n_context = n_context.get_admin_context()

        super(ASR1KMechanismDriver, self).__init__(self.agent_type, self.vif_type, self.vif_details)

        self.start_rpc_listeners()

        LOG.info(_LI("ASR mechanism driver initialized."))

    def _setup_rpc(self):
        """Initialize components to support agent communication."""
        self.endpoints = [
            rpc_api.ASR1KPluginCallback()
        ]

    @log_helpers.log_method_call
    def start_rpc_listeners(self):
        """Start the RPC loop to let the plugin communicate with agents."""
        self._setup_rpc()
        self.topic = asr1k_constants.ASR1K_TOPIC
        self.conn = n_rpc.create_connection(new=True)
        self.conn.create_consumer(self.topic, self.endpoints, fanout=False)

        return self.conn.consume_in_threads()

    def initialize(self):
        pass

    def get_mappings(self, agent):
        return {}

    def get_allowed_network_types(self, agent):
        return ([p_constants.TYPE_VLAN])

    def update_port_postcommit(self, context):
        pass

    def delete_port_precommit(self, context):
        pass

    def delete_port_postcommit(self, context):
        pass

    def try_to_bind_segment_for_agent(self, context, segment, agent):
        LOG.info(_LI("try_to_bind_segment_for_agent"))
        LOG.info(context.current)

        # We only do router devices
        device_owner = context.current['device_owner']
        device_id = context.current['device_id']

        if not device_owner or not device_owner.startswith('network:router'):
            return False

        if not agent.get('admin_state_up', False) \
                or not agent.get('alive', False) \
                or agent['agent_type'].lower() != asr1k_constants.AGENT_TYPE_ASR1K_ML2.lower():
            return False

        agent_host = agent.get('host', None)

        # If the agent is bound to a host, then it can only handle those

        if agent_host and agent_host != context.current['binding:host_id']:
            return False

        extra_atts_db = asr1k_db.ExtraAttsDb(device_id, segment, context)
        extra_atts_db.update_extra_atts()

        context.set_binding(segment[api.ID],
                            self.vif_type,
                            self.vif_details)
        return True