# Copyright 2025 SAP SE
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

from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, YANG_TYPE
from asr1k_neutron_l3.models.netconf_yang import xml_utils


class CryptoConstants(object):
    CRYPTO = "crypto"
    IPSEC = "ipsec"
    IKEV2 = "ikev2"
    PROFILE = "profile"
    POLICY = "policy"
    PROPOSAL = "proposal"
    PROPOSALS = "proposals"
    NAME = "name"
    ENCRYPTION = "encryption"
    GROUP = "group"
    INTEGRITY = "integrity"
    PRF = "prf"

    KEYRING = "keyring"
    PEER = "peer"
    ADDRESS = "address"
    IPV4 = "ipv4"
    IPV4_ADDRESS = "ipv4-address"
    IPV4_MASK = "ipv4-mask"
    IDENTITY = "identity"
    ADDRESS_TYPE = "address-type"
    PRE_SHARED_KEY = "pre-shared-key"
    KEY = "key"

    SET = "set"
    IKEV2_PROFILE = "ikev2-profile"
    TRANSFORM_SET = "transform-set"
    PFS = "pfs"
    SECURITY_ASSOCIATION = "security-association"
    LIFETIME = "lifetime"
    SECONDS = "seconds"
    SECONDS_CASE = "seconds-case"
    KILOBYTES = "kilobytes"
    REVERSE_ROUTE = "reverse-route"

    TAG = "tag"
    ESP = "esp"
    KEY_BIT = "key-bit"
    ESP_HMAC = "esp-hmac"
    MODE = "mode"
    TUNNEL_CHOICE = "tunnel-choice"
    TUNNEL = "tunnel"
    TRANSPORT_CHOICE = "transport-choice"
    TRANSPORT = "transport"

    FVRF = "fvrf"
    AUTHENTICATION = "authentication"
    LOCAL = "local"
    REMOTE = "remote"
    PRE_SHARE = "pre-share"
    DPD = "dpd"
    INTERVAL = "interval"
    RETRY = "retry"
    QUERY = "query"
    MATCH = "match"


class IPSecProfile(NyBase):
    ITEM_PATH = [CryptoConstants.CRYPTO]
    LIST_KEY = CryptoConstants.IPSEC
    LIST_KEY_NS = xml_utils.NS_CISCO_CRYPTO
    ITEM_KEY = CryptoConstants.PROFILE

    ID_FILTER = """
        <native>
            <crypto>
                <ipsec>
                    <profile>
                        <name>{id}</name>
                    </profile>
                </ipsec>
            </crypto>
        </native>
        """

    GET_ALL_STUB = """
        <native>
            <crypto>
                <ipsec>
                    <profile>
                        <name/>
                    </profile>
                </ipsec>
            </crypto>
        </native>
        """

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'name', 'id': True},

            {'key': 'ikev2_profile', 'yang-path': 'set'},
            {'key': 'transform_set', 'yang-path': 'set'},
            {'key': 'pfs', 'yang-key': 'group', 'yang-path': 'set/pfs'},

            {'key': 'sa_lifetime_sec', 'yang-key': 'seconds', 'yang-path': 'set/security-association/lifetime'},
            {'key': 'sa_lifetime_sec_case', 'yang-key': 'seconds-case',
             'yang-path': 'set/security-association/lifetime'},
            {'key': 'sa_lifetime_kb', 'yang-key': 'kilobytes', 'yang-path': 'set/security-association/lifetime'},

            {'key': 'reverse_route', 'yang-type': YANG_TYPE.EMPTY, 'default': False},
        ]

    def to_dict(self, context):
        profile = {
            CryptoConstants.NAME: self.name,
            CryptoConstants.SET: {},
        }

        p_set = profile[CryptoConstants.SET]
        if self.ikev2_profile:
            p_set[CryptoConstants.IKEV2_PROFILE] = self.ikev2_profile
        if self.transform_set:
            p_set[CryptoConstants.TRANSFORM_SET] = self.transform_set
        if self.pfs:
            p_set[CryptoConstants.PFS] = {CryptoConstants.GROUP: self.pfs}

        if self.sa_lifetime_sec or self.sa_lifetime_sec_case or self.sa_lifetime_kb:
            p_set[CryptoConstants.SECURITY_ASSOCIATION] = {
                CryptoConstants.LIFETIME: {
                    CryptoConstants.SECONDS_CASE: self.sa_lifetime_sec_case,
                    CryptoConstants.KILOBYTES: self.sa_lifetime_kb,
                    CryptoConstants.SECONDS: self.sa_lifetime_sec,
                }
            }

        if self.reverse_route:
            profile[CryptoConstants.REVERSE_ROUTE] = ""

        return {CryptoConstants.PROFILE: profile}

    def is_orphan_vpnaas(self, all_ipsec_siteconnection_ids, all_tunnel_ids):
        # 31 is the max length of an IPSecProfile on cisco and we truncate our router ids to it
        if not self.name or len(self.name) != 31:
            return False

        return not any(utils.uuid_to_ipsec_short_id(sitecon_id) == self.name
                       for sitecon_id in all_ipsec_siteconnection_ids)


