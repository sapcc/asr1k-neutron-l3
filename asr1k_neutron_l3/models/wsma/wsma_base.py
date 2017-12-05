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

import requests

from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class WSMABase(object):

    @classmethod
    def _get_auth(cls, context):
        return (context.username, context.password)

    @classmethod
    def _make_url(cls, context):
        return '{protocol}://{host}:{port}/wsma'.format(
            **{'protocol': context.protocol, 'host': context.host, 'port': str(context.port)})

    def __init__(self, base):
        self.base = base


    def create(self,context):
        LOG.debug(self.to_data())
        return requests.post(self._make_url(context), auth=self._get_auth(context), data=self.to_data(),
                             headers=context.headers, verify=not context.insecure)

    def to_data(self):
        pass
