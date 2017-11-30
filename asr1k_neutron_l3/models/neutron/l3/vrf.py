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
    def __init__(self, id, description=None):
        super(Vrf, self).__init__()
        self.id = utils.uuid_to_vrf_id(id)
        self.description = description

    @base.excute_on_pair
    def purge(cls, context, id):
        vrf_definition = vrf.VrfDefinition.get(context, utils.uuid_to_vrf_id(id))
        if vrf_definition is not None:
            vrf_definition.delete()

    @base.excute_on_pair
    def update(self, context=None):
        vrf_definition = vrf.VrfDefinition(context, id=self.id, description=self.description)
        vrf_definition.update()

    @base.excute_on_pair
    def delete(self, context=None):
        vrf_definition = vrf.VrfDefinition(context, id=self.id, description=self.description)
        vrf_definition.delete()

    @base.excute_on_pair
    def purge(self, context=None):
        vrf_definition = vrf.VrfDefinition(context, id=self.id, description=self.description)
        vrf_definition.delete()
