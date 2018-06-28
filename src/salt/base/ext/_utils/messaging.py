import datetime
import logging
import re
import salt.exceptions
import salt.utils.event
import threading
import threading_more
import time
import urlparse
import uuid


log = logging.getLogger(__name__)


class MessageProcessor(object):
    """
    Native hooks:
        - 'worker':    TODO
        - 'workflow':  TODO
        - 'listener':  TODO

    Built-in workers:
        - 'shared':    Workflow is performed by the current message processor thread.
        - 'dedicated': Workflow is performed by a dedicated thread.

    Built-in workflows and their additional hooks:
        - 'simple':    <handler> --> [returner]
        - 'extended':  [validator] (--> [returner]) --> <handler> --> [converter] --> [retuner]
        - 'manage':    Special workflow for management stuff. See implementation for details.

    NOTES:
        - All hook functions registered using the hook decorator are synchronized before invocation to ensure thread safety.
        - If you add your own hook methods by inheriting from this class you are responsible for thread synchronization.
    """

    def __init__(self, default_hooks={}):
        self._default_hooks = default_hooks
        self._hook_funcs = {}  # Index of all registered hook functions
        self._hook_lock = threading.RLock()  # Used to synchronize hook function calls
        self._worker_threads = threading_more.ThreadRegistry()  # Keeps track of all active workers
        self._listeners = []

        # Set default hooks that will be used if none specified
        if not "worker" in self._default_hooks:
            self._default_hooks["worker"] = "shared"
        if not "workflow" in self._default_hooks:
            self._default_hooks["workflow"] = "simple"

    def close(self):

        # Kill all worker threads if any
        threads = self._worker_threads.kill_all_for("*")
        if threads:
            log.info("Killing all worker thread(s): {:s}".format(", ".join([t.name for t in threads])))

    def register_hook(self, synchronize=True):
        """
        Decorator to register hook functions for this message processor.

        Args:
            synchronize (bool): Enables thread synchronization for entire hook function.
        """

        def decorator(func):
            ret_func = func

            # Wrap in synchronizer if requeexitsted
            if synchronize:
                def synchronizer(*args, **kwargs):
                    with self._hook_lock:
                        return func(*args, **kwargs)
                ret_func = synchronizer

            # Add function to hook registry
            name = func.__name__
            self._hook_funcs[name] = ret_func

            log.debug("Registered hook function '%s'", name)

            return ret_func

        return decorator

    def register_listener(self, matcher=None):
        """
        Decorator to register result listener functions.
        """

        def decorator(func):
            log.debug("Registered listener function '%s'", func.__name__)

            self._listeners.append({
                "func": func,
                "matcher": matcher,
            })

            return func

        return decorator

    def process(self, message):
        """
        Process a single message.
        """

        # Find worker and use it
        func, settings = self._get_hook_for(message, "worker", parse_settings=True)
        result = func(message, **settings)

        return result

    #region Available workers

    def shared_worker(self, message, **settings):
        """
        Run workflow in current thread.
        """

        found, result = self._call_hook_for(message, "workflow", message)

        return result

    def dedicated_worker(self, message, **settings):
        """
        Run workflow in a dedicated thread.
        """

        # Check if we need to dequeue message from an existing worker thread
        if "dequeue" in settings:
            threads = self._worker_threads.modify_all_for(settings["dequeue"],
                lambda t: t.context["messages"].remove(message))

            return {
                "dequeued": [t.name for t in threads]
            }

        # Check if we need to enqueue message to an existing worker thread
        if "enqueue" in settings:
            threads = self._worker_threads.modify_all_for(settings["enqueue"],
                lambda t: t.context["messages"].append(message))

            return {
                "enqueued": [t.name for t in threads]
            }

        # Exceptions will kill worker thread as default behavior
        suppress_exceptions = settings.pop("suppress_exceptions", False)

        # Terminates worker thread after a successful run without warnings nor exceptions
        kill_upon_success = settings.pop("kill_upon_success", False)

        # Prepare function that performs actual work
        def do_work(thread, context):
            success = True

            # Loop through all messages found in thread context
            for message in list(context["messages"]):  # Copy list to allow changes while looping
                try:

                    # Run workflow
                    self._call_hook_for(message, "workflow", message)

                except Warning as w:
                    log.info("Warning in worker thread '{:}': {:}".format(thread.name, w))
                    success = False

                except Exception:
                    log.exception("Exception in worker thread '{:}' while running workflow for message: {:}".format(thread.name, message))
                    success = False

                    if suppress_exceptions:
                        log.warn("Suppressing above exception and continues as nothing happened")
                    else:
                        raise

            if kill_upon_success and success:
                thread.kill()

                log.info("Killed worker thread '{:}' upon successful run")

        # Auto start is default
        auto_start = settings.pop("start", True)

        # Add new worker thread
        thread = threading_more.WorkerThread(
            target=do_work,
            context={"messages": [message] if message else []},
            registry=self._worker_threads,  # Registers thread in registry
            **settings)  # Pass additional settings

        if auto_start:
            thread.start()

            return {
                "started": thread.name
            }

        return {
            "created": thread.name
        }

    #endregion

    #region Available workflows

    def simple_workflow(self, message):
        """
        Simlpe message processing flow and available hooks:

            <handler> --> [returner]
        """

        args = message.get("args", [])
        kwargs = message.get("kwargs", {})

        # Call handler hook
        found, result = self._call_hook_for(message, "handler", *args, **kwargs)

        # Call result listeners
        self._call_listeners_for(message, result)

        # Call returner hook
        self._call_hook_for(message, "returner", message, result)

        return result

    def extended_workflow(self, message):
        """
        Extended message processing flow and available hooks:

            [validator] --> <handler> --> [converter] --> [retuner]
        """

        args = message.get("args", [])
        kwargs = message.get("kwargs", {})

        # Call validator hook
        found, error = self._call_hook_for(message, "validator", *args, **kwargs)
        if found and error:
            raise Exception(error)

        # Call handler hook
        found, result = self._call_hook_for(message, "handler", *args, **kwargs)

        # Call converter hook
        found, convert = self._call_hook_for(message, "converter", result)
        if found:
            result = convert

        # Call result listeners
        self._call_listeners_for(message, result)

        # Call returner hook
        self._call_hook_for(message, "returner", message, result)

        return result

    def manage_workflow(self, message):
        """
        Administration workflow to query and manage this processor instance.

        Supported commands:
            - <hook> [name]
            - <worker> <list|show|create|start|kill> [name|*]
        """

        args = message.get("args", [])
        kwargs = message.get("kwargs", {})

        if len(args) > 1 and args[0] == "hook":
            if len(args) > 2:
                return self._get_func(args[1])(*args[2:], **kwargs)
            else:
                return {
                    "result": [h for h in self._hook_funcs]
                }

        elif len(args) > 1 and args[0] == "worker":
            if args[1] == "list":
                return {
                    "result": [
                        t.name for t in self._worker_threads.find_all_by(args[2] \
                            if len(args) > 2 else "*")
                    ]
                }

            elif args[1] == "show":
                threads = self._worker_threads.find_all_by(args[2] if len(args) > 2 else "*")
                return {
                    "result": {t.name: t.context for t in threads}
                }

            elif args[1] == "create":
                return self.dedicated_worker(None, **kwargs)

            elif args[1] == "start":
                threads = self._worker_threads.start_all_for(args[2])
                return {
                    "started": [t.name for t in threads]
                }

            elif args[1] == "kill":
                threads = self._worker_threads.kill_all_for(args[2])
                return {
                    "killed": [t.name for t in threads]
                }

        raise Exception("Invalid or unknown command")

    #endregion

    #region Private helpers

    def _call_hook_for(self, message, kind, *args, **kwargs):
        func = self._get_hook_for(message, kind)
        if func:
            return True, func(*args, **kwargs)
        return False, None

    def _get_hook_for(self, message, kind, parse_settings=False):
        url = self._get_hook_url_for(message, kind)
        if not url:
            return

        name = url

        # Parse settings from url if requsted
        if parse_settings:
            name, settings = self._parse_hook_url(url)

        # Get hook function by name
        func = self._get_func("{:s}_{:s}".format(name, kind))

        if parse_settings:
            return (func, settings)
        else:
            return func

    def _parse_hook_url(self, url):
        u = urlparse.urlparse(url)

        name = u.path
        settings = {}

        if u.query:
            qs = urlparse.parse_qs(u.query, strict_parsing=True)

            for k, v in qs.iteritems():

                # Convert into appropriate types using eval (integers, decimals and booleans)
                v = [eval(e) if re.match("^(?:[-+]?\d*\.?\d*|True|False)$", e) else e for e in v]

                if len(v) == 1:
                    settings[k] = v[0]
                else:
                    settings[k] = v

        return (name, settings)

    def _get_hook_url_for(self, message, kind):
        return message.get(kind, self._default_hooks.get(kind, None))

    def _get_func(self, name):
        if name in self._hook_funcs:
            return self._hook_funcs[name]
        elif hasattr(self, name):
            return getattr(self, name)
        else:
            raise Exception("No function found for hook '{:}'".format(name))

    def _call_listeners_for(self, message, result):
        if result == None:
            return

        for listener in self._listeners:
            try:
                # Use matcher function if specified
                matcher = listener["matcher"]
                if matcher != None and not matcher(message, result):
                    continue

                # Call listener
                listener["func"](result)
            except Exception:
                log.exception("Failed executing listener: {:}".format(listener))

    #endregion


