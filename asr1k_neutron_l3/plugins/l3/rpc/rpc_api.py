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

        LOG.debug(ports)

        for port_id in ports:
            self.db.delete_extra_att(self.context, port_id, l3=True)
