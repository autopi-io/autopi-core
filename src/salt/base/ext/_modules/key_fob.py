import logging

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack


__virtualname__ = "keyfob"

log = logging.getLogger(__name__)

client = EventDrivenMessageClient("key_fob")


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
    Deprecated: Use 'manage context' instead.
    Gets current context.
    """

    raise DeprecationWarning("Use '{:}.manage context' instead".format(__virtualname__))


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


def manage(*args, **kwargs):
    """
    Runtime management of the underlying service instance.

    Supported commands:
      - 'hook list|call <name> [argument]... [<key>=<value>]...'
      - 'worker list|show|start|pause|resume|kill <name>'
      - 'reactor list|show <name>'
      - 'run <key>=<value>...'

    Examples:
      - 'keyfob.manage hook list'
      - 'keyfob.manage hook call power'
      - 'keyfob.manage worker list *'
      - 'keyfob.manage worker show *'
      - 'keyfob.manage worker start *'
      - 'keyfob.manage worker pause *'
      - 'keyfob.manage worker resume *'
      - 'keyfob.manage worker kill *'
      - 'keyfob.manage reactor list'
      - 'keyfob.manage reactor show *'
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))