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
from operator import attrgetter

from collections import OrderedDict
from oslo_log import log as logging

from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.models.netconf_yang.ny_base import NC_OPERATION, NyBase, execute_on_pair
from asr1k_neutron_l3.models.netconf_yang import xml_utils
from asr1k_neutron_l3.plugins.db import asr1k_db

LOG = logging.getLogger(__name__)


class L2Constants(object):
    INTERFACE = 'interface'
    PORT_CHANNEL = 'Port-channel'
    SERVICE = "service"
    SERVICE_INSTANCE = "instance"
    BD_SERVICE_INSTANCE = "service-instance"
    BD_SERVICE_INSTANCE_LIST = "service-instance-list"
    BD_SERVICE_INSTANCE_ID = "instance-id"

    ID = "id"
    NAME = "name"
    DESCRIPTION = "description"

    ETHERNET = "ethernet"
    ENCAPSULATION = 'encapsulation'
    BRIDGE_DOMAIN = "bridge-domain"
    BRIDGE_ID = "bridge-id"
    BRIDGE_DOMAIN_ID = "bridge-domain-id"
    BRIDGE_DOMAIN_BRIDGE_ID = "brd-id"
    DOT1Q = "dot1q"
    SECOND_DOT1Q = "second-dot1q"
    INGRESS = "ingress"
    TAG = "tag"
    POP = "pop"
    REWRITE = "rewrite"
    REWRITE_WAY = "way"
    REWRITE_MODE = "mode"

    MEMBER = "member"
    MEMBER_IFACE = "member-interface"
    MEMBER_BDVIF = "BD-VIF"


class BridgeDomain(NyBase):
    LIST_KEY = L2Constants.BRIDGE_DOMAIN
    ITEM_KEY = L2Constants.BRIDGE_DOMAIN_BRIDGE_ID

    ID_FILTER = """
        <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
            <bridge-domain>
                <brd-id xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-bridge-domain">
                    <bridge-domain-id>{id}</bridge-domain-id>
                </brd-id>
            </bridge-domain>
        </native>
    """

    GET_ALL_STUB = """
        <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
            <bridge-domain>
                <brd-id xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-bridge-domain">
                    <bridge-domain-id/>
                </brd-id>
            </bridge-domain>
        </native>
    """

    @classmethod
    def __parameters__(cls):
        return [
            {"key": "id", "yang-key": L2Constants.BRIDGE_DOMAIN_ID, "primary_key": True},
            {"key": "if_members", "type": [BDIfMember],
             "yang-path": L2Constants.MEMBER, "yang-key": L2Constants.MEMBER_IFACE, "default": []},
            {"key": "bdvif_members", "type": [BDVIFMember],
             "yang-path": L2Constants.MEMBER, "yang-key": L2Constants.MEMBER_BDVIF, "default": []},
            {"key": "has_complete_member_config", "default": False},
        ]

    @classmethod
    def get_for_bdvif(self, bdvif_name, context, partial=False):
        xpath_filter = "/native/bridge-domain/brd-id/member/BD-VIF[name='{}']".format(bdvif_name)
        bd = self._get(xpath_filter=xpath_filter, context=context)
        if bd is not None:
            if partial:
                return bd
            return bd._internal_get(context=context)

    def __init__(self, *args, **kwargs):
        super(BridgeDomain, self).__init__(*args, **kwargs)

        # data from the device might result in a single list with one None element
        # this should be fixed in NyBase.from_json(), but as this might impact other parts of the code
        # we just filter out the values for now
        if self.if_members == [None]:
            self.if_members = []
        if self.bdvif_members == [None]:
            self.bdvif_members = []

    def preflight(self, context):
        """Remove wrong interface membership for all BD-VIF members"""
        if not context.version_min_17_3:
            return

        # go through all non-deleted member interfaces
        for bdvif in self.bdvif_members:
            if bdvif.mark_deleted:
                continue
            LOG.debug("Host %s: preflight check for interface %s on in bridge %s",
                      context.host, bdvif.name, self.id)
            bridge = self.get_for_bdvif(bdvif.name, context, partial=True)

            # check if interface is in correct bridge
            if bridge is not None and bridge.id != self.id:
                LOG.warning("Host %s: found BD-VIF%s in wrong BD %s, should be in BD %s, "
                            "removing membership from BD %s",
                            context.host, bdvif.name, bridge.id, self.id, bridge.id)
                # should have only one result, but who knows what cisco will return
                for fb_bdvif in bridge.bdvif_members:
                    if fb_bdvif.name == bdvif.name:
                        # remove interface from wrong bridge
                        #  - don't call preflight, we don't need this check to run for the other bridge
                        #  - don't call internal validate (which will only execute if "something changed")
                        LOG.debug("Host %s: Deleting BD-VIF%s from BD %s", context.host, bdvif.name, bridge.id)
                        fb_bdvif.mark_deleted = True
                        bridge._update(context=context, method=NC_OPERATION.PATCH, preflight=False,
                                       internal_validate=False)
                        break
                else:
                    LOG.warning("Host %s: could not find BD_VIF%s as member of (wrong) bridge %s, skipping",
                                context.host, bdvif.name, bridge.id)

    def postflight(self, context, method):
        """Remove all members from bridge as otherwise we can't delete it"""
        bd = self._internal_get(context=context)
        if bd is not None:
            has_members = False
            for member in bd.if_members + bd.bdvif_members:
                member.mark_deleted = True
                has_members = True

            if has_members:
                LOG.debug("Bridge %s still has members, clearing the bridge before delete", self.id)
                bd._update(context=context, method=NC_OPERATION.PATCH, preflight=False,
                           internal_validate=False)

    def to_dict(self, context):
        bddef = OrderedDict()
        bddef[xml_utils.NS] = xml_utils.NS_CISCO_BRIDGE_DOMAIN
        bddef[L2Constants.BRIDGE_DOMAIN_ID] = self.id

        if context.version_min_17_3:
            if context.use_bdvif:
                bddef[L2Constants.MEMBER] = {
                    L2Constants.MEMBER_IFACE: [_m.to_dict(context)
                                               for _m in sorted(self.if_members,
                                                                key=lambda _x: _x.interface)],
                    L2Constants.MEMBER_BDVIF: [_m.to_dict(context)
                                               for _m in sorted(self.bdvif_members, key=attrgetter('name'))],
                }
                if self.has_complete_member_config:
                    bddef[L2Constants.MEMBER][xml_utils.OPERATION] = NC_OPERATION.PUT
            else:
                # This can be used for migrating back from new-style bridges, but might bring some problems
                # if the bridge was never used as a new-stlye bridge
                # bddef[L2Constants.MEMBER] = {xml_utils.OPERATION: NC_OPERATION.DELETE}
                pass

        return {L2Constants.BRIDGE_DOMAIN_BRIDGE_ID: bddef}

    def _diff(self, context, device_config):
        if context.use_bdvif and device_config and not self.has_complete_member_config:
            # we don't know all bd-vif members - the diff should represent if
            # the bd-vifs we know about are configured
            neutron_bdvif_names = [_m.name for _m in self.bdvif_members]
            for bdvif in list(device_config.bdvif_members):
                if bdvif.name not in neutron_bdvif_names:
                    device_config.bdvif_members.remove(bdvif)
        return super(BridgeDomain, self)._diff(context, device_config)

    def is_orphan(self, all_router_ids, all_segmentation_ids, all_bd_ids, context):
        return asr1k_db.MIN_DOT1Q <= int(self.id) <= asr1k_db.MAX_DOT1Q and \
            int(self.id) not in all_segmentation_ids


