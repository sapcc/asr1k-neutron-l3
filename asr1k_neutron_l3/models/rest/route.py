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

from asr1k_neutron_l3.models.rest.rest_base import RestBase


class RouteConstants(object):
    DEFINITION = "Cisco-IOS-XE-native:vrf"

    VRF="vrf"
    IP = "ip"
    ROUTE = "route"
    NAME = "name"

    FOWARDING = "ip-route-interface-forwarding-list"
    FWD_LIST = "fwd-list"
    FWD = "fwd"
    PREFIX = "prefix"
    MASK = "mask"


class VrfRoute(RestBase):

    LIST_KEY =RouteConstants.DEFINITION

    list_path = "/Cisco-IOS-XE-native:native/ip/route"
    item_path = "{}/{}".format(list_path, RouteConstants.DEFINITION)

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'name', 'id': True},
            {'key': 'routes', 'yang-key':RouteConstants.FOWARDING, 'type': IpRoute ,  'default': []}
        ]

    def __init__(self, **kwargs):
        super(VrfRoute, self).__init__( **kwargs)

    def update(self):

        if len(self.routes) > 0:
            super(VrfRoute, self).update(method='put')
        else:
            self.delete()

    def to_dict(self):

        vrf_route = OrderedDict()
        vrf_route[RouteConstants.NAME] = self.name

        vrf_route[RouteConstants.FOWARDING] = []

        if isinstance(self.routes,list):
            for route in self.routes:
                #ip_route = IpRoute(self.name,prefix=route.destination,mask=route.destination,fwd_list=[{RouteConstants.FWD: route.nexthop}])
                vrf_route[RouteConstants.FOWARDING].append(route.to_single_dict())

        result = OrderedDict()
        result[RouteConstants.DEFINITION] = vrf_route

        return dict(result)


class IpRoute(RestBase):

    LIST_KEY =RouteConstants.FOWARDING

    list_path = "/Cisco-IOS-XE-native:native/ip/route/vrf={vrf}/ip-route-interface-forwarding-list"
    item_path = list_path

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'prefix', 'mandatory': True},
            {'key': 'mask', 'mandatory': True},
            {'key': 'fwd_list','yang-key':RouteConstants.FWD_LIST, 'default': []}
        ]

    def __init__(self,**kwargs):
        super(IpRoute, self).__init__(**kwargs)
        self.vrf = kwargs.get(RouteConstants.VRF)
        self.list_path = IpRoute.list_path.format(**{'vrf': self.vrf})
        self.item_path = IpRoute.item_path.format(**{'vrf': self.vrf})

    def __id_function__(self, id_field, **kwargs):
        self.id = "{},{}".format(self.prefix, self.mask)

    def to_single_dict(self):

        ip_route = OrderedDict()
        ip_route[RouteConstants.PREFIX] = self.prefix
        ip_route[RouteConstants.MASK] = self.mask
        ip_route[RouteConstants.FWD_LIST] = self.fwd_list


        return ip_route

    def to_dict(self):

        result = OrderedDict()
        result[RouteConstants.FOWARDING] = self.to_single_dict()

        return dict(result)