# Copyright 2025 SAP SE
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
from asr1k_neutron_l3.models.netconf_yang import l3_interface


class TestL3Interface(base.BaseTestCase):
    def test_tunnel_iface_parsing(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <interface>
        <Tunnel>
          <name>2147483647</name>
          <description>meep meep</description>
          <keepalive-config>
            <keepalive>true</keepalive>
            <period>23</period>
            <retries>42</retries>
          </keepalive-config>
          <vrf>
            <forwarding>mediterranean-gull</forwarding>
          </vrf>
          <ip>
            <address>
              <primary>
                <address>169.254.169.254</address>
                <mask>255.255.255.252</mask>
              </primary>
            </address>
            <tcp>
              <adjust-mss>1460</adjust-mss>
            </tcp>
            <mtu>8950</mtu>
          </ip>
          <ipv6>
            <address>
              <prefix-list>
                <prefix>FD86:CB3C:C988:28C:C2B:597A:B88C:AC85/126</prefix>
              </prefix-list>
            </address>
          </ipv6>
          <tunnel xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-tunnel">
            <source>4.5.6.7</source>
            <destination-config>
              <ipv4>3.141.59.26</ipv4>
            </destination-config>
            <mode>
              <ipsec>
                <ipv4-mode/>
              </ipsec>
            </mode>
            <path-mtu-discovery/>
            <protection>
              <ipsec xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-crypto">
                <policy>
                  <ipv4>better-safe-than-sorry</ipv4>
                </policy>
                <profile-option>
                  <name>0249769d514849c1adc7001f122e1d8</name>
                </profile-option>
              </ipsec>
            </protection>
            <vrf-config>
              <vrf-common>
                <vrf>mediterranean-gull</vrf>
              </vrf-common>
            </vrf-config>
          </tunnel>
        </Tunnel>
      </interface>
    </native>
  </data>
</rpc-reply>
"""

        context = FakeASR1KContext()
        iface = l3_interface.TunnelInterface.from_xml(xml, context)
        self.assertEqual("2147483647", iface.name)
        self.assertEqual("meep meep", iface.description)
        self.assertEqual("true", iface.keepalive)
        self.assertEqual("23", iface.keepalive_period)
        self.assertEqual("42", iface.keepalive_retries)
        self.assertEqual("mediterranean-gull", iface.vrf)
        self.assertEqual("1460", iface.tcp_mss)
        self.assertEqual("8950", iface.mtu)
        self.assertEqual("169.254.169.254", iface.ipv4_address)
        self.assertEqual("255.255.255.252", iface.ipv4_netmask)
        self.assertEqual(1, len(iface.ipv6_addresses))
        self.assertEqual("fd86:cb3c:c988:28c:c2b:597a:b88c:ac85/126", iface.ipv6_addresses[0].prefix.lower())
        self.assertEqual("fd86:cb3c:c988:28c:c2b:597a:b88c:ac85/126",
                         iface.to_dict(context)['Tunnel']['ipv6']['address']['prefix-list'][0]['prefix'])
        self.assertEqual("4.5.6.7", iface.tunnel_src)
        self.assertEqual("3.141.59.26", iface.tunnel_dest_ipv4)
        self.assertTrue(iface.tunnel_mode_ipsec_ipv4)
        self.assertTrue(iface.path_mtu_discovery)
        self.assertEqual("better-safe-than-sorry", iface.ipsec_policy_ipv4)
        self.assertEqual("0249769d514849c1adc7001f122e1d8", iface.ipsec_profile)
        self.assertEqual("mediterranean-gull", iface.tunnel_vrf)

    def test_tunnel_iface_serialization(self):
        context = FakeASR1KContext()
        iface = l3_interface.TunnelInterface(
            name=2342, description="meep meep", keepalive="true", keepalive_period=23, keepalive_retries=42,
            vrf="mediterranean-gull", tcp_mss=1420, mtu=5678,
            ipv4_address="13.37.73.31", ipv4_netmask="255.255.255.252",
            tunnel_src="1.1.1.1", tunnel_dest_ipv4="1.1.1.2", tunnel_mode_ipsec_ipv4=True, path_mtu_discovery=True,
            ipsec_policy_ipv4="foo", ipsec_profile="bar", tunnel_vrf="mediterranean-gull"
        )
        self.assertEqual({
            'name': '2342',
            'description': 'meep meep',
            'shutdown': {'@operation': 'remove'},
            'ip': {
                'address': {
                    'primary': {
                        'address': '13.37.73.31',
                        'mask': '255.255.255.252',
                    }
                },
                'tcp': {'adjust-mss': '1420'},
                'mtu': '5678',
            },
            'vrf': {'forwarding': 'mediterranean-gull'},
            'keepalive-config': {'keepalive': 'true', 'period': '23', 'retries': '42'},
            'tunnel': {
                '@xmlns': 'http://cisco.com/ns/yang/Cisco-IOS-XE-tunnel',
                'source': '1.1.1.1',
                'destination-config': {'ipv4': '1.1.1.2'},
                'mode': {'ipsec': {'ipv4-mode': ''}},
                'path-mtu-discovery': '',
                'protection': {'ipsec': {
                    '@xmlns': 'http://cisco.com/ns/yang/Cisco-IOS-XE-crypto',
                    'policy': {'ipv4': 'foo'},
                    'profile-option': {'name': 'bar'}
                }},
                'vrf-config': {'vrf-common': {'vrf': 'mediterranean-gull'}}}

            },
            iface.to_dict(context)["Tunnel"])
