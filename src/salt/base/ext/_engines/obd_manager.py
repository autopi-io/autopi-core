from __future__ import division

import battery_util
import ConfigParser
import cProfile as profile
import datetime
import elm327_proxy
import logging
import math
import obd
import os
import psutil
import salt.loader

from binascii import unhexlify
from common_util import abs_file_path, add_rotating_file_handler_to, factory_rendering
from obd.utils import OBDError
from obd_conn import OBDConn
from messaging import EventDrivenMessageProcessor, extract_error_from, filter_out_unchanged
from timeit import default_timer as timer


log = logging.getLogger(__name__)

home_dir = "/opt/autopi/obd"

# Message processor
edmp = EventDrivenMessageProcessor("obd", default_hooks={"workflow": "extended", "handler": "query"})

# OBD connection
conn = OBDConn()

# ELM327 proxy instance
proxy = elm327_proxy.ELM327Proxy()

# Loaded CAN databases indexed by procotol ID
can_db_cache = {}

context = {
    "battery": {
        "state": "",
        "count": 0,
        "timer": 0.0,
        "event_thresholds": {
            "*": 3,  # Default is three seconds
            "unknown": 0,
            battery_util.CRITICAL_LEVEL_STATE: 180
        },
        "critical_limit": 0
    },
    "readout": {},
    "monitor": {
        "count": 0,
        "readout": {
            "acc": 0,
            "avg": 0.0,
            "min": -1,
            "max": -1
        }
    }
}


@edmp.register_hook(synchronize=False)
def context_handler(key=None):
    """
    Gets current context.
    """

    if key:
        return context.get(key, None)

    return context


@edmp.register_hook()
def query_handler(name, mode=None, pid=None, header=None, bytes=0, decoder=None, formula=None, unit=None, protocol=None, baudrate=None, verify=False, force=False):
    """
    Queries an OBD command.

    Arguments:
      - name (str): Name of the command.

    Optional arguments:
      - mode (str): Service section of the PID.
      - pid (str): Code section of the PID.
      - header (str): Identifer of message to send. If none is specifed the default header will be used.
      - bytes (int): Default value is '0'.
      - decoder (str): Specific decoder to be used to process the response.
      - formula (str): Formula written in Python to convert the response.
      - unit (str): Unit of the result.
      - protocol (str): ID of specific protocol to be used to receive the data. If none is specifed the current protocol will be used.
      - baudrate (int): Specific protocol baudrate to be used. If none is specifed the current baudrate will be used.
      - verify (bool): Verify that OBD-II communication is possible with the desired protocol? Default value is 'False'.
      - force (bool): Force query of unknown command. Default is 'False'.
    """

    ret = {
        "_type": name.lower()
    }

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Querying: %s", name)

    if pid != None:
        mode = "{:02X}".format(int(str(mode), 16)) if mode != None else "01"
        pid = "{:02X}".format(int(str(pid), 16))

        cmd = obd.OBDCommand(name, None, "{:}{:}".format(mode, pid), bytes, getattr(obd.decoders, decoder or "raw_string"))
    elif obd.commands.has_name(name.upper()):
        cmd = obd.commands[name.upper()]
    else:
        cmd = obd.OBDCommand(name, None, name, bytes, getattr(obd.decoders, decoder or "raw_string"))

    # Ensure protocol
    if protocol in [str(None), "null"]:  # Allow explicit skip - exception made for 'ELM_VOLTAGE' command which requires no active protocol
        pass
    else:
        conn.ensure_protocol(protocol, baudrate=baudrate, verify=verify)

    # Check if command is supported
    if not cmd in conn.supported_commands() and not force:
        raise Exception("Command may not be supported - add 'force=True' to run it anyway")

    res = conn.query(cmd, header=header, formula=formula, force=force)

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Got query result: %s", res)

    # Unpack command result
    if not res.is_null():
        if isinstance(res.value, obd.UnitsAndScaling.Unit.Quantity):
            ret["value"] = res.value.m
            ret["unit"] = unit or str(res.value.u)
        else:
            ret["value"] = res.value
            if unit != None:
                ret["unit"] = unit

    return ret


