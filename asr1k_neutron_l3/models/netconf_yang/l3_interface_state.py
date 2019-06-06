from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair
from asr1k_neutron_l3.models.netconf_yang import xml_utils


class BDIInterfaceState(NyBase):
    ID_FILTER = """
                  <interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
                    <interface>
                      <name>BDI{id}</name>
                    </interface>
                  </interfaces-state>          
             """

    LIST_KEY = "interfaces-state"
    ITEM_KEY = "interface"

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'id', 'yang-key': 'name'},
            {'key': 'type'},
            {'key': 'admin_status', 'yang-key': 'admin-status'},
            {'key': 'oper_status', 'yang-key': 'oper-status'},
            {'key': 'last_change', 'yang-key': 'last-change'},
            {'key': 'phys_address', 'yang-key': 'phys-address'},
            {'key': 'speed', 'yang-key': 'speed'},
            {'key': 'in_octets', 'yang-key': 'in-octets', 'yang-path': 'statistics'},
            {'key': 'in_unicast_pkts', 'yang-key': 'in-unicast-pkts', 'yang-path': 'statistics'},
            {'key': 'in_broadcast_pkts', 'yang-key': 'in-broadcast-pkts', 'yang-path': 'statistics'},
            {'key': 'in_multicast_pkts', 'yang-key': 'in-multicast-pkts', 'yang-path': 'statistics'},
            {'key': 'in_discards', 'yang-key': 'in-discards', 'yang-path': 'statistics'},
            {'key': 'in_errors', 'yang-key': 'in-errors', 'yang-path': 'statistics'},
            {'key': 'in_unknown_protos', 'yang-key': 'in-unknown-protos', 'yang-path': 'statistics'},
            {'key': 'out_octets', 'yang-key': 'out-octets', 'yang-path': 'statistics'},
            {'key': 'out_unicast_pkts', 'yang-key': 'out-unicast-pkts', 'yang-path': 'statistics'},
            {'key': 'out_broadcast_pkts', 'yang-key': 'out-broadcast-pkts', 'yang-path': 'statistics'},
            {'key': 'out_multicast_pkts', 'yang-key': 'out-multicast-pkts', 'yang-path': 'statistics'},
            {'key': 'out_discards', 'yang-key': 'out-discards', 'yang-path': 'statistics'},
            {'key': 'out_errors', 'yang-key': 'out-errors', 'yang-path': 'statistics'},
        ]

    def __init__(self, **kwargs):
        super(BDIInterfaceState, self).__init__(**kwargs)

    @classmethod
    @execute_on_pair()
    def get(cls, id=None, port_channel=None, context=None):
        return cls._get(id=id, context=context)

    @classmethod
    def _remove_base_wrapper(cls, dict):
        dict = dict.get(xml_utils.RPC_REPLY, dict)
        dict = dict.get(xml_utils.DATA, dict)
        if dict is None:
            return
        dict = dict.get(cls.LIST_KEY, dict)

        return dict

    def to_dict(self, context=None):
        statistics = {'in_octets': self.in_octets, 'in_unicast_pkts': self.in_unicast_pkts,
                      'in_broadcast_pkts': self.in_broadcast_pkts,
                      'in_multicast_pkts': self.in_multicast_pkts, 'in_discards': self.in_discards,
                      'in_errors': self.in_errors, 'in_unknown_protos': self.in_unknown_protos,
                      'out_octets': self.out_octets, 'out_unicast_pkts': self.out_unicast_pkts,
                      'out_broadcast_pkts': self.out_broadcast_pkts, 'out_multicast_pkts': self.out_multicast_pkts,
                      'out_discards': self.out_discards, 'out_errors': self.out_errors}

        return {'admin_status': self.admin_status, 'oper_status': self.oper_status, 'phys_address': self.phys_address,
                'speed': self.speed, 'statistics': statistics}
