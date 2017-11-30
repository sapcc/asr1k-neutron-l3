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

from asr1k_neutron_l3.models.rest.rest_base import RestBase


class L2Constants(object):
    SERVICE_INSTANCE = "Cisco-IOS-XE-ethernet:instance"

    ID = "id"
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


class ServiceInstance(RestBase):
    REWRITE_INGRESS_TAG_POP_WAY = 2

    list_path = "/Cisco-IOS-XE-native:native/interface/Port-channel={port_channel}/service"
    item_path = list_path + "/instance"

    @classmethod
    def get(cls, context, port_channel, id):
        service = cls(port_channel, id)
        service.context = context
        return service._get(context)

    def __parameters__(self):
        return [
            {"key": "port_channel", "mandatory": True},
            {"key": "id", "mandatory": True},
            {"key": "description"},
            {"key": "bridge_domain"},
            {"key": "dot1q"},
            {"key": "second_dot1q"}
        ]

    def __init__(self, context, **kwargs):
        super(ServiceInstance, self).__init__(context, **kwargs)

        self.list_path = ServiceInstance.list_path.format(**{'port_channel': self.port_channel})
        self.item_path = ServiceInstance.item_path.format(**{'port_channel': self.port_channel})

    def to_dict(self):

        dot1q = dict(OrderedDict())

        dot1q[L2Constants.ID] = self.dot1q
        if self.second_dot1q is not None:
            dot1q[L2Constants.SECOND_DOT1Q] = self.second_dot1q

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
        instance[L2Constants.ETHERNET] = "[null]"
        instance[L2Constants.DESCRIPTION] = "{}".format(self.description)

        instance[L2Constants.ENCAPSULATION] = OrderedDict()
        instance[L2Constants.ENCAPSULATION][L2Constants.DOT1Q] = dot1q
        instance[L2Constants.BRIDGE_DOMAIN] = bridge_domain
        instance[L2Constants.REWRITE] = rewrite

        result = OrderedDict()
        result[L2Constants.SERVICE_INSTANCE] = instance

        return dict(result)

    def from_json(self, json):
        blob = json.get(L2Constants.SERVICE_INSTANCE, None)

        self.description = blob.get(L2Constants.DESCRIPTION, None)

        dot1q = blob.get(L2Constants.ENCAPSULATION, {}).get(L2Constants.DOT1Q, {}).get(L2Constants.ID, [])
        if len(dot1q) > 0:
            self.dot1q = dot1q.pop()

        second_dot1q = blob.get(L2Constants.ENCAPSULATION, {}).get(L2Constants.DOT1Q, {}).get(L2Constants.SECOND_DOT1Q,
                                                                                              [])
        if len(second_dot1q) > 0:
            self.second_dot1q = second_dot1q.pop()

        self.bridge_domain = blob.get(L2Constants.BRIDGE_DOMAIN, {}).get(L2Constants.BRIDGE_ID, None)

        return self


class ExternalInterface(ServiceInstance):
    REWRITE_INGRESS_TAG_POP_WAY = 1

    def __init__(self, context, port_channel, id, description=None):
        super(ExternalInterface, self).__init__(context, port_channel=port_channel, id=id, description=description,
                                                bridge_domain=id, dot1q=id)


class LoopbackExternalInterface(ServiceInstance):

    def __init__(self, context, port_channel, id, description=None, dot1q=None, second_dot1q=None):
        super(LoopbackExternalInterface, self).__init__(context, port_channel=port_channel, id=id,
                                                        description=description, bridge_domain=dot1q, dot1q=dot1q,
                                                        second_dot1q=second_dot1q)


class LoopbackInternalInterface(ServiceInstance):

    def __init__(self, context, port_channel, id, description=None, bridge_domain=None, dot1q=None, second_dot1q=None):
        super(LoopbackInternalInterface, self).__init__(context, port_channel=port_channel, id=id,
                                                        description=description, bridge_domain=bridge_domain,
                                                        dot1q=dot1q, second_dot1q=second_dot1q)
