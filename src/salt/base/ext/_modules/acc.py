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

    For additional help run: acc.query help

    Examples:
        acc.query status
        acc.query xyz
        acc.query active value=False
        acc.range value=4
        acc.data_rate value=12.5
        acc.offset x=0.1 y=-0.1 z=0
    """

    return client.send_sync(msg_pack(cmd, *args, **kwargs))


def dump(**kwargs):
    """
    Dumps raw XYZ readings to screen or file.

    Optional arguments:
        duration (int): How many seconds to record data? Default value is 1.
        file (str): Write data to a file with the given name.
        range (int): Maximum number of g-forces being measured. Default value is 8.
        rate (float): How many Hz (samples per second)? Default value is 50.
        decimals (int): How many decimals to calculate? Default value is 4.
        timestamp (bool): Add timestamp to each sample? Default value is True.
        sound (bool): Play sound when starting and stopping recording? Default value is True.
        interrupt_driven (bool): Await hardware data ready signal before reading a sample? Default value is False.
    """

    return client.send_sync(msg_pack(_handler="dump", **kwargs))


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
