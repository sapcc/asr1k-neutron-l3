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

from threading import Lock
from asr1k_neutron_l3.models.asr1k_pair import ASR1KPair
from asr1k_neutron_l3.common.asr1k_exceptions import DeviceUnreachable

from ncclient import manager
from oslo_log import log as logging
from oslo_config import cfg
from paramiko.client import SSHClient,AutoAddPolicy
from ncclient.operations.errors import TimeoutExpiredError
from ncclient.transport.errors import SSHError

LOG = logging.getLogger(__name__)


def ssh_connect(context,legacy):
    connect = None
    try:
        if legacy:
            port = context.legacy_port
        else:
            port = context.yang_port
        #LOG.debug("Checking device connectivity.")
        client = SSHClient()
        client.set_missing_host_key_policy(AutoAddPolicy())
        connect = client.connect(context.host,port=port,username=context.username,password=context.password,timeout=0.5)
        #LOG.debug("Connection to {} on port {} successful".format(context.host,port))
    except Exception as e:
        if isinstance(e,socket.error):
            return False
    finally:
        if connect is not None:
            connect.close()


    return True

def check_devices():
    for context in ASR1KPair().contexts:
        device_reachable = ssh_connect(context, False) and ssh_connect(context, True)
        if not device_reachable:
            context.alive = device_reachable
            LOG.debug("Device {} is not reachable, marked as dead".format(context.host))
        else:
            if not context.alive:
                context.alive = device_reachable
                LOG.debug("Device {} is now reachable, marked as alive".format(context.host))

class  ConnectionPoolExhausted(Exception):
    pass

class ConnectionManager(object):

    def __init__(self,context=None, legacy=False):
        self.context = context
        self.legacy  = False

    def __enter__(self):
        self.connection = ConnectionPool().pop_connection(context=self.context,legacy=self.legacy)
        return self.connection

    def __exit__(self, type, value, traceback):
        ConnectionPool().push_connection(self.connection,legacy=self.legacy)


class ConnectionPool(object):
    __instance = None



    def __new__(cls):
        if ConnectionPool.__instance is None:
            ConnectionPool.__instance = object.__new__(cls)
            ConnectionPool.__instance.__setup()

        return ConnectionPool.__instance

    def _key(self,context,legacy):
        key = '{}_yang'.format(context.host)
        if legacy :
            key = '{}_legacy'.format(context.host)

        return key

    def __setup(self):
        self.lock = Lock()
        self.yang_pool_size = cfg.CONF.asr1k.yang_connection_pool_size
        self.legacy_pool_size = cfg.CONF.asr1k.legacy_connection_pool_size
        self.pair_config = ASR1KPair()

        self.devices = {}

        LOG.debug("Initializing connection pool of yang pool size {}, legacy pool size {}".format(self.yang_pool_size,self.legacy_pool_size))

        for context in self.pair_config.contexts:
            yang = []
            legacy = []
            for i in range(self.yang_pool_size):
                yang.append(YangConnection(context))
            for i in range(self.legacy_pool_size):
                legacy.append(LegacyConnection(context))

            self.devices['{}_yang'.format(context.host)] = yang
            self.devices['{}_legacy'.format(context.host)] = legacy

    def _retry_if_exhausted(self,exception):
        return isinstance(exception,ConnectionPoolExhausted)

    @retry(stop_max_attempt_number=5, wait_fixed=100,retry_on_exception=_retry_if_exhausted)
    def pop_connection(self,context=None, legacy=False):
        key = self._key(context,legacy)
        pool = self.devices.get(key)

        if len(pool) == 0 :
            raise ConnectionPoolExhausted()

        connection = pool.pop(0)

        LOG.debug('Using connection {} aged {} pool now {}'.format(connection.session_id, connection.age, len(pool)))
        return connection

    def push_connection(self,connection,legacy=False):
        key = self._key(connection.context,legacy)
        if legacy:
            self.devices.get(key).append(LegacyConnection(connection.context))
        else:
            pool = self.devices.get(key)
            LOG.debug('Returning connection {} aged {} to pool of size {}'.format(connection.session_id,connection.age,len(pool)))
            pool.append(connection)


    def get_connection(self,context,legacy=False):

        key = self._key(context,legacy)

        connection = self.devices.get(key).pop(0)

        # if connection.age >  cfg.CONF.asr1k.connection_max_age:
        #     connection.close()
        #
        if legacy:
            self.devices.get(key).append(LegacyConnection(context))
        else:
            LOG.debug('Using connection {} aged {}'.format(connection.session_id,connection.age))
            self.devices.get(key).append(connection)

        if connection is None:
            raise Exception('No connection can be found for {}'.format(key))

        return connection




class NCConnection(object):

    def __init__(self, context,legacy=False):

        self.context = context
        self.legacy  = legacy
        self._ncc_connection = None
        self.start = time.time()

    @property
    def age(self):
        return time.time() - self.start

    @property
    def session_id(self):
       if self._ncc_connection is not None and  self._ncc_connection._session is not None:
            return self._ncc_connection.session_id
    @property
    def connection(self):

        try:
            if self._ncc_connection is None or not self._ncc_connection.connected:
                self._ncc_connection = self._connect(self.context)
        except Exception as e:
            if isinstance(e,TimeoutExpiredError):
                self.context.alive = False
            elif isinstance(e, SSHError):
                self.context.alive = False
            raise e


        return self._ncc_connection


    def _connect(self, context):

        port = context.yang_port

        if self.legacy :
            port = context.legacy_port

        return manager.connect(
            host=context.host, port=port,
            username=context.username, password=context.password,
            hostkey_verify=False,
            device_params={'name': "iosxe"}, timeout=context.nc_timeout,
            allow_agent=False, look_for_keys=False)



    def close(self):
        if self._ncc_connection is not None and self._ncc_connection.connected:
            #close session is not playing nicely with eventlet so try paramiko directly
            if self._ncc_connection._session is not None and self._ncc_connection._session._transport is not None:
                self._ncc_connection._session._transport.close()
                LOG.debug("Closed {} session {} aged {}".format(self.__class__.__name__,self._ncc_connection.session_id, self.age))

        self._ncc_connection = None
        self.start = time.time()

    def get(self,filter=''):
        if self.context.alive:
            return self.connection.get(filter=('subtree', filter))
        else :
            raise DeviceUnreachable(host=self.context.host)


    def edit_config(self,config='',target='running'):
        # with self.connection.locked(target):
        if self.context.alive:
            return self.connection.edit_config(target=target, config=config)
        else :
            raise DeviceUnreachable(host=self.context.host)

class YangConnection(NCConnection):
    def __init__(self,context):
        super(YangConnection,self).__init__(context)

class LegacyConnection(NCConnection):
    def __init__(self,context):
        super(LegacyConnection,self).__init__(context,legacy=True)