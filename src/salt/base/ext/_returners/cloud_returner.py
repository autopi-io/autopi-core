import datetime
import logging
try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

from cloud_cache import CloudCache
from salt.utils import jid


log = logging.getLogger(__name__)


__virtualname__ = "cloud"


def __virtual__():
    if not HAS_REDIS:
        return False, "Could not import cloud returner; " \
                      "redis python client is not installed."

    return __virtualname__


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


def returner(result):
    returner_job(result)


def returner_job(result):
    """
    Return a Salt job.
    """

    if not result or not result.get("success", False):
        log.info("Skipping unsuccessful result with JID: {:}".format(result.get("jid", None)))
        return

    # TODO: Timestamp can be extracted from JID value

    kind = result["fun"] if not "_type" in result["return"] else result["fun"].split(".")[0]

    res = _prepare_recursively(result["return"], kind, timestamp=None)

    cloud_cache = CloudCache().setup(**__salt__["config.get"]("cloud_cache"))
    for r in res:
        cloud_cache.enqueue(r)


def returner_event(result):
    """
    Return an event.
    """

    tag_parts = result["tag"].lstrip("/").split("/")
    kind = "event.{:s}".format(".".join(tag_parts[:1]))

    data = result["data"].copy()
    data["@tag"] = result["tag"]

    returner_raw(data, kind)


def returner_raw(result, kind):
    """
    Return any arbitrary data structure.
    """

    if not result or "error" in result:
        log.info("Skipping empty or error result")
        return

    res = _prepare_recursively(result, kind)

    cloud_cache = CloudCache().setup(**__salt__["config.get"]("cloud_cache"))
    for r in res:
        cloud_cache.enqueue(r)
