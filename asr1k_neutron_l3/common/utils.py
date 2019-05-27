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

import re
import socket
import struct

from netaddr import IPNetwork, IPAddress
from oslo_log import log as logging


from asr1k_neutron_l3.common import asr1k_constants as constants
from asr1k_neutron_l3.common import config as asr1k_config

LOG = logging.getLogger(__name__)


def calculate_deleted_ports(router):
    extra_atts = router.get(constants.ASR1K_EXTRA_ATTS_KEY)

    router_ports = get_router_ports(router)

    extra_atts_ports = []
    if extra_atts is not None:
        extra_atts_ports = extra_atts.keys()

    return list(set(extra_atts_ports) - set(router_ports))


def get_router_ports(router):
    router_ports = []

    if router.get('gw_port_id') is not None:
        router_ports.append(router.get('gw_port_id'))
    for interface in router.get('_interfaces', []):
        router_ports.append(interface.get('id'))

    return router_ports


def uuid_to_vrf_id(uuid):
    return uuid.replace('-', '')


def vrf_id_to_uuid(id):
    if id is None or isinstance(id, str):
        return False

    if re.match("[0-9a-f]{32}", id):
        return "{}-{}-{}-{}-{}".format(id[0:8], id[8:12], id[12:16], id[16:20], id[20:32])
    return False


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


def prefix_from_cidr(cidr):
    split = cidr.split('/')
    return int(split[1])


def to_cidr(ip, netmask):
    if isinstance(netmask, str):
        nm = IPAddress(netmask)
        cidr = nm.netmask_bits()
    else:
        cidr = netmask

    return '{}/{}'.format(ip, netmask)


def to_wildcard_mask(prefix_len):
    if isinstance(prefix_len, (int, long)):
        netmask = to_netmask(prefix_len)
    else:
        netmask = prefix_len

    wildcard = ".".join([str(255 - int(octect)) for octect in netmask.split(".")])

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


def to_rd(asn, rd):
        if asn is None or rd is None:
            return
        return "{}:{}".format(asn, rd)


def get_address_scope_config(plugin_rpc, context):
    scope_config = asr1k_config.create_address_scope_dict()

    db_scopes = plugin_rpc.get_address_scopes(context, scope_config.keys())

    result = {}
    for name in scope_config.keys():
        if name in db_scopes.keys():
            id = db_scopes.get(name, {}).get("id")
            result[id] = scope_config.get(name)
        else:
            LOG.warning('Could not find DB config for configured scope {}'.format(name))

    LOG.debug("Address scopes from config")
    LOG.debug(result)

    return result


def to_bridge_domain(second_dot1q):
    if second_dot1q is not None:
        return 4096 + int(second_dot1q)
    else:
        LOG.error('Have been asked to convert a null second dot1q tag to a bridge domain, '
                  'router att for port is missing : probable cause is a port binding failing. ')
