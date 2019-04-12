from neutron.agent.common.resource_processing_queue import ExclusiveResourceProcessor
from six.moves import queue as Queue
from oslo_config import cfg

class RouterProcessingQueue(object):
    """Manager of the queue of routers to process."""
    def __init__(self):
        self._queue = Queue.PriorityQueue()

    def add(self, update):
        self._queue.put(update)

    def each_update_to_next_router(self):
        """Grabs the next router from the queue and processes

        This method uses a for loop to process the router repeatedly until
        updates stop bubbling to the front of the queue.
        """

        next_update = self._queue.get()
        if next_update is not None:
            with ExclusiveRouterProcessor(next_update.id) as rp:
                # Queue the update whether this worker is the master or not.
                rp.queue_update(next_update)

                # Here, if the current worker is not the master, the call to
                # rp.updates() will not yield and so this will essentially be a
                # noop.
                for update in rp.updates():
                    yield (rp, update)
