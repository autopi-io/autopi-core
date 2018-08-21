import logging

from messaging import EventDrivenMessageClient, msg_pack


__virtualname__ = "obd"

log = logging.getLogger(__name__)

client = EventDrivenMessageClient("elm327")


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


def execute(cmd, **kwargs):
    """
    Executes a raw command.
    """

    return client.send_sync(msg_pack(str(cmd), _handler="execute", **kwargs))


def status(**kwargs):
    """
    Get current connection status and protocol.
    """

    return client.send_sync(msg_pack(_handler="status", **kwargs))


def battery(**kwargs):
    """
    Get current battery voltage
    """

    return client.send_sync(msg_pack("ELM_VOLTAGE", _converter="battery", **kwargs))


def dtc(clear=False, **kwargs):
    """
    Readout Diagnostics Trouble Codes (DTCs).
    """

    cmd = "GET_DTC" if not clear else "CLEAR_DTC"

    res = query(cmd, **kwargs)
    if res.get("return"):
        res["return"] = {r[0]: r[1] for r in res["return"]}

    return res


def monitor(**kwargs):
    """
    Monitor all messages on OBD bus.
    """

    return client.send_sync(msg_pack(_handler="monitor", **kwargs))


def manage(*args, **kwargs):
    """
    Example: obd.manage worker list *
    """

    return client.send_sync(msg_pack(*args, _workflow="manage", **kwargs))