class BDIfMember(NyBase):
    """Normal interface as a member of a bridge-domain"""

    @classmethod
    def __parameters__(cls):
        return [
            {"key": "interface", "yang-key": L2Constants.INTERFACE},
            {"key": "service_instances", "yang-key": L2Constants.BD_SERVICE_INSTANCE_LIST, "default": [],
             "type": [BDIfMemberServiceInstance]},
            {"key": "mark_deleted", "default": False},
        ]

    def to_dict(self, context):
        result = {
            L2Constants.INTERFACE: self.interface,
        }

        if self.service_instances:
            service_instances = []
            for service_instance in sorted(self.service_instances, key=attrgetter('id')):
                service_instances.append(service_instance.to_dict(context))
            result[L2Constants.BD_SERVICE_INSTANCE_LIST] = service_instances

        if self.mark_deleted:
            result[xml_utils.OPERATION] = NC_OPERATION.REMOVE
        return result


class BDIfMemberServiceInstance(NyBase):
    """Represents a service instance id of a BDIfMember"""

    @classmethod
    def __parameters__(cls):
        return [
            {"key": "id", "yang-key": L2Constants.BD_SERVICE_INSTANCE_ID},
        ]

    def to_dict(self, context):
        return {
            L2Constants.BD_SERVICE_INSTANCE_ID: self.id,
        }


class BDVIFMember(NyBase):
    """BD-VIF as a member of a bridge-domain"""
    @classmethod
    def __parameters__(cls):
        return [
            {"key": "name"},
            {"key": "mark_deleted", "default": False},
        ]

    def to_dict(self, context):
        result = {
            L2Constants.NAME: self.name,
        }
        if self.mark_deleted:
            result[xml_utils.OPERATION] = NC_OPERATION.REMOVE

        return result


