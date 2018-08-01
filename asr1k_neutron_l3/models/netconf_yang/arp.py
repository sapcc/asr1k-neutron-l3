from collections import OrderedDict

from oslo_log import log as logging

from oslo_config import cfg
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair, YANG_TYPE,NC_OPERATION
from asr1k_neutron_l3.models.netconf_yang import xml_utils
from asr1k_neutron_l3.common import utils,asr1k_constants



LOG = logging.getLogger(__name__)


class ARPConstants(object):
    ARP = 'arp'
    VRF = 'vrf'
    VRF_NAME = 'vrf-name'
    ARP_ENTRY = "arp-entry"
    IP = "ip"
    HARDWARE_ADDRESS = "hardware-address"
    ARP_TYPE = "arp-type"
    ALIAS = "alias"

class VrfArpList(NyBase):
    ID_FILTER = """
      <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native" xmlns:ios-arp="http://cisco.com/ns/yang/Cisco-IOS-XE-arp">
        <ios-arp:arp>
          <ios-arp:vrf>
            <ios-arp:vrf-name>{vrf}</ios-arp:vrf-name>
          </ios-arp:vrf>
        </ios-arp:arp>
      </native>
                """

    LIST_KEY = ARPConstants.ARP
    ITEM_KEY = ARPConstants.VRF
    EMPTY_TYPE = []

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'vrf', 'yang-key':'vrf-name','id': True},
            {'key': 'arp_entry','yang-key':'arp-entry', 'type': [ArpEntry] ,  'default': []}
        ]


    @classmethod
    def get_primary_filter(cls,**kwargs):
        return cls.ID_FILTER.format(**{'vrf': kwargs.get('vrf')})



    def __init__(self, **kwargs):
        super(VrfArpList, self).__init__( **kwargs)

    @classmethod
    def remove_wrapper(cls,dict):

        dict = super(VrfArpList, cls)._remove_base_wrapper(dict)
        if dict is None:
            return

        dict = dict.get(cls.LIST_KEY, dict)


        return dict


    def _wrapper_preamble(self,dict):
        result = {}
        result[self.LIST_KEY] = dict
        result[self.LIST_KEY][xml_utils.NS] = xml_utils.NS_CISCO_ARP
        return result



    def to_dict(self):
        arp_list = OrderedDict()
        arp_list[ARPConstants.VRF_NAME]=self.vrf
        arp_list[ARPConstants.ARP_ENTRY]= []
        for arp_entry in sorted(self.arp_entry, key=lambda arp_entry: arp_entry.ip):
            arp_list[ARPConstants.ARP_ENTRY].append(arp_entry.to_single_dict())


        return {ARPConstants.VRF:arp_list}


    def clean_arp(self,context=None):
        arp_list = self._internal_get(context)
        neutron_ids = []
        neutron_ips = {}

        for arp in self.arp_entry:
            neutron_ids.append(arp.ip)
            neutron_ips[arp.ip] = arp.hardware_address
        if arp_list is not None:
            for arp_entry in arp_list.arp_entry:
                arp_entry.vrf = self.vrf
                if not arp_entry.ip in neutron_ids:
                    LOG.debug('Removing unknown arp {} > {} from vrf {}'.format(arp_entry.ip,arp_entry.hardware_address, self.vrf))
                    arp_entry.delete()
                hardware_address = neutron_ips.get(arp_entry.ip)
                if hardware_address is not None and hardware_address != arp_entry.hardware_address:
                    LOG.debug('Removing invalid arp {} > {} from vrf {}'.format(arp_entry.ip,arp_entry.hardware_address, self.vrf))
                    arp_entry.delete()
    @execute_on_pair()
    def update(self,context=None):
        self.clean_arp(context)
        if len(self.arp_entry) > 0 :
            result = super(VrfArpList, self)._update(context=context, method=NC_OPERATION.PUT)
            return result


    @execute_on_pair()
    def delete(self,context=None):
        self.clean_arp(context)
        #result = super(VrfArpList, self)._delete(context=context)

        #return result



