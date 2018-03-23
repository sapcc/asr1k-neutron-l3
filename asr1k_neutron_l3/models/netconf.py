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

from asr1k_neutron_l3.models.asr1k_pair import ASR1KPair
from asr1k_neutron_l3.common.asr1k_exceptions import DeviceUnreachable

from ncclient import manager
from oslo_log import log as logging
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

class ConnectionPool(object):
    __instance = None

    def __new__(cls):
        if ConnectionPool.__instance is None:
            ConnectionPool.__instance = object.__new__(cls)
            ConnectionPool.__instance.__setup()

        return ConnectionPool.__instance


    def __setup(self):
        self.pair_config = ASR1KPair()

        self.devices = {}

        for context in self.pair_config.contexts:
            self.devices['{}_yang'.format(context.host)] = YangConnection(context)
            self.devices['{}_legacy'.format(context.host)] = LegacyConnection(context)

    def get_connection(self,host,legacy=False):
        key = '{}_yang'.format(host)
        if legacy :
            key = '{}_legacy'.format(host)

        connection = self.devices.get(key)

        if connection is None:
            raise Exception('No connection can be found for {}'.format(key))

        return connection


class NCConnection(object):

    def __init__(self, context,legacy=False):

        self.context = context
        self.legacy  = legacy
        self._ncc_connection = None


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
            device_params={'name': "default"}, timeout=context.nc_timeout,
            allow_agent=False, look_for_keys=False)

    def close(self):
        if self._ncc_connection is not None and self._ncc_connection.connected:
            #close session is not playing nicely with eventlet so try paramiko directly
            LOG.debug("Closing session {} to {}  legacy = {} at the request of the client".format(
                self._ncc_connection.session_id, self.context.host, self.legacy))
            if self._ncc_connection._session is not None and self._ncc_connection._session._transport is not None:
                self._ncc_connection._session._transport.close()
            self._ncc_connection = None


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