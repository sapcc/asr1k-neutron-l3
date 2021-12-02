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

import random
from typing import Dict

from neutron.db import address_scope_db
from neutron.db import db_base_plugin_v2
from neutron.db import external_net_db
from neutron.db import l3_agentschedulers_db
from neutron.db import l3_db
from neutron.db import models_v2
from neutron.db import segments_db
from neutron.db.models import agent as agent_model
from neutron.db.models import l3 as l3_models
from neutron.db.models import l3agent as l3agent_models
from neutron.db.models import segment as segment_models
from neutron.plugins.ml2 import db as ml2_db
from neutron.plugins.ml2 import models as ml2_models
from neutron_lib import constants as n_constants
from neutron_lib import context as n_context
from neutron_lib.api.definitions import portbindings
from neutron_lib.exceptions import l3 as l3_exc
from networking_bgpvpn.neutron.db import bgpvpn_db
from neutron_lib.db import api as db_api
from oslo_log import helpers as log_helpers
from oslo_log import log
from oslo_utils import timeutils
import sqlalchemy as sa
from sqlalchemy import and_
from sqlalchemy import func

from asr1k_neutron_l3.common import asr1k_constants as constants
from asr1k_neutron_l3.common import asr1k_exceptions
from asr1k_neutron_l3.plugins.db import models as asr1k_models

MIN_DOT1Q = 1000
MAX_DOT1Q = 4096

MIN_SECOND_DOT1Q = 500
MAX_SECOND_DOT1Q = 3904  # to_bridge_domain(MAX_SECOND_DOT1Q) <= 8000 on 16.9!

MIN_RD = 1
MAX_RD = 65535

LOG = log.getLogger(__name__)


_db_plugin_instance = None


def get_db_plugin():
    """Get the DBPlugin singleton"""
    global _db_plugin_instance
    if _db_plugin_instance is None:
        _db_plugin_instance = DBPlugin()
    return _db_plugin_instance


