from asr1k_neutron_l3.models.neutron.l3 import base
from asr1k_neutron_l3.models.netconf_yang import route_map
from asr1k_neutron_l3.plugins.common import utils


class RouteMap(base.Base):
    def __init__(self, name, rt=None):
        super(RouteMap, self).__init__()
        self.vrf = utils.uuid_to_vrf_id(name)
        self.name = "exp-{}".format(self.vrf)
        self.rt = rt



    @property
    def _rest_definition(self):
         sequences = []
         sequences.append(route_map.MapSequence(ordering_seq=10, operation='permit', prefix_list='snat-{}'.format(self.vrf), asn=self.rt))
         sequences.append(route_map.MapSequence(ordering_seq=20, operation='deny', prefix_list='exp-{}'.format(self.vrf)))

         return route_map.RouteMap(name=self.name, seq=sequences)


    def get(self):
        return route_map.RouteMap.get(self.name)




    def update(self):
        self._rest_definition.update()


    def delete(self):
        self._rest_definition.delete()


    def valid(self):
        return self._rest_definition == self.get()