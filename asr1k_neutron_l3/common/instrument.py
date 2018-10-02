import time
import six
from oslo_log import log as logging

LOG = logging.getLogger(__name__)





class instrument(object):

    def __init__(self, log=True, report=True):
        self.log = log
        self.report = report

    def __call__(self, method):
        @six.wraps(method)
        def wrapper(*args, **kwargs):
            start = time.time()

            context = kwargs.get('context')

            host = ''

            if context is not None:
                host = "{} : ".format(context.host)

            result = method(*args, **kwargs)
            duration = time.time()-start

            if self.log:
                LOG.debug('{}{} executed on {} in {}s'.format(host, method.__name__,args[0].__class__.__name__ ,duration))

            return result

        return wrapper