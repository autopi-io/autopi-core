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

from obd_conn import OBDConn
from messaging import EventDrivenMessageProcessor
from timeit import default_timer as timer


log = logging.getLogger(__name__)

# Message processor
edmp = EventDrivenMessageProcessor("obd", default_hooks={"workflow": "extended", "handler": "query"})

# OBD connection
conn = OBDConn()

returner_func = None

context = {
    "engine": {
        "state": ""
    },
    "battery": {
        "state": "",
        "recurrences": 0,
        "recurrence_thresholds": {
            "*": 3,  # Default is three repetitions
            battery_util.CRITICAL_LEVEL_STATE: 60
        },
        "critical_limit": 0
    },
    "readout": {}
}


@edmp.register_hook()
def query_handler(name, mode=None, pid=None, bytes=0, decoder=None, force=False):
    """
    Queries an OBD command.
    """

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

    # Check if command is supported
    if not cmd in conn.supported_commands() and not force:
        raise Exception("Command may not be supported - set 'force=True' to run it anyway")

    res = conn.query(cmd, force=force)

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Got query result: %s", res)

    # Prepare return value
    ret = {
        "_type": cmd.name.lower(),
        "value": None
    }

    # Unpack command result
    if not res.is_null():
        if isinstance(res.value, obd.UnitsAndScaling.Unit.Quantity):
            ret["value"] = res.value.m
            ret["unit"] = str(res.value.u)
        else:
            ret["value"] = res.value

    return ret


@edmp.register_hook()
def send_handler(msg, **kwargs):
    """
    Sends a raw message on bus.
    """

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Sending: %s", msg)

    res = conn.send(msg, **kwargs)

    # Prepare return value(s)
    ret = {}
    if res:
        if len(res) == 1:
            ret["value"] = res[0]
        else:
            ret["values"] = res

    return ret


@edmp.register_hook()
def execute_handler(cmd, reset=None, keep_conn=True):
    """
    Executes an AT/ST command.
    """

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Executing: %s", cmd)

    res = conn.execute(cmd)

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Got execute result: {:}".format(res))

    # Reset interface if requested
    if reset:
        conn.reset(mode=reset)

    # Close connection if requested (required when putting STN to sleep)
    if not keep_conn:
        conn.close(permanent=True)
        log.warn("Closed connection permanently after executing command: {:}".format(cmd))

    # Prepare return value(s)
    ret = {}
    if res:
        if len(res) == 1:
            ret["value"] = res[0]
        else:
            ret["values"] = res

    return ret


@edmp.register_hook(synchronize=False)
def dtc_converter(res):
    """
    Converts Diagnostics Trouble Codes (DTCs) result into a cloud friendly format.
    """

    if res.get("_type", None) != "get_dtc":
        raise Exception("Unable to convert as DTC result: {:}".format(res))

    if "value" in res:
        res["_type"] = "dtc"
        res["values"] = [{"code": r[0], "text": r[1]} for r in res.pop("value")]

    return res


@edmp.register_hook()
def commands_handler(mode=None):
    """
    Lists all supported OBD commands found for vehicle.
    """

    return {cmd.name: cmd.desc for cmd in conn.supported_commands()}


@edmp.register_hook()
def protocol_handler(set=None, baudrate=None, confirm=None):
    """
    Configures protocol or lists all supported.
    """

    ret = {}

    if set == None and baudrate == None:
        ret["supported"] = {"AUTO": "Automatic"}
        ret["supported"].update(conn.supported_protocols())

    if set != None:
        id = str(set).upper()
        if id == "AUTO":
            conn.change_protocol(None)
        elif id in conn.supported_protocols():
            if not confirm == True:
                raise Exception(
                    "Please be advised that current active workers can send unwanted data with " + \
                    "the manually selected protocol - add parameter 'confirm=true' to continue anyway")

            conn.change_protocol(id, baudrate=baudrate)
        else:
            raise Exception("Unsupported protocol specified")

    ret["current"] = conn.protocol_info()

    return ret


@edmp.register_hook()
def status_handler(reset=None):
    """
    Gets current connection status and more.
    """

    if reset:
        conn.reset(mode=reset)

    ret = {
        "connection": conn.info(),
        "context": context
    }

    return ret


