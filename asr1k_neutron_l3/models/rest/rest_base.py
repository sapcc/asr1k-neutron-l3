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
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class JSONDict(dict):
    def __str__(self):
        return json.dumps(self, sort_keys=False)


class RestStatus(object):

    def __init__(self, response):
        self.response = response
        if response is None:
            raise Exception("A valid 'requests' http response must be provided")

    @property
    def status(self):
        return self.response.status_code

    @property
    def response_as_json(self):
        try:
            return self.response.json()
        except:
            return None

    @property
    def response_as_text(self):
        return self.response.text


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

    def __init__(self, context, **kwargs):
        self.context = context
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
    def from_json(cls, context, json):
        params = {}
        for param in cls.__parameters__():
            key = param.get('key', "")
            cisco_key = key.replace("_", "-")
            params[key] = json.get(cisco_key)

        return cls(context, **params)

    @classmethod
    def _get_auth(cls, context):
        return (context.username, context.password)

    @classmethod
    def _make_url(cls, context, path):
        return '{protocol}://{host}:{port}{base}{path}'.format(
            **{'protocol': context.protocol, 'host': context.host, 'port': str(context.port),
               'base': RestBase.base_path, 'path': path})

    @classmethod
    def get_all(cls, context, filters={}):
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
                    result.append(cls.from_json(context, item))
            else:
                result.append(cls.from_json(context, item))
        return result

    @classmethod
    def get(cls, context, id):
        result = requests.get(cls._make_url(context, cls.item_path) + "=" + str(id), auth=cls._get_auth(context),
                              headers=context.headers, verify=not context.insecure)

        if result.status_code != 200:
            return None
            # raise result.raise_for_status()

        return cls.from_json(context, result.json().get(cls.LIST_KEY, {}))

    # @classmethod
    # def delete(cls,context,id):
    #     if cls.exists(context,id):
    #         result = requests.delete(cls._make_url(context,cls.item_path)+"="+str(id), auth=cls._get_auth(context),headers=context.headers,verify=not context.insecure)
    #         return RestStatus(result)

    @classmethod
    def exists(cls, context, id, **kwargs):
        result = requests.head(cls._make_url(context, cls.item_path.format(**kwargs)) + "=" + str(id),
                               auth=cls._get_auth(context), headers=context.headers, verify=not context.insecure)
        return result.status_code == 200

    def to_data(self):

        dict = self.to_dict()

        return JSONDict(dict).__str__().replace("\"[null]\"", "[null]")

    def _exists(self):
        result = requests.head(self._make_url(self.context, self.item_path) + "=" + str(self.id),
                               auth=self._get_auth(self.context), headers=self.context.headers,
                               verify=not self.context.insecure)
        return result.status_code == 200

    def create(self):
        LOG.debug(self.to_data())
        return requests.post(self._make_url(self.context, self.list_path), auth=self._get_auth(self.context),
                             data=self.to_data(), headers=self.context.headers, verify=not self.context.insecure)

    def update(self, method='patch'):

        if not self._exists():
            return self.create()
        else:
            if method not in ['patch', 'put']:
                raise Exception('Update should be called with method = put | patch')

            LOG.debug(self.to_data())
            request_method = getattr(requests, method)
            if callable(request_method):
                return request_method(self._make_url(self.context, self.item_path) + "=" + str(self.id),
                                      auth=self._get_auth(self.context), data=self.to_data(),
                                      headers=self.context.headers, verify=not self.context.insecure)
            else:
                raise Exception(
                    'put | patch not callable, this should not happen if you have installed pythoin requests properly')

    @wrap_rest_retry_on_lock()
    def delete(self):
        if self._exists():
            return requests.delete(self._make_url(self.context, self.item_path) + "=" + str(self.id),
                                   auth=self._get_auth(self.context), headers=self.context.headers,
                                   verify=not self.context.insecure)

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
