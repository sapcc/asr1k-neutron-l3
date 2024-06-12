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

from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.models.netconf_yang import route as l3_route
from asr1k_neutron_l3.models.neutron.l3 import base


class BaseRouteCollection(base.Base):
    def __init__(self, router_id):
        super().__init__()
        self.router_id = utils.uuid_to_vrf_id(router_id)
        self.routes = []

    @property
    def _route_collection_model(self):
        raise NotImplementedError

    @property
    def _rest_definition(self):
        rest_routes = [route._rest_definition for route in self.routes]
        return self._route_collection_model(name=self.router_id, routes=rest_routes)

    def append(self, route):
        self.routes.append(route)


class RouteCollectionV4(BaseRouteCollection):
    @property
    def _route_collection_model(self):
        return l3_route.VrfRouteV4


class RouteV4(base.Base):
    def __init__(self, router_id, destination, mask, nexthop):
        self.router_id = router_id
        self.destination = destination
        self.mask = mask
        self.nexthop = nexthop

        self._rest_definition = l3_route.IpRouteV4(vrf=self.router_id, prefix=self.destination, mask=self.mask,
                                                   fwd_list={"fwd": self.nexthop})

    @property
    def cidr(self):
        return utils.to_cidr(self.destination, self.mask)


class RouteCollectionV6(BaseRouteCollection):
    @property
    def _route_collection_model(self):
        return l3_route.VrfRouteV6


class RouteV6(base.Base):
    def __init__(self, router_id, destination, nexthop):
        self.router_id = router_id
        self.destination = destination
        self.nexthop = nexthop

        self._rest_definition = l3_route.IpRouteV6(vrf=self.router_id, prefix=self.destination,
                                                   fwd_list={"fwd": self.nexthop})

    @property
    def cidr(self):
        return self.destination
