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
import time
import eventlet
import eventlet.debug
import dictdiffer
from collections import OrderedDict


eventlet.debug.hub_exceptions(False)
from oslo_log import log as logging
from asr1k_neutron_l3.common import asr1k_exceptions as exc
from asr1k_neutron_l3.models import asr1k_pair
from asr1k_neutron_l3.models.netconf import ConnectionPool
from asr1k_neutron_l3.models.netconf_yang import xml_utils
from asr1k_neutron_l3.models.netconf_yang.xml_utils import JsonDict



from ncclient.operations.rpc import RPCError
from ncclient.transport.errors import SessionCloseError
from ncclient.transport.errors import SSHError
from ncclient.operations.errors import TimeoutExpiredError


LOG = logging.getLogger(__name__)


class NC_OPERATION(object):
    DELETE = 'delete'
    REMOVE = 'remove'
    CREATE = 'create'
    PUT = 'replace'
    PATCH = 'merge'

class YANG_TYPE(object):
    EMPTY = 'empty'


class classproperty(property):
    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()


class execute_on_pair(object):

    def __init__(self, return_raw=False, result_type=None):
        self.return_raw = return_raw

        self.result_type = PairResult
        if result_type is not None:
            self.result_type = result_type

    def _execute_method(self,*args,**kwargs):
        method = kwargs.pop('_method')
        result = kwargs.pop('_result')

        try:

            response = method(*args, **kwargs)

            # if we wrap in a wrapped method return the
            # base result
            if isinstance(response, self.result_type):
                result = response
            else:
                result.append( kwargs.get('context'), response)



        except BaseException as e:
            LOG.exception(e)
            result.append(kwargs.get('context'), e)

    def __call__(self, method):




        @six.wraps(method)
        def wrapper(*args, **kwargs):

            result = self.result_type(args[0],method.__name__)
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

            if isinstance(result,self.result_type):
                if not result.success:
                    LOG.warning(result.errors)
                    result.raise_errors()

            return result

        return wrapper

class retry_on_failure(object):

    def __init__(self, retry_interval=0.5, max_retries=15):
        self.retry_interval = retry_interval
        self.max_retries = max_retries


        super(retry_on_failure, self).__init__()

    def __call__(self, f):

        @six.wraps(f)
        def wrapper(*args, **kwargs):
            retries = 0
            exception = None

            context = kwargs.get('context')
            host = None
            if context is not None:
                host = context.host

            while retries < self.max_retries:
                if retries > 0:
                    LOG.debug("** [{}] Retry method {} on {} : {} of {}".format(host, f.__name__,args[0].__class__.__name__ ,retries,self.max_retries))

                try:
                    result = f(*args, **kwargs)

                    if result is not None and not isinstance(result, PairResult) and not result.ok:
                        time.sleep(self.retry_interval)
                        retries += 1
                    else:
                        return result
                except exc.DeviceUnreachable as e:
                    if context is not None:
                        context.alive = False
                    break

                except (RPCError , SessionCloseError,SSHError,TimeoutExpiredError) as e:

                    if isinstance(e, TimeoutExpiredError):
                        # close and re-establish connection
                        connection = args[0]._get_connection(context)
                        connection.close()

                    if isinstance(e,RPCError):
                        if e.tag in  ['data-missing']:
                            return None
                        elif e.message=='inconsistent value: Device refused one or more commands':  # the data model is not compatible with the device
                            LOG.debug(e.to_dict())
                            raise exc.InconsistentModelException(host=host,entity = args[0],operation = f.__name__)
                        elif e.message == 'internal error':  # something can't be configured maybe due to transient state e.g. BGP session active these should be requeued
                            LOG.debug(e.to_dict())
                            raise exc.InternalErrorException(host=host, entity = args[0],operation = f.__name__)
                        elif e.tag in ['in-use']:  # Lock
                            pass  # retry on lock
                    else:
                        LOG.exception(e)
                    time.sleep(self.retry_interval)
                    retries += 1
                    exception = e

            if exception is not None:
              raise exception

        return wrapper

