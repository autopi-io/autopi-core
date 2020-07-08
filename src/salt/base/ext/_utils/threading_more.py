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

    def __init__(self, name=None, target=None, context={}, loop=-1, delay=0, interval=0, auto_start=False, registry=None):

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
        #self.parent = threading.current_thread()
        self.target = target
        self.context = context
        self.loop = loop
        self.delay = delay
        self.interval = interval
        self.auto_start = auto_start
        self.registry = registry
        self.proceed_event = threading.Event()
        self.wake_event = threading.Event()
        self.terminate = False
        self.run_on_terminate = False

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

            # Perform delayed start if requested
            self.__delay()

            # No need to continue if already terminated at this point
            if self.terminate:
                return

            if log.isEnabledFor(logging.DEBUG):
                log.debug("Running worker thread '%s'...", self.name)

            self.context["state"] = "running"
            self.context["first_run"] = datetime.datetime.utcnow().isoformat()

            # Ensure allowed to proceed
            self.proceed_event.set()

            # Loop until completion
            while self.__proceed() and self.loop != 0:
                if self.loop > 0:
                    self.loop -= 1

                self.target(self, self.context)

                if self.interval > 0:
                    self.context["last_run"] = datetime.datetime.utcnow().isoformat()

                    # Sleep until awakened or timeout reached
                    self.wake_event.wait(self.interval)

            self.context["state"] = "completed"

        except Exception:
            log.exception("Fatal exception in worker thread '%s'", self.name)

            self.context["state"] = "failed"

            raise

        finally:

            if self.run_on_terminate:
                log.info("Running worker thread '%s' one last time before being terminated", self.name)

                try:
                    self.target(self, self.context)
                except:
                    log.exception("Failed to run worker thread '%s' one last time before being terminated", self.name)

            log.info("Worker thread '%s' terminated", self.name)

            if self.registry and self.registry.remove(self):
                if log.isEnabledFor(logging.DEBUG):
                    log.debug("Worker thread '%s' removed from registry", self.name)
            else:
                log.warn("Was unable to remove worker thread '%s' from registry", self.name)

    def pause(self):
        if not self.proceed_event.is_set():
            return

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Pausing worker thread '%s'...", self.name)

        # Disallow to proceed
        self.proceed_event.clear()

        # Ensure to wake up if sleeping
        self.wake_event.set()

    def resume(self):
        if self.proceed_event.is_set():
            return

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Resuming worker thread '%s'...", self.name)

        # Disallow wake to enforce sleep interval again
        self.wake_event.clear()

        # Allow to proceed
        self.proceed_event.set()

    def kill(self, run=False):
        if self.terminate:
            return

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Killing worker thread '%s'...", self.name)

        # Set flag that decide whether to run one last time
        self.run_on_terminate = run

        # Raise the white flag
        self.terminate = True

        # Ensure to proceed if waiting
        self.proceed_event.set()

        # Ensure to wake up if sleeping
        self.wake_event.set()

    def __delay(self):
        if self.delay and self.delay > 0.0:
            log.info("Delayed startup/resume of %f second(s) of worker thread '%s'...", self.delay, self.name)

            self.context["state"] = "pending"

            # Sleep until awakened or timeout reached
            self.wake_event.wait(self.delay)

    def __proceed(self):

        # Check whether to wait or proceed
        if not self.proceed_event.is_set():
            self.context["state"] = "paused"

            log.info("Paused worker thread '%s'", self.name)

            # Wait until allowed to proceed again
            self.proceed_event.wait()

            # No need to continue if terminated at this point
            if self.terminate:
                return False

            log.info("Resumed worker thread '%s'", self.name)

            # Perform initial delay if any
            self.__delay()

            self.context["state"] = "running"

        # Check if set to terminate
        if self.terminate:
            return False

        return True


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

    def do_for_all_by(self, name, func, force_wildcard=False):
        with self._lock:
            ret = []

            threads = self.find_all_by(name)
            for t in threads:

                # Unless forced is name starting with an underscore not matched with wildcard
                if not force_wildcard and t.name.startswith("_") and t.name != name:
                    continue

                func(t)

                ret.append(t)

            return ret

    def do_for_all(self, filter_func, do_func):
        with self._lock:
            ret = []

            for t in filter(filter_func, self._threads):
                do_func(t)

                ret.append(t)

            return ret


class TimedEvent(threading._Event):
    """
    Records exact timestamp of when a event was set.
    """

    def __init__(self, *args, **kwargs):
        self.timestamp = None

        super(TimedEvent, self).__init__(*args, **kwargs)

    def set(self):
        self.timestamp = datetime.datetime.utcnow()

        super(TimedEvent, self).set()

    def clear(self):
        self.timestamp = None
        
        super(TimedEvent, self).clear()


class ReturnThread(threading.Thread):
    """
    Stores the return value from the target function.
    """

    def __init__(self, *args, **kwargs):
        super(ReturnThread, self).__init__(*args, **kwargs)

        self._return = None
        self.exception = None

    def run(self):
        if self._Thread__target is not None:
            try:
                self._return = self._Thread__target(*self._Thread__args, **self._Thread__kwargs)
            except Exception as ex:
                self.exception = ex

    def join(self):
        super(ReturnThread, self).join()

        return self._return
