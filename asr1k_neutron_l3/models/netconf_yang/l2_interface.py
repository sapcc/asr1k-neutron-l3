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
from asr1k_neutron_l3.models.netconf_yang.ny_base import NC_OPERATION, NyBase, execute_on_pair
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


class BridgeDomain(NyBase):
    pass


class ServiceInstance(NyBase):
    PORT_CHANNEL = 0
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

    LIST_KEY = L2Constants.SERVICE
    ITEM_KEY = L2Constants.SERVICE_INSTANCE

    @classmethod
    def __parameters__(cls):
        return [
            {"key": "port_channel", 'validate': False, 'primary_key': True},
            {"key": "id", "mandatory": True, 'default': 0},
            {"key": "description"},
            {"key": "bridge_domain", 'yang-path': 'bridge-domain', 'yang-key': 'bridge-id'},
            {"key": "dot1q", 'yang-path': 'encapsulation/dot1q', 'yang-key': 'id'},
            {"key": "second_dot1q", 'yang-path': 'encapsulation/dot1q', 'yang-key': 'second-dot1q'},
            {"key": "way", 'yang-path': 'rewrite/ingress/tag/pop'},
            {"key": "mode", 'yang-path': 'rewrite/ingress/tag/pop'}
        ]

    @classmethod
    def get_primary_filter(cls, **kwargs):
        return cls.ID_FILTER.format(id=kwargs.get('id'), port_channel=cls.PORT_CHANNEL)

    @classmethod
    @execute_on_pair(return_raw=True)
    def get(cls, id, context):
        return super(ServiceInstance, cls)._get(id=id, port_channel=cls.PORT_CHANNEL, context=context)

    @classmethod
    @execute_on_pair(return_raw=True)
    def exists(cls, id, context):
        return super(ServiceInstance, cls)._exists(id=id, port_channel=cls.PORT_CHANNEL, context=context)

    @classmethod
    def remove_wrapper(cls, json):
        json = super(ServiceInstance, cls)._remove_base_wrapper(json)
        if json is None:
            return
        json = json.get(L2Constants.INTERFACE, json)
        json = json.get(L2Constants.PORT_CHANNEL, json)

        if isinstance(json, list):
            result = []
            for pc in json:
                if pc.get("name") == cls.PORT_CHANNEL:
                    service = pc.get(L2Constants.SERVICE, pc)
                    if not isinstance(service.get(L2Constants.SERVICE_INSTANCE, None), list):
                        if service.get(L2Constants.SERVICE_INSTANCE, None) is not None:
                            service[L2Constants.SERVICE_INSTANCE] = [service.get(L2Constants.SERVICE_INSTANCE)]
                    result.append(service)

            json = result
        else:
            json = json.get(L2Constants.SERVICE, json)
        return json

    def orphan_info(self):
        return {self.__class__.__name__: {'description': self.description, 'service_instance': self.id,
                                          'port_channel': self.PORT_CHANNEL, 'bridge_domain': self.bridge_domain}}

    def _wrapper_preamble(self, dict):
        result = {}
        dict[xml_utils.NS] = xml_utils.NS_CISCO_ETHERNET
        result[self.LIST_KEY] = dict
        result[L2Constants.NAME] = self.PORT_CHANNEL
        result = {L2Constants.PORT_CHANNEL: result}
        result = {L2Constants.INTERFACE: result}
        return result

    def __init__(self, **kwargs):
        kwargs['port_channel'] = self.PORT_CHANNEL
        super(ServiceInstance, self).__init__(**kwargs)

        if self.id == 'None' or self.id is None:
            self.id = -1

    def to_dict(self, context):
        dot1q = dict(OrderedDict())

        dot1q[L2Constants.ID] = [str(self.dot1q)]
        if self.second_dot1q is not None:
            dot1q[L2Constants.SECOND_DOT1Q] = [str(self.second_dot1q)]

        bridge_domain = OrderedDict()
        bridge_domain[L2Constants.BRIDGE_ID] = self.bridge_domain

        rewrite = OrderedDict()
        rewrite[L2Constants.INGRESS] = OrderedDict()

        rewrite[L2Constants.INGRESS][L2Constants.TAG] = OrderedDict()
        if self.way is not None and self.mode is not None:
            rewrite[L2Constants.INGRESS][L2Constants.TAG][L2Constants.POP] = OrderedDict()
            rewrite[L2Constants.INGRESS][L2Constants.TAG][L2Constants.POP][
                L2Constants.REWRITE_WAY] = self.way
            rewrite[L2Constants.INGRESS][L2Constants.TAG][L2Constants.POP][L2Constants.REWRITE_MODE] = self.mode

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

    def to_delete_dict(self, context):
        instance = OrderedDict()
        instance[L2Constants.ID] = "{}".format(str(self.id))
        instance[L2Constants.ETHERNET] = ''

        result = OrderedDict()
        result[L2Constants.SERVICE_INSTANCE] = instance

        return dict(result)

    @execute_on_pair()
    def update(self, context):
        result = super(ServiceInstance, self)._update(context=context, method=NC_OPERATION.PUT)


class ExternalInterface(ServiceInstance):
    PORT_CHANNEL = "1"

    def __init__(self, **kwargs):
        kwargs['bridge_domain'] = kwargs.get('id')
        kwargs['dot1q'] = kwargs.get('id')
        super(ExternalInterface, self).__init__(**kwargs)


class LoopbackExternalInterface(ServiceInstance):
    PORT_CHANNEL = "2"

    def __init__(self, **kwargs):
        kwargs['bridge_domain'] = kwargs.get('dot1q')
        kwargs['dot1q'] = kwargs.get('dot1q')
        super(LoopbackExternalInterface, self).__init__(**kwargs)


class LoopbackInternalInterface(ServiceInstance):
    PORT_CHANNEL = "3"

    def __init__(self, **kwargs):
        super(LoopbackInternalInterface, self).__init__(**kwargs)
