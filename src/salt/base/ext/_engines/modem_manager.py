import logging
import re

from le910cx_conn import LE910CXConn
from messaging import EventDrivenMessageProcessor
from threading_more import intercept_exit_signal


log = logging.getLogger(__name__)

context = {}

# Message processor
edmp = EventDrivenMessageProcessor("modem", context=context, default_hooks={"workflow": "extended", "handler": "query"})

conn = LE910CXConn()


@edmp.register_hook()
def query_handler(cmd, *args, **kwargs):
    """
    Queries a given command.

    Arguments:
      - cmd (str): The command to query.
    """

    ret = {
        "_type": cmd.lower(),
    }

    try:
        func = getattr(conn, cmd)
    except AttributeError:
        ret["error"] = "Unsupported command: {:s}".format(cmd)
        return ret

    res = func(*args, **kwargs)
    if res != None:
        if isinstance(res, dict):
            ret.update(res)
        else:
            ret["value"] = res

    return ret


@intercept_exit_signal
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting modem manager with settings: {}".format(settings))

        # TODO HN
        conn.init({
            "device": "/dev/ttyTLT01",
            "baudrate": 115200,
            "timeout": 30,
        })

        # Init and start message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))

        edmp.run()

    except Exception as e:
        log.exception("Failed to start modem manager")
        raise

    finally:
        log.info("Stopping modem manager")
