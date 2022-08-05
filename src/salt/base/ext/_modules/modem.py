import logging
import salt.exceptions

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack


__virtualname__ = "modem"

log = logging.getLogger(__name__)

client = EventDrivenMessageClient(__virtualname__)


def __virtual__():
    return __virtualname__


def __init__(opts):
    client.init(opts)


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"](__virtualname__)


def query(cmd, *args, **kwargs):
    """
    Queries a given command.

    Arguments:
      - cmd (str): The command to query.
    """

    return client.send_sync(_msg_pack(cmd, *args, **kwargs))


def reset(*args, **kwargs):
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

    return client.send_sync(_msg_pack(*args, _handler="reset", **kwargs), timeout=60)


def read_sms(*args, **kwargs):
    """
    Reads SMS messages stored in the modem and processes them into 'system/sms/received' events.
    Those events hold information such as the timestamp of the message (when it was received by the
    modem), the sender and the text.

    Optional parameters:
    - clear (bool): Should the messages be deleted from the modem after being processed? Default: False.
    """

    return client.send_sync(_msg_pack(*args, _handler="read_sms", **kwargs))


def manage(*args, **kwargs):
    """
    Runtime management of the underlying service instance.

    Supported commands:
      - 'hook list|call <name> [argument]... [<key>=<value>]...'
      - 'worker list|show|start|pause|resume|kill <name>'
      - 'reactor list|show <name>'
      - 'run <key>=<value>...'

    Examples:
      - 'modem.manage hook list'
      - 'modem.manage hook call query_handler status'
      - 'modem.manage worker list *'
      - 'modem.manage worker show *'
      - 'modem.manage worker start *'
      - 'modem.manage worker pause *'
      - 'modem.manage worker resume *'
      - 'modem.manage worker kill *'
      - 'modem.manage reactor list'
      - 'modem.manage reactor show *'
      - 'modem.manage run handler="query" args="[\"status\"]"'
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))

