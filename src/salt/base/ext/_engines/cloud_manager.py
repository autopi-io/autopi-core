import logging

from messaging import EventDrivenMessageProcessor


log = logging.getLogger(__name__)

# Message processor
edmp = EventDrivenMessageProcessor("cloud")

cache = CloudCache()

context = {
	"upload": {}
}


@edmp.register_hook()
def cache_handler(cmd, *args, **kwargs):
    """
    Query/call a cache function.
    """

    ret = {
        "_type": cmd,
    }

    try:
        func = getattr(cache, cmd)
    except AttributeError:
        ret["error"] = "Unsupported command: {:s}".format(cmd)
        return ret

    res = func(*args, **kwargs)
    if res != None:
        if isinstance(res, [list, set, tuple]):
            ret["values"] = res
        else:
            ret["value"] = res

    return ret


@edmp.register_hook()
def upload_handler():
	"""
	Upload data to cloud.
	"""

	ctx = context["upload"]

	# Only try upload failed on first run - then only pending and retry
	res = cache.upload_everything(include_failed=bool(ctx))

	# Update context with summed values
	for key, val in res.iteritems():
		ctx[key] = ctx.get(key, 0) + val

	return res


@edmp.register_hook(synchronize=False)
def status_handler():
    """
    Get current upload status.
    """

    return context


 def start(endpoint, workers, **kwargs):
    try:
        log.debug("Starting cloud manager")

        # Setup cache
        options = __salt__["config.get"]("cloud_cache")
        options["endpoint"] = endpoint
        cache.setup(**options)

        # Initialize and run message processor
        edmp.init(__opts__, workers=workers)
        edmp.run()

    except Exception:
        log.exception("Failed to start cloud manager")
        raise
    finally:
        log.info("Stopping cloud manager")
