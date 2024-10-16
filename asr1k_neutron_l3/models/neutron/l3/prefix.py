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
from operator import itemgetter, attrgetter

from asr1k_neutron_l3.models.neutron.l3 import base
from asr1k_neutron_l3.common import utils

from asr1k_neutron_l3.models.netconf_yang import prefix


class BasePrefix(base.Base):
    def __init__(self, name_prefix, router_id, gateway_interface, internal_interfaces):
        self.vrf = utils.uuid_to_vrf_id(router_id)
        self.internal_interfaces = internal_interfaces
        self.gateway_interface = gateway_interface
        self.gateway_address_scope = None
        self.has_prefixes = False

        if self.gateway_interface is not None:
            self.gateway_address_scope = self.gateway_interface.address_scope

        self._rest_definition = prefix.Prefix(name="{}-{}".format(name_prefix, self.vrf))

    def diff(self, should_be_none=False):
        return super().diff(should_be_none=not self.has_prefixes)


class ExtPrefix(BasePrefix):
    def __init__(self, router_id=None, gateway_interface=None, internal_interfaces=None):
        super(ExtPrefix, self).__init__(name_prefix='ext', router_id=router_id, gateway_interface=gateway_interface,
                                        internal_interfaces=internal_interfaces)

        if self.gateway_interface is not None:
            i = 1
            for subnet in sorted(self.gateway_interface.subnets, key=itemgetter('id')):
                self.has_prefixes = True
                self._rest_definition.add_seq(
                    prefix.PrefixSeq(no=i * 10, action="permit", ip=subnet.get('cidr')))
                i += 1


class SnatPrefix(BasePrefix):
    def __init__(self, router_id=None, gateway_interface=None, internal_interfaces=None):
        super(SnatPrefix, self).__init__(name_prefix='snat', router_id=router_id, gateway_interface=gateway_interface,
                                         internal_interfaces=internal_interfaces)

        i = 1
        for interface in sorted(self.internal_interfaces, key=attrgetter('id')):
            for subnet in sorted(interface.subnets, key=itemgetter('id')):
                self.has_prefixes = True
                self._rest_definition.add_seq(
                    prefix.PrefixSeq(no=i * 10, action="permit", ip=subnet.get('cidr')))
                i += 1


class RoutePrefix(BasePrefix):
    def __init__(self, router_id=None, gateway_interface=None, internal_interfaces=None):
        super(RoutePrefix, self).__init__(name_prefix='route', router_id=router_id, gateway_interface=gateway_interface,
                                          internal_interfaces=internal_interfaces)

        i = 1
        for interface in sorted(self.internal_interfaces, key=attrgetter('id')):
            for subnet in sorted(interface.subnets, key=itemgetter('id')):
                self.has_prefixes = True
                cidr = subnet.get('cidr')
                permit_ge = utils.prefix_from_cidr(cidr) + 1
                self._rest_definition.add_seq(
                    prefix.PrefixSeq(no=i * 10, action="permit", ip=cidr, ge=permit_ge))
                i += 1