class IPSecTransformSet(NyBase):
    ITEM_PATH = [CryptoConstants.CRYPTO]
    LIST_KEY = CryptoConstants.IPSEC
    LIST_KEY_NS = xml_utils.NS_CISCO_CRYPTO
    ITEM_KEY = CryptoConstants.TRANSFORM_SET

    ID_FILTER = """
        <native>
            <crypto>
                <ipsec>
                    <transform-set>
                        <tag>{id}</tag>
                    </transform-set>
                </ipsec>
            </crypto>
        </native>
        """

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'tag', 'id': True},

            {'key': 'esp'},
            {'key': 'key_bit'},
            {'key': 'esp_hmac'},
            {'key': 'tunnel_choice', 'yang-path': 'mode', 'yang-type': YANG_TYPE.EMPTY},
            {'key': 'transport_choice', 'yang-path': 'mode', 'yang-type': YANG_TYPE.EMPTY},
        ]

    def to_dict(self, context):
        ts = {
            CryptoConstants.TAG: self.tag,
        }

        if self.esp:
            ts[CryptoConstants.ESP] = self.esp
        if self.key_bit:
            ts[CryptoConstants.KEY_BIT] = self.key_bit
        if self.esp_hmac:
            ts[CryptoConstants.ESP_HMAC] = self.esp_hmac
        if self.tunnel_choice:
            ts.setdefault(CryptoConstants.MODE, {})[CryptoConstants.TUNNEL_CHOICE] = ""
        if self.transport_choice:
            ts.setdefault(CryptoConstants.MODE, {})[CryptoConstants.TRANSPORT_CHOICE] = ""

        return {CryptoConstants.TRANSFORM_SET: ts}


class IKEv2Profile(NyBase):
    ITEM_PATH = [CryptoConstants.CRYPTO]
    LIST_KEY = CryptoConstants.IKEV2
    LIST_KEY_NS = xml_utils.NS_CISCO_CRYPTO
    ITEM_KEY = CryptoConstants.PROFILE

    ID_FILTER = """
        <native>
            <crypto>
                <ikev2>
                    <profile>
                        <name>{id}</name>
                    </profile>
                </ikev2>
            </crypto>
        </native>
        """

    GET_ALL_STUB = """
        <native>
            <crypto>
                <ikev2>
                    <profile>
                        <name/>
                    </profile>
                </ikev2>
            </crypto>
        </native>
        """

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'name', 'id': True},

            {'key': 'auth_local_pre_share', 'yang-key': 'pre-share', 'yang-path': 'authentication/local',
             'yang-type': YANG_TYPE.EMPTY},
            {'key': 'auth_remote_pre_share', 'yang-key': 'pre-share', 'yang-path': 'authentication/remote',
             'yang-type': YANG_TYPE.EMPTY},

            {'key': 'dpd_interval', 'yang-key': 'interval', 'yang-path': 'dpd'},
            {'key': 'dpd_retry', 'yang-key': 'retry', 'yang-path': 'dpd'},
            {'key': 'dpd_query', 'yang-key': 'query', 'yang-path': 'dpd'},
            {'key': 'keyring_local', 'yang-key': 'name', 'yang-path': 'keyring/local'},
            {'key': 'lifetime_sec', 'yang-key': 'seconds', 'yang-path': 'lifetime'},

            # TODO(seba): ipv6 identity
            {'key': 'fvrf', 'yang-key': 'name', 'yang-path': 'match/fvrf'},
            {'key': 'remote_identities_v4', 'yang-key': 'ipv4', 'yang-path': 'match/identity/remote/address',
             'type': [IKEv2ProfileIdentityV4]},
        ]

    def to_dict(self, context):
        profile = {
            CryptoConstants.NAME: self.name,
        }

        auth = {}
        if self.auth_local_pre_share:
            auth[CryptoConstants.LOCAL] = {CryptoConstants.PRE_SHARE: ""}
        if self.auth_remote_pre_share:
            auth[CryptoConstants.REMOTE] = {CryptoConstants.PRE_SHARE: ""}
        if auth:
            profile[CryptoConstants.AUTHENTICATION] = auth

        dpd = {}
        if self.dpd_interval:
            dpd[CryptoConstants.INTERVAL] = self.dpd_interval
        if self.dpd_retry:
            dpd[CryptoConstants.RETRY] = self.dpd_retry
        if self.dpd_query:
            dpd[CryptoConstants.QUERY] = self.dpd_query
        if dpd:
             profile[CryptoConstants.DPD] = dpd

        if self.keyring_local:
            profile[CryptoConstants.KEYRING] = {
                CryptoConstants.LOCAL: {
                    CryptoConstants.NAME: self.keyring_local,
                },
            }

        if self.lifetime_sec:
            profile[CryptoConstants.LIFETIME] = {
                CryptoConstants.SECONDS: self.lifetime_sec,
            }

        pmatch = {}
        if self.fvrf:
            pmatch[CryptoConstants.FVRF] = {CryptoConstants.NAME: self.fvrf}
        if self.remote_identities_v4:
            pmatch[CryptoConstants.IDENTITY] = {
                CryptoConstants.REMOTE: {
                    CryptoConstants.ADDRESS: {
                        CryptoConstants.IPV4: [ri.to_dict(context) for ri in self.remote_identities_v4],
                    }
                }
            }
        if pmatch:
            profile[CryptoConstants.MATCH] = pmatch

        return {CryptoConstants.PROFILE: profile}

    def is_orphan_vpnaas(self, all_ipsec_siteconnection_ids, all_tunnel_ids):
        if self.name:
            sitecon_id = utils.vrf_id_to_uuid(self.name)
            return sitecon_id and sitecon_id not in all_ipsec_siteconnection_ids
        return False


