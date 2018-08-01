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
import re
import  time
from oslo_log import log as logging
from asr1k_neutron_l3.models.ssh_legacy import ssh_base
from asr1k_neutron_l3.models.netconf_yang.ny_base import retry_on_failure

LOG = logging.getLogger(__name__)


class DynamicNat(ssh_base.SSHBase):

    @retry_on_failure()
    def delete_interface(self, context):
        config = [member.format(**{'vrf': self.base.vrf,'bridge_domain':self.base.bridge_domain}) for member in DELETE_DYNAMIC_NAT_INTERFACE_FORCED]
        return self._edit_running_config(context, config, action='no_dymanic_nat',accept_failure=True)

    @retry_on_failure()
    def delete_pool(self, context):
        config = [member.format(**{'vrf': self.base.vrf}) for member in DELETE_DYNAMIC_NAT_POOL_FORCED]
        return self._edit_running_config(context, config,action='no_nat_pool',accept_failure=True)



DELETE_DYNAMIC_NAT_INTERFACE_FORCED = ["no ip nat inside source list NAT-{vrf} interface BDI{bridge_domain} vrf {vrf} overload forced"]
DELETE_DYNAMIC_NAT_POOL_FORCED = ["no ip nat inside source list NAT-{vrf} pool {vrf} vrf {vrf} overload forced"]
