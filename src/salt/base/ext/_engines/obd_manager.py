from __future__ import division

import battery_util
import ConfigParser
import cProfile as profile
import datetime
import _strptime  # Attempt to avoid: Failed to import _strptime because the import lockis held by another thread
import elm327_proxy
import io
import json
import logging
import math
import obd
import os
import psutil
import re
import RPi.GPIO as gpio
import salt.loader
import signal
import subprocess
import time

from collections import OrderedDict
from common_util import abs_file_path, add_rotating_file_handler_to, factory_rendering, fromisoformat
from obd.utils import OBDError
from obd_conn import OBDConn, decode_can_frame_for, FILTER_TYPE_CAN_PASS, FILTER_TYPE_J1939_PGN
from messaging import EventDrivenMessageProcessor, extract_error_from, filter_out_unchanged
from threading_more import intercept_exit_signal
from timeit import default_timer as timer


log = logging.getLogger(__name__)

home_dir = "/opt/autopi/obd"

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
        "critical_limit": 0,
        "nominal_voltage": 0
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
    },
    "export": {
        "state": ""
    }
}

# Message processor
edmp = EventDrivenMessageProcessor("obd", context=context, default_hooks={"workflow": "extended", "handler": "query"})

# OBD connection is instantiated during start
conn = None

# ELM327 proxy instance
proxy = elm327_proxy.ELM327Proxy()

# Loaded CAN databases indexed by procotol ID
can_db_cache = {}

export_subprocess = None


def _can_db_for(protocol):
    """
    Helper function to find cached CAN database instance or load it from file.
    The CAN database file (.dbc) is found on the local file system by the following path expression:

        /opt/autopi/obd/can/db/protocol_<PROTOCOL ID>.dbc
    """

    ret = can_db_cache.get(protocol.ID, None)
    if not ret:
        import cantools

        # Check for override (prefixed with underscore)
        path = os.path.join(home_dir, "can/db", "_protocol_{:}.dbc".format(protocol.ID))
        if os.path.isfile(path):
            log.warning("Using overridden CAN database file '{:}'".format(path))
        else:
            path = os.path.join(home_dir, "can/db", "protocol_{:}.dbc".format(protocol.ID))

        # Load file
        conf = context["settings"].get("can_db", {}).get("protocol_configs", {}).get(protocol.ID, {})
        ret = cantools.db.load_file(path, **conf)
        log.info("Loaded CAN database from file '{:}' with configuration: {:}".format(path, conf))

        # Put into cache
        can_db_cache[protocol.ID] = ret

    return ret


def _ensure_filtering(ident):
    """
    Helper method to ensure filtering.
    """

    # Skip if boolean
    if not isinstance(ident, str):
        return

    if ident == "auto":
        conn.interface().auto_filtering(enable=True)
    elif ident == "can":
        conn.sync_filters_with(_can_db_for(conn.cached_protocol), FILTER_TYPE_CAN_PASS)
    elif ident == "j1939":
        conn.sync_filters_with(_can_db_for(conn.cached_protocol), FILTER_TYPE_J1939_PGN)
    else:
        raise ValueError("Unsupported filtering value - supported values are: auto, can, j1939")


