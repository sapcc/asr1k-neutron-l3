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
from asr1k_neutron_l3.models.netconf_yang import vrf
from asr1k_neutron_l3.common import utils


class Vrf(base.Base):
    def __init__(self, name, description=None,asn=None,rd=None,routeable_interface=False):
        super(Vrf, self).__init__()
        self.name = utils.uuid_to_vrf_id(name)
        self.description = description
        self.routeable_interface = routeable_interface

        self.asn=None
        self.rd =None
        self.asn = asn
        self.rd = utils.to_rd(self.asn, rd)

        self.disable_bgp = False

        # self.disable_bgp = True
        #
        # if self.routeable_interface:
        #     self.disable_bgp = False


    @property
    def _rest_definition(self):
         return vrf.VrfDefinition(name=self.name, description=self.description, rd=self.rd, disable_bgp=self.disable_bgp)


    def get(self):
        return vrf.VrfDefinition.get(self.name)




    def update(self):
        self._rest_definition.update()


    def delete(self):
        self._rest_definition.delete()


    def valid(self):
        return self._rest_definition.is_valid()

