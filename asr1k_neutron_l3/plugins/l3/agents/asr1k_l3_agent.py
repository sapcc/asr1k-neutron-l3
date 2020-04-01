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
import os

if not os.environ.get('DISABLE_EVENTLET_PATCHING'):
    import eventlet
    eventlet.monkey_patch()

import datetime
import time
import eventlet
import requests
import urllib3
import re

import gc
import traceback
from greenlet import greenlet

import sys
import signal

from oslo_service import service
from oslo_utils import timeutils

from neutron import service as neutron_service

from oslo_config import cfg
from oslo_log import log as logging
from oslo_log import helpers as log_helpers
from asr1k_neutron_l3.common import asr1k_constants as constants, utils

import oslo_messaging
from oslo_service import loopingcall
from oslo_service import periodic_task
from neutron.agent.linux import external_process
from neutron_lib.callbacks import events
from neutron_lib.callbacks import registry
from neutron_lib.callbacks import resources

from neutron.agent import rpc as agent_rpc
from neutron.common import exceptions as n_exc
from neutron.common import rpc as n_rpc
from neutron.common import topics
from neutron.common import config as common_config
from neutron_lib import context as n_context
from neutron_lib import constants as lib_constants
from neutron_lib.agent import constants as agent_consts
from neutron import manager

from neutron.agent.common import resource_processing_queue as queue

from asr1k_neutron_l3.plugins.l3.agents import router_processing_queue as asr1k_queue
from asr1k_neutron_l3.common.exc_helper import exc_info_full
from asr1k_neutron_l3.common import prometheus_monitor
from asr1k_neutron_l3.common.prometheus_monitor import PrometheusMonitor
from asr1k_neutron_l3.common import asr1k_exceptions as exc
from asr1k_neutron_l3.common.instrument import instrument
from asr1k_neutron_l3.common import config as asr1k_config
from asr1k_neutron_l3.models.netconf_yang.copy_config import CopyConfig
from asr1k_neutron_l3.models.neutron.l3 import router as l3_router
from asr1k_neutron_l3.models import asr1k_pair
from asr1k_neutron_l3.models import connection
from asr1k_neutron_l3.plugins.l3.agents import operations
from asr1k_neutron_l3.plugins.l3.agents.device_cleaner import DeviceCleanerMixin

# try:
#     from neutron_fwaas.services.firewall.agents.l3reference \
#         import firewall_l3_agent
# except Exception:
#     # TODO(dougw) - REMOVE THIS FROM NEUTRON; during l3_agent refactor only
#     from neutron.services.firewall.agents.l3reference import firewall_l3_agent

LOG = logging.getLogger(__name__)

