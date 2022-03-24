import datetime
import logging
import re
import signal
import sys
import threading

from timeit import default_timer as timer


PROFILING = False

if PROFILING:
    import cProfile as profile

log = logging.getLogger(__name__)

DEBUG = log.isEnabledFor(logging.DEBUG)

on_exit = []


def append_signal_handler_for(sig, func):
    """
    Appends signal handler instead of replacing any existing. Remember this is only possible from main thread.
    """

    # Check for an existing handler
    curr_func = signal.getsignal(sig)
    if not callable(curr_func):
        curr_func = None

    def wrapper(signum, frame, func=func, parent_func=curr_func):
        must_exit = False

        # First call parent handler
        if parent_func != None:
            try:
                parent_func(signum, frame)
            except SystemExit:
                must_exit = True
            except:
                log.exception("Error in parent signal handler {:} for signal number {:}".format(parent_func, signum))

        # Then call handler
        try:
            func(signum, frame)
        finally:
            if must_exit:
                sys.exit()

    # Register wrapper
    signal.signal(sig, wrapper)


def intercept_exit_signal(func):
    """
    Decorator
    """

    def handle_signal(signum, frame):
        for func in on_exit:
            try:
                func()
            except:
                log.exception("Error in exit event handler {:} for signal number {:}".format(func, sig))

    append_signal_handler_for(signal.SIGINT, handle_signal)
    append_signal_handler_for(signal.SIGTERM, handle_signal)

    return func


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

            if DEBUG:
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
                if DEBUG:
                    log.debug("Worker thread '%s' removed from registry", self.name)
            else:
                log.warn("Was unable to remove worker thread '%s' from registry", self.name)

    def pause(self):
        if not self.proceed_event.is_set():
            return

        if DEBUG:
            log.debug("Pausing worker thread '%s'...", self.name)

        # Disallow to proceed
        self.proceed_event.clear()

        # Ensure to wake up if sleeping
        self.wake_event.set()

    def start_or_resume(self):
        """
        Starts or resumes the WorkerThread instance
        """

        # Noop when we've raised the white flag
        if self.terminate:
            return

        # Thread hasn't started yet
        if not self.is_alive():
            self.start()

        # Assume thread is paused
        else:
            self.resume() # This method will do the checking for us

    def resume(self):
        if self.proceed_event.is_set():
            return

        if DEBUG:
            log.debug("Resuming worker thread '%s'...", self.name)

        # Disallow wake to enforce sleep interval again
        self.wake_event.clear()

        # Allow to proceed
        self.proceed_event.set()

    def kill(self, run=False):
        if self.terminate:
            return

        if DEBUG:
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


class AsyncWriterThread(threading.Thread):
    """
    Writes to file asynchronously in background thread.
    """

    def __init__(self, file, flush_threshold=8192, flush_timeout=1, buffer_size=10485760, buffer_high_watermark=0):
        super(AsyncWriterThread, self).__init__()

        # Validate arguments
        if not flush_threshold:
            raise ValueError("Flush threshold must greater than zero")

        if not flush_timeout:
            raise ValueError("Flush timeout must greater than zero")

        if not buffer_size:
            raise ValueError("Buffer size must greater than zero")

        if flush_threshold * 2 > buffer_size:
            raise ValueError("Flush threshold cannot be higher than half of buffer size")

        if buffer_high_watermark > buffer_size:
            raise ValueError("Buffer high watermark cannot be higher than buffer size")

        # Set inherited attributes
        self.daemon = True

        # Set public attributes
        self.flush_threshold = flush_threshold
        self.flush_timeout = flush_timeout
        self.buffer_size = buffer_size

        # Set private attributes
        self._file = file
        self._stop = False
        self._lock = threading.RLock()
        self._event = threading.Event()
        self._next_flush_timeout = timer() + flush_timeout
        self._buffer_data = ""
        self._buffer_count = 0
        self._buffer_high_watermark = buffer_high_watermark or flush_threshold * 2

        # Start thread
        self.start()

    def __str__(self):
        return "<{:}.{:} file={:} at {:}>".format(
            self.__class__.__module__,
            self.__class__.__name__,
            self._file,
            hex(id(self))
        )

    @property
    def name(self):
        return self._file.name
    
    @property
    def stopped(self):
        return self._stop

    @property
    def closed(self):
        return self._file.closed

    def stop(self):

        # Skip if already stopped
        if self._stop:
            return

        # Raise stop flag
        self._stop = True

        # Signal event to interrupt waiting
        self._event.set()

        # Wait for thread to terminate
        self.join()

    def close(self):

        # First ensure stopped
        self.stop()

        # Then close file
        self._file.close()

    def write(self, data):

        # Skip if no data
        if not data:
            return

        data_len = len(data)

        # Append data to buffer inside critical section
        with self._lock:

            # Check for buffer overflow
            if self._buffer_count + data_len > self.buffer_size:
                # NOTE: Possible broken line here if partial line written
                raise Warning("Buffer overflow in asynchronous writer for {:}".format(self._file))

            self._buffer_data += data
            self._buffer_count += data_len

            if self._stop:
                log.warning("Asynchronous writer for {:} is stopped - writing buffer synchronously".format(self._file))

                # Force write buffer synchronously
                self._write_buffer(force=True)

            else:

                # Signal event if flush threshold is reached
                if self.flush_threshold > 0 and self._buffer_count >= self.flush_threshold:
                    self._event.set()

    def _write_buffer(self, force=False):

        with self._lock:

            # First reset event if set
            if self._event.is_set():
                self._event.clear()

            # Skip if buffer is empty
            if not self._buffer_count:
                if DEBUG:
                    log.debug("Buffer empty for {:}".format(self._file))

                return

            if not force:

                # Skip if flush timeout is not reached 
                if self._next_flush_timeout > timer():
                    return
                elif DEBUG:
                    log.debug("Buffer flush timeout exceeded with {:} second(s) for {:}".format(timer() - self._next_flush_timeout, self._file))

            # Read out buffer to local variable
            buf = self._buffer_data
            buf_len = self._buffer_count

            # Clear buffer
            self._buffer_data = ""
            self._buffer_count = 0

        # Check if high watermark warning should be reported
        if buf_len >= self._buffer_high_watermark:
            log.warning("Buffer reached high watermark ({:}/{:}) for {:}".format(buf_len, self._buffer_high_watermark, self._file))

        # Perform actual write outside critical section
        if DEBUG:
            log.debug("Asynchronously writing buffer ({:}/{:} bytes) to {:}".format(buf_len, self.buffer_size, self._file))

        self._file.write(buf)

        # Update next flush timeout
        self._next_flush_timeout = timer() + self.flush_timeout

    def run(self):
        log.info("Starting asynchronous writer thread for {:}".format(self._file))

        try:

            # Loop until stopped
            while not self._stop:

                # Wait for event up until flush timeout
                if self._event.wait(self.flush_timeout):
                    self._write_buffer(force=self._stop)  # Force write out if stopped

                # Waiting timed out
                else:
                    if DEBUG:
                        log.debug("Buffer timed out waiting for data to {:}".format(self._file))

                    self._write_buffer(force=True)

            log.info("Stopped asynchronous writer thread for {:}".format(self._file))
        except:

            # Ensure stop flag is set
            self._stop = True

            log.exception("Error in asynchronous writer thread for {:}".format(self._file))
