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

from asr1k_neutron_l3.models.rest import l2_interface
from asr1k_neutron_l3.models.rest.rest_base import execute_on_pair

LOG = logging.getLogger(__name__)


def create_ports(asr_pair, ports, callback=None):
    succeeded_ports = []
    for port in ports:
        l2_port = Port(asr_pair, port)
        result = l2_port.create()
        succeeded_ports.append(l2_port.id)

    if callable(callback):
        callback(succeeded_ports, [])


def delete_ports(asr_pair, port_extra_atts, callback=None):
    succeeded_ports = []

    for port in port_extra_atts:
        l2_port = Port(asr_pair, port)
        result = l2_port.delete()
        succeeded_ports.append(l2_port.id)

    if callable(callback):

        callback(succeeded_ports, [])


class Port:

    def __init__(self, asr_pair, port_info):

        self.port_info = port_info
        self.config = asr_pair.config
        self.id = self.port_info.get('port_id')

    @property
    def ext_portchannel(self):
        return self.config.asr1k_devices.external_interface

    @property
    def lb_ext_portchannel(self):
        return self.config.asr1k_devices.loopback_external_interface

    @property
    def lb_int_portchannel(self):
        return self.config.asr1k_devices.loopback_internal_interface


    def create(self,callback=None):

        self._create()
        # TODO handle success/failure
        if callable(callback):
            callback([self.id], [])

        return self.id


    def _create(self):


        service_instance = self.port_info.get('service_instance')
        bridge_domain = self.port_info.get('bridge_domain')
        second_dot1q = self.port_info.get('second_dot1q')
        segmentation_id = self.port_info.get('segmentation_id')
        network_id = self.port_info.get('network_id')

        # ideally this bit would be transcational

        ext_interface = l2_interface.ExternalInterface(port_channel=self.ext_portchannel,
                                                       id=segmentation_id, description=network_id)
        lb_ext_interface = l2_interface.LoopbackExternalInterface(port_channel=self.lb_ext_portchannel,
                                                                  id=service_instance, description=self.id,
                                                                  dot1q=segmentation_id, second_dot1q=second_dot1q)
        lb_int_interface = l2_interface.LoopbackInternalInterface(port_channel=self.lb_int_portchannel,
                                                                  id=service_instance, description=self.id,
                                                                  bridge_domain=bridge_domain,
                                                                  dot1q=segmentation_id, second_dot1q=second_dot1q)

        ext_interface.create()
        lb_ext_interface.create()
        lb_int_interface.create()

        # TODO handle success/failure

    def delete(self, callback=None):


        self._delete()
        # TODO handle success/failure
        if callable(callback):
            callback([self.id], [])

        return self.id

    def _delete(self):


        segmentation_id = self.port_info.get('segmentation_id')
        service_instance = self.port_info.get('service_instance')


        ext_interface = l2_interface.ExternalInterface(port_channel=self.ext_portchannel,
                                                       id=segmentation_id)
        lb_ext_interface = l2_interface.LoopbackExternalInterface(port_channel=self.lb_ext_portchannel,
                                                                  id=service_instance)
        lb_int_interface = l2_interface.LoopbackInternalInterface(port_channel=self.lb_int_portchannel,
                                                                  id=service_instance)

        # TODO only on last port on network
        ext_result = ext_interface.delete()

        # For every port deletion
        lb_ext_result = lb_ext_interface.delete()
        lb_int_result = lb_int_interface.delete()

        # TODO handle success/failure

