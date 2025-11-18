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
from neutron_lib.db import model_base
from neutron_vpnaas.db.vpn import vpn_models
from oslo_log import log

LOG = log.getLogger(__name__)


class ASR1KExtraAttsModel(model_base.BASEV2):
    __tablename__ = 'asr1k_extra_atts'

    def set_external_deleteable(self, value):
        self.external_deleteable = value

    router_id = sa.Column(sa.String(length=36), sa.ForeignKey('routers.id', ondelete='CASCADE'), nullable=False,
                          primary_key=True)
    agent_host = sa.Column(sa.String(length=36), nullable=False, primary_key=True)
    port_id = sa.Column(sa.String(length=36), nullable=False, primary_key=True)
    segment_id = sa.Column(sa.String(length=36), nullable=False)
    segmentation_id = sa.Column(sa.BigInteger(), nullable=False)
    second_dot1q = sa.Column(sa.BigInteger(), nullable=False)
    deleted_l2 = sa.Column('deleted_l2', sa.Boolean())
    deleted_l3 = sa.Column('deleted_l3', sa.Boolean())


class ASR1KRouterAttsModel(model_base.BASEV2):
    __tablename__ = 'asr1k_router_atts'

    router_id = sa.Column(sa.String(length=36), sa.ForeignKey('routers.id', ondelete='CASCADE'), nullable=False,
                          primary_key=True)
    rd = sa.Column(sa.Integer(), nullable=False)
    # format is ip-ip/prefixlen, for ipv6 that'd be 39 chars per ip, 3 for cidr --> max length 83
    dynamic_nat_pool = sa.Column(sa.String(length=83), nullable=True)
    deleted_at = sa.Column(sa.DateTime)


class ASR1KDeviceInfoModel(model_base.BASEV2):
    __tablename__ = 'asr1k_device_info'

    id = sa.Column(sa.String(length=36), nullable=False, primary_key=True)
    host = sa.Column(sa.String(length=36), nullable=False)
    enabled = sa.Column('enabled', sa.Boolean())


class ASR1KTunnelId(model_base.BASEV2):
    __tablename__ = 'asr1k_tunnel_ids'

    agent_host = sa.Column(sa.String(length=36), nullable=False, primary_key=True)
    ipsec_site_connection_id = sa.Column(sa.String(length=36),
                                         sa.ForeignKey('ipsec_site_connections.id', ondelete='CASCADE'),
                                         nullable=False, primary_key=True)
    number = sa.Column(sa.Integer(), nullable=False)

    __table_args__ = (
        sa.UniqueConstraint(
            agent_host, number,
            name='agent_host0number'),
        model_base.BASEV2.__table_args__
    )


class ASR1KInternalTunnelIp(model_base.BASEV2):
    __tablename__ = 'asr1k_internal_tunnel_ips'

    ipsec_site_connection_id = sa.Column(sa.String(length=36),
                                         sa.ForeignKey('ipsec_site_connections.id', ondelete='CASCADE'),
                                         nullable=False, primary_key=True)
    local_cidr_v4 = sa.Column(sa.String(64), nullable=False)
    peer_address_v4 = sa.Column(sa.String(64), nullable=False)
    local_cidr_v6 = sa.Column(sa.String(64), nullable=False)
    peer_address_v6 = sa.Column(sa.String(64), nullable=False)

    ipsec_site_connection = sa.orm.relationship(
        vpn_models.IPsecSiteConnection, load_on_pending=True,
        backref=sa.orm.backref("int_tunnel_ips", lazy='joined',
                               uselist=False, cascade='delete'))


class ASR1KVPNNatAddress(model_base.BASEV2):
    __tablename__ = 'asr1k_vpn_nat_address'

    ipsec_site_connection_id = sa.Column(sa.String(length=36),
                                         sa.ForeignKey('ipsec_site_connections.id', ondelete='CASCADE'),
                                         nullable=False, primary_key=True)
    address = sa.Column(sa.String(64), nullable=False)

    ipsec_site_connection = sa.orm.relationship(
        vpn_models.IPsecSiteConnection, load_on_pending=True,
        backref=sa.orm.backref("nat_address", lazy='joined',
                               uselist=False, cascade='delete'))
