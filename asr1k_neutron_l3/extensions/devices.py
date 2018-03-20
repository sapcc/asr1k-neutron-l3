import abc

from neutron._i18n import _
from neutron.api import extensions
from neutron.api.v2 import attributes as attr
from neutron.api.v2 import base
from neutron.plugins.common import constants as svc_constants
from neutron import manager
from neutron import wsgi
import webob.exc
from oslo_log import log as logging
from neutron.common import exceptions
from oslo_serialization import jsonutils


from neutron import api

LOG = logging.getLogger(__name__)

ASR1K_DEVICES_ALIAS = 'asr1k_devices'


RESOURCE_NAME = 'device'
RESOURCE_COLLECTION = 'devices'

MEMBER_ACTIONS = {'validate':'GET','sync':'PUT','interface_statistics':'GET','teardown':'DELETE'}

RESOURCE_ATTRIBUTE_MAP = {

    RESOURCE_COLLECTION: {
        'id': {'allow_post': True, 'allow_put': True,
               'validate': {'type:string_or_none': None}, 'is_visible': True,
               'default': None, 'primary_key': True},
    }

}


class Devices(extensions.ExtensionDescriptor):

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

        plural_mappings = {'devices': 'device'}
        attr.PLURALS.update(plural_mappings)

        plugin = manager.NeutronManager.get_service_plugins().get(svc_constants.L3_ROUTER_NAT)
        params = RESOURCE_ATTRIBUTE_MAP.get(RESOURCE_COLLECTION)
        controller = base.create_resource(RESOURCE_COLLECTION,
                                          RESOURCE_NAME,
                                          plugin, params,
                                          member_actions=MEMBER_ACTIONS.keys())

        ex = extensions.ResourceExtension(RESOURCE_COLLECTION,
                                          controller, member_actions=MEMBER_ACTIONS)
        return [ex]

    def get_extended_resources(self, version):
        return {}




class DevicePluginBase(object):

    @abc.abstractmethod
    def get_device(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def validate(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def sync(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def interface_statistics(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def teardown(self, context, id, fields=None):
        pass