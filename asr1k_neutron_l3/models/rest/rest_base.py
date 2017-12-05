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

import json
import requests
import six
import time
import pprint
from oslo_log import log as logging
from asr1k_neutron_l3.models import asr1k_pair


LOG = logging.getLogger(__name__)


class JSONDict(dict):
    def __str__(self):
        return json.dumps(self, sort_keys=False)

class execute_on_pair(object):

    def __init__(self, return_raw=False):
        self.return_raw = return_raw

    def __call__(self, method):
        @six.wraps(method)
        def wrapper(*args, **kwargs):

            result = PairResult()
            if not self.return_raw:
                for context in asr1k_pair.ASR1KPair().contexts:
                    kwargs['context'] = context
                    try:
                         response = method(*args, **kwargs)
                         result.append(context,response)

                    except Exception as e:
                        LOG.exception(e)
                        raise e
            else:
                # Context passed explitly execute once and return
                # base result
                if  kwargs.get('context') is None:
                    kwargs['context'] = asr1k_pair.ASR1KPair().contexts[0]

                try:
                    response = method(*args, **kwargs)
                    result = response

                except Exception as e:
                    LOG.exception(e)

            LOG.debug(str(result))

            return result

        return wrapper


class PairResult(object,):

    def __init__(self,success_statuses=list(range(200,299))):

        self.success_statuses = success_statuses

        self.result = {}
        self.is_http_response= True

    def append(self, context, response):

        if isinstance(response,requests.Response):
            response = RestResponse(response)
            self.result[context.host] = response
        elif isinstance(response, list):
            for r in response:
                if isinstance(r,requests.Response):
                    self.result[context.host] = r
        else:
            self.is_http_response= False
            self.result[context.host] = response

    @property
    def succeeded(self):
        return len(self.errors) > 0

    @property
    def errors(self):
        copy = self.result.copy()
        for key in copy.keys():
            response = self.result.get(key)
            if response.status_code  in self.success_statuses:
                copy.pop(key,None)
        return copy

    @property
    def successful(self):
        copy = self.result.copy()
        for key in copy.keys():
            response = self.result.get(key)
            if response.status_code  not in self.success_statuses:
                copy.pop(key,None)
        return copy

    def __str__(self):
        if self.is_http_response:
            json = {}
            for key in self.result.keys():
                response = self.result.get(key)

                json[key]={"status":response.status_code,"json":response.json}

            return pprint.pformat(json)
        else:
            return str(self.result)

class RestResponse(object):

    def __init__(self, raw_response):
        self.raw_response = raw_response

    @property
    def status_code(self):
        return self.raw_response.status_code

    @property
    def json(self):
        try:
            json = self.raw_response.json()
        except:
            json = {}
        return json

    def __str__(self):
        return pprint.pformat(self.json)



class wrap_rest_retry_on_lock(object):

    def __init__(self, retry_interval=0.5, max_retries=10):
        self.retry_interval = retry_interval
        self.max_retries = max_retries

        super(wrap_rest_retry_on_lock, self).__init__()

    def __call__(self, f):

        @six.wraps(f)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < self.max_retries:
                try:
                    result = f(*args, **kwargs)

                    if result is not None:
                        if result.status_code == 409 and 'lock-denied' in self._error_tags(result):
                            time.sleep(self.retry_interval)
                            retries += 1
                    else:
                        return result

                except Exception as e:
                    raise e

        return wrapper

    def _error_tags(self, response):
        result = []
        try:
            LOG.debug(response.json())
            for error in response.json().get('errors', {}).get('error', []):
                result.append(error.get('error-tag'))
        except:
            pass

        LOG.debug(result)

        return result


