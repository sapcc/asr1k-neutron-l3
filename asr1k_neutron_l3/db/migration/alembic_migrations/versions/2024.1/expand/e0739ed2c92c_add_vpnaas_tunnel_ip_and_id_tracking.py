# Copyright 2025 SAP SE
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

"""Add VPNaas tunnel ip and id tracking tables

Revision ID: e0739ed2c92c
Revises: fe1f53f6a61d
Create Date: 2025-10-10 18:02:08.888398

"""

# revision identifiers, used by Alembic.
revision = 'e0739ed2c92c'
down_revision = 'fe1f53f6a61d'

from alembic import op
import sqlalchemy as sa



def upgrade():
    op.create_table(
        'asr1k_tunnel_ids',
        sa.Column('agent_host', sa.String(length=36), nullable=False),
        sa.Column('ipsec_site_connection_id',
                  sa.String(length=36),
                  sa.ForeignKey('ipsec_site_connections.id', ondelete='CASCADE'),
                  nullable=False, primary_key=True),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.UniqueConstraint('agent_host', 'number', name='agent_host0number'),
    )

    op.create_table(
        'asr1k_internal_tunnel_ips',
            sa.Column('ipsec_site_connection_id',
                      sa.String(length=36),
                      sa.ForeignKey('ipsec_site_connections.id', ondelete='CASCADE'),
                      nullable=False, primary_key=True),
            sa.Column('local_cidr_v4', sa.String(64), nullable=False),
            sa.Column('peer_address_v4', sa.String(64), nullable=False),
            sa.Column('local_cidr_v6', sa.String(64), nullable=False),
            sa.Column('peer_address_v6', sa.String(64), nullable=False),
    )

    op.create_table(
        'asr1k_vpn_nat_address',
            sa.Column('ipsec_site_connection_id',
                      sa.String(length=36),
                      sa.ForeignKey('ipsec_site_connections.id', ondelete='CASCADE'),
                      nullable=False, primary_key=True),
            sa.Column('address', sa.String(64), nullable=False),
    )

