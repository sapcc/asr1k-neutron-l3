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

import signal

import eventlet
import oslo_messaging
import requests
import six
import urllib3

eventlet.monkey_patch()

from oslo_log import log as logging
from oslo_log import helpers as log_helpers
from oslo_config import cfg
from oslo_utils import timeutils
from oslo_service import loopingcall
import neutron.context
from neutron.i18n import _LI, _LE
from neutron.agent import rpc as agent_rpc, securitygroups_rpc as sg_rpc
from neutron.common import config as common_config, topics, constants as n_const
from asr1k_neutron_l3.plugins.common import config
from asr1k_neutron_l3.plugins.common import asr1k_constants as constants
from asr1k_neutron_l3.models import asr1k_pair
from asr1k_neutron_l3.plugins.ml2.drivers.mech_asr1k import rpc_api
from asr1k_neutron_l3.models.neutron.l2 import port as l2_port

from requests.packages.urllib3.exceptions import InsecureRequestWarning

LOG = logging.getLogger(__name__)
CONF = cfg.CONF

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ASR1KNeutronAgent(sg_rpc.SecurityGroupAgentRpcCallbackMixin):
    target = oslo_messaging.Target(version='1.4')

    def __init__(self,
                 quitting_rpc_timeout=None,
                 conf=None):

        super(ASR1KNeutronAgent, self).__init__()
        self.conf = conf or CONF
        self.catch_sigterm = False
        self.catch_sighup = False
        self.run_daemon_loop = True
        self.polling_interval = 10
        self.iter_num = 0

        self.updated_ports = {}
        self.known_ports = {}
        self.unbound_ports = {}
        self.deleted_ports = {}
        self.added_ports = set()

        self.pool = eventlet.greenpool.GreenPool(size=10)  # Start small, so we identify possible bottlenecks

        self.agent_state = {
            'binary': 'asr1k-ml2-agent',
            'host': self.conf.host,
            'topic': n_const.L2_AGENT_TOPIC,
            'configurations': {

            },
            'agent_type': constants.AGENT_TYPE_ASR1K_ML2,
            'start_flag': True}

        self.setup_rpc()

        self.asr1k_pair = asr1k_pair.ASR1KPair(self.conf)

        report_interval = 30
        heartbeat = loopingcall.FixedIntervalLoopingCall(self._report_state)
        heartbeat.start(interval=report_interval, stop_on_exception=False)

        self.connection.consume_in_threads()

    def port_update(self, context, **kwargs):
        port = kwargs.get('port')
        port_id = port['id']
        # Avoid updating a port, which has not been created yet
        # if port_id in self.known_ports and not port_id in self.deleted_ports:
        self.updated_ports[port_id] = port
        LOG.debug("port_update message processed for port {}".format(port_id))

    def port_delete(self, context, **kwargs):
        port = kwargs.get('port')
        port_id = kwargs.get('port_id')
        self.updated_ports.pop(port_id, None)
        self.deleted_ports[port_id] = port
        LOG.debug("port_delete message processed for port {}".format(port_id))

    @log_helpers.log_method_call
    def network_create(self, context, **kwargs):
        pass

    @log_helpers.log_method_call
    def network_update(self, context, **kwargs):
        pass

    @log_helpers.log_method_call
    def network_delete(self, context, **kwargs):
        pass

    @log_helpers.log_method_call
    def setup_rpc(self):
        # RPC network init

        self.context = neutron.context.get_admin_context_without_session()
        self.agent_id = 'asr1k-ml2-agent-%s' % self.conf.host
        self.topic = topics.AGENT
        self.plugin_rpc = agent_rpc.PluginApi(topics.PLUGIN)
        self.agent_rpc = rpc_api.ASR1KPluginApi(self.context)
        self.state_rpc = agent_rpc.PluginReportStateAPI(topics.PLUGIN)

        # Handle updates from service
        self.endpoints = [self]

        # Define the listening consumers for the agent
        consumers = [[topics.PORT, topics.CREATE],
                     [topics.PORT, topics.UPDATE],
                     [topics.PORT, topics.DELETE],
                     [topics.NETWORK, topics.CREATE],
                     [topics.NETWORK, topics.UPDATE],
                     [topics.NETWORK, topics.DELETE],
                     [constants.ASR1K_TOPIC, topics.CREATE],
                     [constants.ASR1K_TOPIC, topics.UPDATE],
                     [constants.ASR1K_TOPIC, topics.DELETE]]

        self.connection = agent_rpc.create_consumers(self.endpoints,
                                                     self.topic,
                                                     consumers,
                                                     start_listening=False)

    def _report_state(self):
        try:
            with timeutils.StopWatch() as w:
                self.state_rpc.report_state(self.context, self.agent_state)
            LOG.debug("Reporting state took {:1.3g}s".format(w.elapsed()))

            self.agent_state.pop('start_flag', None)
        except (oslo_messaging.MessagingTimeout, oslo_messaging.RemoteError, oslo_messaging.MessageDeliveryFailure):
            LOG.exception(_LE("Failed reporting state!"))

    def _check_and_handle_signal(self):
        if self.catch_sigterm:
            LOG.info(_LI("Agent caught SIGTERM, quitting daemon loop."))
            self.run_daemon_loop = False
            self.catch_sigterm = False

        if self.catch_sighup:
            LOG.info(_LI("Agent caught SIGHUP, resetting."))
            self.conf.reload_config_files()
            common_config.setup_logging()
            LOG.debug('Full set of CONF:')
            self.conf.log_opt_values(LOG, logging.DEBUG)
            self.catch_sighup = False

        return self.run_daemon_loop

    def _handle_sigterm(self, signum, frame):
        self.catch_sigterm = True
        if self.quitting_rpc_timeout:
            self.set_rpc_timeout(self.quitting_rpc_timeout)

    def _handle_sighup(self, signum, frame):
        self.catch_sighup = True

    @log_helpers.log_method_call
    def process_ports(self):
        updated_ports = self.updated_ports.copy()

        # Get new ports on the VMWare integration bridge
        found_ports = self._scan_ports()

        ports_to_bind = list(port_id for port_id, port in six.iteritems(updated_ports))

        LOG.debug(ports_to_bind)

        if ports_to_bind:
            LOG.debug("Ports to bind: {}".format([port for port in ports_to_bind]))

            try:
                router_ports = self.agent_rpc.get_ports_with_extra_atts(self.context, ports_to_bind, self.agent_id,
                                                                        self.conf.host)

                l2_port.create_ports(self.asr1k_pair, router_ports, callback=self._bound_ports)
                self.updated_ports = {}
            except Exception as err:
                LOG.exception(err)

        deleted_ports = self.deleted_ports.copy()
        ports_to_delete = list(port_id for port_id, port in six.iteritems(deleted_ports))

        if ports_to_delete:
            try:
                extra_atts = self.agent_rpc.get_extra_atts(self.context, ports_to_delete, self.agent_id, self.conf.host)

                l2_port.delete_ports(self.asr1k_pair, extra_atts, callback=self._deleted_ports)
                self.deleted_ports = {}
            except Exception as err:
                LOG.exception(err)

    def _scan_ports(self):
        pass

    def _deleted_ports(self, succeeded, failed):
        self.agent_rpc.delete_extra_atts(self.context, succeeded)

    @log_helpers.log_method_call
    def _bound_ports(self, succeeded, failed):
        self.pool.spawn(self._update_device_list, succeeded, failed)

    @log_helpers.log_method_call
    def _update_device_list(self, port_up_ids, port_down_ids):
        LOG.debug("update device")
        self.plugin_rpc.update_device_list(self.context, port_up_ids, port_down_ids, self.agent_id, self.conf.host)

    def rpc_loop(self):
        while self._check_and_handle_signal():
            with timeutils.StopWatch() as w:
                self.process_ports()
            self.loop_count_and_wait(w.elapsed())

    def loop_count_and_wait(self, elapsed):
        # sleep till end of polling interval
        if elapsed < self.polling_interval:
            eventlet.sleep(self.polling_interval - elapsed)
        else:
            LOG.debug("Loop iteration exceeded interval "
                      "(%(polling_interval)s vs. %(elapsed)s)!",
                      {'polling_interval': self.polling_interval,
                       'elapsed': elapsed})
        self.iter_num += 1

    def daemon_loop(self):
        # Start everything.
        signal.signal(signal.SIGTERM, self._handle_sigterm)

        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, self._handle_sighup)

        self.rpc_loop()
        # if self.api:
        #     self.api.stop()
        if self.pool:
            self.pool.waitall()

    def _report_state(self):
        try:
            with timeutils.StopWatch() as w:
                self.state_rpc.report_state(self.context, self.agent_state)
            LOG.debug("Reporting state took {:1.3g}s".format(w.elapsed()))

            self.agent_state.pop('start_flag', None)
        except (oslo_messaging.MessagingTimeout, oslo_messaging.RemoteError, oslo_messaging.MessageDeliveryFailure):
            LOG.exception(_LE("Failed reporting state!"))


def main():
    import sys
    conf = cfg.CONF
    conf.register_opts(config.DEVICE_OPTS, "asr1k_devices")

    common_config.init(sys.argv[1:])
    common_config.setup_logging()

    agent = ASR1KNeutronAgent()

    # Start everything.
    LOG.info("Agent initialized successfully, now running... ")
    agent.daemon_loop()