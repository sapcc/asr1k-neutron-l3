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
from asr1k_neutron_l3.models.netconf_yang import bgp

from asr1k_neutron_l3.common import utils


class AddressFamily(base.Base):
    def __init__(self, vrf, asn=None, routeable_interface=False):
        super(AddressFamily, self).__init__()
        self.vrf = utils.uuid_to_vrf_id(vrf)
        self.routeable_interface = routeable_interface
        self.asn = asn




    @property
    def _rest_definition(self):
         return bgp.AddressFamily(vrf=self.vrf,asn=self.asn)


    def get(self):
        return  bgp.AddressFamily.get(self.vrf,asn=self.asn)




    def update(self):

        self._rest_definition.update()

    def delete(self):
        self._rest_definition.delete()


    def valid(self):
        return self._rest_definition.valid(should_be_none= not self.routeable_interface)

