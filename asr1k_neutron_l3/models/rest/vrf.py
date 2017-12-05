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


class VrfConstants(object):
    DEFINITION = "Cisco-IOS-XE-native:definition"

    ID = "id"
    NAME = "name"
    DESCRIPTION = "description"
    ADDRESS_FAMILY = "address-family"
    IPV4 = "ipv4"
    IPV6 = "ipv6"


class VrfDefinition(RestBase):
    LIST_KEY = VrfConstants.DEFINITION

    list_path = "/Cisco-IOS-XE-native:native/vrf"
    item_path = "{}/{}".format(list_path, VrfConstants.DEFINITION)

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'id', 'mandatory': True},
            {'key': 'description'},
            {'key': 'address_families', 'default': [VrfConstants.IPV4]}
        ]

    def __init__(self, context, **kwargs):
        super(VrfDefinition, self).__init__(**kwargs)

        if isinstance(self.address_families, list):
            self.address_families = self.address_families
        else:
            self.address_families = [self.address_families]

    def to_dict(self):

        definition = OrderedDict()
        definition[VrfConstants.NAME] = self.id
        definition[VrfConstants.DESCRIPTION] = self.description
        definition[VrfConstants.ADDRESS_FAMILY] = OrderedDict()
        for address_family in self.address_families:
            definition[VrfConstants.ADDRESS_FAMILY][address_family] = {}

        result = OrderedDict()
        result[VrfConstants.DEFINITION] = definition

        return dict(result)

    def from_json(self, json):
        blob = json.get(VrfConstants.DEFINITION)
        self.description = blob.get(VrfConstants.DESCRIPTION, None)
        self.address_families = blob.get(VrfConstants.ADDRESS_FAMILY, {}).keys()
        return self
