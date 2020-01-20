import logging

from cloud_cache import NextCloudCache
from messaging import EventDrivenMessageProcessor


log = logging.getLogger(__name__)

context = {
    "upload": {
        "count": 0,
        "complete": {},
    }
}

# Message processor
edmp = EventDrivenMessageProcessor("cloud", context=context)

cache = NextCloudCache()


@edmp.register_hook(synchronize=False)
def cache_handler(cmd, *args, **kwargs):
    """
    Queries/calls a given cache function.
    """

    ret = {
        "_type": cmd,
    }

    # Private calls not allowed
    if cmd.startswith("_"):
        raise Exception("Unsupported command: {:s}".format(cmd))

    try:
        func = getattr(cache, cmd)
    except AttributeError:
        raise Exception("Unsupported command: {:s}".format(cmd))

    res = func(*args, **kwargs)
    if res != None:
        if isinstance(res, (list, set, tuple)):
            ret["values"] = res
        else:
            ret["value"] = res

    return ret


@edmp.register_hook()
def upload_handler():
    """
    Uploads cached data to cloud.
    """

    ret = {}

    ctx = context["upload"]
    try:

        # Only try upload failed on first run - then only retry and pending
        if ctx["count"] == 0:
            try:
                res = cache.upload_failing()
                if res["total"] > 0:
                    log.info("Successfully uploaded {:} failed entries".format(res["total"]))

                ret["failed"] = res
            except Exception as ex:
                log.exception("Failed to upload failing entries due to an unhandled exception - this must never happen")

        # Always upload retrying if any
        try:
            res = cache.upload_retrying()
            if res["total"] > 0:
                log.info("Successfully uploaded {:} retried entries".format(res["total"]))

            ret["retried"] = res

            # Check if we have reached retry queue limit
            if res["is_overrun"]:
                log.warning("Skipping upload of pending entries because retry queue limit is reached")

                ret["pending"] = {"errors": ["Postponed because retry queue limit is reached"]}

                return ret
        except:
            log.exception("Failed to upload retrying entries due to an unhandled exception - this must never happen")

        # Upload pending if any
        ret["pending"] = cache.upload_pending()

    finally:

        # TODO: Update this status for each batch upload!
        # Update context
        ctx["count"] += 1
        for key, val in ret.iteritems():
            ctx["complete"][key] = ctx["complete"].get(key, 0) + val.get("total", 0)
            ctx.setdefault("errors", {})[key] = val.get("errors", [])

    return ret


@edmp.register_hook(synchronize=False)
def status_handler():
    """
    Gets current status.
    """

    return context


def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting cloud manager with settings: {:}".format(settings))

        # Setup cache
        options = __salt__["config.get"]("cloud_cache")
        options["endpoint"] = settings["endpoint"]
        cache.setup(**options)

        # Initialize and run message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        edmp.run()

    except Exception:
        log.exception("Failed to start cloud manager")

        raise
    finally:
        log.info("Stopping cloud manager")
