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
import re
import gc
import traceback
import signal
import eventlet
import oslo_messaging
import requests
import six
import urllib3
import time

from greenlet import greenlet

eventlet.monkey_patch()

from oslo_log import log as logging
from oslo_log import helpers as log_helpers
from oslo_config import cfg
from oslo_utils import timeutils
from oslo_utils import importutils
from oslo_service import loopingcall

from neutron_lib import context as n_context
from neutron.agent import rpc as agent_rpc, securitygroups_rpc as sg_rpc
from neutron.common import config as common_config, topics, constants as n_const

from asr1k_neutron_l3.common import prometheus_monitor
from asr1k_neutron_l3.common.prometheus_monitor import  PrometheusMonitor
from asr1k_neutron_l3.common.instrument import instrument
from asr1k_neutron_l3.common import asr1k_constants as constants
from asr1k_neutron_l3.common import config as asr1k_config
from asr1k_neutron_l3.models import asr1k_pair
from asr1k_neutron_l3.models import connection
from asr1k_neutron_l3.plugins.ml2.drivers.mech_asr1k import rpc_api
from asr1k_neutron_l3.models.neutron.l2 import port as l2_port

from requests.packages.urllib3.exceptions import InsecureRequestWarning
from asr1k_neutron_l3.common import config

LOG = logging.getLogger(__name__)
CONF = cfg.CONF

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SYNC_ROUTERS_MAX_CHUNK_SIZE = 256
SYNC_ROUTERS_MIN_CHUNK_SIZE = 32

def main():
    asr1k_config.register_l2_opts()
    agent = ASR1KNeutronAgent()

    # Start everything.
    LOG.info("Agent initialized successfully, now running... ")
    agent.daemon_loop()


