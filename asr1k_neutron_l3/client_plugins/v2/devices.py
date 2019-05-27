import json

from osc_lib.command import command
from osc_lib import utils

from openstackclient.i18n import _
from openstackclient.network import sdk_utils

from asr1k_neutron_l3.client_plugins import base
from neutron_lib._i18n import _

_formatters = {
    'tags': utils.format_list,
}


def _format_router_info(info):
    try:
        return json.dumps(info)
    except (TypeError, KeyError):
        return ''


def _get_columns(item):
    column_map = {
        'tenant_id': 'project_id',
        'is_ha': 'ha',
        'is_distributed': 'distributed',
        'is_admin_state_up': 'admin_state_up',
    }
    if hasattr(item, 'interfaces_info'):
        column_map['interfaces_info'] = 'interfaces_info'
    return sdk_utils.get_osc_show_columns_for_sdk_resource(item, column_map)


class UpdateDevices(command.Command):
    _description = _("Updates a router configuration on ASR1ks")

    def get_parser(self, prog_name):
        parser = super(UpdateDevices, self).get_parser(prog_name)
        parser.add_argument(
            'router',
            metavar='<router>',
            help=_("Router to update")
        )

        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.asr1k
        obj = client.devices.update_device(parsed_args.router, ignore_missing=False)

        interfaces_info = []
        filters = {}
        filters['device_id'] = obj.id
        for port in client.ports(**filters):
            if port.device_owner != "network:router_gateway":
                for ip_spec in port.fixed_ips:
                    int_info = {
                        'port_id': port.id,
                        'ip_address': ip_spec.get('ip_address'),
                        'subnet_id': ip_spec.get('subnet_id')
                    }
                    interfaces_info.append(int_info)

        setattr(obj, 'interfaces_info', interfaces_info)
        display_columns, columns = _get_columns(obj)
        _formatters['interfaces_info'] = _format_router_info
        data = utils.get_item_properties(obj, columns, formatters=_formatters)

        return (display_columns, data)


class DevicesManager(base.BaseEntityManager):
    """Entity Manager for Secret entities"""

    def __init__(self, api):
        super(DevicesManager, self).__init__(api, 'devices')

    def update_device(self, router_id, ignore_missing=False):
        response = self._api.put("{}/{}".format(self._entity, router_id), json={"device": {}})
