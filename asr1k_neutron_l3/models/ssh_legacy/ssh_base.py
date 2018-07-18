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
import time
import re
from oslo_log import log as logging
from oslo_utils import importutils


from asr1k_neutron_l3.common.prometheus_monitor import PrometheusMonitor
from asr1k_neutron_l3.models.connection import ConnectionManager
from ncclient.operations.rpc import RPCError
from paramiko.ssh_exception import SSHException

LOG = logging.getLogger(__name__)


class SSHBase(object):

    def __init__(self, base):
        self.base = base


    def execute(self,context,cmd):
        # return False
        with ConnectionManager(context=context, legacy=True) as manager:
            try:
                return manager.run_cli_command(cmd)

            except SSHException as e:
                self._check_banner_exception(e)
            except Exception as e:
                LOG.exception(e)
                #issue with manager return None and close
                LOG.warning("Failed to execute command on connection, will return None and close connections")
                manager.close()
                return []





    def _edit_running_config(self, context, config, snippet, accept_failure=False):

        with ConnectionManager(context=context,legacy=True) as manager:
            try:
                result = manager.edit_config(config)

            except SSHException as e:
                self._check_banner_exception(e)
            except RPCError as e:
                if not accept_failure:
                    raise e
            except BaseException as e:
                LOG.exception(e)
                raise e

    def _check_banner_exception(self,e):
        if str(e).startswith("Error reading SSH protocol banner"):
            PrometheusMonitor().ssh_banner_errors.inc()

        LOG.exception(e)
        raise e
