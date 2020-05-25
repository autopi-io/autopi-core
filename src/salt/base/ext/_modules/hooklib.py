import logging
import dateutil.parser

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

    return __salt__["minionutil.run_job"](name, *args, **kwargs)


def module_direct_handler(name, *args, **kwargs):
    """
    Calls a Salt execution module directy from current process.
    """

    # Resolve keyword arguments if available
    if kwargs.pop("_keyword_resolve", False):
        kwargs = keyword_resolve(kwargs, keywords={"context": context, "options": __opts__})
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Keyword resolved arguments: {:}".format(kwargs))

    return __salt__[name](*args, **kwargs)


def kernel_error_event_trigger(result):
    """
    Triggers 'system/kernel/error' events
    """

    if not result:
        return

    ctx = __context__.setdefault("hooklib.kernel_error_event_trigger", {})

    for entry in result:

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
