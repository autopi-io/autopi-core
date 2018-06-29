import battery_util
import gpio_pin
import logging
import obd
import RPi.GPIO as gpio
import salt.loader

from elm327_conn import ELM327Conn
from messaging import EventDrivenMessageProcessor


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
def query_handler(name, mode=None, pid=None, bytes=0, decoder="raw_string", force=False, keep_conn=True):
    """
    Queries a given OBD command.
    """

    global conn

    log.debug("Querying: %s", name)

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
    if not cmd in conn.commands() and not force:
        return {
            "error": "Command may not be supported - set 'force=True' to run it anyway"
        }

    res = conn.query(cmd, force)

    log.debug("Got result: %s", res)

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

    # Close connection if requested (required when putting STN to sleep)
    if not keep_conn:
        conn.close()
        conn = None  # Ensure no UART communication that can wake up STN

        log.warn("Closed ELM327 connection upon request")

        edmp.close()  # Will kill all active workers

    return ret


@edmp.register_hook()
def commands_handler(mode=None):
    """
    Lists all supported OBD commands found for vehicle.
    """

    ret = {cmd.name: cmd.desc for cmd in conn.commands()}

    return ret


@edmp.register_hook()
def status_handler():
    """
    Get current connection status and more.
    """

    ret = {
        "connection": {
            "status": conn.status(),
            "protocol": conn.protocol()
        },
        "context": context
    }

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
