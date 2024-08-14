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
from oslo_config import cfg

from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.models.netconf_yang import route_map
from asr1k_neutron_l3.models.neutron.l3 import base, prefix


class RouteMap(base.Base):
    def __init__(self, name, rt=None, routable_interface=False):
        super(RouteMap, self).__init__()
        self.vrf = utils.uuid_to_vrf_id(name)
        self.name = "exp-{}".format(self.vrf)
        self.rt = rt
        self.secondary_rt = None
        if rt is not None:
            components = rt.split(":")
            if len(components) == 2:
                self.secondary_rt = components[0] + ":" + str(int(components[1]) + 1000)

        self.routable_interface = routable_interface
        self.enable_bgp = False
        if self.routable_interface:
            self.enable_bgp = True

        sequences = []
        seq = 10
        if self.routable_interface:
            sequences.append(route_map.MapSequence(seq_no=seq,
                                                   operation='permit',
                                                   prefix_list='snat-{}'.format(self.vrf),
                                                   asn=[self.rt, 'additive'],
                                                   enable_bgp=self.enable_bgp))
            seq += 10
            if self.secondary_rt:
                sequences.append(route_map.MapSequence(seq_no=seq,
                                                       operation='permit',
                                                       prefix_list='route-{}'.format(self.vrf),
                                                       asn=[self.secondary_rt, 'additive'],
                                                       enable_bgp=self.enable_bgp))
                seq += 10

        sequences.append(route_map.MapSequence(seq_no=seq, operation='deny', prefix_list='ext-{}'.format(self.vrf)))

        self._rest_definition = route_map.RouteMap(name=self.name, seq=sequences)

    def get(self):
        return route_map.RouteMap.get(self.name)


class PBRRouteMap(base.Base):
    def __init__(self, name, gateway_interface=None):
        super(PBRRouteMap, self).__init__()

        self.vrf = utils.uuid_to_vrf_id(name)
        self.name = "pbr-{}".format(self.vrf)

        sequences = []

        if gateway_interface is not None:
            sequences.append(route_map.MapSequence(seq_no=10,
                                                   operation='permit',
                                                   access_list='PBR-{}'.format(self.vrf),
                                                   next_hop=gateway_interface.primary_gateway_ip,
                                                   ip_precedence='routine',
                                                   force=True,
                                                   drop_on_17_3=True))
            sequences.append(route_map.MapSequence(seq_no=15,
                                                   operation='permit',
                                                   ip_precedence='routine'))

        self._rest_definition = route_map.RouteMap(name=self.name, seq=sequences)


class BgpvpnRedistRouteMap(base.Base):
    def __init__(self, router_id):
        super().__init__()

        self.vrf = utils.uuid_to_vrf_id(router_id)
        self.name = "BGPVPNREDIST-{}".format(self.vrf)

        sequences = [
            # FIXME: remove once we decided we don't need it (as we do it via network statements)
            route_map.MapSequence(seq_no=10,
                                  operation='permit',
                                  access_list=f"{prefix.RoutableInternalPrefixes.PREFIX_NAME}-{self.vrf}"),

            # FIXME: set community
            route_map.MapSequence(seq_no=20,
                                  operation='permit',
                                  community_list=cfg.CONF.asr1k_l3.dapn_extra_routes_communities,
                                  access_list=f"{prefix.RoutableExtraPrefixes.PREFIX_NAME}-{self.vrf}"),
            route_map.MapSequence(seq_no=30,
                                  operation='permit',
                                  access_list=f"{prefix.BgpvpnPrefixes.PREFIX_NAME}-{self.vrf}"),
        ]

        self._rest_definition = route_map.RouteMap(name=self.name, seq=sequences)
