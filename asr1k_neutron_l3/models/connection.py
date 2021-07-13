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
import os

if not os.environ.get('DISABLE_EVENTLET_PATCHING'):
    import eventlet
    eventlet.monkey_patch()

import datetime
from retrying import retry
from six.moves import urllib
import socket
import time
import re

from threading import Lock
from asr1k_neutron_l3.models.asr1k_pair import ASR1KPair
from asr1k_neutron_l3.common.asr1k_exceptions import DeviceUnreachable, CapabilityNotFoundException
from asr1k_neutron_l3.common import asr1k_constants
from asr1k_neutron_l3.common.prometheus_monitor import PrometheusMonitor

from ncclient import manager
from ncclient.xml_ import to_ele, new_ele, to_xml
from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import loopingcall

import paramiko
from ncclient.operations.errors import TimeoutExpiredError
from ncclient.operations import util
from ncclient.transport.errors import SSHError
from ncclient.transport.errors import SessionCloseError
from ncclient.transport.errors import TransportError

LOG = logging.getLogger(__name__)


def _retry_if_exhausted(exception):
    return isinstance(exception, ConnectionPoolExhausted)


def ssh_connect(context):
    connect = None
    try:
        port = context.yang_port
        # LOG.debug("Checking device connectivity.")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((context.host, port))
        ssh_transport = paramiko.Transport(sock)
        ssh_transport.close()
        # LOG.debug("Connection to {} on port {} successful".format(context.host,port))
    except Exception as e:
        if isinstance(e, socket.error):
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
        if info and not info.get('enabled'):
            admin_up = False

        alive = device_reachable and admin_up

        context.mark_alive(alive)
        LOG.debug("Device {} reachable {} and agent enabled {}, marked as {}"
                  "".format(context.host, device_reachable, admin_up, "alive" if alive else "dead"))


class ConnectionPoolExhausted(Exception):
    pass


class ConnectionPoolNotInitialized(Exception):
    pass


class ConnectionManager(object):
    def __init__(self, context=None):
        self.context = context

    def __enter__(self):
        self.connection = ConnectionPool().pop_connection(context=self.context)
        return self.connection

    def __exit__(self, type, value, traceback):
        ConnectionPool().push_connection(self.connection, context=self.context)


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

    def __check_initialized(self):
        if not hasattr(self, 'initialized'):
            msg = ("Please ensure pool is before first use initilized with "
                   "`ConnectionPool().initialise(self, yang_connection_pool_size=0,max_age=0)`")
            raise ConnectionPoolNotInitialized(msg)

    def initialise(self, yang_connection_pool_size=0, max_age=0):
        try:
            yang_pool_size = min(yang_connection_pool_size, asr1k_constants.MAX_CONNECTIONS)

            if yang_pool_size < yang_connection_pool_size:
                LOG.warning("The yang connection pool size has been reduced to the system maximum its now {}"
                            "".format(yang_pool_size))

            self.yang_pool_size = yang_pool_size
            self.pair_config = ASR1KPair()
            self.devices = {}

            LOG.info("Initializing connection pool with yang pool size {}".format(self.yang_pool_size))

            for context in self.pair_config.contexts:
                yang = []

                for i in range(self.yang_pool_size):
                    yang.append(YangConnection(
                        context, id=i, max_age=max_age))

                self.devices[context.host] = yang

            self.initialized = True
        except Exception as e:
            LOG.exception(e)

    @retry(stop_max_attempt_number=25, wait_fixed=100, retry_on_exception=_retry_if_exhausted)
    def pop_connection(self, context=None):
        pool = self.devices.get(context.host)
        connection = None
        if len(pool) > 0:
            connection = pool.pop(0)

        if connection is None:
            PrometheusMonitor().connection_pool_exhausted.labels(device=context.host).inc()
            raise ConnectionPoolExhausted()

        connection.lock.acquire()

        return connection

    def push_connection(self, connection, context=None):
        connection.lock.release()

        pool = self.devices.get(context.host)
        pool.append(connection)

    def get_connection(self, context):
        connection = self.devices.get(context.host).pop(0)
        self.devices.get(context.host).append(connection)

        if connection is None:
            raise Exception('No connection can be found for {}'.format(context.host))

        return connection


