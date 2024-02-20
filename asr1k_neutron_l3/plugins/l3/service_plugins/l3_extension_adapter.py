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
from collections import OrderedDict
import ipaddress
import json
import time

from neutron.db import dns_db
from neutron.db import extraroute_db
from neutron.db import l3_gwmode_db as l3_db
from neutron.extensions.tagging import TAG_PLUGIN_TYPE
from neutron_lib.api.definitions import availability_zone as az_def
from neutron_lib.api.definitions import l3 as l3_apidef
from neutron_lib import exceptions as nl_exc
from neutron_lib.plugins import constants as plugin_constants
from neutron_lib import constants as nl_const
from neutron_lib.callbacks import events
from neutron_lib.callbacks import registry
from neutron_lib.callbacks import resources
from neutron_lib.db import api as db_api
from neutron_lib.plugins import directory
from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log
from oslo_serialization import jsonutils

from asr1k_neutron_l3.common import asr1k_constants as constants
from asr1k_neutron_l3.common import asr1k_exceptions as asr1k_exc
from asr1k_neutron_l3.common import cache_utils
from asr1k_neutron_l3.common import utils
from asr1k_neutron_l3.common.instrument import instrument
from asr1k_neutron_l3.extensions import asr1koperations as asr1k_ext
from asr1k_neutron_l3.plugins.db import asr1k_db
from asr1k_neutron_l3.plugins.db import models as asr1k_models
from asr1k_neutron_l3.plugins.l3.rpc import ask1k_l3_notifier
from asr1k_neutron_l3.plugins.l3.schedulers import asr1k_scheduler_db
from asr1k_neutron_l3.plugins.l3.service_plugins.initializer import Initializer

LOG = log.getLogger(__name__)


@registry.has_registry_receivers
class L3RpcNotifierMixin(object):
    """Mixin class to add rpc notifier attribute to db_base_plugin_v2."""

    @property
    def l3_rpc_notifier(self):
        if not hasattr(self, '_l3_rpc_notifier') or \
                not isinstance(self._l3_rpc_notifier, ask1k_l3_notifier.ASR1KAgentNotifyAPI):
            self._l3_rpc_notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()
        return self._l3_rpc_notifier

    @l3_rpc_notifier.setter
    def l3_rpc_notifier(self, value):
        self._l3_rpc_notifier = value

    @log_helpers.log_method_call
    def notify_router_updated(self, context, router_id,
                              operation=None):
        if router_id:
            self.l3_rpc_notifier.routers_updated(
                context, [router_id], operation)

    @log_helpers.log_method_call
    def notify_routers_updated(self, context, router_ids,
                               operation=None, data=None):
        if router_ids:
            self.l3_rpc_notifier.routers_updated(
                context, router_ids, operation, data)

    @log_helpers.log_method_call
    def notify_router_deleted(self, context, router_id):
        self.l3_rpc_notifier.router_deleted(context, router_id)

    @log_helpers.log_method_call
    def notify_router_sync(self, context, router_id):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()
        return notifier.router_sync(context, router_id)

    @log_helpers.log_method_call
    def notify_router_teardown(self, context, router_id):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        return notifier.router_teardown(context, router_id)

    @log_helpers.log_method_call
    def notify_router_validate(self, context, router_id):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        return notifier.router_validate(context, router_id)

    @log_helpers.log_method_call
    def notify_network_sync(self, context, network_id):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()
        return notifier.network_sync(context, network_id)

    @log_helpers.log_method_call
    def notify_network_validate(self, context, network_id):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        return notifier.network_validate(context, network_id)

    @log_helpers.log_method_call
    def notify_interface_statistics(self, context, router_id):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        return notifier.interface_statistics(context, router_id)

    @log_helpers.log_method_call
    def notify_show_orphans(self, context, host):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        return notifier.show_orphans(context, host)

    @log_helpers.log_method_call
    def notify_delete_orphans(self, context, host):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        return notifier.delete_orphans(context, host)

    @log_helpers.log_method_call
    def notify_list_devices(self, context, host):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        return notifier.list_devices(context, host)

    @log_helpers.log_method_call
    def notify_show_device(self, context, host, device_id):
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()

        return notifier.show_device(context, host, device_id)

    @log_helpers.log_method_call
    def notify_agent_init_config(self, context, host, router_infos):
        LOG.debug('agent_initial_config')
        notifier = ask1k_l3_notifier.ASR1KAgentNotifyAPI()
        return notifier.agent_init_config(context, host, router_infos)

    @registry.receives(resources.ROUTER_INTERFACE, [events.BEFORE_CREATE])
    @log_helpers.log_method_call
    def _check_internal_net_az_hints(self, resource, event, trigger, payload, **kwargs):
        # FIXME: why the fuck is that in this class
        router_id = payload.resource_id
        network_id = payload.metadata.get("network_id")
        context = payload.context
        LOG.debug("(AZ check) router interface before_create hook for router %s network %s",
                  router_id, network_id)
        plugin = directory.get_plugin()
        router = self.get_router(context, router_id)
        router_az_hint = router.get(az_def.AZ_HINTS)
        if router_az_hint:
            router_az_hint = router_az_hint[0]
            if router_az_hint in constants.NO_AZ_LIST:
                router_az_hint = None

        network = plugin.get_network(context, network_id)
        net_az_hint = network.get(az_def.AZ_HINTS)
        if net_az_hint:
            net_az_hint = net_az_hint[0]
            if net_az_hint in constants.NO_AZ_LIST:
                net_az_hint = None
        LOG.debug("(AZ check) compat check: router %s in %s - network %s in %s",
                  router['id'], router_az_hint, network_id, net_az_hint)

        if (net_az_hint and not router_az_hint) or (router_az_hint and not net_az_hint) or \
                (net_az_hint and router_az_hint and net_az_hint != router_az_hint):
            exc = asr1k_exc.RouterNetworkAZMismatch(network_az=net_az_hint, router_az=router_az_hint)
            if cfg.CONF.asr1k.ignore_router_network_az_hint_mismatch:
                LOG.warning("AZ validation has been disabled, orig error: %s", exc)
            else:
                raise exc


