# Copyright 2024 SAP SE
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
#

"""Add dynamic nat pool to router atts

Revision ID: fe1f53f6a61d
Revises: 5678db342f9
Create Date: 2024-02-28 14:31:08.477571

"""

# revision identifiers, used by Alembic.
revision = 'fe1f53f6a61d'
down_revision = '5678db342f9'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('asr1k_router_atts', sa.Column('dynamic_nat_pool', sa.String(length=83), nullable=True))