class RestBase(object):
    base_path = "/restconf/data"

    def __parameters__(self):
        return {}

    def __init__(self, **kwargs):
        id_field = "id"
        if self.__parameters__():
            for param in self.__parameters__():
                key = param.get('key')
                default = param.get('default')
                mandatory = param.get('mandatory', False)

                # use first id field, there can be only one
                if param.get('id', False) and id_field == 'id':
                    id_field = key

                value = kwargs.get(key, default)

                if mandatory and value is None:
                    raise Exception("Missing mandatory paramter {}".format(key))
                else:
                    setattr(self, key, value)

            self.__id_function__(id_field, **kwargs)

    def __id_function__(self, id_field, **kwargs):
        self.id = kwargs.get(id_field)
        if self.id is None:
            raise Exception("ID field {} is None".format(id_field))

    def __str__(self):
        return self.to_data()

    @classmethod
    def from_json(cls, json):
        params = {}
        for param in cls.__parameters__():
            key = param.get('key', "")
            cisco_key = key.replace("_", "-")
            params[key] = json.get(cisco_key)

        return cls(**params)

    @classmethod
    def _get_auth(cls, context):
        return (context.username, context.password)

    @classmethod
    def _make_url(cls, context, path):
        return '{protocol}://{host}:{port}{base}{path}'.format(
            **{'protocol': context.protocol, 'host': context.host, 'port': str(context.port),
               'base': RestBase.base_path, 'path': path})

    @classmethod
    @execute_on_pair(return_raw=True)
    def get_all(cls, context=None, filters={}):
        result = []

        response = requests.get(cls._make_url(context, cls.item_path), auth=cls._get_auth(context),
                                headers=context.headers, verify=not context.insecure)

        try:

            items = dict(response.json())
        except:
            items = {}

        items = items.get(cls.LIST_KEY, [])

        LOG.debug(items)

        for item in items:
            if filters:
                keep = True
                for key in filters.keys():
                    keep = keep and filters.get(key) == item.get(key)

                if keep:
                    result.append(cls.from_json(item))
            else:
                result.append(cls.from_json( item))
        return result

    @classmethod
    @execute_on_pair(return_raw=True)
    def get(cls, id,context=None):
        result = requests.get(cls._make_url(context, cls.item_path) + "=" + str(id), auth=cls._get_auth(context),
                              headers=context.headers, verify=not context.insecure)

        if result.status_code != 200:
            return None
            # raise result.raise_for_status()

        return cls.from_json(result.json().get(cls.LIST_KEY, {}))

    @classmethod
    @execute_on_pair(return_raw=True)
    def exists(cls, id, context=None, **kwargs):
        result = requests.head(cls._make_url(context, cls.item_path.format(**kwargs)) + "=" + str(id),
                               auth=cls._get_auth(context), headers=context.headers, verify=not context.insecure)
        return result.status_code == 200

    def to_data(self):

        dict = self.to_dict()

        return JSONDict(dict).__str__().replace("\"[null]\"", "[null]")


    def _exists(self,context=None):
        result = requests.head(self._make_url(context, self.item_path) + "=" + str(self.id),
                               auth=self._get_auth(context), headers=context.headers,
                               verify=not context.insecure)
        return result.status_code == 200

    @execute_on_pair()
    def create(self,context=None):
        LOG.debug(self.to_data())
        return requests.post(self._make_url(context, self.list_path), auth=self._get_auth(context),
                             data=self.to_data(), headers=context.headers, verify=not context.insecure)

    @execute_on_pair()
    def update(self, context=None,method='patch'):

        if not self._exists(context):
            return self.create()
        else:
            if method not in ['patch', 'put']:
                raise Exception('Update should be called with method = put | patch')

            LOG.debug(self.to_data())
            request_method = getattr(requests, method)
            if callable(request_method):
                return request_method(self._make_url(context, self.item_path) + "=" + str(self.id),
                                      auth=self._get_auth(context), data=self.to_data(),
                                      headers=context.headers, verify=not context.insecure)
            else:
                raise Exception(
                    'put | patch not callable, this should not happen if you have installed pythoin requests properly')

    @execute_on_pair()
    @wrap_rest_retry_on_lock()
    def delete(self,context=None):
        if self._exists(context):
            return requests.delete(self._make_url(context, self.item_path) + "=" + str(self.id),
                                   auth=self._get_auth(context), headers=context.headers,
                                   verify=not context.insecure)

    # @property
    # def _type_safe_id(self):
    #     _id = self.id
    #
    #     LOG.debug("******* id ")
    #     LOG.debug(_id)
    #
    #     if self.id is None:
    #         _id = ""
    #
    #     return urllib.quote(str(_id))
