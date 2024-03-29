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

from collections import OrderedDict

from asr1k_neutron_l3.models.netconf_yang.ny_base import execute_on_pair, NC_OPERATION, NyBase
from asr1k_neutron_l3.common import utils


class PrefixConstants(object):
    IP = 'ip'
    PREFIX_LIST = 'prefix-list'
    PREFIXES = 'prefixes'
    NAME = 'name'
    DESCRIPTION = 'description'
    SEQ = 'seq'
    NUMBER = 'no'
    ACTION = 'action'
    DENY = 'deny'
    PERMIT = 'permit'
    GE = 'ge'
    LE = 'le'


class Prefix(NyBase):
    ID_FILTER = """
      <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
        <ip>
          <prefix-list>
            <prefixes>
              <name>{id}</name>
            </prefixes>
          </prefix-list>
        </ip>
      </native>
    """

    GET_ALL_STUB = """
      <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
        <ip>
          <prefix-list>
            <prefixes>
              <name/>
            </prefixes>
          </prefix-list>
        </ip>
      </native>
    """

    LIST_KEY = PrefixConstants.PREFIX_LIST
    ITEM_KEY = PrefixConstants.PREFIXES

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'name', 'id': True},
            {'key': 'description'},
            {'key': 'seq', 'type': [PrefixSeq], 'default': []}
        ]

    @classmethod
    def remove_wrapper(cls, dict, context):
        dict = super(Prefix, cls)._remove_base_wrapper(dict, context)
        if dict is None:
            return
        dict = dict.get(PrefixConstants.IP, dict)
        dict = dict.get(cls.LIST_KEY, dict)

        return dict

    def _wrapper_preamble(self, dict, context):
        result = {}
        result[self.LIST_KEY] = dict
        result = {PrefixConstants.IP: result}
        return result

    def __init__(self, **kwargs):
        super(Prefix, self).__init__(**kwargs)

    @property
    def neutron_router_id(self):
        if self.name is not None and self.name.startswith('ext-'):
            return utils.vrf_id_to_uuid(self.name[4:])
        elif self.name is not None and self.name.startswith('snat-'):
            return utils.vrf_id_to_uuid(self.name[5:])
        elif self.name is not None and self.name.startswith('route-'):
            return utils.vrf_id_to_uuid(self.name[6:])

    def add_seq(self, seq):
        if seq.no is None:
            seq.no = (len(self.seq) + 1) * 10
        self.seq.append(seq)

    @execute_on_pair()
    def update(self, context):
        if len(self.seq) > 0:
            return super(Prefix, self)._update(context=context, method=NC_OPERATION.PUT)
        else:
            return super(Prefix, self)._delete(context=context)

    def to_dict(self, context):
        prefix = OrderedDict()
        prefix[PrefixConstants.NAME] = self.name
        prefix[PrefixConstants.SEQ] = []

        for seq in self.seq:
            prefix[PrefixConstants.SEQ].append(seq.to_dict(context))

        result = OrderedDict()
        result[PrefixConstants.PREFIXES] = prefix

        return dict(result)

    def to_delete_dict(self, context):
        prefix = OrderedDict()
        prefix[PrefixConstants.NAME] = self.name
        result = OrderedDict()
        result[PrefixConstants.PREFIXES] = prefix

        return dict(result)


class PrefixSeq(NyBase):
    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'no', 'id': True},
            {'key': 'deny_ip', 'yang-key': 'ip', 'yang-path': 'deny'},
            {'key': 'deny_ge', 'yang-key': 'ge', 'yang-path': 'deny'},
            {'key': 'deny_le', 'yang-key': 'le', 'yang-path': 'deny'},
            {'key': 'permit_ip', 'yang-key': 'ip', 'yang-path': 'permit'},
            {'key': 'permit_ge', 'yang-key': 'ge', 'yang-path': 'permit'},
            {'key': 'permit_le', 'yang-key': 'le', 'yang-path': 'permit'},

            # new seq format for 17.3+
            {'key': 'action'},
            {'key': 'action_ip', 'yang-key': 'ip'},
            {'key': 'le'},
            {'key': 'ge'},
        ]

    def __init__(self, **kwargs):
        super(PrefixSeq, self).__init__(**kwargs)

        if self.deny_ip is not None and self.permit_ip is not None:
            raise Exception("Permit and Deny statements canot coexist on the same sequence")

    def to_dict(self, context):
        seq = OrderedDict()

        seq[PrefixConstants.NUMBER] = self.no
        if context.version_min_17_3:
            if self.action is not None:
                # parameters passed in 17.3 format
                seq[PrefixConstants.ACTION] = self.action
                seq[PrefixConstants.IP] = self.action_ip
                if self.ge:
                    seq[PrefixConstants.GE] = self.ge
                if self.le:
                    seq[PrefixConstants.GE] = self.le
            else:
                # parameters passed in old format by the driver
                if self.deny_ip is not None:
                    seq[PrefixConstants.ACTION] = PrefixConstants.DENY
                    seq[PrefixConstants.IP] = self.deny_ip
                    if self.deny_ge is not None:
                        seq[PrefixConstants.GE] = self.deny_ge
                    if self.deny_le is not None:
                        seq[PrefixConstants.LE] = self.deny_le

                if self.permit_ip is not None:
                    seq[PrefixConstants.ACTION] = PrefixConstants.PERMIT
                    seq[PrefixConstants.IP] = self.permit_ip
                    if self.permit_ge is not None:
                        seq[PrefixConstants.GE] = self.permit_ge
                    if self.permit_le is not None:
                        seq[PrefixConstants.LE] = self.permit_le
        else:
            if self.deny_ip is not None:
                seq[PrefixConstants.DENY] = {PrefixConstants.IP: self.deny_ip}
                if self.deny_ge is not None:
                    seq[PrefixConstants.DENY][PrefixConstants.GE] = self.deny_ge
                if self.deny_le is not None:
                    seq[PrefixConstants.DENY][PrefixConstants.LE] = self.deny_le

            if self.permit_ip is not None:
                seq[PrefixConstants.PERMIT] = {PrefixConstants.IP: self.permit_ip}
                if self.permit_ge is not None:
                    seq[PrefixConstants.PERMIT][PrefixConstants.GE] = self.permit_ge
                if self.permit_le is not None:
                    seq[PrefixConstants.PERMIT][PrefixConstants.LE] = self.permit_le

        return seq
