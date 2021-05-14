
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
from timeit import default_timer as timer


JSON_SEPARATORS = (",", ":")

EPOC_DATETIME = datetime.datetime(1970, 1, 1, 0, 0, 0)

log = logging.getLogger(__name__)

DEBUG = log.isEnabledFor(logging.DEBUG)

tlocal = threading.local()
tlock = threading.RLock()  # NOTE: For this lock to work properly, it is important that this returner module is only loaded once per process


__virtualname__ = "cloud_jsonl"


def __virtual__():
    return __virtualname__


def _exit_handler():
    for filename, writer in __context__.get("cloud_jsonl_returner.writers", {}).iteritems():
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
        "initially_expired": False,
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
        "initially_expired": "initially_expired",
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
        defaults=defaults
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

            key = options["filename"].format(now=EPOC_DATETIME, uid=__opts__["id"], pid=os.getpid(), tid=threading.currentThread().ident)
            writer = __context__.setdefault("cloud_jsonl_returner.writers", {}).get(key, None)
            if not writer or writer.closed:

                def open_file(obj):
                    now = datetime.datetime.utcnow()
                    
                    format_kwargs = dict(now=now, uid=__opts__["id"], pid=os.getpid(), tid=threading.currentThread().ident)

                    # Generate directory
                    directory = options["dir"].format(**format_kwargs)

                    # Generate filename
                    filename = options["filename"].format(**format_kwargs)

                    # Set max file size
                    obj.max_size = options["rotation.size"]

                    # Calculate and set next expiration time
                    expiration_times = []
                    if options["rotation.interval"] > 0:
                        expiration_times.append(float((now + datetime.timedelta(seconds=options["rotation.interval"])).strftime("%s")))
                    if options["rotation.cron"]:
                        expiration_times.append(float(croniter.croniter(options["rotation.cron"], now).get_next()))
                    obj.expiration_time = min(expiration_times) if expiration_times else 0

                    # Ensure directory exists
                    makedirs(directory, exist_ok=True)

                    log.info("Opening JSONL file '{:}'".format(filename))
                    return open(os.path.join(directory, filename), "a", buffering=0)  # Buffering disabled

                writer = AsyncWriterThread(RotatingTextFile(open_file),
                    **{k[len("async_writer."):]: v for k, v in options.iteritems() if k.startswith("async_writer.")})

                # Store writer in context
                __context__["cloud_jsonl_returner.writers"][key] = writer

            elif DEBUG:
                log.debug("Re-using writer {:} found in context".format(writer))

        # Store writer in thread local
        setattr(tlocal, "writer", writer)

    elif DEBUG:
        log.debug("Re-using writer {:} found in thread local".format(writer))

    return writer


def _is_expired_for(ret):
    """
    Helper function to initialize expiration and return current state.
    """

    with tlock:

        # Initialize if not already done
        if not "cloud_jsonl_returner.expiration" in __context__:
            options = _get_options(ret)

            delay = -1  # Disabled
            if options["initially_expired"]:
                delay = 0  # Instantly

                log.info("Returner must be initially expired")

            set_expiration(delay, reason="initial")

        return is_expired()


def is_expired():
    """
    Check if this returner has expired.
    """

    with tlock:

        time = __context__.get("cloud_jsonl_returner.expiration", {}).get("time", -1)
        if time < 0:
            return False

        if time > 0:
            return time <= timer()
        else:
            return True


def set_expiration(delay, reason="unknown"):
    """
    Set or clear expiration for this returner.
    Delay of zero means instant expiration.
    Negative delay will clear any already set expiration.
    """

    with tlock:

        ctx = __context__.setdefault("cloud_jsonl_returner.expiration", {})
        if delay < 0:
            if ctx:

                # Ensure to close writers if already expired
                if is_expired():
                    close_writers()

                ctx.clear()

                log.info("Cleared expiration with reason '{:}'".format(reason))
            else:
                log.info("Attempted to clear expiration with reason '{:}' but no expiration is set".format(reason))

        else:
            if is_expired():
                log.info("Already expired with reason '{:}'".format(ctx.get("reason", "")))
            else:
                if delay > 0:
                    ctx["time"] = float((datetime.datetime.now() + datetime.timedelta(seconds=delay)).strftime("%s"))
                else:
                    ctx["time"] = 0  # Instantly
                ctx["reason"] = reason

                log.info("Set expiration to {:} with reason '{:}'".format(ctx["time"], ctx["reason"]))

        return ctx


def close_writers():
    """
    Ensure all open writers are closed.
    """

    with tlock:

        for key, writer in __context__.get("cloud_jsonl_returner.writers", {}).iteritems():
            if not writer.closed:
                log.info("Closing writer for file '{:}' found in context".format(writer.name))

                writer.close()


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

    if _is_expired_for(job):
        if DEBUG:
            log.debug("Skipping job result because the returner has expired")

        # Ensure any open writer is closed for the calling thread
        writer = getattr(tlocal, "writer", None)
        if writer and not writer.closed:
            log.info("Closing writer for file '{:}' found in thread local".format(writer.name))

            writer.close()

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

    if _is_expired_for(kwargs):
        if DEBUG:
            log.debug("Skipping data result because the returner has expired")

        # Ensure any open writer is closed for the calling thread
        writer = getattr(tlocal, "writer", None)
        if writer and not writer.closed:
            log.info("Closing writer for file '{:}' found in thread local".format(writer.name))

            writer.close()

        return

    res = prepare_result_recursively(data, kind)

    writer = _get_writer_for(kwargs)
    jsonl_dump(res, writer)

