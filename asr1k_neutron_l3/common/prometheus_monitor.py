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