class IKEv2ProfileIdentityV4(NyBase):
    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'address', 'yang-key': 'ipv4-address'},
            {'key': 'mask', 'yang-key': 'ipv4-mask'},
        ]

    def to_dict(self, context):
        return {
            CryptoConstants.IPV4_ADDRESS: self.address,
            CryptoConstants.IPV4_MASK: self.mask,
        }


class IKEv2Keyring(NyBase):
    ITEM_PATH = [CryptoConstants.CRYPTO]
    LIST_KEY = CryptoConstants.IKEV2
    LIST_KEY_NS = xml_utils.NS_CISCO_CRYPTO
    ITEM_KEY = CryptoConstants.KEYRING

    ID_FILTER = """
        <native>
            <crypto>
                <ikev2>
                    <keyring>
                        <name>{id}</name>
                    </keyring>
                </ikev2>
            </crypto>
        </native>
        """

    GET_ALL_STUB = """
        <native>
            <crypto>
                <ikev2>
                    <keyring>
                        <name/>
                    </keyring>
                </ikev2>
            </crypto>
        </native>
    """

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'name', 'id': True},
            {'key': 'peers', 'yang-key': 'peer', 'type': [IKEv2KeyringPeer]},
        ]

    def to_dict(self, context):
        keyring = {
            CryptoConstants.NAME: self.name,
        }
        keyring[CryptoConstants.PEER] = [peer.to_dict(context) for peer in self.peers]

        return {CryptoConstants.KEYRING: keyring}

    def is_orphan_vpnaas(self, all_ipsec_siteconnection_ids, all_tunnel_ids):
        if self.name:
            sitecon_id = utils.vrf_id_to_uuid(self.name)
            return sitecon_id and sitecon_id not in all_ipsec_siteconnection_ids
        return False


class IKEv2KeyringPeer(NyBase):
    ITEM_KEY = CryptoConstants.PEER

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'name', 'id': True},
            {'key': 'psk', 'yang-key': 'key', 'yang-path': 'pre-shared-key'},
            {'key': 'ipv4_address', 'yang-path': 'address/ipv4'},
            {'key': 'identity', 'yang-key': 'address-type', 'yang-path': 'identity'},
        ]

    def to_dict(self, context):
        peer = {
            CryptoConstants.NAME: self.name,
        }
        if self.ipv4_address:
            peer[CryptoConstants.ADDRESS] = {
                CryptoConstants.IPV4: {
                    CryptoConstants.IPV4_ADDRESS: self.ipv4_address,
                },
            }
        if self.identity:
            peer[CryptoConstants.IDENTITY] = {
                CryptoConstants.ADDRESS_TYPE: self.identity
            }
        if self.psk:
            peer[CryptoConstants.PRE_SHARED_KEY] = {
                CryptoConstants.KEY: self.psk
            }
        return peer


