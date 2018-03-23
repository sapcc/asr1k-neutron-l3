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

import eventlet
import requests
import urllib3
from neutron.common import eventlet_utils

eventlet_utils.monkey_patch()

import sys
import signal

from oslo_service import service
from oslo_utils import timeutils
from oslo_utils import importutils

from neutron.agent.common import config
from neutron.agent.l3 import config as l3_config
from neutron.agent.linux import interface
from neutron.agent.metadata import config as metadata_config
from neutron.common import config as common_config
from neutron import service as neutron_service

from oslo_config import cfg
from oslo_log import log as logging
from oslo_log import helpers as log_helpers

import oslo_messaging
from oslo_service import loopingcall
from oslo_service import periodic_task
from oslo_utils import excutils
from neutron._i18n import _LE, _LI, _LW
from neutron.agent.common import utils as common_utils
from neutron.agent.linux import external_process
from neutron.callbacks import events
from neutron.callbacks import registry
from neutron.callbacks import resources

from neutron.agent import rpc as agent_rpc
from neutron.common import constants as l3_constants
from neutron.common import ipv6_utils
from neutron.common import exceptions as n_exc
from neutron.common import rpc as n_rpc
from neutron.common import topics
from neutron import context as n_context
from neutron import manager

from neutron.agent.l3 import router_processing_queue as queue

from asr1k_neutron_l3.common import asr1k_constants as constants, config as asr1k_config, utils
from asr1k_neutron_l3.common import asr1k_exceptions as exc
from asr1k_neutron_l3.models.neutron.l3 import router as l3_router
from asr1k_neutron_l3.models import asr1k_pair
from asr1k_neutron_l3.models import netconf
from asr1k_neutron_l3.plugins.l3.agents import operations

from requests.packages.urllib3.exceptions import InsecureRequestWarning

try:
    from neutron_fwaas.services.firewall.agents.l3reference \
        import firewall_l3_agent
except Exception:
    # TODO(dougw) - REMOVE THIS FROM NEUTRON; during l3_agent refactor only
    from neutron.services.firewall.agents.l3reference import firewall_l3_agent

LOG = logging.getLogger(__name__)

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def register_opts(conf):
    conf.register_opts(l3_config.OPTS)
    conf.register_opts(metadata_config.DRIVER_OPTS)
    conf.register_opts(metadata_config.SHARED_OPTS)
    config.register_interface_driver_opts_helper(conf)
    config.register_agent_state_opts_helper(conf)
    conf.register_opts(interface.OPTS)
    conf.register_opts(external_process.OPTS)
    config.register_availability_zone_opts_helper(conf)


def main(manager='asr1k_neutron_l3.plugins.l3.agents.asr1k_l3_agent.L3ASRAgentWithStateReport'):
    register_opts(cfg.CONF)
    cfg.CONF.register_opts(asr1k_config.DEVICE_OPTS, "asr1k_devices")
    cfg.CONF.register_opts(asr1k_config.ASR1K_OPTS, "asr1k")
    cfg.CONF.register_opts(asr1k_config.ASR1K_L3_OPTS, "asr1k_l3")
    cfg.CONF.register_opts(asr1k_config.ASR1K_L2_OPTS, "asr1k_l2")
    common_config.init(sys.argv[1:])
    config.setup_logging()
    # set periodic interval to 10 seconds, as I understand the code this means
    # the
    server = neutron_service.Service.create(
        binary='neutron-asr1k-l3-agent',
        topic=topics.L3_AGENT,
        report_interval=cfg.CONF.AGENT.report_interval,
        periodic_interval=10,
        periodic_fuzzy_delay=10,
        manager=manager)
    service.launch(cfg.CONF, server).wait()


LOG = logging.getLogger(__name__)

# Number of routers to fetch from server at a time on resync.
# Needed to reduce load on server side and to speed up resync on agent side.

SYNC_ROUTERS_MIN_CHUNK_SIZE = 1


