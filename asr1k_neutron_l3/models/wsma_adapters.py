import socket
import time
import abc
from bs4 import BeautifulSoup as bs

from retrying import retry
import eventlet
import requests
from xml.dom.minidom import parseString
from xml.parsers.expat import ExpatError
import xmltodict
import json

from threading import Lock
from asr1k_neutron_l3.models.asr1k_pair import ASR1KPair
from asr1k_neutron_l3.common.asr1k_exceptions import DeviceUnreachable
from asr1k_neutron_l3.common import asr1k_constants
from asr1k_neutron_l3.common.instrument import instrument


from ncclient import manager
from oslo_utils import uuidutils
from oslo_log import log as logging
from oslo_config import cfg
from oslo_service import loopingcall
from paramiko.client import SSHClient,AutoAddPolicy
import paramiko
from ncclient.operations.errors import TimeoutExpiredError
from ncclient.transport.errors import SSHError
from ncclient.transport.errors import SessionCloseError
from ncclient.transport.errors import TransportError
from paramiko.ssh_exception import SSHException, NoValidConnectionsError,ChannelException

LOG = logging.getLogger(__name__)

class BaseWsmaAdapter(object):


    READ_TIMEOUT = 3
    READ_SOAP12 = '''
    <?xml version="1.0" encoding="UTF-8"?>
    <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
      <soap12:Body>
        <request xmlns="urn:cisco:wsma-exec" correlator="{}">
          <execCLI>
            <cmd>{}</cmd>
          </execCLI>
        </request>
      </soap12:Body>
    </soap12:Envelope>
    ]]>]]>'''


    def __init__(self,context,id=0):
        self.context = context
        self._wsma_transport = None
        self._wsma_channel = None

    @property
    def is_wsma_inactive(self):
        return True

    @property
    def wsma_connection(self):
        try:
            if self.is_wsma_inactive:
                try:
                    self.close()
                except BaseException as e:
                    LOG.warning(
                        "Failed to close WSMA connection due to '{}', connection will be attempted again in subsequent iterations".format(
                            e))
                finally:
                    self.connect(self.context)

        except BaseException as e:
            LOG.warning(
                "Failed to connect via WSMA due to '{}', connection will be attempted again in subsequent iterations".format(
                    e))

            LOG.exception(e)


        return self._wsma_channel

    @abc.abstractmethod
    def connect(self, context):
        pass

    @abc.abstractmethod
    def close(self):
        pass

    @abc.abstractmethod
    def run_cli_command(self, command):
        pass


