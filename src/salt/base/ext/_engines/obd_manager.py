from __future__ import division

import battery_util
import ConfigParser
import cProfile as profile
import datetime
import logging
import math
import obd
import os
import psutil
import salt.loader

from binascii import unhexlify
from common_util import abs_file_path, factory_support
from obd.utils import OBDError
from obd_conn import OBDConn
from messaging import EventDrivenMessageProcessor
from timeit import default_timer as timer


log = logging.getLogger(__name__)

# Message processor
edmp = EventDrivenMessageProcessor("obd", default_hooks={"workflow": "extended", "handler": "query"})

# OBD connection
conn = OBDConn()

# CAN database
can_db = None

context = {
    "engine": {
        "state": ""
    },
    "battery": {
        "state": "",
        "count": 0,
        "timer": 0.0,
        "event_thresholds": {
            "*": 3,  # Default is three seconds
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
def query_handler(name, mode=None, pid=None, header=None, bytes=0, decoder=None, formula=None, unit=None, protocol="auto", baudrate=None, verify=False, force=False):
    """
    Queries an OBD command.

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
      - protocol (str): ID of specific protocol to be used to receive the data. Default value is 'auto'.
      - baudrate (int): Specific protocol baudrate to be used. If none is specifed the current baudrate will be used.
      - verify (bool): Verify that OBD-II communication is possible with the desired protocol? Default value is 'False'.
      - force (bool): Force query of unknown command. Default is 'False'.
    """

    ret = {
        "_type": name.lower()
    }

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Querying: %s", name)

    if obd.commands.has_name(name.upper()):
        cmd = obd.commands[name.upper()]
    elif pid != None:
        mode = "{:02X}".format(int(str(mode), 16)) if mode != None else "01"
        pid = "{:02X}".format(int(str(pid), 16))

        if obd.commands.has_pid(mode, pid):
            cmd = obd.commands[mode][pid]
        else:
            cmd = obd.OBDCommand(name, None, "{:}{:}".format(mode, pid), bytes, getattr(obd.decoders, decoder or "raw_string"))
    else:
        cmd = obd.OBDCommand(name, None, name, bytes, getattr(obd.decoders, decoder or "raw_string"))

    # Only ensure protocol if given
    if protocol and protocol not in [str(None), "null"]:  # Workaround: Also support empty value from pillar

        # We do not want to break workflow upon failure because then listeners will not get called
        try:
            conn.ensure_protocol(protocol, baudrate=baudrate, verify=verify)
        except OBDError as err:

            if log.isEnabledFor(logging.DEBUG):
                log.debug("Failed to ensure protocol: %s", str(err))

            # IMPORTANT: By returning error result the RPM listener function will still get called for RPM results
            #            and thus always trigger appropriate engine event
            ret["error"] = str(err)

            return ret

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

    if action.lower() == "list":
        ret["values"] = conn.list_filters(type=kwargs.get("type", None))

    elif action.lower() == "add":
        conn.add_filter(kwargs.get("type", None), kwargs.get("pattern", ""), kwargs.get("mask", ""))

        ret["values"] = conn.list_filters(type=kwargs.get("type", None))

    elif action.lower() == "clear":
        conn.clear_filters(type=kwargs.get("type", None))

        ret["values"] = []

    else:
        raise ValueError("Unsupported action - allowed options are: 'list', 'add', 'clear'")

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
        path = abs_file_path(file, "/opt/autopi/obd")

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

    path = path or "/opt/autopi/obd"
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
def play_handler(file, delay=None, slice=None, filter=None, group="id", protocol=None, baudrate=None, verify=False, test=False, experimental=False):
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

            incl.update([l for l in lines if l.startswith(f)])
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

            excl.update([l for l in lines if l.startswith(f)])
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
            baudrate = baudrate or header.get("baudrate", None)

        # Ensure protocol
        conn.ensure_protocol(protocol,
            baudrate=baudrate,
            verify=verify)

        start = timer()

        if experimental:

            # For some reason this runs much faster when profiling - go firgure!
            profile.runctx("conn.send_all(lines, delay=delay)", globals(), locals())
        else:
            conn.send_all(lines, delay=delay)

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


@edmp.register_hook(synchronize=False)
def can_converter(result):
    """
    Converts raw CAN data using the CAN database if available.
    """
    
    # Skip failed results
    if "error" in result:
        return

    # Skip if not CAN database is initialized
    if can_db == None:
        log.warning("Skipping CAN conversion because no CAN database is present")

        return

    if not "values" in result:
        log.warning("Skipping CAN conversion because no values found in result: {:}".format(result))

        return

    ret = []

    # Try to decode CAN messages and add to values list
    for res in result["values"]:
        try:
            header, data = res["value"].split(" ", 1)

            # Find message by header
            try:
                 msg = can_db.get_message_by_frame_id(int(header, 16))
            except KeyError:

                # Skip unknown message
                continue

            # Decode data using found message
            for key, val in msg.decode(unhexlify(data.replace(" ", "")), True, True).iteritems():
                ret.append(dict(res, _type=key.lower(), value=val))

        except:
            log.exception("Failed to decode value as CAN message: {:}".format(res))

    return ret


@edmp.register_hook(synchronize=False)
def battery_converter(result):
    """
    Enriches a voltage reading result with battery charge state and level.
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
    Filter that only returns alternating/changed values.
    """

    # TODO HN: Move this function to 'messaging.py' and make it reusable? Or move to returner? 

    # Handle multiple results when used together with 'can_converter'
    if isinstance(result, list):
        ret = []

        for res in result:
            r = alternating_readout_filter(res)
            if r != None:
                ret.append(r)

        return ret

    # Skip failed results
    if "error" in result:
        return

    if not "_type" in result:
        log.warn("Skipping result without any type: {:}".format(result))

        return

    ctx = context["readout"]

    old_read = ctx.get(result["_type"], None)
    new_read = result

    # Update context with new read result
    ctx[result["_type"]] = result

    # Check if value is unchanged
    if old_read != None and old_read == new_read:
        return

    # Return changed value
    return new_read


@edmp.register_listener(matcher=lambda m, r: r.get("_type", None) == "rpm")
def _rpm_listener(result):
    """
    Listens for RPM results and triggers engine running/stopped events.
    """

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Listener got RPM result: {:}".format(result))

    ctx = context["engine"]

    # Check if state has chaged since last known state
    old_state = ctx["state"]
    new_state = "running" if result.get("value", 0) > 0 else \
                    ("stopped" if old_state in ["stopped", "running"] else "not_running")
    if old_state != new_state:
        ctx["state"] = new_state

        # Trigger event
        edmp.trigger_event({},
            "vehicle/engine/{:s}".format(ctx["state"]))


@edmp.register_listener(matcher=lambda m, r: r.get("_type", None) == "bat")
def _battery_listener(result):
    """
    Listens for battery results and triggers battery events when voltage changes.
    """

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Listener got battery result: {:}".format(result))

    ctx = context["battery"]

    # Check if state has chaged since last time
    if ctx["state"] != result["state"]:
        ctx["state"] = result["state"]
        ctx["timer"] = timer()
        ctx["count"] = 1
    else:
        ctx["count"] += 1

    # Proceed only when battery state is repeated at least once and timer threshold is reached
    if ctx["count"] > 1 and timer() - ctx["timer"] >= ctx["event_thresholds"].get(result["state"], ctx["event_thresholds"].get("*", 3)):

        # Reset timer
        ctx["timer"] = timer()

        # Trigger only event if battery state (in tag) and/or level (in data) has changed
        edmp.trigger_event(
            {"level": result["level"]} if result["state"] in [battery_util.DISCHARGING_STATE, battery_util.CRITICAL_LEVEL_STATE] else {},
            "vehicle/battery/{:s}".format(result["state"]),
            skip_duplicates_filter="vehicle/battery/*"
        )


@factory_rendering
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting OBD manager")

        # Give process higher priority - this can lead to process starvation on RPi Zero (single core)
        psutil.Process(os.getpid()).nice(-2)

        # Determine critical limit of battery voltage 
        context["battery"]["critical_limit"] = settings.get("battery_critical_limit", battery_util.DEFAULT_CRITICAL_LIMIT)
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Battery critical limit is %.1fV", context["battery"]["critical_limit"])

        # Initialize message processor
        edmp.init(__salt__, __opts__, returners=settings["returners"], workers=settings["workers"])
        edmp.measure_stats = settings.get("measure_stats", False) 

        # Configure OBD connection
        conn.on_status = lambda status, data: edmp.trigger_event(data, "vehicle/obd/{:s}".format(status)) 
        conn.on_closing = lambda: edmp.close()  # Will kill active workers
        conn.setup(settings["serial_conn"])  # TODO: Rename 'serial_conn' to 'obd_conn'?

        # Initialize CAN database if file is given
        if "can_db_file" in settings:
            try:
                import cantools

                global can_db
                can_db = cantools.db.load_file(settings["can_db_file"])

                # Ensure all filters are cleared
                conn.clear_filters()

                # TODO HN: Can only be added when protocol is set and verified!
                # Add pass filter for each message ID
                for msg in can_db.messages:
                    try:
                        # TODO HN: How to handle 29 bit headers here?
                        conn.add_filter("PASS", "{:03X}".format(msg.frame_id), "7FF")
                    except:
                        log.exception("Failed to add pass filter for CAN message: {:}".format(msg))

            except:
                log.exception("Failed to initialize CAN database from file '{:}'".format(settings["can_db_file"]))

        # Run message processor
        edmp.run()

    except Exception:
        log.exception("Failed to start OBD manager")
        raise
    finally:
        log.info("Stopping OBD manager")
