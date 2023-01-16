import battery_util
import dateutil.parser
import logging
import re

from messaging import extract_error_from, filter_out_unchanged, keyword_resolve
from salt_more import cached_loader
from timeit import default_timer as timer
from geofence_util import read_geofence_file, is_in_circle, is_in_polygon

log = logging.getLogger(__name__)
DEBUG = log.isEnabledFor(logging.DEBUG)

def echo_handler(*args, **kwargs):
    """
    Mainly for testing.
    """

    log.info("Echo: {:}".format(args))


def module_handler(*args, **kwargs):
    """
    Calls a Salt execution module from within the minion process.
    """

    # Resolve keyword arguments if available
    if kwargs.pop("_keyword_resolve", False):
        kwargs = keyword_resolve(kwargs, keywords={"context": context, "options": __opts__})
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Keyword resolved arguments: {:}".format(kwargs))

    kind = kwargs.pop("_type", None)

    ret = __salt__["minionutil.run_job"](args[0], *args[1:], **kwargs)

    if kind != None and isinstance(ret, dict):
        ret["_type"] = kind

    return ret


def module_direct_handler(*args, **kwargs):
    """
    Calls a Salt execution module directy from current process.
    """

    # Resolve keyword arguments if available
    if kwargs.pop("_keyword_resolve", False):
        kwargs = keyword_resolve(kwargs, keywords={"context": context, "options": __opts__})
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Keyword resolved arguments: {:}".format(kwargs))

    kind = kwargs.pop("_type", None)

    ret = __salt__[args[0]](*args[1:], **kwargs)

    if kind != None and isinstance(ret, dict):
        ret["_type"] = kind

    return ret


def returner_call_handler(name, *args, **kwargs):
    """
    Calls a Salt returner module directy from current process.
    """

    ret = cached_loader(__salt__, __opts__, "returners", context=__context__)[name](*args, **kwargs)
    if ret == None:
        ret = {}

    return ret


def skip_empty_filter(result):
    """
    Filters out empty results.
    """

    if not result:
        return

    if isinstance(result, dict):
        if not [v for k, v in result.iteritems() if not k.startswith("_") and v]:
            return

    return result


def alternating_readout_filter(result):
    """
    Filter that only returns alternating/changed results.
    """

    return filter_out_unchanged(result, context=__context__.setdefault("readout", {}))


def battery_converter(result):
    """
    Converts a voltage reading result with battery charge state and level.
    """

    voltage = result.get("value", None)

    opt = __opts__.get("battery", {})
    nominal_voltage = opt.get("nominal_voltage", battery_util.DEFAULT_NOMINAL_VOLTAGE)
    critical_limit = opt.get("critical_level", {}).get("voltage", battery_util.DEFAULT_CRITICAL_LIMIT)

    ret = {
        "_type": "bat",
        "level": battery_util.charge_percentage_for(voltage, nominal_voltage),
        "state": battery_util.state_for(voltage, nominal_voltage, critical_limit),
        "voltage": voltage
    }

    return ret


def battery_event_trigger(result):
    """
    Looks for battery results and triggers 'vehicle/battery/*' event when voltage changes.
    """

    # Check for error result
    error = extract_error_from(result)
    if error:
        log.error("Battery event trigger got error result: {:}".format(result))

        state = "unknown"
    else:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Battery event trigger got battery result: {:}".format(result))

        state = result["state"]

    # Check if state has chaged since last time
    ctx = __context__.setdefault("hooklib.battery_event_trigger", {})
    if not ctx or state != ctx.get("state", None):
        ctx["state"] = state
        ctx["data"] = None
        ctx["timer"] = timer()
        ctx["count"] = 1
    else:
        ctx["count"] += 1

    event_thresholds = ctx.setdefault("event_thresholds", {})
    if not event_thresholds:
        event_thresholds["*"] = 3  # Default is three seconds
        event_thresholds["unknown"] = 0
        event_thresholds[battery_util.CRITICAL_LEVEL_STATE] = __opts__.get("battery", {}).get("critical_level", {}).get("duration", 180)

    # Proceed only when battery state is repeated at least once and timer threshold is reached
    if ctx["count"] > 1 and timer() - ctx["timer"] >= event_thresholds.get(state, event_thresholds["*"]):

        # Reset timer
        ctx["timer"] = timer()

        # Prepare event data
        data = {}
        if state in [battery_util.DISCHARGING_STATE, battery_util.CRITICAL_LEVEL_STATE]:
            data["level"] = result["level"]
        elif state == "unknown" and error:
            data["reason"] = str(error)

        # Trigger only event if level (in data) has changed
        if data != ctx["data"]:
            __salt__["minionutil.trigger_event"]("vehicle/battery/{:s}".format(state), data)

            ctx["data"] = data


def temperature_event_trigger(result):
    """
    Looks for temperature results and triggers 'system/temperature/*' event when temperature changes.
    """

    # Check for error result
    error = extract_error_from(result)
    if error:
        log.error("Temperature event trigger got error result: {:}".format(result))

        state = "unknown"
    else:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Temperature event trigger got temperature result: {:}".format(result))

        if "value" in result:
            if result["value"] < 0:
                state = "freezing"
            elif result["value"] <= 25:
                state = "cold"
            elif result["value"] <= 65:
                state = "warm"
            elif result["value"] <= 90:
                state = "hot"
            else:
                state = "overheating"
        else:
            log.warning("Temperature event trigger did not find any temperature value in result: {:}".format(result))

            state = "unknown"

    # Check if state has chaged since last time
    ctx = __context__.setdefault("hooklib.temperature_event_trigger", {})
    if not ctx or state != ctx.get("state", None):
        ctx["state"] = state
        ctx["is_sent"] = False
        ctx["timer"] = timer()
        ctx["count"] = 1
    else:
        ctx["count"] += 1

    if not ctx["is_sent"]:
        event_thresholds = ctx.setdefault("event_thresholds", {})
        if not event_thresholds:
            event_thresholds["*"] = 10  # Default is ten seconds
            event_thresholds["unknown"] = 0

        # Proceed only when the temperature state is repeated at least once and the timer threshold is reached
        if ctx["count"] > 1 and timer() - ctx["timer"] >= event_thresholds.get(state, event_thresholds["*"]):

            # Prepare event data
            data = {}
            if state == "unknown" and error:
                data["reason"] = str(error)

            __salt__["minionutil.trigger_event"]("system/temperature/{:s}".format(state), data)
            
            ctx["is_sent"] = True


