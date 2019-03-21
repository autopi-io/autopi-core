import datetime
import logging
try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

from cloud_cache import CloudCache
from salt.returners import get_returner_options
from salt.utils import jid


log = logging.getLogger(__name__)


__virtualname__ = "cloud"


def __virtual__():
    if not HAS_REDIS:
        return False, "Could not import cloud returner; " \
                      "redis python client is not installed."

    return __virtualname__


def _get_options(ret=None):

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Getting options for: {:}".format(ret))

    defaults = {
        "host": "localhost",
        "port": 6379,
        "db": 1
    }

    attrs = {
        "host": "redis_host",
        "port": "redis_port",
        "db": "redis_db"
    }

    _options = get_returner_options(
        "{:}_cache".format(__virtualname__),
        ret,
        attrs,
        __salt__=__salt__,
        __opts__=__opts__,
        defaults=defaults)

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Generated options: {:}".format(_options))

    return _options


def _get_cloud_cache_for(ret):

    # Get cloud cache instance from context if present
    _cloud_cache = __context__.get("cloud_cache", None)

    # Create new instance if no existing found
    if _cloud_cache == None:
        options = _get_options(ret)
        log.info("Creating cloud cache instance with Redis options: {:}".format(options))

        _cloud_cache = CloudCache().setup(redis=options)
        __context__["cloud_cache"] = _cloud_cache
    elif log.isEnabledFor(logging.DEBUG):
        log.debug("Re-using cloud cache instance found in context")

    return _cloud_cache


def _prepare_recursively(result, kind, timestamp=None):
    ret = []

    if isinstance(result, dict):

        # Clone result as we might change it
        result = result.copy()

        # Look for override values in result
        timestamp = result.pop("_stamp", timestamp) or datetime.datetime.utcnow().isoformat()
        kind = ".".join(filter(None, [kind, result.pop("_type", None)]))

        # Check if only one single list exists
        lone_key = next(iter(result)) if len(result) == 1 else None
        if lone_key != None and isinstance(result[lone_key], list):

            # Flatten lonely list into seperate results
            ret.extend(_prepare_recursively(result[lone_key], kind, timestamp))
        else:

            # Skip adding result if empty after timestamp and kind have been removed
            if result:
                result.update({
                    "@ts": timestamp,
                    "@t": kind,
                })
                ret.append(result)

    elif isinstance(result, (list, set, tuple)):
        timestamp = timestamp or datetime.datetime.utcnow().isoformat()

        # Flatten list into seperate results
        for res in result:
            ret.extend(_prepare_recursively(res, kind, timestamp))

    else:  # Handle primitive data types
        ret.append({
            "@ts": timestamp or datetime.datetime.utcnow().isoformat(),
            "@t": kind,
            "value": result
        })

    return ret


def returner(ret):
    """
    Return a result to cloud cache.
    """

    returner_job(ret)


def returner_job(job):
    """
    Return a Salt job result to cloud cache.
    """

    if not job or not job.get("jid", None):
        log.warn("Skipping invalid job result: {:}".format(job))

        return

    ret = job.get("return", job.get("ret", None))

    if not ret or not job.get("success", True):  # Default is success if not specified
        log.warn("Skipping unsuccessful job result with JID {:}: {:}".format(job["jid"], job))

        return

    # TODO: Timestamp can be extracted from JID value

    kind = job["fun"] if not "_type" in ret else job["fun"].split(".")[0]

    res = _prepare_recursively(ret, kind, timestamp=None)

    cloud_cache = _get_cloud_cache_for(job)
    for r in res:
        cloud_cache.enqueue(r)


def returner_event(event):
    """
    Return an event to cloud cache.
    """

    if not event:
        log.debug("Skipping empty event result")

        return

    tag_parts = event["tag"].lstrip("/").split("/")
    kind = "event.{:s}".format(".".join(tag_parts[:-1]))

    data = event["data"].copy()
    data["@tag"] = event["tag"]

    returner_data(data, kind)


def returner_data(data, kind, **kwargs):
    """
    Return any arbitrary data structure to cloud cache.
    """

    if not data:
        log.debug("Skipping empty data result")

        return

    if "error" in data:
        log.warn("Skipping data result because of error: {:}".format(data["error"]))

        return

    res = _prepare_recursively(data, kind)

    cloud_cache = _get_cloud_cache_for(kwargs)
    for r in res:
        cloud_cache.enqueue(r)
