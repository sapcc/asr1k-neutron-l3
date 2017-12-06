import os, socket

import errno
from socket import error as socket_error

from oslo_log import log as logging

from prometheus_client import start_http_server
from prometheus_client import Counter
from prometheus_client import Gauge


LOG = logging.getLogger(__name__)

class PrometheusMonitor(object):

    def __new__(cls):

        if not hasattr(cls, 'instance'):
            cls.instance = super(PrometheusMonitor, cls).__new__(cls)

        return cls.instance

    def __init__(self):
        self.floating_ip = Gauge('asr_floating_ips', 'Number of managed Floating IPs', ['device'])


    def start(self):
        if not self.exporter_listening:
            port = int(os.environ.get('METRICS_PORT', 9102))
            LOG.info("Starting prometheus exporter port port %s", port)
            start_http_server(port)


    @property
    def exporter_listening(self):
        LOG.debug("Checking prometheus exporter")
        s = socket.socket()
        address = '127.0.0.1'
        port = int(os.environ.get('METRICS_PORT', 9102))
        try:
            s.connect((address, port))

        except socket_error as serr:
            if serr.errno != errno.ECONNREFUSED:
                return True
        finally:
            s.close()

        return False