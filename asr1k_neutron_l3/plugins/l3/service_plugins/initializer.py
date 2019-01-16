import re

from oslo_log import log

from asr1k_neutron_l3.common.instrument import instrument
from asr1k_neutron_l3.plugins.db import asr1k_db
from neutron.plugins.ml2.plugin import Ml2Plugin
from neutron_lib.api.definitions import portbindings

LOG = log.getLogger(__name__)


class Initializer(object):

    def __init__(self, plugin,context):
        self.plugin = plugin
        self.context = context



    @instrument()
    def cisco_teardown(self,dry_run=False):




        result = {}
        db = asr1k_db.DBPlugin()

        if not dry_run:
            db.clear_cisco_db(self.context)


        routers = self.plugin.get_routers(self.context,fields=['id','name'])
        candidates = []
        for router in routers:
            if re.match('.*HA_backup_1$', router.get('name')) is not None:
                candidates.append(router)
            if re.match('Logical-Global-router', router.get('name')) is not None:
                candidates.append(router)
            if re.match('Global-router-0000-000000000003', router.get('name')) is not None:
                candidates.append(router)
            if re.match('Global-router-0000-000000000004', router.get('name')) is not None:
                candidates.append(router)


        port_candidates = {}
        for candidate in candidates:

            router_id = candidate.get('id')

            result[router_id] = {'name':candidate.get('name')}
            ports = db.get_ports(self.context, filters={'device_id':[router_id]})
            port_list = []
            result[router_id]['interfaces'] = []
            for port in ports:
                if port.get('device_owner') == 'network:router_interface':
                    port_list.append(port)
                    result[router_id]['interfaces'].append({'id':port.get('id')})
            port_candidates[router_id] = port_list


        if not dry_run:

            for router in candidates:
                router_id = router.get('id')

                for port in port_candidates[router_id]:
                    port_id = port.get('id')
                    db.update_port(self.context, port_id, {'port': {'id': port_id, "device_id":"temp","device_owner":"temp"}})
                    db.delete_port(self.context,port_id)

                self.plugin.update_router(self.context,router_id,{'router':{'id':router_id,'external_gateway_info':{},'routes':[]}})

                self.plugin.delete_router(self.context,router_id)
                result[router_id]['deleted'] = True

        return result

    @instrument()
    def init_scheduler(self):
        result = {}
        db = asr1k_db.DBPlugin()

        ml2 = Ml2Plugin()
        router_ids = db.get_all_router_ids(self.context)
        scheduled = 0
        bound = 0
        for router_id in router_ids:
            result[router_id] = {}
            agent = self.plugin.schedule_router(self.context,router_id)
            if agent is not None:

                scheduled += 1
                agent_host = agent.host
                result[router_id]["scheduled"] = agent_host
            else:
                agent = self.plugin.get_agent_for_router(self.context, router_id)

                agent_host = agent.get('host')
                result[router_id]["already_scheduled"] = agent_host

            if agent_host is None:
                result[router_id]['error']  = "Router is not scheduled to a host"

        return result

    @instrument()
    def init_bindings(self):
        result = {}
        db = asr1k_db.DBPlugin()

        ml2 = Ml2Plugin()
        router_ids = db.get_all_router_ids(self.context)
        port_count = 0
        for router_id in router_ids:
            LOG.warn("Updating Router %s" % router_id)
            result[router_id] = {}
            agent = self.plugin.get_agent_for_router(self.context, router_id)
            agent_host = agent.get('host')

            if agent_host is not None:
                ports = db.get_ports_for_router_ids(self.context, [router_id])
                result[router_id]["port host"] = []
                for port in ports:
                    LOG.warn("Updating Port %s of Router %s" % (port.id, router_id))
                    port_count+=1
                    port_id = port.get('id')
                    if  port.get(portbindings.HOST_ID) != agent_host:

                        update_result = ml2.update_port(self.context, port_id,
                                                        {'port': {'id': port_id, portbindings.HOST_ID: agent_host}})
                    result[router_id]["port host"].append({'port': port_id, 'host': agent_host})


            else:
                result[router_id]['error'] = "Router is not scheduled to a host"
            result["ports_processed"] = port_count
        return result


    def init_atts(self):
        result = {}
        db = asr1k_db.DBPlugin()


        router_ids = db.get_all_router_ids(self.context)

        for router_id in router_ids:
            try:
                result[router_id] = self.plugin.ensure_config(self.context, router_id)
            except BaseException as e:
                LOG.exception(e)
                result[router_id] = e.__str__()

        return result

    @instrument()
    def init_config(self, host):
        db = asr1k_db.DBPlugin()
        router_ids = db.get_all_router_ids(self.context,host=host)

        router_infos = self.plugin.get_sync_data(self.context,router_ids=router_ids,host=host)

        config = self.plugin.notify_agent_init_config(self.context, host, router_infos)

        if config is not None:
            return "".join(config)



