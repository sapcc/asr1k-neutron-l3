# Copyright 2020 SAP SE
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
import json
import time

from ncclient.operations import RPCError
from oslo_log import log as logging

from asr1k_neutron_l3.common.exc_helper import exc_info_full
from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.models.asr1k_pair import ASR1KPair
from asr1k_neutron_l3.models.netconf_yang.access_list import AccessList
from asr1k_neutron_l3.models.netconf_yang.arp import VrfArpList
from asr1k_neutron_l3.models.netconf_yang.l2_interface import BridgeDomain, LoopbackInternalInterface, \
    LoopbackExternalInterface, ExternalInterface
from asr1k_neutron_l3.models.netconf_yang.l3_interface import VBInterface
from asr1k_neutron_l3.models.netconf_yang.nat import StaticNat, NatPool, InterfaceDynamicNat, PoolDynamicNat
from asr1k_neutron_l3.models.netconf_yang.prefix import Prefix
from asr1k_neutron_l3.models.netconf_yang.route import VrfRoute
from asr1k_neutron_l3.models.netconf_yang.route_map import RouteMap
from asr1k_neutron_l3.models.netconf_yang.vrf import VrfDefinition
from asr1k_neutron_l3.common.prometheus_monitor import PrometheusMonitor

LOG = logging.getLogger(__name__)


class OrphanEncoder(json.JSONEncoder):
    def encode(self, obj):
        if isinstance(obj, list):
            result = []
            for item in obj:
                result.append(item.orphan_info())
            return result
        else:
            return obj.orphan_info()


class DeviceCleanerMixin(object):
    ENTITIES = [
        BridgeDomain, LoopbackInternalInterface, LoopbackExternalInterface, ExternalInterface,
        StaticNat, PoolDynamicNat, InterfaceDynamicNat, NatPool,
        VBInterface,
        RouteMap, Prefix, AccessList, VrfArpList, VrfRoute, VrfDefinition
    ]

    def _get_all_router_ids(self):
        try:
            all_router_ids = self.plugin_rpc.get_all_router_ids(self.context)
        except BaseException as e:
            LOG.warning("Cleaner could not get active routers due to a server error `{}`. "
                        "Check server logs for more details. Skipping cleaning operation ".format(e.message))
            return

        if len(all_router_ids) == 0:
            LOG.warning("Cleaning was provided 0 active routers, this would trigger a clean of the whole device, "
                        "likely an uncaught error. Skipping cleaning.")
            return

        return all_router_ids

    def clean_device(self, dry_run):
        try:
            clean_start = time.time()
            prom = PrometheusMonitor()
            LOG.info("Starting a cleaning run with dry run=%s", dry_run)

            # 0. reset monitoring
            for context in ASR1KPair().contexts:
                prom.l3_orphan_count.labels(device=context.host).set(0)

            # 1. get all item names (from device)
            all_entity_stubs = []
            for entity_cls in self.ENTITIES:
                result = {}
                fetch_start = time.time()
                item_count = 0
                for context in ASR1KPair().contexts:
                    result[context] = entity_cls.get_all_stubs_from_device(context)
                    item_count += len(result[context])
                    prom.device_entity_count.labels(device=context.host, entity=entity_cls.__name__).set(item_count)
                all_entity_stubs.append((entity_cls, result))
                LOG.debug("Cleaner fetched %d %s in %.2f",
                          item_count, entity_cls.__name__, time.time() - fetch_start)
            LOG.debug("Cleaner fetched all entities from the device")

            # 2. get all info from openstack (router ids, extra atts)
            #    this information needs to be fetched after the device info,
            #    so we don't accidentally delete objects suddently required
            all_router_ids = self._get_all_router_ids()
            if not all_router_ids:
                # warning is already logged by the method
                return
            LOG.debug("Cleaner fetched all router ids")

            all_extra_atts = self.plugin_rpc.get_all_extra_atts(self.context)
            if not all_extra_atts:
                LOG.error("Failed to fetch extra atts, aborting device cleaning")
                return

            all_segmentation_ids = set()
            all_bd_ids = set()
            for rport in all_extra_atts.values():
                for attrs in rport.values():
                    all_segmentation_ids.add(attrs['segmentation_id'])
                    all_bd_ids.add(utils.to_bridge_domain(attrs['second_dot1q']))
            LOG.debug("Cleaner fetched all extra atts")

            # 3. figure out orphans and delete them
            item_count = 0
            orphan_count = 0
            orphan_deleted_count = 0
            for entity_cls, entity_stubs in all_entity_stubs:
                for context, stubs in entity_stubs.items():
                    for stub in stubs:
                        item_count += 1
                        if stub.is_orphan(all_router_ids, all_segmentation_ids, all_bd_ids, context):
                            orphan_count += 1
                            LOG.debug("%s %s on %s for router %s can be cleaned",
                                      entity_cls.__name__, stub.id, context.name, stub.neutron_router_id)
                            prom.l3_orphan_count.labels(device=context.host).inc()
                            if not dry_run:
                                try:
                                    item = stub._internal_get(context=context)
                                    if item is None:
                                        raise ValueError("Entity {} {} not present on device {}"
                                                         .format(entity_cls.__name__, stub.id, context.name))
                                    # This check is done in order to make sure the object fetched from the device in (1)
                                    # has not been reassigned after (2) to another entity with the same primary key.
                                    # Assume we find a BD-VIF ID in (1) on the device, (2) finds out it has been removed
                                    # from extra_atts. While (3) is in progress we reassign it in another thread. We would
                                    # then later delete it. Hence we check if the item from _interal_get was found with a
                                    # different attribute, i.e. VRF.
                                    if stub.is_reassigned(item):
                                        LOG.info("Entity {} {} on device {}"
                                            " has been reassigned to another router, skipping cleanup"
                                            .format(entity_cls.__name__, stub.id, context.name))
                                        continue
                                    item._delete_no_retry(context=context)
                                    orphan_deleted_count += 1
                                except RPCError as e:
                                    extra_info = e.info  # put into a varaiable so it is easier to read in sentry
                                    LOG.error("Cleaning of %s %s failed, extra info: %s",
                                              entity_cls.__name__, stub.id, extra_info,
                                              exc_info=exc_info_full())
                                except ValueError as e:
                                    LOG.warning(e)
                                except BaseException:
                                    LOG.error("Cleaning of %s %s failed", entity_cls.__name__, stub.id,
                                              exc_info=exc_info_full())

            LOG.info("Orphan deletion done in %.2fs, %d items on device, %d orphans, %d orphans deleted",
                     time.time() - clean_start, item_count, orphan_count, orphan_deleted_count)
        except BaseException:
            LOG.error("Cleaning failed with exception", exc_info=exc_info_full())
