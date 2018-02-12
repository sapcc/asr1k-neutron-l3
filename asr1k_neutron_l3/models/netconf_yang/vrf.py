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

from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase


class VrfConstants(object):
    VRF = 'vrf'
    DEFINITION = "definition"

    ID = "id"
    NAME = "name"
    DESCRIPTION = "description"
    ADDRESS_FAMILY = "address-family"
    EXPORT = "export"
    MAP = "map"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    RD = "rd"


class VrfDefinition(NyBase):
    ID_FILTER = """
                <native>
                    <vrf>
                        <definition>
                            <name>{id}</name>
                        </definition>
                    </vrf>
                </native>            
             """

    LIST_KEY = VrfConstants.VRF
    ITEM_KEY = VrfConstants.DEFINITION

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'name', 'id': True},
            {'key': 'description'},
            {'key': 'address_family', 'default': {VrfConstants.IPV4:{}}},
            {'key': 'rd'}
        ]

    def __init__(self,**kwargs):
        super(VrfDefinition, self).__init__(**kwargs)

        if isinstance(self.address_family, dict):
            self.address_family = self.address_family
        else:
            self.address_family = {self.address_family:{}}



    def to_dict(self):

        definition = OrderedDict()
        definition[VrfConstants.NAME] = self.name
        if bool(self.description):
            definition[VrfConstants.DESCRIPTION] = self.description
        definition[VrfConstants.ADDRESS_FAMILY] = OrderedDict()
        for address_family in self.address_family.keys():
            definition[VrfConstants.ADDRESS_FAMILY][address_family] = {}
            definition[VrfConstants.ADDRESS_FAMILY][address_family] = {VrfConstants.EXPORT:{VrfConstants.MAP:'exp-{}'.format(self.name)}}

        if self.rd is not None:
            definition[VrfConstants.RD] = self.rd


        result = OrderedDict()
        result[VrfConstants.DEFINITION] = definition

        return dict(result)

