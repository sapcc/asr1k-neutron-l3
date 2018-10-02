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
import time
from  collections import OrderedDict
import sqlalchemy as sa

from neutron.db import api as db_api

from neutron.db import common_db_mixin
from neutron.db import dns_db
from neutron.db import extraroute_db
from neutron.db import l3_gwmode_db as l3_db
from oslo_log import helpers as log_helpers
from oslo_log import log

from asr1k_neutron_l3.common import asr1k_constants as constants
from asr1k_neutron_l3.common import  utils
from asr1k_neutron_l3.common.instrument import instrument
from asr1k_neutron_l3.plugins.db import asr1k_db
from asr1k_neutron_l3.plugins.db import models as asr1k_models

from asr1k_neutron_l3.plugins.l3.schedulers import asr1k_scheduler_db
from asr1k_neutron_l3.extensions import asr1koperations as asr1k_ext
from asr1k_neutron_l3.plugins.l3.rpc import ask1k_l3_notifier
from asr1k_neutron_l3.plugins.l3.service_plugins.initializer import Initializer

LOG = log.getLogger(__name__)


class L3RpcNotifierMixin(object):
    """Mixin class to add rpc notifier attribute to db_base_plugin_v2."""

    @property
    def l3_rpc_notifier(self):
        if not hasattr(self, '_l3_rpc_notifier') or not isinstance(self._l3_rpc_notifier,ask1k_l3_notifier.ASR1KAgentNotifyAPI)  :
            self._l3_rpc_notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()
        return self._l3_rpc_notifier

    @l3_rpc_notifier.setter
    def l3_rpc_notifier(self, value):
        self._l3_rpc_notifier = value

    @log_helpers.log_method_call
    def notify_router_updated(self, context, router_id,
                              operation=None):
        if router_id:
            self.l3_rpc_notifier.routers_updated(
                context, [router_id], operation)

    @log_helpers.log_method_call
    def notify_routers_updated(self, context, router_ids,
                               operation=None, data=None):
        if router_ids:
            self.l3_rpc_notifier.routers_updated(
                context, router_ids, operation, data)

    @log_helpers.log_method_call
    def notify_router_deleted(self, context, router_id):
        self.l3_rpc_notifier.router_deleted(context, router_id)

    @log_helpers.log_method_call
    def notify_router_sync(self, context, router_id):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()
        return notifier.router_sync(context, router_id)

    @log_helpers.log_method_call
    def notify_router_teardown(self, context, router_id):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        return notifier.router_teardown(context, router_id)

    @log_helpers.log_method_call
    def notify_router_validate(self, context, router_id):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        return notifier.router_validate(context, router_id)

    @log_helpers.log_method_call
    def notify_interface_statistics(self, context, router_id):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        return notifier.interface_statistics(context, router_id)

    @log_helpers.log_method_call
    def notify_show_orphans(self, context,host):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        return notifier.show_orphans(context,host)

    @log_helpers.log_method_call
    def notify_delete_orphans(self, context,host):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        return notifier.delete_orphans(context,host)

    @log_helpers.log_method_call
    def notify_list_devices(self, context,host):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        return notifier.list_devices(context,host)


    @log_helpers.log_method_call
    def notify_show_device(self, context,host,device_id):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        return notifier.show_device(context,host,device_id)

    @log_helpers.log_method_call
    def notify_agent_init_config(self, context, host,router_infos):
        LOG.debug('agent_initial_config')
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()
        return notifier.agent_init_config(context, host,router_infos)

