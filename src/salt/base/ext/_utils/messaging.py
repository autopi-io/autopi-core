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

from salt_more import SuperiorCommandExecutionError
from timeit import default_timer as timer


log = logging.getLogger(__name__)


class MessageProcessor(object):
    """
    Native hooks:
        - 'worker':    TODO
        - 'workflow':  TODO

    Built-in workers:
        - 'shared':    Workflow is performed by the current message processor thread.
        - 'dedicated': Workflow is performed by a dedicated thread.

    Built-in workflows and their additional hooks:
        - 'simple':    <handler> --> [trigger] --> [filter] --> [returner]
        - 'extended':  [validator] (--> [returner]) --> <handler> --> [converter] --> [trigger] --> [filter] --> [enricher] --> [retuner]
        - 'manage':    Special workflow for management stuff. See implementation for details.

    NOTES:
        - All hook functions registered using the hook decorator are synchronized before invocation to ensure thread safety.
        - If you add your own hook methods by inheriting from this class you are responsible for thread synchronization.
    """

    def __init__(self, default_hooks={}):
        self._default_hooks = default_hooks
        self._hook_funcs = {}  # Index of all registered hook functions
        self._hook_lock = threading.RLock()  # Used to synchronize hook function calls
        self._measure_stats = False

        self.worker_threads = threading_more.ThreadRegistry()  # Keeps track of all active workers

        # Set default hooks that will be used if none specified
        if not "worker" in self._default_hooks:
            self._default_hooks["worker"] = "shared"
        if not "workflow" in self._default_hooks:
            self._default_hooks["workflow"] = "simple"

    @property
    def measure_stats(self):
        return self._measure_stats

    @measure_stats.setter
    def measure_stats(self, value):
        self._measure_stats = value

    def register_hook(self, synchronize=True):
        """
        Decorator to register hook functions for this message processor.

        Args:
            synchronize (bool): Enables thread synchronization for entire hook function.
        """

        def decorator(func):
            ret_func = func

            # Wrap in synchronizer if requested
            if synchronize:
                ret_func = self._synchronize_wrapper(self._hook_lock, func)

            # Add function to hook registry
            name = func.__name__
            self._hook_funcs[name] = ret_func

            if log.isEnabledFor(logging.DEBUG):
                log.debug("Registered hook function '%s'", name)

            return ret_func

        return decorator

    def add_hook(self, name, kind, func, synchronize=True):
        """
        Add hook function manually to this message processor.
        """

        # Wrap in synchronizer if requested
        if synchronize:
            func = self._synchronize_wrapper(self._hook_lock, func)

        self._hook_funcs["{:}_{:}".format(name, kind)] = func

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
            threads = self.worker_threads.do_all_for(settings["dequeue"],
                lambda t: t.context["messages"].remove(message))

            return {
                "dequeued": [t.name for t in threads]
            }

        # Check if we need to enqueue message to an existing worker thread
        if "enqueue" in settings:
            threads = self.worker_threads.do_all_for(settings["enqueue"],
                lambda t: t.context["messages"].append(message))

            return {
                "enqueued": [t.name for t in threads]
            }

        # Exceptions will NOT kill worker thread as default behavior
        suppress_exceptions = settings.pop("suppress_exceptions", True)

        # Terminates worker thread after a successful run without warnings nor exceptions
        kill_upon_success = settings.pop("kill_upon_success", False)

        # Perform entire job iteration transactionally
        transactional = settings.pop("transactional", False)

        # Prepare function that performs actual work
        def do_work(thread, context):
            success = True

            # Loop through all messages found in thread context
            for message in list(context["messages"]):  # Copy list to allow changes while looping
                try:

                    # Run workflow
                    self._call_hook_for(message, "workflow", message)

                except Warning as wa:
                    success = False

                    # Register time of last warning in context
                    context["last_warning"] = datetime.datetime.utcnow().isoformat()

                    # Also register all distinct warning messages in context
                    msg = str(wa)
                    context.setdefault("distinct_warnings", {}).setdefault(msg, 0)
                    context["distinct_warnings"][msg] += 1

                    # Only allow recurring warnings to be logged every minute
                    if context["distinct_warnings"][msg] > 3 \
                        and timer() - getattr(thread, "warning_log_timer", 0) < 60:
                        return
                    setattr(thread, "warning_log_timer", timer())

                    # Go ahead and log the warning
                    if context["distinct_warnings"][msg] > 1:
                        log.info("Recurring warning ({:} times) in worker thread '{:}': {:}".format(context["distinct_warnings"][msg], thread.name, wa))
                    else:
                        log.info("Warning in worker thread '{:}': {:}".format(thread.name, wa))

                except Exception as ex:
                    success = False

                    # Register time of last error in context
                    context["last_error"] = datetime.datetime.utcnow().isoformat()

                    # Also register all distinct error messages in context
                    msg = str(ex)
                    context.setdefault("distinct_errors", {}).setdefault(msg, 0)
                    context["distinct_errors"][msg] += 1

                    # Only allow recurring exceptions to be logged every minute
                    if suppress_exceptions and context["distinct_errors"][msg] > 3 \
                        and timer() - getattr(thread, "exception_log_timer", 0) < 60:
                        return
                    setattr(thread, "exception_log_timer", timer())

                    # Go ahead and log the exception
                    if context["distinct_errors"][msg] > 1:
                        log.exception("Recurring exception ({:} times) in worker thread '{:}' while running workflow for message: {:}".format(context["distinct_errors"][msg], thread.name, message))
                    else:
                        log.exception("Exception in worker thread '{:}' while running workflow for message: {:}".format(thread.name, message))

                    # Finally suppress or propagate the exception
                    if suppress_exceptions:
                        if transactional:
                            log.info("Suppressing prior exception in worker thread '{:}' and skips any following work".format(thread.name))

                            break
                        else:
                            log.info("Suppressing prior exception in worker thread '{:}' and continues as normal".format(thread.name))
                    else:
                        raise

            # Clear any warnings and errors on success
            if success:
                context.pop("distinct_warnings", None)
                context.pop("distinct_errors", None)

            if kill_upon_success and success:
                thread.kill()

                if log.isEnabledFor(logging.DEBUG):
                    log.debug("Killed worker thread '{:}' upon successful run".format(thread.name))

        # Auto start is default
        auto_start = settings.pop("start", True)

        # Add new worker thread
        thread = threading_more.WorkerThread(
            target=self._synchronize_wrapper(self._hook_lock, do_work) if transactional else do_work,
            context={"messages": [message] if message else []},
            registry=self.worker_threads,  # Registers thread in registry
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

            <handler> --> [trigger] --> [filter] --> [returner]
        """

        args = message.get("args", [])
        kwargs = message.get("kwargs", {})

        try:

            # Call handler hook
            _, result = self._call_hook_for(message, "handler", *args, **kwargs)

        except Exception as ex:
            result = ex

            raise

        finally:

            # Always call trigger, also on error or empty result
            try:
                self._call_hook_for(message, "trigger", result)
            except:
                log.exception("Error in simple workflow when calling trigger for message: {:}".format(message))

        # Call filter hook if there is a result
        if result:
            found, filtered_result = self._call_hook_for(message, "filter", result)
            if found:
                result = filtered_result

        # Call returner hook if there is a result
        if result:
            self._call_hook_for(message, "returner", message, result)

        return result

    def extended_workflow(self, message):
        """
        Extended message processing flow and available hooks:

            [validator] --> <handler> --> [converter] --> [trigger] --> [filter] --> [enricher] --> [retuner]
        """

        args = message.get("args", [])
        kwargs = message.get("kwargs", {})

        # Call validator hook
        found, error = self._call_hook_for(message, "validator", *args, **kwargs)
        if found and error:
            raise Exception(error)

        try:

            # Call handler hook
            _, result = self._call_hook_for(message, "handler", *args, **kwargs)

            # Call converter hook if there is a result
            if result:
                found, converted_result = self._call_hook_for(message, "converter", result)
                if found:
                    result = converted_result

        except Exception as ex:
            result = ex

            raise

        finally:

            # Always call trigger, also on error or empty result
            try:
                self._call_hook_for(message, "trigger", result)
            except:
                log.exception("Error in extended workflow when calling trigger for message: {:}".format(message))

        # Call filter hook if there is a result
        if result:
            found, filtered_result = self._call_hook_for(message, "filter", result)
            if found:
                result = filtered_result

        # Call enricher hook if there is a result
        if result:
            found, enriched_result = self._call_hook_for(message, "enricher", result)
            if found:
                result = enriched_result

        # Call returner hook if there is a result
        if result:
            self._call_hook_for(message, "returner", message, result)

        return result

    def manage_workflow(self, message):
        """
        Administration workflow to query and manage this processor instance.

        Supported commands:
            - <hook> <list|call> [name]
            - <worker> <list|show|create|start|kill> [name|*]
            - <run>
        """

        args = message.get("args", [])
        kwargs = message.get("kwargs", {})

        if len(args) > 1 and args[0] == "hook":
            if args[1] == "list":
                return {
                    "values": [h for h in self._hook_funcs]
                }

            elif args[1] == "call" and len(args) > 3:
                return self._get_func(args[2])(*args[3:], **kwargs)

        elif len(args) > 1 and args[0] == "worker":
            if args[1] == "list":
                return {
                    "values": [
                        t.name for t in self.worker_threads.find_all_by(args[2] \
                            if len(args) > 2 else "*")
                    ]
                }

            elif args[1] == "show":
                threads = self.worker_threads.find_all_by(args[2] if len(args) > 2 else "*")
                return {
                    "value": {t.name: t.context for t in threads}
                }

            elif args[1] == "create":
                return self.dedicated_worker(None, **kwargs)

            elif args[1] == "start":
                threads = self.worker_threads.do_all_for(args[2], lambda t: t.start())
                return {
                    "values": [t.name for t in threads]
                }

            elif args[1] == "pause":
                threads = self.worker_threads.do_all_for(args[2], lambda t: t.pause())
                return {
                    "values": [t.name for t in threads]
                }

            elif args[1] == "resume":
                threads = self.worker_threads.do_all_for(args[2], lambda t: t.resume())
                return {
                    "values": [t.name for t in threads]
                }

            elif args[1] == "kill":
                threads = self.worker_threads.do_all_for(args[2], lambda t: t.kill())
                return {
                    "values": [t.name for t in threads]
                }

        elif len(args) > 0 and args[0] == "run":
            msg = kwargs
            return self.process(msg)

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

        # Wrap hook function in order to measure statistics
        if self._measure_stats:
            func = self._stats_wrapper_for(message, kind, func)

        if parse_settings:
            return (func, settings)
        else:
            return func

    def _stats_wrapper_for(self, message, kind, func):
        def stats_wrapper(*args, **kwargs):
            start = timer()

            try:
                return func(*args, **kwargs)
            finally:
                duration = timer() - start

                stats = message.setdefault("_stats", {}).setdefault(kind, {
                    "duration": {
                        "acc": 0.0,
                        "avg": 0.0,
                        "min": -1.0,
                        "max": -1.0
                    },
                    "count": 0
                })
                stats["count"] += 1
                stats["duration"]["acc"] += duration
                stats["duration"]["avg"] = stats["duration"]["acc"] / stats["count"]
                if duration < stats["duration"]["min"] or stats["duration"]["min"] < 0:
                    stats["duration"]["min"] = duration
                if duration > stats["duration"]["max"]:
                    stats["duration"]["max"] = duration

        return stats_wrapper

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

    def _synchronize_wrapper(self, lock, func):
        def synchronizer(*args, **kwargs):
            with lock:
                return func(*args, **kwargs)

        return synchronizer

    #endregion


class EventDrivenMessageProcessor(MessageProcessor):

    def __init__(self, namespace, default_hooks={}):
        MessageProcessor.__init__(self, default_hooks)
        self._namespace = namespace
        self._tag_regex = re.compile("^{:s}/req/(?P<id>.+)$".format(namespace))
        self._event_matchers = []
        self._bus_lock = threading.RLock()  # Used to synchronize event bus function calls
        self._outgoing_event_filters = {}

    def init(self, __salt__, __opts__, hooks=[], workers=[]):
        """
        Initialize this instance.
        """

        # Dedicated event bus handle for receiving events
        self._incoming_bus = salt.utils.event.get_event("minion",
            opts=__opts__,
            transport=__opts__["transport"],
            listen=True)

        # Dedicated event bus handle for sending events
        self._outgoing_bus = salt.utils.event.get_event("minion",
            opts=__opts__,
            transport=__opts__["transport"],
            listen=False)

        # Register matcher for event processor
        self.register_event_matcher(
            self._tag_regex.pattern,
            self.process_event,
            match_type="regex")

        # Add specified workflow hooks
        for hook in hooks or []:
            try:

                # Special handling of returners
                if hook["kind"] == "returner":

                    # Load Salt returner function
                    returners = salt.loader.returners(__opts__, __salt__)  # TODO: This can be cached
                    returner_func = returners[hook["func"]]

                    # Wrap returner function to add defined args and kwargs
                    def returner_wrapper(message, result, hook=hook, returner_func=returner_func):

                        # Skip empty results
                        if not result:
                            return

                        args = hook.get("args", [])
                        kwargs = hook.get("kwargs", {})

                        # Automatically set namespace as kind for data results
                        if not args and returner_func.__name__ == "returner_data":
                            args.append(self._namespace)

                        return returner_func(result, *args, **kwargs)

                    self.add_hook(hook["name"], hook["kind"], returner_wrapper, synchronize=hook.get("lock", False))

                else:
                    self.add_hook(hook["name"], hook["kind"], __salt__[hook["func"]], synchronize=hook.get("lock", False))

            except Exception:
                log.exception("Failed to add hook: {:}".format(hook))

        # Add specified workers
        for worker in workers or []:
            messages = worker.pop("messages")

            self.dedicated_worker(None, start=False, **worker)

            # Enqueue all messages to worker
            for message in messages:
                self.dedicated_worker(message, enqueue=worker["name"])

    def _custom_match_tag_regex(self, event_tag, search_tag):
        return self._incoming_bus.cache_regex.get(search_tag).search(event_tag)

    def register_event_matcher(self, tag, func, match_type="startswith"):
        """
        Register additional event matchers to catch other events.
        """

        em = {
            "tag": tag,
            "match_type": match_type,
            "match_func": self._custom_match_tag_regex if match_type == "regex" else self._incoming_bus._get_match_func(match_type),
            "func": func,
        }
        self._event_matchers.append(em)

    def run(self):
        """
        Blocking method that processes all received events.
        """

        # Ensure all worker threads are started
        threads = self.worker_threads.do_all_for("*", lambda t: t.start(), force_wildcard=True)
        if threads:
            log.info("Starting {:d} worker thread(s): {:s}".format(len(threads), ", ".join([t.name for t in threads])))

        # Listen for incoming messages
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Listening for incoming events using %d registered event matcher(s)", len(self._event_matchers))

        try:
            for event in self._incoming_bus.iter_events(full=True, auto_reconnect=True):
                if not event:
                    log.warn("Skipping empty event")
                    continue

                try:
                    for matcher in self._event_matchers:
                        match = matcher["match_func"](event["tag"], matcher["tag"]) 
                        if not match:
                            continue

                        if log.isEnabledFor(logging.DEBUG):
                            log.debug("Matched event: %s", repr(event))

                        matcher["func"](event, match=match)

                except Exception:
                    log.exception("Failed to process received event: {:}".format(event))
        finally:

            # Ensure all worker threads are killed
            threads = self.worker_threads.do_all_for("*", lambda t: t.kill(), force_wildcard=True)
            if threads:
                log.info("Killing all worker thread(s): {:s}".format(", ".join([t.name for t in threads])))

    def process_event(self, event, **kwargs):
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

    def trigger_event(self, data, tag, skip_duplicates_filter=None):
        """
        Trigger an outgoing event.
        """

        # Check for duplicates to skip
        if skip_duplicates_filter != None:
            skip_duplicates_filter = "dupl:{:}".format(skip_duplicates_filter)
            if (tag, data) == self._outgoing_event_filters.get(skip_duplicates_filter, None):
                if log.isEnabledFor(logging.DEBUG):
                    log.debug("Skipping duplicate event with tag '{:s}': {:}".format(tag, data))

                return

        log.info("Triggering event with tag '{:s}': {:}".format(tag, data))

        with self._bus_lock:  # Synchronize just to be safe
            self._outgoing_bus.fire_event(data.copy(), tag)

            # Register last event for duplicate filter
            if skip_duplicates_filter != None:
                self._outgoing_event_filters[skip_duplicates_filter] = (tag, data)


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

        if log.isEnabledFor(logging.DEBUG):
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

        correlation_id = uuid.uuid4()

        # Spawn separate thread to receive reply
        recv_thread = threading_more.ReturnThread(target=self.recv_reply, args=(correlation_id, timeout))
        recv_thread.start()

        # Send the request message
        self.send_async(correlation_id, message)

        # Wait for reply
        reply = recv_thread.join()
        if reply == None:

            # Check for exception
            if recv_thread.exception:
                raise recv_thread.exception

        return reply

    def send_async(self, correlation_id, message):

        # Send message on bus
        tag = "{:s}/req/{:s}".format(self._namespace, correlation_id)

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Sending request message with tag '%s': %s", tag, message)

        self._outgoing_bus.fire_event(message, tag)

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
            if isinstance(message["error"], dict):
                raise SuperiorCommandExecutionError(str(message["error"]), data=message["error"])
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
        res = {}
        for key, val in data.iteritems():
            res[keyword_resolve(key, keywords)] = keyword_resolve(val, keywords)
        data = res

    elif isinstance(data, basestring) and symbol in data:

        # Replace keywords in data
        for key in keywords:
            data = data.replace("{:s}{:s}".format(symbol, key), "__{:s}__".format(key))

        return eval(data, {"__{:s}__".format(key): val for key, val in keywords.iteritems()})

    return data


def extract_error_from(result):
    """
    Helper function to extract error from a result.
    """

    if not result:
        log.error("Cannot attempt to extract error from an empty result: {:}".format(result))

        return

    return result if isinstance(result, Exception) else result.get("error", None) if isinstance(result, dict) else result


def filter_out_unchanged(result, context={}, kind=None):
    """
    Helper function to filter out unchanged results recursively based on their specified types.
    """

    # Build qualified type string for the result
    kind = ".".join(filter(None, [kind, result.get("_type", None)]))

    # Loop through all keys in the result and build entry with the significant alternating values
    entry = {}
    for key, val in result.iteritems():

        # Skip all meta/hidden
        if key.startswith("_"):
            continue

        # Dive into list in an attempt to filter it
        if isinstance(val, list):

            vals = []
            for res in val:

                # Recursive handling of dictionary values
                if isinstance(res, dict):
                    sub_res = filter_out_unchanged(res, context=context, kind=kind)
                    if sub_res:
                        vals.append(sub_res)

                # Special handling of primitive values - they are always added
                else:
                    vals.append(res)

                    # Ensure primitive values are also added to entry
                    entry[key] = vals

            # Set filtered values on result
            result[key] = vals

        # Ordinary primitive or dictionary value
        else:
            entry[key] = val

    # Do we have a type and an entry with one or more significant alternating values?
    if kind and entry:

        # Compare if entry equals content cached in context
        if context.get(kind, None) == entry:

            # Skip entry when equal to cached
            return

        # Otherwise update cache with recent content
        else:
            context[kind] = entry

    return result

