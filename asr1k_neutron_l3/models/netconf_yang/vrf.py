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

from oslo_log import log as logging

from asr1k_neutron_l3.models.netconf_yang.bgp import AddressFamily
from asr1k_neutron_l3.common import cli_snippets
from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.models.netconf_yang.l3_interface import BDIInterface
from asr1k_neutron_l3.models.netconf_yang.nat import InterfaceDynamicNat
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, Requeable, NC_OPERATION, execute_on_pair
from asr1k_neutron_l3.models.netconf_yang.route import VrfRoute

LOG = logging.getLogger(__name__)


class VrfConstants(object):
    VRF = 'vrf'
    DEFINITION = "definition"

    ID = "id"
    NAME = "name"
    DESCRIPTION = "description"
    ADDRESS_FAMILY = "address-family"
    EXPORT = "export"
    IMPORT = "import"
    MAP = "map"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    RD = "rd"
    ROUTE_TARGET = "route-target"


class VrfDefinition(NyBase, Requeable):
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

    CLI_INIT =\
"""vrf definition {}
    description {}
    rd {}
    address-family ipv4
        export map exp-{}"""

    LIST_KEY = VrfConstants.VRF
    ITEM_KEY = VrfConstants.DEFINITION

    def requeable_operations(self):
        return ['create', 'update']

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'name', 'id': True},
            {'key': 'description'},
            {'key': 'address_family_ipv4', "yang-key": "ipv4", "yang-path": "address-family",
             'type': IpV4AddressFamily, "default": {}},
            {'key': 'rd'}
        ]

    def __init__(self, **kwargs):
        super(VrfDefinition, self).__init__(**kwargs)

        self.enable_bgp = kwargs.get('enable_bgp', False)
        if kwargs.get('map', None) is not None or kwargs.get('rt_import', None) is not None or \
                kwargs.get('rt_export', None) is not None:
            self.address_family_ipv4 = IpV4AddressFamily(**kwargs)

        self.asn = None

        if self.rd:
            self.asn = self.rd.split(":")[0]

    @property
    def neutron_router_id(self):
        if self.name is not None:
            return utils.vrf_id_to_uuid(self.name)

    def to_dict(self, context=None):

        definition = OrderedDict()
        definition[VrfConstants.NAME] = self.name
        if bool(self.description):
            definition[VrfConstants.DESCRIPTION] = self.description
        definition[VrfConstants.ADDRESS_FAMILY] = OrderedDict()

        # Idealliy we would not have this, but the Yang API is very unpleasant in case you try to remove things
        # hopefully
        definition[VrfConstants.RD] = self.rd

        if self.address_family_ipv4 is not None:
            definition[VrfConstants.ADDRESS_FAMILY][VrfConstants.IPV4] = self.address_family_ipv4.to_dict(context=context)

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

    def to_delete_dict(self, context=None):
        definition = OrderedDict()
        definition[VrfConstants.NAME] = self.name
        result = OrderedDict()
        result[VrfConstants.DEFINITION] = definition

        return dict(result)

    @execute_on_pair()
    def update(self, context=None):
        return super(VrfDefinition, self)._update(context=context, method=NC_OPERATION.PUT)

    def preflight(self, context):

        LOG.debug("Running preflight check for VRF {}".format(self.id))

        # check for VRFs with the same RD
        rd_filter = self.RD_FILTER.format(**{'rd': self.rd})

        rd_vrf = self._get(context=context, nc_filter=rd_filter)

        if rd_vrf is not None:
            if self.id != rd_vrf.id:
                LOG.warning("Preflight on {} found existing VRF {} with RD {} - attempting to remove"
                            "".format(self.id, rd_vrf.id, self.rd))
                rd_vrf._delete(context)
                LOG.warning("Preflight on {} deleted existing VRF {} with RD {}".format(self.id, rd_vrf.id, self.rd))

    def postflight(self, context):
        # Clean remaining interface NAT
        LOG.debug("Processing Interface NAT")
        interface_nats = []

        try:
            interface_nats = InterfaceDynamicNat.get_for_vrf(context=context, vrf=self.id)

            # Clean remaining interfaces
            if len(interface_nats) == 0:
                LOG.info("No interface NAT to clean")
            for interface_nat in interface_nats:
                LOG.info("Deleting hanging interface nat {} in vrf {} postflight.".format(interface_nat.id, self.name))
                interface_nat._delete(context=context)
                LOG.info("Deleted hanging interface nat {} in vrf {} postflight.".format(interface_nat.id, self.name))
        except BaseException as e:
            LOG.error("Failed to delete {} interface NAT in VRF {} postlight : {}"
                      "".format(len(interface_nats), self.id, e))

        # Clean remaining routes
        LOG.debug("Processing Routes")

        routes = []

        try:
            routes = VrfRoute.get_for_vrf(context=context, vrf=self.id)
            if len(routes) == 0:
                LOG.info("No routes to clean")

            for route in routes:
                LOG.info("Deleting hanging route {} in vrf {} postflight.".format(route.name, self.name))
                route._delete(context=context)
                LOG.info("Deleted hanging route {} in vrf {} postflight.".format(route.name, self.name))
        except BaseException as e:
            LOG.error("Failed to delete {} routes in VRF {} postlight : {}".format(len(routes), self.id, e))

        LOG.debug("Processing Interfaces")
        bdis = []
        try:
            bdis = BDIInterface.get_for_vrf(context=context, vrf=self.id)

            if len(bdis) == 0:
                LOG.info("No interfaces to clean")

            for bdi in bdis:
                LOG.info("Deleting hanging interface BDI{} in vrf {} postflight.".format(bdi.name, self.name))
                bdi._delete(context=context)
                LOG.info("Deleted hanging interface BDI{} in vrf {} postflight.".format(bdi.name, self.name))

        except BaseException as e:
            LOG.error("Failed to delete {} intefaces in VRF {} postlight : {}".format(len(bdis), self.id, e))

        LOG.debug("Processing Address Families")
        afs = []
        try:
            afs = AddressFamily.get_for_vrf(context=context, asn=self.asn, vrf=self.id)

            if len(afs) == 0:
                LOG.info("No address fammilies to clean")

            for af in afs:
                LOG.info("Deleting hanging address family in vrf {} postflight.".format(self.name))
                LOG.info(af)
                result = af._delete(context=context)
                LOG.debug(result)
                LOG.info("Deleted hanging address family in vrf {} postflight.".format(self.name))
        except BaseException as e:
            LOG.error("Failed to delete {} BGP address families in VRF {} postlight : {}".format(len(afs), self.id, e))

        LOG.debug("Postflight check completed for VRF {}".format(self.id))

    def init_config(self):
        return cli_snippets.VRF_CLI_INIT.format(**{'name': self.name, 'description': self.description, 'rd': self.rd})


