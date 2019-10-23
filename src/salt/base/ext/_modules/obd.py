import logging

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack


__virtualname__ = "obd"

log = logging.getLogger(__name__)

client = EventDrivenMessageClient("obd")


def __virtual__():
    return __virtualname__


def __init__(opts):
    client.init(opts)


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"](__virtualname__)


def query(cmd, mode=None, pid=None, bytes=None, decoder=None, force=None, **kwargs):
    """
    Queries a given OBD command. To see supported OBD commands for your vehicle run: 'obd.commands'

    Arguments:
      - name (str): Name of the command.

    Optional arguments:
      - mode (str): Service section of the PID.
      - pid (str): Code section of the PID.
      - header (str): Identifer of message to send. If none is specifed the default OBD header will be used.
      - bytes (int): Default value is '0'.
      - decoder (str): Specific decoder to be used to process the response.
      - formula (str): Formula written in Python to convert the response.
      - unit (str): Unit of the result.
      - protocol (str): ID of specific protocol to be used to receive the data. If none is specifed the current protocol will be used.
      - baudrate (int): Specific protocol baudrate to be used. If none is specifed the current baudrate will be used.
      - verify (bool): Verify that OBD-II communication is possible with the desired protocol? Default value is 'False'.
      - force (bool): Force query of unknown command. Default is 'False'.

    Examples:
      - 'obd.query RPM'
      - 'obd.query SPEED'
      - 'obd.query FUEL_LEVEL force=True'
      - 'obd.query custom_intake_temp_raw mode=01 pid=0F'
      - 'obd.query custom_intake_temp mode=01 pid=0F decoder=temp'
    """

    return client.send_sync(_msg_pack(cmd, mode=mode, pid=pid, bytes=bytes, decoder=decoder, force=force, **kwargs))


def commands(**kwargs):
    """
    Lists all supported OBD commands found for vehicle.
    """

    return client.send_sync(_msg_pack(_handler="commands", **kwargs))


def status(**kwargs):
    """
    Gets current status information.
    """

    return client.send_sync(_msg_pack(_handler="status", **kwargs))


def connection(**kwargs):
    """
    Manages current connection.

    Optional arguments:
      - baudrate (int): Changes baudrate used to communicate with interface.
      - reset (str): Reboots interface and re-initializes connection. 

    Examples:
      - 'obd.connection'
      - 'obd.connection baudrate=1152000'
      - 'obd.connection reset=True'
    """

    return client.send_sync(_msg_pack(_handler="connection", **kwargs))


def protocol(**kwargs):
    """
    Configures protocol or lists all supported.

    Optional arguments:
      - set (str): Change to protocol with given identifier.
      - baudrate (int): Use custom protocol baudrate. 
      - verify (bool): Verify that OBD-II communication is possible with the desired protocol? Default value is 'False'.

    Examples:
      - 'obd.protocol'
      - 'obd.protocol set=auto'
      - 'obd.protocol set=6'
      - 'obd.connection set=53 baudrate=250000'
    """

    return client.send_sync(_msg_pack(_handler="protocol", **kwargs))


def send(msg, **kwargs):
    """
    Sends a message on bus.

    Arguments:
      - msg (str): Message to send.

    Optional arguments:
      - header (str): Identifer of message to send. If none is specifed the default OBD header will be used.
      - auto_format (bool): Apply automatic formatting of messages? Default value is 'False'.
      - expect_response (bool): Wait for response after sending? Avoid waiting for timeout by specifying the exact the number of frames expected. Default value is 'False'.
      - raw_response (bool): Get raw response without any validation nor parsing? Default value is 'False'.
      - echo (bool): Include the request message in the response? Default value is 'False'.
      - protocol (str): ID of specific protocol to be used to receive the data. If none is specifed the current protocol will be used.
      - baudrate (int): Specific protocol baudrate to be used. If none is specifed the current baudrate will be used.
      - verify (bool): Verify that OBD-II communication is possible with the desired protocol? Default value is 'False'.
      - output (str): What data type should the output be returned in? Default is a 'list'.
      - type (str): Specify a name of the type of the result. Default is 'raw'.
    """

    return client.send_sync(_msg_pack(str(msg), _handler="send", **kwargs))


def execute(cmd, **kwargs):
    """
    Executes an AT/ST command.

    Arguments:
      - cmd (str): Command to execute.

    Optional arguments:
      - assert_result (str or list): Validate the response by checking that is matches this specific value.
      - reset (str): Reset interface after execution. Valid options are: 'warm', 'cold'
      - keep_conn (bool): Keep connection to interface after execution or close it permanently? Default value is 'True'.
      - type (str): Specify a name of the type of the result. Default is the given command.
    """

    return client.send_sync(_msg_pack(str(cmd), _handler="execute", **kwargs))


