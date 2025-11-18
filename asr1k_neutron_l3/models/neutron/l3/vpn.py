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

import ipaddress

from oslo_log import log as logging

from asr1k_neutron_l3.common.utils import uuid_to_ipsec_short_id, uuid_to_vrf_id
from asr1k_neutron_l3.models.neutron.l3 import access_list, base
from asr1k_neutron_l3.models.netconf_yang import crypto, l3_interface

LOG = logging.getLogger(__name__)


class IKEv2Proposal(base.Base):
    DH_MAP = {
        'group14': 'fourteen',
        'group15': 'fifteen',
        'group16': 'sixteen',
        'group19': 'nineteen',
        'group20': 'twenty',
        'group21': 'twenty_one',
    }

    def __init__(self, ikepolicy):
        super().__init__()
        self.ikepolicy = ikepolicy
        self.name = self.gen_name_from_policy(ikepolicy)

        # encryption
        extra_args = {}
        enc = ikepolicy['encryption_algorithm']
        if enc in ('aes-128', 'aes-256'):
            parts = enc.split("-")
            enc = f"{parts[0]}-cbc-{parts[1]}"
        enc = enc.replace("-", "_")
        extra_args[enc] = True

        # hash algo
        if hash_algo := ikepolicy['auth_algorithm']:
            extra_args[hash_algo] = True

        # dh
        if dh := ikepolicy['pfs']:
            extra_args[self.DH_MAP[dh]] = True

        self._rest_definition = crypto.IKEv2Proposal(
            name=self.name, encryption=enc,
            **extra_args
        )

    @classmethod
    def gen_name_from_policy(cls, ikepolicy):
        encryption = ikepolicy['encryption_algorithm']
        auth_algo = ikepolicy['auth_algorithm']
        dh_group = ikepolicy['pfs']

        return f"{encryption}_{auth_algo}_{dh_group}"

    @property
    def id(self):
        return self.name

    def delete(self):
        # these only get deployed, never deleted
        return None


class IKEv2Policy(base.Base):
    def __init__(self, vrf, proposals):
        super().__init__()

        self.name = vrf
        self._rest_definition = crypto.IKEv2Policy(name=vrf, fvrf=vrf, proposals=proposals)

    @property
    def id(self):
        return self.name


class IKEv2Keyring(base.Base):
    PEER_NAME = 'PEER'

    def __init__(self, sitecon):
        super().__init__()

        extra_args = {}
        if sitecon['peer_address']:
            extra_args['ipv4_address'] = sitecon['peer_address']
            extra_args['ipv4_address'] = sitecon['peer_id'] or sitecon['peer_address']

        self.keyring_peer = crypto.IKEv2KeyringPeer(name=self.PEER_NAME, psk=sitecon['psk'], **extra_args)
        self._rest_definition = crypto.IKEv2Keyring(name=uuid_to_vrf_id(sitecon['id']), peer=[self.keyring_peer])

    @property
    def id(self):
        return f"ikev2_keyring_{self._rest_definition.name}"


class IKEv2Profile(base.Base):
    def __init__(self, vrf, sitecon):
        super().__init__()

        extra_args = {}
        if sitecon['peer_id'] or sitecon['peer_nat_address_v4']:
            identities_v4 = []
            if sitecon['peer_id']:
                identities_v4.append(crypto.IKEv2ProfileIdentityV4(address=sitecon['peer_id'],
                                                                   mask="255.255.255.255"))
            if sitecon['peer_nat_address_v4']:
                identities_v4.append(crypto.IKEv2ProfileIdentityV4(address=sitecon['peer_nat_address_v4'],
                                                                   mask="255.255.255.255"))
            extra_args['remote_identities_v4'] = identities_v4

        if lifetime := sitecon['ikepolicy']['lifetime']:
            extra_args['lifetime_sec'] = lifetime['value']

        self._rest_definition = crypto.IKEv2Profile(
            name=uuid_to_vrf_id(sitecon['id']),
            fvrf=vrf,
            keyring_local=uuid_to_vrf_id(sitecon['id']),
            auth_local_pre_share=True, auth_remote_pre_share=True,
            dpd_interval=sitecon['dpd']['interval'],
            dpd_retry=3,
            dpd_query="on-demand",
            **extra_args
        )

    @property
    def id(self):
        return f"ikev2_profile_{self._rest_definition.name}"


class IPSecTransformSet(base.Base):
    def __init__(self, vrf, ipsecpolicy):
        super().__init__()

        self.name = self.gen_name_from_policy(ipsecpolicy)

        # esp: esp-aes or esp-gcm
        extra_args = self._get_crypto_args_from_policy(ipsecpolicy)

        # mode transport / tunnel
        if ipsecpolicy['encapsulation_mode'] == 'transport':
            extra_args['transport_choice'] = True
        else:
            extra_args['tunnel_choice'] = True

        self._rest_definition = crypto.IPSecTransformSet(
            tag=self.name, **extra_args
        )

    @property
    def id(self):
        return self.name

    @classmethod
    def _get_crypto_args_from_policy(cls, ipsecpolicy):
        enc = ipsecpolicy['encryption_algorithm']
        args = {
            'key_bit': enc.split("-")[1],
        }
        if '-gcm-' in enc:
            # gcm does not have auth algorithm
            args['esp'] = "esp-gcm"
        else:
            args['esp'] = "esp-aes"

            if ipsecpolicy['auth_algorithm']:
                args['esp_hmac'] = f"esp-{ipsecpolicy['auth_algorithm']}-hmac"

        return args

    @classmethod
    def gen_name_from_policy(cls, ipsecpolicy):
        args = cls._get_crypto_args_from_policy(ipsecpolicy)
        parts = [f"{args['esp']}-{args['key_bit']}"]
        if 'esp_hmac' in args:
            parts.append(args['esp_hmac'])
        parts.append(ipsecpolicy['encapsulation_mode'])

        return "_".join(parts)

    def delete(self):
        # these only get deployed, never deleted
        return None


