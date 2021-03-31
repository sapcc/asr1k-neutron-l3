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

from neutron_fwaas.services.firewall.service_drivers import driver_api
from oslo_log import helpers as log_helpers
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class ASR1KFWaaSDriver(driver_api.FirewallDriverDB):
    # FIXME: we don't need to implement all of these --> throw away the ones we don't need

    @log_helpers.log_method_call
    def start_rpc_listener(self):
        LOG.debug("No rpc listener available atm, so not starting one")
        return []

    # Firewal Group
    @log_helpers.log_method_call
    def create_firewall_group_precommit(self, context, firewall_group):
        pass

    @log_helpers.log_method_call
    def create_firewall_group_postcommit(self, context, firewall_group):
        pass

    @log_helpers.log_method_call
    def update_firewall_group_precommit(self, context, old_firewall_group,
                                        new_firewall_group):
        pass

    @log_helpers.log_method_call
    def update_firewall_group_postcommit(self, context, old_firewall_group, new_firewall_group):
        pass

    @log_helpers.log_method_call
    def delete_firewall_group_precommit(self, context, firewall_group):
        pass

    @log_helpers.log_method_call
    def delete_firewall_group_postcommit(self, context, firewall_group):
        pass

    # Firewall Policy
    @log_helpers.log_method_call
    def create_firewall_policy_precommit(self, context, firewall_policy):
        pass

    @log_helpers.log_method_call
    def create_firewall_policy_postcommit(self, context, firewall_policy):
        pass

    @log_helpers.log_method_call
    def update_firewall_policy_precommit(self, context, old_firewall_policy, new_firewall_policy):
        pass

    @log_helpers.log_method_call
    def update_firewall_policy_postcommit(self, context, old_firewall_policy, new_firewall_policy):
        pass

    @log_helpers.log_method_call
    def delete_firewall_policy_precommit(self, context, firewall_policy):
        pass

    @log_helpers.log_method_call
    def delete_firewall_policy_postcommit(self, context, firewall_policy):
        pass

    # Firewall Rule
    @log_helpers.log_method_call
    def create_firewall_rule_precommit(self, context, firewall_rule):
        pass

    @log_helpers.log_method_call
    def create_firewall_rule_postcommit(self, context, firewall_rule):
        pass

    @log_helpers.log_method_call
    def update_firewall_rule_precommit(self, context, old_firewall_rule, new_firewall_rule):
        pass

    @log_helpers.log_method_call
    def update_firewall_rule_postcommit(self, context, old_firewall_rule, new_firewall_rule):
        pass

    @log_helpers.log_method_call
    def delete_firewall_rule_precommit(self, context, firewall_rule):
        pass

    @log_helpers.log_method_call
    def delete_firewall_rule_postcommit(self, context, firewall_rule):
        pass

    @log_helpers.log_method_call
    def insert_rule_precommit(self, context, policy_id, rule_info):
        pass

    @log_helpers.log_method_call
    def insert_rule_postcommit(self, context, policy_id, rule_info):
        pass

    @log_helpers.log_method_call
    def remove_rule_precommit(self, context, policy_id, rule_info):
        pass

    @log_helpers.log_method_call
    def remove_rule_postcommit(self, context, policy_id, rule_info):
        pass
