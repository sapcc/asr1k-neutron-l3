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

import sqlalchemy as sa

from neutron.db import model_base

from oslo_log import log

LOG = log.getLogger(__name__)


class ASR1KExtraAttsModel(model_base.BASEV2):
    __tablename__ = 'asr1k_extra_atts'

    def set_external_deletable(self, value):
        self.external_deletable = value


    router_id = sa.Column(sa.String(length=36), sa.ForeignKey('routers.id', ondelete='CASCADE'), nullable=False,
                          primary_key=True)
    agent_host = sa.Column(sa.String(length=36), nullable=False, primary_key=True)
    port_id = sa.Column(sa.String(length=36), nullable=False, primary_key=True)
    segment_id = sa.Column(sa.String(length=36), nullable=False)
    segmentation_id = sa.Column(sa.BigInteger(), nullable=False)
    service_instance = sa.Column(sa.BigInteger(), nullable=False)
    bridge_domain = sa.Column(sa.BigInteger(), nullable=False)
    second_dot1q = sa.Column(sa.BigInteger(), nullable=False)
    deleted_l2 = sa.Column('deleted_l2', sa.Boolean())
    deleted_l3 = sa.Column('deleted_l3', sa.Boolean())



class ASR1KRouterAttsModel(model_base.BASEV2):
    __tablename__ = 'asr1k_router_atts'

    router_id = sa.Column(sa.String(length=36), sa.ForeignKey('routers.id', ondelete='CASCADE'), nullable=False,
                          primary_key=True)
    rd = sa.Column(sa.Integer(), nullable=False)
3