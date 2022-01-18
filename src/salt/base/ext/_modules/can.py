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
    Manages current connection.
    """

    return client.send_sync(_msg_pack(_handler="connection", **kwargs))


def filter(*args, **kwargs):
    """
    Manages filters.
    """

    return client.send_sync(_msg_pack(*args, _handler="filter", **kwargs))


def send(*args, **kwargs):
    """
    """

    return client.send_sync(_msg_pack(*args, _handler="send", **kwargs))


def query(*args, **kwargs):
    """
    """

    return client.send_sync(_msg_pack(*args, _handler="query", **kwargs))


def monitor(**kwargs):
    """
    """

    return client.send_sync(_msg_pack(_handler="monitor", **kwargs))


def dump(*args, **kwargs):
    """
    """

    return client.send_sync(_msg_pack(*args, _handler="dump", **kwargs))


def play(*args, **kwargs):
    """
    """

    return client.send_sync(_msg_pack(*args, _handler="play", **kwargs))


def obd_query(*args, **kwargs):
    """
    """

    return client.send_sync(_msg_pack(*args, _handler="obd_query", **kwargs))


def manage(*args, **kwargs):
    """
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))

