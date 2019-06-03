from lxml import etree

from asr1k_neutron_l3.common import asr1k_exceptions as exc
from asr1k_neutron_l3.models.connection import ConnectionManager
from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase, execute_on_pair
from asr1k_neutron_l3.common.prometheus_monitor import PrometheusMonitor


class CopyConfig(NyBase):
    COPY = """
    <copy xmlns='http://cisco.com/ns/yang/Cisco-IOS-XE-rpc'>
        <_source>{source}</_source>
        <_destination>{destination}</_destination>
    </copy>"""

    COPY_1612 = """
    <copy xmlns='http://cisco.com/ns/yang/Cisco-IOS-XE-rpc'>
        <source-drop-node-name>{source}</source-drop-node-name>
        <destination-drop-node-name>{destination}</destination-drop-node-name>
    </copy>"""

    @classmethod
    def __parameters__(cls):
        return []

    @execute_on_pair()
    def copy_config(self, context=None, source='running-config', destination='startup-config'):
        try:
            with PrometheusMonitor().config_copy_duration.labels(device=context.host,
                                                                 entity=self.__class__.__name__,
                                                                 action='copy').time():
                with ConnectionManager(context=context) as connection:
                    if connection.is_min_version_1612:
                        COPY_CMD = self.COPY_1612
                    else:
                        COPY_CMD = self.COPY
                    result = connection.rpc(COPY_CMD.format(source=source, destination=destination),
                                            entity=self.__class__.__name__,
                                            action='copy')
                    parsed = etree.fromstring(result._raw.encode())
                    text = parsed.xpath('//*[local-name()="result"]')[0].text

                    if text == 'RPC request successful':
                        return text
                    else:
                        raise exc.DeviceOperationException()
        except BaseException as e:
            PrometheusMonitor().config_copy_errors.labels(device=context.host,
                                                          entity=self.__class__.__name__,
                                                          action='copy').inc()
            raise e

    def to_dict(self):
        return None
