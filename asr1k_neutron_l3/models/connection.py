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

import socket
import time
from retrying import retry
import eventlet


from threading import Lock
from asr1k_neutron_l3.models.asr1k_pair import ASR1KPair
from asr1k_neutron_l3.common.asr1k_exceptions import DeviceUnreachable
from asr1k_neutron_l3.common import asr1k_constants
from asr1k_neutron_l3.common.prometheus_monitor import PrometheusMonitor

from ncclient import manager
from ncclient.xml_ import to_ele
from oslo_utils import uuidutils
from oslo_log import log as logging
from oslo_config import cfg
from oslo_service import loopingcall
from oslo_utils import importutils

from paramiko.client import SSHClient,AutoAddPolicy
import paramiko
from ncclient.operations.errors import TimeoutExpiredError
from ncclient.transport.errors import SSHError
from ncclient.transport.errors import SessionCloseError
from ncclient.transport.errors import TransportError
from paramiko.ssh_exception import SSHException, NoValidConnectionsError,ChannelException
from bs4 import BeautifulSoup as bs

LOG = logging.getLogger(__name__)


def _retry_if_exhausted(exception):
    return isinstance(exception, ConnectionPoolExhausted)

def ssh_connect(context):
    connect = None
    try:
        port = context.yang_port
        #LOG.debug("Checking device connectivity.")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((context.host, port))
        ssh_transport = paramiko.Transport(sock)
        ssh_transport.close()
        #LOG.debug("Connection to {} on port {} successful".format(context.host,port))
    except Exception as e:
        if isinstance(e,socket.error):
            return False
    finally:
        if connect is not None:
            connect.close()


    return True

def check_devices(device_info):
    for context in ASR1KPair().contexts:
        device_reachable = ssh_connect(context)
        info = device_info.get(context.host, None)

        admin_up = True

        if info is not None and not info.get('enabled'):
            admin_up = False

        if not device_reachable or not admin_up:
            context.alive = False
            LOG.debug("Device reachable {} and enabled {}, marked as dead".format(context.host,admin_up))
        else:
            if device_reachable and admin_up:
                context.alive = True
                LOG.debug("Device reachable {} and enabled {}, marked as alive".format(context.host, admin_up))

class  ConnectionPoolExhausted(Exception):
    pass

class  ConnectionPoolNotInitialized(Exception):
    pass

class ConnectionManager(object):

    def __init__(self,context=None):
        self.context = context

    def __enter__(self):
        self.connection = ConnectionPool().pop_connection(context=self.context)
        return self.connection

    def __exit__(self, type, value, traceback):
        ConnectionPool().push_connection(self.connection,context=self.context)


class ConnectionPool(object):
    __instance = None


    def __new__(cls):
        if ConnectionPool.__instance is None:
            ConnectionPool.__instance = object.__new__(cls)
        else:
            ConnectionPool.__instance.__check_initialized()

        return ConnectionPool.__instance

    def __init__(self):
        pass



    def _ensure_connections_aged(self):

        try:
            for context in self.pair_config.contexts:
                yang = self.devices[context.host]

                for connection in yang:

                    if connection.age > self.max_age:
                        LOG.debug("***** closing aged connection with session id {} aged {:10.2f}s".format(connection.session_id,connection.age))
                        connection.lock.acquire()
                        connection.close()
                        connection.lock.release()
        except Exception as e:
            LOG.exception(e)


    def __check_initialized(self):
        if not hasattr(self, 'initialized'):
            raise ConnectionPoolNotInitialized("Please ensure pool is before first use initilized with `ConnectionPool().initialiase(self, yang_connection_pool_size=0,max_age=0)`")


    def initialiase(self, yang_connection_pool_size=0,max_age=0):

        try:

            yang_pool_size = min(yang_connection_pool_size, asr1k_constants.MAX_CONNECTIONS)

            if yang_pool_size < yang_connection_pool_size:
                LOG.warning(
                    "The yang connection pool size has been reduced to the system maximum its now {}".format(yang_pool_size))

            self.yang_pool_size = yang_pool_size
            self.max_age = max_age
            self.pair_config = ASR1KPair()

            self.devices = {}

            LOG.info("Initializing connection pool with yang pool size {}".format(self.yang_pool_size))

            for context in self.pair_config.contexts:
                yang = []

                for i in range(self.yang_pool_size):
                    yang.append(YangConnection(context,id=i))

                self.devices[context.host] = yang


            if self.max_age > 0:
                LOG.debug("Setting up looping call to close connections older than {} seconds".format(self.max_age))
                self.monitor = loopingcall.FixedIntervalLoopingCall(
                    self._ensure_connections_aged)
                self.monitor.start(interval=self.max_age)

            self.initialized = True
        except Exception as e:
            LOG.exception(e)



    @retry(stop_max_attempt_number=25, wait_fixed=100, retry_on_exception=_retry_if_exhausted)
    def pop_connection(self,context=None):

        pool = self.devices.get(context.host)
        connection = None
        if len(pool) > 0:
            connection = pool.pop(0)

        if connection is None:
            PrometheusMonitor().connection_pool_exhausted.labels(device=context.host).inc()
            raise ConnectionPoolExhausted()

        connection.lock.acquire()

        return connection

    def push_connection(self,connection,context=None):
        connection.lock.release()

        pool = self.devices.get(context.host)
        pool.append(connection)

    def get_connection(self,context):



        connection = self.devices.get(context.host).pop(0)


        self.devices.get(context.host).append(connection)

        if connection is None:
            raise Exception('No connection can be found for {}'.format(context.host))

        return connection