class DBPlugin(db_base_plugin_v2.NeutronDbPluginV2,
               address_scope_db.AddressScopeDbMixin,
               external_net_db.External_net_db_mixin,
               l3_db.L3_NAT_dbonly_mixin,
               l3_agentschedulers_db.L3AgentSchedulerDbMixin,
               bgpvpn_db.BGPVPNPluginDb
               ):
    def __init__(self):
        super(DBPlugin, self).__init__()

    def get_bgpvpns_by_router_id(self, context, router_id, filters=None, fields=None):
        query = context.session.query(bgpvpn_db.BGPVPN)
        query = query.join(bgpvpn_db.BGPVPN.router_associations)
        query = query.filter(bgpvpn_db.BGPVPNRouterAssociation.router_id == router_id)
        query = query.distinct()
        return query.all()

    def get_bgpvpn_advertise_extra_routes_by_router_id(self, context, router_id):
        """Advertise route mode for bgpvpn - only False if all router associations have this turned off"""
        query = context.session.query(bgpvpn_db.BGPVPNRouterAssociation.advertise_extra_routes)
        query = query.filter(bgpvpn_db.BGPVPNRouterAssociation.router_id == router_id)
        for entry in query.all():
            if entry.advertise_extra_routes:
                return True
        return False

    def get_network_port_count_per_agent(self, context: n_context.Context, network_id: str) -> Dict[str, int]:
        query = context.session.query(asr1k_models.ASR1KExtraAttsModel.agent_host,
                                      func.count(asr1k_models.ASR1KExtraAttsModel.port_id).label('port_count')) \
            .join(segment_models.NetworkSegment,
                  segment_models.NetworkSegment.id == asr1k_models.ASR1KExtraAttsModel.segment_id) \
            .filter(segment_models.NetworkSegment.network_id == network_id) \
            .group_by(asr1k_models.ASR1KExtraAttsModel.agent_host)
        return {x.agent_host: x.port_count for x in query.all()}

    def ensure_snat_mode(self, context, port_id, mode):
        if port_id is None:
            LOG.warning("Asked to ensure SNAT mode for port==None, can't do anything.")
            return
        port = self.get_port(context, port_id)

        LOG.debug(port)

        fixed_ips = port.get('fixed_ips', [])
        update = False
        if mode == constants.SNAT_MODE_POOL and len(fixed_ips) == 1:
            gw_ip = fixed_ips[0]
            fixed_ips.append({'subnet_id': gw_ip.get('subnet_id')})
            update = True
        elif mode == constants.SNAT_MODE_INTERFACE and len(fixed_ips) == 2:
            update = True
            fixed_ips.pop()

        if update:
            self.update_port(context, port_id, {'port': port})

    def update_router_status(self, context, router_id, status):
        try:
            # Try using new session to for router updates
            router = {'router': {'status': status}}
            ctx = n_context.get_admin_context()
            self.update_router(ctx, router_id, router)
        except l3_exc.RouterNotFound:
            LOG.info("Update to status to {} for router {} failed, router not found.".format(status, router_id))
            return

    def get_ports_with_extra_atts(self, context, ports, host):
        query = context.session.query(models_v2.Port.id,
                                      models_v2.Port.network_id,
                                      asr1k_models.ASR1KExtraAttsModel.router_id,
                                      asr1k_models.ASR1KExtraAttsModel.second_dot1q,
                                      asr1k_models.ASR1KExtraAttsModel.segmentation_id,
                                      asr1k_models.ASR1KExtraAttsModel.deleted_l2,
                                      asr1k_models.ASR1KExtraAttsModel.deleted_l3
                                      ).filter(
            sa.cast(models_v2.Port.id, sa.Text()).in_(ports)
        ).filter(asr1k_models.ASR1KExtraAttsModel.agent_host == host
                 ).join(asr1k_models.ASR1KExtraAttsModel,
                        and_(asr1k_models.ASR1KExtraAttsModel.port_id == models_v2.Port.id))
        result = []

        for row in query.all():
            result.append({'id': row.id,
                           'port_id': row.id,
                           'network_id': row.network_id,
                           'router_id': row.router_id,
                           'segmentation_id': row.segmentation_id,
                           'second_dot1q': int(row.second_dot1q),
                           'deleted_l2': int(row.deleted_l2),
                           'deleted_l3': int(row.deleted_l3)
                           })

        return result

    def get_all_extra_atts(self, context, host):
        if host is None:
            return context.session.query(asr1k_models.ASR1KExtraAttsModel).all()
        else:
            return context.session.query(asr1k_models.ASR1KExtraAttsModel).filter(
                asr1k_models.ASR1KExtraAttsModel.agent_host == host).all()

    def get_extra_atts_for_routers(self, context, routers, host=None):
        if routers is None:
            return []
        if host is None:
            return context.session.query(asr1k_models.ASR1KExtraAttsModel).filter(
                sa.cast(asr1k_models.ASR1KExtraAttsModel.router_id, sa.Text()).in_(routers)).all()
        else:
            query = context.session.query(asr1k_models.ASR1KExtraAttsModel)
            query = query.filter(asr1k_models.ASR1KExtraAttsModel.agent_host == host)
            query = query.filter(sa.cast(asr1k_models.ASR1KExtraAttsModel.router_id, sa.Text()).in_(routers))
            return query.all()

    def get_extra_atts_for_ports(self, context, ports):
        if ports is None:
            return []
        return context.session.query(asr1k_models.ASR1KExtraAttsModel).filter(
            sa.cast(asr1k_models.ASR1KExtraAttsModel.port_id, sa.Text()).in_(ports)).all()

    def _get_router_ports_on_networks(self, context):
        query = context.session.query(models_v2.Port.network_id,
                                      func.count(models_v2.Port.id).label('port_count')).filter(
            models_v2.Port.device_owner.like("network:router%")).group_by(models_v2.Port.network_id)
        result = {}
        for row in query.all():
            result[row.network_id] = row.port_count

        return result

    def get_orphaned_extra_atts_router_ids(self, context, host):
        subquery = context.session.query(l3_models.Router.id)

        query = context.session.query(asr1k_models.ASR1KExtraAttsModel.router_id)
        query = query.filter(asr1k_models.ASR1KExtraAttsModel.agent_host == host)
        query = query.filter(asr1k_models.ASR1KExtraAttsModel.router_id.notin_(subquery))
        result = []
        for row in query.all():
            if row.router_id not in result:
                result.append(row.router_id)

        # TODO we need to conisder orphaned ports, at least at L2 level
        # but I think if we just do the below the whole router will get deleted
        # for a single orpshaned port

        # subquery = context.session.query(models_v2.Port.device_id)
        #
        # query = context.session.query(asr1k_models.ASR1KExtraAttsModel.router_id)
        # query = query.filter(asr1k_models.ASR1KExtraAttsModel.agent_host == host)
        # query = query.filter(asr1k_models.ASR1KExtraAttsModel.router_id.notin_(subquery))
        # for row in query.all():
        #     result.append(row.router_id)

        if not bool(result):
            result = None

        return result

    def get_orphaned_extra_atts_port_ids(self, context, host):
        subquery = context.session.query(models_v2.Port.id)

        query = context.session.query(asr1k_models.ASR1KExtraAttsModel.port_id).filter(
            asr1k_models.ASR1KExtraAttsModel.agent_host == host).filter(
            asr1k_models.ASR1KExtraAttsModel.port_id.notin_(subquery))
        result = []
        for row in query.all():
            result.append(row.port_id)

        if not bool(result):
            result = None

        return result

    def get_orphaned_extra_atts(self, context, host):
        routers = self.get_orphaned_extra_atts_router_ids(context, host)
        router_extra_atts = self.get_extra_atts_for_routers(context, routers)

        ports = self.get_orphaned_extra_atts_port_ids(context, host)
        port_extra_atts = self.get_extra_atts_for_ports(context, ports)

        return router_extra_atts + list(set(port_extra_atts) - set(router_extra_atts))

    def get_orphaned_router_atts_router_ids(self, context, host):
        subquery = context.session.query(l3_models.Router.id)
        # TODO filter
        query = context.session.query(asr1k_models.ASR1KRouterAttsModel.router_id).filter(
            asr1k_models.ASR1KRouterAttsModel.router_id.notin_(subquery))\

        result = []
        for row in query.all():
            result.append(row.router_id)

        if not bool(result):
            result = None

        return result

    def get_orphaned_router_atts(self, context, host):
        routers = self.get_orphaned_router_atts_router_ids(context, host)
        router_atts = self.get_router_atts_for_routers(context, routers)

        return router_atts

    def get_interface_ports(self, context, limit=1, offset=1, host=None):
        query = context.session.query(models_v2.Port.id,
                                      models_v2.Port.network_id,
                                      asr1k_models.ASR1KExtraAttsModel.router_id,
                                      asr1k_models.ASR1KExtraAttsModel.second_dot1q,
                                      asr1k_models.ASR1KExtraAttsModel.segmentation_id,
                                      asr1k_models.ASR1KExtraAttsModel.deleted_l2,
                                      asr1k_models.ASR1KExtraAttsModel.deleted_l3
                                      ).filter(
            models_v2.Port.device_owner.like("network:router%")).filter(
            asr1k_models.ASR1KExtraAttsModel.agent_host == host

        ).join(asr1k_models.ASR1KExtraAttsModel,
               and_(asr1k_models.ASR1KExtraAttsModel.port_id == models_v2.Port.id)).limit(limit).offset(offset)
        result = []

        for row in query.all():
            result.append({'id': row.id,
                           'port_id': row.id,
                           'network_id': row.network_id,
                           'router_id': row.router_id,
                           'segmentation_id': row.segmentation_id,
                           'second_dot1q': int(row.second_dot1q),
                           'deleted_l2': int(row.deleted_l2),
                           'deleted_l3': int(row.deleted_l3)
                           })

        return result

    def get_networks_with_asr1k_ports(self, context, limit=None, offset=None, host=None, networks=None):
        # get networks with segment information
        squery = (context.session.query(segment_models.NetworkSegment.id,
                                        segment_models.NetworkSegment.network_id,
                                        asr1k_models.ASR1KExtraAttsModel.segmentation_id)
                  .join(asr1k_models.ASR1KExtraAttsModel,
                        asr1k_models.ASR1KExtraAttsModel.segment_id == segment_models.NetworkSegment.id)
                  .distinct()
                  )
        if offset:
            squery = squery.filter(segment_models.NetworkSegment.network_id > offset)
        if networks:
            squery = squery.filter(segment_models.NetworkSegment.network_id.in_(networks))
        if host is not None:
            squery = squery.filter(asr1k_models.ASR1KExtraAttsModel.agent_host == host)
        squery = squery.order_by(segment_models.NetworkSegment.network_id.asc())
        if limit:
            squery = squery.limit(limit)

        # get all ports for each network/segment
        result = []
        for dbsegment in squery.all():
            query = context.session.query(models_v2.Port.id,
                                          models_v2.Port.network_id,
                                          asr1k_models.ASR1KExtraAttsModel.router_id,
                                          asr1k_models.ASR1KExtraAttsModel.second_dot1q,
                                          asr1k_models.ASR1KExtraAttsModel.segmentation_id,
                                          asr1k_models.ASR1KExtraAttsModel.deleted_l2,
                                          asr1k_models.ASR1KExtraAttsModel.deleted_l3
                                          ).filter(
                models_v2.Port.device_owner.like("network:router%"))
            if host is not None:
                query = query.filter(asr1k_models.ASR1KExtraAttsModel.agent_host == host)

            query = (query.filter(asr1k_models.ASR1KExtraAttsModel.segment_id == dbsegment.id)
                          .join(asr1k_models.ASR1KExtraAttsModel,
                                asr1k_models.ASR1KExtraAttsModel.port_id == models_v2.Port.id))

            ports = []
            for row in query.all():
                # id is duplicated by port_id here, as different parts of the code use either id or port_id
                ports.append({'id': row.id,
                              'port_id': row.id,
                              'network_id': row.network_id,
                              'router_id': row.router_id,
                              'segmentation_id': row.segmentation_id,
                              'second_dot1q': int(row.second_dot1q),
                              'deleted_l2': int(row.deleted_l2),
                              'deleted_l3': int(row.deleted_l3)
                              })
            result.append({
                'network_id': dbsegment.network_id,
                'segmentation_id': dbsegment.segmentation_id,
                'ports': ports
            })

        return result

    def get_asr1k_hosts_for_network(self, context, network_id):
        query = (context.session.query(asr1k_models.ASR1KExtraAttsModel.agent_host)
                 .join(segment_models.NetworkSegment,
                       asr1k_models.ASR1KExtraAttsModel.segment_id == segment_models.NetworkSegment.id)
                 .filter(segment_models.NetworkSegment.network_id == network_id)
                 .distinct())

        return [row.agent_host for row in query.all()]

    def get_router_ports(self, context, id):
        query = context.session.query(models_v2.Port).join(ml2_models.PortBinding,
                                                           ml2_models.PortBinding.port_id == models_v2.Port.id)
        ports = query.filter(models_v2.Port.device_id == id)

        result = []
        for port in ports:
            port_dict = self._make_port_dict(port)
            if portbindings.HOST_ID not in port_dict:
                port_dict[portbindings.HOST_ID] = port.port_bindings[0].host

            result.append(port_dict)

        return result

    def get_ports_for_router_ids(self, context, ids):
        query = context.session.query(models_v2.Port).join(ml2_models.PortBinding,
                                                           ml2_models.PortBinding.port_id == models_v2.Port.id)
        ports = query.filter(sa.cast(models_v2.Port.device_id, sa.Text()).in_(ids))

        result = []
        for port in ports:
            port_dict = self._make_port_dict(port)
            if portbindings.HOST_ID not in port_dict:
                port_dict[portbindings.HOST_ID] = port.port_bindings[0].host

            result.append(port_dict)

        return result

    def get_router_segment_for_port(self, context, router_id, port_id):
        agents = self.get_l3_agents_hosting_routers(context, [router_id], admin_state_up=True)
        if len(agents) > 0:
            host = agents[0].host
            binding_levels = ml2_db.get_binding_levels(context, port_id, host)
            if len(binding_levels) > 1:
                # Assuming only two levels for now
                return segments_db.get_segment_by_id(context, binding_levels[1].segment_id)

    def get_extra_atts(self, context, ports, host):
        extra_atts = context.session.query(asr1k_models.ASR1KExtraAttsModel).filter(
            sa.cast(asr1k_models.ASR1KExtraAttsModel.port_id, sa.Text()).in_(ports)
        ).filter(asr1k_models.ASR1KExtraAttsModel.agent_host == host
                 ).all()

        for att in extra_atts:

            ports_on_segment = context.session.query(asr1k_models.ASR1KExtraAttsModel).filter(
                asr1k_models.ASR1KExtraAttsModel.segment_id == att.segment_id).filter(
                asr1k_models.ASR1KExtraAttsModel.agent_host == host).all()

            if len(ports_on_segment) > 1:
                att.set_external_deleteable(False)
            else:
                att.set_external_deleteable(True)

        return extra_atts

    def get_extra_att(self, context, port):
        with context.session.begin(subtransactions=True):
            return context.session.query(asr1k_models.ASR1KExtraAttsModel).filter(
                asr1k_models.ASR1KExtraAttsModel.port_id == port).first()

    def get_all_router_ids(self, context, host=None):
        if host is None:
            routers = context.session.query(l3_models.Router.id).all()
        else:
            query = context.session.query(l3_models.Router.id)
            query = query.join(l3agent_models.RouterL3AgentBinding,
                               l3_models.Router.id == l3agent_models.RouterL3AgentBinding.router_id)
            query = query.join(agent_model.Agent,
                               l3agent_models.RouterL3AgentBinding.l3_agent_id == agent_model.Agent.id)
            query = query.filter(agent_model.Agent.host == host)
            routers = query.all()

        result = []
        for entry in routers:
            result.append(entry.id)

        return result

    def get_router_atts_for_routers(self, context, routers):

        if routers is None:
            return []
        return context.session.query(asr1k_models.ASR1KRouterAttsModel).filter(
            sa.cast(asr1k_models.ASR1KRouterAttsModel.router_id, sa.Text()).in_(routers)).all()

    def get_router_att(self, context, router):
        return context.session.query(asr1k_models.ASR1KRouterAttsModel).filter(
            asr1k_models.ASR1KRouterAttsModel.router_id == router).first()

    def get_deleted_router_atts(self, context):
        return context.session.query(asr1k_models.ASR1KRouterAttsModel).filter(
            asr1k_models.ASR1KRouterAttsModel.deleted_at.isnot(None)).all()

    @log_helpers.log_method_call
    def delete_extra_att(self, context, port_id, l2=None, l3=None):
        delete = False

        extra_att = self.get_extra_att(context, port_id)
        if extra_att is not None:
            if l3 is not None and extra_att.deleted_l2 and l3:
                delete = True
            elif l2 is not None and extra_att.deleted_l3 and l2:
                delete = True

            with context.session.begin(subtransactions=True):
                if delete:

                    context.session.delete(extra_att)
                else:
                    updates = {}
                    if l2:
                        updates['deleted_l2'] = l2
                    if l3:
                        updates['deleted_l3'] = l3

                    extra_att.update(updates)
                    extra_att.save(context.session)

    def delete_router_att(self, context, router_id):
        router_att = self.get_router_att(context, router_id)
        if router_att is not None:
            with context.session.begin(subtransactions=True):
                if router_att.deleted_at is not None:
                    context.session.delete(router_att)
                else:
                    router_att.update({'deleted_at': timeutils.utcnow()})
                    router_att.save(context.session)

    def get_device_info(self, context, host):
        result = {}

        infos = context.session.query(asr1k_models.ASR1KDeviceInfoModel).filter(
            asr1k_models.ASR1KDeviceInfoModel.host == host).all()
        for info in infos:
            result[info.id] = info
        return result

    def get_usage_stats(self, context, host):
        agent = self._get_agent_by_type_and_host(context, constants.AGENT_TYPE_ASR1K_L3, host)

        active_router_ids = []
        error_router_ids = []
        active_interface_ids = []
        error_interface_ids = []
        active_gateway_ids = []
        error_gateway_ids = []
        active_floating_ip_ids = []
        error_floating_ip_ids = []

        if agent is not None:
            routers = self.list_routers_on_l3_agent(context, agent.id).get('routers')
            for router in routers:
                router_id = router.get('id')
                if router.get('status') == n_constants.ACTIVE:
                    active_router_ids.append(router_id)
                else:
                    error_router_ids.append(router_id)

            routers = error_router_ids + active_router_ids
            ports = self.get_ports_for_router_ids(context, routers)
            for port in ports:
                if port.get('device_owner') == 'network:router_interface':
                    self.__filter_port_stats(port, active_interface_ids, error_interface_ids)

                if port.get('device_owner') == 'network:router_gateway':
                    self.__filter_port_stats(port, active_gateway_ids, error_gateway_ids)

            floating_ips = self.get_floatingips(context, {'router_id': routers})
            for floating_ip in floating_ips:
                if floating_ip.get('status') == n_constants.ACTIVE:
                    active_floating_ip_ids.append(floating_ip.get('id'))
                else:
                    error_floating_ip_ids.append(floating_ip.get('id'))

        return {'active': {'routers': len(active_router_ids), 'gateway_ports': len(active_gateway_ids),
                           'interface_ports': len(active_interface_ids), 'floating_ips': len(active_floating_ip_ids)},
                'error': {'routers': len(error_router_ids), 'gateway_ports': len(error_gateway_ids),
                          'interface_ports': len(error_interface_ids), 'floating_ips': len(error_floating_ip_ids)}}

    def __filter_port_stats(self, port, active_port_list, error_port_list):
        status = port.get('status')
        port_id = port.get('id')
        if status == n_constants.PORT_STATUS_ACTIVE:
            active_port_list.append(port_id)
        else:
            error_port_list.append(port_id)