@edmp.register_hook()
def query_handler(name, mode=None, pid=None, header=None, bytes=0, frames=None, strict=False, decoder=None, formula=None, unit=None, protocol=None, baudrate=None, verify=False, force=False, **kwargs):
    """
    Queries an OBD command.

    Arguments:
      - name (str): Name of the command.

    Optional arguments, general:
      - mode (str): Service section of the PID.
      - pid (str): Code section of the PID.
      - header (str): Identifer of message to send. If none is specifed the default header will be used.
      - bytes (int): Byte size of individual returned frame(s). Default value is '0'.
      - frames (int): Expected frame count to be returned?
      - strict (int): Enforce strict validation of specified 'bytes' and/or 'frames'. Default value is 'False'.
      - decoder (str): Specific decoder to be used to process the response.
      - formula (str): Formula written in Python to convert the response.
      - unit (str): Unit of the result.
      - protocol (str): ID of specific protocol to be used to receive the data. If none is specifed the current protocol will be used.
      - baudrate (int): Specific protocol baudrate to be used. If none is specifed the current baudrate will be used.
      - verify (bool): Verify that OBD-II communication is possible with the desired protocol? Default value is 'False'.
      - force (bool): Force query of unknown command. Default is 'False'.

    Optional arguments, CAN specific:
      - can_extended_address (str): Use CAN extended address.
      - can_priority (str): Set CAN priority bits of a 29-bit CAN ID.
      - can_flow_control_clear (bool): Clear all CAN flow control filters and ID pairs before adding any new ones.
      - can_flow_control_filter (str): Ensure CAN flow control filter is added. Value must consist of '<Pattern>,<Mask>'.
      - can_flow_control_id_pair (str): Ensure CAN flow control ID pair is added. Value must consist of '<Transmitter ID>,<Receiver ID>'.

    Optional arguments, J1939 specific:
      - j1939_pgn_filter (str): Ensure J1939 PGN filter is added. Value must consist of '<PGN>[,<Target Address>]'.
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
    cmd.frames = frames
    cmd.strict = strict

    # Ensure protocol
    if protocol in [str(None), "null"]:  # Allow explicit skip - exception made for 'ELM_VOLTAGE' command which requires no active protocol
        pass
    else:
        conn.ensure_protocol(protocol, baudrate=baudrate, verify=verify)

    # Check if command is supported
    if not cmd in conn.supported_commands() and not force:
        raise Exception("Command may not be supported - add 'force=True' to run it anyway")

    res = conn.query(cmd, header=header, formula=formula, force=force, **kwargs)

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
def query_many_handler(*cmds):
    """
    Queries many OBD commands in one call.
    """

    ret = {"values": []}

    for cmd in cmds:
        res = query_handler(*cmd.get("args", []), **cmd.get("kwargs", {}))
        ret["values"].append(res)

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
      - auto_filter (bool): Ensure automatic response filtering is enabled. Default value is 'True' if no custom filters have be added.
      - expect_response (bool): Wait for response after sending? Avoid waiting for timeout by specifying the exact the number of frames expected. Default value is 'False'.
      - format_response (bool): Format response frames by separating header and data with a hash sign. Default value is 'False'.
      - raw_response (bool): Get raw response without any validation nor parsing? Default value is 'False'.
      - echo (bool): Include the request message in the response? Default value is 'False'.
      - protocol (str): ID of specific protocol to be used to receive the data. If none is specifed the current protocol will be used.
      - baudrate (int): Specific protocol baudrate to be used. If none is specifed the current baudrate will be used.
      - verify (bool): Verify that OBD-II communication is possible with the desired protocol? Default value is 'False'.
      - output (str): What data type should the output be returned in? Default is a 'list'.
      - type (str): Specify a name of the type of the result. Default is 'raw'.

    Optional arguments, CAN specific:
      - can_extended_address (str): Use CAN extended address.
      - can_priority (str): Set CAN priority bits of a 29-bit CAN ID.
      - can_flow_control_clear (bool): Clear all CAN flow control filters and ID pairs before adding any new ones.
      - can_flow_control_filter (str): Ensure CAN flow control filter is added. Value must consist of '<Pattern>,<Mask>'.
      - can_flow_control_id_pair (str): Ensure CAN flow control ID pair is added. Value must consist of '<Transmitter ID>,<Receiver ID>'.

    Optional arguments, J1939 specific:
      - j1939_pgn_filter (str): Ensure J1939 PGN filter is added. Value must consist of '<PGN>[,<Target Address>]'.
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
        ret["supported"] = {cmd.name: "{:} (PID 0x{:})".format(cmd.desc, cmd.command) for cmd in conn.supported_commands() if not cmd.command.startswith("AT")}
    else:
        ret["supported"] = [cmd.name for cmd in conn.supported_commands() if not cmd.command.startswith("AT")]

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
        ret["supported"] = OrderedDict({"AUTO": {"name": "Autodetect", "interface": conn.protocol_autodetect_interface}})
        ret["supported"].update({k: {"name": v.NAME, "interface": getattr(v, "INTERFACE", None) or v.__module__[v.__module__.rfind(".") + 1:].upper()} for k, v in conn.supported_protocols().iteritems()})

    if set != None:
        conn.change_protocol(set, baudrate=baudrate, verify=verify)

    ret["current"] = conn.protocol(verify=verify)

    return ret


@edmp.register_hook()
def setup_handler(**kwargs):
    """
    Setup advanced runtime settings.

    Optional arguments, general:
      - adaptive_timing (int): Set adaptive timing mode. Sometimes, a single OBD requests results in multiple response frames. The time between frames varies significantly depending on the vehicle year, make, and model - from as low as 5ms up to 100ms. Default value is '1' (on, normal mode).
      - response_timeout (int): When adaptive timing is on, this sets the maximum time that is to be allowed, even if the adaptive algorithm determines that the setting should be longer. In most circumstances, it is best to let the adaptive timing algorithm determine what to use for the timeout. Default value is '50' x 4ms giving a time of approximately 200ms.

    Optional arguments, CAN specific:
      - can_extended_address (str): Use CAN extended address.
      - can_priority (str): Set CAN priority bits of a 29-bit CAN ID.
      - can_flow_control_clear (bool): Clear all CAN flow control filters and ID pairs before adding any new ones.
      - can_flow_control_filter (str): Ensure CAN flow control filter is added. Value must consist of '<Pattern>,<Mask>'.
      - can_flow_control_id_pair (str): Ensure CAN flow control ID pair is added. Value must consist of '<Transmitter ID>,<Receiver ID>'.

    Optional arguments, J1939 specific:
      - j1939_pgn_filter (str): Ensure J1939 PGN filter is added. Value must consist of '<PGN>[,<Target Address>]'.
    """

    ret = {}

    # Ensure all options are applied
    conn.ensure_advanced_settings(kwargs, filter=True)

    if kwargs:
        raise Exception("Unsupported argument(s): {:}".format(", ".join(kwargs)))

    # Return all advanced runtime settings
    ret["setup"] = conn.advanced_settings()

    return ret


@edmp.register_hook()
def monitor_handler(wait=False, limit=500, duration=None, mode=0, auto_format=False, filtering=False, protocol=None, baudrate=None, verify=False, type="raw", **kwargs):
    """
    Monitors messages on bus until limit or duration is reached.

    Optional arguments:
      - wait (bool): Wait for each message/line to read according to the default timeout of the serial connection (default 1 second). Otherwise there will only be waiting on the first line/message. Default value is 'False'.
      - limit (int): The maximum number of messages to read. Default value is '500'.
      - duration (float): How many seconds to monitor? If not set there is no limitation.
      - mode (int): The STN monitor mode. Default is '0'.
      - auto_format (bool): Apply automatic formatting of messages? Default value is 'False'.
      - filtering (bool): Use filters while monitoring or monitor all messages? Default value is 'False'. It is possible to specify 'can' or 'j1939' (PGN) in order to add filters based on the messages found in a CAN database file (.dbc).
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

    # Ensure filtering
    if filtering:
        _ensure_filtering(filtering)

    # Monitor until limit is reached
    res = conn.monitor_continuously(wait=wait, limit=limit, duration=duration, mode=mode, auto_format=auto_format, filtering=filtering, **kwargs)

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
def filter_handler(action, *args, **kwargs):
    """
    Manages filters.

    Arguments:
      - action (str): Action to perform. Available actions are 'auto', 'list', 'add', 'clear' and 'sync'.
    """

    ret = {}

    action = action.lower()
    if action == "auto":
        ret["value"] = conn.interface().auto_filtering(**kwargs)
    elif action == "list":
        ret["values"] = conn.interface().list_filters(**kwargs)
    elif action == "add":
        conn.interface().add_filter(*args)
        ret["values"] = conn.interface().list_filters(**kwargs)
    elif action == "clear":
        conn.interface().clear_filters(**kwargs)
        ret["values"] = []
    elif action == "sync":
        import cantools
        can_db = cantools.db.load_file(args[0], **kwargs)
        conn.sync_filters_with(can_db, *args[1:], force=True)
    else:
        raise ValueError("Unsupported action - allowed options are: 'auto', 'list', 'add', 'clear', 'sync'")

    return ret


