import battery_util
import cProfile as profile
import gpio_pin
import logging
import math
import obd
import os
import psutil
import RPi.GPIO as gpio
import salt.loader

from elm327_conn import ELM327Conn
from messaging import EventDrivenMessageProcessor
from timeit import default_timer as timer


log = logging.getLogger(__name__)

# Message processor
edmp = EventDrivenMessageProcessor("elm327", default_hooks={"workflow": "extended", "handler": "query"})

# ELM327 connection
conn = ELM327Conn()

returner_func = None

context = {
    "engine": {
        "state": ""
    },
    "battery": {
        "state": "",
        "level": 0,
        "recurrences": 0,
        "recurrence_thresholds": {
            "*": 2,  # Default is two repetitions
            battery_util.CRITICAL_LEVEL_STATE: 60
        },
        "critical_limit": 0
    },
    "readout": {}
}


@edmp.register_hook()
def query_handler(name, mode=None, pid=None, bytes=0, decoder="raw_string", force=False):
    """
    Queries an OBD command.
    """

    global conn

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Querying: %s", name)

    # TODO: Move this logic to new callback function in ELM327Conn to ensure is is always called before UART activity
    # Check if STN has powered down while connection was open (might be due to low battery)
    if conn != None and conn.is_open() and gpio.input(gpio_pin.STN_PWR) == 0:
        conn.close()
        conn = None  # Ensure no UART communication that can wake up STN

        log.warn("Closed ELM327 connection because STN powered off")

        edmp.close()  # Will kill all active workers

    # Check if connection is available
    if conn == None:
        raise Warning("ELM327 connection is no longer available as it has been forcibly closed")

    if obd.commands.has_name(name.upper()):
        cmd = obd.commands[name.upper()]
    elif mode != None and pid != None:
        if obd.commands.has_pid(mode, pid):
            cmd = obd.commands[mode][pid]
        else:
            decoder = obd.decoders.raw_string  # TODO: Get this from kwarg
            cmd = obd.OBDCommand(name, None, "{:02d}{:02X}".format(mode, pid), bytes, decoder)
    else:
        decoder = obd.decoders.raw_string  # TODO: Get this from kwarg
        cmd = obd.OBDCommand(name, None, name, bytes, decoder)

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
def execute_handler(cmd, keep_conn=True):
    """
    Executes an AT/ST command.
    """

    global conn

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Executing: %s", cmd)

    # TODO: Move this logic to new callback function in ELM327Conn to ensure is is always called before UART activity
    # Check if STN has powered down while connection was open (might be due to low battery)
    if conn != None and conn.is_open() and gpio.input(gpio_pin.STN_PWR) == 0:
        conn.close()
        conn = None  # Ensure no UART communication that can wake up STN

        log.warn("Closed ELM327 connection because STN powered off")

        edmp.close()  # Will kill all active workers

    # Check if connection is available
    if conn == None:
        raise Warning("ELM327 connection is no longer available as it has been forcibly closed")

    res = conn.execute(cmd)

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Got execute result: {:}".format(res))

    # Close connection if requested (required when putting STN to sleep)
    if not keep_conn:
        conn.close()
        conn = None  # Ensure no UART communication that can wake up STN

        log.warn("Closed ELM327 connection upon request")

        edmp.close()  # Will kill all active workers

    # Prepare return value(s)
    ret = {}
    if res:
        if len(res) == 1:
            ret["value"] = res[0]
        else:
            ret["values"] = res

    return ret


@edmp.register_hook()
def commands_handler(mode=None):
    """
    Lists all supported OBD commands found for vehicle.
    """

    ret = conn.supported_commands()

    return ret


@edmp.register_hook()
def protocol_handler(set=None, baudrate=None):
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
def dump_handler(duration=2, monitor_mode=0, auto_format=False, baudrate=2304000, file=None):
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
        path = file if os.path.isabs(file) else os.path.join(__opts__["cachedir"], file)
        with open(path, "w") as f:
            for line in res:
                f.write(line + os.linesep)

            ret["file"] = f.name
    else:
        ret["data"] = res

    return ret


@edmp.register_hook()
def play_handler(file, delay=None, slice=None, filter=None, group="id", test=False):
    """
    Plays messages from file on the OBD bus.
    """

    ret = {
        "count": {}
    }

    lines = []
    with open(file, "r") as f:
        lines = f.read().splitlines()

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
        start = timer()

        # TODO: Not sure if this helps or not
        p = psutil.Process(os.getpid())
        p.nice(-20)

        # TODO: For some reason this runs much faster when profiling!
        #conn.send_all(lines, delay=delay)
        profile.runctx("conn.send_all(lines, delay=delay)", globals(), locals())

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
    if old_read != None and old_read.get("value", None) == new_read.get("value", None):
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

    # Check if state or level has chaged since last time
    if ctx["state"] != result["state"] or ctx["level"] != result["level"]:
        ctx["state"] = result["state"]
        ctx["level"] = result["level"]
        ctx["recurrences"] = 1
    else:
        ctx["recurrences"] += 1

    # Trigger only event when state and level is repeated according to recurrence threshold
    if ctx["recurrences"] == ctx["recurrence_thresholds"].get(result["state"], ctx["recurrence_thresholds"].get("*", 2)):

        # Trigger event
        edmp.trigger_event({
                "level": result["level"],
                "voltage": result["voltage"]
            },
            "battery/{:s}".format(result["state"])
        )


def start(serial_conn, returner, workers, **kwargs):
    try:

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting ELM327 manager")

        # Setup GPIO to listen on STN power pin
        gpio.setmode(gpio.BOARD)
        gpio.setup(gpio_pin.STN_PWR, gpio.IN)

        # Prepare returner function
        global returner_func
        returner_func = salt.loader.returners(__opts__, __salt__)["{:s}.returner_raw".format(returner)]

        # Determine critical limit of battery voltage 
        context["battery"]["critical_limit"] = __salt__["grains.get"]("battery:critical_limit", battery_util.DEFAULT_CRITICAL_LIMIT)
        log.info("Battery critical limit is %.1fV", context["battery"]["critical_limit"])

        # Initialize ELM327 connection
        conn.init(serial_conn)

        # Initialize and run message processor
        edmp.init(__opts__, workers=workers)
        edmp.run()

    except Exception:
        log.exception("Failed to start ELM327 manager")
        raise
    finally:
        log.info("Stopping ELM327 manager")
