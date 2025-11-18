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
from collections import OrderedDict

from oslo_config import cfg
from oslo_log import log as logging

from asr1k_neutron_l3.common import cli_snippets, utils
from asr1k_neutron_l3.models.netconf_yang.l2_interface import BridgeDomain
import asr1k_neutron_l3.models.netconf_yang.nat
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair, YANG_TYPE, NC_OPERATION
from asr1k_neutron_l3.models.netconf_yang import route
from asr1k_neutron_l3.models.netconf_yang import xml_utils
from asr1k_neutron_l3.plugins.db import asr1k_db


LOG = logging.getLogger(__name__)


class L3Constants(object):
    INTERFACE = "interface"
    BDI_INTERFACE = "BDI"
    BDVIF_INTERFACE = "BD-VIF"

    ID = "id"
    NAME = "name"
    DESCRIPTION = "description"
    MAC_ADDRESS = "mac-address"
    ZONE_MEMBER = "zone-member"
    SECURITY = "security"
    REDUNDANCY = "redundancy"
    GROUP = "group"
    DECREMENT = "decrement"
    RII = "rii"
    MTU = "mtu"
    IP = "ip"
    ADDRESS = "address"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    MASK = "mask"
    IPV6 = "ipv6"
    PREFIX = 'prefix'
    PREFIX_LIST = 'prefix-list'
    VRF = "vrf"
    FORWARDING = "forwarding"
    SHUTDOWN = "shutdown"
    NAT = "nat"
    NAT_MODE_INSIDE = "inside"
    NAT_MODE_OUTSIDE = "outside"
    NAT_MODE_STICK = "stick"
    POLICY = "policy"
    ROUTE_MAP = "route-map"
    ACCESS_GROUP = "access-group"
    OUT = "out"
    IN = "in"
    ACL = "acl"
    ACL_NAME = "acl-name"
    DIRECTION = "direction"
    DIRECTION_OUT = "out"
    DIRECTION_IN = "in"
    NTP = "ntp"
    NTP_DISABLE = "disable"
    ARP = "arp"
    TIMEOUT = "timeout"
    TRAFFIC_FILTER = "traffic-filter"
    COMMON = "common"

    IFACE_TUNNEL = "Tunnel"
    TUNNEL = "tunnel"
    KEEPALIVE = "keepalive"
    PERIOD = "period"
    RETRIES = "retries"
    KEEPALIVE_CONFIG = "keepalive-config"
    ADJUST_MSS = "adjust-mss"
    TCP = "tcp"
    SOURCE = "source"
    IPV4 = "ipv4"
    DUAL_OVERLAY = "dual-overlay"
    DESTINATION_CONFIG = "destination-config"
    IPSEC = "ipsec"
    MODE = "mode"
    PROFILE_OPTION = "profile-option"
    PROTECTION = "protection"
    VRF_CONFIG = "vrf-config"
    VRF_COMMON = "vrf-common"
    PATH_MTU_DISCOVERY = "path-mtu-discovery"


