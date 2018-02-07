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
import sys
import six
import time
import traceback
import eventlet
from oslo_log import log as logging
from oslo_utils import importutils
from asr1k_neutron_l3.models import asr1k_pair
from asr1k_neutron_l3.models.netconf import ConnectionPool
from asr1k_neutron_l3.models.netconf_yang import xml_utils
from asr1k_neutron_l3.models.netconf_yang.xml_utils import JsonDict



from ncclient.operations.rpc import RPCError
from ncclient.transport.errors import SessionCloseError
from ncclient.transport.errors import SSHError

LOG = logging.getLogger(__name__)


class NC_OPERATION(object):
    DELETE = 'delete'
    REMOVE = 'remove'
    CREATE = 'create'
    PUT = 'replace'
    PATCH = 'merge'

class classproperty(property):
    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()


class execute_on_pair(object):

    def __init__(self, return_raw=False):
        self.return_raw = return_raw

    def _execute_method(self,*args,**kwargs):
        method = kwargs.pop('_method')
        result = kwargs.pop('_result')

        try:
            response = method(*args, **kwargs)
            # if we wrap in a wrapped method return the
            # base result
            if isinstance(response, PairResult):
                result = response
            else:
                result.append( kwargs.get('context'), response)
        except Exception as e:
            LOG.error(e)
            result.append(kwargs.get('context'), e)

    def __call__(self, method):




        @six.wraps(method)
        def wrapper(*args, **kwargs):

            result = PairResult(args[0].__class__.__name__,method.__name__)
            if not self.return_raw:
                pool = eventlet.GreenPool()
                for context in asr1k_pair.ASR1KPair().contexts:
                    kwargs['context'] = context
                    kwargs['_method'] = method
                    kwargs['_result'] = result

                    pool.spawn_n(self._execute_method,*args,**kwargs)


                pool.waitall()

            else:
                # Context passed explitly execute once and return
                # base result
                if  kwargs.get('context') is None:
                    kwargs['context'] = asr1k_pair.ASR1KPair().contexts[0]

                try:
                    response = method(*args, **kwargs)
                    result = response

                except Exception as e:
                    raise e

            print result

            return result

        return wrapper

class retry_on_failure(object):

    def __init__(self, retry_interval=0.5, max_retries=15,raise_exceptions=True):
        self.retry_interval = retry_interval
        self.max_retries = max_retries
        self.raise_exceptions = raise_exceptions

        super(retry_on_failure, self).__init__()

    def __call__(self, f):

        @six.wraps(f)
        def wrapper(*args, **kwargs):
            retries = 0
            exception = None
            while retries < self.max_retries:
                if retries > 0:
                    LOG.debug("** Retry method {} on {} : {} of {}".format(f.__name__,args[0].__class__.__name__ ,retries,self.max_retries))

                try:
                    result = f(*args, **kwargs)

                    if result is not None and not isinstance(result, PairResult) and not result.ok:
                        time.sleep(self.retry_interval)
                        retries += 1
                    else:
                        return result

                except (RPCError , SessionCloseError,SSHError) as e:
                    # LOG.exception(e)
                    # if e.tag not in  ['in-use',]:
                    #     LOG.exception(e)
                    #     raise e
                    # else:
                    #     LOG.info("Lock detected, will retry if expected")

                    time.sleep(self.retry_interval)
                    retries += 1
                    exception = e

            if exception is not None:
                if self.raise_exceptions:
                    raise exception
                else:
                    return exception

        return wrapper

