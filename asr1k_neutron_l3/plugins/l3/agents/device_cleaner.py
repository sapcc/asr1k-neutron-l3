import json

from asr1k_neutron_l3.plugins.db import asr1k_db
from asr1k_neutron_l3.models.netconf_yang.bulk_operations import BulkOperations
from asr1k_neutron_l3.models.netconf_yang.vrf import VrfDefinition
from asr1k_neutron_l3.models.netconf_yang.route import VrfRoute
from asr1k_neutron_l3.models.netconf_yang.route_map import RouteMap
from asr1k_neutron_l3.models.netconf_yang.prefix import Prefix
from asr1k_neutron_l3.models.netconf_yang.access_list import AccessList
from asr1k_neutron_l3.models.netconf_yang.nat import StaticNat,DynamicNat,NatPool
from asr1k_neutron_l3.models.netconf_yang.l3_interface import BDIInterface
from asr1k_neutron_l3.models.netconf_yang.l2_interface import LoopbackInternalInterface, LoopbackExternalInterface, ExternalInterface

from asr1k_neutron_l3.models.asr1k_pair import ASR1KPair


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

    L3_ENTITIES = [RouteMap,Prefix,AccessList,StaticNat, DynamicNat,NatPool, VrfRoute,BDIInterface, VrfDefinition]
    L2_ENTITIES = [LoopbackInternalInterface, LoopbackExternalInterface, ExternalInterface]


    def clean_device(self,dry_run=True):
        result={}
        result["l3"]= self.clean_l3(dry_run=dry_run)
        result["l2"] = self.clean_l2(dry_run=dry_run)

        return result


    def clean_l3(self,dry_run=True):


        all_extra_atts = self.plugin_rpc.get_all_extra_atts(self.context)

        all_router_ids = all_extra_atts.keys()

        orphans  = {}

        for context in ASR1KPair().contexts:
            device_config =  BulkOperations.get_device_config(context)



            for entity in self.L3_ENTITIES:
                items = entity.get_all_from_device_config(device_config)

                for item in items:
                    if item.neutron_router_id  and item.neutron_router_id not in all_router_ids:

                        if(orphans.get(context) is None):
                            orphans[context] = []
                        orphans[context].append(item)



        result = {}
        if dry_run:

            for context in orphans:
                result[context.host] = json.dumps(orphans.get(context), cls=OrphanEncoder)
        else:
            for context, items in orphans.iteritems():
                for item in items:
                    item.delete(context=context)
                result[context.host] = json.dumps(items,cls=OrphanEncoder)

        return result


    def clean_l2(self,dry_run=True):


        all_extra_atts = self.plugin_rpc.get_all_extra_atts(self.context)

        all_router_ids = all_extra_atts.keys()

        orphans  = {}

        for context in ASR1KPair().contexts:
            device_config =  BulkOperations.get_device_config(context)

            for entity in self.L2_ENTITIES:
                items = entity.get_all_from_device_config(device_config)

                filtered = self._filter_l2_interfaces(items,all_extra_atts)

                if (orphans.get(context) is None):
                    orphans[context] = []

                if isinstance(items,list):
                    orphans[context]+=filtered
                else:
                    orphans[context].append(filtered)

        result = {}
        if dry_run:
            for context in orphans:
                items = orphans.get(context)
                if bool(items):
                    result[context.host] = json.dumps(items, cls=OrphanEncoder)
        else:
            for context, items in orphans.iteritems():
                items = orphans.get(context)
                if bool(items):
                    for item in items:
                        item.delete(context=context)
                    result[context.host] = json.dumps(items,cls=OrphanEncoder)

        return result


    def _filter_l2_interfaces(self,interfaces,all_extra_atts):
        results = []


        all_service_instances = []
        all_segmentation_ids = []

        for router_ports in all_extra_atts.values():
            for port_id,atts in router_ports.iteritems():
                all_service_instances.append(atts.get('service_instance'))
                all_segmentation_ids.append(atts.get('segmentation_id'))

        all_service_instances = list(set(all_service_instances))
        all_segmentation_ids = list(set(all_segmentation_ids))

        for interface in interfaces:
            no_match_service_instance = False
            no_match_segmentation_id = False



            if isinstance(interface,LoopbackInternalInterface) or isinstance(interface,LoopbackExternalInterface):
                no_match_service_instance = int(interface.id) >= asr1k_db.MIN_SERVICE_INSTANCE and  int(interface.id) <= asr1k_db.MAX_SERVICE_INSTANCE and int(interface.id) not in all_service_instances
            elif isinstance(interface,ExternalInterface):
                no_match_segmentation_id = int(interface.id) >= asr1k_db.MIN_DOT1Q and  int(interface.id) <= asr1k_db.MAX_DOT1Q and int(interface.id) not in all_segmentation_ids

            if no_match_segmentation_id or no_match_service_instance:
                results.append(interface)

        return results