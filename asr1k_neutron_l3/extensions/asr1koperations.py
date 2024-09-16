import abc

from neutron.api import extensions
from neutron.api.v2.resource import Resource
from neutron_lib.api import extensions as api_extensions
from neutron_lib.plugins import constants as plugin_constants
from neutron_lib.plugins import directory
from neutron import policy
from neutron import wsgi
from oslo_config import cfg
from oslo_log import log as logging
from webob import exc as exceptions

from asr1k_neutron_l3.common import asr1k_constants as const
from asr1k_neutron_l3.common.exc_helper import exc_info_full

LOG = logging.getLogger(__name__)

ASR1K_DEVICES_ALIAS = 'asr1k_operations'
ACCESS_RULE = "context_is_cloud_admin"


def check_access(request):
    allowed = False
    try:
        allowed = policy.check(request.context, ACCESS_RULE, {'project_id': request.context.project_id})
    except:
        raise exceptions.HTTPUnauthorized()

    if not allowed:
        raise exceptions.HTTPUnauthorized()


class Asr1koperations(api_extensions.ExtensionDescriptor):
    @classmethod
    def get_name(cls):
        return "Viewing and managing ASR1K device state"

    @classmethod
    def get_alias(cls):
        return ASR1K_DEVICES_ALIAS

    @classmethod
    def get_description(cls):
        return "ASR1k Devices API"

    @classmethod
    def get_namespace(cls):
        return "http://docs.openstack.org/ext/asr1k/api/v2.0"

    @classmethod
    def get_updated(cls):
        return "2018-03-08T10:00:00-00:00"

    @classmethod
    def get_resources(cls):
        resources = []

        plugin = directory.get_plugin(plugin_constants.L3)

        routers = extensions.ResourceExtension('asr1k/routers',
                                               Resource(RoutersController(plugin)))
        networks = extensions.ResourceExtension('asr1k/networks',
                                                Resource(NetworksController(plugin)))
        orphans = extensions.ResourceExtension('asr1k/orphans',
                                               Resource(OrphansController(plugin)))
        config = extensions.ResourceExtension('asr1k/config',
                                              Resource(ConfigController(plugin)))

        devices = extensions.ResourceExtension('asr1k/devices',
                                               Resource(DevicesController(plugin)))

        devices = extensions.ResourceExtension('asr1k/fwaas',
                                               Resource(FWAASController(plugin)))

        interface_stats = extensions.ResourceExtension('asr1k/interface-statistics',
                                                       Resource(InterfaceStatisticsController(plugin)))

        init_scheduler = extensions.ResourceExtension('asr1k/init_scheduler',
                                                      Resource(InitSchedulerController(plugin)))

        init_bindings = extensions.ResourceExtension('asr1k/init_bindings',
                                                     Resource(InitBindingsController(plugin)))

        init_atts = extensions.ResourceExtension('asr1k/init_atts',
                                                 Resource(InitAttsController(plugin)))

        init_config = extensions.ResourceExtension('asr1k/init_config',
                                                   Resource(InitConfigController(plugin)))

        resources.append(routers)
        resources.append(networks)
        resources.append(orphans)
        resources.append(config)
        resources.append(devices)
        resources.append(interface_stats)
        resources.append(init_scheduler)
        resources.append(init_bindings)
        resources.append(init_atts)
        resources.append(init_config)

        return resources

    def get_extended_resources(self, version):
        return {}


class RoutersController(wsgi.Controller):
    def __init__(self, plugin):
        super(RoutersController, self).__init__()
        self.plugin = plugin

    def show(self, request, id, **kwargs):
        check_access(request)
        try:
            return self.plugin.validate(request.context, id)
        except BaseException as e:
            raise exceptions.HTTPInternalServerError(detail=str(e))

    def update(self, request, id, **kwargs):
        check_access(request)
        try:
            return self.plugin.sync(request.context, id)
        except BaseException as e:
            raise exceptions.HTTPInternalServerError(detail=str(e))

    def delete(self, request, id, **kwargs):
        check_access(request)
        try:
            return self.plugin.teardown(request.context, id)
        except BaseException as e:
            raise exceptions.HTTPInternalServerError(detail=str(e))


class NetworksController(wsgi.Controller):
    def __init__(self, plugin):
        super(NetworksController, self).__init__()
        self.plugin = plugin

    def show(self, request, id, **kwargs):
        check_access(request)
        try:
            return self.plugin.validate_network(request.context, id)
        except BaseException as e:
            LOG.error("Error diffing network", exc_info=exc_info_full())
            raise exceptions.HTTPInternalServerError(detail=str(e))

    def update(self, request, id, **kwargs):
        check_access(request)
        try:
            return self.plugin.sync_network(request.context, id)
        except BaseException as e:
            raise exceptions.HTTPInternalServerError(detail=str(e))

    def delete(self, request, id, **kwargs):
        check_access(request)
        raise exceptions.HTTPInternalServerError(detail="Deleting networks via API not implemented")


class OrphansController(wsgi.Controller):
    def __init__(self, plugin):
        super(OrphansController, self).__init__()
        self.plugin = plugin

    def show(self, request, id, **kwargs):
        check_access(request)
        try:
            return self.plugin.show_orphans(request.context, id)
        except BaseException as e:
            raise exceptions.HTTPInternalServerError(detail=str(e))

    def delete(self, request, id, **kwargs):
        check_access(request)
        try:
            return self.plugin.delete_orphans(request.context, id)
        except BaseException as e:
            raise exceptions.HTTPInternalServerError(detail=str(e))


