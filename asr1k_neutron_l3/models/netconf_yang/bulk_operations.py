from oslo_log import log as logging

from asr1k_neutron_l3.common import asr1k_exceptions as exc
from asr1k_neutron_l3.models.connection import ConnectionManager
from asr1k_neutron_l3.models.netconf_yang import xml_utils

LOG = logging.getLogger(__name__)


class BulkOperations(xml_utils.XMLUtils):
    FULL_CONFIG_FILTER = """<native xmlns = "http://cisco.com/ns/yang/Cisco-IOS-XE-native"></native>"""

    @classmethod
    def get_all_from_device_config(cls, device_config_json, context):
        result = []

        json = cls.remove_wrapper(device_config_json, context)

        if json is not None:
            if isinstance(json, list):
                sub_items = []
                for item in json:
                    obj = item.get(cls.get_item_key(context), item)
                    if isinstance(obj, list):
                        sub_items += obj
                    else:
                        sub_items.append(item)
                json = sub_items
            else:
                json = json.get(cls.get_item_key(context), json)

            if isinstance(json, list):
                for item in json:
                    result.append(cls.from_json(item, context))
            else:

                result.append(cls.from_json(json, context))

        return result

    @classmethod
    def get_device_config(cls, context):
        try:
            with ConnectionManager(context=context) as connection:
                rpc_result = connection.get(filter=cls.FULL_CONFIG_FILTER)

                result = cls.to_raw_json(rpc_result.xml)
                return cls._to_plain_json(result)

        except exc.DeviceUnreachable:
            pass
        except Exception as e:
            LOG.exception(e)

    @classmethod
    def get_all_stub_filter(cls, context):
        if not hasattr(cls, "GET_ALL_STUB"):
            raise NotImplementedError("Class {} is missing a GET_ALL_STUB to retrieve all entities"
                                      .format(cls.__name__))

        return cls.GET_ALL_STUB

    @classmethod
    def get_all_stubs_from_device(cls, context):
        """Get all objects as stub  present on a device

        The object will be created with only a minimal set of values, required to identify it
        """
        try:
            with ConnectionManager(context=context) as connection:
                rpc_result = connection.get(filter=cls.get_all_stub_filter(context))

                result = cls.to_raw_json(rpc_result.xml)
                result = cls._to_plain_json(result)
                return cls.get_all_from_device_config(result, context)
        except Exception:
            LOG.exception("Could not fetch entity {} for cleaning".format(cls.__name__))
            return []

    def is_orphan_fwaas(self, all_fwaas_external_policies, all_fwaas_policies, *args, **kwargs):
        return False

    def is_orphan(self, all_router_ids, all_segmentation_ids, all_bd_ids, all_routers_with_external_policies, context):
        """Check if this entity is an orphan"""
        if self.neutron_router_id:
            return self.neutron_router_id not in all_router_ids
        else:
            if self.in_neutron_namespace:
                # e.g. a device without a vrf/router association
                return True

        return False

    def is_reassigned(self, queried):
        return False

    @property
    def neutron_router_id(self):
        return None

    @property
    def in_neutron_namespace(self):
        return False