class BDInterface(NyBase):
    ID_FILTER = """
                <native>
                    <interface>
                        <BD-VIF>
                            <name>{id}</name>
                        </BD-VIF>
                    </interface>
                </native>
             """

    GET_ALL_STUB = """
                <native>
                    <interface>
                        <BD-VIF>
                            <name/>
                            <vrf>
                                <forwarding/>
                            </vrf>
                        </BD-VIF>
                    </interface>
                </native>
             """

    VRF_FILTER = """
                <native>
                    <interface>
                        <BD-VIF>
                            <vrf>
                                <forwarding>{vrf}</forwarding>
                            </vrf>
                        </BD-VIF>
                    </interface>
                </native>
             """

    VRF_XPATH_FILTER = "/native/interface/BD-VIF/vrf[forwarding='{vrf}']"

    LIST_KEY = L3Constants.INTERFACE
    ITEM_KEY = L3Constants.BDVIF_INTERFACE
    MIN_MTU = 1500
    MAX_MTU = 9216

    @classmethod
    def __parameters__(cls):
        # secondary IPs will be validated in NAT
        # NAT mode should be validated when supported in yang models - no point using netconf for now
        return [
            {"key": "name", "id": True},
            {'key': 'description'},
            {'key': 'mac_address'},
            {'key': 'mtu', 'default': BDInterface.MIN_MTU},
            {'key': 'vrf', 'yang-path': 'vrf', 'yang-key': "forwarding"},
            {'key': 'ip_address', 'yang-path': 'ip/address', 'yang-key': "primary", 'type': BDPrimaryIpAddress},
            {'key': 'secondary_ip_addresses', 'yang-path': 'ip/address', 'yang-key': "secondary",
             'type': [BDSecondaryIpAddress], 'default': [], 'validate': False},
            {'key': 'ipv6_addresses', 'yang-path': 'ipv6/address', 'yang-key': "prefix-list", 'type': [BDIpv6Address]},
            {'key': 'nat_inside', 'yang-key': 'inside', 'yang-path': 'ip/nat', 'default': False,
             'yang-type': YANG_TYPE.EMPTY},
            {'key': 'nat_outside', 'yang-key': 'outside', 'yang-path': 'ip/nat', 'default': False,
             'yang-type': YANG_TYPE.EMPTY},
            {'key': 'nat_stick', 'yang-key': 'stick', 'yang-path': 'ip/nat', 'default': False,
             'yang-type': YANG_TYPE.EMPTY},
            {'key': 'route_map', 'yang-key': 'route-map', 'yang-path': 'ip/policy'},
            {'key': 'policy_map_v6', 'yang-key': 'route-map', 'yang-path': 'ipv6/policy'},
            {'key': 'access_group_out', 'yang-key': 'acl-name', 'yang-path': 'ip/access-group/out/acl'},
            {'key': 'access_group_in', 'yang-key': 'acl-name', 'yang-path': 'ip/access-group/in/acl'},
            {'key': 'traffic_filters_v6', 'yang-key': 'traffic-filter', 'yang-path': 'ipv6',
             'type': [TrafficFilter], 'default': []},
            {'key': 'redundancy_group', 'yang-key': 'id', 'yang-path': 'redundancy/group'},
            {'key': 'redundancy_group_decrement', 'yang-key': 'decrement', 'yang-path': 'redundancy/group'},
            {'key': 'rii', 'yang-key': 'id', 'yang-path': 'redundancy/rii'},
            {'key': 'zone', 'yang-key': 'security', 'yang-path': 'zone-member'},
            {'key': 'shutdown', 'default': False, 'yang-type': YANG_TYPE.EMPTY},
            {'key': 'ntp_disable', 'yang-key': 'disable', 'yang-path': 'ntp', 'default': False,
             'yang-type': YANG_TYPE.EMPTY},
            {'key': 'arp_timeout', 'yang-key': 'timeout', 'yang-path': 'arp'},
        ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if int(self.mtu) < self.MIN_MTU:
            self.mtu = str(self.MIN_MTU)
        if int(self.mtu) > self.MAX_MTU:
            self.mtu = str(self.MAX_MTU)

    @classmethod
    def get_for_vrf(cls, context, vrf):
        return cls._get_all(context=context, xpath_filter=cls.VRF_XPATH_FILTER.format(vrf=vrf))

    @property
    def neutron_router_id(self):
        if self.vrf:
            return utils.vrf_id_to_uuid(self.vrf)

    def to_dict(self, context):
        vbi = OrderedDict()
        vbi[L3Constants.NAME] = self.name
        vbi[L3Constants.DESCRIPTION] = self.description
        vbi[L3Constants.MAC_ADDRESS] = self.mac_address
        vbi[L3Constants.MTU] = self.mtu

        if self.shutdown:
            vbi[L3Constants.SHUTDOWN] = ''
        else:
            vbi[L3Constants.SHUTDOWN] = {xml_utils.OPERATION: NC_OPERATION.REMOVE}

        if self.zone:
            vbi[L3Constants.ZONE_MEMBER] = {
                xml_utils.NS: xml_utils.NS_CISCO_ZONE,
                L3Constants.SECURITY: self.zone
            }
        else:
            vbi[L3Constants.ZONE_MEMBER] = {
                xml_utils.NS: xml_utils.NS_CISCO_ZONE,
                xml_utils.OPERATION: NC_OPERATION.REMOVE
            }

        redundancy = OrderedDict()
        if self.rii and self.redundancy_group and self.redundancy_group_decrement:
            redundancy[L3Constants.RII] = {L3Constants.ID: self.rii}
            redundancy[L3Constants.GROUP] = {
                L3Constants.ID: self.redundancy_group,
                L3Constants.DECREMENT: self.redundancy_group_decrement
            }
        else:
            redundancy[xml_utils.OPERATION] = NC_OPERATION.REMOVE
        vbi[L3Constants.REDUNDANCY] = redundancy

        ip = OrderedDict()
        ip[xml_utils.OPERATION] = NC_OPERATION.PUT

        if self.ip_address is not None:
            ip[L3Constants.ADDRESS] = OrderedDict()
            ip[L3Constants.ADDRESS][L3Constants.PRIMARY] = OrderedDict()
            ip[L3Constants.ADDRESS][L3Constants.PRIMARY][L3Constants.ADDRESS] = self.ip_address.address
            ip[L3Constants.ADDRESS][L3Constants.PRIMARY][L3Constants.MASK] = self.ip_address.mask

        if self.nat_stick or self.nat_inside:
            ip[L3Constants.NAT] = {L3Constants.NAT_MODE_STICK: '', xml_utils.NS: xml_utils.NS_CISCO_NAT}
        elif self.nat_outside:
            ip[L3Constants.NAT] = {L3Constants.NAT_MODE_OUTSIDE: '', xml_utils.NS: xml_utils.NS_CISCO_NAT}

        if self.route_map:
            ip[L3Constants.POLICY] = {L3Constants.ROUTE_MAP: self.route_map}

        access_groups = ip[L3Constants.ACCESS_GROUP] = {}
        if self.access_group_out:
            access_groups[L3Constants.OUT] = {
                L3Constants.ACL: {
                    L3Constants.ACL_NAME: self.access_group_out,
                    L3Constants.DIRECTION_OUT: None
                }
            }
        else:
            access_groups[L3Constants.OUT] = {
                L3Constants.ACL: {
                    xml_utils.OPERATION: NC_OPERATION.REMOVE
                }
            }

        if self.access_group_in:
            access_groups[L3Constants.IN] = {
                L3Constants.ACL: {
                    L3Constants.ACL_NAME: self.access_group_in,
                    L3Constants.DIRECTION_IN: None
                }
            }
        else:
            access_groups[L3Constants.IN] = {
                L3Constants.ACL: {
                    xml_utils.OPERATION: NC_OPERATION.REMOVE
                }
            }
        vbi[L3Constants.IP] = ip

        if self.ipv6_addresses or self.policy_map_v6 or self.traffic_filters_v6:
            ipv6 = {
                xml_utils.OPERATION: NC_OPERATION.PUT,
            }

            if self.ipv6_addresses:
                ipv6[L3Constants.ADDRESS] = {
                    L3Constants.PREFIX_LIST: [
                        addr.to_dict(context) for addr in self.ipv6_addresses
                    ]
                }

            if self.policy_map_v6:
                ipv6[L3Constants.POLICY] = {L3Constants.ROUTE_MAP: self.policy_map_v6}

            if self.traffic_filters_v6:
                ipv6[L3Constants.TRAFFIC_FILTER] = [tf.to_dict(context) for tf in self.traffic_filters_v6]

            vbi[L3Constants.IPV6] = ipv6
        else:
            vbi[L3Constants.IPV6] = {xml_utils.OPERATION: NC_OPERATION.REMOVE}

        vrf = OrderedDict()
        vrf[L3Constants.FORWARDING] = self.vrf
        vbi[L3Constants.VRF] = vrf

        vbi[L3Constants.NTP] = {xml_utils.NS: xml_utils.NS_CISCO_NTP}
        if self.ntp_disable:
            vbi[L3Constants.NTP][L3Constants.NTP_DISABLE] = ''
        else:
            vbi[L3Constants.NTP][xml_utils.OPERATION] = NC_OPERATION.REMOVE

        if self.arp_timeout and int(self.arp_timeout) > 0:
            vbi[L3Constants.ARP] = {L3Constants.TIMEOUT: int(self.arp_timeout)}
        else:
            vbi[L3Constants.ARP] = {L3Constants.TIMEOUT: {xml_utils.OPERATION: NC_OPERATION.REMOVE}}

        result = OrderedDict()
        result[L3Constants.BDVIF_INTERFACE] = vbi

        return dict(result)

    def to_delete_dict(self, context, existing=None):
        vbi = OrderedDict()
        vbi[L3Constants.NAME] = self.name
        vbi[L3Constants.DESCRIPTION] = self.description

        if existing is not None and existing.nat_outside:
            ip = OrderedDict()
            ip[L3Constants.NAT] = {L3Constants.NAT_MODE_OUTSIDE: '', xml_utils.NS: xml_utils.NS_CISCO_NAT}
            vbi[L3Constants.IP] = ip

        result = OrderedDict()
        result[L3Constants.BDVIF_INTERFACE] = vbi

        return dict(result)

    @property
    def in_neutron_namespace(self):
        max = utils.to_bridge_domain(asr1k_db.MAX_SECOND_DOT1Q)
        min = utils.to_bridge_domain(asr1k_db.MIN_SECOND_DOT1Q)

        return min <= int(self.id) <= max

    def postflight(self, context, method):
        if self.nat_outside:
            dyn_nat = asr1k_neutron_l3.models.netconf_yang.nat.InterfaceDynamicNat.get("NAT-{}".format(self.vrf))
            if dyn_nat is not None and dyn_nat.vrf is not None and dyn_nat.vrf == self.vrf:
                LOG.warning("Postflight found instance of dynamic NAT for interface {}, deleting it (instance is {})"
                            "".format(self.id, dyn_nat.id))
                dyn_nat.delete()

        # remove bridge domain membership, as this stops us from deleting the interface
        bd = BridgeDomain.get_for_bdvif(self.name, context, partial=True)
        if bd is not None:
            # in theory there should be only one member, as we're only getting a partial config, but who knows
            for member in bd.bdvif_members:
                if member.name == self.name:
                    member.mark_deleted = True
            bd._update(context=context)

    def init_config(self):
        if self.nat_inside:
            nat = L3Constants.NAT_MODE_INSIDE

        elif self.nat_outside:
            nat = L3Constants.NAT_MODE_OUTSIDE

        if self.route_map is not None:
            return cli_snippets.BDI_POLICY_CLI_INIT.format(id=self.id, description=self.description,
                                                           mac=self.mac_address, mtu=self.mtu,
                                                           vrf=self.vrf, ip=self.ip_address.address,
                                                           netmask=self.ip_address.mask, nat=nat,
                                                           route_map=self.route_map)
        else:
            return cli_snippets.BDI_NO_POLICY_CLI_INIT.format(id=self.id, description=self.description,
                                                              mac=self.mac_address, mtu=self.mtu,
                                                              vrf=self.vrf, ip=self.ip_address.address,
                                                              netmask=self.ip_address.mask, nat=nat)

    def is_orphan(self, all_bd_ids, *args, **kwargs):
        # An interface is an orphan if ALL of these conditions are met
        #   * ID is in neutron namespace
        #   * its ID is not referenced in the extra atts table
        # We can now delete vrf-less interfaces that are in the extra atts table as we
        # key the delete in the with help of _is_reassigned to the VRF
        return self.in_neutron_namespace and \
            int(self.name) not in all_bd_ids

    def is_reassigned(self, queried):
        return self.vrf != queried.vrf


class BDSecondaryIpAddress(NyBase):
    ITEM_KEY = L3Constants.SECONDARY
    LIST_KEY = L3Constants.ADDRESS

    ID_FILTER = """
                  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                    <interface>
                      <BD-VIF>
                        <name>{bridge_domain}</name>
                        <ip>
                          <address>
                            <secondary>
                                <address>{id}</address>
                            </secondary>
                          </address>
                        </ip>
                      </BD-VIF>
                    </interface>
                  </native>
                """

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'bridge_domain', 'validate': False, 'primary_key': True},
            {"key": 'address', 'id': True},
            {'key': 'mask'},
            {'key': 'secondary', 'default': True},

        ]

    @classmethod
    def remove_wrapper(cls, dict, context):
        dict = cls._remove_base_wrapper(dict, context)
        if dict is None:
            return
        dict = dict.get(L3Constants.INTERFACE, dict)
        dict = dict.get(L3Constants.BDVIF_INTERFACE, dict)
        dict = dict.get(L3Constants.IP, dict)
        dict = dict.get(cls.LIST_KEY, None)
        return dict

    def _wrapper_preamble(self, dict, context):
        result = {}
        result[self.LIST_KEY] = dict
        a = OrderedDict()
        a[L3Constants.NAME] = self.bridge_domain
        a[L3Constants.IP] = result
        result = OrderedDict({L3Constants.BDVIF_INTERFACE: a})
        result = OrderedDict({L3Constants.INTERFACE: result})
        return result

    @classmethod
    @execute_on_pair(return_raw=True)
    def get(cls, bridge_domain, id, context):
        return cls._get(id=id, bridge_domain=bridge_domain, context=context)

    @classmethod
    @execute_on_pair(return_raw=True)
    def exists(cls, bridge_domain, id, context):
        return cls._exists(id=id, bridge_domain=bridge_domain, context=context)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bridge_domain = kwargs.get('bridge_domain')

    def to_dict(self, context):
        ip = OrderedDict()
        secondary = OrderedDict()
        secondary[L3Constants.ADDRESS] = self.address
        secondary[L3Constants.MASK] = self.mask
        secondary['secondary'] = ''
        ip[L3Constants.SECONDARY] = secondary

        return ip


