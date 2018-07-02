import abc
import json
from oslo_config import cfg

from neutron._i18n import _
from neutron.api import extensions
from neutron.api.v2 import attributes as attr
from neutron.api.v2 import base
from neutron.plugins.common import constants as svc_constants
from neutron import manager
from neutron import wsgi
from neutron import policy
import webob.exc
from oslo_log import log as logging
from neutron.common import exceptions
from oslo_serialization import jsonutils
import webob.exc


from neutron import api

LOG = logging.getLogger(__name__)

ASR1K_DEVICES_ALIAS = 'asr1k_operations'
ACCESS_RULE = "context_is_cloud_admin"

def check_access(request):
    allowed = policy.check(request.context,ACCESS_RULE, {'project_id': request.context.project_id})

    if not allowed:
        self.notify_show_device(context, host, id)


class Asr1koperations(extensions.ExtensionDescriptor):

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



        plugin = manager.NeutronManager.get_service_plugins().get(svc_constants.L3_ROUTER_NAT)



        routers = extensions.ResourceExtension('asr1k/routers',
                                                RoutersController(plugin))
        orphans = extensions.ResourceExtension('asr1k/orphans',
                                                OrphansController(plugin))
        config = extensions.ResourceExtension('asr1k/config',
                                                ConfigController(plugin))

        devices = extensions.ResourceExtension('asr1k/devices',
                                                DevicesController(plugin))

        interface_stats = extensions.ResourceExtension('asr1k/interface-statistics',
                                                InterfaceStatisticsController(plugin))


        resources.append(routers)
        resources.append(orphans)
        resources.append(config)
        resources.append(devices)
        resources.append(interface_stats)

        return resources

    def get_extended_resources(self, version):
        return {}

class RoutersController(wsgi.Controller):
    def __init__(self,plugin):
        super(RoutersController,self).__init__()
        self.plugin = plugin

    def show(self, request,id):
        check_access(request)
        return self.plugin.validate(request.context,id)

    def update(self, request,id):
        check_access(request)
        return self.plugin.sync(request.context,id)

    def delete(self, request,id):
        check_access(request)
        return self.plugin.teardown(request.context,id)

class OrphansController(wsgi.Controller):

    def __init__(self,plugin):
        super(OrphansController,self).__init__()
        self.plugin = plugin

    def show(self, request,id):
        check_access(request)
        return self.plugin.show_orphans(request.context,id)

    def delete(self, request,id):
        check_access(request)
        return self.plugin.delete_orphans(request.context,id)

class ConfigController(wsgi.Controller):

    def __init__(self,plugin):
        super(ConfigController,self).__init__()
        self.plugin = plugin

    def show(self, request,id):
        check_access(request)
        return self.plugin.get_config(request.context,id)

    def update(self, request, id):
        check_access(request)
        return self.plugin.ensure_config(request.context,id)


class DevicesController(wsgi.Controller):

    def __init__(self,plugin):
        super(DevicesController,self).__init__()
        self.plugin = plugin


    def show(self, request,id):
        check_access(request)
        host = id
        device_id = request.params.get('id',None)

        if device_id is None:
            return self.plugin.list_devices(request.context,host)
        else:
            return self.plugin.show_device(request.context,host,device_id)


    def update(self, request,id):
        check_access(request)
        body = request.body

        json_body = json.loads(body)

        host = id
        result ={}
        for key in json_body:
            enable  = json_body.get(key,'enable')
            if enable =='disable':
                enabled = False
            else :
                enabled =  True

            device_result = self.plugin.update_device(request.context, host, key, enabled)

            result[key] = device_result



        return  result



class InterfaceStatisticsController(wsgi.Controller):

    def __init__(self,plugin):
        super(InterfaceStatisticsController,self).__init__()
        self.plugin = plugin

    def show(self, request,id):
        check_access(request)
        return self.plugin.interface_statistics(request.context,id)


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
    def show_orphans(self,host):
        pass

    @abc.abstractmethod
    def delete_orphans(self,host):
        pass

    def list_devices(self, context):
        pass

    @abc.abstractmethod
    def show_device(self, context, id):
        pass

    @abc.abstractmethod
    def update_device(self, context, id, enabled):
        pass
