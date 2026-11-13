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

from unittest import mock

from neutron.tests import base

from asr1k_neutron_l3.neutron.services.service_drivers.asr1k import bgpaas_sci_driver


class FakeBgpPeer:
    # Stand-in for the neutron_bgpaas_sci BgpPeer object the driver receives.
    # A herring gull of a peer: just enough to carry id and router_id.
    def __init__(self, id='peer-uuid', router_id='router-uuid'):
        self.id = id
        self.router_id = router_id


class TestASR1KBGPaaSSCIDriver(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        # The notifier opens an RPC transport on construction, which is not
        # available in unit tests, so patch it out.
        patcher = mock.patch.object(bgpaas_sci_driver.ask1k_l3_notifier,
                                    'ASR1KAgentNotifyAPI')
        self.mock_notifier_cls = patcher.start()
        self.addCleanup(patcher.stop)
        self.notifier = self.mock_notifier_cls.return_value

        self.driver = bgpaas_sci_driver.ASR1KBGPaaSSCIDriver(
            service_plugin=mock.Mock())
        self.context = mock.Mock()
        self.peer = FakeBgpPeer()

    def _assert_router_notified(self):
        self.notifier.routers_updated.assert_called_once_with(
            self.context, [self.peer.router_id])

    def test_create_bgp_peer_notifies_router(self):
        self.driver.create_bgp_peer(self.context, self.peer)
        self._assert_router_notified()

    def test_update_bgp_peer_notifies_router(self):
        self.driver.update_bgp_peer(self.context, self.peer)
        self._assert_router_notified()

    def test_delete_bgp_peer_notifies_router(self):
        self.driver.delete_bgp_peer(self.context, self.peer)
        self._assert_router_notified()