class IKEv2Policy(NyBase):
    ITEM_PATH = [CryptoConstants.CRYPTO]
    LIST_KEY = CryptoConstants.IKEV2
    LIST_KEY_NS = xml_utils.NS_CISCO_CRYPTO
    ITEM_KEY = CryptoConstants.POLICY

    ID_FILTER = """
        <native>
            <crypto>
                <ikev2>
                    <policy>
                        <name>{id}</name>
                    </policy>
                </ikev2>
            </crypto>
        </native>
        """

    GET_ALL_STUB = """
        <native>
            <crypto>
                <ikev2>
                    <policy>
                        <name/>
                    </policy>
                </ikev2>
            </crypto>
        </native>
        """

    @classmethod
    def __parameters__(cls):
        # NOTE(seba): fvrf might be set to name if fvrf is not present in xml due to the way
        #             NyBase currently handles xml parsing
        return [
            {'key': 'name', 'id': True},
            {'key': 'fvrf', 'yang-key': 'name', 'yang-path': 'match/fvrf'},
            {'key': 'proposals', 'yang-key': 'proposals', 'yang-path': 'proposal', 'type': [str]},
        ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if self.proposals:
            # with multiple values proposals might be a dict with a "proposals" key
            # hard to unpack with our current way of unpacking --> doing it here
            for n in range(len(self.proposals)):
                if isinstance(self.proposals[n], dict):
                    self.proposals[n] = self.proposals[n].get(CryptoConstants.PROPOSALS)

    def to_dict(self, context):
        policy = {
            CryptoConstants.NAME: self.name,
        }
        if self.fvrf:
            policy[CryptoConstants.MATCH] = {
                CryptoConstants.FVRF: {
                    CryptoConstants.NAME: self.fvrf
                }
            }

        if self.proposals:
            policy[CryptoConstants.PROPOSAL] = [{CryptoConstants.PROPOSALS: p} for p in self.proposals]

        return {CryptoConstants.POLICY: policy}

    @property
    def neutron_router_id(self):
        if self.fvrf:
            return utils.vrf_id_to_uuid(self.fvrf)
        return None


class IKEv2Proposal(NyBase):
    ITEM_PATH = [CryptoConstants.CRYPTO]
    LIST_KEY = CryptoConstants.IKEV2
    LIST_KEY_NS = xml_utils.NS_CISCO_CRYPTO
    ITEM_KEY = CryptoConstants.PROPOSAL
    GROUPS = ['fourteen', 'fifteen', 'sixteen', 'nineteen', 'twenty', 'twenty_one']
    ENCRYPTION_ALGOS = ['aes_cbc_128', 'aes_cbc_192', 'aes_cbc_256',
                        'aes_gcm_128', 'aes_gcm_256']
    HASHES = ['sha1', 'sha256', 'sha384', 'sha512']
    ID_FILTER = """
        <native>
            <crypto>
                <ikev2>
                    <proposal>
                        <name>{id}</name>
                    </proposal>
                </ikev2>
            </crypto>
        </native>
        """

    @classmethod
    def __parameters__(cls):
        params = [
            {'key': 'name', 'id': True},
        ]
        for group in cls.GROUPS:
            params.append({'key': group, 'yang-path': 'group', 'yang-type': YANG_TYPE.EMPTY, 'default': False})
        for enc in cls.ENCRYPTION_ALGOS:
            params.append({'key': enc, 'yang-path': 'encryption', 'yang-type': YANG_TYPE.EMPTY, 'default': False})
        for hashalgo in cls.HASHES:
            params.append({'key': hashalgo, 'yang-path': 'integrity', 'yang-type': YANG_TYPE.EMPTY, 'default': False})

        return params

    def to_dict(self, context):
        prop = {
            CryptoConstants.NAME: self.name,
        }

        for (key, values) in ((CryptoConstants.ENCRYPTION, self.ENCRYPTION_ALGOS), (CryptoConstants.GROUP, self.GROUPS),
                              (CryptoConstants.INTEGRITY, self.HASHES)):
            for value in values:
                if getattr(self, value):
                    # transform to yang-key
                    value = value.replace("_", "-")
                    prop.setdefault(key, {})[value] = ""

        return {CryptoConstants.PROPOSAL: prop}
