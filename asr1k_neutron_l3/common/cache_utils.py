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

from neutron.common import cache_utils as neutron_cache_utils
from oslo_log import log
from oslo_config import cfg

LOG = log.getLogger(__name__)


_LOCAL_CACHE = None
DELETED_ROUTER_PREFIX = "deleted-router"


def get_cache():
    global _LOCAL_CACHE
    if not _LOCAL_CACHE:
        cache = neutron_cache_utils.get_cache(cfg.CONF)
        if not cache:
            LOG.error("Could not get connection to neutron cache, which is required for proper router deletion")
            return
        _LOCAL_CACHE = cache
    return _LOCAL_CACHE


def _gen_cache_key(prefix, host, router_id):
    return "asr1k-{}-{}-{}".format(prefix, host, router_id)


def cache_deleted_router(host, router_id, data):
    cache = get_cache()
    if not cache:
        return

    key = _gen_cache_key(DELETED_ROUTER_PREFIX, host, router_id)
    cache.set(key, data)


def get_deleted_router(host, router_id):
    cache = get_cache()
    if not cache:
        return

    key = _gen_cache_key(DELETED_ROUTER_PREFIX, host, router_id)
    return cache.get(key) or None
