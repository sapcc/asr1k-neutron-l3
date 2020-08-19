# Copyright 2019 SAP SE
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
from asr1k_neutron_l3.models.netconf_yang import l2_interface

LOG = logging.getLogger(__name__)


def update_ports(ports, callback=None):
    LOG.debug("Starting a batch update of %d ports", len(ports))
    succeeded_ports = []
    failed_ports = []
    for port in ports:
        with PrometheusMonitor().port_update_duration.time():
            port_id = port['port_id']
            bd = BridgeDomain.make_from_port(port)
            if bd.update():
                succeeded_ports.append(port_id)
            else:
                failed_ports.append(port_id)

    if callable(callback):
        callback(succeeded_ports, failed_ports)
    LOG.debug("Batch update of %d/%d ports completed successfully", len(succeeded_ports), len(ports))

    return succeeded_ports


def delete_ports(port_extra_atts, callback=None):
    LOG.debug("Starting a batch delete of %d ports", len(port_extra_atts))

    succeeded_ports = []
    for port in port_extra_atts:
        with PrometheusMonitor().port_delete_duration.time():
            port_id = port['port_id']
            bd = BridgeDomain.make_from_port(port)
            if port.get('external_deleteable'):
                # no ports left in bd, delete it
                if bd.delete():
                    succeeded_ports.append(port_id)
            else:
                if bd.delete_internal_ifaces():
                    succeeded_ports.append(port_id)

    if callable(callback):
        callback(succeeded_ports, [])
    LOG.debug("Batch delete of %d/%d ports completed successfully",
              len(succeeded_ports), len(port_extra_atts))
    return succeeded_ports


def sync_networks(networks, callback=None):
    succeeded_ports = []
    failed_ports = []
    for network in networks:
        ports = network['ports']
        port_ids = [port['port_id'] for port in ports]
        bd = BridgeDomain(network['segmentation_id'], network['network_id'], network['ports'],
                          has_complete_portset=True)
        if bd.update():
            succeeded_ports.extend(port_ids)
            LOG.debug("BD %s (network %s) updated successfully with %d ports",
                      network['segmentation_id'], network['network_id'], len(ports))
        else:
            failed_ports.extend(port_ids)
            LOG.debug("BD %s (network %s) update failed with %d ports",
                      network['segmentation_id'], network['network_id'], len(ports))

    if callback:
        callback(succeeded_ports, failed_ports)


class BridgeDomain(object):
    def __init__(self, bd_id, network_id, ports, has_complete_portset=True):
        super(BridgeDomain, self).__init__()

        # save vars
        self.bd_id = bd_id
        self.network_id = network_id
        self.ports = ports

        # create portchannel service instances
        self.ext_iface = l2_interface.ExternalInterface(id=self.bd_id,
                                                        description="Network: {}".format(self.network_id)
                                                                    if self.network_id else None,
                                                        way=1, mode="symmetric")
        self.bd_up_iface = l2_interface.KeepBDUpInterface(id=self.bd_id,
                                                          description="Network: {} (keep bd up iface)"
                                                                      .format(self.network_id)
                                                                      if self.network_id else None)

        # process ports (16.9: build hyperloop, 16.12: build bdvif members)
        self.lb_ext_ifaces = []
        self.lb_int_ifaces = []
        self.if_members = [
            l2_interface.BDIfMember(interface='Port-channel1',
                                    service_instances=[l2_interface.BDIfMemberServiceInstance(id=self.bd_id)]),
            # this second interface is only here to keep the BD up on 16.12
            # this can be removed after github issue #29 has been fixed by cisco
            l2_interface.BDIfMember(interface='Port-channel2',
                                    service_instances=[l2_interface.BDIfMemberServiceInstance(id=self.bd_id)]),
        ]
        self.bdvif_members = []
        for port in self.ports:
            second_dot1q = port['second_dot1q']
            int_service_instance = utils.to_bridge_domain(second_dot1q)

            # only used for 16.9
            lb_ext_iface = l2_interface.LoopbackExternalInterface(id=int_service_instance,
                                                                  description="Port : {}".format(port['port_id']),
                                                                  dot1q=self.bd_id,
                                                                  second_dot1q=second_dot1q,
                                                                  way=2, mode="symmetric")
            self.lb_ext_ifaces.append(lb_ext_iface)
            lb_int_iface = l2_interface.LoopbackInternalInterface(id=int_service_instance,
                                                                  description="Port : {}".format(port['port_id']),
                                                                  bridge_domain=int_service_instance,
                                                                  dot1q=self.bd_id,
                                                                  second_dot1q=second_dot1q,
                                                                  way=2, mode="symmetric")
            self.lb_int_ifaces.append(lb_int_iface)

            # only used for 16.12
            bdvif_member = l2_interface.BDVIFMember(name=int_service_instance)
            self.bdvif_members.append(bdvif_member)

        self.bridge_domain = l2_interface.BridgeDomain(id=self.bd_id,
                                                       if_members=self.if_members, bdvif_members=self.bdvif_members,
                                                       has_complete_member_config=has_complete_portset)

    @classmethod
    def make_from_port(cls, port):
        """Create a Neutron BridgeDomain for a single port"""
        return BridgeDomain(port['segmentation_id'], port.get('network_id'), [port], has_complete_portset=False)

    def update(self):
        results = []

        for iface in [self.ext_iface, self.bd_up_iface] + self.lb_ext_ifaces + self.lb_int_ifaces:
            results.append(iface.update())
        results.append(self.bridge_domain.update())

        return all(_r.success for _r in results)

    def delete_internal_ifaces(self):
        result = []

        # mark all internal bd members as deleted
        for member in self.bdvif_members:
            member.mark_deleted = True
        result.append(self.bridge_domain.update())

        for iface in self.lb_ext_ifaces + self.lb_int_ifaces:
            result.append(iface.delete())

        return all(_r.success for _r in result)

    def delete(self):
        result = []

        # delete bridge domain
        result.append(self.bridge_domain.delete())

        # delete ifaces
        for iface in [self.ext_iface, self.bd_up_iface] + self.lb_ext_ifaces + self.lb_int_ifaces:
            result.append(iface.delete())

        return all(_r.success for _r in result)

    def diff(self):
        diff_results = {}

        diff = self.ext_iface.diff()
        if not diff.valid:
            diff_results['ext_interface'] = diff.to_dict()

        for iftype, ifaces in (('lb_ext_interfaces', self.lb_ext_ifaces), ('lb_int_interfaces', self.lb_int_ifaces)):
            diffs = []
            for iface in ifaces:
                diff = iface.diff()
                if not diff.valid:
                    diffs.append(diff.to_dict())
            if diffs:
                diff_results[iftype] = diffs

        diff = self.bridge_domain.diff()
        if not diff.valid:
            diff_results['bridge_domain'] = diff.to_dict()

        return diff_results
