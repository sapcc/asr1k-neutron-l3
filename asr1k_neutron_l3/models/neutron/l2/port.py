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

from asr1k_neutron_l3.common.prometheus_monitor import PrometheusMonitor
from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.models import asr1k_pair
from asr1k_neutron_l3.models.netconf_yang import efp_stats
from asr1k_neutron_l3.models.netconf_yang import l2_interface

LOG = logging.getLogger(__name__)


def create_ports(ports, callback=None):
    LOG.debug("Starting a batch create of {} ports".format(len(ports)))
    succeeded_ports = []
    failed_ports = []
    for port in ports:
        with PrometheusMonitor().port_create_duration.time():
            l2_port = Port(port)
            port_id = port.get('id')
            result = l2_port.create()
            if result:
                succeeded_ports.append(port_id)
            else:
                failed_ports.append(port_id)

    if callable(callback):
        callback(succeeded_ports, failed_ports)
    LOG.debug("Batch create of completed {}/{} ports successfully created".format(len(succeeded_ports), len(ports)))
    return succeeded_ports


def update_ports(ports, callback=None):
    LOG.debug("Starting a batch update of {} ports".format(len(ports)))
    succeeded_ports = []
    failed_ports = []

    for port in ports:
        with PrometheusMonitor().port_update_duration.time():
            port_id = port.get('id')

            l2_port = Port(port)
            result = l2_port.update()
            if result:
                succeeded_ports.append(port_id)
            else:
                failed_ports.append(port_id)

    if callable(callback):
        callback(succeeded_ports, failed_ports)
    LOG.debug("Batch update of completed {}/{} ports successfully updated".format(len(succeeded_ports), len(ports)))
    return succeeded_ports


def delete_ports(port_extra_atts, callback=None):
    LOG.debug("Starting a batch delete of {} ports".format(len(port_extra_atts)))
    succeeded_ports = []

    for port in port_extra_atts:
        with PrometheusMonitor().port_delete_duration.time():
            l2_port = Port(port)
            result = l2_port.delete()
            succeeded_ports.append(l2_port.id)

    if callable(callback):
        callback(succeeded_ports, [])
    LOG.debug("Batch delete of completed {}/{} ports successfully deleted"
              "".format(len(succeeded_ports), len(port_extra_atts)))
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
        ext_interface = l2_interface.ExternalInterface(id=self.segmentation_id,
                                                       description="Network : {}".format(self.network_id),
                                                       way=1, mode="symmetric")
        lb_ext_interface = l2_interface.LoopbackExternalInterface(id=self.service_instance,
                                                                  description="Port : {}".format(self.id),
                                                                  dot1q=self.segmentation_id,
                                                                  second_dot1q=self.second_dot1q,
                                                                  way=2, mode="symmetric")
        lb_int_interface = l2_interface.LoopbackInternalInterface(id=self.service_instance,
                                                                  description="Port : {}".format(self.id),
                                                                  bridge_domain=self.bridge_domain,
                                                                  dot1q=self.segmentation_id,
                                                                  second_dot1q=self.second_dot1q,
                                                                  way=2, mode="symmetric")

        pc_member = l2_interface.BDIfMember(interface='Port-channel1', service_instance=self.segmentation_id)
        bdvif_member = l2_interface.BDVIFMember(name=self.bridge_domain)
        bridge_domain = l2_interface.BridgeDomain(id=self.segmentation_id,
                                                  if_members=[pc_member], bdvif_members=[bdvif_member])

        return ext_interface, lb_ext_interface, lb_int_interface, bridge_domain

    def diff(self):
        ext_interface, lb_ext_interface, lb_int_interface, bridge_domain = self._rest_definition()

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

        bridge_domain_diff = bridge_domain.diff()
        if not bridge_domain_diff.valid:
            result["bridge_domain"] = bridge_domain_diff.to_dict()

        return result

    def get(self):
        ext_interface = l2_interface.ExternalInterface.get(self.segmentation_id)
        lb_ext_interface = l2_interface.LoopbackExternalInterface.get(self.service_instance)
        lb_int_interface = l2_interface.LoopbackInternalInterface.get(self.service_instance)
        bridge_domain = l2_interface.BridgeDomain.get(self.service_instance)

        return ext_interface, lb_ext_interface, lb_int_interface, bridge_domain

    def get_stats(self):
        lb_ext_interface = efp_stats.LoopbackExternalEfpStats.get(id=self.service_instance)
        lb_int_interface = efp_stats.LoopbackInternalEfpStats.get(id=self.service_instance)

        return {"external_lb": lb_ext_interface.to_dict(), "internal_lb": lb_int_interface.to_dict()}

    def update(self, callback=None):
        failure = []
        success = [self.id]
        ext_interface, lb_ext_interface, lb_int_interface, bridge_domain = self._rest_definition()

        result = ext_interface.update()

        if not result.success:
            failure.append(self.id)
            success = []

        result = lb_ext_interface.update()

        if not result.success:
            failure.append(self.id)
            success = []

        result = lb_int_interface.update()

        if not result.success:
            failure.append(self.id)
            success = []

        result = bridge_domain.update()

        if not result.success:
            failure.append(self.id)
            success = []

        if callable(callback):
            callback(success, failure)

        LOG.debug("Port {} update {}".format(self.id, "successfull" if len(success) == 1 else "failed"))

        return len(success) == 1

    def create(self, callback=None):
        return self.update(callback)

    def delete(self, callback=None):
        ext_interface, lb_ext_interface, lb_int_interface, bridge_domain = self._rest_definition()

        failure = []
        success = [self.id]

        # TODO only on last port on network
        if self.external_deleteable:
            result = ext_interface.delete()
            if not result.success:
                failure.append(self.id)
                success = []

            result = bridge_domain.delete()
            if not result.success:
                failure.append(self.id)
                success = []
        else:
            # if not last port, only delete bdvif from bridge
            bridge_domain.bdvif_members[0].mark_deleted = True
            bridge_domain.update()

        # For every port deletion
        result = lb_ext_interface.delete()
        if not result.success:
            failure.append(self.id)
            success = []
        result = lb_int_interface.delete()
        if not result.success:
            failure.append(self.id)
            success = []

        # TODO handle success/failure
        if callable(callback):
            callback([self.id], [])

        return len(success) == 1
