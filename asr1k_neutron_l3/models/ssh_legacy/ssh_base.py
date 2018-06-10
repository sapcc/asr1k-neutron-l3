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


from asr1k_neutron_l3.models.connection import ConnectionManager
from ncclient.operations.rpc import RPCError

LOG = logging.getLogger(__name__)


class SSHBase(object):

    def __init__(self, base):
        self.base = base


    def exists(self,context,config,matches,results=-1):

        # return False
        with ConnectionManager(context=context,legacy=True) as manager:
            try:
                result = manager.run_cli_command(config)



                if result is  not None:
                    exists = True

                    if results >=0 and len(result)!= results:
                        return False

                    reg_lst = []
                    for raw_regex in matches:
                        reg_lst.append(re.compile(raw_regex))

                    for l in result :
                        exists = exists and any(compiled_reg.match(l) for compiled_reg in reg_lst)

                    return  exists
            except Exception as e:
                LOG.exception(e)
                raise e
            return False



    def _edit_running_config(self, context, config, snippet, accept_failure=False):

        with ConnectionManager(context=context,legacy=True) as manager:
            try:
                result = manager.edit_config(config)

            except RPCError as e:
                if not accept_failure:
                    raise e
            except BaseException as e:
                print e
                LOG.exception(e)
                raise e

