import logging
import salt.utils.event


log = logging.getLogger(__name__)


__virtualname__ = "event"


def __virtual__():
    return __virtualname__


def returner(res):
    """
    Publishes a job execution notification on the minion event bus.
    """

    event_bus = salt.utils.event.get_event("minion",
        opts=__opts__,
        transport=__opts__["transport"],
        listen=False)

    # Prepare event data
    data = {
            "success": res["success"],
            "retcode": res.get("retcode", 0)
    }

    # Parse out arguments
    for arg in res["fun_args"]:
        if isinstance(arg, dict):
            data["kwargs"] = arg
        else:
            args = data.get("args", [])
            args.append(arg)
            data["args"] = args

    event_bus.fire_event(data, "salt/job/{:}/fun/{:}".format(res["jid"], res["fun"]))
