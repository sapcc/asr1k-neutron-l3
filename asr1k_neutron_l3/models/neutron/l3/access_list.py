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

    @base.excute_on_pair
    def update(self, context=None):
        acl = access_list.AccessList(context, name=self.id)
        for i, rule in enumerate(self.rules):
            rule = access_list.ACLRule(context, access_list=self.id, sequence=(i + 1) * 10, action=rule.action,
                                       protocol=rule.protocol, source=rule.source, destination=rule.destination)
            acl.add_rule(rule)
        acl.update()

    @base.excute_on_pair
    def delete(self, context=None):
        acl = access_list.AccessList.get(context, self.id)
        acl.delete()

    def append_rule(self, rule):
        self.rules.append(rule)


class Rule(object):

    def __init__(self, action='permit', protocol='ip', source='any', destination='any'):
        self.action = action
        self.protocol = protocol
        self.source = source
        self.destination = destination
