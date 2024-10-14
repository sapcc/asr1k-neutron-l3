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
    POOL_WITH_VRF = 'pool-with-vrf'
    BDI = "BDI"
    BDVIF = "BD-VIF"
    ID = "id"
    START_ADDRESS = "start-address"
    END_ADDRESS = "end-address"
    NETMASK = "netmask"
    PREFIX_LENGTH = "prefix-length"

    LIST = "list"
    LIST_INTERFACE = "list-interface"
    LIST_POOL = "list-pool"
    SOURCE = "source"
    INSIDE = "inside"
    REDUNDANCY = "redundancy"
    REDUNDANCY_NEW = "redundancy-new"
    MAPPING_ID = "mapping-id"
    MAPPING_ID_NEW = "mapping-id-new"
    VRF = "vrf"
    VRF_NEW = "vrf-new"
    OVERLOAD = "overload"
    OVERLOAD_NEW = "overload-new"

    TRANSPORT_LIST = "nat-static-transport-list-with-vrf"
    STATIC = "static"

    LOCAL_IP = "local-ip"
    GLOBAL_IP = "global-ip"
    FORCED = "forced"
    MATCH_IN_VRF = "match-in-vrf"
    STATELESS = "stateless"
    NO_ALIAS = "no-alias"
    GARP_IFACE = 'garp-interface'


class NatPool(NyBase):
    DEFAULT_PREFIX = "POOL-"
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
            {'key': 'prefix_length'}
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
        if self.id is not None and self.id.startswith(self.DEFAULT_PREFIX):
            return utils.vrf_id_to_uuid(self.id[len(self.DEFAULT_PREFIX):])
        return None

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
        result = {
            NATConstants.POOL: {
                NATConstants.ID: self.id,
                NATConstants.START_ADDRESS: self.start_address,
                NATConstants.END_ADDRESS: self.end_address,
                NATConstants.PREFIX_LENGTH: self.prefix_length,
            },
        }

        return result

    def to_delete_dict(self, context):
        result = {
            NATConstants.POOL: {
                NATConstants.ID: self.id,
            },
        }

        return result

    @classmethod
    def gen_id(self, router_id):
        return f"{self.DEFAULT_PREFIX}{router_id.replace('-', '')}"

    @execute_on_pair()
    def update(self, context):
        self._check_and_clean_existing_nat_pool(context)
        return super()._update(context)

    def _check_and_clean_existing_nat_pool(self, context):
        """Delete device pool if start/end/prefix address differ

        We can't properly update pools that are in use (have connections on it),
        so we need to delete it and then add it for proper reconfiguration
        """
        device_pool = self._internal_get(context)
        if not device_pool:
            return

        if (device_pool.start_address != self.start_address or device_pool.end_address != self.end_address or
                device_pool.prefix_length != self.prefix_length):
            LOG.warning("Deleting NatPool %s on %s from device before readding it as it has changed "
                        "(on device: %s, openstack: %s)",
                        self.id, context, device_pool, self)
            device_pool._delete(context)


class DynamicNat(NyBase):
    EXTRA_LIST_KEY = None
    LIST_KEY = NATConstants.SOURCE
    ITEM_KEY = NATConstants.LIST

    @classmethod
    def remove_wrapper(cls, dict, context):
        dict = super(DynamicNat, cls)._remove_base_wrapper(dict, context)
        if dict is None:
            return
        dict = dict.get(NATConstants.IP, dict)
        dict = dict.get(NATConstants.NAT, dict)
        dict = dict.get(NATConstants.INSIDE, dict)
        dict = dict.get(cls.LIST_KEY, dict)
        if cls.EXTRA_LIST_KEY is not None:
            dict = dict.get(cls.EXTRA_LIST_KEY, dict)

        return dict

    def _wrapper_preamble(self, dict, context):
        if self.EXTRA_LIST_KEY is not None:
            dict = {self.EXTRA_LIST_KEY: dict}

        result = {}
        result[self.LIST_KEY] = dict
        result = {NATConstants.INSIDE: result}
        result[xml_utils.NS] = xml_utils.NS_CISCO_NAT
        result = {NATConstants.NAT: result}
        result = {NATConstants.IP: result}
        return result

    @property
    def neutron_router_id(self):
        if self.vrf is not None:
            return utils.vrf_id_to_uuid(self.vrf)

    @execute_on_pair()
    def update(self, context):
        return super(DynamicNat, self)._update(context=context, method=NC_OPERATION.PUT)


