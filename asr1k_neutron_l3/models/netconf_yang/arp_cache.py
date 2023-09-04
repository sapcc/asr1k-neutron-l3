# Copyright 2023 SAP SE
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

import re

from oslo_log import log as logging

from asr1k_neutron_l3.models.connection import ConnectionManager
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair
from asr1k_neutron_l3.common.prometheus_monitor import PrometheusMonitor

LOG = logging.getLogger(__name__)


class ArpCacheConstants:
    ARP_DATA = 'arp-data'
    ARP_VRF = 'arp-vrf'
    VRF = 'vrf'
    ARP_ENTRY = 'arp-entry'


class VRFArpEntry(NyBase):
    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'address'},
            {'key': 'mac', 'yang-key': 'hardware'},
        ]

    def to_dict(self, context):
        return {'address': self.address, 'mac': self.mac}


class VRFArpCache(NyBase):
    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'vrf', 'yang-key': ArpCacheConstants.VRF, 'default': ''},
            {'key': 'entries', 'yang-key': ArpCacheConstants.ARP_ENTRY, 'type': [VRFArpEntry], 'default': []},
        ]

    def to_dict(self, context):
        return {'vrf': self.vrf, 'entries': [entry.to_dict(context) for entry in self.entries]}


class ArpCache(NyBase):
    ITEM_KEY = ArpCacheConstants.ARP_DATA

    ID_FILTER = """
      <arp-data xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-arp-oper">
        <arp-vrf>
          <vrf/>
          <arp-entry>
            <address/>
            <hardware/>
          </arp-entry>
        </arp-vrf>
      </arp-data>
    """

    CLEAN_ARP_ENTRY = """
      <clear xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-rpc">
        <arp-cache>
          <vrf>{vrf}</vrf>
          <ip-drop-node-name>{ip}</ip-drop-node-name>
        </arp-cache>
      </clear>
    """

    VRF_RE = re.compile("^[0-9a-f]{32}$")

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'vrfs', 'yang-key': ArpCacheConstants.ARP_VRF, 'type': [VRFArpCache], 'default': []},
        ]

    @classmethod
    @execute_on_pair()
    def clean_device_arp(cls, context, fip_data):
        LOG.debug("Host %s: Fetching ARP data", context.host)

        stale_entries = []
        arp_data = cls._get(context=context)
        if arp_data is None:
            LOG.warning("ARP cleanup could not fetch ARP cache from device for host %s, cleaning not possible",
                        context.host)
            return

        for vrf in arp_data.vrfs:
            if not cls.VRF_RE.match(vrf.vrf):
                continue

            for entry in vrf.entries:
                if fip_data.get(entry.address) not in (None, entry.mac):
                    stale_entries.append((vrf.vrf, entry.address, entry.mac, fip_data[entry.address]))
                    PrometheusMonitor().fip_on_wrong_mac_count.labels(device=context.host, vrf=vrf.vrf).inc()
        LOG.debug("ARP cleanup on host %s for %s fips and %s ARP entries with %s stale entries",
                  context.host, len(fip_data), sum(len(vrf.entries) for vrf in arp_data.vrfs), len(stale_entries))

        if stale_entries:
            with ConnectionManager(context=context) as connection:
                for vrf, ip, wrong_mac, mac in stale_entries:
                    LOG.warning("Host %s VRF %s has stale entry for ip %s on mac %s, should be %s - cleaning it",
                                context.host, vrf, ip, wrong_mac, mac)
                    connection.rpc(cls.CLEAN_ARP_ENTRY.format(vrf=vrf, ip=ip),
                                   entity=cls.__name__, action="clean_arp")

    def to_dict(self, context):
        return {'vrfs': [vrf.to_dict(context) for vrf in self.vrfs]}