@edmp.register_hook()
def dump_handler(duration=2, monitor_mode=0, filtering=False, auto_format=False, raw_response=False, format_response=True, protocol=None, baudrate=None, verify=False, file=None, description=None):
    """
    Dumps all messages from bus to screen or file.

    Optional arguments:
      - duration (int): How many seconds to record data? Default value is '2' seconds.
      - file (str): Write data to a file with the given name.
      - description (str): Additional description to the file.
      - filtering (bool): Use filters while monitoring or monitor all messages? Default value is 'False'. It is possible to specify 'can' or 'j1939' (PGN) in order to add filters based on the messages found in a CAN database file (.dbc).
      - protocol (str): ID of specific protocol to be used to receive the data. If none is specifed the current protocol will be used.
      - baudrate (int): Specific protocol baudrate to be used. If none is specifed the current baudrate will be used.
      - verify (bool): Verify that OBD-II communication is possible with the desired protocol? Default value is 'False'.
      - raw_response (bool): Get raw response without any validation nor parsing? Default value is 'False'.
      - format_response (bool): Format response messages by separating header and data with a hash sign? Default value is 'True'.
    """

    ret = {}

    # Ensure protocol
    conn.ensure_protocol(protocol, baudrate=baudrate, verify=verify)

    # Ensure filtering
    if filtering:
        _ensure_filtering(filtering)

    # Play sound to indicate recording has begun
    __salt__["cmd.run"]("aplay /opt/autopi/audio/sound/bleep.wav")

    try:
        res = conn.monitor(duration=duration, mode=monitor_mode, filtering=filtering, auto_format=auto_format, raw_response=raw_response, format_response=format_response)
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


