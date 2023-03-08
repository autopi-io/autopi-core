import logging
import pynmea2
import datetime

from common_util import call_retrying
from le910cx_conn import LE910CXConn
from messaging import EventDrivenMessageProcessor, extract_error_from
from threading_more import intercept_exit_signal

log = logging.getLogger(__name__)

context = {}
edmp = EventDrivenMessageProcessor("gnss", context=context, default_hooks={"workflow": "extended", "handler": "connection"})

conn = LE910CXConn()


@edmp.register_hook()
def connection_handler(cmd, *args, **kwargs):
    """
    Queries a given command down to the connection class.

    Argumnets:
      - cmd (str): The command to query.
    """

    ret = {
        "_type": cmd.lower(),
    }

    try:
        func = getattr(conn, cmd)
    except AttributeError:
        ret["error"] = "Unsupported command: {:s}".format(cmd)
        return ret

    res = call_retrying(func, args=args, kwargs=kwargs, limit=3, wait=0.2, context=context)
    if res != None:
        if isinstance(res, dict):
            ret.update(res)
        else:
            ret["value"] = res

    return ret


@edmp.register_hook()
def nmea0183_readout_handler():
    """
    Read and parse all available NMEA0183 sentences through serial connection.
    """

    ret = {
        "values": [],
    }

    # Read lines from serial connection
    lines = conn.nmea_messages()
    if not lines:
        log.warn("No NMEA0183 sentences available")
        return ret

    # Parse NMEA sentences
    for line in lines:
        try:
            obj = pynmea2.parse(line, check=True)

            ret["values"].append({
                "_type": obj.sentence_type.lower(),
                "value": obj,
            })

        except Exception:
            log.exception("Failed to parse NMEA0183 sentence: {:}".format(line))

    return ret


@edmp.register_hook()
def gnss_location_to_position_converter(result):
    """
    Converts a GNSS location result into position type.
    """

    # Validate result
    if not result:
        log.debug("Skipping empty result")
        return

    error = extract_error_from(result)
    if error:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Received error result: {}".format(error))
        return

    ret = {
        "_type": "pos",
        "_stamp": datetime.datetime.utcnow().isoformat(),
        "utc": result["time_utc"],
        "date_utc": result["date_utc"],
        "loc": {
            "lat": result["lat"],
            "lon": result["lon"]
        },
        "alt": result["alt"],
        "sog": result["sog_km"],
        "cog": result["cog"],
        "nsat": result["nsat_gps"], # need the key to be nsat because of backend structure
        "nsat_glonass": result["nsat_glonass"],
        "fix": result["fix"],
    }

    return ret


@edmp.register_hook()
def significant_position_filter(result):
    """
    Filter that only returns significant non duplicated positions.
    """

    # Validate result
    if not result:
        log.debug("Skipping empty result")
        return

    error = extract_error_from(result)
    if error:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Received error result: {}".format(error))
        return

    ctx = context.setdefault("position", {})
    old_pos = ctx.get("last_reported", None)
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

    # Update context with last reported position
    ctx["last_reported"] = new_pos

    return new_pos


@edmp.register_hook(synchronize=False)
def position_event_trigger(result):
    """
    Listens for position results and triggers position unknown/standstill/moving events.
    """

    # Validate result
    if not result:
        log.debug("Skipping empty result")
        return

    error = extract_error_from(result)
    if error:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Received error result: {}".format(error))
        # We don't want to return yet, the trigger will handle the error state

    ctx = context.setdefault("position", {})

    old_state = ctx.get("state", None)
    new_state = None

    old_error = ctx.get("error", None)
    new_error = None

    # Determine new state
    if error:
        new_state = "unknown"
        new_error = str(error)
    elif result.get("sog", 0) > 0:
        new_state = "moving"
    else:
        new_state = "standstill"

    # Check if state has chaged since last known state
    if old_state != new_state or old_error != new_error:
        ctx["state"] = new_state
        ctx["error"] = new_error

        # Trigger event
        edmp.trigger_event(
            {"reason": ctx["error"]} if ctx["error"] else {},
            "vehicle/position/{:s}".format(ctx["state"]))


@edmp.register_hook()
def nmea_gga_to_dict_converter(msg):
    """
    Parses NMEA0183 GGA messages to a dictionary that can be serialized.

    Example values:
    $GPGGA,143824.00,5702.167555,N,00956.116128,E,1,09,0.6,13.9,M,43.0,M,,*55
    $GPGGA,,,,,,0,,,,,,,,*66
    """

    return {
        "utc": msg.timestamp.isoformat(),
        "loc": {
            "lat": msg.latitude,
            "lon": msg.longitude,
        },
        "alt": float(msg.altitude),
        "nsat": int(msg.num_sats),
    }


@edmp.register_hook()
def nmea_vtg_to_dict_converter(msg):
    """
    Parses NMEA0183 VTG messages to a dictionary that can be serialized.

    Example values:
    $GPVTG,,T,0.3,M,0.0,N,0.0,K,A*0E
    $GPVTG,,T,,M,,N,,K,N*2C
    """

    return {
        "sog": msg.spd_over_grnd_kmph,
        "cog": 0 #TODO
    }


@intercept_exit_signal
def start(**settings):
    try:
        global conn
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting GNSS manager with settings: {}".format(settings))

        # Init connection
        conn.init(settings["serial_conn"])
        if settings.get("trigger_events", True):
            conn.on_error = lambda ex: edmp.trigger_event({"message": str(ex), "path": settings["serial_conn"].get("device", None)}, "system/device/le910cx/error")

        # Init and start message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))

        edmp.run()

    except Exception as ex:
        log.exception("Failed to start GNSS manager")

        if settings.get("trigger_events", True):
            edmp.trigger_event({
                "reason": str(ex),
            }, "system/service/{:}/failed".format(__name__.split(".")[-1]))
        
        raise

    finally:
        log.info("Stopping GNSS manager")

        if conn.is_open():
            try:
                # Finally, close connection
                conn.close()
            except:
                log.exception("Failed to close LE910CX connection")
