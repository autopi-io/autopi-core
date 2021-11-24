import logging

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack

__virtualname__ = "rfid"

log = logging.getLogger(__name__)

client = EventDrivenMessageClient("rfid")


def __virtual__():
    return __virtualname__


def __init__(opts):
    client.init(opts)


def load_settings(*args, **kwargs):
    """
    Read the settings file stored in /opt/autopi/rfid/settings.yaml and load it.
    """

    return client.send_sync(_msg_pack(_handler="load_settings"))


def manage(*args, **kwargs):
    """
    Runtime management of the underlying service instance.

    Supported commands:
      - 'hook list|call <name> [argument]... [<key>=<value>]...'
      - 'worker list|show|start|pause|resume|kill <name>'
      - 'reactor list|show <name>'
      - 'run <key>=<value>...'
      - 'context [key]... [value=<value>]'

    Examples:
      - 'rfid.manage hook list'
      - 'rfid.manage hook call power'
      - 'rfid.manage worker list *'
      - 'rfid.manage worker show *'
      - 'rfid.manage worker start *'
      - 'rfid.manage worker pause *'
      - 'rfid.manage worker resume *'
      - 'rfid.manage worker kill *'
      - 'rfid.manage reactor list'
      - 'rfid.manage reactor show *'
      - 'rfid.manage context'
      - 'rfid.manage context <context_key>'
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))