@edmp.register_hook()
def dump_handler(duration=2, monitor_mode=0, auto_format=False, baudrate=576000, file=None, description=None):
    """
    Dumps all messages from OBD bus to screen or file.
    """

    ret = {}

    # Check if baudrate is sufficient compared to protocol baudrate
    protocol_baudrate = conn.protocol_info().get("baudrate", 0)
    if protocol_baudrate > baudrate:
        raise Exception("Connection baudrate '{:}' is lower than protocol baudrate '{:}'".format(baudrate, protocol_baudrate))

    conn.change_baudrate(baudrate)

    # Play sound to indicate recording has begun
    __salt__["cmd.run"]("aplay /opt/autopi/audio/bleep.wav")

    try:
        res = conn.monitor_all(duration=duration, mode=monitor_mode, auto_format=auto_format)
    finally:

        # Play sound to indicate recording has ended
        __salt__["cmd.run"]("aplay /opt/autopi/audio/beep.wav")

    # Write result to file if specified
    if file != None:
        path = file if os.path.isabs(file) else os.path.join("/opt/autopi/obd", file)
        __salt__["file.mkdir"](os.path.dirname(path))

        protocol = conn.protocol_info()

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
def play_handler(file, delay=None, slice=None, filter=None, group="id", baudrate=None, test=False, experimental=False):
    """
    Plays messages from file on the OBD bus.
    """

    ret = {
        "count": {}
    }

    config_parser = ConfigParser.RawConfigParser(allow_no_value=True)
    config_parser.read(file)

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

        # Change to baudrate if given
        if baudrate != None:
            conn.change_baudrate(baudrate)

        start = timer()

        if experimental:

            # Not sure if this have any effect/improvement
            proc = psutil.Process(os.getpid())
            proc.nice(-20)

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
def battery_converter(result):
    """
    Enriches a voltage reading result with battery charge state and level.
    """

    voltage = result["value"]
    ret = {
        "_type": "bat",
        "level": battery_util.charge_percentage_for(voltage),
        "state": battery_util.state_for(voltage, critical_limit=context["battery"]["critical_limit"]),
        "voltage": voltage,
    }

    return ret


@edmp.register_hook()
def alternating_value_returner(message, result):
    """
    Returns alternating/changed values to configured Salt returner module.
    """

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

    # Call Salt returner module
    returner_func(new_read, "obd")


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
    new_state = "running" if result["value"] > 0 else "stopped"
    if old_state != new_state:
        ctx["state"] = new_state

        # Trigger event
        edmp.trigger_event({},
            "engine/{:s}".format(ctx["state"]))


@edmp.register_listener(matcher=lambda m, r: r.get("_type", None) == "bat")
def _battery_listener(result):
    """
    Listens for battery results and triggers battery state events when voltage changes.
    """

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Listener got battery result: {:}".format(result))

    ctx = context["battery"]

    # Check if state has chaged since last time
    if ctx["state"] != result["state"]:
        ctx["state"] = result["state"]
        ctx["recurrences"] = 1
    else:
        ctx["recurrences"] += 1

    # Trigger only event when battery state is repeated according to recurrence threshold
    if ctx["recurrences"] % ctx["recurrence_thresholds"].get(result["state"], ctx["recurrence_thresholds"].get("*", 2)) == 0:

        # Trigger only event if battery state (in tag) and/or level (in data) has changed
        edmp.trigger_event(
            {"level": result["level"]} if result["state"] in [battery_util.DISCHARGING_STATE, battery_util.CRITICAL_LEVEL_STATE] else {},
            "battery/{:s}".format(result["state"]),
            skip_duplicates_filter="battery/*"
        )


def start(serial_conn, returner, workers, battery_critical_limit=None, **kwargs):
    try:

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting OBD manager")

        # Prepare returner function
        global returner_func
        returner_func = salt.loader.returners(__opts__, __salt__)["{:s}.returner_raw".format(returner)]

        # Determine critical limit of battery voltage 
        context["battery"]["critical_limit"] = battery_critical_limit or battery_util.DEFAULT_CRITICAL_LIMIT
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Battery critical limit is %.1fV", context["battery"]["critical_limit"])

        # Configure connection
        conn.setup(serial_conn)
        conn.on_closing = lambda: edmp.close()  # Will kill active workers

        # Initialize and run message processor
        edmp.init(__opts__, workers=workers)
        edmp.run()

    except Exception:
        log.exception("Failed to start OBD manager")
        raise
    finally:
        log.info("Stopping OBD manager")
