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
from asr1k_neutron_l3.models.netconf_yang import bgp
from asr1k_neutron_l3.models.neutron.l3 import base


class AddressFamilyBase(base.Base):
    YANG_BGP_CLASS = None
    YANG_BGP_NETWORK_CLASS = None

    def __init__(self, vrf, asn=None, has_routable_interface=False, enable_af=True, rt_export=[],
                 redistribute_map=None, connected_cidrs=[], routable_networks=[], extra_routes=[]):
        super().__init__()
        self.vrf = utils.uuid_to_vrf_id(vrf)
        self.enable_af = enable_af
        self.has_routable_interface = has_routable_interface
        self.asn = asn
        self.enable_bgp = False
        self.rt_export = rt_export
        self.redistribute_map = redistribute_map
        self.routable_networks = routable_networks
        self.networks = set()

        for net in connected_cidrs + extra_routes:
            # rm is applied to all routable networks and their subnets
            rm = None
            if any(utils.network_in_network(net, routable_network) for routable_network in routable_networks):
                if net in extra_routes:
                    rm = cfg.CONF.asr1k_l3.dapnet_extra_routes_rm
                else:
                    rm = cfg.CONF.asr1k_l3.dapnet_network_rm

            net = self.YANG_BGP_NETWORK_CLASS.from_cidr(net, rm)
            self.networks.add(net)
        self.networks = list(self.networks)

        if self.enable_af and (self.has_routable_interface or len(self.rt_export) > 0):
            self.enable_bgp = True

        self._rest_definition = self.YANG_BGP_CLASS(vrf=self.vrf, asn=self.asn, enable_bgp=self.enable_bgp,
                                                    networks=self.networks,
                                                    redistribute_static_with_rm=redistribute_map,
                                                    redistribute_connected_with_rm=redistribute_map)

    def get(self):
        return self.YANG_BGP_CLASS.get(self.vrf, asn=self.asn, enable_bgp=self.enable_bgp)

    def diff(self, should_be_none=False):
        return super().diff(should_be_none=not self.enable_bgp)


class AddressFamilyV4(AddressFamilyBase):
    YANG_BGP_CLASS = bgp.AddressFamilyV4
    YANG_BGP_NETWORK_CLASS = bgp.NetworkV4


class AddressFamilyV6(AddressFamilyBase):
    YANG_BGP_CLASS = bgp.AddressFamilyV6
    YANG_BGP_NETWORK_CLASS = bgp.NetworkV6