@edmp.register_hook()
def export_handler(run=None, folder=None, wait_timeout=0, monitor_filtering=False, monitor_mode=0, can_auto_format=False, read_timeout=1, serial_baudrate=None, process_nice=-2, protocol=None, baudrate=None, verify=False):
    """
    Fast export of all messages on a bus to a log file.

    Optional arguments:
      - run (bool): Specify if subprocess should be running or not. If not defined the current state will be queried.
      - folder (str): Custom folder to place export log files.
      - wait_timeout (int): Maximum time in seconds to wait for subprocess to complete. Default value is '0'.
      - monitor_filtering (bool): Use filters while monitoring or monitor all messages? Default value is 'False'. It is possible to specify 'can' or 'j1939' (PGN) in order to add filters based on the messages found in a CAN database file (.dbc).
      - monitor_mode (int): The STN monitor mode. Default is '0'.
      - can_auto_format (bool): Apply automatic formatting of messages? Default value is 'False'.
      - read_timeout (int): How long time in seconds should the subprocess wait for data on the serial port? Default value is '1'.
      - serial_baudrate (int): Specify a custom baud rate to use for the serial connection to the STN.
      - process_nice (int): Process nice value that controls the priority of the subprocess. Default value is '-2'.
      - protocol (str): ID of specific protocol to be used to receive the data. If none is specifed the current protocol will be used.
      - baudrate (int): Specific protocol baudrate to be used. If none is specifed the current baudrate will be used.
      - verify (bool): Verify that OBD-II communication is possible with the desired protocol? Default value is 'False'.
    """

    if type(conn) != OBDConn:
        raise Exception("Only relevant when using STN interface")

    ret = {}

    ctx = context.setdefault("export", {})

    folder = folder or os.path.join(home_dir, "export")

    spawn_count = 0
    def spawn_subprocess():

        # Ensure protocol
        conn.ensure_protocol(protocol, baudrate=baudrate, verify=verify)

        # Ensure filtering
        if monitor_filtering:
            _ensure_filtering(monitor_filtering)

        # Setup CAN monitoring mode
        conn.interface().set_can_monitor_mode(monitor_mode)

        # Setup CAN automatic formatting
        conn.interface().set_can_auto_format(can_auto_format)

        # Set baud rate of serial connection
        if serial_baudrate:
            conn.change_baudrate(serial_baudrate)

        # Ensure protocol folder is created
        protocol_folder = os.path.join(folder, "protocol_{:}".format(conn.cached_protocol.ID))
        if not os.path.exists(protocol_folder):
            os.makedirs(protocol_folder)

        # Start external process
        serial = conn.serial()
        cmd = [
            "/usr/bin/stn-dump",
            "-d", serial.portstr,
            "-b", str(serial.baudrate),
            "-c", "STM" if monitor_filtering else "STMA",
            "-t", str(read_timeout * 10),  # Converts from seconds to deciseconds
            "-o", os.path.join(protocol_folder, "{:%Y%m%d%H%M}.log".format(datetime.datetime.utcnow())),
            "-q",  # Quiet mode
        ]
        
        log.info("Spawning export subprocess by running command: {:}".format(" ".join(cmd)))

        return subprocess.Popen(cmd, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=lambda: os.nice(process_nice))

    global export_subprocess
    if export_subprocess == None and run:
        export_subprocess = spawn_subprocess()
        spawn_count += 1

        # Enforce wait for completion
        if wait_timeout < read_timeout + 1:
            wait_timeout = read_timeout + 1

    if export_subprocess != None:

        # Check for return code once or until wait timeout reached
        return_code = export_subprocess.poll()
        for i in range(0, wait_timeout * 10):  # Converts from seconds to deciseconds
            return_code = export_subprocess.poll()
            if return_code != None:
                break

            if wait_timeout > 0:
                time.sleep(0.1)  # Sleep one decisecond

        # Determine if running
        is_running = return_code == None

        # Update timestamp
        ctx["timestamp"] = datetime.datetime.utcnow().isoformat()

        if is_running:
            if run != None:
                if run:
                    log.info("Export subprocess is already running")
                else:
                    log.info("Sending interrupt signal to export subprocess")
                    export_subprocess.send_signal(signal.SIGINT)

                    is_running = False

        if not is_running:

            # Wait for output
            try:
                stdout, stderr = export_subprocess.communicate()
                if stdout:
                    # TODO: Improvement would be to parse individual warnings using 'parsing.into_dict_parser'
                    ret["lines"] = stdout.split("\n")

                    log.warning("Output received from export subprocess: {:}".format(ret["lines"]))
                if stderr:
                    ret["errors"] = stderr.split("\n")

                    log.error("Error(s) received from export subprocess: {:}".format(ret["errors"]))

                return_code = export_subprocess.returncode
            finally:
                export_subprocess = None

        # Determine state
        if is_running:
            ctx["state"] = "running"
        else:
            if return_code == 0:
                ctx["state"] = "completed"
            else:
                ctx["state"] = "failed"
                ctx["return_code"] = return_code

                log.error("Export subprocess failed with return code {:}".format(return_code))
    else:
        ctx["state"] = "stopped"

    ret["state"] = ctx["state"]

    return ret


