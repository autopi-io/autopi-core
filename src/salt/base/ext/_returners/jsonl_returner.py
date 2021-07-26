import datetime
import json
import logging
import os


from salt.returners import get_returner_options


log = logging.getLogger(__name__)


__virtualname__ = "jsonl"


def __virtual__():
    return __virtualname__


def _get_options(ret=None):
    if log.isEnabledFor(logging.DEBUG):
        log.debug("Getting options for: {:}".format(ret))

    defaults = {
        "filename": "{now:%y%m%d%H%M%S}_{pid}.jsonl",
        "dir": "/opt/autopi/data",
        "mode": "a"
    }

    attrs = {
        "filename": "filename",
        "dir": "dir",
        "mode": "mode"
    }

    options = get_returner_options(
        "{:}_returner".format(__virtualname__),
        ret,
        attrs,
        __salt__=__salt__,
        __opts__=__opts__,
        defaults=defaults
    )

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Generated options: {:}".format(options))

    return options


def returner(ret):
    """
    Return a result to JSONL file.

    Example: salt '*' test.ping --return jsonl --return_kwargs '{"dir": "/opt/", "filename": "test.jsonl"}'
    """

    returner_job(ret)


def returner_job(job):
    """
    Return a Salt job result to a JSONL file.
    """

    if not job or not job.get("jid", None):
        log.warn("Skipping invalid job result: {:}".format(job))

        return

    ret = job.get("return", job.get("ret", None))

    if not ret or not job.get("success", True):  # Default is success if not specified
        log.warn("Skipping unsuccessful job result with JID {:}: {:}".format(job["jid"], job))

        return

    namespace = job["fun"].split(".")
    if isinstance(ret, dict) and "_type" in ret:

        # Only use module name when type is available
        returner_data(ret, namespace[0], **job)
    else:
        returner_data(ret, *namespace, **job)


def returner_data(data, *args, **kwargs):
    """
    Return any arbitrary data structure to a JSONL file.
    """

    if not data:
        log.debug("Skipping empty data result")

        return

    now = datetime.datetime.utcnow().isoformat()

    if isinstance(data, dict):
        payload = data
    elif isinstance(data, (list, set, tuple)):
        payload = {
            "_stamp": now,
            "values": data
        }
    else:
        payload = {
            "_stamp": now,
            "value": data
        }

    if args:
        payload["_type"] = ".".join([str(t) for t in list(args) + [payload.get("_type", None)] if t])

    options = _get_options(kwargs)

    format_kwargs = dict(now=now, uid=__opts__["id"], pid=os.getpid())

    directory = options["dir"].format(**format_kwargs)
    filename = options["filename"].format(**format_kwargs)

    with open(os.path.join(directory, filename), options["mode"]) as file:
        file.write(json.dumps(payload, separators=(",", ":")) + "\n")
