import logging

from messaging import EventDrivenMessageClient, msg_pack


__virtualname__ = "obd"

log = logging.getLogger(__name__)

client = EventDrivenMessageClient("obd")


def __virtual__():
    return __virtualname__


def __init__(opts):
    client.init(opts)


def help():
    """
    This command.
    """

    return __salt__["sys.doc"](__virtualname__)


def query(cmd, mode=None, pid=None, bytes=None, decoder=None, force=None, **kwargs):
    """
    Queries a given OBD command.
    """

    return client.send_sync(msg_pack(cmd, mode=mode, pid=pid, bytes=bytes, decoder=decoder, force=force, **kwargs))


def commands(**kwargs):
    """
    Lists all supported OBD commands found for vehicle.
    """

    return client.send_sync(msg_pack(_handler="commands", **kwargs))


def protocol(**kwargs):
    """
    Configures protocol or lists all supported.
    """

    return client.send_sync(msg_pack(_handler="protocol", **kwargs))


def send(msg, **kwargs):
    """
    Sends a raw message on bus.
    """

    return client.send_sync(msg_pack(str(msg), _handler="send", **kwargs))


def execute(cmd, **kwargs):
    """
    Executes an AT/ST command.
    """

    return client.send_sync(msg_pack(str(cmd), _handler="execute", **kwargs))


def status(**kwargs):
    """
    Gets current connection status and more.
    """

    return client.send_sync(msg_pack(_handler="status", **kwargs))


def battery(**kwargs):
    """
    Gets current battery voltage
    """

    return client.send_sync(msg_pack("ELM_VOLTAGE", force=True, _converter="battery", **kwargs))


def dtc(clear=False, **kwargs):
    """
    Reads and clears Diagnostics Trouble Codes (DTCs).
    """

    if clear:
        return query("clear_dtc", **kwargs)

    return query("get_dtc", _converter="dtc", **kwargs)


def dump(**kwargs):
    """
    Dumps all messages from OBD bus to screen or file.
    """

    return client.send_sync(msg_pack(_handler="dump", **kwargs))


def recordings(**kwargs):
    """
    Lists all dumped recordings available on disk.
    """

    return client.send_sync(msg_pack(_handler="recordings", **kwargs))


def play(file, **kwargs):
    """
    Plays all messages from file on the OBD bus.
    """

    return client.send_sync(msg_pack(file, _handler="play", **kwargs))


def manage(*args, **kwargs):
    """
    Example: obd.manage worker list *
    """

    return client.send_sync(msg_pack(*args, _workflow="manage", **kwargs))

