import json

import six

from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.plugins.db import asr1k_db
from asr1k_neutron_l3.models.netconf_yang.bulk_operations import BulkOperations
from asr1k_neutron_l3.models.netconf_yang.vrf import VrfDefinition
from asr1k_neutron_l3.models.netconf_yang.route import VrfRoute
from asr1k_neutron_l3.models.netconf_yang.route_map import RouteMap
from asr1k_neutron_l3.models.netconf_yang.prefix import Prefix
from asr1k_neutron_l3.models.netconf_yang.access_list import AccessList
from asr1k_neutron_l3.models.netconf_yang.nat import StaticNat,DynamicNat,NatPool,InterfaceDynamicNat,PoolDynamicNat
from asr1k_neutron_l3.models.netconf_yang.arp import ArpEntry
from asr1k_neutron_l3.models.netconf_yang.arp import VrfArpList
from asr1k_neutron_l3.models.netconf_yang.l3_interface import BDIInterface
from asr1k_neutron_l3.models.netconf_yang.l2_interface import LoopbackInternalInterface, LoopbackExternalInterface, ExternalInterface
from asr1k_neutron_l3.common.prometheus_monitor import PrometheusMonitor
from asr1k_neutron_l3.models.asr1k_pair import ASR1KPair
from oslo_log import log as logging
from ncclient.operations import RPCError


LOG = logging.getLogger(__name__)

class OrphanEncoder(json.JSONEncoder):


    def encode(self,obj):
        if isinstance(obj,list):
            result=[]
            for item in obj:
                result.append(item.orphan_info())
            return result
        else:
            return obj.orphan_info()