class YangConnection(object):

    def __init__(self, context,id=0):
        self.lock = Lock()
        self.context = context
        self._ncc_connection = None
        self.start = time.time()
        self.id = "{}-{}".format(context.host,id)

    @property
    def age(self):
        return time.time() - self.start

    @property
    def session_id(self):
       if self._ncc_connection is not None and  self._ncc_connection._session is not None:
            return self._ncc_connection.session_id

    @property
    def is_inactive(self):
        return self._ncc_connection is None or not self._ncc_connection.connected or not self._ncc_connection._session._transport.is_active()


    @property
    def connection(self):

        try:
            if self.is_inactive:
                if self.session_id:
                    LOG.debug("Existing session id {} is not active, closing and reconnecting".format(self.session_id))
                try:
                    self.close()
                except TransportError:
                    pass
                finally:
                    self._ncc_connection = self._connect(self.context)

        except Exception as e:
            if isinstance(e,TimeoutExpiredError) or isinstance(e,SSHError) or isinstance(e,SessionCloseError):
                LOG.warning(
                    "Failed to connect due to '{}', connection will be attempted again in subsequent iterations".format(
                        e))
                self.context.alive = False
            else:
                LOG.exception(e)

        return self._ncc_connection

    def _connect(self, context):
        port = context.yang_port

        return manager.connect(
            host=context.host, port=port,
            username=context.username, password=context.password,
            hostkey_verify=False,
            device_params={'name': "iosxe"}, timeout=context.nc_timeout,
            allow_agent=False, look_for_keys=False)

    def close(self):
        if self._ncc_connection is not None:
            self._ncc_connection.close_session()
            self._ncc_connection = None
        self.start = time.time()

    def get(self,filter='',entity=None,action=None):
        if self.context.alive and self.connection is not None:
            with PrometheusMonitor().yang_operation_duration.labels(device=self.context.host, entity=entity,
                                                                      action=action).time():
                return self.connection.get(filter=('subtree', filter))
        else :
            PrometheusMonitor().device_unreachable.labels(device=self.context.host, entity=entity,
                                                               action=action).inc()
            raise DeviceUnreachable(host=self.context.host)


    def edit_config(self,config='',target='running',entity=None,action=None):
        if self.context.alive and self.connection is not None:
            with PrometheusMonitor().yang_operation_duration.labels(device=self.context.host,entity=entity,action=action).time():
                return self.connection.edit_config(target=target, config=config)
        else :
            PrometheusMonitor().device_unreachable.labels(device=self.context.host, entity=entity,
                                                          action=action).inc()
            raise DeviceUnreachable(host=self.context.host)


    def rpc(self,command,entity=None,action=None):
        if self.context.alive and self.connection is not None:
            with PrometheusMonitor().yang_operation_duration.labels(device=self.context.host, entity=entity,action=action).time():
                return self.connection.dispatch(to_ele(command))
        else :
            PrometheusMonitor().device_unreachable.labels(device=self.context.host, entity=entity,
                                                          action=action).inc()
            raise DeviceUnreachable(host=self.context.host)










