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
from asr1k_neutron_l3.common.utils import from_cidr, to_cidr
from asr1k_neutron_l3.models.netconf_yang import bgp
from asr1k_neutron_l3.models.netconf_yang.l2_interface import BridgeDomain
from asr1k_neutron_l3.models.netconf_yang.vrf import VrfDefinition
from asr1k_neutron_l3.models.netconf_yang.nat import StaticNatList


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

    def test_bgp_parsing(self):
        bgp_xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"
           message-id="urn:uuid:9caf3918-3eb9-4d0e-a8a5-5ec268e3bf97">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <router>
        <bgp xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-bgp">
          <id>65148</id>
          <address-family>
            <with-vrf>
              <ipv4>
                <af-name>unicast</af-name>
                <vrf>
                  <name>7beea201af384c1385fb9b531c73ad95</name>
                  <ipv4-unicast>
                    <network>
                      <with-mask>
                        <number>10.180.0.0</number>
                        <mask>255.255.255.0</mask>
                      </with-mask>
                      <with-mask>
                        <number>10.180.1.0</number>
                        <mask>255.255.255.0</mask>
                      </with-mask>
                      <with-mask>
                        <number>10.236.41.192</number>
                        <mask>255.255.255.192</mask>
                        <route-map>wubwubwub</route-map>
                      </with-mask>
                      <with-mask>
                        <number>10.236.41.201</number>
                        <mask>255.255.255.255</mask>
                      </with-mask>
                    </network>
                    <redistribute-vrf>
                      <connected/>
                      <static/>
                    </redistribute-vrf>
                  </ipv4-unicast>
                </vrf>
              </ipv4>
            </with-vrf>
          </address-family>
        </bgp>
      </router>
    </native>
  </data>
</rpc-reply>
"""
        orig_cidrs = {"10.180.0.0/24", "10.180.1.0/24", "10.236.41.192/26", "10.236.41.201/32"}
        cidrs_with_route_map = {"10.236.41.192/26"}
        rm_name = "wubwubwub"

        context = FakeASR1KContext()
        bgp_af = bgp.AddressFamily.from_xml(bgp_xml, context)
        parsed_cidrs = {net.cidr for net in bgp_af.networks_v4}
        self.assertEqual(orig_cidrs, parsed_cidrs)
        for network in bgp_af.networks_v4:
            expected_rm = rm_name if network.cidr in cidrs_with_route_map else None
            self.assertEqual(network.route_map, expected_rm)

        nets = [bgp.Network.from_cidr(cidr, route_map=rm_name if cidr in cidrs_with_route_map else None)
                for cidr in orig_cidrs]
        bgp_af = bgp.AddressFamily(vrf="meow", networks_v4=nets)
        result = bgp_af.to_dict(context)

        orig_netmasks = {from_cidr(cidr) for cidr in orig_cidrs}
        parsed_netmasks = set()
        for network in result["vrf"]["ipv4-unicast"]["network"]["with-mask"]:
            cidr = to_cidr(network['number'], network['mask'])
            expected_rm = rm_name if cidr in cidrs_with_route_map else None
            self.assertEqual(network.get("route-map"), expected_rm)
            parsed_netmasks.add((network['number'], network['mask']))
        self.assertEqual(orig_netmasks, parsed_netmasks)

    def test_static_nat_parsing(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"
    message-id="urn:uuid:9caf3918-3eb9-4d0e-a8a5-5ec268e3bf97">
    <data>
        <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
            <ip>
                <nat xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
                    <inside>
                        <source>
                            <static>
                                <nat-static-transport-list-with-vrf>
                                    <local-ip>10.20.30.40</local-ip>
                                    <global-ip>10.10.10.10</global-ip>
                                    <vrf>route-it-like-they-do-on-discovery-channel</vrf>
                                    <match-in-vrf />
                                    <stateless />
                                    <no-alias />
                                </nat-static-transport-list-with-vrf>
                            </static>
                        </source>
                    </inside>
                </nat>
            </ip>
        </native>
    </data>
</rpc-reply>
"""

        context = FakeASR1KContext()
        snl = StaticNatList.from_xml(xml, context)
        self.assertEqual(1, len(snl.static_nats))
        nat = snl.static_nats[0]
        self.assertEqual('10.20.30.40', nat.local_ip)
        self.assertEqual('10.10.10.10', nat.global_ip)
        self.assertEqual('route-it-like-they-do-on-discovery-channel', nat.vrf)
        self.assertIsNone(nat.redundancy)
        self.assertIsNone(nat.mapping_id)
        self.assertTrue(nat.match_in_vrf)
        self.assertTrue(nat.stateless)
        self.assertTrue(nat.no_alias)
