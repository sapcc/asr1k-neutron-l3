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

from asr1k_neutron_l3.models.neutron.l3 import base
from asr1k_neutron_l3.models.netconf_yang import access_list


class AccessList(base.Base):
    def __init__(self, id, drop_on_17_3=False):
        # If we use super(AccessList, self) here the MRO of type(self) is determining the __init__
        # we call. If self is a child, that could lead to not calling base.Base.__init__().
        # If the second argument to super is a type, the returned method is unbound, hence we pass self to it.
        super(AccessList, AccessList).__init__(self)
        self.id = id
        self._drop_on_17_3 = drop_on_17_3
        self.rules = []

    @property
    def _rest_definition(self):
        acl = access_list.AccessList(name=self.id, drop_on_17_3=self._drop_on_17_3)
        for i, rule in enumerate(self.rules):
            sequence = (i + 1) * 10
            ace_rule = access_list.ACERule(
                access_list=self.id,
                acl_rule=sequence,
                action=rule.action,
                protocol=rule.protocol,
                **rule.ip_args,
                **rule.port_args
            )
            acl_rule = access_list.ACLRule(access_list=self.id, sequence=sequence, ace_rule=[ace_rule])
            acl.add_rule(acl_rule)

        return acl

    def get(self):
        return access_list.AccessList.get(self.id)

    def delete(self):
        acl = access_list.AccessList(name=self.id)
        return acl.delete()

    def append_rule(self, rule):
        self.rules.append(rule)


class Rule():
    def __init__(self, action='permit', protocol='ip',
                source=None, source_mask=None, source_port_range=None,
                destination=None, destination_mask=None, destination_port_range=None,
                named_message_type=None, established=False):
        self.action = action
        self.protocol = protocol
        self.source = source
        self.source_mask = source_mask
        self.source_port_range = source_port_range
        self.destination = destination
        self.destination_mask = destination_mask
        self.destination_port_range = destination_port_range
        self.named_message_type = named_message_type
        self.established = established

    @property
    def ip_args(self):
        ip_args = {}
        if self.source_mask:
            ip_args['ipv4_address'] = self.source
            ip_args['mask'] = self.source_mask
        else:
            ip_args['host'] = self.source

        if self.destination_mask:
            ip_args['dest_ipv4_address'] = self.destination
            ip_args['dest_mask'] = self.destination_mask
        else:
            ip_args['dst_host'] = self.destination

        return ip_args

    @property
    def port_args(self):
        port_args = {}
        for direction, yang_direction in (('source', 'src'), ('destination', 'dst')):
            ports = getattr(self, direction + '_port_range')
            if ports:
                if len(ports) == 1:
                    # Not a range
                    port_args[f'{yang_direction}_eq'] = ports[0]
                else:
                    port_args[f'{yang_direction}_range1'] = ports[0]
                    port_args[f'{yang_direction}_range2'] = ports[1]

        if self.protocol == 'tcp' and self.established:
            port_args['established'] = True

        if self.protocol not in ('tcp', 'udp') and self.named_message_type:
            port_args['named_message_type'] = self.named_message_type

        return port_args