# TODO HN:
#import_lock = threading.Lock()
# See: https://stackoverflow.com/questions/16740104/python-lock-with-statement-and-timeout/16782391
#@edmp.register_hook(synchronize=import_lock, timeout=1)
@edmp.register_hook(synchronize=False)
def import_handler(folder=None, limit=5000, idle_sleep=0, cleanup_grace=60, process_nice=0, type="raw"):
    """
    Fast import of exported log files containing messages from a bus.

    Optional arguments:
      - folder (str): Custom folder to import log files from.
      - limit (int): The maximum number of lines/messages to read each time. Default value is '5000'.
      - idle_sleep (int): Pause in seconds if there is no lines/messages to import. Default value is '0'.
      - cleanup_grace (int): Grace period in seconds before a fully imported log file is deleted. Default value is '60'.
      - process_nice (int): Process nice value that controls the priority of the service. Default value is '0'.
      - type (str): Specify a name of the type of the result. Default is 'raw'.
    """

    ret = {
        "_type": type,
        "values": []
    }

    # Determine working folder
    folder = folder or os.path.join(home_dir, "export", "protocol_{:}".format(conn.cached_protocol.ID) if conn.cached_protocol else ".")
    if not os.path.isdir(folder):
        raise Warning("Folder '{:}' does not exist".format(folder))

    # Try determine protocol from folder path
    match = re.search(r"protocol_(?P<id>[0-9A]{1,2})", folder)
    if match:
        ret["protocol"] = match.group("id")

    # Set process priority
    if process_nice != None and process_nice != psutil.Process(os.getpid()).nice():
        psutil.Process(os.getpid()).nice(process_nice)

    # Open metadata JSON file
    with open(os.path.join(folder, ".import"), "r+" if os.path.isfile(os.path.join(folder, ".import")) else "w+") as metadata_file:
        metadata = {}
        if os.path.getsize(metadata_file.name) > 0:
            try:
                metadata = json.load(metadata_file)

                if log.isEnabledFor(logging.DEBUG):
                    log.debug("Loaded import metadata from JSON file '{:}': {:}".format(metadata_file.name, metadata))

            except:
                metadata_file.seek(0)  # Ensures file pointer is at the begining
                log.exception("Failed to load import metadata from JSON file '{:}': {:}".format(metadata_file.name, metadata_file.read()))

                log.warning("Skipped any progress that was stored in the invalid import metadata JSON file '{:}'".format(metadata_file.name))

        try:
            start = timer()

            count = 0
            files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and f.endswith(".log")]

            # Remove file entries from metadata without a corresponding file in the file system
            for filename in [f for f in metadata.keys() if not f in files]:
                metadata.pop(filename)
                log.info("Removed unaccompanied file entry '{:}' from import metadata".format(filename))

            # Iterate over found files sorted by oldest first
            for filename in sorted(files):

                # Initialize metadata for file, if not already
                metadata.setdefault(filename, {})

                offset = metadata[filename].get("offset", 0)
                size = metadata[filename].get("size", offset)  # Fallback to offset value

                # Compare size/offset with current size
                if size < os.path.getsize(os.path.join(folder, filename)):

                    # Continue to next file if limit is already reached
                    if count >= limit:
                        continue

                    with open(os.path.join(folder, filename), "r") as file:
                        if offset > 0:
                            file.seek(offset)

                            log.info("File '{:}' is partially imported - continuing from offset {:}".format(file.name, offset))

                        # Read first line
                        line = file.readline()
                        while line:

                            # Ensure line ends with a newline (last line might not) 
                            if line[-1] != "\n":
                                log.info("Skipping incomplete line {:}".format(repr(line)))

                                # Set incremented size instead of offset
                                size = offset + len(line)

                                break

                            count += 1
                            offset += len(line)

                            # Try process line
                            try:
                                parts = line.split(" ", 1)

                                ret["values"].append({
                                    "_stamp": datetime.datetime.fromtimestamp(float(parts[0])).isoformat(),
                                    "value": parts[1].rstrip()
                                })

                            except:
                                log.exception("Failed to import line {:}: {:}".format(count, repr(line)))

                            # Stop if limit is reached
                            if count >= limit:
                                break

                            # Read next line
                            line = file.readline()

                        # Update metadata
                        metadata[filename]["offset"] = offset
                        metadata[filename]["size"] = size if size > offset else offset
                        metadata[filename]["timestamp"] = datetime.datetime.utcnow().isoformat()

                else:
                    if log.isEnabledFor(logging.DEBUG):
                        log.debug("File '{:}' is already fully imported".format(os.path.join(folder, filename)))

                    # Candidate for cleanup
                    if cleanup_grace > 0:
                        try:

                            # Check if expired
                            if "timestamp" in metadata[filename]:
                                delta = datetime.datetime.utcnow() - fromisoformat(metadata[filename]["timestamp"])
                                if delta.total_seconds() < cleanup_grace:
                                    continue

                            # Go ahead and delete
                            os.remove(os.path.join(folder, filename))
                            metadata.pop(filename)

                            log.info("Cleaned up imported file '{:}'".format(os.path.join(folder, filename)))

                        except:
                            log.exception("Failed to cleanup imported file '{:}'".format(os.path.join(folder, filename)))

        finally:
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Saving import metadata to JSON file '{:}': {:}".format(metadata_file.name, metadata))

            metadata_file.seek(0)  # Ensures file pointer is at the begining
            metadata_file.truncate()
            json.dump(metadata, metadata_file, indent=4, sort_keys=True)
            metadata_file.flush()

        if count > 0:
            log.info("Imported {:} line(s) in {:}".format(count, timer() - start))

            if count < limit:
                log.info("Did not import maximum data possible - sleeping for {} second(s)".format(idle_sleep))
                time.sleep(idle_sleep)
        else:

            if idle_sleep > 0:
                log.info("No data to import - sleeping for {:} second(s)".format(idle_sleep))

                time.sleep(idle_sleep)

            raise Warning("No data to import")

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
      - delay (float): Delay in milliseconds between sending each message. Default value is '0'.
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
        "count": {
            "total": 0,
            "success": 0,
            "failed": 0
        }
    }

    if not os.path.isfile(file):
        raise ValueError("File does not exist")

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
            baudrate = baudrate or header.get("baudrate", None)

        # Ensure protocol
        conn.ensure_protocol(protocol,
            baudrate=baudrate,
            verify=verify)

        start = timer()

        res = []
        if experimental:

            # For some reason this runs much faster when profiling - go firgure!
            profile.runctx("res.extend(conn.send_all(lines, delay=delay, expect_response=False, raw_response=True, auto_format=auto_format))", globals(), locals())
        else:
            res = conn.send_all(lines, delay=delay, expect_response=False, raw_response=True, auto_format=auto_format)

        # Only failed lines can have responses here
        if res:
            ret["count"]["failed"] = len(res)

            # Append error(s) to corresponding line
            for msg, errs in res:
                idx = lines.index(msg)
                lines[idx] = "{:} -> {:}".format(msg, ", ".join(errs))

        ret["count"]["success"] = len(lines) - ret["count"]["failed"]
        ret["duration"] = timer() - start

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


