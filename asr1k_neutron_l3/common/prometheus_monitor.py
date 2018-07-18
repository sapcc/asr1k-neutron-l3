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
from prometheus_client import core
from prometheus_client import Histogram


LOG = logging.getLogger(__name__)

ACTION_BUCKETS=  (1.0, 2.0, 3.0, 4.0, 5.0, 8.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40., 60.0, core._INF)


class PrometheusMonitor(object):



    __instance = None

    def __new__(cls,namespace=None):
        if PrometheusMonitor.__instance is None:
            PrometheusMonitor.__instance = object.__new__(cls)
            PrometheusMonitor.__instance.__setup__(namespace=namespace)


        return PrometheusMonitor.__instance

    def __setup__(self,namespace=None):
        self.ssh_banner_errors = Counter('ssh_banner_errors', 'Number of ssh banner errors',namespace=namespace)
        self.inconsistency_errors = Counter('inconsistency_errors', 'Number of device inconsistency_errors',namespace=namespace)
        self.internal_errors = Counter('internal_errors', 'Number of device API internal errors',namespace=namespace)
        self.config_locks = Counter('config_locks', 'Number of device config_locks',namespace=namespace)
        self.nc_ssh_errors = Counter('nc_ssh_errors', 'Number of netconf-yang SSH errors', namespace=namespace)
        self.router_create_duration = Histogram("router_create_duration", "Router create duration in seconds", namespace=namespace, buckets=ACTION_BUCKETS)
        self.router_update_duration = Histogram("router_update_duration","Router update duration in seconds", namespace=namespace, buckets=ACTION_BUCKETS)
        self.router_delete_duration = Histogram("router_delete_duration", "Router delete duration in seconds", namespace=namespace, buckets=ACTION_BUCKETS)

        self.port_create_duration = Histogram("port_create_duration", "Port create duration in seconds", namespace=namespace, buckets=ACTION_BUCKETS)
        self.port_update_duration = Histogram("port_update_duration","Port update duration in seconds", namespace=namespace, buckets=ACTION_BUCKETS)
        self.port_delete_duration = Histogram("port_delete_duration", "Port delete duration in seconds", namespace=namespace, buckets=ACTION_BUCKETS)


    def __init__(self,namespace=None):
        pass




    def start(self):
        if not self.exporter_listening:
            port = int(os.environ.get('METRICS_PORT', 9102))
            LOG.info("Starting prometheus exporter port port %s", port)
            try:
                start_http_server(port)
            except Exception as e:
                LOG.error("Failed to start prometheus exporter : %s", e)


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


