"""Handle sync and async tasks."""
import asyncio
from collections import deque
from functools import partial
import logging
import threading
import time
from timeit import default_timer as timer

from .ota import OTAFirmware, load_fw
from .persistence import Persistence

_LOGGER = logging.getLogger(__name__)


class Tasks:
    """Handle gateway tasks.

    I/O is allowed in this class. The Task class should host methods that need
    to do I/O or perform tasks that are not related to the gateway transport
    type.

    The transport attribute should hold an instance of the Transport class.
    """

    # pylint: disable=too-many-arguments

    def __init__(self, const, persistence, persistence_file, sensors, transport):
        """Set up Tasks."""
        self.queue = deque()
        self.ota = OTAFirmware(sensors, const)
        if persistence:
            self.persistence = Persistence(
                sensors, self._schedule_factory, persistence_file=persistence_file
            )
        else:
            self.persistence = None
        self.transport = transport

    def _schedule_factory(self, save_sensors):
        """Return function to schedule saving sensors."""
        raise NotImplementedError

    def add_job(self, func, *args):
        """Add a job that should return a reply to be sent."""
        raise NotImplementedError

    def run_job(self, job=None):
        """Run a job, either passed in or from the queue.

        A job is a tuple of function and optional args. Keyword arguments
        can be passed via use of functools.partial. The job should return a
        string that should be sent by the gateway protocol. The function will
        be called with the arguments and the result will be returned.
        """
        if job is None:
            if not self.queue:
                return None
            job = self.queue.popleft()
        start = timer()
        func, args = job
        reply = func(*args)
        end = timer()
        if end - start > 0.1:
            _LOGGER.debug(
                "Handle queue with call %s(%s) took %.3f seconds",
                func,
                args,
                end - start,
            )
        return reply

    def start(self):
        """Start the gateway and task allow tasks to be scheduled."""
        raise NotImplementedError

    def stop(self):
        """Stop the gateway and stop allowing tasks for the scheduler."""
        raise NotImplementedError

    def start_persistence(self):
        """Start persistence."""
        raise NotImplementedError

    def update_fw(self, nids, fw_type, fw_ver, fw_path=None):
        """Update firwmare."""
        raise NotImplementedError


class SyncTasks(Tasks):
    """Sync version of tasks class."""

    def __init__(self, *args, **kwargs):
        """Set up Tasks."""
        super().__init__(*args, **kwargs)
        self._cancel_save = None
        self._stop_event = threading.Event()

    def add_job(self, func, *args):
        """Add a job that should return a reply to be sent.

        A job is a tuple of function and optional args. Keyword arguments
        can be passed via use of functools.partial. The job should return a
        string that should be sent by the gateway protocol.
        """
        self.queue.append((func, args))

    def start(self):
        """Start the connection to a transport."""
        self.transport.connect()
        poll_thread = threading.Thread(target=self._poll_queue)
        poll_thread.start()

    def _poll_queue(self):
        """Poll the queue for work."""
        while not self._stop_event.is_set():
            reply = self.run_job()
            self.transport.send(reply)
            if self.queue:
                continue
            time.sleep(0.02)

    def _schedule_factory(self, save_sensors):
        """Return function to schedule saving sensors."""

        def schedule_save():
            """Save sensors and schedule a new save."""
            save_sensors()
            scheduler = threading.Timer(10.0, schedule_save)
            scheduler.start()
            self._cancel_save = scheduler.cancel

        return schedule_save

    def start_persistence(self):
        """Load persistence file and schedule saving of persistence file."""
        if not self.persistence:
            return
        self.persistence.safe_load_sensors()
        self.persistence.schedule_save_sensors()

    def stop(self):
        """Stop the background thread."""
        _LOGGER.info("Stopping gateway")
        self.transport.disconnect()
        self._stop_event.set()
        if not self.persistence:
            return
        if self._cancel_save is not None:
            self._cancel_save()
            self._cancel_save = None
        self.persistence.save_sensors()

    def update_fw(self, nids, fw_type, fw_ver, fw_path=None):
        """Update firwmare of all node_ids in nids."""
        fw_bin = None
        if fw_path:
            fw_bin = load_fw(fw_path)
            if not fw_bin:
                return
        self.ota.make_update(nids, fw_type, fw_ver, fw_bin)


class AsyncTasks(Tasks):
    """Async version of tasks class."""

    def __init__(self, *args, loop=None, **kwargs):
        """Set up Tasks."""
        super().__init__(*args, **kwargs)
        self.loop = loop or asyncio.get_event_loop()
        self._cancel_save = None

    async def start(self):
        """Start the connection to a transport."""
        await self.transport.connect()

    async def stop(self):
        """Stop the gateway."""
        _LOGGER.info("Stopping gateway")
        self.transport.disconnect()
        if self.transport.connect_task and not self.transport.connect_task.cancelled():
            self.transport.connect_task.cancel()
            self.transport.connect_task = None
        if not self.persistence:
            return
        if self._cancel_save is not None:
            self._cancel_save()
            self._cancel_save = None
        await self.loop.run_in_executor(None, self.persistence.save_sensors)

    def add_job(self, func, *args):
        """Add a job that should return a reply to be sent.

        A job is a tuple of function and optional args. Keyword arguments
        can be passed via use of functools.partial. The job should return a
        string that should be sent by the gateway protocol.

        The async version of this method will send the reply directly.
        """
        job = func, args
        reply = self.run_job(job)
        self.transport.send(reply)

    def _schedule_factory(self, save_sensors):
        """Return function to schedule saving sensors."""

        async def schedule_save():
            """Save sensors and schedule a new save."""
            await self.loop.run_in_executor(None, save_sensors)
            callback = partial(self.loop.create_task, schedule_save())
            task = self.loop.call_later(10.0, callback)
            self._cancel_save = task.cancel

        return schedule_save

    async def start_persistence(self):
        """Load persistence file and schedule saving of persistence file."""
        if not self.persistence:
            return
        await self.loop.run_in_executor(None, self.persistence.safe_load_sensors)
        await self.persistence.schedule_save_sensors()

    async def update_fw(self, nids, fw_type, fw_ver, fw_path=None):
        """Start update firwmare of all node_ids in nids in executor."""
        fw_bin = None
        if fw_path:
            fw_bin = await self.loop.run_in_executor(None, load_fw, fw_path)
            if not fw_bin:
                return
        self.ota.make_update(nids, fw_type, fw_ver, fw_bin)
