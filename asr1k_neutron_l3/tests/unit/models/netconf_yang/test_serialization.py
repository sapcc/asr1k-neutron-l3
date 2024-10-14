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
        context_17_6 = FakeASR1KContext(version_min_17_13=False, version_min_17_15=False)
        expected = xmltodict.parse("""
                            <nat-static-transport-list-with-vrf>
                                <local-ip>10.10.23.12</local-ip>
                                <global-ip>192.168.23.12</global-ip>
                                <vrf>you-and-me-baby-aint-nothin-but-mammals</vrf>
                                <match-in-vrf></match-in-vrf>
                            </nat-static-transport-list-with-vrf>""")[NATConstants.TRANSPORT_LIST]

        for k in expected:
            if expected[k] is None:
                expected[k] = ''

        expected['stateless'] = ''
        expected['no-alias'] = ''

        self.assertEqual(expected,
                         sn_stateless.to_single_dict(context_17_6))

    def test_static_nat_garp_flag(self):
        sn_args = dict(
            vrf='the-seagull-is-a-majestic-bird',
            local_ip='10.10.23.12', global_ip='192.168.23.12',
            match_in_vrf=True, garp_bdvif_iface=1234
        )
        sn = StaticNat(**sn_args)

        context_17_13 = FakeASR1KContext()
        self.assertEqual({'BD-VIF': '1234'}, sn.to_single_dict(context_17_13).get('garp-interface'))

        context_17_6 = FakeASR1KContext(version_min_17_13=False)
        self.assertNotIn('garp-interface', sn.to_single_dict(context_17_6))

    def test_static_nat_garp_flag_remove(self):
        sn_args = dict(
            vrf='the-seagull-is-a-majestic-bird',
            local_ip='10.10.23.12', global_ip='192.168.23.12',
            match_in_vrf=True
        )
        sn = StaticNat(**sn_args)

        context_17_13 = FakeASR1KContext()
        self.assertEqual({'@operation': 'remove'}, sn.to_single_dict(context_17_13).get('garp-interface'))
