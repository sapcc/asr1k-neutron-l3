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
from asr1k_neutron_l3.common.instrument import instrument

from ncclient import manager
from oslo_log import log as logging
from oslo_config import cfg
from oslo_service import loopingcall
from paramiko.client import SSHClient,AutoAddPolicy
import paramiko
from ncclient.operations.errors import TimeoutExpiredError
from ncclient.transport.errors import SSHError
from ncclient.transport.errors import SessionCloseError
from ncclient.transport.errors import TransportError

from bs4 import BeautifulSoup as bs

LOG = logging.getLogger(__name__)


def _retry_if_exhausted(exception):
    return isinstance(exception, ConnectionPoolExhausted)

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

class  ConnectionPoolNotInitialized(Exception):
    pass

class ConnectionManager(object):

    def __init__(self,context=None, legacy=False):
        self.context = context
        self.legacy  = legacy

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
        else:
            ConnectionPool.__instance.__check_initialized()

        return ConnectionPool.__instance

    def __init__(self):
        pass



    def _ensure_connections_aged(self):

        try:
            for context in self.pair_config.contexts:
                yang = self.devices[self._key(context, False)]

                for connection in yang:

                    if connection.age > self.max_age:
                        LOG.debug("***** closing aged connection with session id {} aged {:10.2f}s".format(connection.session_id,connection.age))
                        connection.lock.acquire()
                        connection.close()
                        connection.lock.release()
        except Exception as e:
            LOG.exception(e)


    def _key(self,context,legacy):
        key = '{}_yang'.format(context.host)
        if legacy :
            key = '{}_legacy'.format(context.host)

        return key

    def __check_initialized(self):
        if not hasattr(self, 'initialized'):
            raise ConnectionPoolNotInitialized("Please ensure pool is before first use initilized with `ConnectionPool().initialiase(self, yang_connection_pool_size=0,legacy_connection_pool_size=0,max_age=0)`")


    def initialiase(self, yang_connection_pool_size=0,legacy_connection_pool_size=0,max_age=0):

        try:

            yang_pool_size = min(yang_connection_pool_size, asr1k_constants.MAX_CONNECTIONS)

            if yang_pool_size < yang_connection_pool_size:
                LOG.warning(
                    "The yang connectopm pool size has been reduced to the system maximum its now {}".format(yang_pool_size))

            self.yang_pool_size = yang_pool_size
            self.legacy_pool_size = legacy_connection_pool_size
            self.max_age = max_age
            self.pair_config = ASR1KPair()

            self.devices = {}

            LOG.debug("Initializing connection pool of yang pool size {}, legacy pool size {}".format(self.yang_pool_size,self.legacy_pool_size))

            for context in self.pair_config.contexts:
                yang = []
                legacy = []
                for i in range(self.yang_pool_size):
                    yang.append(YangConnection(context,id=i))
                for i in range(self.legacy_pool_size):
                    legacy.append(SSHConnection(context,id=i))

                self.devices[self._key(context,False)] = yang
                self.devices[self._key(context,True)] = legacy

            if self.max_age > 0:
                LOG.debug("Setting up looping call to close connections older than {} seconds".format(self.max_age))
                self.monitor = loopingcall.FixedIntervalLoopingCall(
                    self._ensure_connections_aged)
                self.monitor.start(interval=self.max_age)

            self.initialized = True
        except Exception as e:
            LOG.exception(e)



    @retry(stop_max_attempt_number=5, wait_fixed=100,retry_on_exception=_retry_if_exhausted)
    def pop_connection(self,context=None, legacy=False):
        key = self._key(context,legacy)
        pool = self.devices.get(key)

        if len(pool) == 0 :
            raise ConnectionPoolExhausted()

        connection = pool.pop(0)
        connection.lock.acquire()

        # if legacy:
        #     self.devices.get(key).append(LegacyConnection(connection.context))
        # else:

        pool = self.devices.get(key)
        pool.append(connection)

        return connection

    def push_connection(self,connection,legacy=False):
        connection.lock.release()



    def get_connection(self,context,legacy=False):

        key = self._key(context,legacy)

        connection = self.devices.get(key).pop(0)

        # if connection.age >  self.max_age
        #     connection.close()
        #
        # if legacy:
        #     self.devices.get(key).append(LegacyConnection(context))
        # else:

        self.devices.get(key).append(connection)

        if connection is None:
            raise Exception('No connection can be found for {}'.format(key))

        return connection




class NCConnection(object):

    def __init__(self, context,legacy=False,id=0):
        self.lock = Lock()
        self.context = context
        self.legacy  = legacy
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

        if self.legacy :
            port = context.legacy_port

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

    def get(self,filter=''):
        if self.context.alive and self.connection is not None:
            return self.connection.get(filter=('subtree', filter))
        else :
            raise DeviceUnreachable(host=self.context.host)


    def edit_config(self,config='',target='running'):
        if self.context.alive and self.connection is not None:
            return self.connection.edit_config(target=target, config=config)
        else :
            raise DeviceUnreachable(host=self.context.host)

class YangConnection(NCConnection):
    def __init__(self,context,id=0):
        super(YangConnection,self).__init__(context,id=id)

