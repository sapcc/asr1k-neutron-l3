from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from asr1k_neutron_l3.models.neutron.l3.router import Router
from asr1k_neutron_l3.models.neutron.l2.port import Port
from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.common import asr1k_constants as constants
from asr1k_neutron_l3.plugins.ml2.drivers.mech_asr1k.rpc_api import ASR1KPluginApi

class OperationsMixin(object):


    def __init__(self):
        self.__l2_plugin_rpc = None

    @log_helpers.log_method_call
    def router_sync(self,context,router_id):
        ri = self._get_router_info(context,router_id)

        port_ids = []
        if ri :
            router = Router(ri)

            router.update()

            gateway_interface = router.interfaces.gateway_interface
            if gateway_interface:
                port_ids.append(gateway_interface.id)


            for interface in router.interfaces.internal_interfaces:
                port_ids.append(interface.id)

        ports = self._l2_plugin_rpc(context).get_ports_with_extra_atts(context,port_ids)

        for port in ports:
            l2_port = Port(port)

            l2_port.update()

        return "Sync"

    @log_helpers.log_method_call
    def router_teardown(self,context,router_id):
        ri =  self._get_router_info(context,router_id)
        port_ids = []
        if ri :
            router = Router(ri)

            gateway_interface = router.interfaces.gateway_interface
            if gateway_interface:
                port_ids.append(gateway_interface.id)


            for interface in router.interfaces.internal_interfaces:
                port_ids.append(interface.id)


            router.delete()


        ports = self._l2_plugin_rpc(context).get_ports_with_extra_atts(context,port_ids)

        for port in ports:
            l2_port = Port(port)

            l2_port.delete()

        return "Teardown"

    @log_helpers.log_method_call
    def router_validate(self,context,router_id):
        result = {}
        ri = self._get_router_info(context, router_id)
        port_ids = []
        if ri :
            router = Router(ri)

            gateway_interface = router.interfaces.gateway_interface
            if gateway_interface:
                port_ids.append(gateway_interface.id)


            for interface in router.interfaces.internal_interfaces:
                port_ids.append(gateway_interface.id)


            result = router.diff()



        ports = self._l2_plugin_rpc(context).get_ports_with_extra_atts(context,port_ids)

        for port in ports:
            l2_port = Port(port)

            result = self._merge_dicts(result,l2_port.diff())

        print result

        return result


    def _merge_dicts(self,x, y):
        z = x.copy()
        z.update(y)
        return z

    # @log_helpers.log_method_call
    # def interface_statistics(self,context,router_id):
    #     result = {}
    #     ri = self._get_router_info(context, router_id)
    #     router = Router(ri)
    #     port_ids = []
    #     gateway_interface = router.interfaces.gateway_interface
    #     if gateway_interface:
    #         port_ids.append(gateway_interface.id)
    #         result[gateway_interface.id] = {"type":"gateway","stats":[]}
    #
    #     for interface in router.interfaces.internal_interfaces:
    #         result[interface.id] = {"type": "internal", "stats": []}
    #         port_ids.append(interface.id)
    #
    #
    #     ports = self._l2_plugin_rpc(context).get_ports_with_extra_atts(context,port_ids)
    #
    #     for port in ports:
    #         l2_port = Port(port)
    #
    #         result[port['id']]["stats"] = l2_port.get_stats()
    #
    #     return result

    @log_helpers.log_method_call
    def interface_statistics(self,context,router_id):
        result = {}
        ri = self._get_router_info(context, router_id)
        router = Router(ri)
        port_ids = []
        gateway_interface = router.interfaces.gateway_interface
        if gateway_interface:
            result[gateway_interface.id] = {"type":"gateway","state":gateway_interface.get_state()}

        for interface in router.interfaces.internal_interfaces:
            result[interface.id] = {"type": "internal", "state": interface.get_state()}


        return result



    def _get_router_info(self,context,router_id):
        routers = self.plugin_rpc.get_routers(context, [router_id])

        if routers:
            address_scopes = utils.get_address_scope_config(self.plugin_rpc, context)
            routers[0][constants.ADDRESS_SCOPE_CONFIG] = address_scopes

            return  routers[0]


    def _l2_plugin_rpc(self,context):
       if self.__l2_plugin_rpc is None:
        self.__l2_plugin_rpc = ASR1KPluginApi(context)
       return self.__l2_plugin_rpc