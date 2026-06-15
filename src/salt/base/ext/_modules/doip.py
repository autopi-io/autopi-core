import logging
import salt.exceptions

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack


__virtualname__ = "doip"

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
    Gets current context.
    """

    return client.send_sync(_msg_pack(_handler="context", **kwargs))


def interface(*args, **kwargs):
    """
    Manages the DoIP interface.

    Examples:
      - 'doip.interface'
      - 'doip.interface help'
      - 'doip.interface activate'
      - 'doip.interface activate pin_setup=alt'
      - 'doip.interface deactivate'
      - 'doip.interface connect'
      - 'doip.interface disconnect'
      - 'doip.interface reconnect'
    """

    return client.send_sync(_msg_pack(*args, _handler="interface", **kwargs))


def uds(cmd, *args, **kwargs):
    """
    Queries using the UDS client. The UDS client works synchronously and can handle a single request/response at a time.

    Examples:
      - 'doip.uds help'
      - 'doip.uds help change_session'
      - 'doip.uds change_session 1'
    """

    return client.send_sync(_msg_pack(cmd, *args, _handler="uds", **kwargs))


def manage(*args, **kwargs):
    """
    Runtime management of the underlying service instance.

    Supported commands:
      - 'hook list|call <name> [argument]... [<key>=<value>]...'
      - 'worker list|show|start|pause|resume|kill <name>'
      - 'reactor list|show <name>'
      - 'run <key>=<value>...'

    Examples:
      - 'doip.manage hook list'
      - 'doip.manage hook call uds_handler change_session 1'
      - 'doip.manage worker list *'
      - 'doip.manage worker show *'
      - 'doip.manage worker start *'
      - 'doip.manage worker pause *'
      - 'doip.manage worker resume *'
      - 'doip.manage worker kill *'
      - 'doip.manage reactor list'
      - 'doip.manage reactor show *'
      - 'doip.manage run handler="uds" args="[\"change_session\", 1]"'
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))
