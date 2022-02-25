import battery_util
import dateutil.parser
import logging
import re

from messaging import extract_error_from, filter_out_unchanged, keyword_resolve
from salt_more import cached_loader
from timeit import default_timer as timer


log = logging.getLogger(__name__)


def echo_handler(*args, **kwargs):
    """
    Mainly for testing.
    """

    log.info("Echo: {:}".format(args))


def module_handler(name, *args, **kwargs):
    """
    Calls a Salt execution module from within the minion process.
    """

    # Resolve keyword arguments if available
    if kwargs.pop("_keyword_resolve", False):
        kwargs = keyword_resolve(kwargs, keywords={"context": context, "options": __opts__})
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Keyword resolved arguments: {:}".format(kwargs))

    kind = kwargs.pop("_type", None)

    ret = __salt__["minionutil.run_job"](name, *args, **kwargs)

    if kind != None and isinstance(ret, dict):
        ret["_type"] = kind

    return ret


def module_direct_handler(name, *args, **kwargs):
    """
    Calls a Salt execution module directy from current process.
    """

    # Resolve keyword arguments if available
    if kwargs.pop("_keyword_resolve", False):
        kwargs = keyword_resolve(kwargs, keywords={"context": context, "options": __opts__})
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Keyword resolved arguments: {:}".format(kwargs))

    kind = kwargs.pop("_type", None)

    ret = __salt__[name](*args, **kwargs)

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
    critical_limit = opt.get("critical_limit", {}).get("voltage", battery_util.DEFAULT_CRITICAL_LIMIT)

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
        event_thresholds[battery_util.CRITICAL_LEVEL_STATE] = __opts__.get("battery", {}).get("critical_limit", {}).get("duration", 180)

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
