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
from asr1k_neutron_l3.models.netconf_yang import crypto


class CryptoSerialization(base.BaseTestCase):
    def test_ipsec_profile_parsing(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <crypto>
        <ipsec xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-crypto">
          <profile>
            <name>meowmeow</name>
            <reverse-route/>
            <set>
              <ikev2-profile>my-very-first-profile</ikev2-profile>
              <pfs>
                <group>group21</group>
              </pfs>
              <transform-set>AES256_SHA512_Tunnel</transform-set>
              <security-association>
                <lifetime>
                  <seconds-case>1338</seconds-case>
                  <kilobytes>disable</kilobytes>
                  <seconds>1337</seconds>
                </lifetime>
              </security-association>
            </set>
          </profile>
        </ipsec>
      </crypto>
    </native>
  </data>
</rpc-reply>
"""

        context = FakeASR1KContext()
        prof = crypto.IPSecProfile.from_xml(xml, context)
        self.assertEqual("meowmeow", prof.name)
        self.assertTrue(prof.reverse_route)
        self.assertEqual("AES256_SHA512_Tunnel", prof.transform_set)
        self.assertEqual("my-very-first-profile", prof.ikev2_profile)
        self.assertEqual("group21", prof.pfs)
        self.assertEqual("1337", prof.sa_lifetime_sec)
        self.assertEqual("1338", prof.sa_lifetime_sec_case)
        self.assertEqual("disable", prof.sa_lifetime_kb)
        self.assertEqual("group21", prof.pfs)

        self.assertEqual("meowmeow", prof.to_dict(context)["profile"]["name"])

    def test_ipsec_profile_serialization(self):
        context = FakeASR1KContext()
        prof = crypto.IPSecProfile(name="no-crypto-just-meowmeow", reverse_route=True,
                                   transform_set="from-here-to-there", ikev2_profile="itsa-meeee",
                                   pfs="group9999", sa_lifetime_sec=1337,
                                   sa_lifetime_sec_case=1338,
                                   sa_lifetime_kb="disable",)
        self.assertEqual({
                'name': 'no-crypto-just-meowmeow',
                'reverse-route': '',
                'set': {
                    'ikev2-profile': 'itsa-meeee',
                    'pfs': {'group': 'group9999'},
                    'security-association': {
                        'lifetime': {
                            'kilobytes': 'disable',
                            'seconds': '1337',
                            'seconds-case': '1338'}
                    },
                    'transform-set': 'from-here-to-there'
                }
            },
            prof.to_dict(context)["profile"])

    def test_ipsec_transform_set_parsing(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <crypto>
        <ipsec xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-crypto">
          <transform-set>
            <tag>AES256_SHA512_Tunnel</tag>
            <esp>esp-aes</esp>
            <key-bit>256</key-bit>
            <esp-hmac>esp-sha512-hmac</esp-hmac>
            <mode>
              <tunnel-choice/>
              <tunnel/>
            </mode>
          </transform-set>
        </ipsec>
      </crypto>
    </native>
  </data>
</rpc-reply>
"""

        context = FakeASR1KContext()
        ts = crypto.IPSecTransformSet.from_xml(xml, context)

        self.assertEqual("AES256_SHA512_Tunnel", ts.tag)
        self.assertEqual("esp-aes", ts.esp)
        self.assertEqual("256", ts.key_bit)
        self.assertEqual("esp-sha512-hmac", ts.esp_hmac)
        self.assertTrue(ts.tunnel_choice)

    def test_ipsec_transform_set_serialization(self):
        context = FakeASR1KContext()
        ts = crypto.IPSecTransformSet(tag="special-transform-set", esp="esp-aes", key_bit=256, esp_hmac="esp-foo",
                                      transport_choice=True)
        self.assertEqual({
                'esp': 'esp-aes',
                'esp-hmac': 'esp-foo',
                'key-bit': '256',
                'mode': {'transport-choice': ''},
                'tag': 'special-transform-set'
            },
            ts.to_dict(context)["transform-set"])

    def test_ikev2_profile_parsing_single_identity(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <crypto>
        <ikev2 xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-crypto">
          <profile>
            <name>oystercatcher</name>
            <authentication>
              <local>
                <pre-share/>
              </local>
              <remote>
                <pre-share/>
              </remote>
            </authentication>
            <dpd>
              <interval>10</interval>
              <retry>3</retry>
              <query>on-demand</query>
            </dpd>
            <keyring>
              <local>
                <name>secret-stash</name>
              </local>
            </keyring>
            <lifetime>
              <seconds>4242</seconds>
            </lifetime>
            <match>
              <fvrf>
                <name>mediterranean-gull</name>
              </fvrf>
              <identity>
                <remote>
                  <address>
                    <ipv4>
                      <ipv4-address>23.23.23.23</ipv4-address>
                      <ipv4-mask>255.255.255.255</ipv4-mask>
                    </ipv4>
                  </address>
                </remote>
              </identity>
            </match>
          </profile>
        </ikev2>
      </crypto>
    </native>
  </data>
</rpc-reply>

"""

        context = FakeASR1KContext()
        prof = crypto.IKEv2Profile.from_xml(xml, context)
        self.assertEqual("oystercatcher", prof.name)
        self.assertTrue(prof.auth_local_pre_share)
        self.assertTrue(prof.auth_remote_pre_share)
        self.assertEqual("10", prof.dpd_interval)
        self.assertEqual("3", prof.dpd_retry)
        self.assertEqual("on-demand", prof.dpd_query)
        self.assertEqual("secret-stash", prof.keyring_local)
        self.assertEqual("4242", prof.lifetime_sec)
        self.assertEqual("mediterranean-gull", prof.fvrf)
        self.assertEqual(1, len(prof.remote_identities_v4))
        self.assertEqual("23.23.23.23", prof.remote_identities_v4[0].address)
        self.assertEqual("255.255.255.255", prof.remote_identities_v4[0].mask)

    def test_ikev2_profile_parsing_multiple_identities(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <crypto>
        <ikev2 xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-crypto">
          <profile>
            <name>oystercatcher</name>
            <authentication>
              <local>
                <pre-share/>
              </local>
              <remote>
                <pre-share/>
              </remote>
            </authentication>
            <dpd>
              <interval>10</interval>
              <retry>3</retry>
              <query>on-demand</query>
            </dpd>
            <keyring>
              <local>
                <name>secret-stash</name>
              </local>
            </keyring>
            <lifetime>
              <seconds>4242</seconds>
            </lifetime>
            <match>
              <fvrf>
                <name>mediterranean-gull</name>
              </fvrf>
              <identity>
                <remote>
                  <address>
                    <ipv4>
                      <ipv4-address>23.23.23.23</ipv4-address>
                      <ipv4-mask>255.255.255.255</ipv4-mask>
                    </ipv4>
                    <ipv4>
                      <ipv4-address>42.42.42.0</ipv4-address>
                      <ipv4-mask>255.255.255.0</ipv4-mask>
                    </ipv4>
                  </address>
                </remote>
              </identity>
            </match>
          </profile>
        </ikev2>
      </crypto>
    </native>
  </data>
</rpc-reply>

"""

        context = FakeASR1KContext()
        prof = crypto.IKEv2Profile.from_xml(xml, context)
        self.assertEqual("oystercatcher", prof.name)
        self.assertTrue(prof.auth_local_pre_share)
        self.assertTrue(prof.auth_remote_pre_share)
        self.assertEqual("10", prof.dpd_interval)
        self.assertEqual("3", prof.dpd_retry)
        self.assertEqual("on-demand", prof.dpd_query)
        self.assertEqual("secret-stash", prof.keyring_local)
        self.assertEqual("4242", prof.lifetime_sec)
        self.assertEqual("mediterranean-gull", prof.fvrf)
        self.assertEqual(2, len(prof.remote_identities_v4))
        self.assertEqual("23.23.23.23", prof.remote_identities_v4[0].address)
        self.assertEqual("255.255.255.255", prof.remote_identities_v4[0].mask)
        self.assertEqual("42.42.42.0", prof.remote_identities_v4[1].address)
        self.assertEqual("255.255.255.0", prof.remote_identities_v4[1].mask)

    def test_ikev2_profile_serialization(self):
        prof = crypto.IKEv2Profile(
            name="oystercatcher", auth_local_pre_share=True, auth_remote_pre_share=True,
            dpd_interval=20, dpd_retry=20, dpd_query="whatever", keyring_local="secret-stash", lifetime_sec=9999,
            fvrf="mediterranean-gull",
            remote_identities_v4=[crypto.IKEv2ProfileIdentityV4(address="23.23.23.23", mask="255.255.255.255")])

        context = FakeASR1KContext()
        self.assertEqual(
            {
                'name': 'oystercatcher',
                'authentication': {
                    'local': {'pre-share': ''},
                    'remote': {'pre-share': ''}},
                'dpd': {'interval': '20', 'retry': '20', 'query': 'whatever'},
                'keyring': {'local': {'name': 'secret-stash'}},
                'lifetime': {'seconds': '9999'},
                'match': {
                    'fvrf': {'name': 'mediterranean-gull'},
                    'identity': {'remote': {'address': {'ipv4': [{
                        'ipv4-address': '23.23.23.23',
                        'ipv4-mask': '255.255.255.255'
                    }]}}}
                }
            },
            prof.to_dict(context)["profile"])

    def test_ikev2_keyring_parsing(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <crypto>
        <ikev2 xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-crypto">
          <keyring>
            <name>secret-stash</name>
            <peer>
              <name>SANCTUARY</name>
              <address>
                <ipv4>
                  <ipv4-address>42.42.42.42</ipv4-address>
                </ipv4>
              </address>
              <identity>
                <address-type>1.3.93.77</address-type>
              </identity>
              <pre-shared-key>
                <key>ug-thak</key>
              </pre-shared-key>
            </peer>
          </keyring>
        </ikev2>
      </crypto>
    </native>
  </data>
</rpc-reply>

"""

        context = FakeASR1KContext()
        kr = crypto.IKEv2Keyring.from_xml(xml, context)
        self.assertEqual("secret-stash", kr.name)
        self.assertEqual(1, len(kr.peers))

        peer = kr.peers[0]
        self.assertEqual("SANCTUARY", peer.name)
        self.assertEqual("ug-thak", peer.psk)
        self.assertEqual("42.42.42.42", peer.ipv4_address)
        self.assertEqual("1.3.93.77", peer.identity)

    def test_ikev2_keyring_parsing_multi_peers(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <crypto>
        <ikev2 xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-crypto">
          <keyring>
            <name>secret-stash</name>
            <peer>
              <name>SANCTUARY</name>
              <pre-shared-key>
                <key>ug-thak</key>
              </pre-shared-key>
            </peer>
            <peer>
              <name>NEWHAVEN</name>
              <pre-shared-key>
                <key>dance-dance</key>
              </pre-shared-key>
            </peer>
          </keyring>
        </ikev2>
      </crypto>
    </native>
  </data>
</rpc-reply>

"""

        context = FakeASR1KContext()
        kr = crypto.IKEv2Keyring.from_xml(xml, context)
        self.assertEqual("secret-stash", kr.name)
        self.assertEqual(2, len(kr.peers))

        self.assertEqual("SANCTUARY", kr.peers[0].name)
        self.assertEqual("NEWHAVEN", kr.peers[1].name)

    def test_ikev2_policy_parsing(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <crypto>
        <ikev2 xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-crypto">
          <policy>
            <name>proposal-gull</name>
            <match>
              <fvrf>
                <name>secret-stash</name>
              </fvrf>
            </match>
            <proposal>
              <proposals>aes-gcm-256-sha512-group20</proposals>
            </proposal>
          </policy>
        </ikev2>
      </crypto>
    </native>
  </data>
</rpc-reply>
"""

        context = FakeASR1KContext()
        pol = crypto.IKEv2Policy.from_xml(xml, context)
        self.assertEqual(pol.name, "proposal-gull")
        self.assertEqual(pol.fvrf, "secret-stash")
        self.assertEqual(pol.proposals, ["aes-gcm-256-sha512-group20"])

    def test_ikev2_policy_parsing_multiple_proposals(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <crypto>
        <ikev2 xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-crypto">
          <policy>
            <name>proposal-gull</name>
            <match>
              <fvrf>
                <name>secret-stash</name>
              </fvrf>
            </match>
            <proposal>
              <proposals>aes-gcm-256-sha512-group20</proposals>
            </proposal>
            <proposal>
              <proposals>aes-seagull</proposals>
            </proposal>
          </policy>
        </ikev2>
      </crypto>
    </native>
  </data>
</rpc-reply>
"""

        context = FakeASR1KContext()
        pol = crypto.IKEv2Policy.from_xml(xml, context)
        self.assertEqual(pol.name, "proposal-gull")
        self.assertEqual(pol.fvrf, "secret-stash")
        self.assertEqual(pol.proposals, ["aes-gcm-256-sha512-group20", "aes-seagull"])

    def test_ikev2_policy_serialization(self):
        pol = crypto.IKEv2Policy(name="porposal-gull", fvrf="secret-stash",
                                 proposals=["aes-gcm-256-sha512-group20", "aes-seagull"])

        context = FakeASR1KContext()
        self.assertEqual(pol.to_dict(context)["policy"],
                         {"name": "porposal-gull", "match": {"fvrf": {"name": "secret-stash"}},
                          "proposal": [{"proposals": "aes-gcm-256-sha512-group20"}, {"proposals": "aes-seagull"}]})

    def test_ikev2_proposal_parsing(self):
        xml = """
<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
      <crypto>
        <ikev2 xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-crypto">
          <proposal>
            <name>eurasian-starling</name>
            <encryption>
              <aes-cbc-256/>
            </encryption>
            <group>
              <nineteen/>
              <twenty-one/>
            </group>
            <integrity>
              <sha256/>
            </integrity>
          </proposal>
        </ikev2>
      </crypto>
    </native>
  </data>
</rpc-reply>

"""

        context = FakeASR1KContext()
        prop = crypto.IKEv2Proposal.from_xml(xml, context)
        self.assertEqual(prop.name, "eurasian-starling")

        self.assertTrue(prop.nineteen)
        self.assertTrue(prop.twenty_one)
        self.assertFalse(prop.fourteen)
        self.assertFalse(prop.fifteen)
        self.assertFalse(prop.sixteen)
        self.assertFalse(prop.twenty)

        self.assertTrue(prop.aes_cbc_256)
        self.assertFalse(prop.aes_cbc_128)
        self.assertFalse(prop.aes_cbc_192)
        self.assertFalse(prop.aes_gcm_128)
        self.assertFalse(prop.aes_gcm_256)

        self.assertTrue(prop.sha256)
        self.assertFalse(prop.sha384)
        self.assertFalse(prop.sha512)
        self.assertEqual({"name": "eurasian-starling",
                          "encryption": {"aes-cbc-256": ""},
                          "group": {"nineteen": "", "twenty-one": ""},
                          "integrity": {"sha256": ""}},
                         prop.to_dict(context)["proposal"])

    def test_ikev2_proposal_serialization(self):
        context = FakeASR1KContext()
        prop = crypto.IKEv2Proposal(name="eurasian-starling", nineteen=True, twenty_one=True,
                                    aes_cbc_256=True, sha256=True)
        self.assertEqual({"name": "eurasian-starling",
                          "encryption": {"aes-cbc-256": ""},
                          "group": {"nineteen": "", "twenty-one": ""},
                          "integrity": {"sha256": ""}},
                         prop.to_dict(context)["proposal"])
