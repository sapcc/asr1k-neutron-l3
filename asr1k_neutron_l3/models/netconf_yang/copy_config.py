import re
from lxml import etree

from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase,execute_on_pair
from asr1k_neutron_l3.common import asr1k_exceptions as exc
from asr1k_neutron_l3.models.connection import ConnectionManager
from asr1k_neutron_l3.common.prometheus_monitor import PrometheusMonitor

class CopyConfig(NyBase):

    COPY = """
    <copy xmlns='http://cisco.com/ns/yang/Cisco-IOS-XE-rpc'>
        <_source>{}</_source>
        <_destination>{}</_destination>
    </copy>"""


    @classmethod
    def __parameters__(cls):
        return []




    @execute_on_pair()
    def copy_config(self, context=None, source='running-config',destination='startup-config'):
        try :

            with PrometheusMonitor().config_copy_duration.time():
                with ConnectionManager(context=context) as connection:
                    result = connection.rpc(self.COPY.format(source,destination))
                    parsed = etree.fromstring(result._raw.encode())
                    text = parsed.xpath('//*[local-name()="result"]')[0].text

                    if re.match(".*\[OK\]$",text) is not None:
                        return text
                    else :
                        raise exc.DeviceOperationException()
        except BaseException as e:
            PrometheusMonitor().config_copy_errors.inc()
            raise e