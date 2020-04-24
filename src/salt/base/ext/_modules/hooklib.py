import logging

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

    for entry in result:

        # Reuse timestamp for event
        entry["_stamp"] = entry.get("timestamp")

        __salt__["event.fire"](entry, "system/kernel/error")