class YangConnection(object):
    def __init__(self, context, id=0, max_age=0):
        self.lock = Lock()
        self.context = context
        self._ncc_connection = None
        self.start = time.time()
        self.max_age = max_age
        self.id = "{}-{}".format(context.host, id)

    def __repr__(self):
        return "<{} to {} at {}>".format(self.__class__.__name__, self.context.host, hex(id(self)))

    @property
    def age(self):
        return time.time() - self.start

    @property
    def session_id(self):
        if self._ncc_connection is not None and self._ncc_connection._session is not None:
            return self._ncc_connection.session_id

    @property
    def is_inactive(self):
        return (self._ncc_connection is None or
                not self._ncc_connection.connected or
                not self._ncc_connection._session._transport.is_active())

    @property
    def is_aged(self):
        return self.max_age > 0 and self.age > self.max_age

    @property
    def connection(self):
        try:
            if self.is_inactive or self.is_aged:
                LOG.debug("Existing session id {} is not active or aged ({:10.2f}s), closing and reconnecting".format(self.session_id, self.age))
                try:
                    with self.lock():
                        self.close()
                except TransportError:
                    pass
                finally:
                    self._ncc_connection = self._connect(self.context)
        except Exception as e:
            if isinstance(e, TimeoutExpiredError) or isinstance(e, SSHError) or isinstance(e, SessionCloseError):
                LOG.warning(
                    "Failed to connect due to '{}', connection will be attempted again in subsequent iterations".format(
                        e))
                self.context.mark_alive(False)
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

    def xpath_get(self, filter='', entity=None, action=None):
        return self._run_yang_cmd(filter=('xpath', filter), source="running", method='get_config',
                                  entity=entity, action=action)

    def get(self, filter='', entity=None, action=None):
        return self._run_yang_cmd(filter=('subtree', filter), method='get', entity=entity, action=action)

    def edit_config(self, config='', target='running', entity=None, action=None):
        return self._run_yang_cmd(config=config, target=target, method='edit_config', entity=entity, action=action)

    def rpc(self, command, entity=None, action=None):
        return self._run_yang_cmd(to_ele(command), method='dispatch', entity=entity, action=action)

    def _run_yang_cmd(self, *args, **kwargs):
        entity = kwargs.pop("entity", None)
        action = kwargs.pop("action", None)
        method = kwargs.pop("method")

        if self.context.alive and self.connection is not None:
            success = False
            if cfg.CONF.asr1k.trace_all_yang_calls or cfg.CONF.asr1k.trace_yang_call_failures:
                call_start = time.time()
            try:
                with PrometheusMonitor().yang_operation_duration.labels(device=self.context.host, entity=entity,
                                                                        action=action).time():
                    data = getattr(self.connection, method)(*args, **kwargs)
                    success = True
                    return data
            except TimeoutExpiredError:
                LOG.error("Timeout for yang operation on device %s method %s entity %s action %s args=%s kwargs=%s",
                          self.context.host, method, entity, action, args, kwargs)
                raise
            finally:
                if cfg.CONF.asr1k.trace_all_yang_calls or \
                        not success and cfg.CONF.asr1k.trace_yang_call_failures:
                    try:
                        duration = time.time() - call_start
                        success = "succeeded" if success else "failed"
                        xml_data = self.gen_xml_from_ncc_call(method=method, args=args, kwargs=kwargs)
                        LOG.debug("YANG call trace %s in %.4fs on %s: %s",
                                  success, duration, self.context.host, xml_data)
                    except Exception as e:
                        LOG.exception(e)
        else:
            PrometheusMonitor().device_unreachable.labels(device=self.context.host, entity=entity,
                                                          action=action).inc()
            raise DeviceUnreachable(host=self.context.host)

    @staticmethod
    def gen_xml_from_ncc_call(method, args, kwargs, compact_output=True):
        """Try to reconstruct xml for ncc call arguments - best effort approach"""
        if method == 'dispatch':
            node = args[0]
        else:
            node = new_ele(method.replace("_", "-"))
        if kwargs.get("source"):
            node.append(util.datastore_or_url("source", kwargs["source"]))
        if kwargs.get("filter"):
            node.append(util.build_filter(kwargs["filter"]))
        if kwargs.get("target"):
            node.append(util.datastore_or_url("target", kwargs["target"]))
        if kwargs.get("config"):
            node.append(to_ele(kwargs["config"]))
        rpc = new_ele("rpc", {"message-id": "yang-trace"})
        rpc.append(node)

        xml = to_xml(rpc)
        if compact_output:
            xml = re.sub(r"\s*\n\s*", "", xml)
        return xml

    def check_capability(self, module, min_revision, baseurl='http://cisco.com/ns/yang/{module}'):
        baseurl = baseurl.format(module=module)
        min_rev_date = datetime.datetime.strptime(min_revision, "%Y-%m-%d")

        if getattr(self.connection, "server_capabilities", None) is None:
            raise DeviceUnreachable(host=self.context.host)

        for url in self.connection.server_capabilities:
            url = url.strip()  # some urls still have spaces and \n around them
            if url.startswith(baseurl + '?'):
                schema = urllib.parse.urlparse(url)
                schema_qs = urllib.parse.parse_qs(schema.query)
                schema_rev_date = datetime.datetime.strptime(schema_qs['revision'][0], "%Y-%m-%d")

                return schema_rev_date >= min_rev_date

        raise CapabilityNotFoundException(host=self.context.host, entity_name=baseurl)
