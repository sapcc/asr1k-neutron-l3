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

import six
from oslo_log import log as logging

from asr1k_neutron_l3.models import asr1k_pair

LOG = logging.getLogger(__name__)


def excute_on_pair(method):
    @six.wraps(method)
    def wrapper(*args, **kwargs):

        result = PairResponse()

        for context in asr1k_pair.ASR1KPair().contexts:
            kwargs['context'] = context
            try:
                response = RestReponse(method(*args, **kwargs))
                result.add_response(context, response)
            except Exception as e:
                LOG.exception(e)

        return result

    return wrapper


class PairResponse(object):

    def __init__(self):
        self.responses = {}

    def add_response(self, context, response):
        self.responses[context.host] = response


class RestReponse(object):

    def __init__(self, raw_response):
        self.raw_response = raw_response


class Base(object):

    def __init__(self):
        self.contexts = asr1k_pair.ASR1KPair().contexts
