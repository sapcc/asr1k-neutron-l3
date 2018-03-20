import importlib
import logging
import os
import sys
import warnings

from keystoneauth1 import adapter
from keystoneauth1 import session as ks_session
from oslo_utils import importutils
from openstack import connection


LOG = logging.getLogger(__name__)
_DEFAULT_SERVICE_TYPE = 'network'
_DEFAULT_SERVICE_INTERFACE = 'public'
_DEFAULT_API_VERSION = 'v2.0'
_SUPPORTED_API_VERSION_MAP = {'v2.0': 'asr1k_neutron_l3.client_plugins.v2.client.Client'}




# NOTE(dtroyer): Attempt an import to detect if the SDK installed is new
#                enough to not use Profile.  If so, use that.
try:
    from openstack.config import loader as config   # noqa
    profile = None
except ImportError:
    from openstack import profile
from osc_lib import utils

from openstackclient.i18n import _


LOG = logging.getLogger(__name__)

DEFAULT_API_VERSION = '2.0'
API_VERSION_OPTION = 'os_ars1k_api_version'
API_NAME = "asr1k"
API_VERSIONS = {
    "2.0": "openstack.connection.Connection",
    "2": "openstack.connection.Connection",
}


def make_client(instance):
    # """Returns a network proxy"""
    # if getattr(instance, "sdk_connection", None) is None:
    #     if profile is None:
    #         # If the installed OpenStackSDK is new enough to not require a
    #         # Profile obejct and osc-lib is not new enough to have created
    #         # it for us, make an SDK Connection.
    #         # NOTE(dtroyer): This can be removed when this bit is in the
    #         #                released osc-lib in requirements.txt.
    #         conn = connection.Connection(
    #             config=instance._cli_options,
    #             session=instance.session,
    #         )
    #     else:
    #         # Fall back to the original Connection creation
    #         prof = profile.Profile()
    #         prof.set_region(API_NAME, instance.region_name)
    #         prof.set_version(API_NAME, instance._api_version[API_NAME])
    #         prof.set_interface(API_NAME, instance.interface)
    #         conn = connection.Connection(
    #             authenticator=instance.session.auth,
    #             verify=instance.session.verify,
    #             cert=instance.session.cert,
    #             profile=prof,
    #         )
    #
    #     instance.sdk_connection = conn
    #
    # conn = instance.sdk_connection
    # LOG.debug('Connection: %s', conn)
    # LOG.debug('ASR1K client initialized using OpenStack SDK: %s',
    #           conn.network)
    # return conn.network


    return Client(session=instance.session,
                         region_name=instance._region_name,
                         interface=instance.interface)



def build_option_parser(parser):
    """Hook to add global options"""
    parser.add_argument(
        '--os-asr1k-api-version',
        metavar='<asr1k-api-version>',
        default=utils.env('OS_ASR1K_API_VERSION'),
        help=_("ASR1K API version, default=%s "
               "(Env: OS_ASR1K_API_VERSION)") % DEFAULT_API_VERSION
    )
    return parser






class _HTTPClient(adapter.Adapter):

    def __init__(self, session, project_id=None, **kwargs):
        kwargs.setdefault('interface', _DEFAULT_SERVICE_INTERFACE)
        kwargs.setdefault('service_type', _DEFAULT_SERVICE_TYPE)
        kwargs.setdefault('version', _DEFAULT_API_VERSION)
        endpoint = kwargs.pop('endpoint', None)



        super(_HTTPClient, self).__init__(session, **kwargs)

        if endpoint:
            self.endpoint_override = '{0}/{1}'.format(endpoint, self.version)

        if project_id is None:
            self._default_headers = dict()
        else:
            # If provided we'll include the project ID in all requests.
            self._default_headers = {'X-Project-Id': project_id}

    def request(self, *args, **kwargs):
        headers = kwargs.setdefault('headers', {})
        headers.update(self._default_headers)

        # Set raise_exc=False by default so that we handle request exceptions
        kwargs.setdefault('raise_exc', False)

        resp = super(_HTTPClient, self).request(*args, **kwargs)
        self._check_status_code(resp)
        return resp

    def get(self, *args, **kwargs):
        headers = kwargs.setdefault('headers', {})
        headers.setdefault('Accept', 'application/json')



        return super(_HTTPClient, self).get(*args, **kwargs).json()

    def post(self, path, *args, **kwargs):
        path = self._fix_path(path)

        return super(_HTTPClient, self).post(path, *args, **kwargs).json()

    def _fix_path(self, path):
        if not path[-1] == '/':
            path += '/'

        return path

    def _get_raw(self, path, *args, **kwargs):
        return self.request(path, 'GET', *args, **kwargs).content

    def _check_status_code(self, resp):
        status = resp.status_code
        LOG.debug('Response status {0}'.format(status))
        if status == 401:
            LOG.error('Auth error: {0}'.format(self._get_error_message(resp)))
            raise exceptions.HTTPAuthError(
                '{0}'.format(self._get_error_message(resp))
            )
        if not status or status >= 500:
            LOG.error('5xx Server error: {0}'.format(
                self._get_error_message(resp)
            ))
            raise exceptions.HTTPServerError(
                '{0}'.format(self._get_error_message(resp)),
                status
            )
        if status >= 400:
            LOG.error('4xx Client error: {0}'.format(
                self._get_error_message(resp)
            ))
            raise exceptions.HTTPClientError(
                '{0}'.format(self._get_error_message(resp)),
                status
            )

    def _get_error_message(self, resp):
        try:
            response_data = resp.json()
            message = response_data['title']
            description = response_data.get('description')
            if description:
                message = '{0}: {1}'.format(message, description)
        except ValueError:
            message = resp.content
        return message