class IpV4AddressFamily(NyBase):
    LIST_KEY = VrfConstants.ADDRESS_FAMILY
    ITEM_KEY = VrfConstants.IPV4

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'map', 'yang-path': "export", "default": None},
            {'key': 'rt_export', 'yang-key': "asn-ip", 'yang-path': "route-target/export",
             'type': [str], "default": []},
            {'key': 'rt_import', 'yang-key': "asn-ip", 'yang-path': "route-target/import",
             'type': [str], "default": []},
        ]

    def __init__(self, **kwargs):
        super(IpV4AddressFamily, self).__init__(**kwargs)

        self.map = kwargs.get("map")
        self.rt_export = kwargs.get("rt_export")
        self.rt_import = kwargs.get("rt_import")

    def to_dict(self, context=None):
        address_family = OrderedDict()

        if self.map is not None:
            address_family[VrfConstants.EXPORT] = {"map": self.map}

        address_family[VrfConstants.ROUTE_TARGET] = {}

        if self.rt_export is not None and len(self.rt_export) > 0:
            asns = []
            for rt in self.rt_export:
                if rt is not None and rt != '':
                    asns.append({"asn-ip": rt})
            address_family[VrfConstants.ROUTE_TARGET][VrfConstants.EXPORT] = asns

        if self.rt_import is not None and len(self.rt_import) > 0:
            asns = []
            for rt in self.rt_import:
                if rt is not None and rt != '':
                    asns.append({"asn-ip": rt})
            address_family[VrfConstants.ROUTE_TARGET][VrfConstants.IMPORT] = asns

        return dict(address_family)