class ServiceInstance(NyBase):
    PORT_CHANNEL = 0
    ID_FILTER = """
          <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                  xmlns:ios-eth="http://cisco.com/ns/yang/Cisco-IOS-XE-ethernet">
            <interface>
              <Port-channel>
                <name>{port_channel}</name>
                <ios-eth:service>
                  <ios-eth:instance>
                    <id>{id}</id>
                  </ios-eth:instance>
                </ios-eth:service>
              </Port-channel>
            </interface>
          </native>
    """

    GET_ALL_STUB = """
          <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                  xmlns:ios-eth="http://cisco.com/ns/yang/Cisco-IOS-XE-ethernet">
            <interface>
              <Port-channel>
                <name>{port_channel}</name>
                <ios-eth:service>
                  <ios-eth:instance>
                    <ios-eth:id/>
                  </ios-eth:instance>
                </ios-eth:service>
              </Port-channel>
            </interface>
          </native>
    """

    LIST_KEY = L2Constants.SERVICE
    ITEM_KEY = L2Constants.SERVICE_INSTANCE

    @classmethod
    def __parameters__(cls):
        return [
            {"key": "port_channel", 'validate': False, 'primary_key': True},
            {"key": "id", "mandatory": True, 'default': 0},
            {"key": "description"},
            {"key": "bridge_domain", 'yang-path': 'bridge-domain', 'yang-key': 'bridge-id'},
            {"key": "dot1q", 'yang-path': 'encapsulation/dot1q', 'yang-key': 'id'},
            {"key": "second_dot1q", 'yang-path': 'encapsulation/dot1q', 'yang-key': 'second-dot1q'},
            {"key": "way", 'yang-path': 'rewrite/ingress/tag/pop'},
            {"key": "mode", 'yang-path': 'rewrite/ingress/tag/pop'}
        ]

    @classmethod
    def get_primary_filter(cls, **kwargs):
        return cls.ID_FILTER.format(id=kwargs.get('id'), port_channel=cls.PORT_CHANNEL)

    @classmethod
    def get_all_stub_filter(cls, context):
        return cls.GET_ALL_STUB.format(port_channel=cls.PORT_CHANNEL)

    @classmethod
    @execute_on_pair(return_raw=True)
    def get(cls, id, context):
        return super(ServiceInstance, cls)._get(id=id, port_channel=cls.PORT_CHANNEL, context=context)

    @classmethod
    @execute_on_pair(return_raw=True)
    def exists(cls, id, context):
        return super(ServiceInstance, cls)._exists(id=id, port_channel=cls.PORT_CHANNEL, context=context)

    @classmethod
    def remove_wrapper(cls, json, context):
        json = super(ServiceInstance, cls)._remove_base_wrapper(json, context)
        if json is None:
            return
        json = json.get(L2Constants.INTERFACE, json)
        json = json.get(L2Constants.PORT_CHANNEL, json)

        if isinstance(json, list):
            result = []
            for pc in json:
                if pc.get("name") == cls.PORT_CHANNEL:
                    service = pc.get(L2Constants.SERVICE, pc)
                    if not isinstance(service.get(L2Constants.SERVICE_INSTANCE, None), list):
                        if service.get(L2Constants.SERVICE_INSTANCE, None) is not None:
                            service[L2Constants.SERVICE_INSTANCE] = [service.get(L2Constants.SERVICE_INSTANCE)]
                    result.append(service)

            json = result
        else:
            json = json.get(L2Constants.SERVICE, json)
        return json

    def orphan_info(self):
        return {self.__class__.__name__: {'description': self.description, 'service_instance': self.id,
                                          'port_channel': self.PORT_CHANNEL, 'bridge_domain': self.bridge_domain}}

    def _wrapper_preamble(self, dict, context):
        result = {}
        dict[xml_utils.NS] = xml_utils.NS_CISCO_ETHERNET
        result[L2Constants.NAME] = self.PORT_CHANNEL
        result[self.LIST_KEY] = dict
        result = {L2Constants.PORT_CHANNEL: result}
        result = {L2Constants.INTERFACE: result}
        return result

    def __init__(self, **kwargs):
        kwargs['port_channel'] = self.PORT_CHANNEL
        super(ServiceInstance, self).__init__(**kwargs)

        if self.id == 'None' or self.id is None:
            self.id = -1

    def to_dict(self, context):
        dot1q = dict(OrderedDict())

        dot1q[L2Constants.ID] = [str(self.dot1q)]
        if self.second_dot1q is not None:
            dot1q[L2Constants.SECOND_DOT1Q] = [str(self.second_dot1q)]

        bridge_domain = OrderedDict()
        bridge_domain[L2Constants.BRIDGE_ID] = self.bridge_domain

        rewrite = OrderedDict()
        rewrite[L2Constants.INGRESS] = OrderedDict()

        rewrite[L2Constants.INGRESS][L2Constants.TAG] = OrderedDict()
        if self.way is not None and self.mode is not None:
            rewrite[L2Constants.INGRESS][L2Constants.TAG][L2Constants.POP] = OrderedDict()
            rewrite[L2Constants.INGRESS][L2Constants.TAG][L2Constants.POP][
                L2Constants.REWRITE_WAY] = self.way
            rewrite[L2Constants.INGRESS][L2Constants.TAG][L2Constants.POP][L2Constants.REWRITE_MODE] = self.mode

        instance = OrderedDict()
        instance[L2Constants.ID] = "{}".format(str(self.id))
        instance[L2Constants.ETHERNET] = ''
        if self.description is not None:
            instance[L2Constants.DESCRIPTION] = "{}".format(self.description)

        instance[L2Constants.ENCAPSULATION] = OrderedDict()
        instance[L2Constants.ENCAPSULATION][L2Constants.DOT1Q] = dot1q
        instance[L2Constants.REWRITE] = rewrite
        if not context.use_bdvif:
            instance[L2Constants.BRIDGE_DOMAIN] = bridge_domain

        result = OrderedDict()
        result[L2Constants.SERVICE_INSTANCE] = instance

        return dict(result)

    def to_delete_dict(self, context):
        instance = OrderedDict()
        instance[L2Constants.ID] = "{}".format(str(self.id))
        instance[L2Constants.ETHERNET] = ''

        result = OrderedDict()
        result[L2Constants.SERVICE_INSTANCE] = instance

        return dict(result)

    @execute_on_pair()
    def update(self, context):
        return super(ServiceInstance, self)._update(context=context, method=NC_OPERATION.PUT)


