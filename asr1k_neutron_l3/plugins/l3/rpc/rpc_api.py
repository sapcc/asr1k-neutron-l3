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

from neutron import context
from neutron.api.rpc.handlers import l3_rpc
from oslo_log import helpers as log_helpers
from oslo_log import log


from asr1k_neutron_l3.plugins.db import asr1k_db

LOG = log.getLogger(__name__)


class ASR1KRpcAPI(l3_rpc.L3RpcCallback):

    def __init__(self):
        self.db = asr1k_db.DBPlugin()
        self.context = context.get_admin_context()


    @log_helpers.log_method_call
    def delete_extra_atts_l3(self, context, **kwargs):
        ports = kwargs.get('ports', [])

        for port_id in ports:
            self.db.delete_extra_att(self.context, port_id, l3=True)

    @log_helpers.log_method_call
    def get_address_scopes(self, context, **kwargs):

        scopes = kwargs.get('scopes', [])

        scopes = self.db.get_address_scopes(self.context, filters={'name': scopes})

        result = {}

        for scope in scopes:
            result[scope.get('name')] = scope

        return result


    @log_helpers.log_method_call
    def update_router_status(self, context, **kwargs):

        router_id = kwargs.get('router_id')
        status = kwargs.get('status')

        if router_id is not None and status is not None:
            self.db.update_router_status(self.context, router_id,status)

    @log_helpers.log_method_call
    def get_deleted_routers(self,context, **kwargs):
        host = kwargs.get('host')
        router_ids = kwargs.get('router_ids')

        return self.l3plugin.get_sync_data(context, router_ids=router_ids, active=None,host=host)


    @log_helpers.log_method_call
    def get_extra_atts_orphans(self,context, **kwargs):
        host = kwargs.get('host')
        routers = self.db.get_orphaned_extra_atts_router_ids(self.context,host)

        if routers is None:
            return []

        return self.l3plugin.get_sync_data(context, router_ids=routers, active=None,host=host)

    @log_helpers.log_method_call
    def get_all_extra_atts(self, context, host=None):
        db = asr1k_db.DBPlugin()
        extra_atts = db.get_all_extra_atts(context, host=host)

        return_dict = {}

        for extra_att in extra_atts:
            router_id = extra_att.get('router_id')
            if return_dict.get(router_id) is None:
                return_dict[router_id] = {}
            return_dict[router_id][extra_att.get('port_id')] = extra_att
        return return_dict

    def ensure_snat_mode(self,context, port_id=None,mode=None):
        db = asr1k_db.DBPlugin()
        return db.ensure_snat_mode(context,port_id,mode)


    def get_deleted_router_atts(self,context,**kwargs):
        db = asr1k_db.DBPlugin()
        router_atts = db.get_deleted_router_atts(context)

        return router_atts

    @log_helpers.log_method_call
    def delete_router_atts(self, context, **kwargs):
        router_ids = kwargs.get('router_ids', [])
        for router_id in router_ids:
            self.db.delete_router_att(self.context, router_id)


    @log_helpers.log_method_call
    def get_router_atts_orphans(self,context, **kwargs):
        host = kwargs.get('host')
        routers = self.db.get_orphaned_router_atts_router_ids(self.context,host)

        if routers is None:
            return []

        return self.l3plugin.get_sync_data(context, router_ids=routers, active=None,host=host)


    @log_helpers.log_method_call
    def get_device_info(self,context, **kwargs):
        host = kwargs.get('host')
        return self.db.get_device_info(context,host)
