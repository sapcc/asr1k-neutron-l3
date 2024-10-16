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

from asr1k_neutron_l3.models import asr1k_pair

LOG = logging.getLogger(__name__)


class Base(object):
    def __init__(self, **kwargs):
        self.contexts = asr1k_pair.ASR1KPair().contexts

    @property
    def _rest_definition(self):
        return self.__rest_definition

    @_rest_definition.setter
    def _rest_definition(self, rest_definition):
        self.__rest_definition = rest_definition

    def update(self):
        return self._rest_definition.update()

    def delete(self):
        return self._rest_definition.delete()

    def diff(self, should_be_none=False):
        return self._rest_definition.diff(should_be_none=should_be_none)

    def init_config(self):
        return self._rest_definition.init_config()
