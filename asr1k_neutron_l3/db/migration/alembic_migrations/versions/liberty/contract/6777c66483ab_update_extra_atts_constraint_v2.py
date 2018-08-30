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

Revision ID: 6777c66483ab
Revises: 5767b6d423d7
Create Date: 2018-08-29 10:25:43.37445

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '6777c66483ab'
down_revision = '5767b6d423d7'


def upgrade():
    op.drop_constraint("asr1k_extra_atts_router_id_agent_host_second_dot_key", 'asr1k_extra_atts', 'unique')
    op.create_unique_constraint('asr1k_extra_atts_router_id_agent_host_second_dot_key', 'asr1k_extra_atts',['agent_host','second_dot1q'])