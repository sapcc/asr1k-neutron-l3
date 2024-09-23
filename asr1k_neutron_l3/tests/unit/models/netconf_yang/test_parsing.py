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
from asr1k_neutron_l3.models.netconf_yang.access_list import AccessList
from asr1k_neutron_l3.models.netconf_yang.arp_cache import ArpCache
from asr1k_neutron_l3.models.netconf_yang import bgp
from asr1k_neutron_l3.models.netconf_yang.class_map import ClassMap
from asr1k_neutron_l3.models.netconf_yang.l2_interface import BridgeDomain
from asr1k_neutron_l3.models.netconf_yang.vrf import VrfDefinition
from asr1k_neutron_l3.models.netconf_yang.nat import InterfaceDynamicNat, PoolDynamicNat, StaticNatList
from asr1k_neutron_l3.models.netconf_yang.parameter_map import ParameterMapInspectGlobalVrf
from asr1k_neutron_l3.models.netconf_yang.prefix import Prefix
from asr1k_neutron_l3.models.netconf_yang.service_policy import ServicePolicy
from asr1k_neutron_l3.models.netconf_yang.zone import Zone
from asr1k_neutron_l3.models.netconf_yang.zone_pair import ZonePair


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

    def test_arp_cache_parsing(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"
           message-id="urn:uuid:37bffcac-d037-48c6-b382-f29aaeddaa4a">
  <data>
    <arp-data xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-arp-oper">
      <arp-vrf>
        <vrf>07c1791106244933b693282c5447adfe</vrf>
        <arp-entry>
          <address>10.180.0.1</address>
          <hardware>fa:16:3e:45:81:b2</hardware>
        </arp-entry>
        <arp-entry>
          <address>10.180.0.3</address>
          <hardware>fa:16:3e:ff:aa:bb</hardware>
        </arp-entry>
      </arp-vrf>
      <arp-vrf>
        <vrf>2742f0347af546878c600d608cf38382</vrf>
        <arp-entry>
          <address>1.2.3.4</address>
          <hardware>fa:16:3e:11:22:33</hardware>
        </arp-entry>
      </arp-vrf>
    </arp-data>
  </data>
</rpc-reply>"""

        context = FakeASR1KContext()
        cache = ArpCache.from_xml(xml, context)
        self.assertEqual(2, len(cache.vrfs))

        vrf0 = cache.vrfs[0]
        self.assertEqual(2, len(vrf0.entries))
        self.assertEqual("07c1791106244933b693282c5447adfe", vrf0.vrf)
        self.assertEqual("10.180.0.1", vrf0.entries[0].address)
        self.assertEqual("fa:16:3e:45:81:b2", vrf0.entries[0].mac)
        self.assertEqual("10.180.0.3", vrf0.entries[1].address)
        self.assertEqual("fa:16:3e:ff:aa:bb", vrf0.entries[1].mac)

        vrf1 = cache.vrfs[1]
        self.assertEqual(1, len(vrf1.entries))
        self.assertEqual("2742f0347af546878c600d608cf38382", vrf1.vrf)
        self.assertEqual("1.2.3.4", vrf1.entries[0].address)
        self.assertEqual("fa:16:3e:11:22:33", vrf1.entries[0].mac)

    def test_parse_nat_garp_flag(self):
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
                    <local-ip>10.180.250.161</local-ip>
                    <global-ip>10.216.24.4</global-ip>
                    <vrf>76433b4941974003a881847fda8af23b</vrf>
                    <no-alias/>
                    <match-in-vrf/>
                    <stateless/>
                    <garp-interface>
                      <BD-VIF>6657</BD-VIF>
                    </garp-interface>
                  </nat-static-transport-list-with-vrf>
                </static>
              </source>
            </inside>
          </nat>
        </ip>
      </native>
  </data>
</rpc-reply>"""
        context = FakeASR1KContext()
        snl = StaticNatList.from_xml(xml, context)
        nat = snl.static_nats[0]
        self.assertEqual('6657', nat.garp_bdvif_iface)

    def test_acl_parsing(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"
           message-id="urn:uuid:37bffcac-d037-48c6-b382-f29aaeddaa4a">
<data>
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
    <ip>
      <access-list>
        <extended xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-acl">
          <name>ACL-FWAAS-TEST-ACL</name>
          <access-list-seq-rule>
            <sequence>10</sequence>
            <ace-rule>
              <action>permit</action>
              <protocol>tcp</protocol>
              <any/>
              <dst-any/>
              <established/>
            </ace-rule>
          </access-list-seq-rule>
          <access-list-seq-rule>
            <sequence>20</sequence>
            <ace-rule>
              <action>permit</action>
              <protocol>icmp</protocol>
              <any/>
              <dst-any/>
              <named-msg-type>echo-reply</named-msg-type>
            </ace-rule>
          </access-list-seq-rule>
          <access-list-seq-rule>
            <sequence>100</sequence>
            <ace-rule>
              <action>deny</action>
              <protocol>tcp</protocol>
              <host-address>1.1.1.1</host-address>
              <host>1.1.1.1</host>
              <dst-host-address>2.2.2.2</dst-host-address>
              <dst-host>2.2.2.2</dst-host>
              <dst-eq>3333</dst-eq>
            </ace-rule>
          </access-list-seq-rule>
          <access-list-seq-rule>
            <sequence>110</sequence>
            <ace-rule>
              <action>permit</action>
              <protocol>udp</protocol>
              <ipv4-address>10.0.0.0</ipv4-address>
              <mask>0.0.0.255</mask>
              <dest-ipv4-address>192.16.0.0</dest-ipv4-address>
              <dest-mask>0.0.0.16</dest-mask>
              <dst-eq>22</dst-eq>
            </ace-rule>
          </access-list-seq-rule>
          <access-list-seq-rule>
            <sequence>120</sequence>
            <ace-rule>
              <action>permit</action>
              <protocol>tcp</protocol>
              <ipv4-address>192.16.0.0</ipv4-address>
              <mask>0.0.0.16</mask>
              <dest-ipv4-address>10.0.0.0</dest-ipv4-address>
              <dest-mask>0.0.0.255</dest-mask>
              <dst-range1>1999</dst-range1>
              <dst-range2>2991</dst-range2>
            </ace-rule>
          </access-list-seq-rule>
          <access-list-seq-rule>
            <sequence>130</sequence>
            <ace-rule>
              <action>deny</action>
              <protocol>icmp</protocol>
              <ipv4-address>100.200.0.0</ipv4-address>
              <mask>0.0.255.255</mask>
              <dst-any/>
            </ace-rule>
          </access-list-seq-rule>
          <access-list-seq-rule>
            <sequence>150</sequence>
            <ace-rule>
              <action>deny</action>
              <protocol>udp</protocol>
              <host-address>1.1.1.1</host-address>
              <host>1.1.1.1</host>
              <src-range1>10000</src-range1>
              <src-range2>20000</src-range2>
              <dst-any/>
            </ace-rule>
          </access-list-seq-rule>
          <access-list-seq-rule>
            <sequence>160</sequence>
            <ace-rule>
              <action>deny</action>
              <protocol>ip</protocol>
              <ipv4-address>192.168.1.0</ipv4-address>
              <mask>0.0.0.255</mask>
              <dest-ipv4-address>192.168.2.0</dest-ipv4-address>
              <dest-mask>0.0.0.255</dest-mask>
            </ace-rule>
          </access-list-seq-rule>
        </extended>
      </access-list>
    </ip>
  </native>
</data>
</rpc-reply>
"""

        context = FakeASR1KContext()
        acl = AccessList.from_xml(xml, context)
        self.assertEqual("ACL-FWAAS-TEST-ACL", acl.id)
        self.assertEqual("ACL-FWAAS-TEST-ACL", acl.name)
        self.assertEqual(8, len(acl.rules))
        rules = acl.rules

        rule = rules[0]
        self.assertEqual("10", rule.sequence)
        ace = rule.ace_rule[0]
        self.assertEqual("permit", ace.action)
        self.assertEqual("tcp", ace.protocol)
        self.assertTrue(ace.any)
        self.assertTrue(ace.dst_any)
        self.assertTrue(ace.established)

        rule = rules[1]
        self.assertEqual("20", rule.sequence)
        ace = rule.ace_rule[0]
        self.assertEqual("permit", ace.action)
        self.assertEqual("icmp", ace.protocol)
        self.assertTrue(ace.any)
        self.assertTrue(ace.dst_any)
        self.assertEqual("echo-reply", ace.named_message_type)

        rule = rules[2]
        self.assertEqual("100", rule.sequence)
        ace = rule.ace_rule[0]
        self.assertEqual("deny", ace.action)
        self.assertEqual("tcp", ace.protocol)
        self.assertEqual("1.1.1.1", ace.host)
        self.assertEqual("2.2.2.2", ace.dst_host)
        self.assertEqual("3333", ace.dst_eq)

        rule = rules[3]
        self.assertEqual("110", rule.sequence)
        ace = rule.ace_rule[0]
        self.assertEqual("permit", ace.action)
        self.assertEqual("udp", ace.protocol)
        self.assertEqual("10.0.0.0", ace.ipv4_address)
        self.assertEqual("0.0.0.255", ace.mask)
        self.assertEqual("192.16.0.0", ace.dest_ipv4_address)
        self.assertEqual("0.0.0.16", ace.dest_mask)
        self.assertEqual("22", ace.dst_eq)

        rule = rules[4]
        self.assertEqual("120", rule.sequence)
        ace = rule.ace_rule[0]
        self.assertEqual("permit", ace.action)
        self.assertEqual("tcp", ace.protocol)
        self.assertEqual("192.16.0.0", ace.ipv4_address)
        self.assertEqual("0.0.0.16", ace.mask)
        self.assertEqual("10.0.0.0", ace.dest_ipv4_address)
        self.assertEqual("0.0.0.255", ace.dest_mask)
        self.assertEqual("1999", ace.dst_range1)
        self.assertEqual("2991", ace.dst_range2)

        rule = rules[5]
        self.assertEqual("130", rule.sequence)
        ace = rule.ace_rule[0]
        self.assertEqual("deny", ace.action)
        self.assertEqual("icmp", ace.protocol)
        self.assertEqual("100.200.0.0", ace.ipv4_address)
        self.assertEqual("0.0.255.255", ace.mask)
        self.assertTrue(ace.dst_any)

        rule = rules[6]
        self.assertEqual("150", rule.sequence)
        ace = rule.ace_rule[0]
        self.assertEqual("deny", ace.action)
        self.assertEqual("udp", ace.protocol)
        self.assertEqual("1.1.1.1", ace.host)
        self.assertEqual("10000", ace.src_range1)
        self.assertEqual("20000", ace.src_range2)
        self.assertTrue(ace.dst_any)

        rule = rules[7]
        self.assertEqual("160", rule.sequence)
        ace = rule.ace_rule[0]
        self.assertEqual("deny", ace.action)
        self.assertEqual("ip", ace.protocol)
        self.assertEqual("192.168.1.0", ace.ipv4_address)
        self.assertEqual("0.0.0.255", ace.mask)

    def test_class_map_parsing(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"
           message-id="urn:uuid:37bffcac-d037-48c6-b382-f29aaeddaa4a">
<data>
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
    <policy>
      <class-map xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-policy">
        <name>CM-FWAAS-COFFEE-CRIMES</name>
        <type>inspect</type>
        <prematch>match-all</prematch>
        <match>
          <access-group>
            <name>ACL-FWAAS-FROZEN-CARAMEL-MACHIATO</name>
          </access-group>
        </match>
      </class-map>
    </policy>
  </native>
</data>
</rpc-reply>
"""
        context = FakeASR1KContext()
        cm = ClassMap.from_xml(xml, context)
        self.assertEqual("CM-FWAAS-COFFEE-CRIMES", cm.id)
        self.assertEqual("inspect", cm.type)
        self.assertEqual("match-all", cm.prematch)
        self.assertEqual("ACL-FWAAS-FROZEN-CARAMEL-MACHIATO", cm.acl_id)

    def test_parameter_map_inspect_global_vrf_parsing(self):

        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"
           message-id="urn:uuid:37bffcac-d037-48c6-b382-f29aaeddaa4a">
<data> 
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
    <parameter-map>
      <type>
        <inspect-global xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-policy">
          <icmp-unreachable-allow/>
          <inspect>
            <vrf>
              <id>DAGOBERTDUCK</id>
              <name>PAM-FWAAS-POLICE-VRF</name>
            </vrf>
          </inspect>
        </inspect-global>
      </type>
    </parameter-map>
  </native>
</data>
</rpc-reply>
"""
        context = FakeASR1KContext()
        pm = ParameterMapInspectGlobalVrf.from_xml(xml, context)
        self.assertEqual("DAGOBERTDUCK", pm.vrf)
        self.assertEqual("PAM-FWAAS-POLICE-VRF", pm.parameter_map)

    def test_service_policy_parsing(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"
           message-id="urn:uuid:37bffcac-d037-48c6-b382-f29aaeddaa4a">
<data xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
    <policy>
      <policy-map xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-policy">
        <name>SP-FWAAS-NO-CRAP-ON-TAP</name>
        <type>inspect</type>
        <class>
          <name>CM-FWAAS-NO-CRAP-ON-TAP</name>
          <type>inspect</type>
          <policy>
            <action>inspect</action>
          </policy>
        </class>
        <class>
          <name>class-default</name>
          <policy>
            <action>drop</action>
            <log/>
          </policy>
        </class>
      </policy-map>
    </policy>
  </native>
</data>
</rpc-reply>
"""

        context = FakeASR1KContext()
        sp = ServicePolicy.from_xml(xml, context)
        self.assertEqual("SP-FWAAS-NO-CRAP-ON-TAP", sp.id)
        self.assertEqual("inspect", sp.type)
        classes = sp.classes
        self.assertEqual(2, len(classes))
        self.assertEqual("CM-FWAAS-NO-CRAP-ON-TAP", classes[0].id)
        self.assertEqual("inspect", classes[0].type)
        self.assertEqual("inspect", classes[0].policy_action)
        self.assertEqual("class-default", classes[1].id)
        self.assertEqual("drop", classes[1].policy_action)
        self.assertTrue(classes[1].log)

    def test_zone_parsing(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"
           message-id="urn:uuid:37bffcac-d037-48c6-b382-f29aaeddaa4a">
<data xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
    <zone>
      <security xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-zone">
        <id>ZN-FWAAS-123</id>
      </security>
    </zone>
  </native>
</data>
</rpc-reply>
"""

        context = FakeASR1KContext()
        zone = Zone.from_xml(xml, context)
        self.assertEqual("ZN-FWAAS-123", zone.id)

    def test_zone_pair_parsing(self):
        xml = """
    <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"
            message-id="urn:uuid:37bffcac-d037-48c6-b382-f29aaeddaa4a">
    <data xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
        <zone-pair>
        <security xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-zone">
            <id>ZP-FWAAS-EXT-EGRESS-123</id>
            <source>default</source>
            <destination>ZN-FWAAS-123</destination>
            <service-policy>
            <type>
                <inspect>SP-FWAAS-ALLOW-INSPECT</inspect>
            </type>
            </service-policy>
        </security>
        </zone-pair>
    </native>
    </data>
    </rpc-reply>
    """
        context = FakeASR1KContext()
        zone_pair = ZonePair.from_xml(xml, context)
        self.assertEqual("ZP-FWAAS-EXT-EGRESS-123", zone_pair.id)
        self.assertEqual("default", zone_pair.source)
        self.assertEqual("ZN-FWAAS-123", zone_pair.destination)
        self.assertEqual("SP-FWAAS-ALLOW-INSPECT", zone_pair.service_policy)
        
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"
        message-id="urn:uuid:37bffcac-d037-48c6-b382-f29aaeddaa4a">
<data xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
<native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
    <zone-pair>
      <security xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-zone">
        <id>ZP-FWAAS-EXT-INGRESS-123</id>
        <source>ZN-FWAAS-123</source>
        <destination>default</destination>
        <service-policy>
          <type>
            <inspect>SP-FWAAS-NO-CRAP-ON-TAP</inspect>
          </type>
        </service-policy>
      </security>
    </zone-pair>
</native>
</data>
</rpc-reply>
"""

        zone_pair = ZonePair.from_xml(xml, context)
        self.assertEqual("ZP-FWAAS-EXT-INGRESS-123", zone_pair.id)
        self.assertEqual("ZN-FWAAS-123", zone_pair.source)
        self.assertEqual("default", zone_pair.destination)
        self.assertEqual("SP-FWAAS-NO-CRAP-ON-TAP", zone_pair.service_policy)

    def test_parse_prefix_list_format(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <ip>
        <prefix-lists>
          <prefixes>
            <name>seagull-yang-test</name>
            <no>10</no>
            <action>permit</action>
            <ip>1.1.1.0/24</ip>
            <le>32</le>
          </prefixes>
          <prefixes>
            <name>seagull-yang-test</name>
            <no>20</no>
            <action>permit</action>
            <ip>2.2.2.2/32</ip>
          </prefixes>
          <prefixes>
            <name>seagull-yang-test</name>
            <no>30</no>
            <action>permit</action>
            <ip>3.3.3.0/24</ip>
            <ge>28</ge>
          </prefixes>
        </prefix-lists>
      </ip>
    </native>
  </data>
</rpc-reply>

"""
        context = FakeASR1KContext()
        pfx = Prefix.from_xml(xml, context)
        self.assertEqual("seagull-yang-test", pfx.name)

        seqs = [(s.no, s.action, s.ip, s.le, s.ge) for s in pfx.seq]
        expected_seqs = [
            ('10', 'permit', '1.1.1.0/24', '32', None),
            ('20', 'permit', '2.2.2.2/32', None, None),
            ('30', 'permit', '3.3.3.0/24', None, '28'),
        ]
        self.assertEqual(expected_seqs, seqs)

    def test_parse_prefix_list_format_single(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <ip>
        <prefix-lists>
          <prefixes>
            <name>seagull-yang-test</name>
            <no>10</no>
            <action>permit</action>
            <ip>1.1.1.0/24</ip>
            <le>32</le>
          </prefixes>
        </prefix-lists>
      </ip>
    </native>
  </data>
</rpc-reply>

"""
        context = FakeASR1KContext()
        pfx = Prefix.from_xml(xml, context)
        self.assertEqual("seagull-yang-test", pfx.name)

        seqs = [(s.no, s.action, s.ip) for s in pfx.seq]
        seqs = [(s.no, s.action, s.ip, s.le, s.ge) for s in pfx.seq]
        expected_seqs = [
            ('10', 'permit', '1.1.1.0/24', '32', None),
        ]
        self.assertEqual(expected_seqs, seqs)

    def test_parse_interface_dynamic_nat(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"
           message-id="urn:uuid:614fba98-6ee3-4551-a529-c96f09989cc9">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <ip>
        <nat xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
          <inside>
            <source>
              <list-interface>
                <list>
                  <id>NAT-025723acabdd4dcfa2e72b6644a86b45</id>
                  <interface>
                    <name>BD-VIF5692</name>
                    <vrf-new>
                      <name>025723acabdd4dcfa2e72b6644a86b45</name>
                      <overload-new/>
                    </vrf-new>
                  </interface>
                </list>
              </list-interface>
            </source>
          </inside>
        </nat>
      </ip>
    </native>
  </data>
</rpc-reply>
"""
        context = FakeASR1KContext()
        idn = InterfaceDynamicNat.from_xml(xml, context)
        self.assertEqual("NAT-025723acabdd4dcfa2e72b6644a86b45", idn.id)
        self.assertEqual("BD-VIF5692", idn.interface)
        self.assertEqual("025723acabdd4dcfa2e72b6644a86b45", idn.vrf)
        self.assertTrue(idn.overload)

    def test_parse_pool_dynamic_nat(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"
           message-id="urn:uuid:2f906e1b-14bf-454d-9743-ede37968be06">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <ip>
        <nat xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-nat">
          <inside>
            <source>
              <list-pool>
                <list>
                  <id>NAT-2677a86be25a41c4b26d9c23576c7d13</id>
                  <pool>
                    <name>POOL-2677a86be25a41c4b26d9c23576c7d13</name>
                    <redundancy-new>
                      <name>1</name>
                      <mapping-id-new>
                        <name>267786254</name>
                        <vrf-new>
                          <name>2677a86be25a41c4b26d9c23576c7d13</name>
                          <overload-new/>
                        </vrf-new>
                      </mapping-id-new>
                    </redundancy-new>
                  </pool>
                </list>
              </list-pool>
            </source>
          </inside>
        </nat>
      </ip>
    </native>
  </data>
</rpc-reply>
"""
        context = FakeASR1KContext()
        pdn = PoolDynamicNat.from_xml(xml, context)
        self.assertEqual("NAT-2677a86be25a41c4b26d9c23576c7d13", pdn.id)
        self.assertEqual("POOL-2677a86be25a41c4b26d9c23576c7d13", pdn.pool)
        self.assertEqual("2677a86be25a41c4b26d9c23576c7d13", pdn.vrf)
        self.assertEqual('267786254', pdn.mapping_id)
        self.assertEqual('1', pdn.redundancy)
        self.assertTrue(pdn.overload)