class DeviceCleanerMixin(object):

    L3_ENTITIES = [RouteMap, Prefix, AccessList, StaticNat,VrfArpList,PoolDynamicNat,InterfaceDynamicNat, NatPool, VrfRoute, BDIInterface,
                   VrfDefinition]
    L2_ENTITIES = [LoopbackInternalInterface, LoopbackExternalInterface, ExternalInterface]


    def clean_device(self,dry_run=True):
        try:
            LOG.info("Starting a cleaning run with dry run ={}".format(dry_run))

            result={}
            result["l3"]= self.clean_l3(dry_run=dry_run)
            result["l2"] = self.clean_l2(dry_run=dry_run)

            LOG.info("Orphan deletion results {}".format(result))

            return result
        except BaseException as e:
            LOG.error("Clean failed to complate to to exception {}".format(e))
            LOG.exception(e)



    def clean_l3(self,dry_run=True):
        LOG.info("L3 Cleaner running")
        all_router_ids = self.plugin_rpc.get_all_router_ids(self.context)

        LOG.debug("Cleaner found {} active routers from Neutron DB".format(len(all_router_ids)))

        orphans  = {}

        for context in ASR1KPair().contexts:
            device_config =  BulkOperations.get_device_config(context)

            PrometheusMonitor().l3_orphan_count.labels(device=context.host).set(0)
            ignore = 0
            entities=0
            for entity in self.L3_ENTITIES:
                items = entity.get_all_from_device_config(device_config)
                for item in items:
                    entities +=1
                    if item.neutron_router_id  and item.neutron_router_id not in all_router_ids:

                        LOG.debug("Candidate for cleaning  {} : {} does not have a known router id ".format(entity,item.neutron_router_id))

                        if(orphans.get(context) is None):
                            orphans[context] = []
                        orphans[context].append(item)
                        PrometheusMonitor().l3_orphan_count.labels(device=context.host).inc()
                    elif item.neutron_router_id is None and item.in_neutron_namespace:
                        LOG.debug("Candidate for cleaning  {} is not in neutron namespace".format(entity))


                        if(orphans.get(context) is None):
                            orphans[context] = []
                        orphans[context].append(item)
                        PrometheusMonitor().l3_orphan_count.labels(device=context.host).inc()
                    else:
                        ignore += 1

            LOG.debug("Igorning {}/{} known entities on host {}".format(ignore, entities, context.host))

        result = {}

        if dry_run:
            LOG.debug("Dry run cleaning the following items {}".format(orphans))
            for context in orphans:
                result[context.host] = json.dumps(orphans.get(context), cls=OrphanEncoder)
        else:
            LOG.debug("Cleaning the following items {}".format(orphans))

            for context, items in six.iteritems(orphans):
                for item in items:
                    LOG.debug("Cleaning on {} {}".format(context.host, item))
                    try:
                        item._delete_no_retry(context=context)

                    except RPCError as e:
                        LOG.error(e.message)
                    except BaseException as e:
                        LOG.exception(e)
                    except:
                        LOG.error("An exception accurred in the cleaning loop")

                try:
                    result[context.host] = json.dumps(items, cls=OrphanEncoder)
                    LOG.debug("Result {}".format(json.dumps(items, cls=OrphanEncoder)))
                except BaseException as e:
                    LOG.exception(e)
                except:
                    LOG.error("An exception accurred reporting result")


        LOG.info("L3 Cleaner complete")

        return result


    def clean_l2(self,dry_run=True):


        all_extra_atts = self.plugin_rpc.get_all_extra_atts(self.context)

        orphans  = {}

        for context in ASR1KPair().contexts:
            PrometheusMonitor().l3_orphan_count.labels(device=context.host).set(0)
            device_config =  BulkOperations.get_device_config(context)

            for entity in self.L2_ENTITIES:
                items = entity.get_all_from_device_config(device_config)

                filtered = self._filter_l2_interfaces(items,all_extra_atts)

                if (orphans.get(context) is None):
                    orphans[context] = []

                if isinstance(items,list):
                    orphans[context]+=filtered
                    PrometheusMonitor().l3_orphan_count.labels(device=context.host).inc(len(filtered))
                else:
                    orphans[context].append(filtered)
                    PrometheusMonitor().l3_orphan_count.labels(device=context.host).inc()


        result = {}
        if dry_run:
            for context in orphans:
                items = orphans.get(context)
                if bool(items):
                    result[context.host] = json.dumps(items, cls=OrphanEncoder)
        else:
            for context, items in six.iteritems(orphans):
                items = orphans.get(context)
                if bool(items):
                    for item in items:
                        LOG.debug("Cleaning {}".format(item))
                        try:
                            item.delete(context=context)
                        except BaseException as e:
                            LOG.exception(e)

                    result[context.host] = json.dumps(items,cls=OrphanEncoder)

        return result


    def _filter_l2_interfaces(self,interfaces,all_extra_atts):
        results = []


        all_service_instances = []
        all_segmentation_ids = []
        all_ports = []

        for router_ports in all_extra_atts.values():
            for port_id,atts in six.iteritems(router_ports):
                all_service_instances.append(utils.to_bridge_domain(atts.get('second_dot1q')))
                all_segmentation_ids.append(atts.get('segmentation_id'))
                all_ports.append(port_id)
        all_service_instances = list(set(all_service_instances))
        all_segmentation_ids = list(set(all_segmentation_ids))

        for interface in interfaces:
            no_match_service_instance = False
            no_match_segmentation_id = False

            if interface.description is not None and interface.description.startswith("Port : "):

                interface_port =  interface.description[7:]

                if interface_port not in all_ports:
                    results.append(interface)
                    continue

            if isinstance(interface,LoopbackInternalInterface) or isinstance(interface,LoopbackExternalInterface):
                no_match_service_instance = int(interface.id) >= utils.to_bridge_domain(asr1k_db.MIN_SECOND_DOT1Q) and  int(interface.id) <= utils.to_bridge_domain(asr1k_db.MAX_SECOND_DOT1Q) and int(interface.id) not in all_service_instances
            elif isinstance(interface,ExternalInterface):
                no_match_segmentation_id = int(interface.id) >= asr1k_db.MIN_DOT1Q and  int(interface.id) <= asr1k_db.MAX_DOT1Q and int(interface.id) not in all_segmentation_ids

            if no_match_segmentation_id or no_match_service_instance:
                results.append(interface)

        return results