class PairResult(object):

    def __init__(self,entity,operation):

        self.entity = entity
        self.operation = operation
        self.results = {}
        self.errors = {}
        self.show_success = True
        self.show_failure = True

    def append(self, context, response):

        if isinstance(response,BaseException):
            self.errors[context.host] = response
        else:
            self.results[context.host] = response

    @property
    def success(self):
        return (not bool(self.errors)) and bool(self.results)

    @property
    def error(self):
        return bool(self.errors)


    def raise_errors(self):
        # Operation will start in _ as we use the internal CRD call on each device
        # to evaluate whether to to raise we use raise_on_create/delete/update so we trim the first char
        operation = self.operation
        if operation.startswith('_'):
            operation = operation[1:]

        check_attr = 'raise_on_{}'.format(operation)

        should_raise = False

        if hasattr(self.entity, check_attr):
            should_raise = getattr(self.entity, check_attr)

        for host, error in self.errors.iteritems():
            if should_raise and isinstance(error,exc.DeviceOperationException) and error.raise_exception:
                raise error


    def __str__(self):
        result = ''
        if self.success and self.show_success:
            result = "** Success  for [{}] action [{}]\n".format(self.entity.__class__.__name__, self.operation)
            for host in self.results:
                result += "[{}] : {}\n".format(host,self.results.get(host))

        if self.error and self.show_failure:
            result = "** Errors for [{}] action [{}]\n".format(self.entity.__class__.__name__, self.operation)

            for host in self.errors:
                error = self.errors.get(host,None)
                if hasattr(self.entity,'to_xml'):
                    result += "{}\n".format(self.entity.to_xml())

                result += "{} : {} : {}\n".format(host,error.__class__.__name__, error)

        return result

    def to_dict(self):
        result = {}
        for host in self.results:
            host_result = self.results.get(host)
            if host_result is not None:
                result[host] = self.results.get(host).to_dict()
            else:
                result[host] = {}

        return result

class DiffResult(PairResult):


    @property
    def valid(self):
        valid = True
        for host in self.results.keys():
            diffs = self.results.get(host)
            valid = valid and not diffs

        return valid

    @property
    def invalid_devicess(self):
        results = []
        for host in self.results.keys():
            diffs = self.results.get(host)
            if len(diffs) > 0:
                results.append(host)
        return results

    @property
    def diffs(self):
        return self.results

    def diffs_for_device(self, host):
        return  self.results.get(host,[])


    def to_dict(self):
        result = {}
        for host in self.results:
            result[host] = self.results.get(host)

        return result

    # def __str__(self):
    #     result = ''
    #     for host in self.results.keys():
    #         result = result + "{} : {} {} : {} \n".format(host,self.entity,self.valid,self.results.get(host))
    #
    #
    #     return result