requests.packages.urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main(manager='asr1k_neutron_l3.plugins.l3.agents.asr1k_l3_agent.L3ASRAgentWithStateReport'):
    asr1k_config.register_l3_opts()
    common_config.init(sys.argv[1:])
    common_config.setup_logging()
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

    @instrument()
    def get_routers(self, context, router_ids=None):
        """Make a remote process call to retrieve the sync data for routers."""
        cctxt = self.client.prepare()
        return cctxt.call(context, 'sync_routers', host=self.host,
                          router_ids=router_ids)

    @instrument()
    def get_deleted_router(self, context, router_id):
        """Make a remote process call to retrieve the deleted router data."""
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_deleted_router', host=self.host,
                          router_id=router_id)

    @instrument()
    def delete_extra_atts_orphans(self, context, router_ids=None):
        """Make a remote process call to retrieve the orphans in extra atts table."""
        cctxt = self.client.prepare()
        return cctxt.call(context, 'delete_extra_atts_orphans', host=self.host)

    @instrument()
    def delete_router_atts_orphans(self, context):
        """Make a remote process call to retrieve the orphans in extra atts table."""
        cctxt = self.client.prepare()
        return cctxt.call(context, 'delete_router_atts_orphans', host=self.host)

    @instrument()
    def get_all_extra_atts(self, context):
        """Make a remote process call to retrieve the orphans in extra atts table."""
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_extra_atts', host=self.host)

    @instrument()
    def get_router_ids(self, context):
        """Make a remote process call to retrieve scheduled routers ids."""
        cctxt = self.client.prepare(version='1.9')
        return cctxt.call(context, 'get_router_ids', host=self.host)

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

    def get_ports_by_subnet(self, context, subnet_id):
        """Retrieve ports by subnet id."""
        cctxt = self.client.prepare(version='1.2')
        return cctxt.call(context, 'get_ports_by_subnet', host=self.host,
                          subnet_id=subnet_id)

    def get_agent_gateway_port(self, context, fip_net):
        """Get or create an agent_gateway_port."""
        cctxt = self.client.prepare(version='1.2')
        return cctxt.call(context, 'get_agent_gateway_port',
                          network_id=fip_net, host=self.host)

    def get_service_plugin_list(self, context):
        """Make a call to get the list of activated services."""
        cctxt = self.client.prepare(version='1.3')
        return cctxt.call(context, 'get_service_plugin_list')

    def process_prefix_update(self, context, prefix_update):
        """Process prefix update whenever prefixes get changed."""
        cctxt = self.client.prepare(version='1.6')
        return cctxt.call(context, 'process_prefix_update',
                          subnets=prefix_update)

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

    @instrument()
    def get_deleted_router_atts(self, context):
        """Make a remote process call to retrieve the orphans in extra atts table."""
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_deleted_router_atts', host=self.host)

    def delete_router_atts(self, context, router_ids):
        """Delete extra atts for unused l3 ports"""
        cctxt = self.client.prepare(version='1.7')
        return cctxt.call(context, 'delete_router_atts',
                          host=self.host, router_ids=router_ids)

    def get_address_scopes(self, context, scopes):
        """Get address scopes with names """
        cctxt = self.client.prepare(version='1.7')
        return cctxt.call(context, 'get_address_scopes',
                          host=self.host, scopes=scopes)

    def update_router_status(self, context, router_id, status):
        cctxt = self.client.prepare(version='1.7')
        return cctxt.call(context, 'update_router_status',
                          host=self.host, router_id=router_id, status=status)

    def ensure_snat_mode(self, context, port_id, mode):
        cctxt = self.client.prepare(version='1.7')
        return cctxt.call(context, 'ensure_snat_mode', port_id=port_id, mode=mode)

    def get_device_info(self, context):
        cctxt = self.client.prepare(version='1.7')
        return cctxt.call(context, 'get_device_info', host=self.host)

    def get_usage_stats(self, context):
        cctxt = self.client.prepare(version='1.7')
        return cctxt.call(context, 'get_usage_stats', host=self.host)

    @instrument()
    def get_all_router_ids(self, context):
        """Make a remote process call to retrieve the orphans in extra atts table."""
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_all_router_ids', host=self.host)