def Client(version=None, session=None, *args, **kwargs):
        """Barbican client used to interact with barbican service.

        :param version: The API version to use.
        :param session: An instance of keystoneauth1.session.Session that
            can be either authenticated, or not authenticated.  When using
            a non-authenticated Session, you must provide some additional
            parameters.  When no session is provided it will default to a
            non-authenticated Session.
        :param endpoint: Barbican endpoint url. Required when a session is not
            given, or when using a non-authenticated session.
            When using an authenticated session, the client will attempt
            to get an endpoint from the session.
        :param project_id: The project ID used for context in Barbican.
            Required when a session is not given, or when using a
            non-authenticated session.
            When using an authenticated session, the project ID will be
            provided by the authentication mechanism.
        :param verify: When a session is not given, the client will create
            a non-authenticated session.  This parameter is passed to the
            session that is created.  If set to False, it allows
            barbicanclient to perform "insecure" TLS (https) requests.
            The server's certificate will not be verified against any
            certificate authorities.
            WARNING: This option should be used with caution.
        :param service_type: Used as an endpoint filter when using an
            authenticated keystone session. Defaults to 'key-manager'.
        :param service_name: Used as an endpoint filter when using an
            authenticated keystone session.
        :param interface: Used as an endpoint filter when using an
            authenticated keystone session. Defaults to 'public'.
        :param region_name: Used as an endpoint filter when using an
            authenticated keystone session.
        """
        LOG.debug("Creating Client object")

        if not session:
            session = ks_session.Session(verify=kwargs.pop('verify', True))

        if session.auth is None and kwargs.get('auth') is None:
            if not kwargs.get('endpoint'):
                raise ValueError('Barbican endpoint url must be provided when '
                                 'not using auth in the Keystone Session.')

            if kwargs.get('project_id') is None:
                raise ValueError('Project ID must be provided when not using '
                                 'auth in the Keystone Session')
        if not version:
            version = _DEFAULT_API_VERSION

        try:
            client_path = _SUPPORTED_API_VERSION_MAP[version]
            client_class = importutils.import_class(client_path)
            return client_class(session=session, *args, **kwargs)
        except (KeyError, ValueError):
            supported_versions = ', '.join(_SUPPORTED_API_VERSION_MAP.keys())
            msg = ("Invalid client version %(version)s; must be one of: "
                   "%(versions)s") % {'version': version,
                                      'versions': supported_versions}
            raise Exception(msg)


def env(*vars, **kwargs):
    """Search for the first defined of possibly many env vars

    Returns the first environment variable defined in vars, or
    returns the default defined in kwargs.

    Source: Keystone's shell.py
    """
    for v in vars:
        value = os.environ.get(v, None)
        if value:
            return value
    return kwargs.get('default', '')


class _LazyImporter(object):
    def __init__(self, module):
        self._module = module

    def __getattr__(self, name):
        # This is only called until the import has been done.
        lazy_submodules = [
            'devices',

        ]
        if name in lazy_submodules:
            warnings.warn("The %s module is moved to barbicanclient/v2 "
                          "directory, direct import of "
                          "barbicanclient.client.%s "
                          "will be deprecated. Please import "
                          "barbicanclient.v2.%s instead."
                          % (name, name, name))
            return importlib.import_module('asr1k_neutron_l3.client_plugins.v2.%s' % name)

        # Return module attributes like __all__ etc.
        return getattr(self._module, name)


sys.modules[__name__] = _LazyImporter(sys.modules[__name__])

