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

from asr1k_neutron_l3.models.netconf_yang.ny_base import execute_on_pair, NC_OPERATION, NyBase
from asr1k_neutron_l3.models.netconf_yang import xml_utils
from asr1k_neutron_l3.common import utils

LOG = logging.getLogger(__name__)


class PrefixConstants(object):
    IP = 'ip'
    PREFIX_LISTS = 'prefix-lists'
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
          <prefix-lists>
            <prefixes>
              <name>{id}</name>
            </prefixes>
          </prefix-lists>
        </ip>
      </native>
    """

    GET_ALL_STUB = """
      <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
        <ip>
          <prefix-lists>
            <prefixes>
              <name/>
              <no/>
            </prefixes>
          </prefix-lists>
        </ip>
      </native>
    """

    LIST_KEY = PrefixConstants.IP
    ITEM_KEY = PrefixConstants.PREFIX_LISTS

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'name', 'id': True},
            {'key': 'description'},
            {'key': 'seq', 'type': [PrefixSeq], 'default': []}
        ]

    @classmethod
    def remove_wrapper(cls, dict, context):
        dict = super().remove_wrapper(dict, context)
        if dict is None:
            return
        dict = dict.get(cls.ITEM_KEY, {})
        if PrefixConstants.PREFIXES not in dict:
            return

        # merge together prefix lists with the same name
        prefixes = dict[PrefixConstants.PREFIXES]
        if not isinstance(prefixes, list):
            prefixes = [prefixes]

        seqs = {}
        for prefix in prefixes:
            pfx_name = prefix.get(PrefixConstants.NAME)
            seqs.setdefault(pfx_name, []).append(prefix)

        result = [
            {
                PrefixConstants.NAME: name,
                PrefixConstants.SEQ: seq,
            }
            for name, seq in seqs.items()
        ]

        # default get will only have a single entry due to the xml filter
        # get_all_stubs_from_device() will have a single or multiple entries (and can handle both)
        # --> we unpack the list in case of a single entry
        if len(result) == 1:
            result = result[0]

        result = {cls.ITEM_KEY: result}
        return result

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
            return super(Prefix, self)._update(context=context)
        else:
            return super(Prefix, self)._delete(context=context)

    def preflight(self, context):
        # delete all rules that should not be on the device (by seq no, rest is done by update-replace)
        # NOTE: if this deletion succeeds and a later update fails we might get in a situation
        #       where a route is deleted here (with seq 30) that cannot be readded (with seq 20)
        #       and we loose an entry until the next update. The probability is pretty low, but we
        #       should keep this in mind if we see behavior like that
        dev_pfx_list = self._internal_get(context=context)
        if dev_pfx_list and dev_pfx_list.seq:
            dev_seq_to_remove = {seq.no for seq in dev_pfx_list.seq} - {seq.no for seq in self.seq}
            if dev_seq_to_remove:
                LOG.warning("Prefix-list %s needs cleaning - seq %s present on device but not in neutron",
                            self.name, ", ".join(map(str, dev_seq_to_remove)))
                dev_pfx_list.seq = dev_seq_to_remove
                dev_pfx_list._delete(context=context)

    def to_dict(self, context):
        prefixes = []
        for seq in self.seq:
            seq_dict = {PrefixConstants.NAME: self.name}
            seq_dict.update(seq.to_dict(context))
            prefixes.append(seq_dict)
        return {PrefixConstants.PREFIX_LISTS: {PrefixConstants.PREFIXES: prefixes}}

    def to_delete_dict(self, context):
        prefixes = []
        for seq in self.seq:
            prefixes.append({
                PrefixConstants.NAME: self.name,
                PrefixConstants.NUMBER: seq.no,
            })
        return {PrefixConstants.PREFIX_LISTS: {PrefixConstants.PREFIXES: prefixes}}


class PrefixSeq(NyBase):
    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'no', 'id': True},

            # new seq format for 17.3+
            {'key': 'action'},
            {'key': 'action_ip', 'yang-key': 'ip'},
            {'key': 'le'},
            {'key': 'ge'},
        ]

    def to_dict(self, context):
        seq = {}

        seq[xml_utils.OPERATION] = NC_OPERATION.PUT
        seq[PrefixConstants.NUMBER] = self.no
        seq[PrefixConstants.ACTION] = self.action
        seq[PrefixConstants.IP] = self.action_ip
        if self.ge:
            seq[PrefixConstants.GE] = self.ge
        if self.le:
            seq[PrefixConstants.GE] = self.le

        return seq
