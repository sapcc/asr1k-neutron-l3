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
from asr1k_neutron_l3.models.netconf_yang import bgp
from asr1k_neutron_l3.models.neutron.l3 import base


class AddressFamily(base.Base):
    def __init__(self, vrf, asn=None, routable_interface=False, rt_export=[], networks_v4=[]):
        super(AddressFamily, self).__init__()
        self.vrf = utils.uuid_to_vrf_id(vrf)
        self.routable_interface = routable_interface
        self.asn = asn
        self.enable_bgp = False
        self.rt_export = rt_export
        self.networks_v4 = [bgp.Network.from_cidr(net) for net in networks_v4]
        if self.routable_interface or len(self.rt_export) > 0:
            self.enable_bgp = True

        self._rest_definition = bgp.AddressFamily(vrf=self.vrf, asn=self.asn, enable_bgp=self.enable_bgp,
                                                  static=True, connected=True, networks_v4=self.networks_v4)

    def get(self):
        return bgp.AddressFamily.get(self.vrf, asn=self.asn, enable_bgp=self.enable_bgp)

    def diff(self, should_be_none=False):
        return super(AddressFamily, self).diff(should_be_none=not self.enable_bgp)