class InterfaceDynamicNat(DynamicNat):
    EXTRA_LIST_KEY = NATConstants.LIST_INTERFACE

    ID_FILTER = """
                  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                          xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat"
                          xmlns:ios-eth="http://cisco.com/ns/yang/Cisco-IOS-XE-ethernet">
                    <ip>
                      <ios-nat:nat>
                        <ios-nat:inside>
                          <ios-nat:source>
                            <ios-nat:list-interface>
                              <ios-nat:list>
                                <ios-nat:id>{id}</ios-nat:id>
                              </ios-nat:list>
                            </ios-nat:list-interface>
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
                            <ios-nat:list-interface>
                              <ios-nat:list>
                                <ios-nat:id/>
                              </ios-nat:list>
                            </ios-nat:list-interface>
                          </ios-nat:source>
                        </ios-nat:inside>
                      </ios-nat:nat>
                    </ip>
                  </native>
    """

    VRF_XPATH_FILTER = "/native/ip/nat/inside/source/list-interface/list[id='NAT-{vrf}']"

    @classmethod
    def __parameters__(cls):
        return [
            {"key": "id", "mandatory": True},
            {'key': 'interface', 'yang-key': 'name', 'yang-path': "interface"},
            {'key': 'redundancy'},
            {'key': 'mapping_id'},
            {'key': 'vrf', 'yang-key': 'name', 'yang-path': "interface/vrf-new"},
            {'key': 'overload', 'yang-key': 'overload-new', 'yang-path': "interface/vrf-new",
             'yang-type': YANG_TYPE.EMPTY},
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

        self.mapping_id = utils.uuid_to_mapping_id(self.vrf)
        self.redundancy = None

    def to_dict(self, context):
        ifname = "{}{}".format(context.bd_iftype, self.bd)
        vrf = {
            NATConstants.NAME: self.vrf,
        }
        if self.overload:
            vrf[NATConstants.OVERLOAD_NEW] = ''

        result = {
            NATConstants.LIST: {
                NATConstants.ID: self.id,
                NATConstants.INTERFACE: {
                    NATConstants.NAME: ifname,
                    NATConstants.VRF_NEW: vrf,
                }
            }
        }

        return result


class PoolDynamicNat(DynamicNat):
    EXTRA_LIST_KEY = NATConstants.LIST_POOL

    ID_FILTER = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                      xmlns:ios-nat="http://cisco.com/ns/yang/Cisco-IOS-XE-nat"
                      xmlns:ios-eth="http://cisco.com/ns/yang/Cisco-IOS-XE-ethernet">
                <ip>
                  <ios-nat:nat>
                    <ios-nat:inside>
                      <ios-nat:source>
                        <ios-nat:list-pool>
                          <ios-nat:list>
                            <ios-nat:id>{id}</ios-nat:id>
                          </ios-nat:list>
                        </ios-nat:list-pool>
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
                        <ios-nat:list-pool>
                          <ios-nat:list>
                            <ios-nat:id/>
                          </ios-nat:list>
                        </ios-nat:list-pool>
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

            {'key': 'vrf', 'yang-key': 'name', 'yang-path': "pool/vrf-new"},
            {'key': 'redundancy', 'yang-key': 'name', 'yang-path': 'pool/redundancy-new'},
            {'key': 'mapping_id', 'yang-key': 'name', 'yang-path': 'pool/redundancy-new/mapping-id-new'},
            {'key': 'pool', 'yang-key': 'name', 'yang-path': "pool"},
            {'key': 'overload', 'yang-key': 'overload-new', 'yang-path': "pool/vrf-new",
             'default': False, 'yang-type': YANG_TYPE.EMPTY},

            {'key': 'redundancy_vrf', 'yang-key': 'name',
             'yang-path': "pool/redundancy-new/mapping-id-new/vrf-new"},
            {'key': 'redundancy_overload', 'yang-key': 'overload-new',
             'yang-path': "pool/redundancy-new/mapping-id-new/vrf-new", 'yang-type': YANG_TYPE.EMPTY},

        ]

    def __init__(self, **kwargs):
        # if we have vrf/overload via redundancy tag this overrides whatever we have in the pool
        # normally they're also mutually exclusive, so we're basically just copying the values for unified handling
        if kwargs.get('redundancy_vrf'):
            kwargs['vrf'] = kwargs['redundancy_vrf']
        if kwargs.get('redundancy_overload'):
            kwargs['overload'] = kwargs['redundancy_overload']

        super().__init__(**kwargs)

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
        vrf = {
            NATConstants.NAME: self.vrf,
        }
        if self.overload:
            vrf[NATConstants.OVERLOAD_NEW] = ""

        # we don't support pool dynamic nat without redundancy flag
        entry = {
            NATConstants.ID: self.id,
            NATConstants.POOL: {
                NATConstants.NAME: self.pool,
                NATConstants.REDUNDANCY_NEW: {
                    NATConstants.NAME: self.redundancy,
                    NATConstants.MAPPING_ID_NEW: {
                        NATConstants.NAME: self.mapping_id,
                        NATConstants.VRF_NEW: vrf,
                    },
                }
            }
        }

        result = {
            NATConstants.LIST: [entry],
        }

        return result


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
                    nat_entry._delete(context=context)
                global_ip = neutron_local_ips.get(nat_entry.local_ip)
                if global_ip is not None and global_ip != nat_entry.global_ip:
                    LOG.debug('Removing invalid local mapping local {} > {} from vrf {}'
                              ''.format(nat_entry.local_ip, nat_entry.global_ip, self.vrf))
                    nat_entry._delete(context=context)

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
            {'key': 'match_in_vrf', 'yang-type': YANG_TYPE.EMPTY, 'default': False},
            {'key': 'stateless', 'yang-type': YANG_TYPE.EMPTY, 'default': False},
            {'key': 'no_alias', 'yang-type': YANG_TYPE.EMPTY, 'default': False},
            {'key': 'garp_bdvif_iface', 'yang-path': 'garp-interface/BD-VIF'},
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
            entry[NATConstants.NO_ALIAS] = ""
        else:
            if self.stateless:
                entry[NATConstants.STATELESS] = ""
            if self.no_alias:
                entry[NATConstants.NO_ALIAS] = ""
            if self.redundancy:
                entry[NATConstants.REDUNDANCY] = self.redundancy
            if self.mapping_id:
                entry[NATConstants.MAPPING_ID] = self.mapping_id

        if context.version_min_17_13:
            if self.garp_bdvif_iface:
                entry[NATConstants.GARP_IFACE] = {NATConstants.BDVIF: str(self.garp_bdvif_iface)}
            else:
                entry[NATConstants.GARP_IFACE] = {xml_utils.OPERATION: NC_OPERATION.REMOVE}

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