@edmp.register_hook()
def send_handler(msg, **kwargs):
    """
    Sends a message on bus.

    Arguments:
      - msg (str): Message to send.

    Optional arguments, general:
      - header (str): Identifer of message to send. If none is specifed the default header will be used.
      - auto_format (bool): Apply automatic formatting of messages? Default value is 'False'.
      - expect_response (bool): Wait for response after sending? Avoid waiting for timeout by specifying the exact the number of frames expected. Default value is 'False'.
      - raw_response (bool): Get raw response without any validation nor parsing? Default value is 'False'.
      - echo (bool): Include the request message in the response? Default value is 'False'.
      - protocol (str): ID of specific protocol to be used to receive the data. If none is specifed the current protocol will be used.
      - baudrate (int): Specific protocol baudrate to be used. If none is specifed the current baudrate will be used.
      - verify (bool): Verify that OBD-II communication is possible with the desired protocol? Default value is 'False'.
      - output (str): What data type should the output be returned in? Default is a 'list'.
      - type (str): Specify a name of the type of the result. Default is 'raw'.

    Optional arguments, CAN specific:
      - can_extended_address (str): Use CAN extended address.
      - can_flow_control_clear (bool): Clear all CAN flow control filters and ID pairs before adding any new ones.
      - can_flow_control_filter (str): Ensure CAN flow control filter is added. Value must consist of '<pattern>,<mask>'.
      - can_flow_control_id_pair (str): Ensure CAN flow control ID pair is added. Value must consist of '<transmitter ID>,<receiver ID>'.
    """

    ret = {
        "_type": kwargs.pop("type", "raw")
    }

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Sending: %s", msg)

    # Ensure protocol
    conn.ensure_protocol(kwargs.pop("protocol", None),
        baudrate=kwargs.pop("baudrate", None),
        verify=kwargs.pop("verify", False))

    # Get desired data type for output
    output = kwargs.pop("output", "list")
    if output not in ["dict", "list"]:
        raise ValueError("Unsupported output type - supported values are 'dict' or 'list'")

    res = conn.send(msg, **kwargs)

    if res:
        if output == "dict":
            if len(res) == 1:
                ret["value"] = res[0]
            else:
                ret["values"] = {idx: val for idx, val in enumerate(res, 1)}
        else:
            ret["values"] = res

    return ret


@edmp.register_hook()
def execute_handler(cmd, assert_result=None, reset=None, keep_conn=True, type=None):
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

    ret = {
        "_type": type or cmd.lower()
    }

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Executing: %s", cmd)

    res = conn.execute(cmd)

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Got execute result: {:}".format(res))

    # Assert the result if requested
    if assert_result != None:
        if not isinstance(assert_result, list):
            assert_result = [assert_result]

        if assert_result != res:
            raise ValueError("Unexpected result: {:}".format(res))

    # Reset interface if requested
    if reset:
        conn.reset(mode=reset)

    # Close connection if requested (required when putting STN to sleep)
    if not keep_conn:
        conn.close(permanent=True)
        log.warn("Closed connection permanently after executing command: {:}".format(cmd))

    # Prepare return value(s)
    if res:
        if len(res) == 1:
            ret["value"] = res[0]
        else:
            ret["values"] = res

    return ret


@edmp.register_hook()
def commands_handler(protocol="auto", baudrate=None, verify=True, output="dict"):
    """
    Lists all supported OBD commands found for vehicle.
    """

    # Validate input
    if output not in ["dict", "list"]:
        raise ValueError("Unsupported output type - supported values are 'dict' or 'list'")

    # Ensure protocol
    conn.ensure_protocol(protocol, baudrate=baudrate, verify=verify)

    # Prepare return value
    ret = {
        "protocol": conn.protocol()
    }

    if output == "dict":
        ret["supported"] = {cmd.name: cmd.desc for cmd in conn.supported_commands()}
    else:
        ret["supported"] = [cmd.name for cmd in conn.supported_commands()]

    return ret


