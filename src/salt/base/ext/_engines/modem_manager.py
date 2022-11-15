import logging
import re

from le910cx_conn import LE910CXConn, NoSimPresentException
from messaging import EventDrivenMessageProcessor, extract_error_from
from threading_more import intercept_exit_signal


log = logging.getLogger(__name__)

context = {}

# Message processor
edmp = EventDrivenMessageProcessor("modem", context=context, default_hooks={"workflow": "extended", "handler": "connection"})

conn = LE910CXConn()


@edmp.register_hook()
def connection_handler(cmd, *args, **kwargs):
    """
    Queries a given connection class command.

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


@edmp.register_hook()
def read_sms_handler(*args, **kwargs):
    """
    Reads SMS messages stored in the modem and optionally processes them into 'system/sms/received' events.
    Those events hold information such as the timestamp of the message (when it was received by the
    modem), the sender and the text.

    Optional parameters:
    - status (str): The status of the messages that are to be returned. Look below for avalable options. Default: "ALL".
    - clear (bool): Should the returned messages be removed from the modem as well?
    - format_mode (str): The format in which the messages should be processed. Currently, only TXT mode is supported. Default: "TXT".
    - trigger_events (bool): Should the handler trigger SMS events? Default: False

    Available options (status):
    - "REC UNREAD" - new messages
    - "REC READ" - read messages
    - "STO UNSENT" - stored messages not sent yet
    - "STO SENT" - stored messages already sent
    - "ALL" - all messages
    """

    trigger_events = kwargs.pop("trigger_events", False)

    # Get messages and clear them
    try:
        res = conn.sms_list(*args, **kwargs)
    except NoSimPresentException as e:
        log.warning("No SIM present, breaking workflow")
        return

    # Some validation
    if "values" not in res:
        raise Exception("sms_list returned response with no 'values' key")

    if type(res["values"]) is not list:
        raise Exception("sms_list returned 'values' that isn't a list")

    # For each message, create an event
    if trigger_events:
        for msg in res["values"]:
            # Trigger event
            data = {
                "sender": msg["sender"],
                "timestamp": msg["timestamp"],
                "text": msg["data"],
            }

            __salt__["minionutil.trigger_event"]("system/sms/received", data=data)

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
