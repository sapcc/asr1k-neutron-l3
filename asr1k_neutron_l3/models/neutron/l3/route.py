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

from asr1k_neutron_l3.models.neutron.l3 import base
from asr1k_neutron_l3.models.netconf_yang import route as l3_route
from asr1k_neutron_l3.common import utils



class RouteCollection(base.Base):

    def __init__(self, router_id):
        super(RouteCollection, self).__init__()
        self.router_id = utils.uuid_to_vrf_id(router_id)
        self.routes = []

    @property
    def _rest_definition(self):
         rest_routes = []
         for route in self.routes:
             rest_routes.append(route._rest_definition)


         return l3_route.VrfRoute(name=self.router_id, routes=rest_routes)

    def get(self):
        return l3_route.VrfRoute.get(self.router_id)

    def append(self, route):
        self.routes.append(route)

    def valid(self):
        return self._rest_definition.valid()


    def update(self):
        return self._rest_definition.update()

    def delete(self):
        rc = l3_route.VrfRoute(name=self.router_id)

        return rc.delete()



class Route(base.Base):

    def __init__(self, router_id, destination, mask, nexthop):
        self.router_id = router_id
        self.destination = destination
        self.mask = mask
        self.nexthop = nexthop

    @property
    def _rest_definition(self):
         return l3_route.IpRoute(vrf=self.router_id,prefix=self.destination,mask=self.mask,fwd_list={"fwd":self.nexthop})