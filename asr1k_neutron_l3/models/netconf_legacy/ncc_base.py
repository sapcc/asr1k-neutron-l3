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

from oslo_log import log as logging
from oslo_utils import importutils

import ncclient
from asr1k_neutron_l3.models.netconf import ConnectionPool
from ncclient.operations.rpc import RPCError


LOG = logging.getLogger(__name__)


class NccBase(object):

    def __init__(self, base):
        self.base = base

        self._ncc_connection = None

    def _edit_running_config(self, context, conf_str, snippet):
        connection = self._get_connection(context)

        try:
            rpc_obj = connection.edit_config(config=conf_str)

            return rpc_obj

            #self._check_response(rpc_obj, snippet, conf_str=conf_str)
        except RPCError as e:
            return e
        except Exception as e:
            raise e
        finally:
            connection.close()

    def _get_connection(self, context):
        return ConnectionPool().get_connection(context.host,legacy=True)

    def _check_response(self, rpc_obj, snippet_name, conf_str=None):
        LOG.debug("RPCReply for %(snippet_name)s is %(rpc_obj)s",
                  {'snippet_name': snippet_name, 'rpc_obj': rpc_obj.xml})
        xml_str = rpc_obj.xml
        if "<ok />" in xml_str:
            # LOG.debug("RPCReply for %s is OK", snippet_name)
            LOG.info("%s was successfully executed", snippet_name)
            return True
        # Not Ok, we throw a ConfigurationException
        e_type = rpc_obj._root[0][0].text
        e_tag = rpc_obj._root[0][1].text
        params = {'snippet': snippet_name, 'type': e_type, 'tag': e_tag,
                  'confstr': conf_str}
        raise Exception(**params)
