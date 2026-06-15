import logging
import time

from common_util import dict_get, dict_find, dict_filter
from messaging import EventDrivenMessageProcessor, extract_error_from
from threading_more import intercept_exit_signal
from timeit import default_timer as timer


log = logging.getLogger(__name__)

DEBUG = log.isEnabledFor(logging.DEBUG)

context = {
    "cache.get": lambda *args, **kwargs: dict_get(context.get("cache", None), *args, **kwargs),
    "cache.find": lambda *args, **kwargs: dict_find(context.get("cache", {}).values(), *args, **kwargs),
    "result_cache.get": lambda *args, **kwargs: dict_get(context.get("result_cache", None), *args, **kwargs),
}

# Message processor
edmp = EventDrivenMessageProcessor("reactor", context=context, default_hooks={"workflow": "extended"})


@edmp.register_hook()
def module_result_cache_returner(message, result):
    """
    Stores/caches a module result in context.
    """

    if not message["handler"].startswith("module"):
        log.warn("Skipping result for unsupported handler '{:}': {:}".format(message["handler"], result))

        return

    ctx = context.setdefault("result_cache", {})
    cmd = message["args"][0]

    ctx[cmd] = result


@edmp.register_hook()
def cache_handler(key=None, **kwargs):
    """
    Manages cached data.
    """

    # Validate input
    if key == None and kwargs:
        raise ValueError("A key must be given to identify cache data")

    ret = {}

    ctx = context.setdefault("cache", {})

    # List all cached items if not key is specified
    if key == None:
        ret["values"] = ctx

        return ret

    # Return cached entry for key if not data is specified
    if not kwargs:
        ret["value"] = ctx.get(key, {})

        return ret

    # Go ahead and update cache
    if not key in ctx or \
        dict_filter(ctx[key], lambda k: not k.startswith("_")) != dict_filter(kwargs, lambda k: not k.startswith("_")):
        kwargs["_count"] = 1
        ctx[key] = kwargs

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Inserted into cache '{:}': {:}".format(key, kwargs))

        ret["value"] = kwargs

    else:
        kwargs["_count"] = ctx[key]["_count"] + 1
        ctx[key] = kwargs

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Updated cache '{:}': {:}".format(key, kwargs))

        ret["value"] = kwargs

    return ret


@edmp.register_hook(synchronize=False)
def passthrough_handler(result):
    if DEBUG:
        log.debug("Passthrough handler got result: {}".format(result))

    return result


@edmp.register_hook()
def composite_event_handler(name, source_key, tag="", data={}, allow_duplicates=True, match_count=1, detain_period=0):
    """
    Creates composite events that are based on other events.
    """

    if not tag:
        raise ValueError("A 'tag' value must be defined")

    ret = {}  # The composite event

    ctx = context.setdefault("composite_event_handler", {}).setdefault(name, {})

    # Update the source key map with the new tag
    source_key_map = ctx.setdefault("source_key_map", {})
    if tag != source_key_map.get(source_key, None):
        source_key_map[source_key] = tag

    # or skip if duplicates are not allowed
    elif not allow_duplicates:
        log.info("Composite event '{}' already has event tag '{}' registered for source key '{}'".format(name, tag, source_key))

        return ret

    # Check for matches of source key tags
    if match_count > 1 and match_count > len([t for t in source_key_map.values() if t == tag]):
        log.info("Composite event '{}' has fewer than required {} source keys with event tag matching '{}': {}".format(name, match_count, tag, source_key_map))

        return ret

    ret["name"] = name
    ret["type"] = "composite_event"
    ret["tag"] = tag
    ret["data"] = data
    
    # NOTE: Only to be used by the 'detained_composite_event_converter'
    if detain_period > 0:
        ret["detain_period"] = detain_period
        ret["detained_at"] = None

    # NOTE: Only to be used by the 'composite_event_trigger'
    ret["allow_duplicates"] = allow_duplicates
    ret["triggered_at"] = None

    ctx["last_event"] = ret

    return ret