# class LegacyConnection(NCConnection):
#     def __init__(self,context,id=0):
#         super(LegacyConnection,self).__init__(context,legacy=True,id=id)


class SSHConnection(object):

    PROT = 'ssh'
    EOM = ']]>]]>'
    BUF = 1024 * 1024

    READ_SOAP12 = '''
<?xml version="1.0" encoding="UTF-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <request xmlns="urn:cisco:wsma-exec" correlator="c-1">
      <execCLI>
        <cmd>{}</cmd>
      </execCLI>
    </request>
  </soap12:Body>
</soap12:Envelope>
]]>]]>'''



    def __init__(self, context,id=0):
        self.lock = Lock()
        self.context = context

        self._ssh_transport = None
        self._wsma_transport = None
        self._ssh_channel = None
        self._wsma_channel = None
        self.start = time.time()
        self.id = "{}-{}".format(context.host,id)

    @property
    def age(self):
        return time.time() - self.start

    @property
    def session_id(self):
       if not self.is_inactive and self._ssh_channel is not None and  self._ssh_transport is not None:
            return self._ssh_transport.session_id

    @property
    def is_inactive(self):
        if self._ssh_channel is None or self._wsma_channel is None or self._ssh_transport is None or self._wsma_transport is None:
            return True
        try:
            self._ssh_channel.send("show whoami \r\n")
            self._wsma_channel.sendall(self.READ_SOAP12.format("show whoami"))
            return False
        except BaseException as e :
            return True



    @property
    def connection(self):
        try:
            if self.is_inactive:
                if self.session_id:
                    LOG.debug("Existing session id {} is not active, closing and reconnecting".format(self.session_id))
                try:
                    self.close()
                except BaseException:
                    pass
                finally:
                    self._connect(self.context)

        except BaseException as e:
            if isinstance(e,TimeoutExpiredError) or isinstance(e,SSHError) or isinstance(e,SessionCloseError):
                LOG.warning(
                    "Failed to connect due to '{}', connection will be attempted again in subsequent iterations".format(
                        e))
                self.context.alive = False
            else:
                LOG.exception(e)


        return self._ssh_channel

    @property
    def wsma_connection(self):
        self.connection
        return self._wsma_channel


    def _connect(self, context):
        port = context.legacy_port

        # client = SSHClient()
        # client.set_missing_host_key_policy(AutoAddPolicy())
        # client.connect(context.host, port=port, username=context.username, password=context.password, timeout=0.5)
        #
        # ssh_channel = client.invoke_shell()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((context.host, port))
        ssh_transport = paramiko.Transport(sock)
        try:
            ssh_transport.connect(username=context.username, password=context.password)
        except paramiko.AuthenticationException:
            print("SSH Authentication failed.")

        wsma_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        wsma_sock.connect((context.host, port))
        wsma_transport = paramiko.Transport(wsma_sock)
        try:
            wsma_transport.connect(username=context.username, password=context.password)
        except paramiko.AuthenticationException:
            print("SSH Authentication failed.")




        ssh_channel = ssh_transport.open_session()
        ssh_channel.get_pty()
        ssh_channel.set_name('ssh')
        ssh_channel.invoke_shell()

        wsma_channel = wsma_transport.open_session()
        wsma_channel.set_name('wsma')
        wsma_channel.invoke_subsystem('wsma')
        self._wsma_reply(wsma_channel)

        # self._ssh_client = client
        self._ssh_transport = ssh_transport
        self._ssh_channel = ssh_channel
        self._wsma_transport = wsma_channel
        self._wsma_channel = wsma_channel


    def close(self):

        if self._ssh_transport is not None :
            try:
                self._ssh_transport.close()
            except BaseException:
                pass

        if self._wsma_transport is not None :
            try:
                self._wsma_transport.close()
            except BaseException:
                pass



        self._ssh_transport = None
        self._ssh_channel = None
        self._wsma_channel = None
        self.start = time.time()

    def get(self,filter=''):
        raise NotImplementedError()

    @instrument()
    def run_cli_command(self, command):

        self.wsma_connection.sendall(self.READ_SOAP12.format(command))

        return self._wsma_reply(self.wsma_connection)

    def _wsma_reply(self,channel):

        bytes = u''
        while bytes.find(self.EOM) == -1:
            bytes += channel.recv(self.BUF).decode('utf-8')
        bytes = bytes.replace(self.EOM, '')

        result = []
        return_text = bs(bytes, 'lxml').find('text')
        if return_text is not None:
            raw = bs(bytes, 'lxml').find('text').contents[0].splitlines()

            for l in raw:
                if len(l.strip(" "))>0:
                    result.append(l)
        else:
            return None

        return result



    @instrument()
    def edit_config(self,config='',target='running'):

        if self.context.alive and self.connection is not None and not self.is_inactive:
            self.connection.send("config t \r\n")

            if isinstance(config,list):
                for cmd in config:
                    self.connection.send(cmd+"\r\n")
            elif isinstance(config,str):
                self.connection.send(config+"\r\n")

            self.connection.send("end \r\n")


        else :
            raise DeviceUnreachable(host=self.context.host)


    # def _get_reply(self, channel):
    #     bytes = u''
    #     while bytes.find(eom)==-1:
    #         bytes += channel.recv(65535).decode('utf-8')
    #     return bytes