class ASR1KNeutronAgent(sg_rpc.SecurityGroupAgentRpcCallbackMixin):
    target = oslo_messaging.Target(version='1.4')

    def __init__(self,
                 quitting_rpc_timeout=None,
                 conf=None):

        super(ASR1KNeutronAgent, self).__init__()
        self.conf = conf or CONF

        self.yang_connection_pool_size = cfg.CONF.asr1k_l2.yang_connection_pool_size



        connection.ConnectionPool().initialiase(yang_connection_pool_size=self.yang_connection_pool_size,max_age=cfg.CONF.asr1k.connection_max_age)

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

        self.sync_chunk_size = self.conf.asr1k_l2.sync_chunk_size
        self.sync_offset = 0
        self.sync_interval = self.conf.asr1k_l2.sync_interval
        self.sync_active = self.conf.asr1k_l2.sync_active


        self.pool = eventlet.greenpool.GreenPool(size=10)  # Start small, so we identify possible bottlenecks
        self.loop_pool = eventlet.greenpool.GreenPool(size=5)  # Start small, so we identify possible bottlenecks

        self.agent_state = {
            'binary': 'asr1k-ml2-agent',
            'host': self.conf.host,
            'topic': n_const.L2_AGENT_TOPIC,
            'configurations': {

            },
            'agent_type': constants.AGENT_TYPE_ASR1K_ML2,
            'start_flag': True}

        self.setup_rpc()

        self.asr1k_pair = asr1k_pair.ASR1KPair()

        report_interval = 30
        heartbeat = loopingcall.FixedIntervalLoopingCall(self._report_state)
        heartbeat.start(interval=report_interval, stop_on_exception=False)

        self.monitor  = self._initialize_monitor()


        self.connection.consume_in_threads()

        signal.signal(signal.SIGUSR2, self.dump_greenlets)


    def dump_greenlets(self,signum, frame):
        count=0
        total_count = 0
        for ob in gc.get_objects():
            if not isinstance(ob, greenlet):
                continue
            if not ob:
                continue

            LOG.debug(''.join(traceback.format_stack(ob.gr_frame)))
            if re.search('ncclient/transport/ssh.py', traceback.format_stack(ob.gr_frame).__str__(), re.I):

                count += 1
            total_count+=1
        LOG.debug("************* Total SSH Greenlets : {} out of {}".format(count,total_count))


    def _initialize_monitor(self):
        monitor = PrometheusMonitor(host=self.conf.host,namespace="neutron_asr1k",type=prometheus_monitor.L2)
        monitor.start()

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

        self.context = n_context.get_admin_context_without_session()
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
            LOG.exception("Failed reporting state!")

    def _check_and_handle_signal(self):
        if self.catch_sigterm:
            LOG.info("Agent caught SIGTERM, quitting daemon loop.")
            self.run_daemon_loop = False
            self.catch_sigterm = False

        if self.catch_sighup:
            LOG.info("Agent caught SIGHUP, resetting.")
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
        connection.check_devices(self.agent_rpc.get_device_info(self.conf.host))

        updated_ports = self.updated_ports.copy()


        ports_to_bind = list(port_id for port_id, port in six.iteritems(updated_ports))
        succeeded_ports = []

        LOG.debug(ports_to_bind)

        if ports_to_bind:
            LOG.debug("Ports to bind: {}".format([port for port in ports_to_bind]))

            try:
                router_ports = self.agent_rpc.get_ports_with_extra_atts(self.context, ports_to_bind, self.agent_id,
                                                                        self.conf.host)

                l2_port.create_ports(router_ports, callback=self._bound_ports)
                self.updated_ports = {}
            except BaseException as err:
                LOG.exception(err)

        deleted_ports = self.deleted_ports.copy()
        ports_to_delete = list(port_id for port_id, port in six.iteritems(deleted_ports))

        if ports_to_delete:
            try:
                extra_atts = self.agent_rpc.get_extra_atts(self.context, ports_to_delete, agent_id=self.agent_id, host=self.conf.host)



                l2_port.delete_ports(extra_atts, callback=self._deleted_ports)
                self.deleted_ports = {}
            except BaseException as err:
                LOG.exception(err)


    @instrument()
    def sync_known_ports(self):

        connection.check_devices(self.agent_rpc.get_device_info(self.conf.host))

        if self.sync_active:

            interface_ports = self.agent_rpc.get_interface_ports(limit=self.sync_chunk_size, offset=self.sync_offset,host=self.conf.host)

            LOG.debug("Syncing {} ports ".format(len(interface_ports)))

            if len(interface_ports)==0:
                self.sync_offset = 0
                interface_ports = self.agent_rpc.get_interface_ports(limit=self.sync_chunk_size, offset=self.sync_offset,host=self.conf.host)
            else:
                self.sync_offset = self.sync_offset+self.sync_chunk_size

            l2_port.update_ports(interface_ports,callback=self._bound_ports)

            LOG.debug("Syncing {} ports completed".format(len(interface_ports)))
        else:
            LOG.info("Skipping sync, disabled in config")

    @instrument()
    def scavenge(self):

        if self.sync_active:
            try:
                extra_atts = self.agent_rpc.get_orphaned_extra_atts(self.context, agent_id=self.agent_id, host=self.conf.host)
                print self.conf.host
                print "***** {}".format(extra_atts)
                l2_port.delete_ports(extra_atts, callback=self._deleted_ports)
                self.deleted_ports = {}
            except BaseException as err:
                LOG.exception(err)

    def _deleted_ports(self, succeeded, failed):
        LOG.debug("Callback to delete extra atts for {}".format(succeeded))

        self.agent_rpc.delete_extra_atts(self.context, succeeded)

    @log_helpers.log_method_call
    def _bound_ports(self, succeeded, failed):

        LOG.debug('Updating device list with succeeded {} and failed {}'.format(succeeded, failed))

        self.pool.spawn(self._update_device_list, succeeded, failed)

    @log_helpers.log_method_call
    def _update_device_list(self, port_up_ids, port_down_ids):
        self.plugin_rpc.update_device_list(self.context, port_up_ids, port_down_ids, self.agent_id, self.conf.host)

    def rpc_loop(self):

        while self._check_and_handle_signal():
            LOG.debug("**** RPC Loop")
            with timeutils.StopWatch() as w:
                try:
                    self.process_ports()
                except Exception as e:
                    LOG.exception(e)
            self.loop_count_and_wait(w.elapsed(), self.polling_interval)

    def sync_loop(self):

        while self._check_and_handle_signal():
            LOG.debug("**** SYNC Loop : known ports")
            with timeutils.StopWatch() as w:
                try:
                    self.sync_known_ports()
                except Exception as e:
                    LOG.exception(e)

            self.loop_count_and_wait(w.elapsed(), self.sync_interval)

    def scavenge_loop(self):

        while self._check_and_handle_signal():
            LOG.debug("**** SYNC Loop")
            with timeutils.StopWatch() as w:
                try:
                    self.scavenge()
                except Exception as e:
                    LOG.exception(e)
            self.loop_count_and_wait(w.elapsed(), self.sync_interval)

    def loop_count_and_wait(self, elapsed,polling_interval):
        # sleep till end of polling interval
        if elapsed < polling_interval:
            eventlet.sleep(polling_interval - elapsed)
        else:
            LOG.debug("Loop iteration exceeded interval "
                      "(%(polling_interval)s vs. %(elapsed)s)!",
                      {'polling_interval': polling_interval,
                       'elapsed': elapsed})
        self.iter_num += 1

    def _run_first(self):
        LOG.debug("Init mode active - in noop mode")
        while self._check_and_handle_signal():
            with timeutils.StopWatch() as w:
                time.sleep(5)
                self.loop_count_and_wait(w.elapsed(),60)

    def daemon_loop(self):
        # Start everything.
        signal.signal(signal.SIGTERM, self._handle_sigterm)

        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, self._handle_sighup)
        if self.conf.asr1k.init_mode:
            self.loop_pool.spawn(self._run_first)
        else:
            self.loop_pool.spawn(self.rpc_loop)
            self.loop_pool.spawn(self.sync_loop)
            self.loop_pool.spawn(self.scavenge_loop)
            # if self.api:
            #     self.api.stop()



        if self.pool:
            self.pool.waitall()

        if self.loop_pool:
            self.loop_pool.waitall()

    def _report_state(self):
        try:
            with timeutils.StopWatch() as w:
                self.state_rpc.report_state(self.context, self.agent_state)
            LOG.debug("Reporting state took {:1.3g}s".format(w.elapsed()))

            self.agent_state.pop('start_flag', None)
        except (oslo_messaging.MessagingTimeout, oslo_messaging.RemoteError, oslo_messaging.MessageDeliveryFailure):
            LOG.exception("Failed reporting state!")



