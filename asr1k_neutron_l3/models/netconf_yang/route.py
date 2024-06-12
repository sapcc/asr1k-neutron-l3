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

from oslo_log import log as logging

from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair, NC_OPERATION
from asr1k_neutron_l3.common import utils

LOG = logging.getLogger(__name__)


class RouteConstants(object):
    VRF = "vrf"
    IP = "ip"
    ROUTE = "route"
    NAME = "name"

    IPV6 = "ipv6"
    IPV6_ROUTE_LIST = "ipv6-route-list"
    IPV6_FWD_LIST = "ipv6-fwd-list"

    FORWARDING = "ip-route-interface-forwarding-list"
    FWD_LIST = "fwd-list"
    FWD = "fwd"
    PREFIX = "prefix"
    MASK = "mask"


class VrfRouteBase(NyBase):
    ID_FILTER = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                      xmlns:ios-eth="http://cisco.com/ns/yang/Cisco-IOS-XE-ethernet">
                <ip>
                  <route>
                   <vrf>
                    <name>{id}</name>
                   </vrf>
                  </route>
                </ip>
              </native>
    """

    GET_ALL_STUB = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                <ip>
                  <route>
                   <vrf>
                    <name/>
                   </vrf>
                  </route>
                </ip>
              </native>
    """

    VRF_XPATH_FILTER = "/native/ip/route/vrf[name='{vrf}']"

    LIST_KEY = RouteConstants.ROUTE
    ITEM_KEY = RouteConstants.VRF

    IP_ROUTE_CLASS = None
    IP_KEY = None

    @classmethod
    def get_for_vrf(cls, context, vrf=None):
        return cls._get_all(context=context, xpath_filter=cls.VRF_XPATH_FILTER.format(vrf=vrf))

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'name', 'id': True},
            {'key': 'routes', 'yang-key': cls.IP_ROUTE_CLASS.LIST_KEY, 'type': [cls.IP_ROUTE_CLASS], 'default': []}
        ]

    @classmethod
    def get_primary_filter(cls, **kwargs):
        return cls.ID_FILTER.format(id=kwargs.get('id'))

    @classmethod
    def remove_wrapper(cls, dict, context):
        dict = cls._remove_base_wrapper(dict, context)
        if dict is None:
            return

        dict = dict.get(cls.IP_KEY, dict)
        dict = dict.get(cls.LIST_KEY, dict)

        return dict

    def _wrapper_preamble(self, dict, context):
        return {
            self.IP_KEY: {
                self.LIST_KEY: dict,
            }
        }

    @property
    def neutron_router_id(self):
        if self.name is not None:
            return utils.vrf_id_to_uuid(self.name)

    @execute_on_pair()
    def update(self, context):
        if len(self.routes) > 0:
            return self._update(context=context, method=NC_OPERATION.PUT)
        else:
            return self._delete(context=context)

    def to_single_dict(self, context):
        raise NotImplementedError

    def to_dict(self, context):
        if not self.routes:
            # no routes --> empty container
            return {}

        vrf_routes = []
        if self.routes:
            for route in sorted(self.routes, key=lambda route: route.prefix):
                vrf_routes.append(route.to_single_dict(context))

        return {
            RouteConstants.VRF: {
                RouteConstants.NAME: self.name,
                self.IP_ROUTE_CLASS.LIST_KEY: vrf_routes,
            }
        }

    def to_delete_dict(self, context):
        return {
            RouteConstants.VRF: {
                RouteConstants.NAME: self.name,
                self.IP_ROUTE_CLASS.LIST_KEY: [],
            }
        }


class IpRouteV4(NyBase):
    LIST_KEY = RouteConstants.FORWARDING

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'prefix', 'mandatory': True},
            {'key': 'mask', 'mandatory': True},
            {'key': 'fwd_list', 'yang-key': RouteConstants.FWD_LIST, 'default': []}
        ]

    def to_single_dict(self, context):
        return {
            RouteConstants.PREFIX: self.prefix,
            RouteConstants.MASK: self.mask,
            RouteConstants.FWD_LIST: self.fwd_list,
        }

    def to_dict(self, context):
        return {self.LIST_KEY: self.to_single_dict(context)}


class IpRouteV6(NyBase):
    LIST_KEY = RouteConstants.IPV6_ROUTE_LIST

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'prefix', 'mandatory': True},
            {'key': 'fwd_list', 'yang-key': RouteConstants.IPV6_FWD_LIST, 'default': []}
        ]

    def to_single_dict(self, context):
        return {
            RouteConstants.PREFIX: self.prefix,
            RouteConstants.IPV6_FWD_LIST: self.fwd_list,
        }

    def to_dict(self, context):
        return {self.LIST_KEY: self.to_single_dict(context)}


class VrfRouteV4(VrfRouteBase):
    ID_FILTER = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                      xmlns:ios-eth="http://cisco.com/ns/yang/Cisco-IOS-XE-ethernet">
                <ip>
                  <route>
                   <vrf>
                    <name>{id}</name>
                   </vrf>
                  </route>
                </ip>
              </native>
    """

    GET_ALL_STUB = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                <ip>
                  <route>
                   <vrf>
                    <name/>
                   </vrf>
                  </route>
                </ip>
              </native>
    """

    VRF_XPATH_FILTER = "/native/ip/route/vrf[name='{vrf}']"
    IP_ROUTE_CLASS = IpRouteV4
    IP_KEY = RouteConstants.IP

    def to_single_dict(self, context):
        return {
            RouteConstants.PREFIX: self.prefix,
            RouteConstants.MASK: self.mask,
            RouteConstants.FWD_LIST: self.fwd_list
        }


class VrfRouteV6(VrfRouteBase):
    ID_FILTER = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                      xmlns:ios-eth="http://cisco.com/ns/yang/Cisco-IOS-XE-ethernet">
                <ipv6>
                  <route>
                   <vrf>
                    <name>{id}</name>
                   </vrf>
                  </route>
                </ipv6>
              </native>
    """

    GET_ALL_STUB = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                <ipv6>
                  <route>
                   <vrf>
                    <name/>
                   </vrf>
                  </route>
                </ipv6>
              </native>
    """

    VRF_XPATH_FILTER = "/native/ipv6/route/vrf[name='{vrf}']"
    IP_ROUTE_CLASS = IpRouteV6
    IP_KEY = RouteConstants.IPV6

    def to_single_dict(self, context):
        return {
            RouteConstants.PREFIX: self.prefix,
            RouteConstants.IPV6_FWD_LIST: self.fwd_list
        }