class L3PluginApi(object):
    """Agent side of the l3 agent RPC API.

    API version history:
        1.0 - Initial version.
        1.1 - Floating IP operational status updates
        1.2 - DVR support: new L3 plugin methods added.
              - get_ports_by_subnet
              - get_agent_gateway_port
              Needed by the agent when operating in DVR/DVR_SNAT mode
        1.3 - Get the list of activated services
        1.4 - Added L3 HA update_router_state. This method was reworked in
              to update_ha_routers_states
        1.5 - Added update_ha_routers_states
        1.6 - Added process_prefix_update
        1.7 - DVR support: new L3 plugin methods added.
              - delete_agent_gateway_port
        1.8 - Added address scope information
        1.9 - Added get_router_ids
    """

    def __init__(self, topic, host):
        self.host = host
        target = oslo_messaging.Target(topic=topic, version='1.0')
        self.client = n_rpc.get_client(target)

    @log_helpers.log_method_call
    def get_routers(self, context, router_ids=None):
        """Make a remote process call to retrieve the sync data for routers."""
        cctxt = self.client.prepare()
        return cctxt.call(context, 'sync_routers', host=self.host,
                          router_ids=router_ids)

    @log_helpers.log_method_call
    def get_router_ids(self, context):
        """Make a remote process call to retrieve scheduled routers ids."""
        cctxt = self.client.prepare(version='1.9')
        return cctxt.call(context, 'get_router_ids', host=self.host)

    @log_helpers.log_method_call
    def get_external_network_id(self, context):
        """Make a remote process call to retrieve the external network id.

        @raise oslo_messaging.RemoteError: with TooManyExternalNetworks as
                                           exc_type if there are more than one
                                           external network
        """
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_external_network_id', host=self.host)

    @log_helpers.log_method_call
    def update_floatingip_statuses(self, context, router_id, fip_statuses):
        """Call the plugin update floating IPs's operational status."""
        cctxt = self.client.prepare(version='1.1')
        return cctxt.call(context, 'update_floatingip_statuses',
                          router_id=router_id, fip_statuses=fip_statuses)

    @log_helpers.log_method_call
    def get_ports_by_subnet(self, context, subnet_id):
        """Retrieve ports by subnet id."""
        cctxt = self.client.prepare(version='1.2')
        return cctxt.call(context, 'get_ports_by_subnet', host=self.host,
                          subnet_id=subnet_id)

    @log_helpers.log_method_call
    def get_agent_gateway_port(self, context, fip_net):
        """Get or create an agent_gateway_port."""
        cctxt = self.client.prepare(version='1.2')
        return cctxt.call(context, 'get_agent_gateway_port',
                          network_id=fip_net, host=self.host)

    @log_helpers.log_method_call
    def get_service_plugin_list(self, context):
        """Make a call to get the list of activated services."""
        cctxt = self.client.prepare(version='1.3')
        return cctxt.call(context, 'get_service_plugin_list')

    @log_helpers.log_method_call
    def update_ha_routers_states(self, context, states):
        """Update HA routers states."""
        cctxt = self.client.prepare(version='1.5')
        return cctxt.call(context, 'update_ha_routers_states',
                          host=self.host, states=states)

    @log_helpers.log_method_call
    def process_prefix_update(self, context, prefix_update):
        """Process prefix update whenever prefixes get changed."""
        cctxt = self.client.prepare(version='1.6')
        return cctxt.call(context, 'process_prefix_update',
                          subnets=prefix_update)

    @log_helpers.log_method_call
    def delete_agent_gateway_port(self, context, fip_net):
        """Delete Floatingip_agent_gateway_port."""
        cctxt = self.client.prepare(version='1.7')
        return cctxt.call(context, 'delete_agent_gateway_port',
                          host=self.host, network_id=fip_net)

    def delete_extra_atts_l3(self, context, ports):
        """Delete extra atts for unused l3 ports"""
        cctxt = self.client.prepare(version='1.7')
        return cctxt.call(context, 'delete_extra_atts_l3',
                          host=self.host, ports=ports)

    def get_address_scopes(self, context, scopes):
        """Get address scopes with names """
        cctxt = self.client.prepare(version='1.7')
        return cctxt.call(context, 'get_address_scopes',
                          host=self.host, scopes=scopes)


