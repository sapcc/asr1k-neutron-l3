# Copyright 2022 SAP SE
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from copy import deepcopy
import xmltodict

from neutron.tests import base

from asr1k_neutron_l3.models.asr1k_pair import FakeASR1KContext
from asr1k_neutron_l3.models.netconf_yang.nat import NATConstants, StaticNat


class SerializationTest(base.BaseTestCase):

    def test_static_nat(self):
        sn_args = dict(
            vrf='you-and-me-baby-aint-nothin-but-mammals',
            local_ip='10.10.23.12', global_ip='192.168.23.12',
            match_in_vrf=True
        )
        sn_stateless = StaticNat(**sn_args, stateless=True)
        sn = StaticNat(**sn_args, stateless=False)

        context_17_3 = FakeASR1KContext(version_min_17_3=True, version_min_17_6=False)
        context_17_6 = FakeASR1KContext(version_min_17_3=True, version_min_17_6=True)

        expected_17_3 = xmltodict.parse("""
                            <nat-static-transport-list-with-vrf>
                                <local-ip>10.10.23.12</local-ip>
                                <global-ip>192.168.23.12</global-ip>
                                <vrf>you-and-me-baby-aint-nothin-but-mammals</vrf>
                                <match-in-vrf></match-in-vrf>
                            </nat-static-transport-list-with-vrf>""")[NATConstants.TRANSPORT_LIST]

        for k in expected_17_3:
            if expected_17_3[k] is None:
                expected_17_3[k] = ''

        expected_stateless_17_3 = deepcopy(expected_17_3)
        expected_stateless_17_3['stateless'] = ''

        expected_17_6 = deepcopy(expected_stateless_17_3)
        expected_17_6['no-alias'] = ''

        self.assertEqual(expected_17_3, sn.to_single_dict(context_17_3))
        self.assertEqual(expected_stateless_17_3,
                         sn_stateless.to_single_dict(context_17_3))

        self.assertEqual(expected_17_6, sn.to_single_dict(context_17_6))
        self.assertEqual(expected_17_6,
                         sn_stateless.to_single_dict(context_17_6))
