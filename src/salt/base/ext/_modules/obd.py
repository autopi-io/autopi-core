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

    To see supported OBD commands for your vehicle run: obd.commands

    Examples:
        obd.query RPM
        obd.query SPEED
        obd.query FUEL_LEVEL force=True
        obd.query custom_intake_temp_raw mode=01 pid=0F 
        obd.query custom_intake_temp     mode=01 pid=0F decoder=temp
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

    Optional arguments:
        duration (int): How many seconds to record data? Default value is 2 seconds.
        file (str): Write data to a file with the given name.
        description (str): Additional description to the file.
        protocol (str): ID of specific protocol to be used to receive the data. If none is specifed the current protocol will be used.
        baudrate (int): Specific protocol baudrate to be used. If none is specifed the current baudrate will be used.
    """

    return client.send_sync(msg_pack(_handler="dump", **kwargs))


def recordings(**kwargs):
    """
    Lists all dumped recordings available on disk.
    """

    return client.send_sync(msg_pack(_handler="recordings", **kwargs))


def play(file, **kwargs):
    """
    Plays all messages from a file on the OBD bus.

    Arguments:
        file (str): Path to file recorded with the 'obd.dump' command.

    Optional arguments:
        delay (float): Delay in seconds between sending each message. Default value is 0.
        slice (str): Slice the list of messages before sending on the CAN bus. Based one the divide and conquer algorithm. Multiple slice characters can be specified in continuation of each other.
            Acceptable values:
              t: Top half of remaining result.
              b: Bottom half of remaining result.
        filter (str): Filter out messages before sending on the CAN bus. Multiple filters can be specified if separated using comma characters.
            Acceptable values:
                +[id][#][data]: Include only messages matching string.
                -[id][#][data]: Exclude messages matching string.
                +duplicate: Include only messages where duplicates exist.
                -duplicate: Exclude messages where duplicates exist.
                +mutate: Include only messages where data mutates.
                -mutate: Exclude messages where data mutates.
        group (str): How to group the result of sent messages. This only affects the display values returned from this command. Default value is 'id'.
            Acceptable values:
                id: Group by message ID only.
                msg: Group by entire message string.
        protocol (str): ID of specific protocol to be used to send the data. If none is specifed the current protocol will be used.
        baudrate (int): Specific protocol baudrate to be used. If none is specifed the current baudrate will be used.
        test (bool): Run command in test-only (dry-run) mode. No data will be sent on CAN bus. Default value is False.
    """

    return client.send_sync(msg_pack(file, _handler="play", **kwargs))


def manage(*args, **kwargs):
    """
    Example: obd.manage worker list *
    """

    return client.send_sync(msg_pack(*args, _workflow="manage", **kwargs))