class NyBase(xml_utils.XMLUtils):

    _ncc_connection = {}

    PARENT = 'parent'

    def __init__(self, **kwargs):
        # Should we delete even if object reports not existing
        #
        self.force_delete = False

        # Should fatal exceptions be raised

        self.raise_on_create = True
        self.raise_on_update = True
        self.raise_on_delete = True
        self.raise_on_valid = False


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
                    value = kwargs.get(yang_key.replace("_", "-"))
                if value is None and default is not None :
                    value = default


                if isinstance(value,int) and not isinstance(value,bool):
                    value = str(value)

                if mandatory and value is None:
                    pass
                    #raise Exception("Missing mandatory paramter {}".format(key))
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
        self.id = str(kwargs.get(id_field))
        if self.id is None:
            raise Exception("ID field {} is None".format(id_field))

    def __str__(self):
        value = JsonDict(self.to_dict()).__str__()
        if value is None:
            value =""
        return value

    def __eq__(self, other):

        diff = self._diff(other)

        return diff.valid

    def _diff(self,other):


        self_json = self._to_plain_json(self.to_dict())
        other_json= {}
        if other is not None:
            other_json = self._to_plain_json(other.to_dict())
        else:
            other_json = {}



        return self.__json_diff(self_json,other_json)



    def __json_diff(self,self_json,other_json):
        ignore=[]
        for param in self.__parameters__():
            if not param.get('validate',True):
                ignore.append(param.get('key',param.get('yang-key')))

        diff =  self.__diffs_to_dicts(dictdiffer.diff(self_json, other_json, ignore=ignore))

        return diff

    def __diffs_to_dicts(self,diffs):
        result= []
        if not isinstance(diffs,list):
            diffs = list(diffs)
        if diffs:
            for diff in diffs:
                if len(diff)==3:
                    neutron = None
                    device = None

                    if len(diff[2])==1:
                        neutron = diff[2][0]

                    elif len(diff[2])==2:
                        neutron = diff[2][0]
                        device = diff[2][1]


                    result.append({'entity':self.id,'type':diff[0],'item':diff[1],'neutron':neutron,'device':device})

        return result

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

                    if  param.get('yang-type') == YANG_TYPE.EMPTY:
                        if values.has_key(yang_key):
                            value = True
                        else:
                            value = False
                    else:
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

                                if value is not None:
                                    value[cls.PARENT] = params
                                    result.append(type.from_json(value))
                            value = result
                        else:
                            value = type.from_json(value)

                    if isinstance(value, dict) and value =={}:
                        value = True

                    params[key] = value
        except Exception as e:
            LOG.exception(e)

        return cls(**params)



    @classmethod
    def _get_connection(cls, context):
        return ConnectionPool().get_connection(context)


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
        try:
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

                cls.__ensure_primary_keys(result, **kwargs)

                return result
        except exc.DeviceUnreachable:
            pass

    @classmethod
    def _get_all(cls,**kwargs):
        result = []
        try:
            nc_filter = kwargs.get('nc_filter')
            if nc_filter is None:
                nc_filter = cls.get_all_filter(**kwargs.get('filter'))
            connection = cls._get_connection(kwargs.get('context'))
            rpc_result = connection.get(filter=nc_filter)

            json = cls.to_json(rpc_result.xml)

            if json is not None:
                json = json.get(cls.ITEM_KEY, json)

                if isinstance(json,list):

                    for item in json:
                        result.append(cls.from_json(item))
                else:

                    result.append(cls.from_json(json))

                #Add missing primary keys from get


                for item in result:
                    cls.__ensure_primary_keys(item,**kwargs)
        except exc.DeviceUnreachable:
            pass
        except Exception as e:
            LOG.exception(e)


        return result

    @classmethod
    def __ensure_primary_keys(cls,item,**kwargs):
        # Add missing primary keys from get
        params = cls.__parameters_as_dict()

        for key in kwargs.keys():

            param = params.get(key, {})
            if key != 'context' and param.get('primary_key', False):
                setattr(item, key, kwargs.get(key))


    @classmethod
    def __parameters_as_dict(cls):
        result = {}

        for param in cls.__parameters__():
            result[param.get('key')] = param

        return result




    @classmethod
    def _exists(cls, **kwargs):
        try:
            result = cls._get(**kwargs)
        except Exception as e:
            # raise e
            result = None

        if result is not None:
            return True

        return False

    def _internal_exists(self,context=None):
        kwargs = self.__dict__
        kwargs['context'] = context
        return self.__class__._exists(**kwargs)

    def _internal_get(self,context=None):
        kwargs = self.__dict__
        kwargs['context'] = context
        return self.__class__._get(**kwargs)



    @execute_on_pair()
    def create(self, context=None):
        return self._create(context=context)


    @retry_on_failure()
    def _create(self,context=None):
        connection = self._get_connection(context)
        result = connection.edit_config(config=self.to_xml(operation=NC_OPERATION.PUT))
        return result


    @execute_on_pair()
    def update(self, context=None, method= NC_OPERATION.PATCH):
        return self._update(context=context,method=method)

    @retry_on_failure()
    def _update(self, context=None,method=NC_OPERATION.PATCH):
        if len(self._internal_validate(context=context)) > 0 :

            # print "{} device configuration {} invalid or missing updating".format(self.__class__.__name__,context.host)
            if not self._internal_exists(context):
                return self._create(context=context)
            else:
                connection = self._get_connection(context)
                if method not in [NC_OPERATION.PATCH, NC_OPERATION.PUT]:
                    raise Exception('Update should be called with method = NC_OPERATION.PATCH | NC_OPERATION.PUT')

                result = connection.edit_config(config=self.to_xml(operation=method))
                return result
        # else:
            # print "{} device configuration {} already upto date".format(self.__class__.__name__,context.host)

    @execute_on_pair()
    def delete(self, context=None,method=NC_OPERATION.DELETE):
        return self._delete(context=context,method=method)


    @retry_on_failure()
    def _delete(self,context=None,method=NC_OPERATION.DELETE):
        connection = self._get_connection(context)

        if self._internal_exists(context) or self.force_delete:
            json = self.to_delete_dict()
            result = connection.edit_config(config=self.to_xml(json=json,operation=method))
            return result

    def _internal_validate(self,should_be_none=False, context=None):
        device_config = self._internal_get(context=context)

        if should_be_none:
            if device_config is None:
                return []

        return self._diff(device_config)


    @execute_on_pair(result_type=DiffResult)
    def _validate(self,should_be_none=False,context=None):
        return self._internal_validate(should_be_none=False,context=None)




    def diff(self, should_be_none=False):
        result = self._validate(should_be_none=should_be_none)
        return result


    def is_valid(self, should_be_none=False):
        result = self.diff(should_be_none=should_be_none)

        return result.valid