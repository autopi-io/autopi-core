import logging

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack


__virtualname__ = "gnss"

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


def query(*args, **kwargs):
    """
    Query the connection class.
    """

    return client.send_sync(_msg_pack(*args, _handler="query", **kwargs))


def manage(*args, **kwargs):
    """
    Runtime management of the underlying service instance.

    Supported commands:
      - 'hook list|call <name> [argument]... [<key>=<value>]...'
      - 'worker list|show|start|pause|resume|kill <name>'
      - 'reactor list|show <name>'
      - 'run <key>=<value>...'

    Examples:
      - 'gnss.manage hook list'
      - 'gnss.manage hook call gnss_query_handler location'
      - 'gnss.manage worker list *'
      - 'gnss.manage worker show *'
      - 'gnss.manage worker start *'
      - 'gnss.manage worker pause *'
      - 'gnss.manage worker resume *'
      - 'gnss.manage worker kill *'
      - 'gnss.manage reactor list'
      - 'gnss.manage reactor show *'
      - 'gnss.manage run handler="query" args="[\"gnss_location\"]" converter="gnss_location_to_position" returner="cloud"'
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))

