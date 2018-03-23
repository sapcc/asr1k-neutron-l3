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

class Asr1kException(BaseException):
    pass


class DeviceUnreachable(BaseException):
    message = "Device %(host)s is not reachable"
    def __init__(self, **kwargs):
        self.host = kwargs.get('host')

class DeviceOperationException(Asr1kException):

    def __init__(self,**kwargs):
         self.host = kwargs.get('host')
         self.entity = kwargs.get('entity')
         kwargs['entity_name'] = 'Unknown'
         if self.entity is not None:
             kwargs['entity_name'] = self.entity.__class__.__name__
         self.operation = kwargs.get('operation')
         self.msg = self.message % kwargs
         super(DeviceOperationException,self).__init__()

    @property
    def raise_exception(self):
        return False

    def __str__(self):
        return self.msg


class ConfigurationLockExcexption(DeviceOperationException):
    message = "Configuration is locked on device %(host)s"

class ReQueueException(DeviceOperationException):

    @property
    def raise_exception(self):
        return True


class InternalErrorException(ReQueueException):
    message = "An internal error executing %(operation)s for model %(entity_name)s on device %(host)s .  Model entity : %(entity)s"

class InconsistentModelException(ReQueueException):
    message = "%(operation)s for model %(entity_name)s cannot be executed on %(host)s due to a model/device inconsistency. Model entity : %(entity)s"


class DeviceConnectionException(DeviceOperationException):
    message = "Cannot connect to device %(host)s"
