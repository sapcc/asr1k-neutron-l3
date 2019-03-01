# Copyright 2018 SAP SE
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import os
import requests
import re

from oslo_log import log as logging
LOG = logging.getLogger(__name__)


def _get_prometheus_url():
    port = int(os.environ.get('METRICS_PORT', 12415))
    return "http://127.0.0.1:{}/metrics".format(port)

def check_prometheus_metric(needle):
    r = requests.get(_get_prometheus_url())
    if r.ok:
        return re.search(needle, r.text)

    return False