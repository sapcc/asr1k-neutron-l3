import re
from lxml import etree

from collections import OrderedDict


from oslo_log import log as logging
from oslo_config import cfg

from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase,execute_on_pair
from asr1k_neutron_l3.common import asr1k_exceptions as exc
from asr1k_neutron_l3.models.connection import ConnectionManager
from asr1k_neutron_l3.common.prometheus_monitor import PrometheusMonitor
from asr1k_neutron_l3.models.netconf_yang import  xml_utils

LOG = logging.getLogger(__name__)

IOS_NAT_DATA = 'nat-data'


class NATStatisticsConstants(object):
    pass


class NatStatistics(NyBase):
    IP_NAT_STATISTICS = "ip-nat-statistics"

    NAT_STATS = """
                  <nat-data xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-nat-oper">
                    <ip-nat-statistics/>
                  </nat-data>
                """

    # @classmethod
    # def __parameters__(cls):
    #     return [
    #         {'key': 'entries', 'mandatory': True},
    #         {'key': 'statics'},
    #         {'key': 'flows'},
    #         {'key': 'insides'},
    #         {'key': 'outsides'},
    #         {'key': 'hits'},
    #         {'key': 'misses'},
    #         {'key': 'packets_punted'},
    #         {'key': 'in2out_drops'},
    #         {'key': 'out2in_drops'},
    #     ]


    def __init__(self, **kwargs):
        super(NatStatistics, self).__init__(**kwargs)


    def to_dict(self):
        result = OrderedDict()

        return result

    def get_stats(self,context=None):

        result =  self._get_stats()

        return result.to_dict()


    @execute_on_pair()
    def _get_stats(self,context=None):
        try :

            with PrometheusMonitor().nat_stats_duration.labels(device=context.host,entity=self.__class__.__name__,action='get_nat_stats').time():
                with ConnectionManager(context=context) as connection:

                    result = connection.get(self.NAT_STATS,entity=self.__class__.__name__,action='get_nat_stats')

                    json = self.to_json(result.xml)
                    return json

        except BaseException as e:
            PrometheusMonitor().nat_stats_errors.labels(device=context.host,entity=self.__class__.__name__,action='get_nat_stats').inc()
            raise e


    @classmethod
    def remove_wrapper(cls,dict):

        dict = cls._remove_base_wrapper(dict)

        if dict is not None:
            dict = dict.get(cls.IP_NAT_STATISTICS, dict)

        return dict



    @classmethod
    def _remove_base_wrapper(cls,dict):
        if dict is None:
            return

        dict = dict.get(xml_utils.RPC_REPLY,dict)
        dict = dict.get(xml_utils.DATA, dict)
        if dict is None:
            return
        dict = dict.get(IOS_NAT_DATA, dict)


        return dict
