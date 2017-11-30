from oslo_log import log as logging
from oslo_utils import importutils

ncclient = importutils.try_import('ncclient')
manager = importutils.try_import('ncclient.manager')

LOG = logging.getLogger(__name__)


class NccBase(object):
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

    def __init__(self, base):
        self.base = base

        self._ncc_connection = None

    def _edit_running_config(self, context, conf_str, snippet):
        conn = self._get_connection(context)

        try:
            rpc_obj = conn.edit_config(target='running', config=conf_str)
            self._check_response(rpc_obj, snippet, conf_str=conf_str)
        except Exception as e:

            raise e

    def _get_connection(self, context):
        try:
            if not (self._ncc_connection and self._ncc_connection.connected):
                self._ncc_connection = manager.connect(
                    host=context.host, port=context.nc_port,
                    username=context.username, password=context.password,
                    device_params={'name': "csr"}, timeout=context.nc_timeout)


        except Exception as e:
            raise e

        return self._ncc_connection

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
