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
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair, YANG_TYPE, NC_OPERATION
from asr1k_neutron_l3.models.netconf_yang import xml_utils
from asr1k_neutron_l3.common import utils

LOG = logging.getLogger(__name__)


class NATConstants(object):
    IP = 'ip'
    NAT = 'nat'
    POOL = "pool"
    POOL_WITH_VRF = 'pool-with-vrf'
    NAME = "name"
    VRF_NAME = "vrf-name"
    INTERFACE = "interface"
    INTERFACE_WITH_VRF = 'interface-with-vrf'
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

    TRANSPORT_LIST = "nat-static-transport-list-with-vrf"
    STATIC = "static"

    LOCAL_IP = "local-ip"
    GLOBAL_IP = "global-ip"
    FORCED = "forced"
    MATCH_IN_VRF = "match-in-vrf"
    STATELESS = "stateless"


class NatPool(NyBase):
    LIST_KEY = NATConstants.NAT
    ITEM_KEY = NATConstants.POOL

    ID_FILTER = """
            <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                    xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
                <ip>
                    <ios-nat:nat>
                        <ios-nat:pool>
                            <id>{id}</id>
                        </ios-nat:pool>
                    </ios-nat:nat>
                </ip>
            </native>
    """

    GET_ALL_STUB = """
            <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                    xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
                <ip>
                    <ios-nat:nat>
                        <ios-nat:pool>
                            <ios-nat:id/>
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
    def remove_wrapper(cls, dict, context):
        dict = super(NatPool, cls)._remove_base_wrapper(dict, context)
        if dict is None:
            return
        dict = dict.get(NATConstants.IP, dict)
        dict = dict.get(cls.LIST_KEY, dict)

        return dict

    @property
    def neutron_router_id(self):
        if self.vrf is not None:
            return utils.vrf_id_to_uuid(self.id)

    def _wrapper_preamble(self, dict, context):
        result = {}
        dict[xml_utils.NS] = xml_utils.NS_CISCO_NAT
        result[self.LIST_KEY] = dict
        result = {NATConstants.IP: result}
        return result

    def __init__(self, **kwargs):
        super(NatPool, self).__init__(**kwargs)
        self.vrf = self.id

    def to_dict(self, context):
        pool = OrderedDict()
        pool[NATConstants.ID] = self.id

        pool[NATConstants.START_ADDRESS] = self.start_address
        pool[NATConstants.END_ADDRESS] = self.end_address
        pool[NATConstants.NETMASK] = self.netmask

        result = OrderedDict()
        result[NATConstants.POOL] = pool

        return dict(result)

    def to_delete_dict(self, context):
        pool = OrderedDict()
        pool[NATConstants.ID] = self.id

        result = OrderedDict()
        result[NATConstants.POOL] = pool

        return dict(result)


class DynamicNat(NyBase):
    LIST_KEY = NATConstants.SOURCE
    ITEM_KEY = NATConstants.LIST

    # @classmethod
    # def get_primary_filter(cls,**kwargs):
    #     return cls.ID_FILTER.format(**{'id': kwargs.get('id'),'vrf':kwargs.get('vrf')})

    @classmethod
    def remove_wrapper(cls, dict, context):
        dict = super(DynamicNat, cls)._remove_base_wrapper(dict, context)
        if dict is None:
            return
        dict = dict.get(NATConstants.IP, dict)
        dict = dict.get(NATConstants.NAT, dict)
        dict = dict.get(NATConstants.INSIDE, dict)

        dict = dict.get(cls.LIST_KEY, dict)

        return dict

    def _wrapper_preamble(self, dict, context):
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
        self.redundancy = None

    @property
    def neutron_router_id(self):
        if self.vrf is not None:
            return utils.vrf_id_to_uuid(self.vrf)

    @execute_on_pair()
    def update(self, context):
        return super(DynamicNat, self)._update(context=context, method=NC_OPERATION.PUT)


class InterfaceDynamicNat(DynamicNat):
    ID_FILTER = """
                  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                          xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat"
                          xmlns:ios-eth="http://cisco.com/ns/yang/Cisco-IOS-XE-ethernet">
                    <ip>
                      <ios-nat:nat>
                        <ios-nat:inside>
                          <ios-nat:source>
                            <ios-nat:list>
                              <ios-nat:id>{id}</ios-nat:id>
                            </ios-nat:list>
                          </ios-nat:source>
                        </ios-nat:inside>
                      </ios-nat:nat>
                    </ip>
                  </native>
    """

    GET_ALL_STUB = """
                  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                          xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
                    <ip>
                      <ios-nat:nat>
                        <ios-nat:inside>
                          <ios-nat:source>
                            <ios-nat:list>
                              <ios-nat:id/>
                            </ios-nat:list>
                          </ios-nat:source>
                        </ios-nat:inside>
                      </ios-nat:nat>
                    </ip>
                  </native>
    """

    VRF_XPATH_FILTER = "/native/ip/nat/inside/source/list[id='NAT-{vrf}']"

    @classmethod
    def get_for_vrf(cls, context, vrf=None):
        return cls._get_all(context=context, xpath_filter=cls.VRF_XPATH_FILTER.format(vrf=vrf))

    @classmethod
    def __parameters__(cls):
        return [
            {"key": "id", "mandatory": True},
            {'key': 'interface', 'yang-key': 'name', 'yang-path': "interface-with-vrf/interface"},
            {'key': 'redundancy'},
            {'key': 'mapping_id'},
            {'key': 'vrf', 'yang-key': 'vrf-name', 'yang-path': "interface-with-vrf/interface/vrf"},
            {'key': 'overload', 'yang-path': "interface-with-vrf/interface/vrf", 'default': False,
             'yang-type': YANG_TYPE.EMPTY}
        ]

    @classmethod
    def _exists(cls, **kwargs):
        try:
            result = cls._get(**kwargs)
        except Exception as e:
            LOG.exception(e)
            result = None

        if result is not None and result.interface is not None:
            return True

        return False

    def __init__(self, **kwargs):
        super(InterfaceDynamicNat, self).__init__(**kwargs)

        if kwargs.get("interface") is not None:
            if self.interface.startswith("BDI"):
                self.bd = int(self.interface[3:])
            elif self.interface.startswith("BD-VIF"):
                self.bd = int(self.interface[6:])
            else:
                raise ValueError("Could not determine bd id from interface '{}'".format(self.interface))
        else:
            self.bd = kwargs.get("bridge_domain")

    def to_dict(self, context):
        ifname = "{}{}".format(context.bd_iftype, self.bd)

        entry = OrderedDict()
        entry[NATConstants.ID] = self.id

        entry[NATConstants.INTERFACE_WITH_VRF] = {
            NATConstants.INTERFACE: {
                NATConstants.NAME: ifname,
                NATConstants.VRF: {
                    NATConstants.VRF_NAME: self.vrf
                },
            },
        }

        if self.overload:
            entry[NATConstants.INTERFACE_WITH_VRF][NATConstants.INTERFACE][NATConstants.VRF][NATConstants.OVERLOAD] = ""

        if self.redundancy is not None:
            entry[NATConstants.REDUNDANCY] = self.redundancy
            entry[NATConstants.MAPPING_ID] = self.mapping_id

        result = OrderedDict()
        result[NATConstants.LIST] = []
        result[NATConstants.LIST].append(entry)

        return dict(result)


class PoolDynamicNat(DynamicNat):
    ID_FILTER = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                      xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat"
                      xmlns:ios-eth="http://cisco.com/ns/yang/Cisco-IOS-XE-ethernet">
                <ip>
                  <ios-nat:nat>
                    <ios-nat:inside>
                      <ios-nat:source>
                        <ios-nat:list>
                          <ios-nat:id>{id}</ios-nat:id>
                        </ios-nat:list>
                      </ios-nat:source>
                    </ios-nat:inside>
                  </ios-nat:nat>
                </ip>
              </native>
    """

    GET_ALL_STUB = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                      xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
                <ip>
                  <ios-nat:nat>
                    <ios-nat:inside>
                      <ios-nat:source>
                        <ios-nat:list>
                          <ios-nat:id/>
                        </ios-nat:list>
                      </ios-nat:source>
                    </ios-nat:inside>
                  </ios-nat:nat>
                </ip>
              </native>
    """

    @classmethod
    def __parameters__(cls):
        return [
            {"key": "id", "mandatory": True},
            {'key': 'vrf', 'yang-key': 'name', 'yang-path': "pool-with-vrf/pool/vrf"},
            {'key': 'redundancy'},
            {'key': 'mapping_id'},
            {'key': 'pool', 'yang-key': 'name', 'yang-path': "pool-with-vrf/pool"},
            {'key': 'overload', 'yang-path': "pool-with-vrf/pool/vrf", 'default': False, 'yang-type': YANG_TYPE.EMPTY}
        ]

    @classmethod
    def _exists(cls, **kwargs):
        try:
            result = cls._get(**kwargs)
        except Exception as e:
            LOG.exception(e)
            result = None

        if result is not None and result.pool is not None:
            return True

        return False

    def to_dict(self, context):
        entry = OrderedDict()
        entry[NATConstants.ID] = self.id

        entry[NATConstants.POOL_WITH_VRF] = {}
        entry[NATConstants.POOL_WITH_VRF][NATConstants.POOL] = {}
        entry[NATConstants.POOL_WITH_VRF][NATConstants.POOL][NATConstants.NAME] = self.pool
        entry[NATConstants.POOL_WITH_VRF][NATConstants.POOL][NATConstants.VRF] = {}
        entry[NATConstants.POOL_WITH_VRF][NATConstants.POOL][NATConstants.VRF][NATConstants.NAME] = self.vrf
        if self.overload:
            entry[NATConstants.POOL_WITH_VRF][NATConstants.POOL][NATConstants.VRF][NATConstants.OVERLOAD] = ""

        if self.redundancy is not None:
            entry[NATConstants.REDUNDANCY] = self.redundancy
            entry[NATConstants.MAPPING_ID] = self.mapping_id

        result = OrderedDict()
        result[NATConstants.LIST] = []
        result[NATConstants.LIST].append(entry)

        return dict(result)


class StaticNatList(NyBase):
    ID_FILTER = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                      xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
                <ip>
                  <ios-nat:nat>
                    <ios-nat:inside>
                      <ios-nat:source>
                        <ios-nat:static>
                          <ios-nat:nat-static-transport-list-with-vrf>
                            <ios-nat:vrf>{vrf}</ios-nat:vrf>
                          </ios-nat:nat-static-transport-list-with-vrf>
                        </ios-nat:static>
                      </ios-nat:source>
                    </ios-nat:inside>
                  </ios-nat:nat>
                </ip>
              </native>
    """

    LIST_KEY = NATConstants.STATIC
    ITEM_KEY = NATConstants.TRANSPORT_LIST
    EMPTY_TYPE = []

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'vrf', 'id': True, 'validate': False, 'deserialise': False},
            {'key': 'static_nats', 'yang-key': NATConstants.TRANSPORT_LIST,
             'type': [StaticNat], 'root-list':True, 'default': []}
        ]

    @classmethod
    def get_primary_filter(cls, **kwargs):
        return cls.ID_FILTER.format(vrf=kwargs.get('vrf'))

    @classmethod
    def remove_wrapper(cls, dict, context):
        dict = super(StaticNatList, cls)._remove_base_wrapper(dict, context)
        if dict is None:
            return

        dict = dict.get(NATConstants.IP, dict)
        dict = dict.get(NATConstants.NAT, dict)
        dict = dict.get(NATConstants.INSIDE, dict)
        dict = dict.get(NATConstants.SOURCE, dict)
        dict = dict.get(cls.LIST_KEY, dict)

        return dict

    def _wrapper_preamble(self, dict, context):
        result = {}
        result[self.LIST_KEY] = dict
        result = {NATConstants.SOURCE: result}
        result = {NATConstants.INSIDE: result}
        result = {NATConstants.NAT: result}
        result[NATConstants.NAT][xml_utils.NS] = xml_utils.NS_CISCO_NAT
        result = {NATConstants.IP: result}
        return result

    def __init__(self, **kwargs):
        super(StaticNatList, self).__init__(**kwargs)

    def to_dict(self, context):
        nat_list = []

        for static_nat in sorted(self.static_nats, key=lambda static_nat: static_nat.local_ip):
            nat_list.append(dict({self.ITEM_KEY: static_nat.to_single_dict(context)}))

        return nat_list

    def clean_nat(self, context):
        nat_list = self._internal_get(context=context)

        neutron_ids = []
        neutron_local_ips = {}
        for nat in self.static_nats:
            neutron_ids.append(nat.id)
            neutron_local_ips[nat.local_ip] = nat.global_ip
        if nat_list is not None:
            for nat_entry in nat_list.static_nats:
                if nat_entry.id not in neutron_ids:
                    LOG.debug('Removing unknown mapping local {} > {} from vrf {}'
                              ''.format(nat_entry.local_ip, nat_entry.global_ip, self.vrf))
                    nat_entry.delete(context=context)
                global_ip = neutron_local_ips.get(nat_entry.local_ip)
                if global_ip is not None and global_ip != nat_entry.global_ip:
                    LOG.debug('Removing invalid local mapping local {} > {} from vrf {}'
                              ''.format(nat_entry.local_ip, nat_entry.global_ip, self.vrf))
                    nat_entry.delete(context=context)

    @execute_on_pair()
    def update(self, context):
        self.clean_nat(context)
        result = super(StaticNatList, self)._update(context=context, method=NC_OPERATION.PUT)
        return result

    @execute_on_pair()
    def delete(self, context):
        self.clean_nat(context)
        result = super(StaticNatList, self)._delete(context=context)
        return result