@edmp.register_hook(synchronize=False)
def can_converter(result):
    """
    Converts raw CAN data using the CAN database available for the current protocol.
    This converter supports both single value results as well as multiple values results.
    The CAN database file (.dbc) is found on the local file system by the following path expression:

        /opt/autopi/obd/can/db/protocol_<PROTOCOL ID>.dbc
    """

    start = timer()

    protocol = conn.supported_protocols().get(result.pop("protocol", None), conn.cached_protocol)  # NOTE: If 'protocol' key not popped the cloud returner is unable to split into separate results

    try:
        can_db = _can_db_for(protocol)
    except:
        log.exception("Skipping CAN conversion because no CAN database could be loaded for protocol '{:}'".format(protocol))

        return

    # Check for multiple values in result
    if "values" in result:

        # Try to decode CAN messages and add to list
        res = []
        fail_count = 0
        for val in result["values"]:
            val = val if isinstance(val, dict) else {"value": val}
            try:
                res.extend(decode_can_frame_for(can_db, protocol, val))
            except Exception as ex:
                log.info("Failed to decode raw CAN frame result '{:}' as a CAN message: {:}".format(val, ex))

                # Count failed
                fail_count += 1

        # Report if any failed
        if fail_count:
            log.error("{:} out of {:} raw CAN frame(s) in result failed to be decoded as CAN message(s)".format(fail_count, len(result["values"])))

        if not res:
            log.warning("No raw CAN frame(s) out of {:} value(s) in result was decoded as CAN messages".format(len(result["values"])))

            # Skip if none decoded
            return
        else:
            log.info("Converted {:}/{:} raw CAN frame(s) into {:} CAN signals in {:}".format(len(result["values"]) - fail_count, len(result["values"]), len(res), timer() - start))

        result["values"] = res

        # Clear parent type if raw
        if result.get("_type", None) == "raw":
            result.pop("_type")

    # Check for single value in result
    elif "value" in result:

        # Try to decode CAN messages
        res = None
        try:
            res = decode_can_frame_for(can_db, protocol, result)
        except Exception as ex:
            log.error("Failed to decode raw CAN frame result '{:}' as a CAN message(s): {:}".format(result, ex))

        # Skip if none decoded
        if not res:
            log.warning("No raw CAN frame in result was decoded as CAN message(s)")

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
        "level": battery_util.charge_percentage_for(voltage, nominal_voltage=context["battery"]["nominal_voltage"]),
        "state": battery_util.state_for(voltage, nominal_voltage=context["battery"]["nominal_voltage"], critical_limit=context["battery"]["critical_limit"]),
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
def alternating_dtc_filter(result):
    """
    Filters out repeating Diagnostics Trouble Codes (DTCs).
    """

    if result.get("_type", None) != "dtc":
        raise Exception("Unrecognized _type received in dtc_filter: {}".format(result["_type"]))

    ctx = context.setdefault("dtc_filter", {})

    # check for new DTCs, this will later be returned
    new_dtcs = []
    for dtc in result.get("values", []):

        # if DTC code doesn't exist in context
        if dtc["code"] not in [c["code"] for c in ctx.get("previous", [])]:
            new_dtcs.append(dtc)

    # reassign context
    ctx["previous"] = result["values"]

    if len(new_dtcs) > 0:
        result["values"] = new_dtcs
        return result


