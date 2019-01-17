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

import oslo_messaging
from neutron_lib import context
from neutron.common import rpc as n_rpc
from oslo_log import helpers as log_helpers
from oslo_log import log

from asr1k_neutron_l3.common import asr1k_constants, instrument
from asr1k_neutron_l3.plugins.db import asr1k_db

LOG = log.getLogger(__name__)


class ASR1KPluginApi(object):
    version = '1.0'

    def __init__(self, topic):
        target = oslo_messaging.Target(topic=topic, version='1.0')
        self.client = n_rpc.get_client(target)

    def _fanout(self):
        return self.client.prepare(version=self.version, topic=asr1k_constants.ASR1K_TOPIC, fanout=False)

    def get_ports_with_extra_atts(self, context, ports, agent_id=None, host=None):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_ports_with_extra_atts', ports=ports,
                          agent_id=agent_id, host=host)

    def get_extra_atts(self, context, ports, deleteable= False, agent_id=None, host=None):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_extra_atts', ports=ports,
                          agent_id=agent_id, host=host)

    def get_orphaned_extra_atts(self, context,agent_id=None, host=None):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_orphaned_extra_atts',
                          agent_id=agent_id, host=host)

    def delete_extra_atts(self, context, ports, agent_id=None, host=None):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'delete_extra_atts', ports=ports,
                          agent_id=agent_id, host=host)

    def get_interface_ports(self, context, limit=None , offset=None,host=None):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_interface_ports',limit=limit , offset=offset,host=host)

    def get_device_info(self, context, host):
        cctxt = self.client.prepare()
        return cctxt.call(context, 'get_device_info', host=host)


class ASR1KPluginCallback(object):

    def __init__(self):
        self.db = asr1k_db.DBPlugin()
        self.context = context.get_admin_context()

    @instrument.instrument()
    def get_ports_with_extra_atts(self, rpc_context, ports, agent_id=None, host=None):
        return self.db.get_ports_with_extra_atts(self.context, ports,host)

    @instrument.instrument()
    def get_extra_atts(self, rpc_context, ports, agent_id=None, host=None):
        return self.db.get_extra_atts(self.context, ports,host)

    def get_orphaned_extra_atts(self, rpc_context, agent_id=None, host=None):
        return self.db.get_orphaned_extra_atts(self.context, host=host)

    @log_helpers.log_method_call
    def delete_extra_atts(self, rpc_context, ports, agent_id=None, host=None):
        LOG.debug("Deleting extra atts for ports {}".format(ports))

        for port_id in ports:
            self.db.delete_extra_att(self.context, port_id, l2=True)

    @instrument.instrument()
    def get_interface_ports(self, rpc_context, limit=None, offset=None,host=None):


        ports = self.db.get_interface_ports(self.context, limit=limit, offset=offset,host=host)

        LOG.debug("ports len %s",len(ports))

        return ports

    @instrument.instrument()
    def get_device_info(self, context, host):
        return self.db.get_device_info(context, host)