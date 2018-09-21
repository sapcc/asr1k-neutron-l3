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
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair, retry_on_failure, YANG_TYPE, NC_OPERATION
import asr1k_neutron_l3.models.netconf_yang.nat
from asr1k_neutron_l3.models.netconf_yang.l2_interface import LoopbackInternalInterface
from asr1k_neutron_l3.models.netconf_yang import xml_utils
from asr1k_neutron_l3.models.connection import ConnectionManager
from asr1k_neutron_l3.common import asr1k_exceptions as exc
from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.plugins.db import asr1k_db
from oslo_log import log as logging
LOG = logging.getLogger(__name__)

class L3Constants(object):
    INTERFACE = "interface"
    BDI_INTERFACE = "BDI"

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
    POLICY = "policy"
    ROUTE_MAP = "route-map"


class BDIInterface(NyBase):

    ID_FILTER = """
                <native>
                    <interface>
                        <BDI>
                            <name>{id}</name>
                        </BDI>
                    </interface>
                </native>            
             """

    LIST_KEY = L3Constants.INTERFACE
    ITEM_KEY = L3Constants.BDI_INTERFACE
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
            {'key': 'mtu', 'default': BDIInterface.MIN_MTU},
            {'key': 'vrf','yang-path':'vrf','yang-key':"forwarding"},
            {'key': 'ip_address','yang-path':'ip/address','yang-key':"primary",'type':BDIPrimaryIpAddress},
            {'key': 'secondary_ip_addresses','yang-path':'ip/address','yang-key':"secondary",'type':[BDISecondaryIpAddress], 'default': [], 'validate':False},
            {'key': 'nat_inside','yang-key':'inside','yang-path':'ip/nat','default':False,'yang-type':YANG_TYPE.EMPTY},
            {'key': 'nat_outside', 'yang-key': 'outside', 'yang-path': 'ip/nat', 'default': False,'yang-type':YANG_TYPE.EMPTY},
            {'key': 'route_map', 'yang-key': 'route-map','yang-path': 'ip/policy'},
            {'key': 'redundancy_group'},
            {'key': 'shutdown','default':False,'yang-type':YANG_TYPE.EMPTY}

        ]



    def __init__(self, **kwargs):
        super(BDIInterface, self).__init__(**kwargs)
        if int(self.mtu) < self.MIN_MTU:
            self.mtu = str(self.MIN_MTU)
        if int(self.mtu) > self.MAX_MTU:
            self.mtu = str(self.MAX_MTU)

    @property
    def neutron_router_id(self):
        if self.vrf:
            return utils.vrf_id_to_uuid(self.vrf)

    def to_dict(self):
        bdi = OrderedDict()
        bdi[L3Constants.NAME] = self.name
        bdi[L3Constants.DESCRIPTION] = self.description
        bdi[L3Constants.MAC_ADDRESS] = self.mac_address
        bdi[L3Constants.MTU] = self.mtu
        if self.shutdown:
            bdi[L3Constants.SHUTDOWN] = ''

        ip = OrderedDict()
        if self.ip_address is not None:
            ip[L3Constants.ADDRESS] = OrderedDict()
            ip[L3Constants.ADDRESS][L3Constants.PRIMARY] = OrderedDict()
            ip[L3Constants.ADDRESS][L3Constants.PRIMARY][L3Constants.ADDRESS] = self.ip_address.address
            ip[L3Constants.ADDRESS][L3Constants.PRIMARY][L3Constants.MASK] = self.ip_address.mask

        if self.nat_inside:
            ip[L3Constants.NAT] = {L3Constants.NAT_MODE_INSIDE:'',xml_utils.NS:xml_utils.NS_CISCO_NAT}

        elif self.nat_outside:
            ip[L3Constants.NAT] = {L3Constants.NAT_MODE_OUTSIDE:'',xml_utils.NS:xml_utils.NS_CISCO_NAT}

        if self.route_map:
            ip[L3Constants.POLICY] = {L3Constants.ROUTE_MAP: self.route_map}

        vrf = OrderedDict()
        vrf[L3Constants.FORWARDING] = self.vrf

        bdi[L3Constants.IP] = ip
        bdi[L3Constants.VRF] = vrf

        result = OrderedDict()
        result[L3Constants.BDI_INTERFACE] = bdi

        return dict(result)

    def to_delete_dict(self,existing=None):
        bdi = OrderedDict()
        bdi[L3Constants.NAME] = self.name
        bdi[L3Constants.DESCRIPTION] = self.description

        if existing is not None and existing.nat_outside:
            ip = OrderedDict()
            ip[L3Constants.NAT] = {L3Constants.NAT_MODE_OUTSIDE:'',xml_utils.NS:xml_utils.NS_CISCO_NAT}
            bdi[L3Constants.IP] = ip

        result = OrderedDict()
        result[L3Constants.BDI_INTERFACE] = bdi

        return dict(result)

    @execute_on_pair()
    def update(self,context=None,method=NC_OPERATION.PATCH):
        result = super(BDIInterface, self)._update(context=context)
        if result is not None: # We had a diff and need may need to  PUT to unshut
            result = super(BDIInterface, self)._update(context=context,method=NC_OPERATION.PUT)
        return result

    @execute_on_pair()
    def delete(self,context=None):
            # To work around removal of interface NAT we clear everything off the BDI and let the
            # cleaner tidy up

            existing = self.get(self.name)
            if existing is None or existing.nat_outside:
                self.description = "Deleted from vrf {}".format(self.vrf)
                return super(BDIInterface, self)._update(context=context,json=self.to_delete_dict(existing=existing),method=NC_OPERATION.PUT,postflight=True)
            else:
                return super(BDIInterface, self)._delete(context=context)


    @property
    def in_neutron_namespace(self):
        max = utils.to_bridge_domain(asr1k_db.MAX_SECOND_DOT1Q)
        min = utils.to_bridge_domain(asr1k_db.MIN_SECOND_DOT1Q)

        return min <= int(self.id) <= max


    def postflight(self, context):
        l2 = LoopbackInternalInterface.get(self.name)
        if l2 is not None:
            LOG.warning(
                "Postflight failed for interface {} due to configured L2 EFP {}".format(self.name,l2))
            raise exc.EntityNotEmptyException(device=context.host, entity=self, action="delete")
        else:
            LOG.warning(
                "Postflight check passed for interface {} no configured L2 EFP {}".format(self.name,self.name))


        # dyn_nat = asr1k_neutron_l3.models.netconf_yang.nat.InterfaceDynamicNat.get("NAT-{}".format(self.vrf))
        # if dyn_nat is not None:
        #         if dyn_nat.vrf is not None and dyn_nat.vrf == self.vrf:
        #             LOG.warning(
        #                 "Postflight failed for interface {} due to configured interface presence of dynamic NAT {}".format(
        #                     self.id,
        #                     dyn_nat))
        #             raise exc.EntityNotEmptyException(device=context.host, entity=self, action="delete")

    #     LOG.debug("Running postflight for BDI {}".format(self.name))
    #     device = self._internal_get(context=context)
    #     if device is not None:
    #         device.route_map = None
    #         device._update(context=context,method=NC_OPERATION.PUT)



