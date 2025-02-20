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
from asr1k_neutron_l3.models.netconf_yang import vrf
from asr1k_neutron_l3.models.neutron.l3 import base

from oslo_config import cfg


class Vrf(base.Base):
    def __init__(self, name, description=None, asn=None, rd=None, routable_interface=False,
                 rt_import=None, rt_export=None, global_vrf_id=None, enable_ipv4=True, enable_ipv6=False):
        super(Vrf, self).__init__()
        self.name = utils.uuid_to_vrf_id(name)
        self.description = description
        self.routable_interface = routable_interface

        self.asn = None
        self.rd = None
        self.asn = asn
        self.rd = utils.to_rd(self.asn, rd)

        if self.routable_interface:
            self.map = f"{cfg.CONF.asr1k_l3.dapnet_rm_prefix}{global_vrf_id:02d}"
        else:
            self.map = f"exp-{self.name}"

        self.rt_import = [vrf.RouteTarget(asn_ip=asn_ip) for asn_ip in rt_import] if rt_import else None
        self.rt_export = [vrf.RouteTarget(asn_ip=asn_ip) for asn_ip in rt_export] if rt_export else None

        af_common_kwargs = {"rt_export": self.rt_export, "rt_import": self.rt_import}
        self.enable_ipv4 = enable_ipv4
        af_ipv4 = None
        if self.enable_ipv4:
            af_ipv4 = vrf.IpV4AddressFamily(map=self.map, **af_common_kwargs)

        self.map_v6 = None
        self.enable_ipv6 = enable_ipv6
        af_ipv6 = None
        if self.enable_ipv6:
            self.map_v6 = f"bgp-redistribute6-{self.name}"
            af_ipv6 = vrf.IpV6AddressFamily(map=self.map_v6, **af_common_kwargs)

        self._rest_definition = vrf.VrfDefinition(name=self.name, description=self.description, rd=self.rd,
                                                  address_family_ipv4=af_ipv4, address_family_ipv6=af_ipv6)

    def get(self):
        return vrf.VrfDefinition.get(self.name)