@edmp.register_hook()
def status_handler():
    """
    Gets current status information.
    """

    ret = {
        "connection": conn.status(),
        "protocol": conn.protocol(),
    }

    return ret


@edmp.register_hook()
def connection_handler(baudrate=None, reset=None):
    """
    Manages current connection.

    Optional arguments:
      - baudrate (int): Changes baudrate used to communicate with interface.
      - reset (str): Reboots interface and re-initializes connection. 
    """

    if baudrate != None:
        conn.change_baudrate(baudrate)

    if reset:
        conn.reset(mode=reset)

    ret = conn.status()

    return ret


@edmp.register_hook()
def protocol_handler(set=None, baudrate=None, verify=False):
    """
    Configures protocol or lists all supported.

    Optional arguments:
      - set (str): Change to protocol with given identifier.
      - baudrate (int): Use custom protocol baudrate. 
      - verify (bool): Verify that OBD-II communication is possible with the desired protocol? Default value is 'False'.
    """

    ret = {}

    if set == None and baudrate == None:
        ret["supported"] = conn.supported_protocols()

    if set != None:
        conn.change_protocol(set, baudrate=baudrate, verify=verify)

    ret["current"] = conn.protocol(verify=verify)

    return ret


@edmp.register_hook()
def setup_handler(**kwargs):
    """
    Setup advanced runtime settings.

    Optional arguments:
      - can_extended_address (str): Use CAN extended address.
      - can_flow_control_clear (bool): Clear all CAN flow control filters and ID pairs before adding any new ones.
      - can_flow_control_filter (str): Ensure CAN flow control filter is added. Value must consist of '<pattern>,<mask>'.
      - can_flow_control_id_pair (str): Ensure CAN flow control ID pair is added. Value must consist of '<transmitter ID>,<receiver ID>'.
    """

    ret = {}

    # Ensure all options are applied
    conn.ensure_runtime_settings(kwargs, filter=True)

    if kwargs:
        raise Exception("Unsupported argument(s): {:}".format(", ".join(kwargs)))

    # Return all runtime settings
    ret["runtime_settings"] = conn.runtime_settings()

    return ret


@edmp.register_hook()
def monitor_handler(wait=False, limit=500, duration=None, mode=0, auto_format=False, filtering=False, protocol=None, baudrate=None, verify=False, type="raw"):
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

    ret = {
        "_type": type
    }

    # Ensure protocol
    conn.ensure_protocol(protocol, baudrate=baudrate, verify=verify)

    # Monitor until limit reached
    res = conn.monitor_continuously(wait=wait, limit=limit, duration=duration, mode=mode, auto_format=auto_format, filtering=filtering)

    # Update context with summary
    ctx = context["monitor"]
    ctx["count"] += 1
    ctx["readout"]["acc"] += len(res)
    ctx["readout"]["avg"] = ctx["readout"]["acc"] / ctx["count"]
    if len(res) < ctx["readout"]["min"] or ctx["readout"]["min"] < 0:
        ctx["readout"]["min"] = len(res)
    if len(res) > ctx["readout"]["max"]:
        ctx["readout"]["max"] = len(res)

    # Check for received messages
    if not res:
        raise Warning("No messages received on bus")

    ret["values"] = res

    return ret


@edmp.register_hook()
def filter_handler(action, **kwargs):
    """
    Manages filters used when monitoring.

    Arguments:
      - action (str): Action to perform. Available actions are 'list', 'add' and 'clear'.
    """

    ret = {}

    action = action.lower()
    if action == "list":
        ret["values"] = conn.list_filters(type=kwargs.get("type", None))

    elif action == "add":
        conn.add_filter(kwargs.get("type", None), kwargs.get("pattern", ""), kwargs.get("mask", ""))

        ret["values"] = conn.list_filters(type=kwargs.get("type", None))

    elif action == "clear":
        conn.clear_filters(type=kwargs.get("type", None))

        ret["values"] = []

    elif action == "sync":
        import cantools
        conn.sync_filters(cantools.db.load_file(kwargs.pop("can_db_file")), **kwargs)

    else:
        raise ValueError("Unsupported action - allowed options are: 'list', 'add', 'clear', 'sync'")

    return ret


