from collections import OrderedDict
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair, retry_on_failure
from asr1k_neutron_l3.models.netconf import l3_interface as nc_l3_interface

class L3Constants(object):
    INTERFACE = "interface"
    BDI_INTERFACE = "BDI"

    ID = "id"
    NAME = "name"
    DESCRIPTION = "description"
    MAC_ADDRESS = "mac-address"
    MTU = "mtu"
    IP = "ip"
    ADDRESS = "address"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    MASK = "mask"
    VRF = "vrf"
    FORWARDING = "forwarding"
    SHUTDOWN = "shutdown"
    NAT = "nat"
    NAT_MODE_INSIDE = "inside"
    NAT_MODE_OUTSIDE = "outside"


class BDIInterface(NyBase):

    ID_FILTER = """
                <native>
                    <interface>
                        <BDI>
                            <name>{id}</name>
                        </BDI>
                    </interface>
                </native>            
             """

    LIST_KEY = L3Constants.INTERFACE
    ITEM_KEY = L3Constants.BDI_INTERFACE


    @classmethod
    def __parameters__(cls):
        # secondary IPs will be validated in NAT
        # NAT mode should be validated when supported in yang models - no point using netconf for now
        return [
            {"key": "name", "id": True},
            {'key': 'description'},
            {'key': 'mac_address'},
            {'key': 'mtu', 'default': 1500},
            {'key': 'vrf','yang-path':'vrf','yang-key':"forwarding"},
            {'key': 'ip_address','yang-path':'ip/address','yang-key':"primary",'type':BDIPrimaryIpAddress},
            {'key': 'secondary_ip_addresses','yang-path':'ip/address','yang-key':"secondary",'type':BDISecondaryIpAddress, 'default': [], 'validate':False},
            {'key': 'nat_mode', 'default': 'outside', 'validate':False},
            {'key': 'redundancy_group'},
            {'key': 'shutdown','default':False},

        ]


    def __init__(self, **kwargs):
        super(BDIInterface, self).__init__(**kwargs)
        self.ncc = nc_l3_interface.BDIInterface(self)

    def to_dict(self):
        bdi = OrderedDict()
        bdi[L3Constants.NAME] = self.name
        bdi[L3Constants.DESCRIPTION] = self.description
        bdi[L3Constants.MAC_ADDRESS] = self.mac_address
        bdi[L3Constants.MTU] = self.mtu
        if self.shutdown:
            bdi[L3Constants.SHUTDOWN] = ''

        ip = OrderedDict()
        if self.ip_address is not None:
            ip[L3Constants.ADDRESS] = OrderedDict()
            ip[L3Constants.ADDRESS][L3Constants.PRIMARY] = OrderedDict()
            ip[L3Constants.ADDRESS][L3Constants.PRIMARY][L3Constants.ADDRESS] = self.ip_address.address
            ip[L3Constants.ADDRESS][L3Constants.PRIMARY][L3Constants.MASK] = self.ip_address.mask

        vrf = OrderedDict()
        vrf[L3Constants.FORWARDING] = self.vrf

        bdi[L3Constants.IP] = ip
        bdi[L3Constants.VRF] = vrf

        result = OrderedDict()
        result[L3Constants.BDI_INTERFACE] = bdi

        return dict(result)

    #TODO : remove when nat is support in BDI yang model
    #TODO - the ncc update ins not propagated to both nodes
    @execute_on_pair()
    def update(self,context=None):
        result = super(BDIInterface, self)._update(context=context)
        self.ncc.update(context)
        return result

    @execute_on_pair()
    def create(self,context=None):
        result = super(BDIInterface, self)._create(context=context)
        self.ncc.update(context)
        return result

    @execute_on_pair()
    def disable_nat(self, context=None):
        self.ncc.disable_nat(context)

    @execute_on_pair()
    def enable_nat(self, context=None):
        self.ncc.enable_nat(context)

class BDISecondaryIpAddress(NyBase):
    ITEM_KEY = L3Constants.SECONDARY
    LIST_KEY = L3Constants.ADDRESS

    ID_FILTER = """
                  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                    <interface>
                      <BDI>
                        <name>{bridge_domain}</name>
                        <ip>
                          <address>
                            <secondary>
                                <address>{id}</address>
                            </secondary>
                          </address>
                        </ip>
                      </BDI>
                    </interface>
                  </native>    
                """

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'bridge_domain','validate': False},
            {"key": 'address', 'id': True},
            {'key': 'mask'},
            {'key': 'secondary','default':True}

        ]


    @classmethod
    def remove_wrapper(cls,dict):
        dict = super(BDISecondaryIpAddress, cls)._remove_base_wrapper(dict)
        if dict is None:
            return
        dict = dict.get(L3Constants.INTERFACE,dict)
        dict = dict.get(L3Constants.BDI_INTERFACE,dict)
        dict = dict.get(L3Constants.IP, dict)
        dict = dict.get(cls.LIST_KEY, None)
        return dict

    def _wrapper_preamble(self,dict):
        result = {}
        result[self.LIST_KEY] = dict
        a = OrderedDict()
        a[L3Constants.NAME] = self.bridge_domain
        a[L3Constants.IP] = result
        result = OrderedDict({L3Constants.BDI_INTERFACE: a})
        result = OrderedDict({L3Constants.INTERFACE: result})
        return result

    @classmethod
    def get_primary_filter(cls,**kwargs):
        return cls.ID_FILTER.format(**{'id': kwargs.get('id'),'bridge_domain':kwargs.get('bridge_domain')})


    @classmethod
    @execute_on_pair(return_raw=True)
    def get(cls,bridge_domain,id, context=None):
        return super(BDISecondaryIpAddress, cls)._get(id=id, bridge_domain=bridge_domain,context=context)

    @classmethod
    @execute_on_pair(return_raw=True)
    def exists(cls, bridge_domain,id, context=None):
        return super(BDISecondaryIpAddress, cls)._exists(id=id, bridge_domain=bridge_domain, context=context)



    def __init__(self, **kwargs):
        super(BDISecondaryIpAddress, self).__init__(**kwargs)
        self.bridge_domain = kwargs.get('bridge_domain')

    def to_dict(self):
        ip = OrderedDict()
        secondary = OrderedDict()
        secondary[L3Constants.ADDRESS] = self.address
        secondary[L3Constants.MASK] = self.mask
        secondary['secondary'] = ''
        ip[L3Constants.SECONDARY] = secondary

        return ip

class BDIPrimaryIpAddress(NyBase):
    ITEM_KEY = L3Constants.PRIMARY
    LIST_KEY = L3Constants.ADDRESS

    @classmethod
    def __parameters__(cls):
        return [
            {"key": 'address', 'id': True},
            {'key': 'mask'},

        ]



    def __init__(self, **kwargs):


        super(BDIPrimaryIpAddress, self).__init__(**kwargs)
        self.bridge_domain = kwargs.get('bridge_domain')


    def to_dict(self):
        ip = OrderedDict()
        primary = OrderedDict()
        primary[L3Constants.ADDRESS] = self.address
        primary[L3Constants.MASK] = self.mask
        ip[L3Constants.PRIMARY] = primary

        return ip