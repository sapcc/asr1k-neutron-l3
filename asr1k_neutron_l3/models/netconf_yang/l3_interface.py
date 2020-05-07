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
import copy

from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair, YANG_TYPE, NC_OPERATION
import asr1k_neutron_l3.models.netconf_yang.nat
from asr1k_neutron_l3.models.netconf_yang import xml_utils

from asr1k_neutron_l3.common import cli_snippets, utils
from asr1k_neutron_l3.common import asr1k_exceptions as exc

from asr1k_neutron_l3.plugins.db import asr1k_db
from oslo_log import log as logging
LOG = logging.getLogger(__name__)


class L3Constants(object):
    INTERFACE = "interface"
    BDI_INTERFACE = "BDI"
    BDVIF_INTERFACE = "BD-VIF"

    ID = "id"
    NAME = "name"
    DESCRIPTION = "description"
    MAC_ADDRESS = "mac-address"
    MTU = "mtu"
    IP = "ip"
    ADDRESS = "address"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    MASK = "mask"
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
    ACL = "acl"
    ACL_NAME = "acl-name"
    DIRECTION_OUT = "out"


class VBInterface(NyBase):
    ID_FILTER = """
                <native>
                    <interface>
                        <{iftype}>
                            <name>{id}</name>
                        </{iftype}>
                    </interface>
                </native>
             """

    GET_ALL_STUB = """
                <native>
                    <interface>
                        <{iftype}>
                            <name/>
                            <vrf>
                                <forwarding/>
                            </vrf>
                        </{iftype}>
                    </interface>
                </native>
             """

    VRF_FILTER = """
                <native>
                    <interface>
                        <{iftype}>
                            <vrf>
                                <forwarding>{vrf}</forwarding>
                            </vrf>
                        </{iftype}>
                    </interface>
                </native>
             """

    VRF_XPATH_FILTER = "/native/interface/{iftype}/vrf[forwarding='{vrf}']"

    LIST_KEY = L3Constants.INTERFACE
    MIN_MTU = 1500
    MAX_MTU = 9216

    @classmethod
    def get_item_key(cls, context):
        return context.bd_iftype

    @classmethod
    def get_primary_filter(cls, id, context, **kwargs):
        return cls.ID_FILTER.format(id=id, iftype=context.bd_iftype)

    @classmethod
    def get_all_stub_filter(cls, context):
        return cls.GET_ALL_STUB.format(iftype=context.bd_iftype)

    @classmethod
    def get_for_vrf(cls, context, vrf=None):
        return cls._get_all(context=context, xpath_filter=cls.VRF_XPATH_FILTER.format(vrf=vrf,
                                                                                      iftype=context.bd_iftype))

    @classmethod
    def __parameters__(cls):
        # secondary IPs will be validated in NAT
        # NAT mode should be validated when supported in yang models - no point using netconf for now
        return [
            {"key": "name", "id": True},
            {'key': 'description'},
            {'key': 'mac_address'},
            {'key': 'mtu', 'default': VBInterface.MIN_MTU},
            {'key': 'vrf', 'yang-path': 'vrf', 'yang-key': "forwarding"},
            {'key': 'ip_address', 'yang-path': 'ip/address', 'yang-key': "primary", 'type': VBIPrimaryIpAddress},
            {'key': 'secondary_ip_addresses', 'yang-path': 'ip/address', 'yang-key': "secondary",
             'type': [VBISecondaryIpAddress], 'default': [], 'validate':False},
            {'key': 'nat_inside', 'yang-key': 'inside', 'yang-path': 'ip/nat', 'default': False,
             'yang-type': YANG_TYPE.EMPTY},
            {'key': 'nat_outside', 'yang-key': 'outside', 'yang-path': 'ip/nat', 'default': False,
             'yang-type': YANG_TYPE.EMPTY},
            {'key': 'nat_stick', 'yang-key': 'stick', 'yang-path': 'ip/nat', 'default': False,
             'yang-type': YANG_TYPE.EMPTY},
            {'key': 'route_map', 'yang-key': 'route-map', 'yang-path': 'ip/policy'},
            {'key': 'access_group_out', 'yang-key': 'acl-name', 'yang-path': 'ip/access-group/out/acl'},
            {'key': 'redundancy_group'},
            {'key': 'shutdown', 'default': False, 'yang-type': YANG_TYPE.EMPTY},
            {'key': 'desire_nat_stick', 'default': False},
        ]

    def __init__(self, **kwargs):
        super(VBInterface, self).__init__(**kwargs)
        if int(self.mtu) < self.MIN_MTU:
            self.mtu = str(self.MIN_MTU)
        if int(self.mtu) > self.MAX_MTU:
            self.mtu = str(self.MAX_MTU)

    @property
    def neutron_router_id(self):
        if self.vrf:
            return utils.vrf_id_to_uuid(self.vrf)

    @staticmethod
    def is_bdvif(context):
        return context.version_min_1612 and context.use_bdvif

    def preflight(self, context):
        """Remove BDI with same name when BD-VIF is in use (migration code)"""
        if not context.use_bdvif:
            return

        # XXX: to get the BDI we need to act like this context does
        # this should be removed after we're done with the migration
        nobdvif_context = copy.copy(context)
        nobdvif_context._use_bdvif = False

        bdi = self._internal_get(context=nobdvif_context)
        if bdi:
            LOG.debug("Removing BDI%s from %s before adding new BD-VIF%s", bdi.name, context.host, self.name)
            bdi._delete(context=nobdvif_context, postflight=False)  # disable postflight checks

    def to_dict(self, context):
        vbi = OrderedDict()
        vbi[L3Constants.NAME] = self.name
        vbi[L3Constants.DESCRIPTION] = self.description
        vbi[L3Constants.MAC_ADDRESS] = self.mac_address
        vbi[L3Constants.MTU] = self.mtu
        if self.shutdown:
            vbi[L3Constants.SHUTDOWN] = ''

        ip = OrderedDict()
        ip[xml_utils.OPERATION] = NC_OPERATION.PUT

        if self.ip_address is not None:
            ip[L3Constants.ADDRESS] = OrderedDict()
            ip[L3Constants.ADDRESS][L3Constants.PRIMARY] = OrderedDict()
            ip[L3Constants.ADDRESS][L3Constants.PRIMARY][L3Constants.ADDRESS] = self.ip_address.address
            ip[L3Constants.ADDRESS][L3Constants.PRIMARY][L3Constants.MASK] = self.ip_address.mask

        if self.nat_stick or (self.nat_inside and context.version_min_1612 and self.desire_nat_stick):
            ip[L3Constants.NAT] = {L3Constants.NAT_MODE_STICK: '', xml_utils.NS: xml_utils.NS_CISCO_NAT}
        elif self.nat_inside:
            ip[L3Constants.NAT] = {L3Constants.NAT_MODE_INSIDE: '', xml_utils.NS: xml_utils.NS_CISCO_NAT}
        elif self.nat_outside:
            ip[L3Constants.NAT] = {L3Constants.NAT_MODE_OUTSIDE: '', xml_utils.NS: xml_utils.NS_CISCO_NAT}

        if self.route_map:
            ip[L3Constants.POLICY] = {L3Constants.ROUTE_MAP: self.route_map}

        if self.access_group_out:
            ip[L3Constants.ACCESS_GROUP] = {
                L3Constants.OUT: {
                    L3Constants.ACL: {
                        L3Constants.ACL_NAME: self.access_group_out,
                        L3Constants.DIRECTION_OUT: None
                    }
                }
            }

        vrf = OrderedDict()
        vrf[L3Constants.FORWARDING] = self.vrf

        vbi[L3Constants.IP] = ip
        vbi[L3Constants.VRF] = vrf

        result = OrderedDict()
        result[context.bd_iftype] = vbi

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
        result[context.bd_iftype] = vbi

        return dict(result)

    @property
    def in_neutron_namespace(self):
        max = utils.to_bridge_domain(asr1k_db.MAX_SECOND_DOT1Q)
        min = utils.to_bridge_domain(asr1k_db.MIN_SECOND_DOT1Q)

        return min <= int(self.id) <= max

    def postflight(self, context, method):
        dyn_nat = asr1k_neutron_l3.models.netconf_yang.nat.InterfaceDynamicNat.get("NAT-{}".format(self.vrf))
        if self.nat_outside and dyn_nat is not None:
            if dyn_nat.vrf is not None and dyn_nat.vrf == self.vrf:
                LOG.warning("Postflight failed for interface {} due to configured interface presence of dynamic NAT {}"
                            "".format(self.id, dyn_nat))
                raise exc.EntityNotEmptyException(device=context.host, entity=self, action="delete")

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

    def is_orphan(self, all_router_ids, all_segmentation_ids, all_bd_ids, context):
        # An interface is an orphan if ALL of these conditions are met
        #   * it does not belong to any VRF or the router does not exist anymore
        #   * ID is in neutron namespace
        #   * its ID is not referenced in the extra atts table
        # We don't delete vrf-less interfaces that are in the extra atts table as they could be reused
        # while we're deleting them
        return ((self.neutron_router_id and self.neutron_router_id not in all_router_ids) or
                not self.neutron_router_id) and \
            self.in_neutron_namespace and \
            int(self.name) not in all_bd_ids


