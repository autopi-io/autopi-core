import logging

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack


__virtualname__ = "tracking"

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
    Gets current context.
    """

    raise DeprecationWarning("Use '{:}.manage context' instead".format(__virtualname__))


def status(**kwargs):
    """
    Gets current status.
    """

    return client.send_sync(_msg_pack(_handler="status", **kwargs))


def load_geofences(*args, **kwargs):
    """
    Loads geofences.
    Optional arguments:
      - 'path' path to the geofences file
    """
    return client.send_sync(_msg_pack(_handler="load_geofences", **kwargs))


def manage(*args, **kwargs):
    """
    Runtime management of the underlying service instance.

    Supported commands:
      - 'hook list|call <name> [argument]... [<key>=<value>]...'
      - 'worker list|show|start|pause|resume|kill <name>'
      - 'reactor list|show <name>'
      - 'run <key>=<value>...'

    Examples:
      - 'tracking.manage hook list'
      - 'tracking.manage hook call gnss_query_handler location'
      - 'tracking.manage worker list *'
      - 'tracking.manage worker show *'
      - 'tracking.manage worker start *'
      - 'tracking.manage worker pause *'
      - 'tracking.manage worker resume *'
      - 'tracking.manage worker kill *'
      - 'tracking.manage reactor list'
      - 'tracking.manage reactor show *'
      - 'tracking.manage run handler="gnss_query" args="[\"location\"]" converter="gnss_location_to_position" returner="cloud"'
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))

