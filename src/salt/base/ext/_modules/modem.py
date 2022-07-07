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

