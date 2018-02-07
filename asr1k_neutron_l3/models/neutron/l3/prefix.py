

from asr1k_neutron_l3.models.neutron.l3 import base
from asr1k_neutron_l3.plugins.common import utils

from asr1k_neutron_l3.models.netconf_yang import prefix

class BasePrefix(base.Base):

    def __init__(self,router_id=None,interfaces=None):
        self.vrf = utils.uuid_to_vrf_id(router_id)
        self.interfaces = interfaces
        self.internal_interfaces = interfaces.internal_interfaces
        self.gateway_interface = interfaces.gateway_interface
        self.gateway_address_scope = None

        if self.gateway_interface is not None:
            self.gateway_address_scope = self.gateway_interface.address_scope

    def update(self):
        self.rest_definition.update()

    def delete(self):
        self.rest_definition.delete()


class ExtPrefix(BasePrefix):

    def __init__(self,router_id=None,interfaces=None):
        super(ExtPrefix,self).__init__(router_id=router_id,interfaces=interfaces)
        self.name = 'ext-{}'.format(self.vrf)

        self.rest_definition = prefix.Prefix(name=self.name)

        if self.gateway_interface is not None:
            i = 0
            for subnet in self.gateway_interface.subnets:
                i+=1
                self.rest_definition.add_seq(prefix.PrefixSeq(no=i*10,permit_ip=subnet.get('cidr')))




class SnatPrefix(BasePrefix):
    def __init__(self, router_id=None,interfaces=None):
        super(SnatPrefix,self).__init__(router_id=router_id,interfaces=interfaces)
        self.name = 'snat-{}'.format(self.vrf)

        self.rest_definition = prefix.Prefix(name=self.name)
        i=0
        for interface in interfaces.internal_interfaces:
            i += 1
            if interface.address_scope == self.gateway_address_scope:
                for subnet in interface.subnets:
                    self.rest_definition.add_seq(prefix.PrefixSeq(no=i * 10, permit_ip=subnet.get('cidr')))
                    i += 1