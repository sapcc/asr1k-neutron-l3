# Copyright 2020 SAP SE
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
from neutron.tests import base

from asr1k_neutron_l3.models.asr1k_pair import FakeASR1KContext
from asr1k_neutron_l3.models.netconf_yang.l2_interface import BridgeDomain
from asr1k_neutron_l3.models.netconf_yang.vrf import VrfDefinition


class ParsingTest(base.BaseTestCase):
    def test_bridgedomain_Parsing(self):
        bd_xml = """
<rpc-reply message-id="urn:uuid:d5a26f2e-38c1-4f82-9cc4-e0212cc8ef00" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <bridge-domain>
        <brd-id xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-bridge-domain">
          <bridge-domain-id>9000</bridge-domain-id>
          <mac>
            <learning/>
          </mac>
          <member>
            <member-interface>
              <interface>Port-channel1</interface>
              <service-instance-list>
                <instance-id>6723</instance-id>
              </service-instance-list>
              <service-instance>6723</service-instance>
            </member-interface>
            <member-interface>
              <interface>Port-channel2</interface>
              <service-instance-list>
                <instance-id>6379</instance-id>
              </service-instance-list>
              <service-instance-list>
                <instance-id>6383</instance-id>
              </service-instance-list>
              <service-instance>6379</service-instance>
            </member-interface>
            <BD-VIF>
              <name>9003</name>
            </BD-VIF>
            <BD-VIF>
              <name>9004</name>
            </BD-VIF>
          </member>
        </brd-id>
      </bridge-domain>
    </native>
  </data>
</rpc-reply>"""

        context = FakeASR1KContext()
        bd = BridgeDomain.from_xml(bd_xml, context)
        self.assertEqual(bd.id, "9000")

        bdvifs = [int(bdvif.name) for bdvif in bd.bdvif_members]
        self.assertEqual([9003, 9004], bdvifs)

        self.assertEqual(bd.if_members[0].interface, "Port-channel1")
        self.assertEqual(bd.if_members[0].service_instances[0].id, "6723")
        self.assertEqual(bd.if_members[1].interface, "Port-channel2")
        bdif2_ids = [int(si.id) for si in bd.if_members[1].service_instances]
        self.assertEqual(bdif2_ids, [6379, 6383])

    def test_vrf_parsing_with_rt(self):
        vrf_xml_1609_multi = """
<rpc-reply message-id="urn:uuid:68f753a2-4d41-45ad-98f7-3a6460c8dd9d" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <vrf>
        <definition>
          <name>1ccc4863d8bc4c82affa0cb198e8d5d1</name>
          <description>Router 1ccc4863-d8bc-4c82-affa-0cb198e8d5d1</description>
          <rd>65148:871</rd>
          <address-family>
            <ipv4>
              <export>
                <map>exp-1ccc4863d8bc4c82affa0cb198e8d5d1</map>
              </export>
              <route-target>
                <export>
                  <asn-ip>4268359684:12345</asn-ip>
                </export>
                <export>
                  <asn-ip>65148:12345</asn-ip>
                </export>
                <import>
                  <asn-ip>4268359685:12345</asn-ip>
                </import>
                <import>
                  <asn-ip>65148:12345</asn-ip>
                </import>
              </route-target>
            </ipv4>
          </address-family>
        </definition>
      </vrf>
    </native>
  </data>
</rpc-reply>
"""
        vrf_xml_1609_single = """
<rpc-reply message-id="urn:uuid:68f753a2-4d41-45ad-98f7-3a6460c8dd9d" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <vrf>
        <definition>
          <name>1ccc4863d8bc4c82affa0cb198e8d5d1</name>
          <description>Router 1ccc4863-d8bc-4c82-affa-0cb198e8d5d1</description>
          <rd>65148:871</rd>
          <address-family>
            <ipv4>
              <export>
                <map>exp-1ccc4863d8bc4c82affa0cb198e8d5d1</map>
              </export>
              <route-target>
                <export>
                  <asn-ip>4268359684:12345</asn-ip>
                </export>
                <import>
                  <asn-ip>4268359685:12345</asn-ip>
                </import>
              </route-target>
            </ipv4>
          </address-family>
        </definition>
      </vrf>
    </native>
  </data>
</rpc-reply>
"""

        vrf_xml_1731 = """
<rpc-reply message-id="urn:uuid:d40a38bd-0a67-4f09-86b1-42ea770a8b5e" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <vrf>
        <definition>
          <name>1ccc4863d8bc4c82affa0cb198e8d5d1</name>
          <description>Router 1ccc4863-d8bc-4c82-affa-0cb198e8d5d1</description>
          <rd>65148:871</rd>
          <address-family>
            <ipv4>
              <export>
                <map>exp-1ccc4863d8bc4c82affa0cb198e8d5d1</map>
              </export>
              <route-target>
                <export-route-target>
                  <without-stitching>
                    <asn-ip>65130.4:12345</asn-ip>
                  </without-stitching>
                  <without-stitching>
                    <asn-ip>65148:12345</asn-ip>
                  </without-stitching>
                </export-route-target>
                <import-route-target>
                  <without-stitching>
                    <asn-ip>65130.5:12345</asn-ip>
                  </without-stitching>
                  <without-stitching>
                    <asn-ip>65148:12345</asn-ip>
                  </without-stitching>
                </import-route-target>
              </route-target>
            </ipv4>
          </address-family>
        </definition>
      </vrf>
    </native>
  </data>
</rpc-reply>
"""

        expected_single = {
            "rt_export": {"4268359684:12345", },
            "rt_import": {"4268359685:12345"},
        }
        expected_multi = {
            "rt_export": {"4268359684:12345", "65148:12345"},
            "rt_import": {"4268359685:12345", "65148:12345"},
        }

        context_1609 = FakeASR1KContext(version_min_17_3=False)
        context_17_3 = FakeASR1KContext(version_min_17_3=True)

        for context, vrf_xml, expected in ((context_1609, vrf_xml_1609_single, expected_single),
                                           (context_1609, vrf_xml_1609_multi, expected_multi),
                                           (context_17_3, vrf_xml_1731, expected_multi)):
            vrf = VrfDefinition.from_xml(vrf_xml, context)
            self.assertEqual(expected['rt_export'],
                             set([rt.normalized_asn_ip for rt in vrf.address_family_ipv4.rt_export]),
                             "rt_export failed for 17_3={}".format(context.version_min_17_3))
            self.assertEqual(expected['rt_import'],
                             set([rt.normalized_asn_ip for rt in vrf.address_family_ipv4.rt_import]),
                             "rt_import failed for 17_3={}".format(context.version_min_17_3))
