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


@edmp.register_hook()
def reset_handler(*args, **kwargs):
    """
    Enable or disable the one shot or periodic unit reset.

    Optional parameters:
    - mode (string): The mode in which to operate the command. For available values, look below. Default: None.
    - delay (number): Time interval in minutes after that the unit reboots. Default: 0.
    - reason (str): The reason the reset was performed. Default: "unspecified".

    Available modes:
    - disabled: Disables unit reset.
    - one_shot: Enables the unit reset only one time (one shot reset).
    - periodic: Enables periodic resets of the unit.
    """

    reason = kwargs.pop("reason", "unspecified")

    res = conn.reset(*args, **kwargs)

    tag = "system/device/le910cx/reset"
    data = { "reason": reason }

    __salt__["minionutil.trigger_event"](tag, data=data)

    return res


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
