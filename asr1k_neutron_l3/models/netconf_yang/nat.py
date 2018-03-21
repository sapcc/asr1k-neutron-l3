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

from oslo_log import log as logging
from asr1k_neutron_l3.models.netconf_legacy import nat as nc_nat
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair, YANG_TYPE
from asr1k_neutron_l3.models.netconf_yang import xml_utils
from asr1k_neutron_l3.common import utils


LOG = logging.getLogger(__name__)


class NATConstants(object):
    IP = 'ip'
    NAT = 'nat'
    POOL = "pool"
    INTERFACE = "interface"
    BDI = "BDI"
    ID = "id"
    START_ADDRESS = "start-address"
    END_ADDRESS = "end-address"
    NETMASK = "netmask"

    LIST = "list"
    SOURCE = "source"
    INSIDE = "inside"
    REDUNDANCY = "redundancy"
    MAPPING_ID = "mapping-id"
    VRF = "vrf"
    OVERLOAD = "overload"

    TRANSPORT_LIST = "nat-static-transport-list"
    STATIC = "static"

    LOCAL_IP = "local-ip"
    GLOBAL_IP = "global-ip"
    FORCED = "forced"
    MATCH_IN_VRF = "match-in-vrf"


class NatPool(NyBase):
    LIST_KEY = NATConstants.NAT
    ITEM_KEY = NATConstants.POOL



    ID_FILTER = """
                    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native" xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
                        <ip>
                          <ios-nat:nat>
                            <ios-nat:pool>
                               <id>{id}</id>
                            </ios-nat:pool>   
                          </ios-nat:nat>
                        </ip>
                    </native>
                """

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'id', 'mandatory': True},
            {'key': 'start_address'},
            {'key': 'end_address'},
            {'key': 'netmask'}
        ]

    @classmethod
    def remove_wrapper(cls,dict):
        dict = super(NatPool, cls)._remove_base_wrapper(dict)
        if dict is None:
            return
        dict = dict.get(NATConstants.IP,dict)
        dict = dict.get(cls.LIST_KEY, dict)

        return dict

    def _wrapper_preamble(self,dict):
        result = {}
        dict[xml_utils.NS] = xml_utils.NS_CISCO_NAT
        result[self.LIST_KEY] = dict
        result = {NATConstants.IP: result}
        return result


    def __init__(self, **kwargs):
        super(NatPool, self).__init__(**kwargs)

    def to_dict(self):
        pool = OrderedDict()
        pool[NATConstants.ID] = self.id

        pool[NATConstants.START_ADDRESS] = self.start_address
        pool[NATConstants.END_ADDRESS] = self.end_address
        pool[NATConstants.NETMASK] = self.netmask

        result = OrderedDict()
        result[NATConstants.POOL] = pool

        return dict(result)

    def to_delete_dict(self):
        pool = OrderedDict()
        pool[NATConstants.ID] = self.id

        result = OrderedDict()
        result[NATConstants.POOL] = pool

        return dict(result)


class NatBase(NyBase):

    def __init__(self, **kwargs):
        super(NatBase, self).__init__(**kwargs)

        # if self.mapping_id is None:
        #     self.mapping_id = randint(1, 2147483647)


