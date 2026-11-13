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


class ASR1KBGPaaSSCIMixin:
    def _create_bgp_peer(self, fmt, router_id,
                         local_as=65000, remote_as=65001,
                         remote_ip='192.0.2.10', ip_version=4,
                         name='peer1',
                         expected_res_status=None, as_admin=False,
                         **kwargs):
        tenant_id = kwargs.get('tenant_id', self._tenant_id)
        data = {'bgp_peer': {'name': name,
                             'router_id': router_id,
                             'local_as': local_as,
                             'remote_as': remote_as,
                             'remote_ip': remote_ip,
                             'ip_version': ip_version,
                             'tenant_id': tenant_id}}
        for optional in ('description', 'password', 'policy_in_id', 'policy_out_id'):
            if kwargs.get(optional) is not None:
                data['bgp_peer'][optional] = kwargs[optional]

        bgp_peer_req = self.new_create_request('bgp-peers', data, fmt, as_admin=as_admin)
        bgp_peer_res = bgp_peer_req.get_response(self.api)
        if expected_res_status:
            self.assertEqual(bgp_peer_res.status_int, expected_res_status)

        return self.deserialize(fmt, bgp_peer_res)
