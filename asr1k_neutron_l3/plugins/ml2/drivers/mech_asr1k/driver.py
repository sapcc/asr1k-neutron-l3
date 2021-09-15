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

from neutron_lib.api.definitions import portbindings
from neutron_lib import constants as p_constants
from neutron_lib import context as n_context
from neutron_lib.plugins.ml2 import api
from neutron_lib import rpc as n_rpc
from neutron import service
from neutron.plugins.ml2.drivers import mech_agent
from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from asr1k_neutron_l3.common import asr1k_constants
from asr1k_neutron_l3.plugins.db import asr1k_db
from asr1k_neutron_l3.plugins.ml2.drivers.mech_asr1k import constants
from asr1k_neutron_l3.plugins.ml2.drivers.mech_asr1k import rpc_api

LOG = logging.getLogger(__name__)

cfg.CONF.import_group('ml2_asr1k',
                      'asr1k_neutron_l3.plugins.ml2.drivers.mech_asr1k.config')


class ASR1KMechanismDriver(mech_agent.SimpleAgentMechanismDriverBase):
    def __init__(self):
        LOG.info("ASR mechanism driver initializing...")

        self.agent_type = asr1k_constants.AGENT_TYPE_ASR1K_ML2
        self.vif_type = constants.VIF_TYPE_ASR1K
        self.vif_details = {portbindings.CAP_PORT_FILTER: False}
        self.physical_networks = cfg.CONF.ml2_asr1k.physical_networks

        self.vif_details = {portbindings.CAP_PORT_FILTER: False,
                            portbindings.OVS_HYBRID_PLUG: False,
                            }
        self.n_context = n_context.get_admin_context()

        super(ASR1KMechanismDriver, self).__init__(self.agent_type, self.vif_type, self.vif_details)
        self.db = asr1k_db.get_db_plugin()

        LOG.info("ASR mechanism driver initialized.")

    def _setup_rpc(self):
        """Initialize components to support agent communication."""
        self.endpoints = [
            rpc_api.ASR1KPluginCallback()
        ]

    def get_workers(self):
        return [service.RpcWorker([self], worker_process_count=0)]

    @log_helpers.log_method_call
    def start_rpc_listeners(self):
        """Start the RPC loop to let the plugin communicate with agents."""
        self._setup_rpc()
        self.topic = asr1k_constants.ASR1K_TOPIC
        self.conn = n_rpc.Connection()
        self.conn.create_consumer(self.topic, self.endpoints, fanout=False)

        return self.conn.consume_in_threads()

    def initialize(self):
        pass

    def get_mappings(self, agent):
        return {}

    def get_allowed_network_types(self, agent=None):
        return [p_constants.TYPE_VLAN]

    def update_port_postcommit(self, context):
        port_id = context.current.get('id')

        # We only do router devices
        device_owner = context.current.get('device_owner', None)
        device_id = context.current.get('device_id', None)

        if device_id is None or device_owner is None or not device_owner.startswith('network:router'):
            return

        admin_context = n_context.get_admin_context()
        att = self.db.get_extra_att(admin_context, port_id)
        if att is None:
            LOG.warning("Detected ,missing port extra atts for port {} attempting to recreate".format(port_id))
            device_id = context.current.get('device_id', None)
            segment = context.bottom_bound_segment
            if device_id is not None and segment is not None:
                asr1k_db.ExtraAttsDb.ensure(device_id, context.current, segment, clean_old=True)

    def delete_port_precommit(self, context):
        pass

    def delete_port_postcommit(self, context):
        pass

    def try_to_bind_segment_for_agent(self, context, segment, agent):
        if segment.get(api.PHYSICAL_NETWORK) in self.physical_networks:

            LOG.info("try_to_bind_segment_for_agent")
            LOG.info(context.current)

            # We only do router devices
            device_owner = context.current.get('device_owner', None)
            device_id = context.current.get('device_id', None)

            if device_id is None or device_owner is None or not device_owner.startswith('network:router'):
                return False

            if not agent.get('admin_state_up', False) \
                    or not agent.get('alive', False) \
                    or agent['agent_type'].lower() != asr1k_constants.AGENT_TYPE_ASR1K_ML2.lower():
                return False

            agent_host = agent.get('host', None)

            # If the agent is bound to a host, then it can only handle those

            if agent_host and agent_host != context.current['binding:host_id']:
                return False

            LOG.debug("Creating extra atts for segment {}".format(segment))

            asr1k_db.ExtraAttsDb.ensure(device_id, context.current, segment, clean_old=True)

            context.set_binding(segment[api.ID],
                                self.vif_type,
                                self.vif_details)
            return True
        else:
            LOG.debug('Skipping binding, physical network on segment "{}" is not managed by this driver, '
                      'managed networks are {}'
                      ''.format(segment.get(api.PHYSICAL_NETWORK), self.physical_networks))