class DynamicNat(NatBase):

    ID_FILTER = """
                  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native" xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat" xmlns:ios-eth="http://cisco.com/ns/yang/Cisco-IOS-XE-ethernet">
                    <ip>
                      <ios-nat:nat>
                        <ios-nat:inside>
                          <ios-nat:source>
                            <ios-nat:list>
                              <ios-nat:id>{id}</ios-nat:id>
                              <vrf>{vrf}</vrf>
                            </ios-nat:list>
                          </ios-nat:source>
                        </ios-nat:inside>
                      </ios-nat:nat>
                    </ip>
                  </native>
    
                """

    LIST_KEY = NATConstants.SOURCE
    ITEM_KEY = NATConstants.LIST

    @classmethod
    def __parameters__(cls):
        return [
            {"key": "id", "mandatory": True},
            {'key': 'vrf'},
            {'key': 'bridge_domain','yang-key':'BDI','yang-path':'interface'},
            {'key': 'redundancy'},
            {'key': 'mapping_id'},
            {'key': 'overload','default':True,'yang-type':YANG_TYPE.EMPTY}
        ]


    @classmethod
    def get_primary_filter(cls,**kwargs):
        return cls.ID_FILTER.format(**{'id': kwargs.get('id'),'vrf':kwargs.get('vrf')})

    @classmethod
    def remove_wrapper(cls,dict):
        dict = super(DynamicNat, cls)._remove_base_wrapper(dict)
        if dict is None:
            return
        dict = dict.get(NATConstants.IP,dict)
        dict = dict.get(NATConstants.NAT, dict)
        dict = dict.get(NATConstants.INSIDE, dict)

        dict = dict.get(cls.LIST_KEY, dict)

        return dict

    def _wrapper_preamble(self,dict):
        result = {}
        result[self.LIST_KEY] = dict
        result = {NATConstants.INSIDE: result}
        result[xml_utils.NS] = xml_utils.NS_CISCO_NAT
        result = {NATConstants.NAT: result}
        result = {NATConstants.IP: result}
        return result


    def __init__(self, **kwargs):
        super(DynamicNat, self).__init__(**kwargs)
        self.mapping_id = utils.uuid_to_mapping_id(self.vrf)
        self.redundancy=None
        self.raise_on_delete = False
        self.raise_on_update = False

    def to_dict(self):
        entry = OrderedDict()
        entry[NATConstants.ID] = self.id

        entry[NATConstants.VRF] = self.vrf

        if self.bridge_domain is not None:
            entry[NATConstants.INTERFACE] = {NATConstants.BDI:self.bridge_domain}

        if self.redundancy is not None:
            entry[NATConstants.REDUNDANCY] = self.redundancy
            entry[NATConstants.MAPPING_ID] = self.mapping_id
        if self.overload:
            entry[NATConstants.OVERLOAD] = ""




        result = OrderedDict()
        result[NATConstants.LIST] = []
        result[NATConstants.LIST].append(entry)

        return dict(result)

    def to_delete_dict(self):
        entry = OrderedDict()
        entry[NATConstants.ID] = self.id
        entry[NATConstants.VRF] = self.vrf
        result = OrderedDict()
        result[NATConstants.LIST] = []
        result[NATConstants.LIST].append(entry)

        return dict(result)


