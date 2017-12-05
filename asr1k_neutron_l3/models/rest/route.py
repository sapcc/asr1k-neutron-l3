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

    IP = "ip"
    ROUTE = "route"
    NAME = "name"

    FOWARDING = "ip-route-interface-forwarding-list"
    FWD_LIST = "fwd-list"
    FWD = "fwd"
    PREFIX = "prefix"
    MASK = "mask"


class RouteCollection(RestBase):
    list_path = "/Cisco-IOS-XE-native:native/ip/route"
    item_path = list_path + "/vrf"

    def __parameters__(self):
        return [
            {'key': 'vrf', 'id': True},
            {'key': 'routes', 'default': []}
        ]

    def __init__(self, **kwargs):
        super(RouteCollection, self).__init__( **kwargs)

    def update(self):

        if len(self.routes) > 0:
            super(RouteCollection, self).update(method='put')
        else:
            self.delete()

    def to_dict(self):

        vrf_route = OrderedDict()
        vrf_route[RouteConstants.NAME] = self.id

        vrf_route[RouteConstants.FOWARDING] = []

        for route in self.routes:
            ip_route = OrderedDict()
            ip_route[RouteConstants.PREFIX] = route.destination
            ip_route[RouteConstants.MASK] = route.mask
            ip_route[RouteConstants.FWD_LIST] = [{RouteConstants.FWD: route.nexthop}]
            vrf_route[RouteConstants.FOWARDING].append(ip_route)

        result = OrderedDict()
        result[RouteConstants.DEFINITION] = vrf_route

        return dict(result)

    def from_json(self, json):
        blob = json.get(RouteConstants.VRF)
        self.id = blob.get(RouteConstants.NAME, None)

        return self