class SshWsmaAdapter(BaseWsmaAdapter):

    PROT = 'ssh'
    EOM = ']]>]]>'
    BUF = 1024 * 1024

    def __init__(self, context, id=0):
        super(SshWsmaAdapter,self).__init__(context,id)





    @property
    def is_wsma_inactive(self):

        if self._wsma_channel is None or self._wsma_transport is None:
            return True
        try:
            return (self._wsma_channel.closed
                    or self._wsma_channel.eof_received
                    or self._wsma_channel.eof_sent
                    or not self._wsma_channel.active)

        except BaseException as e:
            LOG.exception(e)
            return True

    def connect(self, context):
        port = context.legacy_port

        wsma_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        wsma_sock.connect((context.host, port))
        wsma_transport = paramiko.Transport(wsma_sock)
        wsma_transport.connect(username=context.username, password=context.password)

        wsma_channel = wsma_transport.open_session(timeout=2)
        wsma_channel.set_name('wsma')
        wsma_channel.invoke_subsystem('wsma')
        self._wsma_transport = wsma_transport
        self._wsma_channel = wsma_channel
        self._wsma_channel.setblocking(True)

        bytes = u''

        while bytes.find(self.EOM) == -1:
            start= time.time()
            if time.time() - start > self.READ_TIMEOUT:
                LOG.error("Timeout on WSMA read")
                break
            bytes += self._wsma_channel.recv(self.BUF)


    def close(self):
        if self._wsma_transport is not None :
            try:
                self._wsma_transport.close()
            except BaseException as e:
                LOG.warning(
                    "Failed to close WSMA connection due to '{}', connection will be attempted again in subsequent iterations".format(
                        e))
                LOG.exception(e)
        self._wsma_transport = None
        self._wsma_channel = None

    def run_cli_command(self, command):
        start = time.time()
        uuid = uuidutils.generate_uuid()
        self.wsma_connection.sendall(self.READ_SOAP12.format(uuid,command))

        response =  self._wsma_reply(self.wsma_connection,uuid)
        LOG.debug("{}] {} run cli command {} in {}s".format(self.context.host,uuid,command, time.time() - start))
        return response

    def _wsma_reply(self,channel,uuid=None):
        bytes = self._wsma_read(channel)

        if self._is_wsma_hello(bytes):
            LOG.debug("Filtered hello for channel stdout ")
            return []

        response = bs(bytes, 'lxml').find('response')
        if uuid is not None and response is not None:
            if response.get("correlator") != uuid:
                LOG.warning("Failed to correlate reply {} with request {} in CLI execute".format(response.get("correlator"),uuid))
                return []




        result = []
        return_text = bs(bytes, 'lxml').find('text')
        if return_text is not None:
            raw = bs(bytes, 'lxml').find('text').contents[0].splitlines()
            for l in raw:
                if len(l.strip(" "))>0:
                    result.append(l.strip(" "))


        return result

    def _is_wsma_hello(self,bytes):
        request = bs(bytes, 'lxml').find('request')
        if request is not None:
            if request.get("xmlns") == "urn:cisco:wsma-hello":
                return True

        return False

    def _wsma_read(self,channel):
        start = time.time()
        bytes = u''
        while bytes.find(self.EOM) == -1:

            if time.time() - start > self.READ_TIMEOUT:
                LOG.error("Timeout on WSMA read")
                break
            bytes += channel.recv(self.BUF).decode('utf-8')

        return bytes.replace(self.EOM, '')





class HttpWsmaAdapter(BaseWsmaAdapter):

    def __init__(self, context, id=0):
        super(HttpWsmaAdapter, self).__init__(context, id)


    def connect(self, context):
        verify = False
        self._wsma_transport = requests.Session()
        self._wsma_transport.auth = (context.username, context.password)
        self._wsma_channel = self._wsma_transport
        if context.insecure:
            requests.packages.urllib3.disable_warnings()

    def close(self):
        if self._wsma_transport is not None:
            self._wsma_transport.close()

    def run_cli_command(self, command):
        uuid = uuidutils.generate_uuid()
        payload = self.READ_SOAP12.format(uuid,command)

        response =   self.wsma_connection.post(url="{}://{}:{}/wsma".format(self.context.protocol, self.context.host, self.context.http_port), data=payload,
                            verify= not self.context.insecure,
                            timeout=3)
        xml_text = response.content.decode("utf-8")

        success,result = self._process(xml_text)

        return result



    def _parseXML(self,xml_text):
        if xml_text is None:
            return dict(error='XML body is empty')


        try:
            dom = parseString(xml_text)
        except ExpatError as e:
            return dict(error='%s' % e)

        response = dom.getElementsByTagName('response')
        if len(response) > 0:
            return xmltodict.parse(response[0].toxml())

        return xmltodict.parse(
            dom.getElementsByTagNameNS(
                "http://schemas.xmlsoap.org/soap/envelope/",
    "Envelope")[0].toxml())


    def _process(self,xml_data):
        data = self._parseXML(xml_data)

          # did the parsing yield an error?
        if data.get('error') is not None:
            return False,[]


        # was it successful?
        try:
            success = bool(int(data['response']['@success']))
        except KeyError:
            output = 'unknown error / key error'
            return False,[]

        # exec mode?
        if data['response']['@xmlns'] == "urn:cisco:wsma-exec":
            if success:
                try:
                    t = data['response']['execLog'][
                        'dialogueLog']['received']['text']
                except KeyError:
                    t = None
                t = '' if t is None else t
                output = t.splitlines()

                return True, output

            if not success:
                e = data['response']['execLog'][
                    'errorInfo']['errorMessage']
                output = e
                return False, output




        return False,[]