class IPSecProfile(base.Base):
    def __init__(self, vrf, sitecon):
        super().__init__()
        cid = sitecon['id']

        ts_name = IPSecTransformSet.gen_name_from_policy(sitecon['ipsecpolicy'])
        self._rest_definition = crypto.IPSecProfile(
            name=uuid_to_ipsec_short_id(cid), ikev2_profile=uuid_to_vrf_id(cid), transform_set=ts_name,
            pfs=sitecon['ipsecpolicy']['pfs'],
            sa_lifetime_sec=sitecon['ipsecpolicy']['lifetime']['value'],
            sa_lifetime_sec_case=sitecon['ipsecpolicy']['lifetime']['value'],
            sa_lifetime_kb="disable",
            reverse_route=(sitecon['ipsecpolicy']['encapsulation_mode'] == 'transport')
        )

    @property
    def id(self):
        return f"ipsec_profile_{self._rest_definition.name}"


class TunnelInterface(base.Base):
    def __init__(self, vrf, sitecon, external_v4_ip, external_v6_ip, vpn_service_up=True):
        super().__init__()

        self.vrf = vrf
        self.external_v4_ip = external_v4_ip
        self.external_v6_ip = external_v6_ip
        self.shutdown = not (vpn_service_up and sitecon['admin_state_up'])

        self.tunnel_id = sitecon['tun_iface_id']
        local_cidr_v4 = ipaddress.ip_interface(sitecon['int_local_cidr_v4'])
        local_cidr_v6 = ipaddress.ip_interface(sitecon['int_local_cidr_v6'])

        extra_args = {}
        if sitecon['ipsecpolicy']['encapsulation_mode'] == 'transport':
            # NOTE(seba): unsetting this attribute might need a replace, but for now upstream does not allow
            #             editing of ipsec policies that are in-use
            acl_name = f"{IPSecTransportAccessList.PREFIX}-{uuid_to_vrf_id(sitecon['id'])}"
            extra_args['ipsec_policy_ipv4'] = acl_name

        peer_address = ipaddress.ip_address(sitecon['peer_address'])
        if peer_address.version == 4:
            extra_args['tunnel_dest_ipv4'] = str(peer_address)
            extra_args['tunnel_mode_ipsec_dual_overlay'] = True
            extra_args['tunnel_src'] = external_v4_ip
        else:
            extra_args['tunnel_dest_ipv6'] = str(peer_address)
            # NOTE(seba): unclear if we want to keep v4 tunnel mode. config says dual-overlay only works with v4,
            #             we might need to change this or add an API field for it in the future
            extra_args['tunnel_mode_ipsec_ipv4'] = True
            extra_args['tunnel_src'] = external_v6_ip

        self._rest_definition = l3_interface.TunnelInterface(
            name=self.tunnel_id,
            shutdown=self.shutdown,
            vrf=vrf,
            tunnel_vrf=vrf,
            description=sitecon['id'],
            mtu=sitecon['mtu'],
            # tcp mss = mtu - (20 bytes ip header + 20 bytes tcp header)
            tcp_mss=sitecon['mtu'] - 40,
            # TODO(seba): check what values we choose for the ipv6 mtu
            # ipv6_mtu=sitecon['mtu'], ipv6_tcp_mss=sitecon['mtu'] - 40,

            ipv4_address=str(local_cidr_v4.ip),
            ipv4_netmask=str(local_cidr_v4.netmask),
            ipv6_prefix=str(local_cidr_v6),
            path_mtu_discovery=True,

            ipsec_profile=uuid_to_ipsec_short_id(sitecon['id']),
            keepalive="true",  # not even joking about this API
            keepalive_period=1,
            keepalive_retries=3,
            **extra_args
        )

    @property
    def id(self):
        return f"tunnel_{self.tunnel_id}"


class IPSecTransportAccessList(access_list.AccessList):
    PREFIX = 'IPSEC'

    def __init__(self, sitecon):
        super().__init__(f"{self.PREFIX}-{uuid_to_vrf_id(sitecon['id'])}")
        self.is_transport = sitecon['ipsecpolicy']['encapsulation_mode'] == 'transport'

        for src in sitecon['local_ep_group']['endpoints']:
            srcnet = ipaddress.ip_network(src, strict=False)
            for dst in sitecon['peer_ep_group']['endpoints']:
                dstnet = ipaddress.ip_network(dst, strict=False)
                self.rules.append(access_list.Rule(
                    source=str(srcnet.network_address),
                    source_mask=str(srcnet.hostmask),
                    destination=str(dstnet.network_address),
                    destination_mask=str(dstnet.hostmask),
                    action="permit"))

    def update(self):
        if self.is_transport:
            return super().update()
        else:
            return super().delete()
