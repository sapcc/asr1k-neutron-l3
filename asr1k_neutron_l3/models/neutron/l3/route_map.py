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
from asr1k_neutron_l3.models.netconf_yang import route_map
from asr1k_neutron_l3.models.neutron.l3 import base


class RouteMap(base.Base):
    def __init__(self, name, rt=None, routable_interface=False, enable_ipv6=False):
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
        sequences = []

        # ipv4
        seq = 10
        if self.routable_interface:
            sequences.append(route_map.MapSequence(seq_no=seq,
                                                   operation='permit',
                                                   prefix_list='snat-{}'.format(self.vrf),
                                                   asn=[self.rt, 'additive']))
            seq += 10
            if self.secondary_rt:
                sequences.append(route_map.MapSequence(seq_no=seq,
                                                       operation='permit',
                                                       prefix_list='route-{}'.format(self.vrf),
                                                       asn=[self.secondary_rt, 'additive']))
                seq += 10

        sequences.append(route_map.MapSequence(seq_no=seq, operation='deny', prefix_list=f'ext-{self.vrf}'))
        seq += 10

        # ipv6
        if enable_ipv6:
            sequences.append(route_map.MapSequence(seq_no=seq, operation='deny', prefix_list_v6=f'ext-{self.vrf}'))
            seq += 10

        self._rest_definition = route_map.RouteMap(name=self.name, seq=sequences)

    def get(self):
        return route_map.RouteMap.get(self.name)


class PBRRouteMap(base.Base):
    def __init__(self, name, has_gateway_interface=False):
        super().__init__()

        self.vrf = utils.uuid_to_vrf_id(name)
        self.name = f"pbr-{self.vrf}"
        self.has_gateway_interface = has_gateway_interface

        sequences = []

        if has_gateway_interface:
            sequences.append(route_map.MapSequence(seq_no=15,
                                                   operation='permit',
                                                   ip_precedence='routine'))

        self._rest_definition = route_map.RouteMap(name=self.name, seq=sequences)

    def diff(self, should_be_none=False):
        return super().diff(should_be_none=not self.has_gateway_interface)

    def update(self):
        if self.has_gateway_interface:
            return super().update()
        else:
            return self.delete()


class RedistRouteMapBase(base.Base):
    def __init__(self, router_id, routable_rt, extraroutes_rt, enabled):
        super().__init__()

        self.vrf = utils.uuid_to_vrf_id(router_id)
        self.name = f"bgp-redistribute{self.IP_VERSION}-{self.vrf}"
        self.enabled = enabled
        routable_rt_list = [routable_rt] if routable_rt else None
        extraroutes_rt_list = [extraroutes_rt] if extraroutes_rt else None

        sequences = [
            route_map.MapSequence(
                seq_no=10, operation='permit', asn=routable_rt_list,
                **{self.PREFIX_LIST_PARAM: f"routable{self.IP_VERSION}-{self.vrf}"}),
            route_map.MapSequence(
                seq_no=20, operation='permit', asn=extraroutes_rt_list,
                **{self.PREFIX_LIST_PARAM: f"routable-extraroutes{self.IP_VERSION}-{self.vrf}"}),
            route_map.MapSequence(
                seq_no=30, operation='permit',
                **{self.PREFIX_LIST_PARAM: f"internal{self.IP_VERSION}-{self.vrf}"}),
            route_map.MapSequence(
                seq_no=40, operation='permit',
                **{self.PREFIX_LIST_PARAM: f"internal-extraroutes{self.IP_VERSION}-{self.vrf}"}),
        ]

        self._rest_definition = route_map.RouteMap(name=self.name, seq=sequences)

    def diff(self, should_be_none=False):
        return super().diff(should_be_none=not self.enabled)

    def update(self):
        if self.enabled:
            return super().update()
        else:
            return self.delete()


class RedistRouteMapV4(RedistRouteMapBase):
    IP_VERSION = "4"
    PREFIX_LIST_PARAM = "prefix_list"


class RedistRouteMapV6(RedistRouteMapBase):
    IP_VERSION = "6"
    PREFIX_LIST_PARAM = "prefix_list_v6"
