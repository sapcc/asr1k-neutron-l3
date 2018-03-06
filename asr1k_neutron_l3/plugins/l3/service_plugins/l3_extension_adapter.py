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

from neutron.api.rpc.agentnotifiers import l3_rpc_agent_api
from neutron.db import common_db_mixin
from neutron.db import dns_db
from neutron.db import extraroute_db
from neutron.db import l3_gwmode_db as l3_db
from oslo_log import helpers as log_helpers
from oslo_log import log

from asr1k_neutron_l3.common import asr1k_constants as constants
from asr1k_neutron_l3.common.instrument import instrument
from asr1k_neutron_l3.plugins.db import asr1k_db
from asr1k_neutron_l3.plugins.l3.schedulers import asr1k_scheduler_db

LOG = log.getLogger(__name__)


class L3RpcNotifierMixin(object):
    """Mixin class to add rpc notifier attribute to db_base_plugin_v2."""

    @property
    def l3_rpc_notifier(self):
        if not hasattr(self, '_l3_rpc_notifier'):
            self._l3_rpc_notifier = l3_rpc_agent_api.L3AgentNotifyAPI()
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


class ASR1KPluginBase(common_db_mixin.CommonDbMixin, l3_db.L3_NAT_db_mixin,
                      asr1k_scheduler_db.AZASR1KL3AgentSchedulerDbMixin, extraroute_db.ExtraRoute_db_mixin,
                      dns_db.DNSDbMixin, L3RpcNotifierMixin):


    @instrument()
    @log_helpers.log_method_call
    def get_sync_data(self, context, router_ids=None, active=None):
        extra_atts = self._get_extra_atts(context, router_ids)
        router_atts = self._get_router_atts(context, router_ids)

        routers = super(ASR1KPluginBase, self).get_sync_data(context, router_ids=router_ids, active=active)

        for router in routers:
            extra_att = extra_atts.get(router['id'], {})
            router[constants.ASR1K_EXTRA_ATTS_KEY] = extra_att

            router_att = router_atts.get(router['id'], {})
            router[constants.ASR1K_ROUTER_ATTS_KEY] = router_att


        return routers

    def _get_extra_atts(self, context, router_ids):
        db = asr1k_db.DBPlugin()
        extra_atts = db.get_extra_atts_for_routers(context, router_ids)

        return_dict = {}

        for extra_att in extra_atts:
            if return_dict.get(extra_att.get('router_id')) is None:
                return_dict[extra_att.get('router_id')] = {}

            return_dict[extra_att.get('router_id')][extra_att.get('port_id')] = extra_att

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
        router_atts_db = asr1k_db.RouterAttsDb(result.get('id'), context)
        router_atts_db.update_router_atts()



        return result

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
