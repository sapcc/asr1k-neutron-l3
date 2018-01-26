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


import argparse

from oslo_utils import importutils

from neutron.common import eventlet_utils

eventlet_utils.monkey_patch()

ACTION_MODULE = 'asr1k_neutron_l3.cli.actions.'


class Execute(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        super(Execute, self).__init__(option_strings, dest, **kwargs)
        self.actions = {"validate": "validate.Validate", "update": "update.Update", "delete": "delete.Delete","netconf": "netconf.Netconf"}

    def __call__(self, parser, namespace, values, option_string=None):
        action = self.actions.get(values)
        if action:
            instance = importutils.import_object(ACTION_MODULE + action, namespace)

            instance.execute()


def main():
    parser = argparse.ArgumentParser(prog='asr1k_utils', description='Operations utilities for ASR1k driver.')

    parser.add_argument('command',
                        help='command to execute', action=Execute, choices=["validate", "update", "delete", "netconf"])

    parser.add_argument('--router-id', dest='router_id',
                        help='router id', action='store')


    parser.add_argument('--confirm', dest='confirm', action='store_true',
                        help='Confirm high risk action')

    parser.add_argument('--config-file', dest='config', action='append',
                        default=["/etc/neutron/asr1k.conf", "/etc/neutron/neutron.conf"],
                        help='Configuration files')

    parser.add_argument('--log',dest='log', action='store_true',
                       help='Enable openstack log output')

    parser.parse_args()
