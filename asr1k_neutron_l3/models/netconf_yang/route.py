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

from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair, NC_OPERATION
from asr1k_neutron_l3.common import utils

LOG = logging.getLogger(__name__)


class RouteConstants(object):
    DEFINITION = "vrf"

    VRF = "vrf"
    IP = "ip"
    ROUTE = "route"
    NAME = "name"

    FOWARDING = "ip-route-interface-forwarding-list"
    FWD_LIST = "fwd-list"
    FWD = "fwd"
    PREFIX = "prefix"
    MASK = "mask"


class VrfRoute(NyBase):
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
    ITEM_KEY = RouteConstants.DEFINITION

    @classmethod
    def get_for_vrf(cls, context, vrf=None):
        return cls._get_all(context=context, xpath_filter=cls.VRF_XPATH_FILTER.format(vrf=vrf))

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'name', 'id': True},
            {'key': 'routes', 'yang-key': RouteConstants.FOWARDING, 'type': [IpRoute], 'default': []}
        ]

    @classmethod
    def get_primary_filter(cls, **kwargs):
        return cls.ID_FILTER.format(id=kwargs.get('id'))

    @classmethod
    def remove_wrapper(cls, dict, context):
        dict = super(VrfRoute, cls)._remove_base_wrapper(dict, context)
        if dict is None:
            return

        dict = dict.get(RouteConstants.IP, dict)
        dict = dict.get(cls.LIST_KEY, dict)

        return dict

    def _wrapper_preamble(self, dict, context):
        result = {}
        result[self.LIST_KEY] = dict
        result = {RouteConstants.IP: result}
        return result

    def __init__(self, **kwargs):
        super(VrfRoute, self).__init__(**kwargs)

    @property
    def neutron_router_id(self):
        if self.name is not None:
            return utils.vrf_id_to_uuid(self.name)

    @execute_on_pair()
    def update(self, context):
        if len(self.routes) > 0:
            return super(VrfRoute, self)._update(context=context, method=NC_OPERATION.PUT)
        else:
            return self._delete(context=context)

    def to_dict(self, context):
        vrf_route = OrderedDict()
        vrf_route[RouteConstants.NAME] = self.name
        vrf_route[RouteConstants.FOWARDING] = []

        if isinstance(self.routes, list):
            for route in sorted(self.routes, key=lambda route: route.prefix):
                vrf_route[RouteConstants.FOWARDING].append(route.to_single_dict(context))

        result = OrderedDict()
        result[RouteConstants.DEFINITION] = vrf_route

        return dict(result)

    def to_delete_dict(self, context):
        vrf_route = OrderedDict()
        vrf_route[RouteConstants.NAME] = self.name
        vrf_route[RouteConstants.FOWARDING] = []

        result = OrderedDict()
        result[RouteConstants.DEFINITION] = vrf_route

        return dict(result)


class IpRoute(NyBase):
    LIST_KEY = RouteConstants.FOWARDING

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'prefix', 'mandatory': True},
            {'key': 'mask', 'mandatory': True},
            {'key': 'fwd_list', 'yang-key': RouteConstants.FWD_LIST, 'default': []}
        ]

    def __init__(self, **kwargs):
        super(IpRoute, self).__init__(**kwargs)

    @property
    def vrf(self):
        if self.parent:
            self.parent.get(RouteConstants.VRF)

    def __id_function__(self, id_field, **kwargs):
        self.id = "{},{}".format(self.prefix, self.mask)

    def to_single_dict(self, context):
        ip_route = OrderedDict()
        ip_route[RouteConstants.PREFIX] = self.prefix
        ip_route[RouteConstants.MASK] = self.mask
        ip_route[RouteConstants.FWD_LIST] = self.fwd_list

        return ip_route

    def to_dict(self, context):
        result = OrderedDict()
        result[RouteConstants.FOWARDING] = self.to_single_dict(context)

        return dict(result)
