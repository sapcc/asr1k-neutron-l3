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

import socket
import struct

from netaddr import IPNetwork, IPAddress

from asr1k_neutron_l3.plugins.common import asr1k_constants as constants


def calculate_deleted_ports(router):
    extra_atts = router.get(constants.ASR1K_EXTRA_ATTS_KEY)

    router_ports = get_router_ports(router)

    return list(set(extra_atts.keys()) - set(router_ports))


def get_router_ports(router):
    router_ports = []

    if router.get('gw_port_id') is not None:
        router_ports.append(router.get('gw_port_id'))
    for interface in router.get('_interfaces', []):
        router_ports.append(interface.get('id'))

    return router_ports


def uuid_to_vrf_id(uuid):
    return uuid.replace('-', '')


def vrf_to_access_list_id(vrf_id):
    return "NAT-{}".format(vrf_id)


def uuid_to_mapping_id(uuid):
    if uuid is None:
        return None

    numbers = [int(s) for s in uuid if s.isdigit()]
    number = ("".join(str(x) for x in numbers))
    if (len(number) < 10):
        result = number
    else:
        result = number[0:9]
    return int(result)


def ip_to_int(ip):
    numbers = [int(s) for s in ip if s.isdigit()]
    number = ("".join(str(x) for x in numbers))
    return int(number)


def to_cisco_mac(mac):
    if mac is not None:
        return "{}{}.{}{}.{}{}".format(mac[:2], mac[3:5], mac[6:8], mac[9:11], mac[12:14], mac[15:17])


def from_cidr(cidr):
    split = cidr.split('/')

    ip = split[0]

    netmask = to_netmask(int(split[1]))

    return ip, netmask

def to_wildcard_mask(prefix_len):

    if isinstance(prefix_len, (int, long)):
        netmask = to_netmask(prefix_len)
    else:
        netmask = prefix_len

    wildcard = ".".join([str(255- int(octect)) for octect in netmask.split(".")])

    return wildcard

def ip_in_network(ip, net):
    return IPAddress(ip) in IPNetwork(net)


def to_netmask(prefix_len):
    if isinstance(prefix_len, (int, long)):
        host_bits = 32 - prefix_len
        netmask = socket.inet_ntoa(struct.pack('!I', (1 << 32) - (1 << host_bits)))
    else:
        netmask = prefix_len
    return netmask