class BDPrimaryIpAddress(NyBase):
    ITEM_KEY = L3Constants.PRIMARY
    LIST_KEY = L3Constants.ADDRESS

    @classmethod
    def __parameters__(cls):
        return [
            {"key": 'address', 'id': True},
            {'key': 'mask'},
        ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bridge_domain = kwargs.get('bridge_domain')

    def to_dict(self, context):
        ip = OrderedDict()
        primary = OrderedDict()
        primary[L3Constants.ADDRESS] = self.address
        primary[L3Constants.MASK] = self.mask
        ip[L3Constants.PRIMARY] = primary

        return ip


class BDIpv6Address(NyBase):
    ITEM_KEY = L3Constants.PREFIX
    LIST_KEY = L3Constants.PREFIX_LIST

    @classmethod
    def __parameters__(cls):
        return [
            {"key": 'prefix', 'id': True},
        ]

    def to_dict(self, context):
        return {L3Constants.PREFIX: self.prefix.lower()}

    @property
    def address(self):
        if self.prefix:
            return self.prefix.split("/")[0]
        return None


class TrafficFilter(NyBase):
    @classmethod
    def __parameters__(cls):
        return [
            {"key": 'direction'},
            {'key': 'access_list', 'yang-key': 'common'},
        ]

    def to_dict(self, context):
        return {
            L3Constants.DIRECTION: self.direction,
            L3Constants.COMMON: self.access_list,
        }


class TunnelInterface(NyBase):
    LIST_KEY = L3Constants.INTERFACE
    ITEM_KEY = L3Constants.IFACE_TUNNEL
    ID_FILTER = """
                <native>
                    <interface>
                        <Tunnel>
                            <name>{id}</name>
                        </Tunnel>
                    </interface>
                </native>
             """

    GET_ALL_STUB = """
                <native>
                    <interface>
                        <Tunnel>
                            <name/>
                            <vrf>
                                <forwarding/>
                            </vrf>
                        </Tunnel>
                    </interface>
                </native>
             """

    VRF_XPATH_FILTER = "/native/interface/Tunnel/vrf[forwarding='{vrf}']"

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'name', 'id': True},
            {'key': 'description'},
            {'key': 'mtu', 'yang-path': 'ip'},
            {'key': 'ipv6_mtu', 'yang-path': 'ipv6'},
            {'key': 'tcp_mss', 'yang-key': 'adjust-mss', 'yang-path': 'ip/tcp'},
            {'key': 'ipv6_tcp_mss', 'yang-key': 'adjust-mss', 'yang-path': 'ipv6/tcp'},

            {'key': 'keepalive', 'yang-path': 'keepalive-config'},
            {'key': 'keepalive_period', 'yang-key': 'period', 'yang-path': 'keepalive-config'},
            {'key': 'keepalive_retries', 'yang-key': 'retries', 'yang-path': 'keepalive-config'},

            {'key': 'vrf', 'yang-path': 'vrf', 'yang-key': 'forwarding'},

            {'key': 'ipv4_address', 'yang-key': 'address', 'yang-path': 'ip/address/primary'},
            {'key': 'ipv4_netmask', 'yang-key': 'mask', 'yang-path': 'ip/address/primary'},
            {'key': 'ipv6_prefix', 'yang-key': 'prefix', 'yang-path': 'ipv6/address/prefix-list'},

            {'key': 'tunnel_src', 'yang-key': 'source', 'yang-path': 'tunnel'},
            {'key': 'tunnel_dest_ipv4', 'yang-key': 'ipv4', 'yang-path': 'tunnel/destination-config'},
            {'key': 'tunnel_dest_ipv6', 'yang-key': 'ipv6', 'yang-path': 'tunnel/destination-config'},

            {'key': 'tunnel_mode_ipsec_ipv4', 'yang-key': 'ipv4', 'yang-path': 'tunnel/mode/ipsec',
             'yang-type': YANG_TYPE.EMPTY},
            {'key': 'tunnel_mode_ipsec_ipv6', 'yang-key': 'ipv6', 'yang-path': 'tunnel/mode/ipsec',
             'yang-type': YANG_TYPE.EMPTY},
            {'key': 'tunnel_mode_ipsec_dual_overlay', 'yang-key': 'dual-overlay', 'yang-path': 'tunnel/mode/ipsec',
             'yang-type': YANG_TYPE.EMPTY},
            {'key': 'path_mtu_discovery', 'yang-path': 'tunnel', 'yang-type': YANG_TYPE.EMPTY},

            {'key': 'ipsec_policy_ipv4', 'yang-key': 'ipv4', 'yang-path': 'tunnel/protection/ipsec/policy'},
            {'key': 'ipsec_profile', 'yang-key': 'name', 'yang-path': 'tunnel/protection/ipsec/profile-option'},

            {'key': 'tunnel_vrf', 'yang-key': 'vrf', 'yang-path': 'tunnel/vrf-config/vrf-common'},
            {'key': 'shutdown', 'default': False, 'yang-type': YANG_TYPE.EMPTY},
        ]

    @classmethod
    def get_for_vrf(cls, context, vrf):
        return cls._get_all(context=context, xpath_filter=cls.VRF_XPATH_FILTER.format(vrf=vrf))

    def to_dict(self, context):
        iface = {
            L3Constants.NAME: self.name,
            L3Constants.DESCRIPTION: self.description,
        }

        keepalive = {}
        if self.keepalive:
            keepalive[L3Constants.KEEPALIVE] = self.keepalive
        if self.keepalive_period:
            keepalive[L3Constants.PERIOD] = self.keepalive_period
        if self.keepalive_retries:
            keepalive[L3Constants.RETRIES] = self.keepalive_retries
        if keepalive:
            iface[L3Constants.KEEPALIVE_CONFIG] = keepalive

        ip = {}
        if self.ipv4_address:
            ip[L3Constants.ADDRESS] = {
                L3Constants.PRIMARY: {
                    L3Constants.ADDRESS: self.ipv4_address,
                    L3Constants.MASK: self.ipv4_netmask,
                }
            }
        if self.tcp_mss:
            ip[L3Constants.TCP] = {L3Constants.ADJUST_MSS: self.tcp_mss}
        if self.mtu:
            ip[L3Constants.MTU] = self.mtu
        if ip:
            iface[L3Constants.IP] = ip

        ipv6 = {}
        if self.ipv6_prefix:
            ipv6[L3Constants.ADDRESS] = {L3Constants.PREFIX_LIST: {L3Constants.PREFIX: self.ipv6_prefix}}
        if self.ipv6_tcp_mss:
            ipv6[L3Constants.TCP] = {L3Constants.ADJUST_MSS: self.ipv6_tcp_mss}
        if self.ipv6_mtu:
            ipv6[L3Constants.MTU] = self.ipv6_mtu
        if ipv6:
            iface[L3Constants.IPV6] = ipv6

        if self.vrf:
            iface[L3Constants.VRF] = {L3Constants.FORWARDING: self.vrf}

        if self.shutdown:
            iface[L3Constants.SHUTDOWN] = ''
        else:
            iface[L3Constants.SHUTDOWN] = {xml_utils.OPERATION: NC_OPERATION.REMOVE}

        tun = {}
        if self.tunnel_src:
            tun[L3Constants.SOURCE] = self.tunnel_src
        if self.tunnel_dest_ipv4 or self.tunnel_dest_ipv6:
            dest_config = {}
            if self.tunnel_dest_ipv4:
                dest_config[L3Constants.IPV4] = self.tunnel_dest_ipv4
            if self.tunnel_dest_ipv6:
                dest_config[L3Constants.IPV6] = self.tunnel_dest_ipv6
            tun[L3Constants.DESTINATION_CONFIG] = dest_config
        if self.tunnel_mode_ipsec_ipv4:
            tun[L3Constants.MODE] = {L3Constants.IPSEC: {L3Constants.IPV4: ""}}
        if self.tunnel_mode_ipsec_ipv6:
            tun[L3Constants.MODE] = {L3Constants.IPSEC: {L3Constants.IPV6: ""}}
        if self.tunnel_mode_ipsec_dual_overlay:
            tun[L3Constants.MODE] = {L3Constants.IPSEC: {L3Constants.DUAL_OVERLAY: ""}}
        if self.path_mtu_discovery:
            tun[L3Constants.PATH_MTU_DISCOVERY] = ""

        prot_ipsec = {}
        if self.ipsec_policy_ipv4:
            prot_ipsec[L3Constants.POLICY] = {L3Constants.IPV4: self.ipsec_policy_ipv4}
        if self.ipsec_profile:
            prot_ipsec[L3Constants.PROFILE_OPTION] = {L3Constants.NAME: self.ipsec_profile}
        if prot_ipsec:
            prot_ipsec[xml_utils.NS] = xml_utils.NS_CISCO_CRYPTO
            tun[L3Constants.PROTECTION] = {L3Constants.IPSEC: prot_ipsec}

        if self.tunnel_vrf:
            tun[L3Constants.VRF_CONFIG] = {L3Constants.VRF_COMMON: {L3Constants.VRF: self.tunnel_vrf}}

        if tun:
            tun[xml_utils.NS] = xml_utils.NS_CISCO_TUNNEL
            iface[L3Constants.TUNNEL] = tun

        return {L3Constants.IFACE_TUNNEL: iface}

    @property
    def neutron_router_id(self):
        if self.vrf:
            return utils.vrf_id_to_uuid(self.vrf)
        return None

    def postflight(self, context, method):
        if self.name:
            # clear all routes referencing this tunnel interface
            for route_cls in (route.VrfRouteV4, route.VrfRouteV6):
                route_cls.delete_routes_by_nexthop(context, f"Tunnel{self.name}")

    def is_orphan_vpnaas(self, all_ipsec_siteconnection_ids, all_tunnel_ids):
        if not self.name:
            return False
        tun_id = int(self.name)
        return tun_id not in all_tunnel_ids and tun_id in cfg.CONF.asr1k_l3.vpnaas_tunnel_id_range
