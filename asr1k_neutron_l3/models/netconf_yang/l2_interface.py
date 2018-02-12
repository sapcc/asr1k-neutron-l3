# Copyright 2017 SAP SE
#
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from collections import OrderedDict

from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair
from asr1k_neutron_l3.models.netconf_yang import xml_utils

class L2Constants(object):
    INTERFACE = 'interface'
    PORT_CHANNEL = 'Port-channel'
    SERVICE = "service"
    SERVICE_INSTANCE = "instance"

    ID = "id"
    NAME = "name"
    DESCRIPTION = "description"

    ETHERNET = "ethernet"
    ENCAPSULATION = 'encapsulation'
    BRIDGE_DOMAIN = "bridge-domain"
    BRIDGE_ID = "bridge-id"
    DOT1Q = "dot1q"
    SECOND_DOT1Q = "second-dot1q"
    INGRESS = "ingress"
    TAG = "tag"
    POP = "pop"
    REWRITE = "rewrite"
    REWRITE_WAY = "way"
    REWRITE_MODE = "mode"
    SYMMETRIC = "symmetric"

class BridgeDomain(NyBase):
    pass


class ServiceInstance(NyBase):

    ID_FILTER = """
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native" xmlns:ios-eth="http://cisco.com/ns/yang/Cisco-IOS-XE-ethernet">
                <interface>
                  <Port-channel>
                    <name>{port_channel}</name>
                    <ios-eth:service>
                      <ios-eth:instance>
                        <id>{id}</id>
                      </ios-eth:instance>
                    </ios-eth:service>
                  </Port-channel>
                </interface>
              </native>        
             """


    REWRITE_INGRESS_TAG_POP_WAY = 2

    LIST_KEY = L2Constants.SERVICE
    ITEM_KEY = L2Constants.SERVICE_INSTANCE


    @classmethod
    def __parameters__(cls):
        return [
            {"key": "port_channel", 'validate':False},
            {"key": "id", "mandatory": True},
            {"key": "description"},
            {"key": "bridge_domain",'yang-path':'bridge-domain','yang-key':'bridge-id'},
            {"key": "dot1q",'yang-path':'encapsulation/dot1q','yang-key':'id'},
            {"key": "second_dot1q",'yang-path':'encapsulation/dot1q','yang-key':'second-dot1q'}
        ]

    @classmethod
    def get_primary_filter(cls,**kwargs):
        return cls.ID_FILTER.format(**{'id': kwargs.get('id'),'port_channel':kwargs.get('port_channel')})

    @classmethod
    @execute_on_pair(return_raw=True)
    def get(cls,port_channel,id, context=None):
        return super(ServiceInstance, cls)._get(id=id, port_channel=port_channel,context=context)

    @classmethod
    @execute_on_pair(return_raw=True)
    def exists(cls, port_channel,id, context=None):
        return super(ServiceInstance, cls)._exists(id=id, port_channel=port_channel, context=context)



    @classmethod
    def remove_wrapper(cls,dict):
        dict = super(ServiceInstance, cls)._remove_base_wrapper(dict)
        if dict is  None:
            return
        dict = dict.get(L2Constants.INTERFACE,dict)
        dict = dict.get(L2Constants.PORT_CHANNEL,dict)
        dict = dict.get(L2Constants.SERVICE, dict)
        return dict

    def _wrapper_preamble(self,dict):
        result = {}
        dict [xml_utils.NS] = xml_utils.NS_CISCO_ETHERNET
        result[self.LIST_KEY] = dict
        result[L2Constants.NAME] = self.port_channel
        result = {L2Constants.PORT_CHANNEL:result}
        result = {L2Constants.INTERFACE: result}
        return result


    def __init__(self, **kwargs):
        super(ServiceInstance, self).__init__(**kwargs)

    def to_dict(self):

        dot1q = dict(OrderedDict())

        dot1q[L2Constants.ID] = [str(self.dot1q)]
        if self.second_dot1q is not None:
            dot1q[L2Constants.SECOND_DOT1Q] = [str(self.second_dot1q)]

        bridge_domain = OrderedDict()
        bridge_domain[L2Constants.BRIDGE_ID] = self.bridge_domain

        rewrite = OrderedDict()
        rewrite[L2Constants.INGRESS] = OrderedDict()
        rewrite[L2Constants.INGRESS][L2Constants.TAG] = OrderedDict()
        rewrite[L2Constants.INGRESS][L2Constants.TAG][L2Constants.POP] = OrderedDict()
        rewrite[L2Constants.INGRESS][L2Constants.TAG][L2Constants.POP][
            L2Constants.REWRITE_WAY] = self.REWRITE_INGRESS_TAG_POP_WAY
        rewrite[L2Constants.INGRESS][L2Constants.TAG][L2Constants.POP][L2Constants.REWRITE_MODE] = L2Constants.SYMMETRIC

        instance = OrderedDict()
        instance[L2Constants.ID] = "{}".format(str(self.id))
        instance[L2Constants.ETHERNET] = ''
        instance[L2Constants.DESCRIPTION] = "{}".format(self.description)

        instance[L2Constants.ENCAPSULATION] = OrderedDict()
        instance[L2Constants.ENCAPSULATION][L2Constants.DOT1Q] = dot1q
        instance[L2Constants.BRIDGE_DOMAIN] = bridge_domain
        instance[L2Constants.REWRITE] = rewrite

        result = OrderedDict()
        result[L2Constants.SERVICE_INSTANCE] = instance

        return dict(result)



class ExternalInterface(ServiceInstance):
    REWRITE_INGRESS_TAG_POP_WAY = 1

    def __init__(self, **kwargs):

        kwargs['bridge_domain'] = kwargs.get('id')
        kwargs['dot1q'] = kwargs.get('id')

        super(ExternalInterface, self).__init__(**kwargs)

class LoopbackExternalInterface(ServiceInstance):

    def __init__(self, **kwargs):
        kwargs['bridge_domain'] = kwargs.get('dot1q')
        kwargs['dot1q'] = kwargs.get('dot1q')

        super(LoopbackExternalInterface, self).__init__(**kwargs)


class LoopbackInternalInterface(ServiceInstance):

    def __init__(self, **kwargs):
        super(LoopbackInternalInterface, self).__init__(**kwargs)