class StaticNat(NyBase):
    ID_FILTER = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                      xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
                <ip>
                  <ios-nat:nat>
                    <ios-nat:inside>
                      <ios-nat:source>
                        <ios-nat:static>
                          <ios-nat:nat-static-transport-list-with-vrf>
                            <ios-nat:local-ip>{local_ip}</ios-nat:local-ip>
                            <ios-nat:global-ip>{global_ip}</ios-nat:global-ip>
                          </ios-nat:nat-static-transport-list-with-vrf>
                        </ios-nat:static>
                      </ios-nat:source>
                    </ios-nat:inside>
                  </ios-nat:nat>
                </ip>
              </native>
    """

    MAPPING_ID_FILTER = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                      xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
                <ip>
                  <ios-nat:nat>
                    <ios-nat:inside>
                      <ios-nat:source>
                        <ios-nat:static>
                          <ios-nat:nat-static-transport-list-with-vrf>
                            <ios-nat:mapping-id>{mapping_id}</ios-nat:mapping-id>
                          </ios-nat:nat-static-transport-list-with-vrf>
                        </ios-nat:static>
                      </ios-nat:source>
                    </ios-nat:inside>
                  </ios-nat:nat>
                </ip>
              </native>
                """

    LOCAL_IP_FILTER = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                      xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
                <ip>
                  <ios-nat:nat>
                    <ios-nat:inside>
                      <ios-nat:source>
                        <ios-nat:static>
                          <ios-nat:nat-static-transport-list-with-vrf>
                            <ios-nat:local-ip>{local_ip}</ios-nat:local-ip>
                            <ios-nat:vrf>{vrf}</ios-nat:vrf>
                          </ios-nat:nat-static-transport-list-with-vrf>
                        </ios-nat:static>
                      </ios-nat:source>
                    </ios-nat:inside>
                  </ios-nat:nat>
                </ip>
              </native>
                """

    ALL_FILTER = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                      xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
                <ip>
                  <ios-nat:nat>
                    <ios-nat:inside>
                      <ios-nat:source>
                        <ios-nat:static>
                          <ios-nat:nat-static-transport-list-with-vrf>
                           <ios-nat:vrf>{vrf}</ios-nat:vrf>
                          </ios-nat:nat-static-transport-list-with-vrf>
                        </ios-nat:static>
                      </ios-nat:source>
                    </ios-nat:inside>
                  </ios-nat:nat>
                </ip>
              </native>
                """

    GET_ALL_STUB = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                      xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
                <ip>
                  <ios-nat:nat>
                    <ios-nat:inside>
                      <ios-nat:source>
                        <ios-nat:static>
                          <ios-nat:nat-static-transport-list-with-vrf>
                            <ios-nat:vrf/>
                            <ios-nat:local-ip/>
                            <ios-nat:global-ip/>
                          </ios-nat:nat-static-transport-list-with-vrf>
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
            {'key': 'match_in_vrf', 'yang-key': 'match-in-vrf', 'default': False},
            {'key': 'stateless', 'yang-type': YANG_TYPE.EMPTY, 'default': False},
        ]

    @classmethod
    def get_primary_filter(cls, **kwargs):
        return cls.ID_FILTER.format(local_ip=kwargs.get('local_ip'), global_ip=kwargs.get('global_ip'))

    @classmethod
    def get_global_ip_filter(cls, **kwargs):
        return cls.ID_FILTER.format(global_ip=kwargs.get('global_ip'))

    @classmethod
    @execute_on_pair(return_raw=True)
    def get(cls, local_ip, global_ip, context):
        return super(StaticNat, cls)._get(local_ip=local_ip, global_ip=global_ip, context=context)

    @classmethod
    @execute_on_pair(return_raw=True)
    def get_all(cls, filter={}, context=None):
        return super(StaticNat, cls)._get_all(filter=filter, context=context)

    @classmethod
    @execute_on_pair(return_raw=True)
    def exists(cls, local_ip, global_ip, context):
        return super(StaticNat, cls)._exists(local_ip=local_ip, global_ip=global_ip, context=context)

    @classmethod
    def remove_wrapper(cls, dict, context):
        dict = super(StaticNat, cls)._remove_base_wrapper(dict, context)
        if dict is None:
            return
        dict = dict.get(NATConstants.IP, dict)
        dict = dict.get(NATConstants.NAT, dict)
        dict = dict.get(NATConstants.INSIDE, dict)
        dict = dict.get(NATConstants.SOURCE, dict)
        dict = dict.get(cls.LIST_KEY, dict)

        return dict

    def orphan_info(self):
        return {self.__class__.__name__: {'local_ip': self.local_ip, 'global_ip': self.global_ip, 'vrf': self.vrf}}

    def _wrapper_preamble(self, dict, context):
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

    @property
    def neutron_router_id(self):
        if self.vrf is not None:
            return utils.vrf_id_to_uuid(self.vrf)

    def __id_function__(self, id_field, **kwargs):
        self.id = "{},{}".format(self.local_ip, self.global_ip)

    def to_dict(self, context):
        result = OrderedDict()
        result[NATConstants.TRANSPORT_LIST] = []
        result[NATConstants.TRANSPORT_LIST].append(self.to_single_dict(context))

        return dict(result)

    def to_single_dict(self, context):
        entry = OrderedDict()
        entry[NATConstants.LOCAL_IP] = self.local_ip
        entry[NATConstants.GLOBAL_IP] = self.global_ip
        entry[NATConstants.VRF] = self.vrf

        if self.match_in_vrf:
            entry[NATConstants.MATCH_IN_VRF] = ""
        entry[NATConstants.MATCH_IN_VRF] = ""

        if not self.from_device:
            if self.stateless and context.has_stateless_nat:
                entry[NATConstants.STATELESS] = ""
            elif self.redundancy is not None:
                # only set redundancy if we should not or cannot enable stateless
                entry[NATConstants.REDUNDANCY] = self.redundancy
                entry[NATConstants.MAPPING_ID] = self.mapping_id
        else:
            if self.stateless:
                entry[NATConstants.STATELESS] = ""
            if self.redundancy:
                entry[NATConstants.REDUNDANCY] = self.redundancy
            if self.mapping_id:
                entry[NATConstants.MAPPING_ID] = self.mapping_id

        return entry

    def to_delete_dict(self, context):
        entry = OrderedDict()
        entry[NATConstants.LOCAL_IP] = self.local_ip
        entry[NATConstants.GLOBAL_IP] = self.global_ip
        entry[NATConstants.VRF] = self.vrf
        entry[NATConstants.FORCED] = ''

        result = OrderedDict()
        result[NATConstants.TRANSPORT_LIST] = []
        result[NATConstants.TRANSPORT_LIST].append(entry)

        return dict(result)

    @execute_on_pair()
    def update(self, context):
        self._check_and_clean_mapping_id(context=context)
        self._check_and_clean_local_ip(context=context)
        result = super(StaticNat, self)._update(context=context)
        return result

    def _check_and_clean_mapping_id(self, context):
        # check if mapping ID is already in use in another VRF: if so its orphaned and should be removed
        filter = self.MAPPING_ID_FILTER.format(mapping_id=self.mapping_id)

        nats = self._get_all(nc_filter=filter, context=context)

        for nat in nats:
            if nat.vrf != self.vrf:
                LOG.info('Removing invalid global mapping {} > {} in VRF {} for mapping id {}'
                         ''.format(nat.local_ip, nat.global_ip, nat.vrf, self.mapping_id))
                nat._delete(context)

    def _check_and_clean_local_ip(self, context):
        # check if local IP is already mapped in VRF: if so its orphaned and should be removed
        filter = self.LOCAL_IP_FILTER.format(local_ip=self.local_ip, vrf=self.vrf)

        nats = self._get_all(nc_filter=filter, context=context)

        for nat in nats:
            if nat.global_ip != self.global_ip:
                LOG.info('Removing invalid local mapping {} > {} in VRF {}'
                         ''.format(nat.local_ip, nat.global_ip, nat.vrf))
                nat._delete(context)

    @execute_on_pair()
    def delete(self, context):
        result = super(StaticNat, self)._delete(context=context)

        return result
