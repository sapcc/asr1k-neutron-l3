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

            result = method(*args, **kwargs)

            duration = time.time()-start

            if self.log:
                LOG.debug('{} executed on {} in {}s'.format(method.__name__,args[0].__class__.__name__ ,duration))

            # Crash if update takes too long - temporary workaround to blocking threads
            if duration > 15:
                exit(1)

            return result

        return wrapper