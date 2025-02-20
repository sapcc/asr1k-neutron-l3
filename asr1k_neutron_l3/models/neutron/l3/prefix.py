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
    def __init__(self, name_prefix, router_id, prefixes, add_deny_if_empty=False):
        self.vrf = utils.uuid_to_vrf_id(router_id)
        self.name = f"{name_prefix}-{self.vrf}"
        self.prefixes = prefixes
        self._rest_definition = self.PREFIX_MODEL(name=self.name)

        for n, pfx in enumerate(prefixes, 1):
            self._rest_definition.add_seq(
                self._make_seq(n * 10, pfx)
            )

        if add_deny_if_empty and not prefixes:
            self._rest_definition.add_seq(
                # use 4242 as a likely not-used seq no
                self._make_seq(4242, self.DEFAULT, action="deny")
            )

    def diff(self, should_be_none=False):
        return super().diff(should_be_none=not self.prefixes)

    def _make_seq(self, no, cidr, action="permit"):
        return prefix.PrefixSeq(no=no, action=action, ip=cidr)


class BasePrefixV4(BasePrefix):
    PREFIX_MODEL = prefix.PrefixV4
    DEFAULT = "0.0.0.0/0"


class BasePrefixV6(BasePrefix):
    PREFIX_MODEL = prefix.PrefixV6
    DEFAULT = "::/0"


# ext prefix, containing externally routed prefixes
class ExtPrefixMixIn:
    def __init__(self, *args, **kwargs):
        super().__init__(name_prefix='ext', *args, **kwargs)


class ExtPrefixV4(ExtPrefixMixIn, BasePrefixV4):
    pass


class ExtPrefixV6(ExtPrefixMixIn, BasePrefixV6):
    pass


# snat prefixes, list containing everything that should not be snatted
class SnatPrefix(BasePrefixV4):
    def __init__(self, *args, **kwargs):
        super().__init__(name_prefix='snat', *args, **kwargs)


# everything that should be routed
class RoutePrefixMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(name_prefix='route', *args, **kwargs)

    def _make_seq(self, no, cidr, action="permit"):
        permit_ge = utils.prefix_from_cidr(cidr) + 1
        return prefix.PrefixSeq(no=no, action=action, ip=cidr, ge=permit_ge)


class RoutePrefixV4(RoutePrefixMixin, BasePrefixV4):
    pass


class RoutePrefixV6(RoutePrefixMixin, BasePrefixV6):
    pass