class ASR1KPluginBase(l3_db.L3_NAT_db_mixin,
                      asr1k_scheduler_db.AZASR1KL3AgentSchedulerDbMixin, extraroute_db.ExtraRoute_db_mixin,
                      dns_db.DNSDbMixin, L3RpcNotifierMixin, asr1k_ext.DevicePluginBase):
    def __init__(self):
        self.db = asr1k_db.get_db_plugin()

    def get_agent_for_router(self, context, router_id):
        """Returns all hosts to send notification about router update"""
        agents = self.list_l3_agents_hosting_router(context, router_id)

        agents_list = agents.get('agents', [])

        if len(agents_list) == 1:
            return agents_list[0]
        else:
            LOG.error('get host for router: there should be one and only one agent, got {}'.format(agents_list))

    def get_host_for_router(self, context, router_id):
        agent = self.get_agent_for_router(context, router_id)
        if agent is not None:
            return agent.get('host')

    def get_hosts_for_network(self, context, network_id):
        return self.db.get_asr1k_hosts_for_network(context, network_id)

    def _ensure_second_dot1q(self, context):
        session = db_api.get_writer_session()
        extra_atts = session.query(asr1k_models.ASR1KExtraAttsModel).all()
        second_dot1qs = []

        for extra_att in extra_atts:
            second_dot1qs.append(extra_att.second_dot1q)

        for extra_att in extra_atts:
            if extra_att.second_dot1q == 0:
                for x in range(asr1k_db.MIN_SECOND_DOT1Q, asr1k_db.MAX_SECOND_DOT1Q):
                    if x not in second_dot1qs:
                        extra_att.second_dot1q = x
                        second_dot1qs.append(x)
                        break

                with context.session.begin(subtransactions=True):
                    entry = session.query(asr1k_models.ASR1KExtraAttsModel).filter_by(router_id=extra_att.router_id,
                                                                                      agent_host=extra_att.agent_host,
                                                                                      port_id=extra_att.port_id,
                                                                                      segment_id=extra_att.segment_id
                                                                                      ).first()
                    if entry:
                        entry.update(extra_att)

    @instrument()
    @log_helpers.log_method_call
    def get_sync_data(self, context, router_ids=None, active=None, host=None):
        # FIXME: isn't this more like a db function.....
        if host is not None:
            host_router_ids = self.db.get_all_router_ids(context, host)
            router_ids = [r for r in router_ids if r in host_router_ids]

        if not bool(router_ids):
            return []

        extra_atts = self._get_extra_atts(context, router_ids, host)
        router_atts = self._get_router_atts(context, router_ids)

        try:
            routers = super(ASR1KPluginBase, self).get_sync_data(context, router_ids=router_ids, active=active)
        except TypeError:
            # We may have a race in the L3/L2 scavengers, lets back of and try again
            time.sleep(.25)
            routers = super(ASR1KPluginBase, self).get_sync_data(context, router_ids=router_ids, active=active)

        if not bool(routers):
            routers = []
            for router_id in router_ids:
                routers.append({'id': router_id, constants.ASR1K_ROUTER_ATTS_KEY: router_atts.get(router_id, {})})

        for router in routers:
            extra_att = extra_atts.get(router['id'])
            if extra_atts is None:
                if host is None:
                    LOG.debug("Not including router {} in sync its extra atts are missing.".format(router['id']))
                else:
                    LOG.debug("Not including router {} in sync its extra atts are missing for host {}."
                              "".format(router['id'], host))
                continue

            router[constants.ASR1K_EXTRA_ATTS_KEY] = extra_att

            router_att = router_atts.get(router['id'], {})
            router[constants.ASR1K_ROUTER_ATTS_KEY] = router_att

            # Make sure the gateway IPs all have prefixes and are sorted consistently
            # this is to prevent foo when we have to assign to nat pool, because we
            # can guarantee a consistent order from neutron and we can't change the
            # pool on the active device and it has (currently) to be different from
            # the interface device.

            gw_info = router.get('external_gateway_info', None)
            gw_port = router.get('gw_port', None)
            if gw_port is not None:
                ips = gw_port.get('fixed_ips', [])
                prefixes = {}
                if bool(ips):
                    for ip in ips:
                        prefix = ip.get('prefixlen', None)
                        subnet_id = ip.get('subnet_id', None)
                        if prefix is not None and subnet_id is not None:
                            prefixes[subnet_id] = prefix

                    for ip in ips:
                        if ip.get('prefixlen', None) is None:
                            prefix = prefixes.get(ip.get('subnet_id', None))
                            if prefix is not None:
                                ip['prefixlen'] = prefix

                    gw_port['fixed_ips'] = sorted(ips, key=lambda k: k.get('ip_address'))
                    if gw_info is not None:
                        gw_info['external_fixed_ips'] = gw_port['fixed_ips']

            rt_import = []
            rt_export = []
            bgpvpns = self.db.get_bgpvpns_by_router_id(context, router['id'])
            router["bgpvpn_advertise_extra_routes"] = True
            if bgpvpns:
                adv_mode = self.db.get_bgpvpn_advertise_extra_routes_by_router_id(context, router['id'])
                router["bgpvpn_advertise_extra_routes"] = adv_mode

            for bgpvpn in bgpvpns:
                if bgpvpn.route_targets:
                    rt_import += bgpvpn.route_targets.split(",")
                    rt_export += bgpvpn.route_targets.split(",")
                if bgpvpn.import_targets:
                    rt_import += bgpvpn.import_targets.split(",")
                if bgpvpn.export_targets:
                    rt_export += bgpvpn.export_targets.split(",")

            router["rt_export"] = list(set(rt_export))
            router["rt_import"] = list(set(rt_import))

        return routers

    def get_deleted_router_atts(self, context):
        return self.db.get_deleted_router_atts(context)

    def _get_device_info(self, context, host):
        return self.db.get_device_info(context, host)

    def _get_extra_atts(self, context, router_ids, host=None):
        extra_atts = self.db.get_extra_atts_for_routers(context, router_ids, host=host)

        return_dict = {}

        for extra_att in extra_atts:
            router_id = extra_att.get('router_id')
            if return_dict.get(router_id) is None:
                return_dict[router_id] = {}

            if host is None:
                return_dict[router_id][extra_att.get('port_id')] = extra_att
            else:
                if host == extra_att.get('agent_host'):
                    return_dict[router_id][extra_att.get('port_id')] = extra_att

        return return_dict

    def _get_router_atts(self, context, router_ids):
        router_atts = self.db.get_router_atts_for_routers(context, router_ids)
        return {ra.router_id: ra for ra in router_atts}

    def _allocate_and_check_ips(self, context, router, nat_ip_count):
        gw_info = router.get(l3_apidef.EXTERNAL_GW_INFO, nl_const.ATTR_NOT_SPECIFIED)
        if gw_info == nl_const.ATTR_NOT_SPECIFIED:
            return

        # FIXME: where do we actually write the info back into the asr1k extra atts
        LOG.debug("Request for router %s requires %s nat ips", router.get('id', '<no id assigned yet>'), nat_ip_count)
        # TODO: find out where to find the fixed ips in the gw info
        # TODO: split into gw ip / nat pool ips
        # TODO: validate requested ips
        # TODO: find all missing ips from ipam
        # TODO: write back into data structure

    @registry.receives(resources.ROUTER, [events.PRECOMMIT_CREATE])
    def allocate_router_atts_on_create(self, resource, event, trigger, payload):
        LOG.debug("Allocating extra atts for router %s", payload.resource_id)
        self.db.ensure_router_atts(payload.context, payload.resource_id)

    def _get_nat_ip_count_from_flavor(self, context, flavor_id):
        dynamic_nat_ips = None
        flavor_plugin = directory.get_plugin(plugin_constants.FLAVORS)

        # fetch service profile
        flavor = flavor_plugin.get_flavor(context, flavor_id)
        for profile_id in flavor['service_profiles']:
            profile = flavor_plugin.get_service_profile(context, profile_id)
            try:
                metainfo = jsonutils.loads(profile['metainfo'])
            except json.JSONDecodeError as e:
                LOG.warning("Could not load metainfo: %s - %s", profile['metainfo'], e)
                continue
            if meta_nat_ips := metainfo.get('dynamic-nat-ips'):
                dynamic_nat_ips = meta_nat_ips

        return dynamic_nat_ips

    @registry.receives(resources.ROUTER, [events.PRECOMMIT_CREATE])
    def handle_flavor_extra_config(self, resource, event, trigger, payload):
        # only state has flavor_id set properly
        router = payload.states[0]

        dynamic_nat_ips = None
        if router.get("flavor_id", nl_const.ATTR_NOT_SPECIFIED) != nl_const.ATTR_NOT_SPECIFIED:
            # # flavors have service profiles, which have metainfo where we might find json info
            # flavor_plugin = directory.get_plugin(plugin_constants.FLAVORS)
            # # fetch service profile
            # LOG.info("i501315 - flavor test, fetching flavor for %s", router['flavor_id'])
            # flavor = flavor_plugin.get_flavor(payload.context, router['flavor_id'])
            # LOG.info("i501315 - flavor %s", flavor)
            # for profile_id in flavor['service_profiles']:
            #     LOG.info("i501315 - fetching profile %s...", profile_id)
            #     profile = flavor_plugin.get_service_profile(payload.context, profile_id)
            #     try:
            #         metainfo = jsonutils.loads(profile['metainfo'])
            #         LOG.info("i501315 - metainfo loaded: %s", metainfo)
            #     except json.JSONDecodeError as e:
            #         LOG.info("i501315 - could not load metainfo: %s - %s", profile['metainfo'], e)
            #         continue
            #     if meta_nat_ips := metainfo.get('dynamic-nat-ips'):
            #         dynamic_nat_ips = meta_nat_ips

            if dynamic_nat_ips := self._get_nat_ip_count_from_flavor(payload.context, router['flavor_id']):
                # verify that the right amount of ips is in the gateway thing
                LOG.debug("Router %s will have %s dynamic nat pool size %s", router['id'], dynamic_nat_ips)
                self.db.set_router_dynamic_nat_ip_count(payload.context, router['id'], dynamic_nat_ips)
                # self._allocate_and_check_ips(context, router['router'], dynamic_nat_ips)

    @log_helpers.log_method_call
    def create_router(self, context, router):
        # dynamic_nat_ips = None
        # if router['router'].get("flavor_id", nl_const.ATTR_NOT_SPECIFIED) != nl_const.ATTR_NOT_SPECIFIED:
        #     # flavors have service profiles, which have metainfo where we might find json info
        #     flavor_plugin = directory.get_plugin(plugin_constants.FLAVORS)
        #     # fetch service profile
        #     LOG.info("i501315 - flavor test, fetching flavor for %s", router['router']['flavor_id'])
        #     flavor = flavor_plugin.get_flavor(context, router['router']['flavor_id'])
        #     LOG.info("i501315 - flavor %s", flavor)
        #     for profile_id in flavor['service_profiles']:
        #         LOG.info("i501315 - fetching profile %s...", profile_id)
        #         profile = flavor_plugin.get_service_profile(context, profile_id)
        #         try:
        #             metainfo = jsonutils.loads(profile['metainfo'])
        #             LOG.info("i501315 - metainfo loaded: %s", metainfo)
        #         except json.JSONDecodeError as e:
        #             LOG.info("i501315 - could not load metainfo: %s - %s", profile['metainfo'], e)
        #             continue
        #         if meta_nat_ips := metainfo.get('dynamic-nat-ips'):
        #             dynamic_nat_ips = meta_nat_ips

        # if dynamic_nat_ips:
        #     # verify that the right amount of ips is in the gateway thing
        #     self._allocate_and_check_ips(context, router['router'], dynamic_nat_ips)

        result = super(ASR1KPluginBase, self).create_router(context, router)
        return result

    def _create_gw_port(self, context, router_id, router, new_network_id, ext_ips):
        super()._create_gw_port
        # FIXME: oder doch _validate_gw_info()
        pass

    def _update_router_gw_info(self, context, router_id, info,
                               request_body, router=None):
        ext_ips = info.get('external_fixed_ips', []) if info else []
        dynamic_nat_pool = None
        if len(ext_ips) > 1:
            # someone is trying to add a gw with a nat pool (multiple ips)
            if len(ext_ips) == 2:
                raise ValueError("You need to provide at least two IPs for the pool and one for the router "
                                 "for dynamic nat pooling to be enabled")

            has_ip_specified = False
            has_no_ip_specified = False
            alloc_subnet_id = None
            for ip_def in ext_ips[:-1]:
                # check if we have mixed ip/no-ip requests
                if 'ip_address' in ip_def:
                    has_ip_specified = True
                else:
                    has_no_ip_specified = True

                # check if everything is the same subnet
                if 'subnet_id' in ip_def:
                    if alloc_subnet_id is None:
                        alloc_subnet_id = ip_def['subnet_id']
                    elif alloc_subnet_id != ip_def['subnet_id']:
                        raise ValueError("Found two differend subnets in request for dynamic NAT pool, which is not "
                                         f"allowed. ({alloc_subnet_id} vs {ip_def['subnet_id']}")
            if has_ip_specified and has_no_ip_specified:
                raise ValueError("IPs for the NAT pool have only been partially specified. "
                                 "Either specify all IPs or none")

            if has_no_ip_specified:
                if not alloc_subnet_id:
                    raise ValueError("Tried to allocate IPs for dynamic NAT pool but "
                                     "neither IP nor subnet was provided")
                ips = self._allocate_ips_for_dynamic_nat_pool(self, context, alloc_subnet_id, len(ext_ips) - 1)
                if not ips:
                    # FIXME: this will be one of the most frequent error messages for this feature
                    #        make sure it's a good one ;)
                    raise ValueError(f"Could not find {len(ext_ips)} consecutive IP addresses "
                                     f"in subnet {alloc_subnet_id} - make sure there is enough undivided IP space.")

                for ext_ip, ip in zip(ext_ips, ips):
                    ext_ip['ip_address'] = ip

        # router = router or self._get_router(context, router_id)
        result = super()._update_router_gw_info(context, router_id, info, request_body, router)
        if dynamic_nat_pool is not None:
            # FIXME: can we somehow put this into a transaction?
            self.db.set_router_ext_nat_pool(context, router_id, dynamic_nat_pool)

        return result

    def _allocate_ips(self, context, subnet_id, ip_count):
        # FIXME: only call if NO ip is allocated. mixtures are not allowed
        from neutron.ipam import driver
        import netaddr

        ipam_driver = driver.Pool.get_instance(None, context)
        ipam_subnet = ipam_driver.get_subnet(subnet_id)
        allocations = ipam_subnet.subnet_manager.list_allocations(context)
        ip_allocations = netaddr.IPSet([netaddr.IPAddress(allocation.ip_address) for allocation in allocations])

        for ip_pool in self.subnet_manager.list_pools(context):
            ip_set = netaddr.IPSet()
            ip_set.add(netaddr.IPRange(ip_pool.first_ip, ip_pool.last_ip))
            av_set = ip_set.difference(ip_allocations)
            if av_set.size < ip_count:
                continue

            # av_set.iter_cidrs() --> netaddr.IPNetwork
            av_iter = iter(av_set)
            result = [next(av_iter)]
            # FIXME: validate that the ip set is always sorted? is that a thing
            for ip in av_iter:
                if int(ip) - 1 != int(result[-1]):
                    # non-consecutive IP
                    result = [ip]
                    continue
                result.append(ip)
                if len(result) == ip_count:
                    return [str(ip) for ip in result]

        # FIXME: raise
        raise ValueError("that is boooooorked")

    def _validate_gw_info(self, context, info, ext_ips, router):
        network_id = super()._validate_gw_info(context, info, ext_ips, router)

        router_atts = self.db.get_router_att(context, router.id)
        if router_atts.nat_ip_count:
            print("Given extips", ext_ips)
            if len(ext_ips) != router_atts.nat_ip_count + 1:
                raise nl_exc.NeutronException(message="Can't update external gateway for router, as it has an exended "
                                                      f"nat pool with {router_atts.nat_ip_count} ips + 1 gateway ip, "
                                                      f" but only {len(ext_ips)} were provided")

            pool_ips = ext_ips[:-1]
            ip = ipaddress.ip_address(pool_ips[0])
            for next_ip in pool_ips[1:]:
                next_ip = ipaddress.ip_address(next_ip)
                if int(next_ip) - int(ip) != 1:
                    raise nl_exc.NeutronException(message=f"Invalid extended nat pool for router: IP {ip} and "
                                                          "{next_ip} don't follow each other directly")
        elif len(ext_ips) > 1:
            # routers without an extended nat pool don't get more than one dynamic nat ip
            raise nl_exc.NeutronException(message="Router does not have an extended nat pool, but more than one "
                                                  f"external gateway ip was given ({len(ext_ips)} found)")

        # 3. (after original validate) make sure the ips fulfill our requirements / validate
        # make sure all given ips are subsequent for nat pool usage

        # if this is a router with multiple external ips, make sure
        print(context, info, ext_ips, router)

        return network_id

    def ensure_default_route_skip_monitoring(self, context, router_id, router):
        tag_plugin = directory.get_plugin(TAG_PLUGIN_TYPE)
        custom_default_route_tags = {constants.TAG_SKIP_MONITORING, constants.TAG_DEFAULT_ROUTE_OVERWRITE}

        has_custom_default_route = any(r['destination'].endswith('/0') for r in router['routes'])
        with context.session.begin(subtransactions=True):
            router_tags = set(tag_plugin.get_tags(context, 'routers', router_id)['tags'])

            has_default_route_tags = custom_default_route_tags.issubset(router_tags)

            if has_default_route_tags != has_custom_default_route:
                if has_default_route_tags:
                    router_tags = router_tags - custom_default_route_tags
                else:
                    router_tags = router_tags.union(custom_default_route_tags)

                tag_plugin.update_tags(context, 'routers', router_id, dict(tags=router_tags))

    @registry.receives(resources.ROUTER_GATEWAY, [events.BEFORE_UPDATE])
    def prevent_updating_ext_gw_for_nat_pool_routers(self, resource, event, trigger, payload):
        # FIXME: do we need to allow this case?
        router = payload.states[0]
        router_atts = self.db.get_router_att(payload.context, router.id)
        if router_atts and router_atts.ext_nat_ips:
            raise nl_exc.NeutronException(message=f"Router {router.id} has a nat pool with {router_atts.ext_nat_ips} "
                                                  "ips, changing the external gateway ips is currently not supported")

    @log_helpers.log_method_call
    def update_router(self, context, id, router):
        result = super(ASR1KPluginBase, self).update_router(context, id, router)
        self.ensure_default_route_skip_monitoring(context, id, result)
        return result

    @log_helpers.log_method_call
    def get_router(self, context, id, fields=None):
        return super(ASR1KPluginBase, self).get_router(context, id, fields)

    def _add_router_to_cache(self, context, router_id):
        LOG.debug("Adding router %s to internal router cache", router_id)
        host = self.get_host_for_router(context, [router_id])
        routers = self.get_sync_data(context, [router_id])
        if not routers:
            LOG.warning("Could not add router %s to internal router cache: get_sync_data came up empty", router_id)
            return

        cache_utils.cache_deleted_router(host, router_id, routers[0])

    @log_helpers.log_method_call
    def delete_router(self, context, id):
        self._add_router_to_cache(context, id)
        return super(ASR1KPluginBase, self).delete_router(context, id)

    @log_helpers.log_method_call
    def add_router_to_l3_agent(self, context, agent_id, router_id):
        result = super(ASR1KPluginBase, self).add_router_to_l3_agent(context, agent_id, router_id)
        return result

    @log_helpers.log_method_call
    def remove_router_from_l3_agent(self, context, agent_id, router_id):
        self._add_router_to_cache(context, router_id)
        return super(ASR1KPluginBase, self).remove_router_from_l3_agent(context, agent_id, router_id)

    @log_helpers.log_method_call
    def add_router_interface(self, context, router_id, interface_info=None):
        return super(ASR1KPluginBase, self).add_router_interface(context, router_id, interface_info)

    @log_helpers.log_method_call
    def remove_router_interface(self, context, router_id, interface_info):
        return super(ASR1KPluginBase, self).remove_router_interface(context, router_id, interface_info)

    def validate(self, context, id, fields=None):
        result = self.notify_router_validate(context, id)
        return {'diffs': result}

    def sync(self, context, id, fields=None):
        result = self.notify_router_sync(context, id)
        return {'device': {'network_id': result}}

    def validate_network(self, context, id, fields=None):
        result = self.notify_network_validate(context, id)
        return {'diffs': result}

    def sync_network(self, context, id, fields=None):
        result = self.notify_network_sync(context, id)
        return {'device': {'network_id': result}}

    def orphans(self, context, dry_run=True):
        result = self.notify_router_sync(context, dry_run)
        return result

    def get_config(self, context, id):
        router_atts = self._get_router_atts(context, [id])

        extra_atts = self._get_extra_atts(context, [id])
        atts = extra_atts.get(id, None)
        result = OrderedDict({'id': id, 'rd': None})
        if len(router_atts) > 0:
            att = router_atts.get(id, None)
            if att is not None:
                result['rd'] = att.get('rd')

        ports = []

        if atts is not None:
            for port_id in atts.keys():
                port = OrderedDict({'port_id': port_id})
                att = atts.get(port_id)
                if att is not None:
                    port['segment_id'] = att.segment_id
                    port['segmentation_id'] = att.segmentation_id
                    port['second_dot1q'] = att.second_dot1q
                    port['external_service_instance'] = att.segmentation_id
                    port['loopback_service_instance'] = utils.to_bridge_domain(att.second_dot1q)
                    port['bridge_domain'] = utils.to_bridge_domain(att.second_dot1q)
                    port['deleted_l2'] = att.deleted_l2
                    port['deleted_l3'] = att.deleted_l3

                ports.append(port)
        result['ports'] = ports

        return dict(result)

    @registry.receives(resources.ROUTER_GATEWAY, [events.BEFORE_CREATE])
    @log_helpers.log_method_call
    def ensure_bdvif_limit(self, resource: str, event: str, trigger, payload: events.DBEventPayload):
        """
        There is a hardware limit on ASR1K/C8500 that allows us to not bind more than X BD-VIFs in a BD.
        As configuration would just silently fail, we try to catch the situation on API level.
        """
        context = payload.context
        network_id = payload.metadata['network_id']
        router_id = payload.resource_id

        host = self.get_l3_agents_hosting_routers(context, [router_id])
        if len(host) == 0:
            host = None
        else:
            host = host[0].host

        port_count = self.db.get_network_port_count_per_agent(context, network_id)

        # Either the router is scheduled and the agent has no room for BD-VIFs in that BD
        # or it is not scheduled and all existing agents are above the limit
        limit = cfg.CONF.asr1k_l2.bdvif_bd_limit
        if (host and port_count[host] >= limit) \
                or (not host and all(x >= limit for x in port_count.values())):
            raise asr1k_exc.BdVifInBdExhausted(network_id=network_id, router_id=router_id)

    def ensure_config(self, context, id):
        self.db.ensure_router_atts(context, id)

        ports = self.db.get_router_ports(context, id)
        for port in ports:
            segment = self.db.get_router_segment_for_port(context, id, port.get('id'))
            asr1k_db.ExtraAttsDb.ensure(id, port, segment, clean_old=True)

        return self.get_config(context, id)

    def interface_statistics(self, context, id, fields=None):
        result = self.notify_interface_statistics(context, id)
        return {'interface_statistics': result}

    def teardown(self, context, id, fields=None):
        result = self.notify_router_teardown(context, id)
        return {'device': {'id': result}}

    def show_orphans(self, context, host):
        result = self.notify_show_orphans(context, host)
        return result

    def delete_orphans(self, context, host):
        result = self.notify_delete_orphans(context, host)
        return result

    def list_devices(self, context, host):
        result = self.notify_list_devices(context, host)
        device_info = self.db.get_device_info(context, host)
        for id in result:
            device = result.get(id)
            self._add_device_enabled(device_info, device)
        return result

    def show_device(self, context, host, id):
        result = self.notify_show_device(context, host, id)
        device_info = self.db.get_device_info(context, host)
        self._add_device_enabled(device_info, result)
        return result

    def _add_device_enabled(self, device_info, device):
        info = device_info.get(device.get('id'))
        if info is None or info.enabled:
            device['enabled'] = True
        else:
            device['enabled'] = False

    def update_device(self, context, host, id, enabled):
        device = self.notify_show_device(context, host, id)
        if device is None:
            return None

        asr1k_db.DeviceInfoDb(context, id, host, enabled).update()

        return {id: enabled}

    def init_scheduler(self, context):
        return Initializer(self, context).init_scheduler()

    def init_bindings(self, context):
        return Initializer(self, context).init_bindings()

    def init_atts(self, context):
        return Initializer(self, context).init_atts()

    def init_config(self, context, host):
        return Initializer(self, context).init_config(host)
