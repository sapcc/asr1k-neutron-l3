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
from xml.etree.ElementTree import fromstring, tostring
import base_action
from asr1k_neutron_l3.models.neutron.l3.router import Router
from asr1k_neutron_l3.models.neutron.l2.port import Port

from asr1k_neutron_l3.models.netconf_yang.l3_interface import BDIInterface, BDISecondaryIpAddress
from asr1k_neutron_l3.models.netconf_yang.vrf import VrfDefinition
from asr1k_neutron_l3.models.netconf_yang.l2_interface import LoopbackExternalInterface
from asr1k_neutron_l3.models.netconf_yang.route import VrfRoute
from asr1k_neutron_l3.models.netconf_yang.nat import NatPool
from asr1k_neutron_l3.models.netconf_yang.nat import DynamicNat
from asr1k_neutron_l3.models.netconf_yang.nat import StaticNat
from asr1k_neutron_l3.models.netconf_yang.access_list import AccessList
from asr1k_neutron_l3.models.netconf_yang.route_map import RouteMap
from asr1k_neutron_l3.models.netconf_yang.route_map import MapSequence
from asr1k_neutron_l3.models.netconf_yang.prefix import Prefix, PrefixSeq

from asr1k_neutron_l3.models.neutron.l2.port import Port

LOG = logging.getLogger(__name__)


class Netconf(base_action.BaseAction):

    def __init__(self, namespace):
        super(Netconf, self).__init__(namespace)

    def execute(self):
        # print(BdiInterface.exists(4098))
        # bdi = BdiInterface.get(4098)
        # bdi.update()
        # bdi.delete()
        # print(BdiInterface.exists(4098))
        # bdi.create()
        # print(BdiInterface.exists(4098))
        # print bdi

        #
        # print(BDISecondaryIpAddress.exists(4098,'10.44.30.25'))
        # bdi_sec = BDISecondaryIpAddress.get(4098,'10.44.30.25')
        # bdi_sec.update()
        # bdi_sec.delete()
        # bdi_sec.update()

        #
        # print(VrfDefinition.exists('5d1b197391424996a272d4bbaf1f2e10'))
        # vrf = VrfDefinition.get('5d1b197391424996a272d4bbaf1f2e10')
        # vrf.update()

        # print(LoopbackExternalInterface.exists(2,100))
        # svi = LoopbackExternalInterface.get(2,100)
        # svi.update()
        # print(LoopbackExternalInterface.exists(2,100))
        # svi.delete()
        # print(LoopbackExternalInterface.exists(2,100))
        # svi.create()
        #
        # print(VrfRoute.exists('5d1b197391424996a272d4bbaf1f2e10'))
        # route = VrfRoute.get('5d1b197391424996a272d4bbaf1f2e10')
        # route.update()
        #
        # print(NatPool.exists('5d1b197391424996a272d4bbaf1f2e10'))
        # natpool = NatPool.get('5d1b197391424996a272d4bbaf1f2e10')
        # natpool.update()
        #
        # print(DynamicNat.exists('NAT-5d1b197391424996a272d4bbaf1f2e10','5d1b197391424996a272d4bbaf1f2e10'))
        # dynamicnat = DynamicNat.get('NAT-5d1b197391424996a272d4bbaf1f2e10'.'5d1b197391424996a272d4bbaf1f2e10')
        # dynamicnat.update()
        #
        # print(StaticNat.exists('10.180.8.8','10.44.30.23'))
        # staticnat = StaticNat.get('10.180.8.8','10.44.30.23')
        # staticnat.update()
        #
        # print(AccessList.exists('NAT-5d1b197391424996a272d4bbaf1f2e10'))
        # acl = AccessList.get('NAT-5d1b197391424996a272d4bbaf1f2e10')
        # acl.update()

        # p = Port({'port_info':'ab1234','service_instance':1234,'bridge_domain':2345,'second_dot1q':3456,'segmentation_id':4567,'network_id':'andrew'})
        # p.create()

        print(RouteMap.get('test123'))

        seq = []
        seq.append(MapSequence(ordering_seq=10, operation='permit', prefix_list='snat-f8a44de0fc8e45df93c7f79bf3b01c95',
                               asn='additive,65126:101'))
        seq.append(MapSequence(ordering_seq=20, operation='deny', prefix_list='snat-f8a44de0fc8e45df93c7f79bf3b01c95'))

        RouteMap(name='test123', seq=seq).update()

        # print(Prefix.get('test1234'))
        #
        # seq = PrefixSeq(no=10,permit_ip='10.10.0.0/24')
        # seq2 = PrefixSeq(no=20, deny_ip="10.11.0.0/24")
        # p = Prefix(name="test1234")
        # p.add_seq(seq)
        # p.add_seq(seq2)
        #
        # p.update()
