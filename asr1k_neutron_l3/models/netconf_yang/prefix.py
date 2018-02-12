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

from asr1k_neutron_l3.models.netconf_yang.ny_base import NyBase


class PrefixConstants(object):
    IP = 'ip'
    PREFIX_LIST='prefix-list'
    PREFIXES = 'prefixes'
    NAME = 'name'
    DESCRIPTION = 'description'
    SEQ = 'seq'
    NUMBER = 'no'
    DENY = 'deny'
    PERMIT = 'permit'


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

    LIST_KEY = PrefixConstants.PREFIX_LIST
    ITEM_KEY = PrefixConstants.PREFIXES

    @classmethod
    def __parameters__(cls):
        return [
            {'key': 'name', 'id': True},
            {'key': 'description'},
            {'key': 'seq','type':[PrefixSeq], 'default':[]}
        ]

    @classmethod
    def remove_wrapper(cls,dict):
        dict = super(Prefix, cls)._remove_base_wrapper(dict)
        if dict is None:
            return
        dict = dict.get(PrefixConstants.IP,dict)
        dict = dict.get(cls.LIST_KEY, dict)

        return dict

    def _wrapper_preamble(self,dict):
        result = {}
        result[self.LIST_KEY] = dict
        result = {PrefixConstants.IP: result}
        return result

    def __init__(self,**kwargs):
        super(Prefix, self).__init__(**kwargs)


    def add_seq(self, seq):
        if seq.no is None:
            seq.no = (len(self.seq)+1)*10
        self.seq.append(seq)

    def update(self,context=None):
        if len(self.seq) >0 :
            super(Prefix,self).update()
        else:
            super(Prefix, self).delete()

    def to_dict(self):

        prefix = OrderedDict()
        prefix[PrefixConstants.NAME] = self.name
        prefix[PrefixConstants.SEQ] = []

        for seq in self.seq:
            prefix[PrefixConstants.SEQ].append(seq.to_dict())



        result = OrderedDict()
        result[PrefixConstants.PREFIXES] = prefix

        return dict(result)


class PrefixSeq(NyBase):


    @classmethod
    def __parameters__(cls):
        return [

            {'key': 'no', 'id':True},
            {'key': 'deny_ip','yang-key':'ip','yang-path':'deny'},
            {'key': 'permit_ip','yang-key':'ip','yang-path':'permit'}

        ]


    def __init__(self, **kwargs):
        super(PrefixSeq, self).__init__( **kwargs)

        if self.deny_ip is not None and self.permit_ip is not None:
            raise Exception("Permit and Deny statements canot coexist on the same sequence")



    def to_dict(self):


        seq = OrderedDict()

        seq[PrefixConstants.NUMBER] = self.no
        if self.deny_ip is not None:
            seq[PrefixConstants.DENY] = {PrefixConstants.IP:self.deny_ip}
        if self.permit_ip is not None:
            seq[PrefixConstants.PERMIT] = {PrefixConstants.IP: self.permit_ip}



        return seq