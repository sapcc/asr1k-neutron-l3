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

import time
from oslo_config import cfg

from asr1k_neutron_l3.common.prometheus_monitor import PrometheusMonitor
from asr1k_neutron_l3.tests.unit import utils
from neutron.tests import base

cfg.CONF.use_stderr = False
cfg.CONF(args=[])

class PrometheusMonitorTest(base.BaseTestCase):
    def _setUp(self):
        super(PrometheusMonitorTest, self).setUp()
        self.host = 'test_host'

        self.monitor = PrometheusMonitor(host=self.host,namespace="neutron_asr1k",type="test")
        self.monitor.start()

    def test_l3_orphan_count(self):
        host = self.host
        PrometheusMonitor().l3_orphan_count.labels(device=host).set(0)
        PrometheusMonitor().l3_orphan_count.labels(device=host).inc()
        self.assertTrue(utils.check_prometheus_metric(
            'neutron_asr1k_test_l3_orphan_count{device="test_host",host="test_host"} 1.0'
        ))

    def test_yang_operation_duration(self):
        host = self.host
        with PrometheusMonitor().yang_operation_duration.labels(
                device=host, entity='test',
                action='test'
        ).time():
            time.sleep(1)

        self.assertTrue(utils.check_prometheus_metric('neutron_asr1k_test_yang_operation_duration_bucket'))