class ArpEntry(NyBase):
    ID_FILTER = """
      <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native" xmlns:ios-arp="http://cisco.com/ns/yang/Cisco-IOS-XE-arp">
        <ios-arp:arp>
          <ios-arp:vrf>
            <ios-arp:vrf-name>{vrf}</ios-arp:vrf-name>
            <ios-arp:arp-entry>
              <ios-arp:ip>{ip}</ios-arp:ip>
            </ios-arp:arp-entry>
          </ios-arp:vrf>
        </ios-arp:arp>
      </native>
                """


    LIST_KEY = ARPConstants.VRF
    ITEM_KEY = ARPConstants.ARP_ENTRY



    @classmethod
    def __parameters__(cls):
        return [
            {"key": "vrf",'primary-key':True},
            {"key": "ip", 'mandatory': True,'id':True},
            {'key': 'hardware_address','yang-key': 'hardware-address'},
            {'key': 'arp_type','yang-key': 'arp-type'},
            {'key': 'alias','default':True,'yang-type':YANG_TYPE.EMPTY}


        ]

    @classmethod
    def get_primary_filter(cls,**kwargs):
        return cls.ID_FILTER.format(**{'vrf':kwargs.get('vrf'),'ip': kwargs.get('ip')})

    @classmethod
    @execute_on_pair(return_raw=True)
    def get(cls,vrf,ip, context=None):
        return super(ArpEntry, cls)._get(vrf=vrf,ip=ip, context=context)


    @classmethod
    @execute_on_pair(return_raw=True)
    def exists(cls, vrf,ip, context=None):
        return super(ArpEntry, cls)._exists(ip=ip, vrf=vrf, context=context)


    @classmethod
    def remove_wrapper(cls,dict):

        dict = super(ArpEntry, cls)._remove_base_wrapper(dict)
        if dict is  None:
            return


        dict = dict.get(ARPConstants.ARP, dict)
        dict = dict.get(cls.LIST_KEY, dict)

        return dict

    def orphan_info(self):
        return {self.__class__.__name__:{'ip':self.ip,'hardware_address':self.hardware_address,'vrf':self.vrf}}

    def _wrapper_preamble(self,single_dict):
        result = OrderedDict()
        result[self.LIST_KEY] =  single_dict

        result[xml_utils.NS] = xml_utils.NS_CISCO_ARP
        result = {ARPConstants.ARP: result}

        return dict(result)

    def __init__(self, **kwargs):
        super(ArpEntry, self).__init__(**kwargs)
        if kwargs.get('vrf') is not None:
            self.vrf = kwargs.get('vrf')
        self.arp_type = 'ARPA'
        self.alias = True

    @property
    def neutron_router_id(self):
        if self.vrf is not None:
            return utils.vrf_id_to_uuid(self.vrf)

    def to_dict(self):
        result = OrderedDict()
        result[ARPConstants.VRF_NAME] = self.vrf
        result[ARPConstants.ARP_ENTRY] = []
        result[ARPConstants.ARP_ENTRY].append(self.to_single_dict())

        return result

    def to_single_dict(self):
        entry = OrderedDict()
        entry[ARPConstants.IP] = self.ip
        entry[ARPConstants.HARDWARE_ADDRESS] = self.hardware_address
        entry[ARPConstants.ARP_TYPE] = self.arp_type

        if self.alias:
            entry[ARPConstants.ALIAS] = ""

        return entry

    def to_delete_dict(self):
        entry = OrderedDict()
        entry[ARPConstants.IP] = self.ip

        result = OrderedDict()
        result[ARPConstants.VRF_NAME] = self.vrf
        result[ARPConstants.ARP_ENTRY] = []
        result[ARPConstants.ARP_ENTRY].append(entry)



        return result