def kernel_error_blacklist_filter(result):
    """
    Filters out blacklisted kernel errors.
    """

    if not result:
        return

    # Get blacklist from configuration file
    pattern = "|".join(__opts__.get("kernel_error_blacklist", []))
    if not pattern:
        return result

    ret = []

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Compiling regex for pattern: {:}".format(pattern))

    regex = re.compile(pattern)

    for entry in result:
        if regex.match(entry.get("message", "")):

            if log.isEnabledFor(logging.DEBUG):
                log.debug("Skipping blacklisted kernel error log entry: {:}".format(entry))

            continue

        ret.append(entry)

    return ret


def kernel_error_event_trigger(result):
    """
    Triggers 'system/kernel/error' events.
    """

    # First filter out blacklisted entries
    entries = kernel_error_blacklist_filter(result)

    if not entries:
        return

    ctx = __context__.setdefault("hooklib.kernel_error_event_trigger", {})

    for entry in entries:

        last = ctx.get("last_recorded", {})
        ctx["last_recorded"] = entry

        # Only report when message changes (to avoid duplicates)
        if entry["message"] == last.get("message", None):
            span = dateutil.parser.parse(entry["timestamp"]) - dateutil.parser.parse(last["timestamp"])
            if span.total_seconds() < 60:

                if log.isEnabledFor(logging.DEBUG):
                    log.debug("Skipping duplicate kernel error log entry ({:} seconds since the last occurrence): {:}".format(span.total_seconds(), entry))

                continue

        # Trigger kernel error event
        __salt__["minionutil.trigger_event"]("system/kernel/error", data=entry)

        # Store last reported entry
        ctx["last_reported"] = entry


def getOrCreateGeofenceInContext(ctx):
    if not ctx.get("geofence"):
        if DEBUG:
            log.debug("Creating Geofence context")

        ctx["geofence"] = {   
            "error": None,
            "repeat_count_to_trigger_change": 3,
            "fences": [],
            "loaded": False
        }

    return ctx["geofence"]


def geofence_event_trigger(result):
    """
    Listens for position results and triggers geofence inside/outside and enter/exit events
    inside/outside - triggered on startup
    enter/exit - triggered during driving
    Change happens when the same result is repeated [repeat_count_to_trigger_change] times
    """

    if isinstance(result, Exception):
        if DEBUG:
            log.debug("No data from GPS, can not determine geofence status. Exception: {}".format(result))
        return
    
    ctx = getOrCreateGeofenceInContext(__context__)
    if not ctx["loaded"]:
        load_geofences_handler()

    # Check if the vehicle has entered/exited of any of the geofences
    current_location = result["loc"]

    for fence in ctx["fences"]:
        if DEBUG:
            log.debug("Checking geofence {} ({})".format(fence["id"], fence["name"]))

        # Check if vehicle is inside or outside given geofence
        if (fence["shape"] == "SHAPE_CIRCLE"  and is_in_circle(current_location, fence["coordinates"][0], fence["circle_radius"] / 1000) or
            fence["shape"] == "SHAPE_POLYGON" and is_in_polygon(current_location, fence["coordinates"])):
            fresh_state = "inside"
        else:
            fresh_state = "outside"

        # Handle GF states/events after first acquiring GPS signal  
        if fence["state"] == None:
            fence["state"] = fresh_state
            __salt__["minionutil.trigger_event"]("vehicle/geofence/{:s}/{:s}".format(fence["slug"], fence["state"]), {"fence_id": fence["id"]})

        # Update or reset repeat counter
        elif fence["last_reading"] == fresh_state:
            fence["repeat_count"] += 1

            # Trigger event and update fence state if repeat count has been reached
            if (fence["repeat_count"] >= ctx["repeat_count_to_trigger_change"] and
                fence["state"] != fresh_state):
    
                if DEBUG:
                    log.debug("Changing state for geofence {} ({}) to {}".format(fence["id"], fence["name"], fresh_state))

                fence["state"] = fresh_state
                
                if fence["state"] == "inside":
                    __salt__["minionutil.trigger_event"]("vehicle/geofence/{:s}/{:s}".format(fence["slug"], "enter"), {"fence_id": fence["id"]})
                else:
                    __salt__["minionutil.trigger_event"]("vehicle/geofence/{:s}/{:s}".format(fence["slug"], "exit"), {"fence_id": fence["id"]})

        else: 
            fence["last_reading"] = fresh_state
            fence["repeat_count"] = 0


def load_geofences_handler(path="/opt/autopi/geofence/settings.yaml"):
    """
    Loads geofence file
    """
    log.info("Loading geofence settings from {}".format(path))

    ctx = getOrCreateGeofenceInContext(__context__)

    ctx["fences"] = read_geofence_file(path)
    ctx["error"] = None 
    ctx["loaded"] = True

    return {}
