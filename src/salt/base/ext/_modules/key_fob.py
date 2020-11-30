import logging

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack


__virtualname__ = "keyfob"

log = logging.getLogger(__name__)

client = EventDrivenMessageClient(__name__)


def __virtual__():
    return __virtualname__


def __init__(opts):
    client.init(opts)


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"](__virtualname__)


def context(**kwargs):
    """
    Gets current context.
    """

    return client.send_sync(_msg_pack(_handler="context", **kwargs))


def power(**kwargs):
    """
    Powers on/off key fob.

    Optional arguments:
      - value (bool): Power on or off. 
    """

    return client.send_sync(_msg_pack(_handler="power", **kwargs))


def action(*args, **kwargs):
    """
    Performs a key fob button action.

    Arguments:
      - *name (str): Name(s) of the action(s) to perform.
    """

    return client.send_sync(_msg_pack(*args, _handler="action", **kwargs))