class EventDrivenMessageProcessor(MessageProcessor):

    def __init__(self, namespace, default_hooks={}):
        MessageProcessor.__init__(self, default_hooks)
        self._namespace = namespace
        self._tag_regex = re.compile("^{:s}/req/(?P<id>.+)$".format(namespace))
        self._event_matchers = []
        self._bus_lock = threading.RLock()  # Used to synchronize event bus function calls

    def init(self, opts, workers=None):
        """
        Initialize this instance.
        """

        # Dedicated event bus handle for receiving events
        self._incoming_bus = salt.utils.event.get_event("minion",
            opts=opts,
            transport=opts["transport"],
            listen=True)

        # Dedicated event bus handle for sending events
        self._outgoing_bus = salt.utils.event.get_event("minion",
            opts=opts,
            transport=opts["transport"],
            listen=False)

        # Prepare match functions for already registered event matchers
        for em in self._event_matchers:
            em["match_func"] = self._incoming_bus._get_match_func(em["match_type"])

        # Register matcher for event processor
        self.register_event_matcher(
            self._tag_regex.pattern,
            self.process_event,
            match_type="regex")

        # Add given workers
        if workers:
            for worker in workers:
                messages = worker.pop("messages")

                self.dedicated_worker(None, start=False, **worker)

                # Enqueue all messages to worker
                for message in messages:
                    self.dedicated_worker(message, enqueue=worker["name"])

    def register_event_matcher(self, tag, func, match_type="startswith"):
        """
        Register additional event matchers to catch other events.
        """

        em = {
            "tag": tag,
            "match_type": match_type,
            "match_func": self._incoming_bus._get_match_func(match_type),
            "func": func,
        }
        self._event_matchers.append(em)

    def run(self):
        """
        Blocking method that processes all received events.
        """

        # Ensure all worker threads are started
        worker_threads = self._worker_threads.start_all_for("*")
        if worker_threads:
            log.info("Starting {:d} worker thread(s): {:s}".format(len(worker_threads), ", ".join([t.name for t in worker_threads])))

        # Listen for incoming messages
        log.debug("Listening for incoming events using %d registered event matcher(s)", len(self._event_matchers))
        for event in self._incoming_bus.iter_events(full=True, auto_reconnect=True):
            if not event:
                log.warn("Skipping empty event")
                continue

            try:
                for matcher in self._event_matchers:
                    if not matcher["match_func"](event["tag"], matcher["tag"]):
                        continue

                    log.debug("Matched event: %s", repr(event))

                    matcher["func"](event)

            except Exception:
                log.exception("Failed to process received event: {:}".format(event))

    def process_event(self, event):
        """
        Process a received event.
        """

        res = None

        try:

            # Extract message from event
            message = event["data"]

            # Add reference to original event tag
            # (used to get correlation id when/if sending back reply)
            message["_event_tag"] = event["tag"]

            # Process message
            res = self.process(message)

        except Exception as ex:
            log.exception("Exception while processing event: {:}".format(event))

            res = {
                "error": str(ex)
            }
        finally:

            # Send back reply event
            if res != None:
                self.send_reply_event_for(message, res)
            else:
                log.warn("No reply to send back for event: {:}".format(event))

    def trigger_event(self, data, tag):
        """
        Trigger an outgoing event.
        """

        log.info("Triggering event with tag '{:s}': {:}".format(tag, data))

        with self._bus_lock:  # Synchronize just to be safe
            self._outgoing_bus.fire_event(data, tag)

    def subscribe_to_events(self, tag, match_type="startswith"):
        """
        Decorator to let a function subscribe to events matching specified tag pattern.
        """

        def decorator(func):
            self._event_matchers.append({
                "tag": tag,
                "match_type": match_type,
                "match_func": None,
                "func": func,
            })

            return func

        return decorator

    def send_reply_event_for(self, message, data):
        """
        Send back reply data for a received message.
        """

        # Extract correlation id from original event
        match = self._tag_regex.match(message["_event_tag"])
        groups = match.groupdict()
        tag = "{:s}/res/{:s}".format(self._namespace, groups["id"])

        log.debug("Sending reply mesage with tag '{:s}': {:}".format(tag, data))

        # Send reply event
        with self._bus_lock:  # Synchronize just to be safe
            self._outgoing_bus.fire_event(data, tag)

    #region Built-in hooks

    def reply_returner(self, message, result):
        self.send_reply_event_for(message, result)

    #endregion


