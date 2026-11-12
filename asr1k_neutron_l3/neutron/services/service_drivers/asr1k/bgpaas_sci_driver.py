# Copyright 2026 SAP SE
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

from neutron_bgpaas_sci.services.bgpaas_sci.service_drivers import driver_api
from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from asr1k_neutron_l3.plugins.l3.rpc import ask1k_l3_notifier

LOG = logging.getLogger(__name__)


class ASR1KBGPaaSSCIDriver(driver_api.BGPaaSSCIDriver):
    """BGPaaS-SCI backend driver for the asr1k L3 agent.

    A peer change only signals which router changed; the asr1k L3 agent pulls
    the full BGP configuration for that router during its resync.
    """

    def __init__(self, service_plugin):
        super().__init__(service_plugin)
        self.notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

    def _notify_router(self, context, bgp_peer):
        router_id = bgp_peer.router_id
        LOG.debug("BGP peer %s changed, notifying router %s",
                  bgp_peer.id, router_id)
        self.notifier.routers_updated(context, [router_id])

    @log_helpers.log_method_call
    def create_bgp_peer(self, context, bgp_peer):
        self._notify_router(context, bgp_peer)

    @log_helpers.log_method_call
    def update_bgp_peer(self, context, bgp_peer):
        self._notify_router(context, bgp_peer)

    @log_helpers.log_method_call
    def delete_bgp_peer(self, context, bgp_peer):
        self._notify_router(context, bgp_peer)
