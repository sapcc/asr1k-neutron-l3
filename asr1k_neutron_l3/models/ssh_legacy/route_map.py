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


from asr1k_neutron_l3.models.netconf_yang.ny_base import retry_on_failure
from asr1k_neutron_l3.models.ssh_legacy import ssh_base
from oslo_log import log as logging

LOG  = logging.getLogger(__name__)

class RouteMap(ssh_base.SSHBase):

    @retry_on_failure()
    def delete(self, context):
        config = [member.format(**{'name':self.base.name}) for member in CLEAR_ROUTE_MAP]
        try:
            self._edit_running_config(context, config, 'CLEAR_ROUTE_MAP')
        except:
            LOG.warning("Error executing legacy NC call to delete route map {} on {} , this may be because its already deleted, in which case thie can be ignored.".format(self.base.name, context.host))


CLEAR_ROUTE_MAP = ["no route-map {name}"]

