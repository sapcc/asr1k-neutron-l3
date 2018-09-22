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


from oslo_log import log as logging
from oslo_config import cfg
from collections import OrderedDict
from asr1k_neutron_l3.common import utils, asr1k_constants
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase,Requeable, NC_OPERATION,execute_on_pair
from asr1k_neutron_l3.models.netconf_yang.nat import InterfaceDynamicNat
from asr1k_neutron_l3.models.netconf_yang.l3_interface import BDIInterface
from asr1k_neutron_l3.common import asr1k_exceptions as exc

LOG = logging.getLogger(__name__)

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


class VrfDefinition(NyBase,Requeable):
    ID_FILTER = """
                <native>
                    <vrf>
                        <definition>
                            <name>{id}</name>
                        </definition>
                    </vrf>
                </native>            
             """


    RD_FILTER = """
                <native>
                    <vrf>
                        <definition>
                            <rd>{rd}</rd>
                        </definition>
                    </vrf>
                </native>            
             """


    ALL_FILTER = """
                <native>
                    <vrf>
                        <definition>
                        </definition>
                    </vrf>
                </native>            
             """


    LIST_KEY = VrfConstants.VRF
    ITEM_KEY = VrfConstants.DEFINITION

    def requeable_operations(self):
        return ['create','update']

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

        self.enable_bgp = kwargs.get('enable_bgp',False)

    @property
    def neutron_router_id(self):
        if self.name is not None:
            return utils.vrf_id_to_uuid(self.name)

    def to_dict(self):

        definition = OrderedDict()
        definition[VrfConstants.NAME] = self.name
        if bool(self.description):
            definition[VrfConstants.DESCRIPTION] = self.description
        definition[VrfConstants.ADDRESS_FAMILY] = OrderedDict()

        # Idealliy we would not have this, but the Yang API is very unpleasant in case you try to remove things
        # hopefully

        definition[VrfConstants.RD] = self.rd
        for address_family in self.address_family.keys():
            definition[VrfConstants.ADDRESS_FAMILY][address_family] = {VrfConstants.EXPORT:{VrfConstants.MAP:'exp-{}'.format(self.name)}}


        # if self.enable_bgp:
        #     definition[VrfConstants.RD] = self.rd
        #     for address_family in self.address_family.keys():
        #         definition[VrfConstants.ADDRESS_FAMILY][address_family] = {VrfConstants.EXPORT:{VrfConstants.MAP:'exp-{}'.format(self.name)}}
        # else:
        #
        #     for address_family in self.address_family.keys():
        #          definition[VrfConstants.ADDRESS_FAMILY][address_family] = {}


        result = OrderedDict()
        result[VrfConstants.DEFINITION] = definition
        return dict(result)

    def to_delete_dict(self):
        definition = OrderedDict()
        definition[VrfConstants.NAME] = self.name
        result = OrderedDict()
        result[VrfConstants.DEFINITION] = definition

        return dict(result)

    @execute_on_pair()
    def update(self,context=None):

        return super(VrfDefinition, self)._update(context=context,method=NC_OPERATION.PUT)


    def preflight(self, context):

        if self.__class__.__name__ in context.preflights:

            LOG.debug("Running preflight check for VRF {}".format(self.id))

            # check for VRFs with the same RD
            rd_filter =  self.RD_FILTER.format(**{'rd':self.rd})

            rd_vrf = self._get(context=context, nc_filter=rd_filter)

            if rd_vrf is not None:
                if self.id != rd_vrf.id:
                    LOG.warning("Preflight found existing VRF {} with RD {} - attempting to remove".format(rd_vrf.id,self.rd))
                    rd_vrf._delete(context)

            LOG.debug("Preflight check completed for VRF {}".format(self.id))
        else:
            LOG.info("Preflight check for {} disabled in configuration".format(self.__class__.__name__))


