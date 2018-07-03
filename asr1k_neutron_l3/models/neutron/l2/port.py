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
from asr1k_neutron_l3.models.netconf_yang import efp_stats
from asr1k_neutron_l3.common import utils


LOG = logging.getLogger(__name__)


def create_ports(ports, callback=None):
    LOG.debug("Starting a batch create of {} ports".format(len(ports)))
    succeeded_ports = []
    for port in ports:
        l2_port = Port(port)
        l2_port._create()
        succeeded_ports.append(port.get('id'))

    if callable(callback):
        callback(succeeded_ports, [])
    LOG.debug("Batch create of completed {} ports successfully created".format(len(succeeded_ports)))
    return succeeded_ports

def update_ports(ports, callback=None):
    LOG.debug("Starting a batch update of {} ports".format(len(ports)))

    succeeded_ports = []
    for port in ports:
        port_id = port.get('id')

        l2_port = Port(port)
        l2_port.update()
        succeeded_ports.append(port_id)
        LOG.debug("Processed Neutron port {} sucessfully".format(port_id))

    if callable(callback):
        callback(succeeded_ports, [])
    LOG.debug("Batch update of completed {} ports successfully updated".format(len(succeeded_ports)))
    return succeeded_ports



def delete_ports(port_extra_atts, callback=None):
    LOG.debug("Starting a batch delete of {} ports".format(len(port_extra_atts)))
    succeeded_ports = []

    for port in port_extra_atts:

        l2_port = Port(port)
        result = l2_port.delete()
        succeeded_ports.append(l2_port.id)

    if callable(callback):

        callback(succeeded_ports, [])
    LOG.debug("Batch delete of completed {} ports successfully deleted".format(len(succeeded_ports)))
    return succeeded_ports


class Port(object):

    def __init__(self, port_info):
        self.port_info = port_info
        self.config = asr1k_pair.ASR1KPair().config

        self.id = self.port_info.get('port_id')

        self.second_dot1q = self.port_info.get('second_dot1q')

        self.service_instance = utils.to_bridge_domain(self.second_dot1q)
        self.bridge_domain = utils.to_bridge_domain(self.second_dot1q)

        self.segmentation_id = self.port_info.get('segmentation_id')
        self.network_id = self.port_info.get('network_id')
        self.external_deleteable = self.port_info.get('external_deleteable')


    def _rest_definition(self):
        ext_interface = l2_interface.ExternalInterface(id=self.segmentation_id, description="Network : {}".format(self.network_id))
        lb_ext_interface = l2_interface.LoopbackExternalInterface(id=self.service_instance, description="Port : {}".format(self.id),
                                                                  dot1q=self.segmentation_id, second_dot1q=self.second_dot1q)
        lb_int_interface = l2_interface.LoopbackInternalInterface(id=self.service_instance, description="Port : {}".format(self.id),
                                                                  bridge_domain=self.bridge_domain,
                                                                  dot1q=self.segmentation_id, second_dot1q=self.second_dot1q)
        return ext_interface, lb_ext_interface, lb_int_interface

    def diff(self):
        ext_interface, lb_ext_interface, lb_int_interface = self._rest_definition()

        result = {}

        ext_diff = ext_interface.diff()
        if not ext_diff.valid:
            result["l2_external"] = ext_diff.to_dict()

        lb_ext_diff = lb_ext_interface.diff()
        if not lb_ext_diff.valid:
            result["l2_external_lb"] = lb_ext_diff.to_dict()

        lb_int_diff = lb_int_interface.diff()
        if not lb_int_diff.valid:
            result["l2_internal_lb"] = lb_int_diff.to_dict()



        return result

    def get(self):

        ext_interface = l2_interface.ExternalInterface.get(self.segmentation_id)
        lb_ext_interface = l2_interface.LoopbackExternalInterface.get(self.service_instance)
        lb_int_interface = l2_interface.LoopbackInternalInterface.get(self.service_instance)


        return ext_interface,lb_ext_interface,lb_int_interface


    def get_stats(self):

        lb_ext_interface = efp_stats.LoopbackExternalEfpStats.get(id=self.service_instance)
        lb_int_interface = efp_stats.LoopbackInternalEfpStats.get(id=self.service_instance)

        return {"external_lb":lb_ext_interface.to_dict(),"internal_lb":lb_int_interface.to_dict()}


    def update(self,callback=None):
        failure = []
        success = [self.id]
        ext_interface, lb_ext_interface, lb_int_interface = self._rest_definition()

        result = ext_interface.update()

        if not result.success:
            failure.append(self.id)
            success = []

        result = lb_ext_interface.update()

        if not result.success:
            failure.append(self.id)
            success=[]

        result = lb_int_interface.update()

        if not result.success:
            failure.append(self.id)
            success = []


        if callable(callback):
            callback(success, failure)

    def create(self,callback=None):

        return self.update(callback)


    def delete(self, callback=None):

        ext_interface, lb_ext_interface, lb_int_interface = self._rest_definition()

        # TODO only on last port on network
        if self.external_deleteable:
            ext_result = ext_interface.delete()

        # For every port deletion
        lb_ext_result = lb_ext_interface.delete()
        lb_int_result = lb_int_interface.delete()

        # TODO handle success/failure
        if callable(callback):
            callback([self.id], [])

        return self.id