@edmp.register_hook()
def dump_handler(duration=2, monitor_mode=0, filtering=False, auto_format=False, protocol=None, baudrate=None, verify=False, file=None, description=None):
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

    ret = {}

    # Ensure protocol
    conn.ensure_protocol(protocol, baudrate=baudrate, verify=verify)

    # Play sound to indicate recording has begun
    __salt__["cmd.run"]("aplay /opt/autopi/audio/sound/bleep.wav")

    try:
        res = conn.monitor(duration=duration, mode=monitor_mode, filtering=filtering, auto_format=auto_format)
    finally:

        # Play sound to indicate recording has ended
        __salt__["cmd.run"]("aplay /opt/autopi/audio/sound/beep.wav")

    # Write result to file if specified
    if file != None:
        path = abs_file_path(file, home_dir)

        __salt__["file.mkdir"](os.path.dirname(path))

        protocol = conn.protocol(verify=verify)

        # Use config parser to write file
        config_parser = ConfigParser.RawConfigParser(allow_no_value=True)

        # Add header section
        config_parser.add_section("header")
        config_parser.set("header", "timestamp", datetime.datetime.utcnow().isoformat())
        config_parser.set("header", "duration", duration)
        config_parser.set("header", "protocol", protocol["id"])
        config_parser.set("header", "baudrate", protocol["baudrate"])
        config_parser.set("header", "count", len(res))
        if description:
            config_parser.set("header", "description", description)

        # Add message lines in data section
        config_parser.add_section("data")
        for line in res:
            config_parser.set("data", line)

        with open(path, "w") as f:
            config_parser.write(f)

            ret["file"] = f.name
    else:
        ret["data"] = res

    return ret


@edmp.register_hook(synchronize=False)
def recordings_handler(path=None):
    """
    Lists all dumped recordings available on disk.
    """

    ret = {
        "values": []
    }

    config_parser = ConfigParser.RawConfigParser(allow_no_value=True)

    path = path or home_dir
    for file in os.listdir(path):
        file_path = os.path.join(path, file)

        try:
            # TODO: Improve performance by not reading 'data' section and only 'header' section
            config_parser.read(file_path)
            header = {k: v for k, v in config_parser.items("header")}

            ret["values"].append({file_path: header})
        except ConfigParser.Error as cpe:
            log.exception("Failed to parse recording in file: {:}".format(file_path))

            ret["values"].append({file_path: {"error": str(cpe)}})

    return ret


