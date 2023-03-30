import logging

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack


__virtualname__ = "can"

log = logging.getLogger(__name__)

client = EventDrivenMessageClient("can")


def __virtual__():
    return __virtualname__


def __init__(opts):
    client.init(opts)


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"](__virtualname__)


def connection(**kwargs):
    """
    Manages the current CAN connection.
    """

    return client.send_sync(_msg_pack(_handler="connection", **kwargs))


def filter(*args, **kwargs):
    """
    Manages the CAN filters.
    """

    return client.send_sync(_msg_pack(*args, _handler="filter", **kwargs))


def send(*args, **kwargs):
    """
    Sends one or more messages on the CAN bus.
    """

    return client.send_sync(_msg_pack(*args, _handler="send", **kwargs))


def query(*args, **kwargs):
    """
    Queries by sending one or more request messages on the CAN bus and then waits for one or more response messages.
    """

    return client.send_sync(_msg_pack(*args, _handler="query", **kwargs))


def monitor(**kwargs):
    """
    Monitors messages on the CAN bus until a limit or duration is reached.
    """

    return client.send_sync(_msg_pack(_handler="monitor", **kwargs))


def dump(*args, **kwargs):
    """
    Stores messages from the CAN bus to a file until a limit or duration is reached.
    """

    return client.send_sync(_msg_pack(*args, _handler="dump", **kwargs))


def play(*args, **kwargs):
    """
    Sends all messages from one or more dump files on the CAN bus.
    """

    return client.send_sync(_msg_pack(*args, _handler="play", **kwargs))


def obd_query(*args, **kwargs):
    """
    Queries an OBD-II PID on the CAN bus.
    """

    return client.send_sync(_msg_pack(*args, _handler="obd_query", **kwargs))


def manage(*args, **kwargs):
    """
    Facilitates runtime management of the underlying service instance.
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))

