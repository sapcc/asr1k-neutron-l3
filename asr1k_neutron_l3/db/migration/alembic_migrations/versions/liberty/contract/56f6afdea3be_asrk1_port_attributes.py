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

"""ASRK1 BOOKKEEPING

Revision ID: 56f6afdea3be
Revises: 635cd5df3467
Create Date: 2017-11-13 14:25:39.157776

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '56f6afdea3be'
down_revision = '635cd5df3467'


def upgrade():
    op.create_table(
        'asr1k_extra_atts',
        sa.Column('router_id', sa.String(length=36), nullable=False),
        sa.Column('agent_host', sa.String(length=36), nullable=False),
        sa.Column('port_id', sa.String(length=36), nullable=False),
        sa.Column('segment_id', sa.String(length=36), nullable=False),
        sa.Column('segmentation_id', sa.BigInteger(), nullable=False),
        sa.Column('service_instance', sa.BigInteger(), nullable=False),
        sa.Column('bridge_domain', sa.BigInteger(), nullable=False),
        sa.Column('second_dot1q', sa.BigInteger(), nullable=False),
        sa.Column('deleted_l2', sa.Boolean(), server_default=sa.sql.false()),
        sa.Column('deleted_l3', sa.Boolean(), server_default=sa.sql.false()),

        sa.ForeignKeyConstraint(['router_id'], ['routers.id'],
                                ondelete='CASCADE'),

        sa.PrimaryKeyConstraint("router_id", "agent_host", "port_id"),
        sa.UniqueConstraint('router_id', 'agent_host', 'segmentation_id'),
        sa.UniqueConstraint('router_id', 'agent_host', 'service_instance'),
        sa.UniqueConstraint('router_id', 'agent_host', 'bridge_domain'),
        sa.UniqueConstraint('router_id', 'agent_host', 'segment_id', 'second_dot1q')
    )