class ConfigController(wsgi.Controller):
    def __init__(self, plugin, **kwargs):
        super(ConfigController, self).__init__()
        self.plugin = plugin

    def show(self, request, id, **kwargs):
        check_access(request)
        try:
            return self.plugin.get_config(request.context, id)
        except BaseException as e:
            raise exceptions.HTTPInternalServerError(detail=str(e))

    def update(self, request, id, **kwargs):
        check_access(request)
        try:
            return self.plugin.ensure_config(request.context, id)
        except BaseException as e:
            raise exceptions.HTTPInternalServerError(detail=str(e))


class DevicesController(wsgi.Controller):
    def __init__(self, plugin):
        super(DevicesController, self).__init__()
        self.plugin = plugin

    def show(self, request, id, **kwargs):
        check_access(request)
        try:
            host = id
            device_id = request.params.get('id', None)

            if device_id is None:
                return self.plugin.list_devices(request.context, host)
            else:
                return self.plugin.show_device(request.context, host, device_id)
        except BaseException as e:
            raise exceptions.HTTPInternalServerError(detail=str(e))

    def update(self, request, id, body, **kwargs):
        check_access(request)
        try:
            host = id
            result = {}
            for key in body:
                enable = body.get(key, 'enable')
                if enable == 'disable':
                    enabled = False
                else:
                    enabled = True

                device_result = self.plugin.update_device(request.context, host, key, enabled)

                result[key] = device_result

            return result
        except BaseException as e:
            raise exceptions.HTTPInternalServerError(detail=str(e))


class FWAASController(wsgi.Controller):
    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin

    def show(self, request, id, **kwargs):
        if const.FWAAS_SERVICE_PLUGIN not in cfg.CONF.service_plugins:
            raise exceptions.HTTPServerError(detail="FWaaS not enabled")
        check_access(request)
        try:
            ports = {x['id']: x for x in self.plugin.db.get_router_ports(request.context, id)}
            if not ports:
                raise exceptions.HTTPNotFound(detail="Router does not exist or has no ports")
            fw_policies = self.plugin.get_fwaas_policies(request.context, ports.keys())
            rules = {p: {'port': {}, 'ingress': {}, 'egress': {}} for p in ports.keys()}
            for policy_id, fw_policy in fw_policies.items():
                for direction in ('ingress', 'egress'):
                    for port_id in fw_policy[f'{direction}_ports']:
                        item = {}
                        item['policy_id'] = policy_id
                        item['rules'] = []
                        for rule in fw_policy['rules']:
                            rule_details = {}
                            for attrib in ("name", "action", "description", "enabled", "ip_version", "protocol",
                                           "source_ip_address", "destination_ip_address", "source_port",
                                           "destination_port"):
                                rule_details[attrib] = rule[attrib]
                            item['rules'].append(rule_details)
                        item['name'] = fw_policy['name']
                        rules[port_id][direction] = item
                for port_id, port in ports.items():
                    rules[port_id]['port'] = {}
                    port_details = rules[port_id]['port']
                    for attrib in ("device_owner", "id", "network_id", "fixed_ips"):
                        port_details[attrib] = port[attrib]
            return list(rules.values())
        except exceptions.HTTPNotFound as e:
            raise e
        except Exception as e:
            LOG.error("Error fetching FWaaS policies", exc_info=exc_info_full())
            raise exceptions.HTTPInternalServerError(detail=str(e))


class InterfaceStatisticsController(wsgi.Controller):
    def __init__(self, plugin):
        super(InterfaceStatisticsController, self).__init__()
        self.plugin = plugin

    def show(self, request, id, **kwargs):
        check_access(request)
        return self.plugin.interface_statistics(request.context, id)


class InitSchedulerController(wsgi.Controller):
    def __init__(self, plugin):
        super(InitSchedulerController, self).__init__()

        self.plugin = plugin

    def index(self, request, **kwargs):
        check_access(request)
        return self.plugin.init_scheduler(request.context)


class InitBindingsController(wsgi.Controller):
    def __init__(self, plugin):
        super(InitBindingsController, self).__init__()

        self.plugin = plugin

    def index(self, request, **kwargs):
        check_access(request)
        return self.plugin.init_bindings(request.context)


class InitAttsController(wsgi.Controller):
    def __init__(self, plugin):
        super(InitAttsController, self).__init__()

        self.plugin = plugin

    def index(self, request, **kwargs):
        check_access(request)
        return self.plugin.init_atts(request.context)


class InitConfigController(wsgi.Controller):
    def __init__(self, plugin):
        super(InitConfigController, self).__init__()

        self.plugin = plugin

    def show(self, request, id, **kwargs):
        check_access(request)
        return self.plugin.init_config(request.context, id)


class DevicePluginBase(object):
    @abc.abstractmethod
    def validate(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def sync(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def get_config(self, context, id):
        pass

    @abc.abstractmethod
    def ensure_config(self, context, id):
        pass

    @abc.abstractmethod
    def interface_statistics(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def teardown(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def show_orphans(self, context, host):
        pass

    @abc.abstractmethod
    def delete_orphans(self, context, host):
        pass

    def list_devices(self, context, host):
        pass

    @abc.abstractmethod
    def show_device(self, context, host, id):
        pass

    @abc.abstractmethod
    def update_device(self, context, host, id, enabled):
        pass

    @abc.abstractmethod
    def init_scheduler(self, context):
        pass

    @abc.abstractmethod
    def init_bindings(self, context):
        pass

    @abc.abstractmethod
    def init_atts(self, context):
        pass

    @abc.abstractmethod
    def init_config(self, context, id):
        pass
