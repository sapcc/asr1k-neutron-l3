import json
from oslo_log import log as logging
from asr1k_neutron_l3.models.netconf_yang import xml_utils
from asr1k_neutron_l3.models.connection import ConnectionManager
from asr1k_neutron_l3.common import asr1k_exceptions as exc

LOG = logging.getLogger(__name__)

class BulkOperations(xml_utils.XMLUtils):

    FULL_CONFIG_FILTER = """<native xmlns = "http://cisco.com/ns/yang/Cisco-IOS-XE-native"></native>"""

    @classmethod
    def get_all_from_device_config(cls, device_config_json):
        result = []

        json = cls.remove_wrapper(device_config_json)

        if json is not None:
            if isinstance(json, list):
                sub_items = []
                for item in json:
                    obj = item.get(cls.ITEM_KEY, item)
                    if isinstance(obj,list):
                        sub_items += obj
                    else:
                        sub_items.append(item)
                json=sub_items
            else:
                json = json.get(cls.ITEM_KEY, json)

            if isinstance(json, list):
                for item in json:
                    result.append(cls.from_json(item))
            else:

                result.append(cls.from_json(json))

        return result

    @classmethod
    def get_device_config(cls, context=None):
        try:
            with ConnectionManager(context=context) as connection:
                rpc_result = connection.get(filter=cls.FULL_CONFIG_FILTER)

                result = cls.to_raw_json(rpc_result.xml)
                return cls._to_plain_json(result)

        except exc.DeviceUnreachable:
            pass
        except Exception as e:
            LOG.exception(e)

    @property
    def in_neutron_namespace(self):
        return False