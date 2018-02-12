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
from neutron.db import address_scope_db
from neutron.db import api as db_api
from neutron.db import db_base_plugin_v2
from neutron.db import external_net_db
from neutron.db import models_v2
from neutron.db import portbindings_db
from neutron.plugins.ml2 import models as ml2_models

from oslo_log import helpers as log_helpers
from oslo_log import log
from sqlalchemy import and_
from sqlalchemy import func

from asr1k_neutron_l3.plugins.db import models as asr1k_models

MIN_SERVICE_INSTANCE = 100
MAX_SERVICE_INSTANCE = 8000
MIN_BRIDGE_DOMAIN = 4097
MAX_BRIDGE_DOMAIN = 16000
MIN_SECOND_DOT1Q = 1000
MAX_SECOND_DOT1Q = 4096

MIN_RD = 1
MAX_RD = 65535


LOG = log.getLogger(__name__)


class DBPlugin(db_base_plugin_v2.NeutronDbPluginV2,
               portbindings_db.PortBindingMixin,
               address_scope_db.AddressScopeDbMixin,
               external_net_db.External_net_db_mixin,
               ):

    def __init__(self):
        pass

    def get_ports_with_binding(self, context, network_id):
        with context.session.begin(subtransactions=True):
            query = context.session.query(models_v2.Port)
            query1 = query.join(ml2_models.PortBinding)
            bind_ports = query1.filter(models_v2.Port.network_id == network_id)

            return bind_ports

    def get_ports_with_extra_atts(self, context, ports):

        with context.session.begin(subtransactions=True):
            query = context.session.query(models_v2.Port.id,
                                          models_v2.Port.network_id,
                                          asr1k_models.ASR1KExtraAttsModel.router_id,
                                          asr1k_models.ASR1KExtraAttsModel.service_instance,
                                          asr1k_models.ASR1KExtraAttsModel.bridge_domain,
                                          asr1k_models.ASR1KExtraAttsModel.second_dot1q,
                                          asr1k_models.ASR1KExtraAttsModel.segmentation_id,
                                          asr1k_models.ASR1KExtraAttsModel.deleted_l2,
                                          asr1k_models.ASR1KExtraAttsModel.deleted_l3
                                          ).filter(
                sa.cast(models_v2.Port.id, sa.Text()).in_(ports)
            ).join(asr1k_models.ASR1KExtraAttsModel,
                   and_(asr1k_models.ASR1KExtraAttsModel.port_id == models_v2.Port.id))
            result = []

            for row in query.all():
                result.append({'id': row.id,
                               'network_id': row.network_id,
                               'router_id': row.router_id,
                               'segmentation_id': row.segmentation_id,
                               'service_instance': int(row.service_instance),
                               'bridge_domain': int(row.bridge_domain),
                               'second_dot1q': int(row.second_dot1q),
                               'deleted_l2': int(row.deleted_l2),
                               'deleted_l3': int(row.deleted_l3)
                               })

            return result

    def get_extra_atts_for_routers(self, context, routers):
        return context.session.query(asr1k_models.ASR1KExtraAttsModel).filter(
            sa.cast(asr1k_models.ASR1KExtraAttsModel.router_id, sa.Text()).in_(routers)).all()

    def _get_router_ports_on_networks(self, context):
        query = context.session.query(models_v2.Port.network_id, func.count(models_v2.Port.id).label('port_count')).filter(models_v2.Port.device_owner.like("network:router%")).group_by(models_v2.Port.network_id)
        result = {}
        for row in query.all():
            result[row.network_id] = row.port_count

        return result

    def get_extra_atts(self, context, ports):
        # marks ports that can delete external service instance
        # network_port_count = self._get_router_ports_on_networks(context)
        #
        # query =context.session.query(models_v2.Port.id,models_v2.Port.network_id).filter(sa.cast(models_v2.Port.id, sa.Text()).in_(ports))
        # LOG.debug(str(query))
        #
        # db_ports = self.get_ports(context,filters={'id':ports})#context.session.query(models_v2.Port).filter(sa.cast(models_v2.Port.id, sa.Text()).in_(ports)).all()
        # LOG.debug("******* db ports {}".format(db_ports))
        #
        # port_dict = {}
        # for port in db_ports:
        #     port_dict[port.id] = port.network_id

        extra_atts = context.session.query(asr1k_models.ASR1KExtraAttsModel).filter(
            sa.cast(asr1k_models.ASR1KExtraAttsModel.port_id, sa.Text()).in_(ports)).all()

        for att in extra_atts:

            ports_on_segment = context.session.query(asr1k_models.ASR1KExtraAttsModel).filter(asr1k_models.ASR1KExtraAttsModel.segment_id==att.segment_id).all()

            if len(ports_on_segment) > 1:
                att.set_external_deleteable(False)
            else:
                att.set_external_deleteable(True)

        return extra_atts

    def get_extra_att(self, context, port):
        return context.session.query(asr1k_models.ASR1KExtraAttsModel).filter(
            asr1k_models.ASR1KExtraAttsModel.port_id == port).first()

    def get_router_atts_for_routers(self, context, routers):
        return context.session.query(asr1k_models.ASR1KRouterAttsModel).filter(
            sa.cast(asr1k_models.ASR1KRouterAttsModel.router_id, sa.Text()).in_(routers)).all()

    def get_router_att(self, context, router):
        return context.session.query(asr1k_models.ASR1RouterAttsModel).filter(
            asr1k_models.ASR1KRouterAttsModel.router_id == router).first()


    @log_helpers.log_method_call
    def delete_extra_att(self, context, port_id, l2=None, l3=None):

        delete = False

        extra_att = self.get_extra_att(context, port_id)

        if extra_att is not None:
            if l3 is not None and extra_att.deleted_l2 and l3:
                delete = True
            elif l2 is not None and extra_att.deleted_l3 and l2:
                delete = True

            if delete:
                with context.session.begin(subtransactions=True):
                    context.session.delete(extra_att)
            else:
                updates = {}
                if l2: updates['deleted_l2'] = l2
                if l3: updates['deleted_l3'] = l3

                extra_att.update(updates)
                extra_att.save(context.session)


