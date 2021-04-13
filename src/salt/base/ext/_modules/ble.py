import logging
import salt.exceptions

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack


__virtualname__ = "ble"

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


def query(cmd, **kwargs):
    """
    Queries a given BlueNRG ACI command.
    """

    return client.send_sync(_msg_pack(cmd, **kwargs))


def interface(*args, **kwargs):
    """
    Manages the interface to the BlueNRG device.
    """

    return client.send_sync(_msg_pack(*args, _handler="interface", **kwargs))


def mode(**kwargs):
    """
    Manages the low-level modes of the BlueNRG device.
    """

    return client.send_sync(_msg_pack(_handler="mode", **kwargs))


def flash_firmware(bin_file, confirm=False, check_only=True, timeout=90):
    """
    Flashes new firmware to the BlueNRG device.
    """

    if not confirm:
        raise salt.exceptions.CommandExecutionError(
            "This command will flash firmware release '{:s}' onto the BlueNRG device - add parameter 'confirm=true' to continue anyway".format(bin_file))

    return client.send_sync(_msg_pack(bin_file, erase=not check_only, write=not check_only, _handler="flash_firmware"), timeout=timeout)


def context(**kwargs):
    """
    Deprecated: Use 'manage context' instead.
    Gets current context.
    """

    raise DeprecationWarning("Use '{:}.manage context' instead".format(__virtualname__))


def manage(*args, **kwargs):
    """
    Runtime management of the underlying service instance.

    Supported commands:
      - 'hook list|call <name> [argument]... [<key>=<value>]...'
      - 'worker list|show|start|pause|resume|kill <name>'
      - 'reactor list|show <name>'
      - 'run <key>=<value>...'

    Examples:
      - 'ble.manage hook list'
      - 'ble.manage hook call query_handler ACI_HAL_GET_FW_BUILD_NUMBER'
      - 'ble.manage worker list *'
      - 'ble.manage worker show *'
      - 'ble.manage worker start *'
      - 'ble.manage worker pause *'
      - 'ble.manage worker resume *'
      - 'ble.manage worker kill *'
      - 'ble.manage reactor list'
      - 'ble.manage reactor show *'
      - 'ble.manage run handler="query" args="[\"ACI_HAL_GET_FW_BUILD_NUMBER\"]"'
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))