class ExtraAttsDb(object):

    @classmethod
    def ensure(cls, router_id, port, segment, clean_old):
        context = n_context.get_admin_context()
        ExtraAttsDb(context, router_id, port, segment)._ensure(clean_old)

    def __init__(self, context, router_id, port, segment):
        self.session = db_api.get_writer_session()
        self.context = context

        # check we have a port, segment and binding host

        self.router_id = router_id

        self.port_id = port.get('id')
        self.agent_host = port.get("binding:host_id")
        self.segment_id = None
        self.segmentation_id = None
        if segment is not None:
            self.segment_id = segment.get('id')
            self.segmentation_id = segment.get('segmentation_id')
            if self.segmentation_id is None or self.segmentation_id < 1 or self.segmentation_id > 4096:
                raise Exception(
                    "Invalid segmentation id {} on segment {}".format(self.segmentation_id, self.segment_id))
        else:
            raise Exception(
                "No segment for for port {}".format(self.port_id))
        self.second_dot1q = None
        self.deleted_l2 = False
        self.deleted_l3 = False

    @property
    def _record_exists(self):
        entry = self.session.query(asr1k_models.ASR1KExtraAttsModel).filter_by(router_id=self.router_id,
                                                                               agent_host=self.agent_host,
                                                                               port_id=self.port_id,
                                                                               segment_id=self.segment_id
                                                                               ).first()
        return entry is not None

    def set_next_entries(self):
        extra_atts = self.session.query(asr1k_models.ASR1KExtraAttsModel).filter_by(agent_host=self.agent_host)
        second_dot1qs_used = set([item.second_dot1q for item in extra_atts])
        second_dot1qs_available = list(set(range(MIN_SECOND_DOT1Q, MAX_SECOND_DOT1Q)) - second_dot1qs_used)
        if len(second_dot1qs_available) == 0:
            raise asr1k_exceptions.SecondDot1QPoolExhausted(agent_host=self.agent_host)
        self.second_dot1q = random.choice(second_dot1qs_available)

    def _ensure(self, clean_old):
        if clean_old and self.agent_host:
            with self.session.begin(subtransactions=True):
                old_data = self.session.query(asr1k_models.ASR1KExtraAttsModel)\
                                       .filter(asr1k_models.ASR1KExtraAttsModel.port_id == self.port_id,
                                               asr1k_models.ASR1KExtraAttsModel.agent_host != self.agent_host)
                if old_data:
                    LOG.debug("Port %s had dangling extra atts on agent %s, deleting", self.port_id,
                              ", ".join(od.agent_host for od in old_data.all()))
                    old_data.delete()

        if not self._record_exists:
            LOG.debug("L2 extra atts not existing, attempting create")

            with self.session.begin(subtransactions=True):
                self.set_next_entries()
                extra_atts = asr1k_models.ASR1KExtraAttsModel(
                    router_id=self.router_id,
                    agent_host=self.agent_host,
                    port_id=self.port_id,
                    segment_id=self.segment_id,
                    segmentation_id=self.segmentation_id,
                    second_dot1q=self.second_dot1q,
                    deleted_l2=self.deleted_l2,
                    deleted_l3=self.deleted_l3
                )
                self.session.add(extra_atts)


