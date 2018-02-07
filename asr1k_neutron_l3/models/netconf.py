
from asr1k_neutron_l3.models.asr1k_pair import ASR1KPair

from ncclient import manager


class ConnectionPool(object):
    __instance = None

    def __new__(cls):
        if ConnectionPool.__instance is None:
            ConnectionPool.__instance = object.__new__(cls)
            ConnectionPool.__instance.__setup()

        return ConnectionPool.__instance


    def __setup(self):
        self.pair_config = ASR1KPair()

        self.devices = {}

        for context in self.pair_config.contexts:
            self.devices['{}_yang'.format(context.host)] = YangConnection(context)
            self.devices['{}_legacy'.format(context.host)] = LegacyConnection(context)

    def get_connection(self,host,legacy=False):
        key = '{}_yang'.format(host)
        if legacy :
            key = '{}_legacy'.format(host)

        connection = self.devices.get(key)

        if connection is None:
            raise Exception('No connection can be found for {}'.format(key))

        return connection


class NCConnection(object):

    def __init__(self, context,legacy=False):

        self.context = context
        self.legacy  = legacy
        self._ncc_connection = None


    @property
    def connection(self):

         try:
             if self._ncc_connection is None or not self._ncc_connection.connected:

                 print("***** new Connection to {}  legacy = {}".format(self.context.host,self.legacy))
                 self._ncc_connection = self._connect(self.context)

         except Exception as e:
             raise e

         return self._ncc_connection


    def _connect(self, context):

        port = context.yang_port

        if self.legacy :
            port = context.legacy_port

        return manager.connect(
            host=context.host, port=port,
            username=context.username, password=context.password,
            hostkey_verify=False,
            device_params={'name': "default"}, timeout=context.nc_timeout,
            allow_agent=False, look_for_keys=False)



    def get(self,filter=''):
        return self.connection.get(filter=('subtree', filter))


    def edit_config(self,config='',target='running'):
        with self.connection.locked(target):
            return self.connection.edit_config(target=target, config=config)


class YangConnection(NCConnection):
    def __init__(self,context):
        super(YangConnection,self).__init__(context)

class LegacyConnection(NCConnection):
    def __init__(self,context):
        super(LegacyConnection,self).__init__(context,legacy=True)