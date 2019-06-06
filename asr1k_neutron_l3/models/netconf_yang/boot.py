from collections import OrderedDict

from oslo_log import log as logging
from oslo_config import cfg
from asr1k_neutron_l3.common import asr1k_exceptions as exc
from asr1k_neutron_l3.models.connection import ConnectionManager
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair, YANG_TYPE, NC_OPERATION

LOG = logging.getLogger(__name__)


class BootConstants(object):
    BOOT = 'boot'
    SYSTEM = 'system'
    FLASH = 'flash'
    FLASH_LIST = 'flash-list'
    FLASH_LEAF = 'flash-leaf'


class VersionCheck(object):

    __instance = None

    def __new__(cls):
        if VersionCheck.__instance is None:
            VersionCheck.__instance = object.__new__(cls)

        return VersionCheck.__instance

    @property
    def versions(self):
        if not hasattr(self, '_versions') or self._versions is None:
            self._versions = self.get_boot_flash()
        return self._versions

    def get_boot_flash(self):
        result ={}
        versions = self._get_boot_flash()

        for key,value in versions.results.items():
            result[key] = value

        return result

    @execute_on_pair()
    def _get_boot_flash(self, context=None):
        try:

            flash_list = BootFlashList._get(context = context)



            if flash_list.flash_leaf is not None and len(flash_list.flash_leaf) > 0:
                return flash_list.flash_leaf[0][BootConstants.FLASH_LEAF]

        except BaseException as e:
            LOG.exception(e)

        return  None

    def latest(self,context=None):
        return self.version(context=context) ==  cfg.CONF.asr1k.latest_firmware


    def version(self,context=None):
        if context is None:
            #raise exc.FirmwareContextUnknown()
            LOG.warning("Can't determine firmware version, context is None")
            return "unknown"
        else:
            version = self.versions[context.host]

            if version is None:
                raise exc.DeviceUnreachable(host=context.host)

            return version



class BootFlashList(NyBase):
    ID_FILTER = """
      <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
        <boot/>
      </native>
                """

    LIST_KEY = BootConstants.FLASH
    ITEM_KEY = BootConstants.FLASH_LIST


    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'flash_leaf', 'yang-key': 'flash-leaf',type:[str]}

        ]

    @classmethod
    def get_primary_filter(cls, **kwargs):
        return cls.ID_FILTER

    def __init__(self, **kwargs):
        super(BootFlashList, self).__init__(**kwargs)

    @classmethod
    def remove_wrapper(cls, dict):

        dict = super(BootFlashList, cls)._remove_base_wrapper(dict)
        if dict is None:
            return
        dict = dict.get(BootConstants.BOOT, dict)
        dict = dict.get(BootConstants.SYSTEM, dict)
        dict = dict.get(cls.LIST_KEY, dict)

        return dict

    @execute_on_pair
    def delete(self, context=None, method=NC_OPERATION.DELETE):
        raise NotImplementedError

    @execute_on_pair
    def update(self, context=None, method=NC_OPERATION.PATCH, json=None, postflight=False):
        raise NotImplementedError



    def to_dict(self, context=None):
        flash_list = OrderedDict()

        flash_list[BootConstants.SYSTEM] = OrderedDict()
        flash_list[BootConstants.FLASH] = OrderedDict()
        flash_list[BootConstants.FLASH_LIST] = []

        for flash_entry in self.flash_leaf:
            flash_list[BootConstants.FLASH_LIST].append(flash_entry)

        return {BootConstants.BOOT: flash_list}