@edmp.register_hook()
def detained_composite_event_converter(result, worker_name_format="_detained_composite_event/{}", worker_kill_timeout=30):
    """
    Ensures a worker thread is scheduled for events with a detain period specified.
    Only one scheduled worker thread can exist at a time.

    Example scenario 1:
      - (00:00:00) tag='vehicle/ignition/on', detain_period=0   -> The event is immediately passed on to the trigger
      - (00:00:01) tag='vehicle/ignition/off', detain_period=5  -> The trigger is scheduled to run in 5 seconds
      - (00:00:02) tag='vehicle/ignition/on', detain_period=0   -> The scheduled trigger is cancelled and the event is immediately passed on to the trigger

    Example scenario 2:
      - (00:00:00) tag='vehicle/ignition/off', detain_period=5  -> The trigger is scheduled to run in 5 seconds
      - (00:00:01) tag='vehicle/ignition/off', detain_period=5  -> The event is enqueued to the already scheduled trigger that will run in now 4 seconds

    Example scenario 3:
      - (00:00:00) tag='vehicle/ignition/on', detain_period=5   -> The trigger is scheduled to run in 5 seconds
      - (00:00:01) tag='vehicle/ignition/off', detain_period=5  -> The scheduled trigger is cancelled and and a new trigger is scheduled to run in 5 seconds
    """

    # Skip if empty result
    if not result:
        return

    # Validate the result type
    assert isinstance(result, dict) and result.get("type", None) == "composite_event", "The passed result must be a composite event"

    event_name = result["name"]

    # Get the last event from the context
    ctx = context.setdefault("detained_composite_event_converter", {}).setdefault(event_name, {})
    last_event = ctx.get("last_event", {})

    # Check if the tag has changed since the last time
    if last_event and last_event["tag"] != result["tag"]:

        # Ensure any existing worker with different tag is killed
        # NOTE: It may be completed we do not know for sure
        res = edmp.process({
            "workflow": "manage",
            "args": ["worker", "kill", worker_name_format.format(event_name)],
            "kwargs": {"join_timeout": worker_kill_timeout}  # Wait to make sure it is killed before creating a new
        })
        if res and res.get("values", []):
            log.info("Detained composite event converter killed existing worker for '{}' event".format(event_name))
        else:
            log.info("Detained composite event converter found no worker to kill for '{}' event".format(event_name))

    # Set as last event in the context
    ctx["last_event"] = result

    # Detain the event if required
    detain_period = result.get("detain_period", 0)
    if detain_period > 0:

        # Prepare the workflow to trigger the event
        workflow = {
            "handler": "passthrough",
            "args": [result],
            "trigger": "composite_event"
        }

        result["detained_at"] = timer()

        # Create or update the worker to run when the detain period has passed
        res = edmp.process({
            "workflow": "manage",
            "args": ["worker", "ensure_and_enqueue", workflow],
            "kwargs": {
                "name": worker_name_format.format(event_name),
                "auto_start": True,
                "kill_upon_success": True,
                "loop": 3,  # Three attempts
                "delay": detain_period
            }
        })
        log.info("Detained composite event converter ensured and enqueued worker for '{}' event: {}".format(event_name, res))

        # Omit passing on the event (to the event trigger)
        return

    # Pass on the composite event ready to be triggered immediately
    return result


@edmp.register_hook()
def composite_event_trigger(result):
    """
    Triggers a composite event and updates its triggered at timestamp.
    """

    # Skip if empty result
    if not result:
        return

    # Check for error result
    error = extract_error_from(result)
    if error:
        if DEBUG:
            log.debug("Composite event trigger got error result: {:}".format(result))

        return

    event_name = result["name"]
    ctx = context.setdefault("composite_event_trigger", {}).setdefault(event_name, {})

    # Check for duplicate to be skipped
    if not result.get("allow_duplicates", False):

        # Get the last event from the context
        last_event = ctx.get("last_event", {})
        if last_event and last_event["tag"] == result["tag"]:
            log.info("Composite event trigger is skipping duplicate for '{}' event: {}".format(event_name, result))

            result["triggered_at"] = -1
            ctx["last_event"] = result

            return

    # Trigger the event
    edmp.trigger_event(result["data"], result["tag"])

    if result.get("detained_at", 0):
        log.info("Triggered composite event for '{}' that was detained for {} second(s): {}".format(event_name, timer() - result["detained_at"], result))

    result["triggered_at"] = timer()
    ctx["last_event"] = result

 
@edmp.register_hook(synchronize=False)
def alternating_cache_event_filter(result):
    """
    Filter that only returns alternating/changed events from cache.
    """

    skip = result["value"]["event"].get("data", {}).pop("_alternating_cache_event_filter.skip", False)
    if not skip and result["value"]["_count"] != 1:
        return  # Considered unchanged

    # Considered changed
    return result["value"]["event"]


@intercept_exit_signal
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting event reactor with settings: {:}".format(settings))

        # Initialize and run message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        edmp.run()

    except Exception:
        log.exception("Failed to start event reactor")

        if settings.get("trigger_events", True):
            try:
                __salt__["minionutil.trigger_event"]("system/service/{:}/failed".format(__name__.split(".")[-1]), data={"reason": str(ex)})
            except:
                log.exception("Unable to trigger service failed event")

        restart_delay = settings.get("restart_delay", 1)
        if restart_delay:
            log.info("Enforcing restart delay of {:} second(s)...".format(restart_delay))
            time.sleep(restart_delay)

        raise

    finally:
        log.info("Stopping event reactor")