class ASR1KPluginBase(common_db_mixin.CommonDbMixin, l3_db.L3_NAT_db_mixin,
                      asr1k_scheduler_db.AZASR1KL3AgentSchedulerDbMixin, extraroute_db.ExtraRoute_db_mixin,
                      dns_db.DNSDbMixin, L3RpcNotifierMixin,asr1k_ext.DevicePluginBase):

    def get_agent_for_router(self, context, router_id):
        """Returns all hosts to send notification about router update"""
        agents = self.list_l3_agents_hosting_router(context, router_id)

        agents_list = agents.get('agents', [])

        if len(agents_list) == 1:
            return agents_list[0]
        else:
            LOG.error('get host for router: there should be one and only one agent, got {}'.format(agents_list))

    def get_host_for_router(self, context, router_id):
        agent = self.get_agent_for_router(context,router_id)
        if agent is not None:
            return agent.get('host')



    def _ensure_second_dot1q(self, context):
        session = db_api.get_session()
        extra_atts = session.query(asr1k_models.ASR1KExtraAttsModel).all()
        second_dot1qs = []

        for extra_att in extra_atts:
            second_dot1qs.append(extra_att.second_dot1q)

        for extra_att in extra_atts:
            if extra_att.second_dot1q==0:
                for x in range(asr1k_db.MIN_SECOND_DOT1Q, asr1k_db.MAX_SECOND_DOT1Q):
                    if x not in second_dot1qs:
                        extra_att.second_dot1q = x;
                        second_dot1qs.append(x)
                        break

                with context.session.begin(subtransactions=True):
                    entry = session.query(asr1k_models.ASR1KExtraAttsModel).filter_by(router_id=extra_att.router_id,
                                                                                   agent_host=extra_att.agent_host,
                                                                                   port_id=extra_att.port_id,
                                                                                   segment_id=extra_att.segment_id
                                                                                   ).first()
                    if entry:
                        entry.update(extra_att)



    @instrument()
    @log_helpers.log_method_call
    def get_sync_data(self, context, router_ids=None, active=None,host=None):

        db = asr1k_db.DBPlugin()
        if host is not None:
            host_router_ids =db.get_all_router_ids(context,host)
            router_ids = [ r for r in router_ids if r in host_router_ids]

        if not bool(router_ids):
            return []

        extra_atts = self._get_extra_atts(context, router_ids,host)
        router_atts = self._get_router_atts(context, router_ids)

        try:
            routers = super(ASR1KPluginBase, self).get_sync_data(context, router_ids=router_ids, active=active)
        except TypeError:
            # We may have a race in the L3/L2 scavengers, lets back of and try again
            time.sleep(.25)
            routers = super(ASR1KPluginBase, self).get_sync_data(context, router_ids=router_ids, active=active)

        if not bool(routers):
            routers = []
            for router_id in router_ids:
                routers.append({'id':router_id,constants.ASR1K_ROUTER_ATTS_KEY:router_atts.get(router_id, {})})

        for router in routers:
            extra_att = extra_atts.get(router['id'])
            if extra_atts is None :
                if host is None:
                    LOG.debug("Not including router {} in sync its extra atts are missing.".format(router['id']))
                else:
                    LOG.debug("Not including router {} in sync its extra atts are missing for host {}.".format(router['id'],host))
                continue

            router[constants.ASR1K_EXTRA_ATTS_KEY] = extra_att

            router_att = router_atts.get(router['id'], {})
            router[constants.ASR1K_ROUTER_ATTS_KEY] = router_att

            # Make sure the gateway IPs all have prefixes and are sorted consistently
            # this is to prevent foo when we have to assign to nat pool, because we
            # can guarantee a consistent order from neutron and we can't change the
            # pool on the active device and it has (currently) to be different from
            # the interface device.
            
            gw_info = router.get('external_gateway_info', None)
            gw_port = router.get('gw_port',None)
            if gw_port is not None:
                ips = gw_port.get('fixed_ips',[])
                prefixes = {}
                if bool(ips):
                    for ip in ips:
                        prefix = ip.get('prefixlen',None)
                        subnet_id = ip.get('subnet_id',None)
                        if prefix is not None and subnet_id is not None:
                            prefixes[subnet_id]=prefix

                    for ip in ips:
                        if ip.get('prefixlen',None) is None:
                            prefix = prefixes.get(ip.get('subnet_id',None))
                            if prefix is not None:
                                ip['prefixlen'] = prefix

                    gw_port['fixed_ips'] = sorted(ips, key=lambda k: k.get('ip_address'))
                    if gw_info is not None:
                        gw_info['external_fixed_ips']=gw_port['fixed_ips']



        return routers


    def get_deleted_router_atts(self,context):
        db = asr1k_db.DBPlugin()
        return db.get_deleted_router_atts(context)

    def _get_device_info(self,context,host):
        db = asr1k_db.DBPlugin()
        return db.get_device_info(context,host)


    def _get_extra_atts(self, context, router_ids, host=None):
        db = asr1k_db.DBPlugin()
        extra_atts = db.get_extra_atts_for_routers(context, router_ids, host=host)

        return_dict = {}

        for extra_att in extra_atts:
            router_id = extra_att.get('router_id')
            if return_dict.get(router_id) is None:
                return_dict[router_id] = {}

            if host is None:
                return_dict[router_id][extra_att.get('port_id')] = extra_att
            else:
                if host == extra_att.get('agent_host'):
                    return_dict[router_id][extra_att.get('port_id')] = extra_att

        return return_dict

    def _get_router_atts(self, context, router_ids):
        db = asr1k_db.DBPlugin()
        router_atts = db.get_router_atts_for_routers(context, router_ids)

        return_dict = {}

        for router_att in router_atts:
            if return_dict.get(router_att.get('router_id')) is None:
                return_dict[router_att.get('router_id')] = {}

            return_dict[router_att.get('router_id')] = router_att



        return return_dict




    @log_helpers.log_method_call
    def create_router(self, context, router):
        result = super(ASR1KPluginBase, self).create_router(context, router)
        asr1k_db.RouterAttsDb.ensure(context,result.get('id'))
        return result


    @log_helpers.log_method_call
    def update_router(self, context, id, router):
        result = super(ASR1KPluginBase, self).update_router(context, id, router)
        asr1k_db.RouterAttsDb.ensure(context, result.get('id'))
        return result

    @log_helpers.log_method_call
    def get_router(self, context, id, fields=None):
        return super(ASR1KPluginBase, self).get_router(context, id, fields)

    @log_helpers.log_method_call
    def delete_router(self, context, id):
        return super(ASR1KPluginBase, self).delete_router( context, id)

    @log_helpers.log_method_call
    def add_router_interface(self, context, router_id, interface_info):
        return super(ASR1KPluginBase,self).add_router_interface(context, router_id, interface_info)

    @log_helpers.log_method_call
    def remove_router_interface(self, context, router_id, interface_info):
        return super(ASR1KPluginBase,self).remove_router_interface(context, router_id, interface_info)




    def validate(self, context, id, fields=None):

        result = self.notify_router_validate(context, id)
        return {'diffs': result}


    def sync(self, context, id, fields=None):
        result = self.notify_router_sync(context,id)
        return {'device': {'router_id': result}}

    def orphans(self, context, dry_run=True):
        result = self.notify_router_sync(context,dry_run)
        return result

    def get_config(self, context, id):
        router_atts = self._get_router_atts(context,[id])

        extra_atts = self._get_extra_atts(context,[id])
        atts = extra_atts.get(id,None)
        result = OrderedDict({'id':id,'rd':None})
        if len(router_atts) > 0:
            att = router_atts.get(id, None)
            if att is not None:
                result['rd'] = att.rd

        ports = []
        result
        if atts is not None:
            for port_id in atts.keys():
                port = OrderedDict({'port_id':port_id})
                att = atts.get(port_id)
                if att is not None:
                    port['segment_id']=att.segment_id
                    port['segmentation_id'] = att.segmentation_id
                    port['second_dot1q'] = att.second_dot1q
                    port['external_service_instance'] = att.segmentation_id
                    port['loopback_service_instance'] = utils.to_bridge_domain(att.second_dot1q)
                    port['bridge_domain'] = utils.to_bridge_domain(att.second_dot1q)
                    port['deleted_l2'] = att.deleted_l2
                    port['deleted_l3'] = att.deleted_l3

                ports.append(port)
        result['ports'] = ports

        return dict(result)

    def ensure_config(self,context,id):
        asr1k_db.RouterAttsDb.ensure(context,id)

        db = asr1k_db.DBPlugin()
        ports = db.get_router_ports(context,id)
        for port in ports:
            segment = db.get_router_segment_for_port(context,id,port.get('id'))
            asr1k_db.ExtraAttsDb.ensure(id,port,segment)


        return self.get_config(context,id)

    def interface_statistics(self, context, id, fields=None):
        result = self.notify_interface_statistics(context, id)
        return {'interface_statistics': result}


    def teardown(self, context, id, fields=None):
        result = self.notify_router_teardown(context, id)
        return {'device': {'id': result}}

    def show_orphans(self, context,host):
        result = self.notify_show_orphans(context,host)
        return result

    def delete_orphans(self, context,host):
        result = self.notify_delete_orphans(context,host)
        return result


    def list_devices(self, context,host):
        result = self.notify_list_devices(context,host)
        db = asr1k_db.DBPlugin()
        device_info = db.get_device_info(context,host)
        for id in result:
            device = result.get(id)
            self._add_device_enabled(device_info,device)
        return result


    def show_device(self, context, host, id):
        db = asr1k_db.DBPlugin()
        result = self.notify_show_device(context, host, id)
        device_info = db.get_device_info(context, host)
        self._add_device_enabled(device_info, result)
        return result

    def _add_device_enabled(self,device_info,device):
        info = device_info.get(device.get('id'))
        if info is None or info.enabled:
            device['enabled'] = True
        else:
            device['enabled'] = False

    def update_device(self, context, host, id, enabled):
        device = self.notify_show_device(context, host, id)
        if device is None:
            return None

        asr1k_db.DeviceInfoDb(context,id,host,enabled).update()

        return {id:enabled}


    def init_scheduler(self, context):

        return Initializer(self,context).init_scheduler()

    def init_bindings(self, context):
        return Initializer(self,context).init_bindings()

    def init_atts(self, context):
        return Initializer(self,context).init_atts()

    def init_config(self, context, host):

        return Initializer(self,context).init_config(host)

    def cisco_teardown(self,context,dry_run=True):

        return Initializer(self,context).cisco_teardown(dry_run=dry_run)



    #
    # @log_helpers.log_method_call
    # def update_router(self, context, id, router):
    #     return self.base.update_router( context, id, router)
    #
    # @log_helpers.log_method_call
    # def get_router(self, context, id, fields=None):
    #     return self.base.get_router(context, id, fields)
    #
    # @log_helpers.log_method_call
    # def delete_router(self, context, id):
    #     return self.base.delete_router( context, id)
    #
    # @log_helpers.log_method_call
    # def get_routers(self, context, filters=None, fields=None,
    #                 sorts=None, limit=None, marker=None, page_reverse=False):
    #     return self.base.get_routers(context, filters, fields,
    #                 sorts, limit, marker, page_reverse)

    # @log_helpers.log_method_call
    # def add_router_interface(self, context, router_id, interface_info):
    #     return super(ASR1KPluginBase,self).add_router_interface(context, router_id, interface_info)
    #
    # @log_helpers.log_method_call
    # def remove_router_interface(self, context, router_id, interface_info):
    #     return super(ASR1KPluginBase,self).remove_router_interface(context, router_id, interface_info)
    #
    # @log_helpers.log_method_call
    # def create_floatingip(self, context, floatingip):
    #     return super(ASR1KPluginBase,self).create_floatingip(context, floatingip)
    #
    # @log_helpers.log_method_call
    # def update_floatingip(self, context, id, floatingip):
    #     return super(ASR1KPluginBase,self).update_floatingip(context, id, floatingip)
    #
    # @log_helpers.log_method_call
    # def get_floatingip(self, context, id, fields):
    #     return super(ASR1KPluginBase,self).get_floatingip(context, id, fields)
    #
    # @log_helpers.log_method_call
    # def delete_floatingip(self, context, id):
    #     return super(ASR1KPluginBase,self).delete_floatingip(context, id)
    #
    # @log_helpers.log_method_call
    # def get_floatingips(self, context, filters=None, fields=None,
    #                     sorts=None, limit=None, marker=None,
    #                     page_reverse=False):
    #
    #     return self.base.get_floatingips(context, filters, fields,
    #                     sorts, limit, marker,
    #                     page_reverse)

    # @log_helpers.log_method_call
    # def disassociate_floatingips(self, context, port_id, do_notify=True):
    #     return super(ASR1KPluginBase,self).disassociate_floatingips(context, port_id, do_notify)
    #
    #
    #
    #
    # def get_routers_count(self, context, filters=None):
    #     raise NotImplementedError()
    #
    # def get_floatingips_count(self, context, filters=None):
    #     raise NotImplementedError()

# class RouterDbBase(common_db_mixin.CommonDbMixin,l3_db.L3_NAT_db_mixin,extraroute_db.ExtraRoute_db_mixin,L3RpcNotifierMixin):
#
#     def __init__(self):
#         pass