class BDISecondaryIpAddress(NyBase):
    ITEM_KEY = L3Constants.SECONDARY
    LIST_KEY = L3Constants.ADDRESS

    ID_FILTER = """
                  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                    <interface>
                      <BDI>
                        <name>{bridge_domain}</name>
                        <ip>
                          <address>
                            <secondary>
                                <address>{id}</address>
                            </secondary>
                          </address>
                        </ip>
                      </BDI>
                    </interface>
                  </native>    
                """

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'bridge_domain','validate': False,'primary_key':True},
            {"key": 'address', 'id': True},
            {'key': 'mask'},
            {'key': 'secondary','default':True},

        ]


    @classmethod
    def remove_wrapper(cls,dict):
        dict = super(BDISecondaryIpAddress, cls)._remove_base_wrapper(dict)
        if dict is None:
            return
        dict = dict.get(L3Constants.INTERFACE,dict)
        dict = dict.get(L3Constants.BDI_INTERFACE,dict)
        dict = dict.get(L3Constants.IP, dict)
        dict = dict.get(cls.LIST_KEY, None)
        return dict

    def _wrapper_preamble(self,dict):
        result = {}
        result[self.LIST_KEY] = dict
        a = OrderedDict()
        a[L3Constants.NAME] = self.bridge_domain
        a[L3Constants.IP] = result
        result = OrderedDict({L3Constants.BDI_INTERFACE: a})
        result = OrderedDict({L3Constants.INTERFACE: result})
        return result

    @classmethod
    def get_primary_filter(cls,**kwargs):
        return cls.ID_FILTER.format(**{'id': kwargs.get('id'),'bridge_domain':kwargs.get('bridge_domain')})


    @classmethod
    @execute_on_pair(return_raw=True)
    def get(cls,bridge_domain,id, context=None):
        return super(BDISecondaryIpAddress, cls)._get(id=id, bridge_domain=bridge_domain,context=context)

    @classmethod
    @execute_on_pair(return_raw=True)
    def exists(cls, bridge_domain,id, context=None):
        return super(BDISecondaryIpAddress, cls)._exists(id=id, bridge_domain=bridge_domain, context=context)


    def __init__(self, **kwargs):
        super(BDISecondaryIpAddress, self).__init__(**kwargs)
        self.bridge_domain = kwargs.get('bridge_domain')

    def to_dict(self):
        ip = OrderedDict()
        secondary = OrderedDict()
        secondary[L3Constants.ADDRESS] = self.address
        secondary[L3Constants.MASK] = self.mask
        secondary['secondary'] = ''
        ip[L3Constants.SECONDARY] = secondary

        return ip



class BDIPrimaryIpAddress(NyBase):
    ITEM_KEY = L3Constants.PRIMARY
    LIST_KEY = L3Constants.ADDRESS

    @classmethod
    def __parameters__(cls):
        return [
            {"key": 'address', 'id': True},
            {'key': 'mask'},

        ]



    def __init__(self, **kwargs):


        super(BDIPrimaryIpAddress, self).__init__(**kwargs)
        self.bridge_domain = kwargs.get('bridge_domain')


    def to_dict(self):
        ip = OrderedDict()
        primary = OrderedDict()
        primary[L3Constants.ADDRESS] = self.address
        primary[L3Constants.MASK] = self.mask
        ip[L3Constants.PRIMARY] = primary

        return ip