class VBISecondaryIpAddress(NyBase):
    ITEM_KEY = L3Constants.SECONDARY
    LIST_KEY = L3Constants.ADDRESS

    ID_FILTER = """
                  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                    <interface>
                      <{iftype}>
                        <name>{bridge_domain}</name>
                        <ip>
                          <address>
                            <secondary>
                                <address>{id}</address>
                            </secondary>
                          </address>
                        </ip>
                      </{iftype}>
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
        dict = super(VBISecondaryIpAddress, cls)._remove_base_wrapper(dict, context)
        if dict is None:
            return
        dict = dict.get(L3Constants.INTERFACE, dict)
        dict = dict.get(context.bd_iftype, dict)
        dict = dict.get(L3Constants.IP, dict)
        dict = dict.get(cls.LIST_KEY, None)
        return dict

    def _wrapper_preamble(self, dict, context):
        result = {}
        result[self.LIST_KEY] = dict
        a = OrderedDict()
        a[L3Constants.NAME] = self.bridge_domain
        a[L3Constants.IP] = result
        result = OrderedDict({context.bd_iftype: a})
        result = OrderedDict({L3Constants.INTERFACE: result})
        return result

    @classmethod
    def get_primary_filter(cls, id, bridge_domain, context, **kwargs):
        return cls.ID_FILTER.format(id=id, iftype=context.bd_iftype, bridge_domain=bridge_domain)

    @classmethod
    @execute_on_pair(return_raw=True)
    def get(cls, bridge_domain, id, context):
        return super(VBISecondaryIpAddress, cls)._get(id=id, bridge_domain=bridge_domain, context=context)

    @classmethod
    @execute_on_pair(return_raw=True)
    def exists(cls, bridge_domain, id, context):
        return super(VBISecondaryIpAddress, cls)._exists(id=id, bridge_domain=bridge_domain, context=context)

    def __init__(self, **kwargs):
        super(VBISecondaryIpAddress, self).__init__(**kwargs)
        self.bridge_domain = kwargs.get('bridge_domain')

    def to_dict(self, context):
        ip = OrderedDict()
        secondary = OrderedDict()
        secondary[L3Constants.ADDRESS] = self.address
        secondary[L3Constants.MASK] = self.mask
        secondary['secondary'] = ''
        ip[L3Constants.SECONDARY] = secondary

        return ip


class VBIPrimaryIpAddress(NyBase):
    ITEM_KEY = L3Constants.PRIMARY
    LIST_KEY = L3Constants.ADDRESS

    @classmethod
    def __parameters__(cls):
        return [
            {"key": 'address', 'id': True},
            {'key': 'mask'},
        ]

    def __init__(self, **kwargs):
        super(VBIPrimaryIpAddress, self).__init__(**kwargs)
        self.bridge_domain = kwargs.get('bridge_domain')

    def to_dict(self, context):
        ip = OrderedDict()
        primary = OrderedDict()
        primary[L3Constants.ADDRESS] = self.address
        primary[L3Constants.MASK] = self.mask
        ip[L3Constants.PRIMARY] = primary

        return ip
