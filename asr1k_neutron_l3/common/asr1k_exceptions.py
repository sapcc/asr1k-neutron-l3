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

from neutron_lib import exceptions as nexception


class Asr1kException(BaseException):
    pass


class RdPoolExhausted(nexception.NotFound):
    message = "No free RD could be allocated to the router. Please raise an issue with support."


class SecondDot1QPoolExhausted(nexception.NotFound):
    message = "No free second dot1q id could be allocated for agent host %(agent_host)s."


class BdVifInBdExhausted(nexception.Conflict):
    message = ("Network %(network_id)s cannot be bound to router %(router_id)s due to BD-VIF hardware limit exceeded. "
               "Please chose another network.")


class DeviceUnreachable(BaseException):
    message = "Device %(host)s is not reachable"

    def __init__(self, **kwargs):
        self.host = kwargs.get('host')


class DeviceOperationException(Asr1kException):
    def __init__(self, **kwargs):
        self.host = kwargs.get('host')
        self.entity = kwargs.get('entity')
        kwargs['entity_name'] = 'Unknown'
        if self.entity is not None:
            kwargs['entity_name'] = self.entity.__class__.__name__
        self.operation = kwargs.get('operation')
        self.msg = self.message % kwargs
        super(DeviceOperationException, self).__init__()

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


class InternalErrorException(DeviceOperationException):
    message = ("An internal error executing %(operation)s for model %(entity_name)s on device %(host)s. "
               "Model entity: %(entity)s. Info: %(info)s")


class ConfigurationLockedException(ReQueueException):
    message = ("Encoutered a requeable lock exception executing %(operation)s for model %(entity_name)s "
               "on device %(host)s.  Model entity: %(entity)s")


class ReQueueableInternalErrorException(ReQueueException):
    message = ("An requeable internal error executing %(operation)s for model %(entity_name)s on device %(host)s. "
               "Model entity: %(entity)s")


class InconsistentModelException(DeviceOperationException):
    message = ("%(operation)s for model %(entity_name)s cannot be executed on %(host)s "
               "due to a model/device inconsistency. Model entity: %(entity)s. Info: %(info)s")


class DeviceConnectionException(DeviceOperationException):
    message = "Cannot connect to device %(host)s"


class EntityNotEmptyException(ReQueueException):
    message = "The config for entity %(entity_name)s is not empty and cannot be deleted without side effects"


class MissingParentException(ReQueueException):
    message = "The parent config for entity %(entity_name)s is missing, cannot create %(entity_name)s"


class CapabilityNotFoundException(DeviceOperationException):
    message = "Could not find capability %(entity)s on host %(host)s"


class VersionInfoNotAvailable(DeviceOperationException):
    message = "Could not get version info for attribute %(entity)s from host %(host)s"


class OnlyOneAZHintAllowed(nexception.BadRequest):
    message = "Only one availability zone hint allowed per object"


class RouterNetworkAZMismatch(nexception.NeutronException):
    message = "AZ hint of router and network do not match (router is in %(router_az)s, network in %(network_az)s)"


class DynamicNatPoolSpecifiedIpsNotConsecutivelyAscending(nexception.BadRequest):
    message = ("Invalid extended nat pool for router: IP %(ip)s and %(next_ip)s don't follow each other directly "
               "in ascending order")


class DynamicNatPoolIPDefinitionMixed(nexception.BadRequest):
    message = "IPs for the dynamic NAT pool must be all specified by subnet or all by ip address, not mixed"


class DynamicNatPoolIPDefinitionSubnetMissing(nexception.BadRequest):
    message = "Tried to allocate IPs for dynamic NAT pool but neither IP nor subnet was provided"


class DynamicNatPoolTwoSubnetsFound(nexception.BadRequest):
    message = ("Found two differend subnets in request for dynamic NAT pool, which is not allowed "
               "(%(subnet_a)s vs %(subnet_b)s)")


class DynamicNatPoolNeedsToHaveAtLeastTwoIPs(nexception.BadRequest):
    message = ("At least three IPs need to be provided for the dynamic NAT pool to be enabled "
               "(at least two for the pool and one for the router itself)")


class DynamicNatPoolGivenIPsDontBelongToNetwork(nexception.BadRequest):
    message = "Given IP %(ip)s does not belong to any subnet of network %(network_id)s"


class DynamicNatPoolExternalNetExhausted(nexception.BadRequest):
    message = ("Could not find %(ip_count)s consecutive IP addresses in subnet %(subnet_id)s - "
               "make sure there is enough undivided IP space")
