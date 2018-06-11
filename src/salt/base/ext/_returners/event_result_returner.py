import logging
import salt.utils.event


log = logging.getLogger(__name__)


__virtualname__ = "event_result"


def __virtual__():
    return __virtualname__


def returner(res):
    """
    Publishes an entire job result on the minion event bus.
    """

    event_bus = salt.utils.event.get_event("minion",
        opts=__opts__,
        transport=__opts__["transport"],
        listen=False)

    event_bus.fire_event(res, "salt/job/{:}/ret".format(res["jid"]))