def context(**kwargs):
    """
    Gets current context.
    """

    return client.send_sync(_msg_pack(_handler="context", **kwargs))


def battery(**kwargs):
    """
    Gets current battery voltage
    """

    return client.send_sync(_msg_pack("ELM_VOLTAGE", protocol=None, force=True, _converter="battery", **kwargs))


def dtc(clear=False, **kwargs):
    """
    Reads and clears Diagnostics Trouble Codes (DTCs).

    Optional arguments:
     - clear (bool): clear DTC codes
    """

    if clear:
        return query("clear_dtc", **kwargs)

    return query("get_dtc", _converter="dtc", **kwargs)


def monitor(**kwargs):
    """
    Monitors messages on bus until limit or duration is reached.

    Optional arguments:
      - wait (bool): Wait for each message/line to read according to the default timeout of the serial connection (default 1 second). Otherwise there will only be waiting on the first line. line/message. Default value is 'False'.
      - limit (int): The maximum number of messages to read. Default value is '500'.
      - duration (float): How many seconds to monitor? If not set there is no limitation.
      - mode (int): The STN monitor mode. Default is '0'.
      - auto_format (bool): Apply automatic formatting of messages? Default value is 'False'.
      - filtering (bool): Use filters while monitoring or monitor all messages? Default value is 'False'.
      - protocol (str): ID of specific protocol to be used to receive the data. If none is specifed the current protocol will be used.
      - baudrate (int): Specific protocol baudrate to be used. If none is specifed the current baudrate will be used.
      - verify (bool): Verify that OBD-II communication is possible with the desired protocol? Default value is 'False'.
      - type (str): Specify a name of the type of the result. Default is 'raw'.
    """

    return client.send_sync(_msg_pack(_handler="monitor", **kwargs))


def filter(action, **kwargs):
    """
    Manages filters used when monitoring.

    Arguments:
      - action (str): Action to perform. Available actions are 'list', 'add' and 'clear'.

    Examples:
      - 'obd.filter list'
      - 'obd.filter add type=<pass|block|flow> pattern=7C8 mask=7FF'
      - 'obd.filter clear [type=<pass|block|flow>]'
    """

    return client.send_sync(_msg_pack(action, _handler="filter", **kwargs))


def dump(**kwargs):
    """
    Dumps all messages from bus to screen or file.

    Optional arguments:
      - duration (int): How many seconds to record data? Default value is '2' seconds.
      - file (str): Write data to a file with the given name.
      - description (str): Additional description to the file.
      - protocol (str): ID of specific protocol to be used to receive the data. If none is specifed the current protocol will be used.
      - baudrate (int): Specific protocol baudrate to be used. If none is specifed the current baudrate will be used.
      - verify (bool): Verify that OBD-II communication is possible with the desired protocol? Default value is 'False'.
    """

    return client.send_sync(_msg_pack(_handler="dump", **kwargs))


def recordings(**kwargs):
    """
    Lists all dumped recordings available on disk.
    """

    return client.send_sync(_msg_pack(_handler="recordings", **kwargs))


def play(file, **kwargs):
    """
    Plays all messages from a file on the bus.

    Arguments:
      - file (str): Path to file recorded with the 'obd.dump' command.

    Optional arguments:
      - delay (float): Delay in seconds between sending each message. Default value is '0'.
      - slice (str): Slice the list of messages before sending on the CAN bus. Based one the divide and conquer algorithm. Multiple slice characters can be specified in continuation of each other.
        - 't': Top half of remaining result.
        - 'b': Bottom half of remaining result.
      - filter (str): Filter out messages before sending on the CAN bus. Multiple filters can be specified if separated using comma characters.
        - '+[id][#][data]': Include only messages matching string.
        - '-[id][#][data]': Exclude messages matching string.
        - '+duplicate': Include only messages where duplicates exist.
        - '-duplicate': Exclude messages where duplicates exist.
        - '+mutate': Include only messages where data mutates.
        - '-mutate': Exclude messages where data mutates.
      - group (str): How to group the result of sent messages. This only affects the display values returned from this command. Default value is 'id'.
        - 'id': Group by message ID only.
        - 'msg': Group by entire message string.
      - protocol (str): ID of specific protocol to be used to send the data. If none is specifed the current protocol will be used.
      - baudrate (int): Specific protocol baudrate to be used. If none is specifed the current baudrate will be used.
      - verify (bool): Verify that OBD-II communication is possible with the desired protocol? Default value is 'False'.
      - test (bool): Run command in test-only? (dry-run) mode. No data will be sent on CAN bus. Default value is 'False'.
    """

    return client.send_sync(_msg_pack(file, _handler="play", **kwargs))


def manage(*args, **kwargs):
    """
    Example: 'obd.manage worker list *'
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))

