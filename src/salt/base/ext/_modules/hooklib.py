import battery_util
import datetime
import dateutil.parser
import logging
import re

from common_util import dict_filter, dict_get
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
        if DEBUG:
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
        if DEBUG:
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


def context_cache_handler(key=None, root_key="cache", compare_data="*", **data):
    """
    Manages cached data in the context.
    """

    # Validate input
    if key == None and data:
        raise ValueError("A key must be given to identify cache data")

    ret = {}

    ctx = __context__.setdefault(root_key, {})

    # List all cached items if not key is specified
    if key == None:
        ret["values"] = ctx

        return ret

    # Return cached entry for key if not data is specified
    if not data:
        ret["value"] = ctx.get(key, {})

        return ret

    # Determine if the data has changed depending on what to compare
    has_data_changed = False
    if key in ctx and compare_data:
        if compare_data == "*":
            old_data = dict_filter(ctx[key], lambda k: not k.startswith("_"))
            new_data = dict_filter(data, lambda k: not k.startswith("_"))
        else:
            old_data = dict_get(ctx[key], *compare_data.split(":"))
            new_data = dict_get(data, *compare_data.split(":"))

        if DEBUG:
            log.debug("Comparing old data '{:}' with new data '{:}' in context cache for key '{:}'".format(old_data, new_data, key))

        has_data_changed = old_data != new_data

    # Go ahead and update the cache
    if not key in ctx or has_data_changed:
        data["_count"] = 1
        data["_first_at"] = datetime.datetime.utcnow()
        data["_last_at"] = datetime.datetime.utcnow()
        ctx[key] = data

        if DEBUG:
            log.debug("Inserted key '{:}' into context cache: {:}".format(key, data))

        ret["value"] = data

    else:
        data["_count"] = ctx[key]["_count"] + 1
        data["_first_at"] = ctx[key]["_first_at"]
        data["_last_at"] = datetime.datetime.utcnow()
        ctx[key] = data

        if DEBUG:
            log.debug("Updated key '{:}' in context cache: {:}".format(key, data))

        ret["value"] = data

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

def alternating_readout_filter(result, **kwargs):
    """
    Filter that only returns alternating/changed results.

    Optional arguments:
      - pass_interval (int): Filter passes values only when this many miliseconds have passed between readings, even when the values are different. Default value is '0'.
    """
    return filter_out_unchanged(result, context=__context__.setdefault("readout", {}), **kwargs)

def battery_converter(result, nominal_voltage_divider=20):
    """
    Converts a voltage reading result with battery charge state and level.
    """

    voltage = result.get("value", None)

    opt = __opts__.get("battery", {})
    nominal_voltage = opt.get("nominal_voltage", battery_util.DEFAULT_NOMINAL_VOLTAGE)
    critical_limit = opt.get("critical_level", {}).get("voltage", battery_util.DEFAULT_CRITICAL_LIMIT)

    # Autodetect the nominal voltage based on the current voltage
    is_nominal_voltage_autodetected = False
    if not nominal_voltage or nominal_voltage == "autodetect":
        is_nominal_voltage_autodetected = True

        if voltage < nominal_voltage_divider:
            nominal_voltage = 12
            if DEBUG:
                log.debug("Battery converter has autodetected a nominal voltage of 12V")

            # Adjust critical limit if out of range
            if critical_limit >= nominal_voltage_divider:
                if DEBUG:
                    log.debug("Battery converter is adjusting down the configured critical limit from {}V to {}V".format(critical_limit, critical_limit / 2))
                critical_limit = critical_limit / 2
        else:
            nominal_voltage = 24
            if DEBUG:
                log.debug("Battery converter has autodetected a nominal voltage of 24V")

            # Adjust critical limit if out of range
            if critical_limit < nominal_voltage_divider:
                if DEBUG:
                    log.debug("Battery converter is adjusting up the configured critical limit from {}V to {}V".format(critical_limit, critical_limit * 2))
                critical_limit = critical_limit * 2

    ret = {
        "_type": "bat",
        "level": battery_util.charge_percentage_for(voltage, nominal_voltage),
        "state": battery_util.state_for(voltage, nominal_voltage, critical_limit),
        "voltage": voltage,
        "nominal_voltage": nominal_voltage,
        "is_nominal_voltage_autodetected": is_nominal_voltage_autodetected
    }

    return ret


def battery_nominal_voltage_event_trigger(result, autodetect_period=10):
    """
    Looks for battery results and triggers 'vehicle/battery/nominal_voltage/*' event when the nominal voltage state changes.
    All possible events are:
      - vehicle/battery/nominal_voltage/unknown
      - vehicle/battery/nominal_voltage/autodetected
      - vehicle/battery/nominal_voltage/predefined
    """

    data = {}

    # Check for error result
    error = extract_error_from(result)
    if error:
        log.error("Battery nominal voltage event trigger got error result: {:}".format(result))

        state = "unknown"
        data["reason"] = str(error)
    else:
        if DEBUG:
            log.debug("Battery nominal voltage event trigger got battery result: {:}".format(result))

        if not "nominal_voltage" in result or not "is_nominal_voltage_autodetected" in result:
            state = "unknown"
            reason = "nominal_voltage_absent"
        elif result["is_nominal_voltage_autodetected"]:
            state = "autodetected"
            data["value"] = result["nominal_voltage"]
        else:
            state = "predefined"
            data["value"] = result["nominal_voltage"]

   # Check if state or data has chaged since last time
    ctx = __context__.setdefault("hooklib.battery_nominal_voltage_event_trigger", {})
    if not ctx or state != ctx.get("state", None) or data != ctx.get("data", None):
        ctx["state"] = state
        ctx["data"] = data
        ctx["timer"] = timer()
        ctx["count"] = 1
        ctx["is_sent"] = False
    else:
        ctx["count"] += 1

    # Skip if already sent
    if ctx["is_sent"]:
        return

    # Skip if state is 'autodetected' and period not reached
    if state == "autodetected" and (ctx["count"] == 1 or timer() - ctx["timer"] < autodetect_period):
        return

    # Trigger event
    __salt__["minionutil.trigger_event"]("vehicle/battery/nominal_voltage/{}".format(state), data=dict(data, **{"_alternating_cache_event_filter.skip": True}))

    ctx["is_sent"] = True


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
        if DEBUG:
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
        if DEBUG:
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

    if DEBUG:
        log.debug("Compiling regex for pattern: {:}".format(pattern))

    regex = re.compile(pattern)

    for entry in result:
        if regex.match(entry.get("message", "")):

            if DEBUG:
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

                if DEBUG:
                    log.debug("Skipping duplicate kernel error log entry ({:} seconds since the last occurrence): {:}".format(span.total_seconds(), entry))

                continue

        # Trigger kernel error event
        __salt__["minionutil.trigger_event"]("system/kernel/error", data=dict(entry, **{"_alternating_cache_event_filter.skip": True}))

        # Store last reported entry
        ctx["last_reported"] = entry


def getOrCreateGeofenceInContext(ctx):
    if not ctx.get("geofence"):
        if DEBUG:
            log.debug("Creating Geofence context")

        ctx["geofence"] = {   
            "error": None,
            "repeat_count_to_trigger_change": 1,
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