class L3ASRAgent(firewall_l3_agent.FWaaSL3AgentRpcCallback, manager.Manager,operations.OperationsMixin):
    """Manager for L3 ASR Agent

        API version history:
        1.0 initial Version
    """
    target = oslo_messaging.Target(version='1.3')

    def __init__(self, host, conf=None):
        if conf:
            self.conf = conf
        else:
            self.conf = cfg.CONF
        self.router_info = {}

        self.process_monitor = external_process.ProcessMonitor(
            config=self.conf,
            resource_type='router')

        self.context = n_context.get_admin_context_without_session()

        self.driver = common_utils.load_interface_driver(self.conf)

        self.context = n_context.get_admin_context_without_session()
        self.plugin_rpc = L3PluginApi(topics.L3PLUGIN, host)
        self.fullsync = cfg.CONF.asr1k_l3.sync_active
        self.pause_process = False
        self.sync_routers_chunk_size = cfg.CONF.asr1k_l3.sync_chunk_size

        self.asr1k_pair = asr1k_pair.ASR1KPair()

        self._queue = queue.RouterProcessingQueue()
        self._requeue = {}

        # Get the list of service plugins from Neutron Server
        # This is the first place where we contact neutron-server on startup
        # so retry in case its not ready to respond.
        while True:
            try:
                self.neutron_service_plugins = (
                    self.plugin_rpc.get_service_plugin_list(self.context))
            except oslo_messaging.RemoteError as e:
                with excutils.save_and_reraise_exception() as ctx:
                    ctx.reraise = False
                    LOG.warning(_LW('l3-agent cannot check service plugins '
                                    'enabled at the neutron server when '
                                    'startup due to RPC error. It happens '
                                    'when the server does not support this '
                                    'RPC API. If the error is '
                                    'UnsupportedVersion you can ignore this '
                                    'warning. Detail message: %s'), e)
                self.neutron_service_plugins = None
            except oslo_messaging.MessagingTimeout as e:
                with excutils.save_and_reraise_exception() as ctx:
                    ctx.reraise = False
                    LOG.warning(_LW('l3-agent cannot contact neutron server '
                                    'to retrieve service plugins enabled. '
                                    'Check connectivity to neutron server. '
                                    'Retrying... '
                                    'Detailed message: %(msg)s.') % {'msg': e})
                    continue
            break

        self._queue = queue.RouterProcessingQueue()
        self.retry_tracker = {}

        self.target_ex_net_id = None
        self.use_ipv6 = ipv6_utils.is_enabled()

        self.monitor = self._initialize_monitor()

        super(L3ASRAgent, self).__init__(conf=self.conf)

        signal.signal(signal.SIGUSR1, self.trigger_sync)
        signal.signal(signal.SIGUSR2, self.pause_processing)




    def trigger_sync(self,signum, frame):
        LOG.info("Setup full sync based on external signal")
        self.fullsync =True

    def pause_processing(self,signum, frame):

        if self.pause_process:
            LOG.info("Resuming processing after receiving external signal")
            self.pause_process = False
        else:
            LOG.info("Pausing processing after receiving external signal")
            self.pause_process = True



    def _initialize_monitor(self):
        try:
            monitor = importutils.import_object(
                self.conf.asr1k.monitor)
            monitor.start()
            return monitor
        except ImportError as e:
            print("Error in loading monitor. Class "
                  "specified is %(class)s. Reason:%(reason)s",
                  {'class': self.conf.asr1k.monitor,
                   'reason': e})
            raise e


    @log_helpers.log_method_call
    def router_deleted(self, context, router_id):
        LOG.debug('Got router deleted notification for %s', router_id)
        update = queue.RouterUpdate(router_id,
                                    queue.PRIORITY_RPC,
                                    action=queue.DELETE_ROUTER)
        self._queue.add(update)

    @log_helpers.log_method_call
    def routers_updated(self, context, routers=[], operation=None):
        LOG.debug('Got routers updated notification :%s %s', routers, operation)
        if routers:
            for id in routers:
                update = queue.RouterUpdate(id, queue.PRIORITY_RPC)
                self._queue.add(update)

    @log_helpers.log_method_call
    def router_removed_from_agent(self, context, router):
        pass

    @log_helpers.log_method_call
    def router_added_to_agent(self, context, payload):
        pass

    @periodic_task.periodic_task(spacing=1, run_immediately=True)
    def check_devices_alive(self,context):
        LOG.debug('Checking device states')
        netconf.check_devices()

    @periodic_task.periodic_task(spacing=30, run_immediately=True)
    def periodic_sync_routers_task(self, context):
        LOG.debug("Starting fullsync periodic_sync_routers_task")

        self.process_services_sync(context)
        if not self.fullsync:
            return


        try:
            self.fetch_and_sync_all_routers(context)
        except n_exc.AbortSyncRouters:
            self.fullsync = cfg.CONF.asr1k_l3.sync_active

    @log_helpers.log_method_call
    def fetch_and_sync_all_routers(self, context):
        prev_router_ids = set(self.router_info)
        curr_router_ids = set()
        timestamp = timeutils.utcnow()

        try:
            router_ids = self.plugin_rpc.get_router_ids(context)
            # fetch routers by chunks to reduce the load on server and to
            # start router processing earlier
            for i in range(0, len(router_ids), self.sync_routers_chunk_size):
                routers = self.plugin_rpc.get_routers(
                    context, router_ids[i:i + self.sync_routers_chunk_size])
                LOG.debug('Syncing {} routers in regular sync loop'.format(len(routers)))
                for r in routers:
                    curr_router_ids.add(r['id'])
                    update = queue.RouterUpdate(
                        r['id'],
                        queue.PRIORITY_SYNC_ROUTERS_TASK,
                        router=r,
                        timestamp=timestamp)
                    self._queue.add(update)
        except oslo_messaging.MessagingTimeout:
            if self.sync_routers_chunk_size > SYNC_ROUTERS_MIN_CHUNK_SIZE:
                self.sync_routers_chunk_size = max(
                    self.sync_routers_chunk_size / 2,
                    SYNC_ROUTERS_MIN_CHUNK_SIZE)
                LOG.error(_LE('Server failed to return info for routers in '
                              'required time, decreasing chunk size to: %s'),
                          self.sync_routers_chunk_size)
            else:
                LOG.error(_LE('Server failed to return info for routers in '
                              'required time even with min chunk size: %s. '
                              'It might be under very high load or '
                              'just inoperable'),
                          self.sync_routers_chunk_size)
            raise
        except oslo_messaging.MessagingException:
            LOG.exception(_LE("Failed synchronizing routers due to RPC error"))
            raise n_exc.AbortSyncRouters()

        LOG.debug("periodic_sync_routers_task successfully completed")
        # adjust chunk size after successful sync
        if self.sync_routers_chunk_size < cfg.CONF.asr1k_l3.sync_chunk_size:
            self.sync_routers_chunk_size = min(
                self.sync_routers_chunk_size + SYNC_ROUTERS_MIN_CHUNK_SIZE,
                cfg.CONF.asr1k_l3.sync_chunk_size)


        self.fullsync = cfg.CONF.asr1k_l3.sync_active


        # Delete routers that have disappeared since the last sync
        for router_id in prev_router_ids - curr_router_ids:
            update = queue.RouterUpdate(router_id,
                                        queue.PRIORITY_SYNC_ROUTERS_TASK,
                                        timestamp=timestamp,
                                        action=queue.DELETE_ROUTER)
            self._queue.add(update)

    @periodic_task.periodic_task(spacing=60, run_immediately=True)
    def periodic_requeue_routers_task(self, context):
        LOG.debug("Requeuing failed routers")
        for update in self._requeue.values():
            LOG.debug("Adding {} to processing queue".format(update.id))
            self._queue.add(update)

        self._requeue = {}



    @log_helpers.log_method_call
    def after_start(self):
        eventlet.spawn_n(self._process_routers_loop)
        LOG.info(_LI("L3 agent started"))
        # Do the report state before we do the first full sync.
        self._report_state()


    @periodic_task.periodic_task(spacing=5, run_immediately=True)
    def periodic_refresh_address_scope_config(self, context):
        LOG.info('Refreshing address scope configuration dict')
        self.address_scopes = utils.get_address_scope_config(self.plugin_rpc, context)







    @log_helpers.log_method_call
    def agent_updated(self, context, payload):
        """Handle the agent_updated notification event."""
        self.fullsync = True
        LOG.info(_LI("agent_updated by server side %s!"), payload)

    @log_helpers.log_method_call
    def _process_router_update(self):
        if not self.pause_process:
            for rp, update in self._queue.each_update_to_next_router():
                LOG.debug("Starting router update for %s, action %s, priority %s",
                          update.id, update.action, update.priority)

                LOG.debug("Starting router update for %s", update.id)
                router = update.router
                if update.action != queue.DELETE_ROUTER and not router:
                    update.timestamp = timeutils.utcnow()
                    routers = self.plugin_rpc.get_routers(self.context, [update.id])

                    if routers:
                        router = routers[0]

                if not router:
                    removed = self._safe_router_deleted(update.id)
                    if not removed:
                        self._resync_router(update)
                        LOG.debug("Router delete failed for %s requeuing for processing", update.id)
                    else:
                        # need to update timestamp of removed router in case
                        # there are older events for the same router in the
                        # processing queue (like events from fullsync) in order to
                        # prevent deleted router re-creation
                        rp.fetched_and_processed(update.timestamp)
                        LOG.debug("Finished a router delete for %s", update.id)

                    continue

                if self._extra_atts_complete(router):
                    try:
                        router[constants.ADDRESS_SCOPE_CONFIG] = self.address_scopes
                        r = l3_router.Router(router)
                        r.update()
                        # set L3 deleted for all ports on the router that have disappeared
                        deleted_ports = utils.calculate_deleted_ports(router)
                        self.plugin_rpc.delete_extra_atts_l3(self.context, deleted_ports)

                        rp.fetched_and_processed(update.timestamp)
                        LOG.debug("Finished a router update for {}".format(update.id))
                        self.retry_tracker.pop(update.id, None)
                    except exc.Asr1kException as  e:
                        LOG.exception(e)
                        if isinstance(e,exc.ReQueueException):
                            requeue_attempts = self.retry_tracker.get(update.id,1)
                            if requeue_attempts < self.conf.asr1k_l3.max_requeue_attempts:
                                LOG.debug('Update failed, with a possibly transient error. Requeuing router {} attempt {} of {}'.format(update.id, requeue_attempts, self.conf.asr1k_l3.max_requeue_attempts))
                                self.retry_tracker[update.id] = requeue_attempts + 1
                                self._requeue_router(update)
                            else:
                                LOG.debug('Max requeing attempts reached for %s' % update.id)
                                self.retry_tracker.pop(update.id,None)
                                raise e
                        else:
                            raise e
                else:
                    self._resync_router(update)


    def _extra_atts_complete(self, router):
        extra_atts = router.get(constants.ASR1K_EXTRA_ATTS_KEY)

        return set(utils.get_router_ports(router)).issubset(extra_atts.keys())

    def _process_routers_loop(self):
        pool = eventlet.GreenPool(size=8)
        while True:
            pool.spawn_n(self._process_router_update)

    def _requeue_router(self, router_update,
                       priority=queue.PRIORITY_SYNC_ROUTERS_TASK):
        router_update.timestamp = timeutils.utcnow()
        router_update.priority = priority
        router_update.router = None  # Force the agent to resync the router

        LOG.info("Requeing router {} after recoverable error.".format(router_update.id))

        self._requeue[router_update.id] = router_update

    def _resync_router(self, router_update,
                       priority=queue.PRIORITY_SYNC_ROUTERS_TASK):
        router_update.timestamp = timeutils.utcnow()
        router_update.priority = priority
        router_update.router = None  # Force the agent to resync the router
        self._queue.add(router_update)

    def _safe_router_deleted(self, router_id):
        """Try to delete a router and return True if successful."""

        try:
            self._router_deleted(router_id)
        except Exception:
            LOG.exception(_LE('Error while deleting router %s'), router_id)
            return False
        else:
            return True

    def _router_deleted(self, router_id):

        registry.notify(resources.ROUTER, events.BEFORE_DELETE,
                        self, router=router_id)

        # l3_router.Router.purge(router_id)

        registry.notify(resources.ROUTER, events.AFTER_DELETE, self, router=router_id)