class L3ASRAgent(manager.Manager, operations.OperationsMixin, DeviceCleanerMixin):
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

        self.yang_connection_pool_size = cfg.CONF.asr1k_l3.yang_connection_pool_size

        if not cfg.CONF.asr1k.init_mode:
            LOG.debug("Preparing connection pool  yang : {} max age : {}"
                      "".format(self.yang_connection_pool_size, cfg.CONF.asr1k.connection_max_age))
            connection.ConnectionPool().initialise(yang_connection_pool_size=self.yang_connection_pool_size,
                                                   max_age=cfg.CONF.asr1k.connection_max_age)
            LOG.debug("Connection pool initialized")

        self.router_info = {}
        self.host = host
        self.process_monitor = external_process.ProcessMonitor(
            config=self.conf,
            resource_type='router')

        self.context = n_context.get_admin_context_without_session()
        self.plugin_rpc = L3PluginApi(topics.L3PLUGIN, host)
        self.fullsync = cfg.CONF.asr1k_l3.sync_active
        self.pause_process = False
        self.sync_routers_chunk_size = cfg.CONF.asr1k_l3.sync_chunk_size
        self.sync_until_queue_size = cfg.CONF.asr1k_l3.sync_until_queue_size

        self.asr1k_pair = asr1k_pair.ASR1KPair()

        self._queue = asr1k_queue.RouterProcessingQueue()
        self._requeue = {}
        self._last_full_sync = timeutils.now()
        self._router_sync_marker = None
        self._last_config_save = None
        self.retry_tracker = {}
        self._deleted_routers = {}

        # Get the list of service plugins from Neutron Server
        # This is the first place where we contact neutron-server on startup
        # so retry in case its not ready to respond.
        # while True:
        #     try:
        #         self.neutron_service_plugins = (
        #             self.plugin_rpc.get_service_plugin_list(self.context))
        #     except oslo_messaging.RemoteError as e:
        #         with excutils.save_and_reraise_exception() as ctx:
        #             ctx.reraise = False
        #             LOG.warning('l3-agent cannot check service plugins '
        #                             'enabled at the neutron server when '
        #                             'startup due to RPC error. It happens '
        #                             'when the server does not support this '
        #                             'RPC API. If the error is '
        #                             'UnsupportedVersion you can ignore this '
        #                             'warning. Detail message: %s', e)
        #         self.neutron_service_plugins = None
        #     except oslo_messaging.MessagingTimeout as e:
        #         with excutils.save_and_reraise_exception() as ctx:
        #             ctx.reraise = False
        #             LOG.warning('l3-agent cannot contact neutron server '
        #                             'to retrieve service plugins enabled. '
        #                             'Check connectivity to neutron server. '
        #                             'Retrying... '
        #                             'Detailed message: %(msg)s.' % {'msg': e})
        #             continue
        #     break
        self.monitor = self._initialize_monitor()

        super(L3ASRAgent, self).__init__()

        signal.signal(signal.SIGUSR1, self.trigger_sync)
        signal.signal(signal.SIGUSR2, self.dump_greenlets)

    @log_helpers.log_method_call
    def after_start(self):
        if cfg.CONF.asr1k.init_mode:
            LOG.info("Init mode is activated")
            eventlet.spawn_n(self._init_noop)
        else:
            self.periodic_refresh_address_scope_config(self.context)

            if cfg.CONF.asr1k_l3.sync_active and cfg.CONF.asr1k_l3.sync_interval > 0:
                self.sync_loop = loopingcall.FixedIntervalLoopingCall(self._periodic_sync_routers_task)
                self.sync_loop.start(interval=cfg.CONF.asr1k_l3.sync_interval, stop_on_exception=False)

                self.scavenge_loop = loopingcall.FixedIntervalLoopingCall(self._periodic_scavenge_task)
                self.scavenge_loop.start(interval=cfg.CONF.asr1k_l3.sync_interval, stop_on_exception=False)

            self.device_check_loop = loopingcall.FixedIntervalLoopingCall(self._check_devices_alive, self.context)
            self.device_check_loop.start(interval=cfg.CONF.asr1k_l3.sync_interval / 2, stop_on_exception=False)

            if cfg.CONF.asr1k.clean_orphans:
                LOG.info("Orphan clean is active, starting cleaning loop")
                self.orphan_loop = loopingcall.FixedIntervalLoopingCall(self.clean_device, dry_run=False)
                self.orphan_loop.start(interval=cfg.CONF.asr1k.clean_orphan_interval, stop_on_exception=False)

            self.clean_deleted_routers_dict_loop = loopingcall.FixedIntervalLoopingCall(
                self._clean_deleted_routers_dict)
            self.clean_deleted_routers_dict_loop.start(interval=3600, stop_on_exception=False)

            eventlet.spawn_n(self._process_routers_loop)

            LOG.info("L3 agent started")

    def trigger_sync(self, signum, frame):
        LOG.info("Setup full sync based on external signal")
        self.fullsync = True

    def dump_greenlets(self, signum, frame):
        count = 0
        total_count = 0
        for ob in gc.get_objects():
            if not isinstance(ob, greenlet):
                continue
            if not ob:
                continue

            LOG.debug(''.join(traceback.format_stack(ob.gr_frame)))
            if re.search('ncclient/transport/ssh.py', traceback.format_stack(ob.gr_frame).__str__(), re.I):

                count += 1
            total_count += 1
        LOG.debug("************* Total SSH Greenlets : {} out of {}".format(count, total_count))

    def _initialize_monitor(self):
        monitor = PrometheusMonitor(host=self.host, namespace="neutron_asr1k", type=prometheus_monitor.L3)
        monitor.start()
        return monitor

    def router_deleted(self, context, router_id):
        self._deleted_routers[router_id] = datetime.datetime.now()
        LOG.debug('************** Got router deleted notification for %s', router_id)
        update = queue.ResourceUpdate(router_id,
                                      queue.PRIORITY_RPC,
                                      action=queue.DELETE_ROUTER)
        self._queue.add(update)

    def routers_updated(self, context, routers=[], operation=None):
        LOG.debug('************** Got routers updated notification :%s %s', routers, operation)
        if routers:
            for id in routers:
                # make sure router is not marked as deleted if it was previously already scheduled on this device
                self._deleted_routers.pop(id, None)

                update = queue.ResourceUpdate(id, queue.PRIORITY_RPC)
                self._queue.add(update)

    def router_removed_from_agent(self, context, payload):
        LOG.debug('Got router removed from agent :%r', payload)
        router_id = payload['router_id']
        update = queue.ResourceUpdate(router_id,
                                      queue.PRIORITY_RPC,
                                      action=queue.DELETE_ROUTER)
        self._queue.add(update)

    def router_added_to_agent(self, context, payload):
        LOG.debug('Got router added to agent :%r', payload)
        self.routers_updated(context, payload)

    def _check_devices_alive(self, context):
        device_info = self.plugin_rpc.get_device_info(context)
        connection.check_devices(device_info)

    def _periodic_scavenge_task(self):
        try:
            LOG.debug('Starting to scavenge orphans from extra atts')
            self.plugin_rpc.delete_extra_atts_orphans(self.context)
            LOG.debug('Starting to scavenge orphans from router atts')
            self.plugin_rpc.delete_router_atts_orphans(self.context)
        except Exception as e:
            LOG.exception(e)

    def _clean_deleted_routers_dict(self):
        for router_id, created_at in list(self._deleted_routers.items()):
            if (datetime.datetime.now() - created_at).total_seconds() > 3600:
                self._deleted_routers.pop(router_id, None)

    def _periodic_sync_routers_task(self):
        try:
            LOG.debug("Starting partial sync, last partial sync started {} seconds ago"
                      "".format(int(timeutils.now() - self._last_full_sync)))

            all_stats = self.plugin_rpc.get_usage_stats(self.context)
            for status in all_stats.keys():
                stats = all_stats.get(status, {})
                PrometheusMonitor().routers.labels(status=status).set(stats.get('routers', 0))
                PrometheusMonitor().interfaces.labels(status=status).set(stats.get('interface_ports', 0))
                PrometheusMonitor().gateways.labels(status=status).set(stats.get('gateway_ports', 0))
                PrometheusMonitor().floating_ips.labels(status=status).set(stats.get('floating_ips', 0))

            if not self.fullsync:
                return

            self._last_full_sync = timeutils.now()
            self.fetch_and_sync_routers_partial(self.context)
        except Exception as e:
            LOG.error("Error in periodic sync: %s", e, exc_info=exc_info_full())
            self.fullsync = cfg.CONF.asr1k_l3.sync_active

    def _save_config(self, force_save=False):
        if cfg.CONF.asr1k.save_config or force_save:
            LOG.info("Saving running device config to startup config")
            start = time.time()
            rpc = CopyConfig()
            result = rpc.copy_config()

            if not result.success:
                LOG.error("Copy config failed, results : {} ".format(result))
            else:
                LOG.info("Saved running device config to startup config in {}s".format(time.time() - start))
                self._last_config_save = timeutils.utcnow()
        else:
            LOG.info("Saving running device config disabled in ASR1K config")

    @instrument()
    def fetch_and_sync_routers_partial(self, context):
        router_updates = 0
        router_deletes = 0
        sync_start_ts = timeutils.utcnow()

        # save config once every syncloop or on a timeout basis
        last_save_sec = (timeutils.utcnow() - self._last_config_save).total_seconds() if self._last_config_save else -1
        if not self._last_config_save or last_save_sec >= cfg.CONF.asr1k_l3.max_config_save_interval or \
                not self._router_sync_marker:
            self._save_config()

        LOG.debug("Starting partial router sync loop at sync marker %s", self._router_sync_marker)
        try:
            # fetch router ids, start with the router after the last one we already synced
            router_ids = sorted(self.plugin_rpc.get_router_ids(context))
            if self._router_sync_marker and router_ids and self._router_sync_marker < router_ids[-1]:
                while router_ids[0] <= self._router_sync_marker:
                    router_ids.pop(0)

            # fetch routers by chunks to reduce the load on server and to
            # start router processing earlier
            for i in range(0, len(router_ids), self.sync_routers_chunk_size):
                routers = self.plugin_rpc.get_routers(
                    context, router_ids[i:i + self.sync_routers_chunk_size])
                LOG.debug('Fetching {} routers in regular sync loop'.format(len(routers)))
                for r in routers:
                    update = queue.ResourceUpdate(
                        r['id'],
                        queue.PRIORITY_SYNC_ROUTERS_TASK,
                        action=queue.ADD_UPDATE_ROUTER,
                        resource=r,
                        timestamp=sync_start_ts)
                    self._queue.add(update)
                    router_updates += 1
                    self._router_sync_marker = r['id']
                    if router_updates >= self.sync_routers_chunk_size and \
                            self._queue.get_size() >= self.sync_until_queue_size:
                        break
                if router_updates >= self.sync_routers_chunk_size and \
                        self._queue.get_size() >= self.sync_until_queue_size:
                    break

            if not router_ids or self._router_sync_marker == router_ids[-1]:
                LOG.debug("Finished a complete round of queueing router updates with last router %s",
                          self._router_sync_marker)
                self._router_sync_marker = None
        except oslo_messaging.MessagingTimeout:
            if self.sync_routers_chunk_size > SYNC_ROUTERS_MIN_CHUNK_SIZE:
                self.sync_routers_chunk_size = max(
                    self.sync_routers_chunk_size / 2,
                    SYNC_ROUTERS_MIN_CHUNK_SIZE)
                LOG.error('Server failed to return info for routers in '
                          'required time, decreasing chunk size to: %s',
                          self.sync_routers_chunk_size)
            else:
                LOG.error('Server failed to return info for routers in '
                          'required time even with min chunk size: %s. '
                          'It might be under very high load or '
                          'just inoperable',
                          self.sync_routers_chunk_size)
            raise
        except oslo_messaging.MessagingException:
            LOG.exception("Failed synchronizing routers due to RPC error")
            raise n_exc.AbortSyncRouters()

        # adjust chunk size after successful sync
        if self.sync_routers_chunk_size < cfg.CONF.asr1k_l3.sync_chunk_size:
            self.sync_routers_chunk_size = min(
                self.sync_routers_chunk_size + SYNC_ROUTERS_MIN_CHUNK_SIZE,
                cfg.CONF.asr1k_l3.sync_chunk_size)

        # handle router deletion
        deleted_atts = self.plugin_rpc.get_deleted_router_atts(context)
        for atts in deleted_atts:
            router_id = atts.get("router_id")
            update = queue.ResourceUpdate(router_id,
                                          queue.PRIORITY_SYNC_ROUTERS_TASK,
                                          timestamp=sync_start_ts,
                                          action=queue.DELETE_ROUTER)
            self._queue.add(update)
            router_deletes += 1

        LOG.debug("periodic_sync_routers_task successfully queued %d router actions (%d update, %d delete)",
                  router_updates + router_deletes, router_updates, router_deletes)

        self.fullsync = cfg.CONF.asr1k_l3.sync_active

    @periodic_task.periodic_task(spacing=60, run_immediately=True)
    def periodic_requeue_routers_task(self, context):
        for update in self._requeue.values():
            LOG.debug("Adding requeued router {} to processing queue".format(update.id))
            self._queue.add(update)

        self._requeue = {}

    @periodic_task.periodic_task(spacing=5, run_immediately=False)
    def periodic_refresh_address_scope_config(self, context):
        self.address_scopes = utils.get_address_scope_config(self.plugin_rpc, context)

    def agent_updated(self, context, payload):
        """Handle the agent_updated notification event."""
        self.fullsync = True
        LOG.info("Agent updated by server with payload : %s!", payload)

    def _ensure_snat_mode_config(self, update):
        router = update.resource

        if update.action != queue.DELETE_ROUTER and not router:
            update.timestamp = timeutils.utcnow()

            routers = self.plugin_rpc.get_routers(self.context, [update.id])
            if routers:
                router = routers[0]

        updated = False

        if router is not None:
            gw_info = router.get('external_gateway_info')
            if bool(gw_info):
                fixed_ips = gw_info.get('external_fixed_ips')
                if cfg.CONF.asr1k_l3.snat_mode == constants.SNAT_MODE_POOL and len(fixed_ips) == 1:
                    self.plugin_rpc.ensure_snat_mode(self.context, router.get('gw_port_id'),
                                                     cfg.CONF.asr1k_l3.snat_mode)
                    updated = True
                elif cfg.CONF.asr1k_l3.snat_mode == constants.SNAT_MODE_INTERFACE and len(fixed_ips) == 2:
                    self.plugin_rpc.ensure_snat_mode(self.context, router.get('gw_port_id'),
                                                     cfg.CONF.asr1k_l3.snat_mode)
                    updated = True

        if updated:
            routers = self.plugin_rpc.get_routers(self.context, [update.id])
            if routers:
                router = routers[0]

        return router

    @instrument()
    def _process_router_update(self):
        try:
            if not self.pause_process:
                for rp, update in self._queue.each_update_to_next_router():
                    if update.action != queue.DELETE_ROUTER and update.id in self._deleted_routers:
                        LOG.debug("Ignoring update request for already deleted router %s", update.id)
                        continue

                    router = self._ensure_snat_mode_config(update)

                    if not router:
                        self._safe_router_deleted(update.id)
                        # need to update timestamp of removed router in case
                        # there are older events for the same router in the
                        # processing queue (like events from fullsync) in order to
                        # prevent deleted router re-creation
                        rp.fetched_and_processed(update.timestamp)
                        continue

                    if self._extra_atts_complete(router):
                        try:
                            router[constants.ADDRESS_SCOPE_CONFIG] = self.address_scopes
                            r = l3_router.Router(router)
                            result = r.update()
                            self.process_update_result(r, result)

                            # set L3 deleted for all ports on the router that have disappeared
                            deleted_ports = utils.calculate_deleted_ports(router)
                            if len(deleted_ports) > 0:
                                self.plugin_rpc.delete_extra_atts_l3(self.context, deleted_ports)

                            rp.fetched_and_processed(update.timestamp)

                            self.retry_tracker.pop(update.id, None)
                        except exc.Asr1kException as e:
                            LOG.exception(e)
                            if isinstance(e, exc.ReQueueException):
                                requeue_attempts = self.retry_tracker.get(update.id, 1)
                                if requeue_attempts < self.conf.asr1k_l3.max_requeue_attempts:
                                    LOG.debug('Update failed, with a possibly transient error. '
                                              'Requeuing router {} attempt {} of {}'
                                              ''.format(update.id, requeue_attempts,
                                                        self.conf.asr1k_l3.max_requeue_attempts))
                                    self.retry_tracker[update.id] = requeue_attempts + 1
                                    self._requeue_router(update)
                                else:
                                    LOG.debug('Max requeing attempts reached for %s' % update.id)
                                    self.retry_tracker.pop(update.id, None)
                                    raise e
                            else:

                                raise e
                        except BaseException as e:
                            LOG.exception(e)
                    else:
                        if len(utils.get_router_ports(router)) > 0:
                            LOG.debug("Requeuing update for router {}".format(update.id))
                            self._resync_router(update)
                        else:
                            LOG.info("Router {} has no ports and no extra atts, supressing requeue".format(update.id))
        except Exception as e:
            LOG.exception(e)

    def process_update_result(self, router, results):
        success = True
        duration = 0
        if results is not None:
            for result in results:
                success = success and result.success
                duration += result.duration

        LOG.debug("Update of {} {} in {:10.3f}s"
                  "".format(router.router_id, "succeeded" if success else "failed", duration))

        current_status = router.status

        # Callback to set router state based on update result
        if not success and current_status != lib_constants.ERROR:
            LOG.debug("Router has new status of ERROR, callback to update DB")
            self.plugin_rpc.update_router_status(self.context, router.router_id, lib_constants.ERROR)
        elif success and current_status != lib_constants.ACTIVE:
            LOG.debug("Router has new status of ACTIVE, callback to update DB")
            self.plugin_rpc.update_router_status(self.context, router.router_id, lib_constants.ACTIVE)

    def _extra_atts_complete(self, router):
        extra_atts = router.get(constants.ASR1K_EXTRA_ATTS_KEY)

        complete = False

        if extra_atts is not None and extra_atts.keys() is not None:
            complete = set(utils.get_router_ports(router)).issubset(extra_atts.keys())

        return complete

    def _process_routers_loop(self):
        poolsize = min(self.conf.asr1k_l3.threadpool_maxsize, self.yang_connection_pool_size, constants.MAX_CONNECTIONS)

        if poolsize < self.conf.asr1k_l3.threadpool_maxsize:
            LOG.warning("The processing thread pool size has been reduced to match 'yang_connection_pool_size' "
                        "its now {}".format(poolsize))

        pool = eventlet.GreenPool(size=poolsize)
        while True:
            pool.spawn_n(self._process_router_update)

    def _requeue_router(self, router_update,
                        priority=queue.PRIORITY_SYNC_ROUTERS_TASK):
        router_update.timestamp = timeutils.utcnow()
        router_update.priority = priority
        router_update.resource = None  # Force the agent to resync the router

        LOG.info("Requeing router {} after potentially recoverable error.".format(router_update.id))

        self._requeue[router_update.id] = router_update

    def _resync_router(self, router_update,
                       priority=queue.PRIORITY_SYNC_ROUTERS_TASK):
        router_update.timestamp = timeutils.utcnow()
        router_update.priority = priority
        router_update.resource = None  # Force the agent to resync the router
        self._queue.add(router_update)

    def _safe_router_deleted(self, router_id):
        """Try to delete a router and return True if successful."""

        registry.notify(resources.ROUTER, events.BEFORE_DELETE,
                        self, router=router_id)

        LOG.debug('Got router deleted notification for %s', router_id)
        router = self.plugin_rpc.get_deleted_router(self.context, router_id)
        if not router:
            LOG.info("Delete of router %s was probably not for %s (no data found in neutron deleted router cache)",
                     router_id, self.host)
            return True

        result = l3_router.Router(router).delete()

        return self._check_delete_result(router, result)

    def _check_delete_result(self, router, result):

        success = self.check_success(result)
        if success:
            LOG.debug("Successfully deleted router %s", router['id'])
            deleted_ports = utils.calculate_deleted_ports(router)
            if len(deleted_ports) > 0:
                LOG.debug("Requesting delete for port extra atts router %s ports %s", router['id'], deleted_ports)
                self.plugin_rpc.delete_extra_atts_l3(self.context, deleted_ports)

            if self._clean(router):
                LOG.debug("Router %s clean, requesting delete for router extra atts", router['id'])
                self.plugin_rpc.delete_router_atts(self.context, [router.get('id')])
            registry.notify(resources.ROUTER, events.AFTER_DELETE, self, router=router.get('id'))
        else:
            LOG.warning("Failed to clean up router %s on device, its been left to the scanvenger", router['id'])

        return success

    def _clean(self, router):
        router_att = router.get(constants.ASR1K_ROUTER_ATTS_KEY, {})
        deleted_at = router_att.get("deleted_at", None)

        if deleted_at is None:
            return True
        else:
            if timeutils.is_older_than(timeutils.parse_isotime(deleted_at), cfg.CONF.asr1k_l3.clean_delta):
                LOG.info("Found deleted extra att entry for router {} older than {} seconds. "
                         "A device cleanup will be attempted before deletion"
                         "".format(router.get('id'), cfg.CONF.asr1k_l3.clean_delta))
                result = l3_router.Router(router).delete()
                return self.check_success(result)
        return False

    def check_success(self, results):
        return results is not None and all(result.success for result in results)

    def _init_noop(self):
        LOG.debug("Init mode active - in noop mode")
        pool = eventlet.GreenPool(size=1)
        while True:
            pool.spawn_n(self._agent_init)

    def _agent_init(self):
        if not self.init_complete:
            time.sleep(5)


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
                'log_agent_heartbeats': self.conf.AGENT.log_agent_heartbeats},
            'start_flag': True,
            'agent_type': constants.AGENT_TYPE_ASR1K_L3}
        report_interval = self.conf.AGENT.report_interval

        if report_interval:
            self.heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            self.heartbeat.start(interval=report_interval, stop_on_exception=False)

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
            num_interfaces += len(ri.router.get(lib_constants.INTERFACE_KEY,
                                                []))
            num_floating_ips += len(ri.router.get(lib_constants.FLOATINGIP_KEY,
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
            if agent_status == agent_consts.AGENT_REVIVED:
                LOG.info('Agent has just been revived. '
                         'Doing a full sync.')
                self.fullsync = True
            self.agent_state.pop('start_flag', None)
        except AttributeError:
            # This means the server does not support report_state
            LOG.warning("Neutron server does not support state report. "
                        "State report for this agent will be disabled.")
            self.heartbeat.stop()
            return
        except Exception:
            LOG.exception("Failed reporting state!")

    def after_start(self):
        # Do the report state before we do the first full sync.
        self._report_state()
        super(L3ASRAgentWithStateReport, self).after_start()

    def agent_updated(self, context, payload):
        """Handle the agent_updated notification event."""
        self.fullsync = True
        LOG.info("agent_updated by server side %s!", payload)
