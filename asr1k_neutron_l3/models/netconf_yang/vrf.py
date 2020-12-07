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
from operator import attrgetter
import re

from oslo_log import log as logging

from asr1k_neutron_l3.models.netconf_yang.bgp import AddressFamily
from asr1k_neutron_l3.common import cli_snippets
from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.models.connection import ConnectionManager
from asr1k_neutron_l3.models.netconf_yang.l3_interface import VBInterface
from asr1k_neutron_l3.models.netconf_yang.nat import InterfaceDynamicNat
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, Requeable, NC_OPERATION, execute_on_pair, \
    retry_on_failure
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
    ROUTE_TARGET_EXPORT = "export-route-target"
    ROUTE_TARGET_IMPORT = "import-route-target"
    WITHOUT_STITCHING = "without-stitching"


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

    GET_ALL_STUB = """
                <native>
                    <vrf xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                        <definition>
                            <name/>
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

    CLI_INIT = """vrf definition {}
    description {}
    rd {}
    address-family ipv4
        export map exp-{}"""

    DELETE_VRF_RD = """
        <config  xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
            <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                <vrf>
                    <definition>
                        <name>{id}</name>
                        <rd operation="delete"/>
                        <address-family>
                            <ipv4>
                                <export operation="delete"/>
                            </ipv4>
                        </address-family>
                    </definition>
                </vrf>
            </native>
        </config>
             """

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

    def to_dict(self, context):
        definition = OrderedDict()
        definition[VrfConstants.NAME] = self.name
        if bool(self.description):
            definition[VrfConstants.DESCRIPTION] = self.description
        definition[VrfConstants.ADDRESS_FAMILY] = OrderedDict()

        # Idealliy we would not have this, but the Yang API is very unpleasant in case you try to remove things
        # hopefully
        definition[VrfConstants.RD] = self.rd

        if self.address_family_ipv4 is not None:
            definition[VrfConstants.ADDRESS_FAMILY][VrfConstants.IPV4] = self.address_family_ipv4.to_dict(context)

        result = OrderedDict()
        result[VrfConstants.DEFINITION] = definition
        return dict(result)

    def to_delete_dict(self, context):
        definition = OrderedDict()
        definition[VrfConstants.NAME] = self.name
        result = OrderedDict()
        result[VrfConstants.DEFINITION] = definition

        return dict(result)

    @execute_on_pair()
    def update(self, context):
        return super(VrfDefinition, self)._update(context=context, method=NC_OPERATION.PUT)

    def preflight(self, context):
        LOG.debug("Running preflight check for VRF {}".format(self.id))

        # check for VRFs with the same RD
        rd_filter = self.RD_FILTER.format(rd=self.rd)

        rd_vrf = self._get(context=context, nc_filter=rd_filter)

        if rd_vrf is not None:
            if self.id != rd_vrf.id:
                LOG.warning("Preflight on {} found existing VRF {} with RD {} - attempting to remove"
                            "".format(self.id, rd_vrf.id, self.rd))
                # remove the rd, as we want to repurpose it
                rd_vrf._delete_rd(context)

                # try deleting the VRF, but don't fail if we cannot do so
                try:
                    rd_vrf._delete(context)
                except Exception as e:
                    LOG.warning("Deleting VRF %s failed, but deleting its RD succeeded - continuing with creating %s",
                                rd_vrf.id, self.id)
                LOG.warning("Preflight on {} deleted existing VRF {} with RD {}".format(self.id, rd_vrf.id, self.rd))

    @retry_on_failure()
    def _delete_rd(self, context):
        config = self.DELETE_VRF_RD.format(id=self.id)
        with ConnectionManager(context=context) as connection:
            return connection.edit_config(config=config, entity=self.__class__.__name__, action="update")

    def postflight(self, context, method):
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
        vbis = []
        try:
            vbis = VBInterface.get_for_vrf(context=context, vrf=self.id)
            if len(vbis) == 0:
                LOG.info("No interfaces to clean")

            for vbi in vbis:
                LOG.info("Deleting hanging interface {}{} in vrf {} postflight."
                         .format(context.bd_iftype, vbi.name, self.name))
                vbi._delete(context=context)
                LOG.info("Deleted hanging interface {}{} in vrf {} postflight."
                         .format(context.bd_iftype, vbi.name, self.name))
        except BaseException as e:
            LOG.error("Failed to delete {} intefaces in VRF {} postlight : {}".format(len(vbis), self.id, e))

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
        return cli_snippets.VRF_CLI_INIT.format(name=self.name, description=self.description, rd=self.rd)


class IpV4AddressFamily(NyBase):
    LIST_KEY = VrfConstants.ADDRESS_FAMILY
    ITEM_KEY = VrfConstants.IPV4

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'map', 'yang-path': "export", "default": None},

            # =16.9
            {'key': 'rt_export', 'yang-key': "export", 'yang-path': "route-target",
             'type': [RouteTarget], "default": []},
            {'key': 'rt_import', 'yang-key': "import", 'yang-path': "route-target",
             'type': [RouteTarget], "default": []},

            # >16.9
            {'key': 'rt_export', 'yang-key': "without-stitching",
             'yang-path': "route-target/export-route-target",
             'type': [RouteTarget], "default": []},
            {'key': 'rt_import', 'yang-key': "without-stitching",
             'yang-path': "route-target/import-route-target",
             'type': [RouteTarget], "default": []},
        ]

    def to_dict(self, context):
        address_family = OrderedDict()

        if self.map is not None:
            address_family[VrfConstants.EXPORT] = {"map": self.map}

        address_family[VrfConstants.ROUTE_TARGET] = {}

        if self.rt_export:
            asns = []
            for rt in sorted(self.rt_export, key=attrgetter('normalized_asn_ip')):
                asns.append(rt.to_dict(context))

            if context.version_min_17_3:
                rt = {VrfConstants.ROUTE_TARGET_EXPORT: {VrfConstants.WITHOUT_STITCHING: asns}}
            else:
                rt = {VrfConstants.EXPORT: asns}
            address_family[VrfConstants.ROUTE_TARGET].update(rt)

        if self.rt_import:
            asns = []
            for rt in sorted(self.rt_import, key=attrgetter('normalized_asn_ip')):
                asns.append(rt.to_dict(context))

            if context.version_min_17_3:
                rt = {VrfConstants.ROUTE_TARGET_IMPORT: {VrfConstants.WITHOUT_STITCHING: asns}}
            else:
                rt = {VrfConstants.IMPORT: asns}
            address_family[VrfConstants.ROUTE_TARGET].update(rt)

        return dict(address_family)


class RouteTarget(NyBase):
    # matches 65001.4:1234
    SHORT_4B_RE = re.compile(r"^(?P<a>\d+)\.(?P<b>\d+):(?P<c>\d+)$")

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'asn_ip'},
        ]

    def to_dict(self, context):
        return {
            "asn-ip": self.normalized_asn_ip,
        }

    @property
    def normalized_asn_ip(self):
        m = self.SHORT_4B_RE.match(self.asn_ip)
        if m:
            asn = (int(m.group('a')) << 16) + int(m.group('b'))
            return "{}:{}".format(asn, m.group('c'))
        return self.asn_ip
