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

Revision ID: 27342df5a5fea
Revises: 3746afa3a3bd
Create Date: 2018-04-18 07:38:21.253453

"""

import sqlalchemy as sa
from alembic import op




# revision identifiers, used by Alembic.
revision = '32442df5a4deb'
down_revision = '27342df5a5fea'


def upgrade():
    op.drop_constraint("asr1k_router_atts_router_id_fkey", 'asr1k_router_atts', 'foreignkey')
    op.create_unique_constraint('uq_rd', 'asr1k_router_atts',['rd'])
    op.add_column('asr1k_router_atts', sa.Column('deleted_at',sa.DateTime))
