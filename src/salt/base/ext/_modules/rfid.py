import logging

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack

__virtualname__ = "rfid"

log = logging.getLogger(__name__)

client = EventDrivenMessageClient("rfid")


def __virtual__():
    return __virtualname__


def __init__(opts):
    client.init(opts)


def read_settings(*args, **kwargs):
    """
    Reads the settings file stored in /opt/autopi/rfid/settings.yaml and applies them again.
    """

    log.info("FEDERLIZER: Calling rfid.read_settings")
    return client.send_sync(_msg_pack(_handler="read_settings"))
