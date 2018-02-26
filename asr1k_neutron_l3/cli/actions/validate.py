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

from oslo_log import log as logging
from asr1k_neutron_l3.models.neutron.l3.router import Router
from asr1k_neutron_l3.models.neutron.l2.port import Port

import base_action

LOG = logging.getLogger(__name__)


class Validate(base_action.BaseAction):

    def __init__(self, namespace):
        super(Validate, self).__init__(namespace)

    def execute(self):
        ri = self.get_router_info()
        port_ids = []
        if ri :
            router = Router(ri)

            gateway_interface = router.interfaces.gateway_interface
            if gateway_interface:
                port_ids.append(gateway_interface.id)


            for interface in router.interfaces.internal_interfaces:
                port_ids.append(gateway_interface.id)


            if router.valid():
                print "Router Valid"


        ports = self.l2_plugin_rpc.get_ports_with_extra_atts(self.context,port_ids)

        for port in ports:
            l2_port = Port(port)

            l2_port.valid()


