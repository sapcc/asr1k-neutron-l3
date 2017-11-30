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
from asr1k_neutron_l3.models.rest import route as l3_route
from asr1k_neutron_l3.plugins.common import utils


class RouteCollection(base.Base):

    def __init__(self, router_id):
        super(RouteCollection, self).__init__()
        self.router_id = utils.uuid_to_vrf_id(router_id)
        self.routes = []

    def append(self, route):
        self.routes.append(route)

    @base.excute_on_pair
    def update(self, context=None):
        rc = l3_route.RouteCollection(context, vrf=self.router_id, routes=self.routes)
        rc.update()

    @base.excute_on_pair
    def delete(self, context=None):
        rc = l3_route.RouteCollection.get(context, self.router_id)
        rc.delete()


class Route(object):

    def __init__(self, router_id, destination, mask, nexthop):
        self.router_id = router_id
        self.destination = destination
        self.mask = mask
        self.nexthop = nexthop
