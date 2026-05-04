# Copyright 2020 SAP SE
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

Revision ID: 6777c66483ab
Revises: 5678db342f9
Create Date: 2020-01-29 14:25:39.157776

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '6777c66483ab'
down_revision = '5678db342f9'


def upgrade():
    op.create_table(
        'asr1k_device_info',
        sa.Column('id',
                  sa.String(length=36),
                  nullable=False,
                  primary_key=True),
        sa.Column('host', sa.String(length=36), nullable=False),
        sa.Column('enabled', sa.Boolean())
    )

    op.create_table(
        'asr1k_router_atts',
        sa.Column('router_id',
                  sa.String(length=36),
                  nullable=False,
                  primary_key=True),
        sa.Column('rd', sa.Integer(), nullable=False),
        sa.Column('deleted_at', sa.DateTime()),
        sa.UniqueConstraint('rd')
    )

    op.create_table(
        'asr1k_extra_atts',
        sa.Column('router_id', sa.String(length=36), nullable=False),
        sa.Column('agent_host', sa.String(length=36), nullable=False),
        sa.Column('port_id', sa.String(length=36), nullable=False),
        sa.Column('segment_id', sa.String(length=36), nullable=False),
        sa.Column('segmentation_id', sa.BigInteger(), nullable=False),
        sa.Column('second_dot1q', sa.BigInteger(), nullable=False),
        sa.Column('deleted_l2', sa.Boolean(), server_default=sa.sql.false()),
        sa.Column('deleted_l3', sa.Boolean(), server_default=sa.sql.false()),
        sa.PrimaryKeyConstraint('router_id', 'agent_host', 'port_id'),
        sa.UniqueConstraint('agent_host', 'second_dot1q')
    )
