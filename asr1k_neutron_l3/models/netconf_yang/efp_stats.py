from oslo_config import cfg

from asr1k_neutron_l3.models.netconf_yang.ny_base import execute_on_pair, NyBase
from asr1k_neutron_l3.models.netconf_yang import xml_utils


class EfpStats(NyBase):
    LIST_KEY = "efp-stats"
    ITEM_KEY = "efp-stat"
    PORT_CHANNEL = 1

    ID_FILTER = """
          <efp-stats xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-efp-oper">
            <efp-stat>
              <id>{id}</id>
              <interface>Port-channel{port_channel}</interface>
            </efp-stat>
          </efp-stats>
    """

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'id'},
            {'key': 'port_channel'},
            {'key': 'in_pkts', 'yang-key': 'in-pkts'},
            {'key': 'in_bytes', 'yang-key': 'in-bytes'},
            {'key': 'out_pkts', 'yang-key': 'out-pkts'},
            {'key': 'out_bytes', 'yang-key': 'out-bytes'},

        ]

    @classmethod
    def get_primary_filter(cls, **kwargs):
        return cls.ID_FILTER.format(id=kwargs.get('id'), port_channel=cls.PORT_CHANNEL)

    def __init__(self, **kwargs):
        super(EfpStats, self).__init__(**kwargs)
        self.port_channel = self.PORT_CHANNEL

    @classmethod
    @execute_on_pair()
    def get(cls, id=None, context=None):
        return cls._get(id=id, port_channel=cls.PORT_CHANNEL, context=context)

    @classmethod
    def _remove_base_wrapper(cls, dict, context):
        dict = dict.get(xml_utils.RPC_REPLY, dict)
        dict = dict.get(xml_utils.DATA, dict)
        if dict is None:
            return
        dict = dict.get('efp-stats', dict)

        return dict

    def to_dict(self, context):
        return {'in_pkts': self.in_pkts, 'in_bytes': self.in_bytes,
                'out_pkts': self.out_pkts, 'out_bytes': self.out_bytes}


class LoopbackExternalEfpStats(EfpStats):
    def __init__(self, **kwargs):
        self.PORT_CHANNEL = cfg.CONF.asr1k_l2.loopback_external_interface
        super(LoopbackExternalEfpStats, self).__init__(**kwargs)


class LoopbackInternalEfpStats(EfpStats):
    def __init__(self, **kwargs):
        self.PORT_CHANNEL = cfg.CONF.asr1k_l2.loopback_internal_interface
        super(LoopbackInternalEfpStats, self).__init__(**kwargs)