class L3ASRAgentWithStateReport(L3ASRAgent):

    def __init__(self, host, conf=None):
        super(L3ASRAgentWithStateReport, self).__init__(host=host, conf=conf)
        self.state_rpc = agent_rpc.PluginReportStateAPI(topics.REPORTS)
        self.agent_state = {
            'binary': 'asr1k-neutron-l3-agent',
            'host': host,
            'availability_zone': self.conf.AGENT.availability_zone,
            'topic': topics.L3_AGENT,
            'configurations': {
                'agent_mode': self.conf.agent_mode,
                'router_id': self.conf.router_id,
                'handle_internal_only_routers':
                    self.conf.handle_internal_only_routers,
                'external_network_bridge': self.conf.external_network_bridge,
                'gateway_external_network_id':
                    self.conf.gateway_external_network_id,
                'interface_driver': self.conf.interface_driver,
                'log_agent_heartbeats': self.conf.AGENT.log_agent_heartbeats},
            'start_flag': True,
            'agent_type': constants.AGENT_TYPE_ASR1K_L3}
        report_interval = self.conf.AGENT.report_interval


        LOG.debug(report_interval)
        if report_interval:
            self.heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            self.heartbeat.start(interval=report_interval)

    def _report_state(self):
        num_ex_gw_ports = 0
        num_interfaces = 0
        num_floating_ips = 0
        router_infos = self.router_info.values()
        num_routers = len(router_infos)
        for ri in router_infos:
            ex_gw_port = ri.get_ex_gw_port()
            if ex_gw_port:
                num_ex_gw_ports += 1
            num_interfaces += len(ri.router.get(l3_constants.INTERFACE_KEY,
                                                []))
            num_floating_ips += len(ri.router.get(l3_constants.FLOATINGIP_KEY,
                                                  []))
        configurations = self.agent_state['configurations']
        configurations['routers'] = num_routers
        configurations['ex_gw_ports'] = num_ex_gw_ports
        configurations['interfaces'] = num_interfaces
        configurations['floating_ips'] = num_floating_ips
        try:
            agent_status = self.state_rpc.report_state(self.context,
                                                       self.agent_state,
                                                       True)
            if agent_status == l3_constants.AGENT_REVIVED:
                LOG.info(_LI('Agent has just been revived. '
                             'Doing a full sync.'))
                self.fullsync = True
            self.agent_state.pop('start_flag', None)
        except AttributeError:
            # This means the server does not support report_state
            LOG.warning(_LW("Neutron server does not support state report. "
                            "State report for this agent will be disabled."))
            self.heartbeat.stop()
            return
        except Exception:
            LOG.exception(_LE("Failed reporting state!"))

    def after_start(self):
        eventlet.spawn_n(self._process_routers_loop)
        LOG.info(_LI("L3 agent started"))
        # Do the report state before we do the first full sync.
        self._report_state()

    def agent_updated(self, context, payload):
        """Handle the agent_updated notification event."""
        self.fullsync = True
        LOG.info(_LI("agent_updated by server side %s!"), payload)