@edmp.register_hook(synchronize=False)
def realistic_speed_converter(result):
    """
    Converts speed value of 255 (max value 0xFF) to 0. Some vehicles can sporadically return value of 255.
    """

    if "value" in result and result["value"] == 255:
        result["value"] = 0

        log.info("Converted speed value of 255 to 0")

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

    if error and isinstance(error, Warning):
        log.info("Communication event trigger got a warning, skipping.")
        return

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

    # Skip empty result
    if not result:
      return

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
            if result.get("_type", None) != kind and result.get("unit", None) != "rpm":  # If unit is RPM we do accept the result
                log.error("RPM {:} event trigger got unsupported RPM type result: {:}".format(key, result))

                return

            # Log RPM result when debugging
            if log.isEnabledFor(logging.DEBUG):
                log.debug("RPM {:} event trigger got RPM result: {:}".format(key, result))

        # Check for multiple values in result
        elif "values" in result:
            for res in result["values"]:

                # TODO HN: Also accept values with unit RPM here? 

                # Only interested in RPM results
                if res.get("_type", None) != kind:
                    continue

                rpm_engine_event_trigger(res, kind=kind, key=key)

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
def speed_motor_event_trigger(result):
    """
    Looks for speed result and triggers motor 'vehicle/motor/[not_running|running|stopped]' event based on the value(s) found.
    This trigger supports single value results as well as multiple values results.
    This trigger is meant to be used for electric vehicles without an engine.
    """

    rpm_engine_event_trigger(result, key="motor", kind="speed")


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
@intercept_exit_signal
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting OBD manager with settings: {:}".format(settings))

        # Also store settings in context
        context["settings"] = settings

        # Give process higher priority - this can lead to process starvation on RPi Zero (single core)
        psutil.Process(os.getpid()).nice(settings.get("process_nice", -2))

        # Setup battery critical level settings
        battery_critical_level = settings.get("battery_critical_level", {})
        context["battery"]["event_thresholds"][battery_util.CRITICAL_LEVEL_STATE] = battery_critical_level.get("duration", 180)
        context["battery"]["critical_limit"] = battery_critical_level.get("voltage", battery_util.DEFAULT_CRITICAL_LIMIT)
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Battery critical limit is {:}V in {:} sec(s)".format(context["battery"]["critical_limit"], context["battery"]["event_thresholds"][battery_util.CRITICAL_LEVEL_STATE]))
        context["battery"]["nominal_voltage"] = settings.get("battery_nominal_voltage", battery_util.DEFAULT_NOMINAL_VOLTAGE)

        # Initialize message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        edmp.measure_stats = settings.get("measure_stats", False) 

        # Initialize OBD connection
        global conn
        conn_settings = {}
        if "can_conn" in settings:
            from can_obd_conn import SocketCAN_OBDConn
            conn = SocketCAN_OBDConn(__salt__)
            conn.on_status = lambda status, data: edmp.trigger_event(data, "system/obd/{:s}".format(status))

            conn_settings = settings["can_conn"]
        else:
            conn = OBDConn()
            conn.on_status = lambda status, data: edmp.trigger_event(data, "system/stn/{:s}".format(status))

            conn_settings = settings["serial_conn"]

        # Configure OBD connection
        conn.on_closing = lambda: edmp.worker_threads.do_for_all_by("*", lambda t: t.pause(), force_wildcard=True)  # Pause all worker threads
        # IMPORTANT: If the STN UART wake trigger is enabled remember to ensure the RPi does not accidentally re-awaken the STN during shutdown!
        if "stn_state_pin" in settings:

            # Prepare GPIO to listen on the STN state input pin
            gpio.setwarnings(False)
            gpio.setmode(gpio.BOARD)
            gpio.setup(settings["stn_state_pin"]["board"], gpio.IN)

            def on_ensure_open(is_open):
                if is_open:

                    # Check if the STN is powered off/sleeping (might be due to low battery)
                    if gpio.input(settings["stn_state_pin"]["board"]) != settings["stn_state_pin"]["level"]:
                        log.warn("Closing OBD connection permanently because the STN has powered off")
                        conn.close(permanent=True)

                        raise Warning("OBD connection closed permanently because the STN has powered off")

                    if export_subprocess:
                        raise Warning("OBD connection is currently used by export subprocess")

            conn.on_ensure_open = on_ensure_open
        conn.setup(protocol=settings.get("protocol", {}),
            advanced=settings.get("advanced", {}),
            **conn_settings)

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
                        threads = edmp.worker_threads.do_for_all_by("*", lambda t: t.pause())
                        log.info("Paused {:} worker(s) while ELM327 proxy is in use".format(len(threads)))

                def on_disconnect(addr):
                    edmp.trigger_event({"client": "{:}:{:}".format(*addr)}, "system/elm327_proxy/disconnected")

                    if conn.is_open() and not proxy._stop:  # No reason to run when shutting down

                        if settings["elm327_proxy"].get("reset_after_use", True):
                            connection_handler(reset="cold")
                            log.info("Performed cold reset after ELM327 proxy has been in use")

                        if settings["elm327_proxy"].get("pause_workers", True):
                            threads = edmp.worker_threads.do_for_all_by("*", lambda t: t.resume())
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

    except:
        log.exception("Failed to start OBD manager")

        raise

    finally:
        log.info("Stopping OBD manager")

        # Terminate subprocess
        if export_subprocess:
            try:
                export_subprocess.terminate()
            except:
                log.exception("Failed to terminate export subprocess")

        # Stop ELM327 proxy if running
        if proxy.is_alive():
            try:
                proxy.stop()
            except:
                log.exception("Failed to stop ELM327 proxy")

        # Close OBD connection if open
        if conn and conn.is_open():
            try:
                conn.close()
            except:
                log.exception("Failed to close OBD connection")

