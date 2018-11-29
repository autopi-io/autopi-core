import logging

from messaging import EventDrivenMessageClient, msg_pack


__virtualname__ = "acc"

log = logging.getLogger(__name__)

client = EventDrivenMessageClient("acc")


def __virtual__():
    return __virtualname__


def __init__(opts):
    client.init(opts)


def help():
    """
    This command.
    """

    return __salt__["sys.doc"](__virtualname__)


def query(cmd, *args, **kwargs):
    """
    Queries a given accelerometer command.
    """

    return client.send_sync(msg_pack(cmd, *args, **kwargs))


def context(**kwargs):
    """
    Gets current context.
    """

    return client.send_sync(msg_pack(_handler="context", **kwargs))


def manage(*args, **kwargs):
    """
    Example: acc.manage worker list *
    """

    return client.send_sync(msg_pack(*args, _workflow="manage", **kwargs))
