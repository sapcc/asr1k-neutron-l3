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
import mock
import errno
from socket import error as socket_error

from oslo_log import log as logging

from prometheus_client import start_http_server
from prometheus_client import Counter
from prometheus_client import Gauge
from prometheus_client import core
from prometheus_client import Histogram


LOG = logging.getLogger(__name__)

ACTION_BUCKETS=  (1.0, 2.0, 3.0, 4.0, 5.0, 8.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40., 60.0, float("inf"))
OPERATION_BUCKETS=  (0.1,0.3,0.5, 0.7,1.0, 2.0, 3.0, 4.0, 5.0, 8.0, 10.0, 15.0, float("inf"))

ORPHANS_LABELS = ['host','device']
CONNECTION_POOL_LABELS = ['host','device']
DETAIL_LABELS = ['host','device', 'entity','action']
BASIC_LABELS = ['host']
STATS_LABELS = ['host','status']

L2 = "l2"
L3 = "l3"

class PrometheusMonitor(object):



    __instance = None

    def __new__(cls,host=None,namespace=None,type=L3):
        if PrometheusMonitor.__instance is None:
            PrometheusMonitor.__instance = object.__new__(cls)
            PrometheusMonitor.__instance.__setup__(host=host,namespace=namespace,type=type)


        return PrometheusMonitor.__instance

    def __setup__(self,host=None,namespace=None,type=L3):
        self.namespace = "{}_{}".format(namespace, type)
        self.type = type
        self.host = host
        self._requeue = Counter('requeue', 'Number of operaton requeues',DETAIL_LABELS,namespace=self.namespace)
        self._ssh_banner_errors = Counter('ssh_banner_errors', 'Number of ssh banner errors',DETAIL_LABELS,namespace=self.namespace)
        self._inconsistency_errors = Counter('inconsistency_errors', 'Number of device inconsistency_errors',DETAIL_LABELS,namespace=self.namespace)
        self._internal_errors = Counter('internal_errors', 'Number of device API internal errors',DETAIL_LABELS,namespace=self.namespace)
        self._config_locks = Counter('config_locks', 'Number of device config_locks',DETAIL_LABELS,namespace=self.namespace,)
        self._nc_ssh_errors = Counter('nc_ssh_errors', 'Number of netconf-yang SSH errors',DETAIL_LABELS,namespace=self.namespace)
        self._device_unreachable = Counter('device_unreachable', 'Unreachable device', DETAIL_LABELS, namespace=self.namespace)
        self._rpc_sync_errors = Counter('rpc_sync_errors', 'Sync block on RPC request', DETAIL_LABELS, namespace=self.namespace)
        self._connection_pool_exhausted = Counter('connection_pool_exhausted', 'Connnection pool  exhausted', CONNECTION_POOL_LABELS, namespace=self.namespace)

        self._yang_operation_duration = Histogram("yang_operation_duration", "Individual entity operation",DETAIL_LABELS,namespace=self.namespace, buckets=OPERATION_BUCKETS)

        self._l3_orphan_count = Gauge('l3_orphan_count', 'Number of L3 orphans found on device', ORPHANS_LABELS,namespace=self.namespace )
        self._l2_orphan_count = Gauge('l2_orphan_count', 'Number of L2 orphans found on device', ORPHANS_LABELS, namespace=self.namespace)

        if self.type == L3:
            self._router_create_duration = Histogram("router_create_duration", "Router create duration in seconds",BASIC_LABELS,namespace=self.namespace,buckets=ACTION_BUCKETS)
            self._router_update_duration = Histogram("router_update_duration","Router update duration in seconds",BASIC_LABELS, namespace=self.namespace,buckets=ACTION_BUCKETS)
            self._router_delete_duration = Histogram("router_delete_duration", "Router delete duration in seconds",BASIC_LABELS, namespace=self.namespace,buckets=ACTION_BUCKETS)
            self._config_copy_duration = Histogram("config_copy_duration", "Running to starup config copy duration in seconds",DETAIL_LABELS, namespace=namespace,buckets=ACTION_BUCKETS)
            self._config_copy_errors = Counter('config_copy_errors', 'Number of config copy errors',DETAIL_LABELS,namespace=self.namespace)
            self._routers = Gauge('routers', 'Number of managed routers', STATS_LABELS, namespace=self.namespace)
            self._interfaces = Gauge('interfaces', 'Number of managed interfaces', STATS_LABELS, namespace=self.namespace)
            self._gateways = Gauge('gateways', 'Number of managed gateways', STATS_LABELS, namespace=self.namespace)
            self._floating_ips = Gauge('floating_ips', 'Number of managed floating_ips', STATS_LABELS, namespace=self.namespace)


        elif self.type == L2:
            self._port_create_duration = Histogram("port_create_duration", "Port create duration in seconds",BASIC_LABELS, namespace=self.namespace,buckets=ACTION_BUCKETS)
            self._port_update_duration = Histogram("port_update_duration","Port update duration in seconds",BASIC_LABELS, namespace=self.namespace,buckets=ACTION_BUCKETS)
            self._port_delete_duration = Histogram("port_delete_duration", "Port delete duration in seconds",BASIC_LABELS, namespace=self.namespace,buckets=ACTION_BUCKETS)


    def __init__(self,host=None,namespace=None,type=L3):
        pass

    # Some magic to to wrap metric to always inject the agent host
    def __getattr__(self, item):
        func = "_{}".format(item)
        if func in self.__dict__:
            return MetricWrapper(self.__dict__[func], host=self.host)
        else:
            try:
                return super(PrometheusMonitor, self).__getattribute__(item)
            except AttributeError as e:
                LOG.exception(e)
                return mock.MagicMock()

    def start(self):
        if not self.exporter_listening:
            port = int(os.environ.get('METRICS_PORT', 9102))
            addr = int(os.environ.get('METRICS_ADDR', '0.0.0.0'))
            LOG.info("Starting prometheus exporter %s:%s", addr, port)
            try:
                start_http_server(port, addr)
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


class MetricWrapper(object):

    def __init__(self, base,host=None):
        self.base = base
        self.host =  host

    def __getattr__(self, item):
        return self.base.labels(host=self.host).__getattribute__(item)

    def labels(self,**labels):
        labels['host'] = self.host
        return self.base.labels(**labels)