class ExternalInterface(ServiceInstance):
    PORT_CHANNEL = "1"

    def __init__(self, **kwargs):
        kwargs['bridge_domain'] = kwargs.get('id')
        kwargs['dot1q'] = kwargs.get('id')
        super(ExternalInterface, self).__init__(**kwargs)

    def is_orphan(self, all_router_ids, all_segmentation_ids, all_bd_ids, context):
        return asr1k_db.MIN_DOT1Q <= int(self.id) <= asr1k_db.MAX_DOT1Q and \
            int(self.id) not in all_segmentation_ids


class LoopbackExternalInterface(ServiceInstance):
    PORT_CHANNEL = "2"

    def __init__(self, **kwargs):
        kwargs['bridge_domain'] = kwargs.get('dot1q')
        kwargs['dot1q'] = kwargs.get('dot1q')
        super(LoopbackExternalInterface, self).__init__(**kwargs)

    def to_dict(self, context):
        if context.use_bdvif:
            return {}
        else:
            return super(LoopbackExternalInterface, self).to_dict(context)

    def is_orphan(self, all_router_ids, all_segmentation_ids, all_bd_ids, context):
        # KeepBDUpInterface is included here, as they share a port-channel
        return not context.use_bdvif and \
            (utils.to_bridge_domain(asr1k_db.MIN_SECOND_DOT1Q) <= int(self.id) <=
             utils.to_bridge_domain(asr1k_db.MAX_SECOND_DOT1Q) and
             int(self.id) not in all_bd_ids) or \
            context.use_bdvif and \
            (asr1k_db.MIN_DOT1Q <= int(self.id) <= asr1k_db.MAX_DOT1Q and
             int(self.id) not in all_segmentation_ids)


class LoopbackInternalInterface(ServiceInstance):
    PORT_CHANNEL = "3"

    def __init__(self, **kwargs):
        super(LoopbackInternalInterface, self).__init__(**kwargs)

    def to_dict(self, context):
        if context.use_bdvif:
            return {}
        else:
            return super(LoopbackInternalInterface, self).to_dict(context)

    def is_orphan(self, all_router_ids, all_segmentation_ids, all_bd_ids, context):
        return context.use_bdvif or \
            (utils.to_bridge_domain(asr1k_db.MIN_SECOND_DOT1Q) <= int(self.id) <=
             utils.to_bridge_domain(asr1k_db.MAX_SECOND_DOT1Q) and
             int(self.id) not in all_bd_ids)


class KeepBDUpInterface(ServiceInstance):
    PORT_CHANNEL = "2"

    def __init__(self, **kwargs):
        super(KeepBDUpInterface, self).__init__(**kwargs)

    def to_dict(self, context):
        if context.use_bdvif:
            return super(KeepBDUpInterface, self).to_dict(context)
        else:
            return {}

    def is_orphan(self, all_router_ids, all_segmentation_ids, all_bd_ids, context):
        raise NotImplementedError("This class' orphan check is handled by LoopbackExternalInterface")