@edmp.register_hook()
def play_handler(file, delay=None, slice=None, filter=None, group="id", protocol=None, baudrate=None, verify=False, auto_format=False, test=False, experimental=False):
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
      - auto_format (bool): Apply automatic formatting of messages? Default value is 'False'.
      - test (bool): Run command in test-only? (dry-run) mode. No data will be sent on CAN bus. Default value is 'False'.
    """

    ret = {
        "count": {}
    }

    config_parser = ConfigParser.RawConfigParser(allow_no_value=True)
    config_parser.read(file)

    header = {k: v for k, v in config_parser.items("header")}
    lines = config_parser.options("data")

    ret["count"]["total"] = len(lines)

    def group_by(mode, lines):
        ret = {}

        if mode.lower() == "id":
            for line in lines:
                id = line[:line.find("#")]
                if id in ret:
                    ret[id] += 1
                else:
                    ret[id] = 1

        elif mode.lower() == "msg":
            for line in lines:
                if line in ret:
                    ret[line] += 1
                else:
                    ret[line] = 1

        else:
            raise ValueError("Unsupported group by mode")

        return ret

    # Slice lines based on defined pattern (used for divide and conquer)
    if not slice is None:
        slice = slice.upper()

        ret["slice"] = {
            "offset": 0
        }

        # Loop through slice chars one by one
        for char in slice:
            if lines <= 1:
                break

            offset = int(math.ceil(len(lines) / 2.0))
            if char == "T":  # Top half
                lines = lines [:offset]
            elif char == "B":  # Bottom half
                lines = lines [offset:]

                ret["slice"]["offset"] += offset
            else:
                raise Exception("Unsupported slice character")

        ret["slice"]["count"] = len(lines)

    # Filter lines based on defined rules
    if not filter is None:
        filters = [f.strip() for f in filter.split(",")]

        mutate = None
        duplicate = None

        # Filter included
        incl = set()
        for f in [f[1:].upper() for f in filters if f.startswith("+")]:
            if f == "MUTATE":
                mutate = True
                continue
            elif f == "DUPLICATE":
                duplicate = True
                continue

            incl.update([l for l in lines if l.upper().startswith(f)])
        if incl:
            lines = [l for l in lines if l in incl]

        # Filter excluded
        excl = set()
        for f in [f[1:].upper() for f in filters if f.startswith("-")]:
            if f == "MUTATE":
                mutate = False
                continue
            elif f == "DUPLICATE":
                duplicate = False
                continue

            excl.update([l for l in lines if l.upper().startswith(f)])
        if excl:
            lines = [l for l in lines if l not in excl]

        # Filter mutating
        if mutate != None:
            groups = group_by("id", set(lines))
            if mutate:
                ids = set(g[0] for g in groups.items() if g[1] > 1)
                lines = [l for l in lines if l[:l.find("#")] in ids]
            else:
                ids = set(g[0] for g in groups.items() if g[1] == 1)
                lines = [l for l in lines if l[:l.find("#")] in ids]

        # Filter duplicates
        if duplicate != None:
            groups = group_by("msg", lines)
            if duplicate:
                msgs = set(g[0] for g in groups.items() if g[1] > 1)
                lines = [l for l in lines if l in msgs]
            else:
                msgs = set(g[0] for g in groups.items() if g[1] == 1)
                lines = [l for l in lines if l in msgs]

        ret["count"]["filtered"] = len(lines)

    # Send lines
    if not test:

        # Only use protocol settings from header when no protocol is specified
        if protocol == None:
            protocol = header.get("protocol", None)
            baudrate = baudrate or (header.get("baudrate", None) if conn.supported_protocols().get(str(protocol), {}).get("interface", None) != "ELM327" else None)  # ELM327 protocols does not support custom baudrates

        # Ensure protocol
        conn.ensure_protocol(protocol,
            baudrate=baudrate,
            verify=verify)

        start = timer()

        if experimental:

            # For some reason this runs much faster when profiling - go firgure!
            profile.runctx("conn.send_all(lines, delay=delay, raw_response=True, auto_format=auto_format)", globals(), locals())
        else:
            conn.send_all(lines, delay=delay, raw_response=True, auto_format=auto_format)

        ret["count"]["sent"] = len(lines)
        ret["duration"] = timer() - start
    else:
        ret["count"]["sent"] = 0

    if group:
        groups = group_by(group, lines)
        ret["output"] = [{i[1]: i[0]} for i in sorted(groups.items(), key=lambda i: (i[1], i[0]), reverse=True)]
    else:
        ret["output"] = lines

    return ret


@edmp.register_hook()
def _relay_handler(cmd):
    """
    System handler to relay commands directly to the ELM327 compatible interface.
    """

    return conn.execute(cmd, raw_response=True)


def _decode_can_frame(can_db, res):
    """
    Helper function to decode a raw CAN frame result. Note that one single CAN frame can output multiple results.
    """

    ret = []

    try:
        header, data = res["value"].split(" ", 1)

        # Find message by header
        try:
             msg = can_db.get_message_by_frame_id(int(header, 16))
        except KeyError:  # Unknown message

            return ret

        # Decode data using found message
        for key, val in msg.decode(unhexlify(data.replace(" ", "")), True, True).iteritems():
            ret.append(dict(res, _type=key.lower(), value=val))

    except:
        log.exception("Failed to decode raw CAN frame result as CAN message: {:}".format(res))

    return ret


@edmp.register_hook(synchronize=False)
def can_converter(result):
    """
    Converts raw CAN data using the CAN database available for the current protocol.
    This converter supports both single value results as well as multiple values results.
    The CAN database file (.dbc) is found on the local file system by the following path expression:

        /opt/autopi/obd/can/db/protocol_<PROTOCOL ID>.dbc
    """

    # Attempt to find cached CAN database instance or else load it from file
    protocol_id = conn.cached_protocol.ID
    can_db = can_db_cache.get(protocol_id, None)
    if not can_db:
        try:
            import cantools

            # Check for override
            path = os.path.join(home_dir, "can/db", "_protocol_{:}.dbc".format(protocol_id))
            if os.path.isfile(path):
                log.warning("Using overridden CAN database file '{:}'".format(path))
            else:
                path = os.path.join(home_dir, "can/db", "protocol_{:}.dbc".format(protocol_id))

            # Load file
            can_db = cantools.db.load_file(path)

            # Put into cache
            can_db_cache[protocol_id] = can_db

        except:
            log.exception("Skipping CAN conversion because failed to load CAN database for protocol '{:}'".format(protocol_id))

            return

    # Check for multiple values in result
    if "values" in result:

        # Try to decode CAN messages and add to list
        res = []
        for val in result["values"]:
            res.extend(_decode_can_frame(can_db,
                val if isinstance(val, dict) else {"value": val}))

        # Skip if none decoded
        if not res:
            log.warning("No CAN frames in result was decoded: {:}".format(result))

            return

        result["values"] = res

        # Clear parent type if raw
        if result.get("_type", None) == "raw":
            result.pop("_type")

    # Check for single value in result
    elif "value" in result:

        # Try to decode CAN messages
        res = _decode_can_frame(can_db, result)

        # Skip if none decoded
        if not res:
            log.warning("No CAN frames in result was decoded: {:}".format(result))

            return

        if len(res) == 1:
            result.update(res[0])
        else:
            result.pop("value")
            result["values"] = res

            # Clear parent type if raw
            if result.get("_type", None) == "raw":
                result.pop("_type")

    # No value(s) found
    else:
        log.warning("Skipping CAN conversion because no value(s) found in result: {:}".format(result))

        return

    return result


@edmp.register_hook(synchronize=False)
def battery_converter(result):
    """
    Converts a voltage reading result with battery charge state and level.
    """

    voltage = result.get("value", None)
    ret = {
        "_type": "bat",
        "level": battery_util.charge_percentage_for(voltage),
        "state": battery_util.state_for(voltage, critical_limit=context["battery"]["critical_limit"]),
        "voltage": voltage,
    }

    return ret


@edmp.register_hook(synchronize=False)
def dtc_converter(result):
    """
    Converts Diagnostics Trouble Codes (DTCs) result into a cloud friendly format.
    """

    if result.get("_type", None) != "get_dtc":
        raise Exception("Unable to convert as DTC result: {:}".format(result))

    result["_type"] = "dtc"
    result["values"] = [{"code": r[0], "text": r[1]} for r in result.pop("value", None) or []]

    return result


@edmp.register_hook(synchronize=False)
def alternating_readout_filter(result):
    """
    Filter that only returns alternating/changed results.
    """

    return filter_out_unchanged(result, context=context["readout"])


@edmp.register_hook(synchronize=False)
def communication_event_trigger(result):
    """
    Looks for error in result and triggers 'vehicle/communication/[inactive|established|disconnected]' event based on the outcome.
    """

    # Check for error result
    error = extract_error_from(result)
    if error and log.isEnabledFor(logging.DEBUG):
        log.debug("Communication event trigger got error result: {:}".format(result))

    # Check if state has chaged since last known state
    ctx = context.setdefault("communication", {})
    old_state = ctx.get("state", "")
    new_state = "established" if not error else ("disconnected" if old_state in ["disconnected", "established"] else "inactive")
    if old_state != new_state:
        ctx["state"] = new_state

        # Trigger event
        edmp.trigger_event({"reason": str(error)} if error else {},
            "vehicle/communication/{:s}".format(ctx["state"]))


@edmp.register_hook(synchronize=False)
def rpm_engine_event_trigger(result, kind="rpm", key="engine"):
    """
    Looks for RPM result and triggers 'vehicle/engine/[not_running|running|stopped]' event based on the value(s) found.
    This trigger supports single value results as well as multiple values results.
    """

    # Check for error result
    error = extract_error_from(result)
    if error:

        if log.isEnabledFor(logging.DEBUG):
            log.debug("RPM {:} event trigger got error result: {:}".format(key, result))

        # Do not return/break flow because this will trigger negative engine event

    else:  # No error found

        # Check for single value in result
        if "value" in result:

            # Skip if not a RPM result
            if result.get("_type", None) != kind:
                log.error("RPM {:} event trigger got unsupported RPM type result: {:}".format(key, result))

                return

            # Log RPM result when debugging
            if log.isEnabledFor(logging.DEBUG):
                log.debug("RPM {:} event trigger got RPM result: {:}".format(key, result))

        # Check for multiple values in result
        elif "values" in result:
            for res in result["values"]:

                # Only interested in RPM results
                if res.get("_type", None) != kind:
                    continue

                rpm_engine_event_trigger(res)

            return

        # Skip if no value(s) found
        else:
            log.error("RPM {:} event trigger could not find any value(s)".format(key))

            return

    # Check if state has chaged since last known state
    ctx = context.setdefault(key, {})
    old_state = ctx.get("state", "")
    new_state = "running" if not error and result.get("value", 0) > 0 else \
                    ("stopped" if old_state in ["stopped", "running"] else "not_running")
    if old_state != new_state:
        ctx["state"] = new_state

        # Trigger event
        edmp.trigger_event({"reason": str(error)} if error else {},
            "vehicle/{:s}/{:s}".format(key, ctx["state"]))


@edmp.register_hook(synchronize=False)
def rpm_motor_event_trigger(result):
    """
    Looks for RPM result and triggers motor 'vehicle/motor/[not_running|running|stopped]' event based on the value(s) found.
    This trigger supports single value results as well as multiple values results.
    This trigger is meant to be used for electric vehicles without an engine.
    """

    rpm_engine_event_trigger(result, key="motor")


@edmp.register_hook(synchronize=False)
def battery_event_trigger(result):
    """
    Looks for battery results and triggers 'vehicle/battery/*' event when voltage changes.
    """

    # Check for error result
    error = extract_error_from(result)
    if error:
        log.error("Battery event trigger got error result: {:}".format(result))

        state = "unknown"
    else:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Battery event trigger got battery result: {:}".format(result))

        state = result["state"]

    # Check if state has chaged since last time
    ctx = context["battery"]
    if ctx["state"] != state:
        ctx["state"] = state
        ctx["timer"] = timer()
        ctx["count"] = 1
    else:
        ctx["count"] += 1

    # Proceed only when battery state is repeated at least once and timer threshold is reached
    if ctx["count"] > 1 and timer() - ctx["timer"] >= ctx["event_thresholds"].get(state, ctx["event_thresholds"].get("*", 3)):

        # Reset timer
        ctx["timer"] = timer()

        # Prepare event data
        data = {}
        if state in [battery_util.DISCHARGING_STATE, battery_util.CRITICAL_LEVEL_STATE]:
            data["level"] = result["level"]
        elif state == "unknown" and error:
            data["reason"] = str(error)

        # Trigger only event if battery state (in tag) and/or level (in data) has changed
        edmp.trigger_event(data, "vehicle/battery/{:s}".format(state),
            skip_duplicates_filter="vehicle/battery/*"
        )


@factory_rendering
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting OBD manager with settings: {:}".format(settings))

        # Give process higher priority - this can lead to process starvation on RPi Zero (single core)
        psutil.Process(os.getpid()).nice(settings.get("process_nice", -2))

        # Setup battery critical level settings
        battery_critical_level = settings.get("battery_critical_level", {})
        context["battery"]["event_thresholds"][battery_util.CRITICAL_LEVEL_STATE] = battery_critical_level.get("duration", 180)
        context["battery"]["critical_limit"] = battery_critical_level.get("voltage", battery_util.DEFAULT_CRITICAL_LIMIT)
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Battery critical limit is {:}V in {:} sec(s)".format(context["battery"]["critical_limit"], context["battery"]["event_thresholds"][battery_util.CRITICAL_LEVEL_STATE]))

        # Initialize message processor
        edmp.init(__salt__, __opts__, hooks=settings.get("hooks", []), workers=settings.get("workers", []))
        edmp.measure_stats = settings.get("measure_stats", False) 

        # Configure OBD connection
        conn.on_status = lambda status, data: edmp.trigger_event(data, "system/stn/{:s}".format(status)) 
        conn.on_closing = lambda: edmp.worker_threads.do_all_for("*", lambda t: t.pause(), force_wildcard=True)  # Pause all worker threads
        conn.setup(protocol=settings.get("protocol", {}), **settings["serial_conn"])

        # Start ELM327 proxy if configured
        if "elm327_proxy" in settings:
            try:

                # Setup file logging if defined
                if "logging" in settings["elm327_proxy"]:
                    try:
                        file = abs_file_path(settings["elm327_proxy"]["logging"].pop("file", "elm327_proxy.log"), "/var/log/salt")
                        add_rotating_file_handler_to(elm327_proxy.log, file, **settings["elm327_proxy"]["logging"])
                    except:
                        log.exception("Failed to setup dedicated file log handler for ELM327 proxy")

                def on_connect(addr):
                    edmp.trigger_event({"client": "{:}:{:}".format(*addr)}, "system/elm327_proxy/connected")

                    if settings["elm327_proxy"].get("pause_workers", True):
                        threads = edmp.worker_threads.do_all_for("*", lambda t: t.pause())
                        log.info("Paused {:} worker(s) while ELM327 proxy is in use".format(len(threads)))

                def on_disconnect(addr):
                    edmp.trigger_event({"client": "{:}:{:}".format(*addr)}, "system/elm327_proxy/disconnected")

                    if conn.is_open() and not proxy._stop:  # No reason to run when shutting down

                        if settings["elm327_proxy"].get("reset_after_use", True):
                            connection_handler(reset="cold")
                            log.info("Performed cold reset after ELM327 proxy has been in use")

                        if settings["elm327_proxy"].get("pause_workers", True):
                            threads = edmp.worker_threads.do_all_for("*", lambda t: t.resume())
                            log.info("Resumed {:} worker(s) after ELM327 proxy has been in use".format(len(threads)))

                proxy.on_command = _relay_handler
                proxy.on_connect = on_connect
                proxy.on_disconnect = on_disconnect

                proxy.start(
                    host=settings["elm327_proxy"].get("host", "0.0.0.0"),
                    port=settings["elm327_proxy"].get("port", 35000)
                )

            except:
                log.exception("Failed to start ELM327 proxy")

        # Run message processor
        edmp.run()

    except Exception:
        log.exception("Failed to start OBD manager")

        raise

    finally:
        log.info("Stopping OBD manager")

        # First stop ELM327 proxy if running
        if proxy.is_alive():
            try:
                proxy.stop()
            except:
                log.exception("Failed to stop ELM327 proxy")

        # Then close OBD connection if open
        if conn.is_open():
            try:
                conn.close()
            except:
                log.exception("Failed to close OBD connection")

