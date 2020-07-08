import logging
import dateutil.parser
import re

from messaging import keyword_resolve


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
