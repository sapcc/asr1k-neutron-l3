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
from asr1k_neutron_l3.models.rest import vrf
from asr1k_neutron_l3.plugins.common import utils


class Vrf(base.Base):
    def __init__(self, name, description=None):
        super(Vrf, self).__init__()
        self.name = utils.uuid_to_vrf_id(name)
        self.description = description



    @property
    def _rest_definition(self):
         return vrf.VrfDefinition(name=self.name, description=self.description)


    def get(self):
        return vrf.VrfDefinition.get(self.name)


    def update(self):

        return self._rest_definition.update()


    def delete(self):

        return self._rest_definition.delete()


    def purge(self):
        return self._rest_definition.delete()

    def valid(self):
        return self._rest_definition == self.get()