class RouterAttsDb(object):
    @classmethod
    def ensure(cls, context, id):
        RouterAttsDb(context, id)._ensure()

    def __init__(self, context, router_id):
        self.session = db_api.get_writer_session()
        self.context = context

        self.router_id = router_id
        self.rd = 0
        self.deleted_at = None

    @property
    def _record_exists(self):
        entry = self.session.query(asr1k_models.ASR1KRouterAttsModel).filter_by(router_id=self.router_id).first()
        return entry is not None

    def _set_next_entries(self):
        rds_used = set([item.rd for item in self.session.query(asr1k_models.ASR1KRouterAttsModel)])
        rds_available = list(set(range(MIN_RD, MAX_RD)) - rds_used)
        if len(rds_available) == 0:
            raise asr1k_exceptions.RdPoolExhausted()
        self.rd = random.choice(rds_available)

    def _ensure(self):
        if not self._record_exists:
            LOG.debug("Router atts not existing, attempting create")

            with self.session.begin(subtransactions=True):
                self._set_next_entries()
                router_atts = asr1k_models.ASR1KRouterAttsModel(
                    router_id=self.router_id,
                    rd=self.rd,
                    deleted_at=self.deleted_at
                )
                self.session.add(router_atts)


class DeviceInfoDb(object):
    def __init__(self, context, id, host, enabled):
        self.session = db_api.get_writer_session()
        self.context = context
        self.id = id
        self.host = host
        self.enabled = enabled

    @property
    def _record_exists(self):
        entry = self.session.query(asr1k_models.ASR1KDeviceInfoModel).filter_by(id=self.id).first()
        return entry

    def update(self):
        with self.session.begin(subtransactions=True):
            device_info = asr1k_models.ASR1KDeviceInfoModel(
                id=self.id,
                host=self.host,
                enabled=self.enabled
            )
            record = self._record_exists

            if record is not None:
                record.update(device_info)
            else:
                self.session.add(device_info)
