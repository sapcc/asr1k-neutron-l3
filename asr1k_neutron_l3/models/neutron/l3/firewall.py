# Copyright 2021 SAP SE
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

from typing import List

from oslo_log import log as logging

from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.models.neutron.l3 import base
from asr1k_neutron_l3.models.neutron.l3 import access_list


LOG = logging.getLogger(__name__)


class FirewallPolicyObject(base.Base):

    PREFIX = None

    @classmethod
    def get_id_by_policy_id(cls, policy_id: str) -> str:
        if not cls.PREFIX:
            raise NotImplementedError("Class derived from 'FirewallPolicyObject' must define static var 'PREFIX'")
        return f"{cls.PREFIX}{policy_id}"

    def __init__(self, policy_id: str):
        self.policy_id = policy_id
        self.id = self.get_id_by_policy_id(self.policy_id)
        super().__init__()


class AccessList(access_list.AccessList, FirewallPolicyObject):

    PREFIX = "ACL-FWAAS-"
    ACTIONS = {
            'allow': 'permit',
            'deny': 'deny',
            'reject': 'deny',
    }

    def __init__(self, policy_id: str, rules: List[dict]):
        self.policy_id = policy_id
        super().__init__(self.get_id_by_policy_id(policy_id))
        for rule in rules:
            if not rule['enabled']:
                # Disabled rules are not programmed
                continue
            if rule['ip_version'] != 4:
                # For the time being, only IPv4 is supported, skip anything else.
                continue

            rule_args = {
                'action': self.ACTIONS[rule['action']],
                'protocol': rule['protocol']
            }

            # check if there is an IP address/CIDR for each direction
            # if so do the whole mask, wildcard dance
            for direction in ('source', 'destination'):
                if rule[f'{direction}_ip_address'] is not None:
                    if '/' in rule[direction + '_ip_address']:
                        rule_args[direction], mask = utils.from_cidr(rule[direction + '_ip_address'])
                        rule_args[direction + '_mask'] = utils.to_wildcard_mask(mask)
                    else:
                        rule_args[direction] = rule[direction + '_ip_address']
                if rule[direction + '_port']:
                    # unpack the port ranges
                    rule_args[direction + '_port_range'] = tuple(rule[direction + '_port'].split(':'))
            self.rules.append(access_list.Rule(**rule_args))
