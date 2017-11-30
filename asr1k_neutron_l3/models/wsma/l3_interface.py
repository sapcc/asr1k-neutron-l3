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

from asr1k_neutron_l3.models.wsma import templates
from asr1k_neutron_l3.models.wsma import wsma_base


class BDIInterface(wsma_base.WSMABase):

    def to_data(self):
        command1 = self.ADD_NAT_TO_BDI.format(**{'id': self.base.id, 'nat_mode': self.base.nat_mode})
        commnnd2 = self.NO_SHUTDOWN

        return templates.CONFIG_TEMPLATE.format(
            **{'command1': command1, 'command2': commnnd2, 'correlator': self.base.id})

    ADD_NAT_TO_BDI = "interface BDI{id} ip nat {nat_mode}"
    NO_SHUTDOWN = "no shutdown"
