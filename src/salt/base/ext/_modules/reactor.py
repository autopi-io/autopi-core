import logging

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack


__virtualname__ = "reactor"

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


def context(**kwargs):
    """
    Deprecated: Use 'manage context' instead.
    Queries or manipulates context of event reactor.
    """

    raise DeprecationWarning("Use '{:}.manage context' instead".format(__virtualname__))


def cache(**kwargs):
    """
    Queries or manipulates cache of event reactor.
    """

    return client.send_sync(_msg_pack(_handler="cache", **kwargs))


def manage(*args, **kwargs):
    """
    Runtime management of the underlying service instance.

    Supported commands:
      - 'hook list|call <name> [argument]... [<key>=<value>]...'
      - 'worker list|show|start|pause|resume|kill <name>'
      - 'reactor list|show <name>'
      - 'run <key>=<value>...'

    Examples:
      - 'reactor.manage hook list'
      - 'reactor.manage worker list *'
      - 'reactor.manage worker show *'
      - 'reactor.manage worker start *'
      - 'reactor.manage worker pause *'
      - 'reactor.manage worker resume *'
      - 'reactor.manage worker kill *'
      - 'reactor.manage reactor list'
      - 'reactor.manage reactor show *'
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))