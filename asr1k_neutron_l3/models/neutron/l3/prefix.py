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
from asr1k_neutron_l3.common import utils

from asr1k_neutron_l3.models.netconf_yang import prefix

class BasePrefix(base.Base):

    def __init__(self,router_id=None,gateway_interface=None, internal_interfaces=None):
        self.vrf = utils.uuid_to_vrf_id(router_id)
        self.internal_interfaces = internal_interfaces
        self.gateway_interface = gateway_interface
        self.gateway_address_scope = None

        if self.gateway_interface is not None:
            self.gateway_address_scope = self.gateway_interface.address_scope

        self.has_prefixes = False

    def update(self):
        self.rest_definition.update()

    def delete(self):
        self.rest_definition.delete()

    def valid(self,should_be_none=False):
        self.rest_definition.valid(should_be_none=should_be_none)


class ExtPrefix(BasePrefix):

    def __init__(self,router_id=None,gateway_interface=None, internal_interfaces=None):
        super(ExtPrefix,self).__init__(router_id=router_id,gateway_interface=gateway_interface, internal_interfaces=internal_interfaces)
        self.name = 'ext-{}'.format(self.vrf)

        self.rest_definition = prefix.Prefix(name=self.name)

        if self.gateway_interface is not None:
            i = 0
            for subnet in self.gateway_interface.subnets:
                self.has_prefixes = True
                i+=1
                self.rest_definition.add_seq(prefix.PrefixSeq(no=i*10,permit_ip=subnet.get('cidr')))




class SnatPrefix(BasePrefix):
    def __init__(self, router_id=None,gateway_interface=None, internal_interfaces=None):
        super(SnatPrefix,self).__init__(router_id=router_id,gateway_interface=gateway_interface, internal_interfaces=internal_interfaces)
        self.name = 'snat-{}'.format(self.vrf)

        self.rest_definition = prefix.Prefix(name=self.name)
        i=0
        for interface in self.internal_interfaces:
            i += 1
            for subnet in interface.subnets:
                self.has_prefixes = True
                self.rest_definition.add_seq(prefix.PrefixSeq(no=i * 10, permit_ip=subnet.get('cidr')))
                i += 1