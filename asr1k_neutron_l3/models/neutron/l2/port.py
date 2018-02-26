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

from asr1k_neutron_l3.models import asr1k_pair
from asr1k_neutron_l3.models.netconf_yang import l2_interface


LOG = logging.getLogger(__name__)


def create_ports(ports, callback=None):
    succeeded_ports = []
    for port in ports:
        l2_port = Port(port)
        l2_port._create()
        succeeded_ports.append(port.get('id'))

    if callable(callback):
        callback(succeeded_ports, [])

    return succeeded_ports

def update_ports(ports, callback=None):
    succeeded_ports = []
    for port in ports:
        l2_port = Port(port)

        print "valid {}".format(l2_port.valid())
        l2_port.update()
        succeeded_ports.append(port.get('id'))

    if callable(callback):
        callback(succeeded_ports, [])

    return succeeded_ports



def delete_ports(port_extra_atts, callback=None):
    succeeded_ports = []

    for port in port_extra_atts:

        l2_port = Port(port)
        result = l2_port.delete()
        succeeded_ports.append(l2_port.id)

    if callable(callback):

        callback(succeeded_ports, [])

    return succeeded_ports


class Port(object):

    def __init__(self, port_info):
        self.port_info = port_info
        self.config = asr1k_pair.ASR1KPair().config
        self.id = self.port_info.get('port_id')

        self.service_instance = self.port_info.get('service_instance')
        self.bridge_domain = self.port_info.get('bridge_domain')
        self.second_dot1q = self.port_info.get('second_dot1q')
        self.segmentation_id = self.port_info.get('segmentation_id')
        self.network_id = self.port_info.get('network_id')
        self.external_deleteable = self.port_info.get('external_deleteable')

    @property
    def ext_portchannel(self):
        return self.config.asr1k_devices.external_interface

    @property
    def lb_ext_portchannel(self):
        return self.config.asr1k_devices.loopback_external_interface

    @property
    def lb_int_portchannel(self):
        return self.config.asr1k_devices.loopback_internal_interface


    def _rest_definition(self):
        ext_interface = l2_interface.ExternalInterface(port_channel=self.ext_portchannel,
                                                       id=self.segmentation_id, description=self.network_id)
        lb_ext_interface = l2_interface.LoopbackExternalInterface(port_channel=self.lb_ext_portchannel,
                                                                  id=self.service_instance, description=self.id,
                                                                  dot1q=self.segmentation_id, second_dot1q=self.second_dot1q)
        lb_int_interface = l2_interface.LoopbackInternalInterface(port_channel=self.lb_int_portchannel,
                                                                  id=self.service_instance, description=self.id,
                                                                  bridge_domain=self.bridge_domain,
                                                                  dot1q=self.segmentation_id, second_dot1q=self.second_dot1q)
        return ext_interface, lb_ext_interface, lb_int_interface

    def valid(self):
        ext_interface, lb_ext_interface, lb_int_interface = self._rest_definition()
        return ext_interface.valid() and lb_ext_interface.valid() and lb_int_interface.valid()

    def get(self):

        ext_interface = l2_interface.ExternalInterface.get(self.ext_portchannel,self.segmentation_id)
        lb_ext_interface = l2_interface.LoopbackExternalInterface.get(self.lb_ext_portchannel, self.service_instance)
        lb_int_interface = l2_interface.LoopbackInternalInterface.get(self.lb_int_portchannel, self.service_instance)


        return ext_interface,lb_ext_interface,lb_int_interface


    def update(self):
        ext_interface, lb_ext_interface, lb_int_interface = self._rest_definition()

        ext_interface.update()
        lb_ext_interface.update()
        lb_int_interface.update()


    def create(self,callback=None):

        self._create()
        # TODO handle success/failure
        if callable(callback):
            callback([self.id], [])

        return self.id


    def _create(self):

        ext_interface, lb_ext_interface, lb_int_interface = self._rest_definition()

        # ideally this bit would be transcational

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

        ext_interface, lb_ext_interface, lb_int_interface = self._rest_definition()

        # TODO only on last port on network
        if self.external_deleteable:
            ext_result = ext_interface.delete()

        # For every port deletion
        lb_ext_result = lb_ext_interface.delete()
        lb_int_result = lb_int_interface.delete()

        # TODO handle success/failure