class ExtraAttsDb(object):

    def __init__(self, router_id, segment, context):
        self.session = db_api.get_session();
        self.context = context

        port = self.context.current

        # check we have a port, segment and binding host

        self.router_id = router_id

        self.port_id = port.get('id')
        self.agent_host = port.get("binding:host_id")
        self.segment_id = None

        if segment is not None:
            self.segment_id = segment.get('id')
            self.segmentation_id = segment.get('segmentation_id')
            if self.segmentation_id < 1 or self.segmentation_id > 4096:
                raise Exception("Invalid segmentation id {} on segment {}".format(self.segmentation_id, self.segment_id))

        self.service_instance = None
        self.bridge_domain = None
        self.second_dot1q = None
        self.deleted_l2 = False
        self.deleted_l3 = False

    @property
    def _port_data_complete(self):
        return self.router_id is not None and self.port_id is not None and self.agent_host is not None and self.segment_id is not None

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

        service_instances = []
        bridge_domains = []
        second_dot1qs = []

        for extra_att in extra_atts:
            service_instances.append(extra_att.service_instance)
            bridge_domains.append(extra_att.bridge_domain)
            if extra_att.segment_id == self.segment_id:
                second_dot1qs.append(extra_att.second_dot1q)

        for x in range(MIN_SERVICE_INSTANCE, MAX_SERVICE_INSTANCE):
            if x not in service_instances:
                self.service_instance = x;
                break

        for x in range(MIN_BRIDGE_DOMAIN, MAX_BRIDGE_DOMAIN):
            if x not in bridge_domains:
                self.bridge_domain = x;
                break

        for x in range(MIN_SECOND_DOT1Q, MAX_SECOND_DOT1Q):
            if x not in second_dot1qs:
                self.second_dot1q = x;
                break

    def update_extra_atts(self):

        if not self._port_data_complete:
            LOG.debug("Skipping L2 extra atts, port not ready")
            return

        if not self._record_exists:
            LOG.debug("L2 extra atts not existing, attempting create")
            self.set_next_entries()

            with self.session.begin(subtransactions=True):
                extra_atts = asr1k_models.ASR1KExtraAttsModel(
                    router_id=self.router_id,
                    agent_host=self.agent_host,
                    port_id=self.port_id,
                    segment_id=self.segment_id,
                    segmentation_id=self.segmentation_id,
                    service_instance=self.service_instance,
                    bridge_domain=self.bridge_domain,
                    second_dot1q=self.second_dot1q,
                    deleted_l2=self.deleted_l2,
                    deleted_l3=self.deleted_l3
                )
                self.session.add(extra_atts)


class RouterAttsDb(object):

    def __init__(self, router_id, context):
        self.session = db_api.get_session();
        self.context = context


        self.router_id = router_id
        self.rd = None


    @property
    def _router_data_complete(self):
        return self.router_id is not None and self.rd is not None

    @property
    def _record_exists(self):
        entry = self.session.query(asr1k_models.ASR1KRouterAttsModel).filter_by(router_id=self.router_id).first()
        return entry is not None

    def set_next_entries(self):
        router_atts = self.session.query(asr1k_models.ASR1KRouterAttsModel).all()

        rds = []

        for router_att in router_atts:
            rds.append(router_att.rd)

        for x in range(MIN_RD, MAX_RD):
            if x not in rds:
                self.rd = x;
                break


    def update_router_atts(self):

        if not self._record_exists:
            LOG.debug("Router atts not existing, attempting create")
            self.set_next_entries()

        if not self._router_data_complete:
            LOG.debug("Skipping router atts, data not complete")
            return

        with self.session.begin(subtransactions=True):
            router_atts = asr1k_models.ASR1KRouterAttsModel(
                router_id=self.router_id,
                rd=self.rd
            )
            self.session.add(router_atts)