class PairResult(object, ):

    def __init__(self,entity,action):
        self.entity = entity
        self.action = action
        self.results = {}
        self.errors = {}

    def append(self, context, response):

        if isinstance(response,Exception):
            self.errors[context.host] = response
        else:
            self.results[context.host] = response

    @property
    def success(self):
        (not bool(self.errors) ) and bool(self.results)

    @property
    def error(self):
        bool(self.errors)


    def __str__(self):
        result = "** Pair Result {} : {} ** \n".format(self.entity,self.action)

        if bool(self.results):
            result += "Successful executions : \n"
            for host in self.results:
                result += "{} : {}\n".format(host,self.results.get(host))

        if bool(self.errors):
            result += "Errors executions : \n"
            for host in self.errors:
                error = self.errors.get(host)
                result += "{} : {} : {}\n".format(host,error.__class__.__name__, error)

        return result

class NyBase(xml_utils.XMLUtils):

    _ncc_connection = {}

    PARENT = 'parent'

    def __init__(self, **kwargs):
        #self._ncc_connection = {}
        id_field = "id"
        if self.__parameters__():
            for param in self.__parameters__():
                key = param.get('key')
                yang_key = param.get('yang-key', key)

                default = param.get('default')
                mandatory = param.get('mandatory', False)

                # use first id field, there can be only one
                if param.get('id', False) and id_field == 'id':
                    id_field = key

                value = kwargs.get(key)

                if value is None:
                    value = kwargs.get(yang_key)
                if value is None:
                    value = kwargs.get(yang_key.replace("_", "-"), default)


                if mandatory and value is None:
                    raise Exception("Missing mandatory paramter {}".format(key))
                else:
                    if isinstance(value, list):
                        new_value = []
                        for item in value:
                            item = self._get_value(param, item)

                            new_value.append(item)
                        value = new_value
                    else:
                        value = self._get_value(param, value)

                setattr(self, key, value)

            if kwargs.has_key(self.PARENT):
                setattr(self, self.parent, kwargs)

            self.__id_function__(id_field, **kwargs)

    def _get_value(self,param,item):
        type = param.get('type')

        if isinstance(type,list):
            type = type[0]

        if type is not None and item is not None and not isinstance(item,type) and not isinstance(item,unicode):
            return type(**item)

        return item


    def __id_function__(self, id_field, **kwargs):
        self.id = kwargs.get(id_field)
        if self.id is None:
            raise Exception("ID field {} is None".format(id_field))

    def __str__(self):
        value = JsonDict(self.to_dict()).__str__()
        if value is None:
            value =""
        return value

    def __eq__(self, other):
        eq = True
        diff = self._diff(other)
        print(diff)
        for key in diff.keys():
             eq = eq and diff.get(key).get('valid')
        return eq

    def _diff(self,other):
        diff = {}
        for param in self.__parameters__():
             if param.get('validate',True):
                 key = param.get('key')
                 self_value = getattr(self, key)

                 other_value=""

                 if other is not None:
                    try :
                        other_value = getattr(other, key)
                    except AttributeError:
                        other_value = None

                 diff[key] = {"self":self_value,"other":other_value,"valid": self_value==other_value}

        return diff

    @classmethod
    def from_json(cls, json,parent=None):
        try:
            if not bool(json):
                return None
            params = {}
            for param in cls.__parameters__():
                key = param.get('key', "")

                cisco_key = key.replace("_", "-")
                yang_key = param.get("yang-key",cisco_key)
                yang_path = param.get("yang-path")
                type = param.get("type")

                values = json
                if yang_path is not None:
                    path = yang_path.split("/")
                    for path_item in path:
                        if bool(values):
                            values = values.get(path_item)
                            if bool(values) is None:
                                LOG.warning("Invalid yang segment {} in {} please check against yang model. Values: {}".format(path_item,yang_path,values))




                if bool(values):

                    value = values.get(yang_key)
                    if type is not None:
                        if isinstance(type,list):
                            type = type[0]
                            result = []
                            if isinstance(value,list):
                                for v in value:
                                    if isinstance(v,dict):
                                        v[cls.PARENT]=params
                                        result.append(type.from_json(v))
                                    else:
                                        result.append(v)
                            else:
                                value[cls.PARENT] = params
                                result.append(type.from_json(value))
                            value = result
                        else:
                            value = type.from_json(value)

                    if isinstance(value, dict) and '$' in value.keys():
                        value = value.get('$')

                    if isinstance(value, dict) and value =={}:
                        value = True

                    params[key] = value
        except Exception as e:
            LOG.exception(e)

        return cls(**params)



    @classmethod
    def _get_connection(cls, context):
        return ConnectionPool().get_connection(context.host)


    @classmethod
    def get_primary_filter(cls,**kwargs):
        return cls.ID_FILTER.format(**{'id': kwargs.get('id')})

    @classmethod
    @execute_on_pair(return_raw=True)
    def get(cls,id, context=None):
        return cls._get(id=id,context=context)

    @classmethod
    @execute_on_pair(return_raw=True)
    def exists(cls, id, context=None):
        return cls._exists(id=id,context=context)

    @classmethod
    def _get(cls,**kwargs):
        nc_filter = kwargs.get('nc_filter')
        if nc_filter is None:
            nc_filter = cls.get_primary_filter(**kwargs)
        connection = cls._get_connection(kwargs.get('context'))
        result =  connection.get(filter=nc_filter)

        json = cls.to_json(result.xml)

        if json is not None:
            json = json.get(cls.ITEM_KEY, json)

            result = cls.from_json(json)

            #Add missing primary keys from get

            for key in kwargs.keys():
                if key != 'context':
                    setattr(result,key,kwargs.get(key))

            return result


    @classmethod
    def _get_all(cls,**kwargs):
        nc_filter = kwargs.get('nc_filter')
        if nc_filter is None:
            nc_filter = cls.get_all_filter(**kwargs.get('filter'))
        connection = cls._get_connection(kwargs.get('context'))
        result = connection.get(filter=nc_filter)

        json = cls.to_json(result.xml)
        result = []
        if json is not None:
            json = json.get(cls.ITEM_KEY, json)

            if isinstance(json,list):

                for item in json:
                    result.append(cls.from_json(item))
            else:

                result.append(cls.from_json(json))

            #Add missing primary keys from get


            for item in result:
                for key in kwargs.keys():

                    if key != 'context':
                        setattr(item,key,kwargs.get(key))

        return result

    @classmethod
    def _exists(cls, **kwargs):
        try:
            result = cls._get(**kwargs)
        except Exception as e:
            # raise e
            result = None

        print '{} {}'.format(cls.__name__,result)


        if result is not None:
            return True

        return False

    def internal_exists(self,context=None):
        kwargs = self.__dict__
        kwargs['context'] = context
        return self.__class__._exists(**kwargs)

    @execute_on_pair()
    def create(self, context=None):
        return self._create(context=context)


    @retry_on_failure()
    def _create(self,context=None):
        connection = self._get_connection(context)
        result = connection.edit_config(config=self.to_xml(operation=NC_OPERATION.PUT))
        return result


    @execute_on_pair()
    def update(self, context=None, method='patch'):
        return self._update(context=context,method=method)

    @retry_on_failure()
    def _update(self, context=None,method='patch'):

        if not self.internal_exists(context):
            return self._create(context=context)
        else:
            connection = self._get_connection(context)
            if method not in ['patch', 'put']:
                raise Exception('Update should be called with method = put | patch')
            operation = getattr(NC_OPERATION, method.upper(),None)
            if operation:
                # print self.to_xml(operation=operation)
                result = connection.edit_config(config=self.to_xml(operation=operation))
                return result
            else:
                raise Exception(
                    '{} can not be mapped to a valid NC operation'.format(method))


    @execute_on_pair()
    def delete(self, context=None):
        return self._delete(context=context)


    @retry_on_failure()
    def _delete(self,context=None):
        connection = self._get_connection(context)
        if self.internal_exists(context):
            json = self.to_delete_dict()

            result = connection.edit_config(config=self.to_xml(json=json,operation=NC_OPERATION.DELETE))
            return result

        print('Delete 404')