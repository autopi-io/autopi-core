import datetime
import logging
import re
import threading


PROFILING = False

if PROFILING:
    import cProfile as profile

log = logging.getLogger(__name__)


class WorkerThread(threading.Thread):
    """
    Class to easily schedule and run worker threads.
    """

    def __init__(self, name=None, target=None, context={}, loop=-1, delay=0, interval=0, registry=None):

        if target == None:
            raise ValueError("Target function must be defined")

        super(WorkerThread, self).__init__()

        # Generate name if none specified
        if name == None:
            name = "{:s}_{{id}}".format(target.__name__)

        # Standard attributes
        self.name = name.format(id=id(self))
        self.daemon = True

        # Additional attributes
        self.target = target
        self.context = context
        self.loop = loop
        self.delay = delay
        self.interval = interval
        self.registry = registry
        self.kill_event = threading.Event()

        if registry and not registry.add(self):
            raise ValueError("Worker thread '{:s}' already added to registry".format(name))

    def run(self):
        if PROFILING:
            prof_file = "/tmp/{:%Y%m%d%H%M%S}_{:}.prof".format(datetime.datetime.now(), self.name)

            log.warning("Profiling worker thread '%s' - after thread termination stats file will be written to: %s", self.name, prof_file)

            profile.runctx("self.work()", globals(), locals(), prof_file)

            log.info("Profiling stats written to: %s", prof_file)

        else:
            self.work()

    def work(self):
        try:

            if self.delay and self.delay > 0.0:
                log.info("Delayed start of %f second(s) of worker thread '%s'", self.delay, self.name)

                self.context["state"] = "pending"

                self.kill_event.wait(self.delay)
                if self.is_killed():
                    return

            log.debug("Running worker thread '%s'...", self.name)

            self.context["state"] = "running"
            self.context["first_run"] = datetime.datetime.utcnow().isoformat()

            while not self.is_killed() and self.loop != 0:
                if self.loop > 0:
                    self.loop -= 1

                self.target(self, self.context)

                if self.interval > 0:
                    self.context["last_run"] = datetime.datetime.utcnow().isoformat()

                    self.kill_event.wait(self.interval)

            self.context["state"] = "completed"

        except Exception:
            log.exception("Fatal exception in worker thread '%s'", self.name)

            self.context["state"] = "failed"

            raise

        finally:
            log.info("Worker thread '%s' terminated", self.name)

            if self.registry and self.registry.remove(self):
                log.debug("Worker thread '%s' removed from registry", self.name)
            else:
                log.warn("Was unable to remove worker thread '%s' from registry", self.name)

    def is_killed(self):
        return self.kill_event.is_set()

    def kill(self):
        self.kill_event.set()


class ThreadRegistry(object):
    """
    Class to safely manage a collection of threads.

    This class is thread safe.
    """

    def __init__(self):
        self._threads = set()
        self._lock = threading.RLock()

    def add(self, thread):
        with self._lock:
            if not self.find_all_by(thread.name):
                self._threads.add(thread)
                return True

            return False

    def remove(self, thread):
        with self._lock:
            if thread in self._threads:
                self._threads.remove(thread)
                return True
                
            return False

    def has(self, thread):
        with self._lock:
            return thread in self._threads

    def find_all_by(self, name):
        with self._lock:
            return [
                t for t in self._threads \
                    if re.match(name.replace("*", ".*"), t.name)
            ]

    def start_all_for(self, name):
        with self._lock:
            threads = self.find_all_by(name)
            for t in threads:
                t.start()

            return threads

    def kill_all_for(self, name, force_wildcard=False):
        with self._lock:
            ret = []

            threads = self.find_all_by(name)
            for t in [t for t in threads if hasattr(t, "kill")]:

                # Names starting with an underscore must be killed explicitly
                if not force_wildcard and t.name.startswith("_") and t.name != name:
                    continue

                t.kill()
                ret.append(t)

            return ret

    def modify_all_for(self, name, callback):
        with self._lock:
            threads = self.find_all_by(name)
            for t in threads:
                callback(t)

            return threads