class EventDrivenMessageClient(object):

    def __init__(self, namespace, default_timeout=30):
        self._namespace = namespace
        self._default_timeout = default_timeout

    def init(self, opts):
        self._opts = opts

        # Shared event bus handle for sending events
        self._outgoing_bus = salt.utils.event.get_event("minion",
            opts=opts,
            transport=opts["transport"],
            listen=False)

    def send_sync(self, message, timeout=None):

        if timeout == None:
            timeout = message.get("timeout", self._default_timeout)

        id = self.send_async(message)
        reply = self.recv_reply(id, timeout)

        return reply

    def send_async(self, message):

        # Send message on bus
        correlation_id = uuid.uuid4()
        tag = "{:s}/req/{:s}".format(self._namespace, correlation_id)

        log.debug("Sending request message with tag '%s': %s", tag, message)
        self._outgoing_bus.fire_event(message, tag)

        return correlation_id

    def recv_reply(self, correlation_id, timeout=None):

        # Determine timeout
        timeout = timeout or self._default_timeout

        # Dedicated event bus handle for receiving reply
        incoming_bus = salt.utils.event.get_event("minion",
            opts=self._opts,
            transport=self._opts["transport"],
            listen=True)

        # Construct event tag to listen on
        tag = "{:s}/res/{:s}".format(self._namespace, correlation_id)

        # Wait for message until timeout
        message = incoming_bus.get_event(wait=timeout, tag=tag, match_type="startswith")
        if not message:
            log.warn("No reply message with tag '%s' received within timeout of %d secs", tag, timeout)

            raise salt.exceptions.CommandExecutionError(
                "No reply message received within timeout of {:d} secs - please try again and maybe increase timeout value".format(timeout))

        # Check for error
        if "error" in message:
            raise salt.exceptions.CommandExecutionError(message["error"])

        return message


def msg_pack(*args, **kwargs):
    """
    Helper method to pack message into dict.
    """

    msg = {}
    if args:
        msg["args"] = args
    if kwargs:
        for k, v in kwargs.iteritems():
            if v == None:
                continue
            if k.startswith("__"):  # Filter out Salt params (__pub_*)
                continue

            if k.startswith("_"):
                msg[k.lstrip("_")] = v
            else:
                if not "kwargs" in msg:
                    msg["kwargs"] = {}

                msg["kwargs"][k] = v

    return msg


def keyword_resolve(data, keywords={}, symbol="$"):
    """
    Helper method to resolve keywords in a data structure.
    """

    if isinstance(data, (list, tuple, set)):
        for idx, val in enumerate(data):
            data[idx] = keyword_resolve(val, keywords)

    if isinstance(data, dict):
        for key, val in data.iteritems():
            data[key] = keyword_resolve(val, keywords)

    elif isinstance(data, basestring) and symbol in data:

        # Replace keywords in data
        for key in keywords:
            data = data.replace("{:s}{:s}".format(symbol, key), "__{:s}__".format(key))

        return eval(data, {"__{:s}__".format(key): val for key, val in keywords.iteritems()})

    return data

