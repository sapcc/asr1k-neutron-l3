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

from neutron.tests import base

from asr1k_neutron_l3.models.asr1k_pair import FakeASR1KContext
from asr1k_neutron_l3.models.netconf_yang import bgp


class BGPSerialization(base.BaseTestCase):
    def test_ipsec_profile_parsing(self):
        xml = """
<rpc-reply>
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <router>
        <bgp xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-bgp">
          <id>65151</id>
          <address-family>
            <with-vrf>
              <ipv4>
                <af-name>unicast</af-name>
                <vrf>
                  <name>i501315-test</name>
                  <ipv4-unicast>
                    <neighbor>
                      <id>1.2.3.4</id>
                      <remote-as>4200000001</remote-as>
                      <activate/>
                      <local-as>
                        <as-no>4200000000</as-no>
                      </local-as>
                      <maximum-prefix>
                        <max-prefix-no>5000</max-prefix-no>
                        <threshold>80</threshold>
                        <restart>1</restart>
                      </maximum-prefix>
                      <password>
                        <enctype>7</enctype>
                        <text>082C49411E140018055A5E57</text>
                      </password>
                      <route-map>
                        <inout>in</inout>
                        <route-map-name>meowinvalidtest1</route-map-name>
                      </route-map>
                      <route-map>
                        <inout>out</inout>
                        <route-map-name>meowinvalidtest2</route-map-name>
                      </route-map>
                      <soft-reconfiguration>inbound</soft-reconfiguration>
                    </neighbor>
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

        context = FakeASR1KContext()
        bgpaf = bgp.AddressFamilyV4.from_xml(xml, context)
        print(bgpaf)
        print(bgpaf.to_xml(context))
        breakpoint()
