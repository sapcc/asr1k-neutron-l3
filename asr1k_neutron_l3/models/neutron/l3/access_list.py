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
from asr1k_neutron_l3.models.rest import access_list



class AccessList(base.Base):

    def __init__(self, id):
        super(AccessList, self).__init__()
        self.id = id
        self.rules = []


    def update(self, ):
        acl = access_list.AccessList(name=self.id)
        for i, rule in enumerate(self.rules):
            rule = access_list.ACLRule(access_list=self.id, sequence=(i + 1) * 10, action=rule.action,
                                       protocol=rule.protocol, ipv4_address=rule.source, mask=rule.source_mask ,dest_ipv4_address=rule.destination, dest_mask = rule.destination_mask)
            acl.add_rule(rule)
        return acl.update()


    def delete(self):
        acl = access_list.AccessList(name=self.id)
        return  acl.delete()

    def append_rule(self, rule):
        self.rules.append(rule)


class Rule(object):

    def __init__(self, action='permit', protocol='ip', source=None, source_mask=None, destination=None,destination_mask=None):
        self.action = action
        self.protocol = protocol
        self.source = source
        self.source_mask = source_mask
        self.destination = destination
        self.destination_mask  = destination_mask