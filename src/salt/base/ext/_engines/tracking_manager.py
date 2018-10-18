import datetime
import logging
import pynmea2
import salt.loader

from messaging import EventDrivenMessageProcessor
from salt_more import SuperiorCommandExecutionError
from serial_conn import SerialConn


log = logging.getLogger(__name__)

# Message processor
edmp = EventDrivenMessageProcessor("tracking", default_hooks={"workflow": "extended"})

# Serial connection
conn = SerialConn()

returner_func = None

context = {
    "position": {
        "state": None,  # Available states: unknown|standstill|moving
        "last_recorded": None,
        "last_reported": None,
    }
}


@edmp.register_hook(synchronize=False)
def status_handler():
    """
    Get current connection status and more.
    """

    ret = {
        "connection": {
            "open": conn.is_open()
        },
        "context": context
    }

    return ret


@edmp.register_hook()
def nmea0183_readout_handler():
    """
    Reads all available NMEA0183 sentences through serial connection.
    """

    ret = {}

    # Read lines from serial connection
    lines = conn.read_lines()
    if not lines:
        log.warn("No NMEA0183 sentences available")

        return ret

    # Parse NMEA sentences
    for line in lines:
        try:
            obj = pynmea2.parse(line, check=True)

            # Put into dict indexed by type
            name = obj.__class__.__name__.lower()
            if name in ret:
                if isinstance(ret[name], list):
                    ret[name].append(obj)
                else:
                    ret[name] = [ret[name], obj]
            else:
                ret[name] = obj

        except Exception:
            log.exception("Failed to parse NMEA0183 sentence: {:}".format(line))

    return ret


@edmp.register_hook()
def nmea0183_readout_to_position_converter(result):
    """
    Converts NMEA0183 sentences result into position type.
    """

    ret = {
        "_type": "pos",
        "_stamp": datetime.datetime.utcnow().isoformat(),
    }

    # Add general fix information
    if not "gga" in result:
        log.warn("No GGA sentence found in result")
    elif result["gga"].gps_qual > 0:
        ret["utc"] = result["gga"].timestamp.isoformat()
        ret["loc"] = {
            "lat": result["gga"].latitude,
            "lon": result["gga"].longitude,
        }
        ret["alt"] = float(result["gga"].altitude)
        ret["nsat"] = int(result["gga"].num_sats)

    # Add vector track data
    if "vtg" in result:
        ret["sog"] = result["vtg"].spd_over_grnd_kmph
        ret["cog"] = 0 #result["vtg"].  # TODO

    return ret


@edmp.register_hook()
def gnss_query_handler(cmd, *args, **kwargs):
    """
    Reads GNSS data and settings synchronously from EC2X module.
    """

    try:
        return __salt__["ec2x.gnss_{:s}".format(cmd)](*args, **kwargs)
    except SuperiorCommandExecutionError as scee:
        if scee.data.get("type", None) == "CME" and \
            scee.data.get("reason", None) in ["516", "Not fixed now"]:
            return {"error": "no_fix"}
        return {"error": str(scee)}
    except Exception as e:
        return {"error": str(e)}


@edmp.register_hook()
def gnss_location_to_position_converter(result):
    """
    Converts a GNSS location result into position type.
    """

    if "error" in result:

        # Return empty position when no fix (to be used by listener to trigger position unknown state)
        if result["error"] == "no_fix":
            return {"_type": "pos"}

        log.warn("Unable to determine GNSS location: {:}".format(result["error"]))
        return

    ret = {
        "_type": "pos",
        "_stamp": result["_stamp"],
        "utc": result["time_utc"],
        "loc": {
            "lat": result["lat"],
            "lon": result["lon"]
        },
        "alt": result["alt"],
        "sog": result["sog_km"],
        "cog": result["cog"],
        "nsat": result["nsat"],
    }

    return ret


@edmp.register_hook()
def significant_position_returner(message, result):
    """
    Returns significant non duplicated positions to configured Salt returner module.
    """

    # First check for position with a location
    if not result or not "loc" in result:
        return

    ctx = context["position"]

    old_pos = ctx["last_reported"]
    new_pos = result

    # Update context with newly recorded position
    ctx["last_recorded"] = new_pos

    # Check whether or not position has changed since last reported
    if old_pos != None:

        # If moving check if direction/speed vector has changed
        if new_pos.get("sog", 0) > 0 and old_pos.get("sog", 0) == new_pos.get("sog", 0) and old_pos.get("cog", 0) == new_pos.get("cog", 0):
            return
        # Or when standing still check if location has changed
        # TODO: Compare with allowed deviation using: pip install geopy
        elif old_pos["loc"]["lat"] == new_pos["loc"]["lat"] and old_pos["loc"]["lon"] == new_pos["loc"]["lon"]:
            return

    # Call Salt returner module
    returner_func(new_pos, "track")

    # Update context with reported position
    ctx["last_reported"] = new_pos


@edmp.register_listener(matcher=lambda m, r: r.get("_type", None) == "pos")
def _position_listener(result):
    """
    Listens for position results and triggers position unknown/standstill/moving events.
    """

    ctx = context["position"]

    old_state = ctx["state"]
    new_state = None

    # Determine new state
    if not "loc" in result:
        new_state = "unknown"
    elif result.get("sog", 0) > 0:
        new_state = "moving"
    else:
        new_state = "standstill"

    # Check if state has chaged since last known state
    if old_state != new_state:
        ctx["state"] = new_state

        # Trigger event
        edmp.trigger_event({},
            "position/{:s}".format(ctx["state"]))


def start(serial_conn, returner, workers, **kwargs):
    try:
        log.debug("Starting tracking manager")

        # Prepare returner function
        global returner_func
        returner_func = salt.loader.returners(__opts__, __salt__)["{:s}.returner_raw".format(returner)]

        # Initialize serial connection
        conn.init(serial_conn)

        # Initialize and run message processor
        edmp.init(__opts__, workers=workers)
        edmp.run()

    except Exception:
        log.exception("Failed to start tracking manager")
        raise
    finally:
        log.info("Stopping tracking manager")
