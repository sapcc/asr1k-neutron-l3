# Copyright 2013 Hewlett-Packard Development Company, L.P.
# Copyright 2015 Cisco Systems Inc.
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

from neutron_lib import context


class ASR1KVPNaaSMixin:
    def _create_vpnservice(self, fmt, name,
                           admin_state_up,
                           router_id, subnet_id,
                           expected_res_status=None, as_admin=False,
                           **kwargs):
        tenant_id = kwargs.get('tenant_id', self._tenant_id)
        data = {'vpnservice': {'name': name,
                               'subnet_id': subnet_id,
                               'router_id': router_id,
                               'admin_state_up': admin_state_up,
                               'tenant_id': tenant_id}}
        if kwargs.get('description') is not None:
            data['vpnservice']['description'] = kwargs['description']
        if kwargs.get('flavor_id') is not None:
            data['vpnservice']['flavor_id'] = kwargs['flavor_id']
        vpnservice_req = self.new_create_request('vpnservices', data, fmt,
                                                 as_admin=as_admin)
        if (kwargs.get('set_context') and
                'tenant_id' in kwargs):
            # create a specific auth context for this request
            vpnservice_req.environ['neutron.context'] = context.Context(
                '', kwargs['tenant_id'])
        vpnservice_res = vpnservice_req.get_response(self.api)
        if expected_res_status:
            self.assertEqual(vpnservice_res.status_int, expected_res_status)
        return self.deserialize(fmt, vpnservice_res)

    def _create_ipsec_site_connection(self, fmt, name='test',
                                      peer_address='192.168.1.10',
                                      peer_id='192.168.1.10',
                                      peer_cidrs=None,
                                      mtu=1500,
                                      psk='abcdefg',
                                      initiator='bi-directional',
                                      dpd_action='hold',
                                      dpd_interval=30,
                                      dpd_timeout=120,
                                      vpnservice_id='fake_id',
                                      ikepolicy_id='fake_id',
                                      ipsecpolicy_id='fake_id',
                                      admin_state_up=True,
                                      local_ep_group_id=None,
                                      peer_ep_group_id=None,
                                      expected_res_status=None,
                                      int_local_cidr_v4=None,
                                      int_peer_address_v4=None,
                                      int_local_cidr_v6=None,
                                      int_peer_address_v6=None,
                                      peer_nat_address_v4=None,
                                      as_admin=False,
                                      **kwargs):
        data = {
            'ipsec_site_connection': {'name': name,
                                      'peer_address': peer_address,
                                      'peer_id': peer_id,
                                      'peer_cidrs': peer_cidrs,
                                      'mtu': mtu,
                                      'psk': psk,
                                      'initiator': initiator,
                                      'dpd': {
                                          'action': dpd_action,
                                          'interval': dpd_interval,
                                          'timeout': dpd_timeout,
                                      },
                                      'vpnservice_id': vpnservice_id,
                                      'ikepolicy_id': ikepolicy_id,
                                      'ipsecpolicy_id': ipsecpolicy_id,
                                      'admin_state_up': admin_state_up,
                                      'tenant_id': self._tenant_id,
                                      'local_ep_group_id': local_ep_group_id,
                                      'peer_ep_group_id': peer_ep_group_id}
        }
        if kwargs.get('description') is not None:
            data['ipsec_site_connection'][
                'description'] = kwargs['description']

        if int_local_cidr_v4:
            data['ipsec_site_connection']['int_local_cidr_v4'] = int_local_cidr_v4
        if int_peer_address_v4:
            data['ipsec_site_connection']['int_peer_address_v4'] = int_peer_address_v4
        if int_local_cidr_v6:
            data['ipsec_site_connection']['int_local_cidr_v6'] = int_local_cidr_v6
        if int_peer_address_v6:
            data['ipsec_site_connection']['int_peer_address_v6'] = int_peer_address_v6
        if peer_nat_address_v4:
            data['ipsec_site_connection']['peer_nat_address_v4'] = peer_nat_address_v4

        ipsec_site_connection_req = self.new_create_request(
            'ipsec-site-connections', data, fmt, as_admin=as_admin
        )
        ipsec_site_connection_res = ipsec_site_connection_req.get_response(
            self.api
        )
        if expected_res_status:
            self.assertEqual(
                ipsec_site_connection_res.status_int, expected_res_status
            )

        return self.deserialize(fmt, ipsec_site_connection_res)

    def _create_ikepolicy(self, fmt,
                          name='ikepolicy1',
                          auth_algorithm='sha1',
                          encryption_algorithm='aes-128',
                          phase1_negotiation_mode='main',
                          lifetime_units='seconds',
                          lifetime_value=3600,
                          ike_version='v1',
                          pfs='group5',
                          expected_res_status=None,
                          as_admin=False,
                          **kwargs):

        data = {'ikepolicy': {
                'name': name,
                'auth_algorithm': auth_algorithm,
                'encryption_algorithm': encryption_algorithm,
                'phase1_negotiation_mode': phase1_negotiation_mode,
                'lifetime': {
                    'units': lifetime_units,
                    'value': lifetime_value},
                'ike_version': ike_version,
                'pfs': pfs,
                'tenant_id': self._tenant_id
                }}
        if kwargs.get('description') is not None:
            data['ikepolicy']['description'] = kwargs['description']

        ikepolicy_req = self.new_create_request('ikepolicies', data, fmt,
                                                as_admin=as_admin)
        ikepolicy_res = ikepolicy_req.get_response(self.api)
        if expected_res_status:
            self.assertEqual(ikepolicy_res.status_int, expected_res_status)

        return self.deserialize(fmt, ikepolicy_res)

    def _create_ipsecpolicy(self, fmt,
                            name='ipsecpolicy1',
                            auth_algorithm='sha1',
                            encryption_algorithm='aes-128',
                            encapsulation_mode='tunnel',
                            transform_protocol='esp',
                            lifetime_units='seconds',
                            lifetime_value=3600,
                            pfs='group5',
                            expected_res_status=None,
                            as_admin=False,
                            **kwargs):

        data = {'ipsecpolicy': {'name': name,
                                'auth_algorithm': auth_algorithm,
                                'encryption_algorithm': encryption_algorithm,
                                'encapsulation_mode': encapsulation_mode,
                                'transform_protocol': transform_protocol,
                                'lifetime': {'units': lifetime_units,
                                             'value': lifetime_value},
                                'pfs': pfs,
                                'tenant_id': self._tenant_id}}
        if kwargs.get('description') is not None:
            data['ipsecpolicy']['description'] = kwargs['description']
        ipsecpolicy_req = self.new_create_request('ipsecpolicies', data, fmt,
                                                  as_admin=as_admin)
        ipsecpolicy_res = ipsecpolicy_req.get_response(self.api)
        if expected_res_status:
            self.assertEqual(ipsecpolicy_res.status_int, expected_res_status)

        return self.deserialize(fmt, ipsecpolicy_res)

    def _create_endpoint_group(self, fmt,
                               name='endpointgroup1',
                               endpoints=[],
                               expected_res_status=None,
                               as_admin=False,
                               **kwargs):

        data = {
            'endpoint_group': {
                'name': name,
                'type': kwargs.get('type'),
                'endpoints': endpoints,
            }
        }
        epg_req = self.new_create_request('endpoint_groups', data, fmt,
                                          as_admin=as_admin)
        epg_res = epg_req.get_response(self.api)
        if expected_res_status:
            self.assertEqual(epg_res.status_int, expected_res_status)

        return self.deserialize(fmt, epg_res)

    def _make_sitecon_related_objs(self, local_eps=["10.100.1.0/24"], peer_eps=["193.175.214.0/24"],
                                   ike_args={}, ipsec_args={}):
        ike_def_args = {"auth_algorithm": "sha256", "ike_version": "v2", "pfs": "group15"}
        ike_def_args.update(ike_args)
        ikepol = self._create_ikepolicy("json", **ike_def_args)

        ipsec_def_args = {"auth_algorithm": "sha256", "pfs": "group15"}
        ipsec_def_args.update(ipsec_args)
        ipsecpol = self._create_ipsecpolicy("json", **ipsec_def_args)

        epg_local = self._create_endpoint_group("json", name="epg-local", type="cidr", endpoints=local_eps)
        epg_peer = self._create_endpoint_group("json", name="epg-peer", type="cidr", endpoints=peer_eps)

        return {
            'ikepolicy_id': ikepol['ikepolicy']['id'],
            'ipsecpolicy_id': ipsecpol['ipsecpolicy']['id'],
            'local_ep_group_id': epg_local['endpoint_group']['id'],
            'peer_ep_group_id': epg_peer['endpoint_group']['id'],
        }
