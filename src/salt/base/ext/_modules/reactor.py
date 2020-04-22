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
    Queries or manipulates context of event reactor.
    """

    return client.send_sync(_msg_pack(_handler="context", **kwargs))


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
      - 'run <key>=<value>...'

    Examples:
      - 'obd.manage hook list'
      - 'obd.manage worker list *'
      - 'obd.manage worker show *'
      - 'obd.manage worker start *'
      - 'obd.manage worker pause *'
      - 'obd.manage worker resume *'
      - 'obd.manage worker kill *'
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))