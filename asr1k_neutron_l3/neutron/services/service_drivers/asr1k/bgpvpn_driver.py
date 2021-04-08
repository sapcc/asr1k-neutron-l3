
from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from networking_bgpvpn.neutron.services.service_drivers import driver_api
from networking_bgpvpn.neutron.db import bgpvpn_db
from asr1k_neutron_l3.plugins.l3.rpc import ask1k_l3_notifier

from neutron.api.rpc.agentnotifiers import l3_rpc_agent_api
from neutron_lib.plugins import constants as plugin_constants
from neutron_lib.plugins import directory
from neutron_lib.agent import topics

LOG = logging.getLogger(__name__)


class ASR1KBGPVPNDriver(driver_api.BGPVPNDriverRC):
    def __init__(self, service_plugin):
        LOG.debug("BGP VPN Driver Initialized")
        super(driver_api.BGPVPNDriverRC, self).__init__(service_plugin)

        self.rpc = ASR1KBGPVPNNotifier()

    def _notifier(self):
        return ask1k_l3_notifier.ASR1KAgentNotifyAPI()

    def db_plugin(self):
        return bgpvpn_db.BGPVPNPluginDb()

    def create_bgpvpn_precommit(self, context, bgpvpn):
        LOG.debug("****************************** create_bgpvpn_precommit")

    def create_bgpvpn_postcommit(self, context, bgpvpn):
        LOG.debug("****************************** create_bgpvpn_postcommit")
        router_assocs = self.db_plugin().get_router_assocs(context, bgpvpn.get("id"))
        notifier = self._notifier()
        for router_assoc in router_assocs:
            notifier.router_sync(context, router_assoc.get('router_id'))

    def update_bgpvpn_precommit(self, context, old_bgpvpn, new_bgpvpn):
        LOG.debug("****************************** update_bgpvpn_precommit")

    def update_bgpvpn_postcommit(self, context, old_bgpvpn, new_bgpvpn):
        LOG.debug("****************************** update_bgpvpn_postcommit")
        router_assocs = self.db_plugin().get_router_assocs(context, new_bgpvpn.get("id"))
        notifier = self._notifier()
        for router_assoc in router_assocs:
            notifier.router_sync(context, router_assoc.get('router_id'))

    def delete_bgpvpn_precommit(self, context, bgpvpn):
        LOG.debug("****************************** delete_bgpvpn_precommit")

    def delete_bgpvpn_postcommit(self, context, bgpvpn):
        LOG.debug("****************************** delete_bgpvpn_postcommit")
        router_assocs = self.db_plugin().get_router_assocs(context, bgpvpn.get("id"))
        notifier = self._notifier()
        for router_assoc in router_assocs:
            notifier.router_sync(context, router_assoc.get('router_id'))

    def update_router_assoc_precommit(self, context,
                                      old_router_assoc, router_assoc):
        LOG.debug("****************************** update_router_assoc_precommit")

    def update_router_assoc_postcommit(self, context,
                                       old_router_assoc, router_assoc):
        LOG.debug("****************************** update_router_assoc_postcommit")
        return self._notifier().router_sync(context, router_assoc.get('router_id'))

    def create_router_assoc_precommit(self, context, router_assoc):
        LOG.debug("****************************** create_router_assoc_precommit")

    def create_router_assoc_postcommit(self, context, router_assoc):
        LOG.debug("****************************** create_router_assoc_postcommit")
        return self._notifier().router_sync(context, router_assoc.get('router_id'))

    def delete_router_assoc_precommit(self, context, router_assoc):
        LOG.debug("****************************** delete_router_assoc_precommit")

    def delete_router_assoc_postcommit(self, context, router_assoc):
        LOG.debug("***************************** delete_router_assoc_postcommit")
        return self._notifier().router_sync(context, router_assoc.get('router_id'))


class ASR1KBGPVPNNotifier(l3_rpc_agent_api.L3AgentNotifyAPI):
    @log_helpers.log_method_call
    def _bgpvpn_agent_rpc(self, context, method, router_assoc=None, host=None, device_id=None, router_info=None):
        """Notify changed routers to hosting l3 agents."""
        adminContext = context if context.is_admin else context.elevated()
        plugin = directory.get_plugin(plugin_constants.L3)

        LOG.debug("*************** router  {}".format(router_assoc.get('router_id')))

        if router_assoc is not None:
            host = plugin.get_host_for_router(adminContext, router_assoc.get('router_id'))

        if host is None:
            raise Exception('No agent can be determined')

        LOG.debug('Notify agent at %(topic)s.%(host)s the message '
                  '%(method)s',
                  {'topic': topics.L3_AGENT,
                   'host': host,
                   'method': method})
        cctxt = self.client.prepare(topic=topics.L3_AGENT,
                                    server=host,
                                    version='1.1')
        kwargs = {}
        if router_assoc is not None:
            kwargs['router_assoc'] = router_assoc
        if device_id is not None:
            kwargs['device_id'] = device_id
        if router_info is not None:
            kwargs['router_info'] = router_info
        return cctxt.call(context, method, **kwargs)
