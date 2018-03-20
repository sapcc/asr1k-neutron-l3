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
from asr1k_neutron_l3.models.netconf_yang import route_map
from asr1k_neutron_l3.models.netconf_yang.ny_base import NC_OPERATION
from asr1k_neutron_l3.common import utils


class RouteMap(base.Base):
    def __init__(self, name, rt=None, routeable_interface=False):
        super(RouteMap, self).__init__()
        self.vrf = utils.uuid_to_vrf_id(name)
        self.name = "exp-{}".format(self.vrf)
        self.rt = rt
        self.routeable_interface  = routeable_interface

        self.enable_bgp = False
        if self.routeable_interface:
            self.enable_bgp = True

        sequences = []
        sequences.append(route_map.MapSequence(ordering_seq=10, operation='permit', prefix_list='snat-{}'.format(self.vrf), asn=[self.rt,'additive'],enable_bgp=self.enable_bgp))
        sequences.append(route_map.MapSequence(ordering_seq=20, operation='deny', prefix_list='exp-{}'.format(self.vrf)))

        self._rest_definition = route_map.RouteMap(name=self.name, seq=sequences)



    def get(self):
        return route_map.RouteMap.get(self.name)