class StaticNat(NatBase):
    ID_FILTER = """
                  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native" xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
                    <ip>
                      <ios-nat:nat>
                        <ios-nat:inside>
                          <ios-nat:source>
                            <ios-nat:static>
                              <ios-nat:nat-static-transport-list>
                                <ios-nat:local-ip>{local_ip}</ios-nat:local-ip>
                                <ios-nat:global-ip>{global_ip}</ios-nat:global-ip>
                              </ios-nat:nat-static-transport-list>
                            </ios-nat:static>
                          </ios-nat:source>
                        </ios-nat:inside>
                      </ios-nat:nat>
                    </ip>
                  </native>
                """

    ALL_FILTER = """
                  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native" xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
                    <ip>
                      <ios-nat:nat>
                        <ios-nat:inside>
                          <ios-nat:source>
                            <ios-nat:static>
                              <ios-nat:nat-static-transport-list>
                               <ios-nat:vrf>{vrf}</ios-nat:vrf> 
                              </ios-nat:nat-static-transport-list>
                            </ios-nat:static>
                          </ios-nat:source>
                        </ios-nat:inside>
                      </ios-nat:nat>
                    </ip>
                  </native>
                """

    LIST_KEY = NATConstants.STATIC
    ITEM_KEY = NATConstants.TRANSPORT_LIST



    @classmethod
    def __parameters__(cls):
        return [
            {"key": "local_ip", "mandatory": True},
            {"key": "global_ip", "mandatory": True},
            {'key': 'vrf'},
            {'key': 'redundancy'},
            {'key': 'mapping_id'},
            {'key': 'match_in_vrf','yang-key':'match-in-vrf','default':True}
        ]

    @classmethod
    def get_primary_filter(cls,**kwargs):
        return cls.ID_FILTER.format(**{'local_ip': kwargs.get('local_ip'),'global_ip':kwargs.get('global_ip')})

    @classmethod
    def get_all_filter(cls,**kwargs):
        return cls.ALL_FILTER.format(**{'vrf': kwargs.get('vrf')})


    @classmethod
    @execute_on_pair(return_raw=True)
    def get(cls,local_ip,global_ip, context=None):
        return super(StaticNat, cls)._get(local_ip=local_ip, global_ip=global_ip,context=context)

    @classmethod
    @execute_on_pair(return_raw=True)
    def get_all(cls,filter={}, context=None):
        return super(StaticNat, cls)._get_all(filter=filter, context=context)

    @classmethod
    @execute_on_pair(return_raw=True)
    def exists(cls, local_ip,global_ip, context=None):
        return super(StaticNat, cls)._exists(local_ip=local_ip, global_ip=global_ip, context=context)


    @classmethod
    def remove_wrapper(cls,dict):
        dict = super(StaticNat, cls)._remove_base_wrapper(dict)
        if dict is  None:
            return
        dict = dict.get(NATConstants.IP,dict)
        dict = dict.get(NATConstants.NAT, dict)
        dict = dict.get(NATConstants.INSIDE, dict)
        dict = dict.get(NATConstants.SOURCE, dict)
        dict = dict.get(cls.LIST_KEY, dict)

        return dict

    def _wrapper_preamble(self,dict):
        result = {}
        result[self.LIST_KEY] = dict
        result = {NATConstants.SOURCE: result}
        result = {NATConstants.INSIDE: result}
        result[xml_utils.NS] = xml_utils.NS_CISCO_NAT
        result = {NATConstants.NAT: result}
        result = {NATConstants.IP: result}
        return result

    def __init__(self, **kwargs):
        super(StaticNat, self).__init__(**kwargs)
        self.bridge_domain = kwargs.get("bridge_domain")
        self.mac_address = kwargs.get("mac_address")

        self.ncc = nc_nat.StaticNat(self)


    def __id_function__(self, id_field, **kwargs):
        self.id = "{},{}".format(self.local_ip, self.global_ip)

    def to_dict(self):
        entry = OrderedDict()
        entry[NATConstants.LOCAL_IP] = self.local_ip
        entry[NATConstants.GLOBAL_IP] = self.global_ip
        entry[NATConstants.VRF] = self.vrf

        if self.redundancy is not None:
            entry[NATConstants.REDUNDANCY] = self.redundancy
            entry[NATConstants.MAPPING_ID] = self.mapping_id

        if self.match_in_vrf:
            entry[NATConstants.MATCH_IN_VRF] = ""
        entry[NATConstants.MATCH_IN_VRF] = ""

        result = OrderedDict()
        result[NATConstants.TRANSPORT_LIST] = []
        result[NATConstants.TRANSPORT_LIST].append(entry)

        return dict(result)

    def to_delete_dict(self):
        entry = OrderedDict()
        entry[NATConstants.LOCAL_IP] = self.local_ip
        entry[NATConstants.GLOBAL_IP] = self.global_ip
        entry[NATConstants.FORCED] = ''

        result = OrderedDict()
        result[NATConstants.TRANSPORT_LIST] = []
        result[NATConstants.TRANSPORT_LIST].append(entry)

        return dict(result)


    @execute_on_pair()
    def update(self, context=None):

        result = super(StaticNat, self)._update(context=context)
        self.ncc.update(context)
        return result

    @execute_on_pair()
    def delete(self, context=None):
        self.ncc.delete(context)
        result = super(StaticNat, self)._delete(context=context)
        return result
