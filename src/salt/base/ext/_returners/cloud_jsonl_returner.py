
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals, with_statement

import croniter
import datetime
import logging
import os
import threading

import salt.returners
import salt.utils

from cloud_cache import prepare_result_recursively
from common_util import jsonl_dump, makedirs, RotatingTextFile
from threading_more import AsyncWriterThread, on_exit


JSON_SEPARATORS = (",", ":")

EPOC_DATETIME = datetime.datetime(1970, 1, 1, 0, 0, 0)

log = logging.getLogger(__name__)

DEBUG = log.isEnabledFor(logging.DEBUG)

tlock = threading.Lock()
tlocal = threading.local()

__virtualname__ = "cloud_jsonl"


def __virtual__():
    return __virtualname__


def _exit_handler():
    for filename, writer in __context__.get("cloud_jsonl_writers", {}).iteritems():
        try:
            writer.stop()
        except:
            log.exception("Error stopping JSONL writer for file '{:}'".format(filename))

on_exit.append(_exit_handler)


def _get_options(ret):
    if DEBUG:
        log.debug("Getting options for: {:}".format(ret))

    defaults = {
        "filename": "{now:%y%m%d%H%M%S}_{pid}.jsonl",
        "dir": "/opt/autopi/data",
        "mode": "a",
        "async_writer.flush_threshold": int(1024*1024*0.5),  # 0.5MB
        "async_writer.flush_timeout": 1,                     # 1 second
        "async_writer.buffer_size": 1024*1024*10,            # 10MB
        "async_writer.buffer_high_watermark": 0,
        "rotation.size": 1024*1024*100,                      # 100MB
        "rotation.cron": "0 0 * * *",                        # At 00:00 every day
        "rotation.interval": 0                               # Disabled
    }

    attrs = {
        "filename": "filename",
        "dir": "dir",
        "mode": "mode",
        "async_writer.flush_threshold": "async_writer.flush_threshold",
        "async_writer.flush_timeout": "async_writer.flush_timeout",
        "async_writer.buffer_size": "async_writer.buffer_size",
        "async_writer.buffer_high_watermark": "async_writer.buffer_high_watermark",
        "rotation.size": "rotation.size",
        "rotation.cron": "rotation.cron",
        "rotation.interval": "rotation.interval"
    }

    _options = salt.returners.get_returner_options(
        __virtualname__,
        ret,
        attrs,
        __salt__=__salt__,
        __opts__=__opts__,
        defaults=defaults,
    )

    if DEBUG:
        log.debug("Generated options: {:}".format(_options))

    return _options


def _get_writer_for(ret):

    # Try to find writer in thread local
    writer = getattr(tlocal, "writer", None)
    if not writer or writer.closed:

        # Then try to find writer in thread shared context
        with tlock:
            options = _get_options(ret)

            # Ensure directory exists
            makedirs(options["dir"], exist_ok=True)

            key = options["filename"].format(now=EPOC_DATETIME, pid=os.getpid(), tid=threading.currentThread().ident)
            writer = __context__.setdefault("cloud_jsonl_writers", {}).get(key, None)
            if not writer or writer.closed:

                def open_file(obj):
                    now = datetime.datetime.utcnow()
                    
                    # Generate filename
                    filename = options["filename"].format(now=now, pid=os.getpid(), tid=threading.currentThread().ident)

                    # Set max file size
                    obj.max_size = options["rotation.size"]

                    # Calculate and set next expiration time
                    expiration_times = []
                    if options["rotation.interval"] > 0:
                        expiration_times.append(float((now + datetime.timedelta(seconds=options["rotation.interval"])).strftime("%s")))
                    if options["rotation.cron"]:
                        expiration_times.append(float(croniter.croniter(options["rotation.cron"], now).get_next()))
                    obj.expiration_time = min(expiration_times) if expiration_times else 0

                    log.info("Opening JSONL file '{:}'".format(filename))
                    return open(os.path.join(options["dir"], filename), "a", buffering=0)  # Buffering disabled

                writer = AsyncWriterThread(RotatingTextFile(open_file),
                    **{k[len("async_writer."):]: v for k, v in options.iteritems() if k.startswith("async_writer.")})
                
                # Store writer in context
                __context__["cloud_jsonl_writers"][key] = writer

            elif DEBUG:
                log.debug("Re-using writer found in context")

        # Store writer in thread local
        setattr(tlocal, "writer", writer)

    elif DEBUG:
        log.debug("Re-using writer found in thread local")

    return writer


def returner(ret):
    """
    Return a result to cloud jsonl file.
    """

    returner_job(ret)


def returner_job(job):
    """
    Return a Salt job result to cloud jsonl file.
    """

    if not job or not job.get("jid", None):
        log.warn("Skipping invalid job result: {:}".format(job))

        return

    ret = job.get("return", job.get("ret", None))

    if not ret or not job.get("success", True):  # Default is success if not specified
        log.warn("Skipping unsuccessful job result with JID {:}: {:}".format(job["jid"], job))

        return

    # TODO: Timestamp can be extracted from JID value

    kind = job["fun"] if isinstance(ret, dict) and not "_type" in ret else job["fun"].split(".")[0]

    res = prepare_result_recursively(ret, kind, timestamp=None)

    writer = _get_writer_for(job)
    jsonl_dump(res, writer)


def returner_event(event):
    """
    Return an event to cloud jsonl file.
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
    Return any arbitrary data structure to cloud jsonl file.
    """

    if not data:
        log.debug("Skipping empty data result")

        return

    if "error" in data:
        log.warn("Skipping data result because of error: {:}".format(data["error"]))

        return

    res = prepare_result_recursively(data, kind)

    writer = _get_writer_for(kwargs)
    jsonl_dump(res, writer)

