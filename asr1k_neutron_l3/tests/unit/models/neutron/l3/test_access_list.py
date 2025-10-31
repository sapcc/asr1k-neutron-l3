# Copyright 2026 SAP SE
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

from asr1k_neutron_l3.models.neutron.l3.access_list import AccessList, Rule
from asr1k_neutron_l3.tests.common.fixtures import RouterWithSyncDataTestCase


class TestAccessList(RouterWithSyncDataTestCase):

    def test_access_list_rule_deduplication(self):
        acl = AccessList(id='test-acl')

        # create two identical rules (must be two rules, so they are different instances, for eq check)
        rule1 = Rule(action='permit',
                     protocol='tcp',
                     source='10.0.0.1',
                     destination='10.0.0.2',
                     destination_port_range=("443",))
        rule2 = Rule(action='permit',
                     protocol='tcp',
                     source='10.0.0.1',
                     destination='10.0.0.2',
                     destination_port_range=("443",))

        rule3 = Rule(action='permit',
                     protocol='tcp',
                     source='10.0.0.6',
                     destination='10.0.0.7',
                     destination_port_range=["443"])

        rule4 = Rule(action='permit',
                     protocol='tcp',
                     source='10.0.0.6',
                     destination='10.0.0.7',
                     destination_port_range=["443"])

        acl.append_rule(rule1)
        acl.append_rule(rule2)
        acl.append_rule(rule3)
        acl.append_rule(rule4)

        self.assertEqual(2, len(acl._rest_definition.rules))
