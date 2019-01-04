import logging
import re
import time

from datetime import datetime
from messaging import EventDrivenMessageProcessor
from serial_conn import SerialConn


log = logging.getLogger(__name__)

# Message processor
edmp = EventDrivenMessageProcessor("ec2x",
    default_hooks={"handler": "exec"})

# Serial connection
conn = SerialConn()

error_regex = re.compile("ERROR|\+(?P<type>.+) ERROR: (?P<reason>.+)")

rtc_time_regex = re.compile('^\+CCLK: "(?P<year>\d{2})/(?P<month>\d{2})/(?P<day>\d{2}),(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?P<tz>[+|-]\d+)"$')
# Example: +CCLK: "08/01/04,00:19:43+00"

network_time_regex = re.compile('^\+QLTS: "(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2}),(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?P<tz>[+|-]\d+),(?P<dst>\d+)"$')
# Example: +QLTS: "2017/01/13,03:40:48+32,0"

context = {
    "time": {
        "state": None
    }
}


def _exec(cmd, ready_words=["OK"], keep_conn=True, cooldown_delay=None):
    log.debug("Executing: %s", cmd)

    res = None

    try:
        conn.write_line(cmd)

        for ready_word in ready_words:
            res = conn.read(ready_word, error_regex)

            if "error" in res:
                break

        log.debug("Got result: %s", res)

    finally:
        if not keep_conn:
            log.debug("Closing AT serial connection")
            conn.close()

    # Wait if cooldown delay is defined
    if cooldown_delay != None:
        log.info("Sleeps for {:f} seconds according to specified cooldown delay".format(cooldown_delay))
        time.sleep(cooldown_delay)

    return res


@edmp.register_hook()
def exec_handler(cmd, **kwargs):
    return _exec(cmd, **kwargs)


@edmp.register_hook()
def power_handler(cmd, reason="unknown"):
    # We need to give the module a cooldown period of 30 secs to power off completely and prevent
    # new requests when not ready. If an open serial connection exists during power off it will block
    # everything when using an USB hub connected to the RPi's built-in USB - yup, go figure!

    # TODO: We also need to close NMEA serial connection to prevent system freeze
    #global nmea_conn
    #nmea_conn.close()
    #nmea_conn = None

    log.warn("Powering down EC2X module - will restart momentartily")

    # TODO: Sometimes raises SerialException: device reports readiness to read but returned no data (device disconnected or multiple access on port?)
    res = _exec(cmd, ready_words=["OK", "POWERED DOWN"], keep_conn=False, cooldown_delay=30)

    # Trigger power off event
    edmp.trigger_event({
        "reason": reason,
    }, "system/device/ec2x/power_off")

    return res


@edmp.register_hook()
def upload_handler(cmd, src):

    content = None
    with open(src, mode="rb") as f:
        content = f.read()

    conn.write_line(cmd)
    res = conn.read("CONNECT", error_regex)

    if "error" in res:
        return res

    conn.serial().write(content)

    res = conn.read("OK", error_regex, echo_on=False)

    return res


@edmp.register_hook()
def download_handler(cmd, size, dest):

    conn.write_line(cmd)
    res = conn.read("CONNECT", error_regex)

    if "error" in res:
        return res

    content = conn.serial().read(size)

    res = conn.read("OK", error_regex, echo_on=False)
    if not "error" in res:
        with open(dest, mode="wb") as f:
            f.write(content)

    return res


@edmp.register_hook()
def sync_time_handler(force=False):

    ret = {}

    ctx = context["time"]

    # Skip if time has already been synchronized
    if ctx["state"] == "synced":
        log.info("System time has already been synchronized")

        return ret

    # Check if system time is already NTP synchronized
    status = __salt__["time.status"]()
    if not force and status["ntp_synchronized"] == "yes":
        log.info("System time is already NTP synchronized")

        ret["source"] = "ntp"

        ctx["state"] = "synced"

    else:

        # We do not want below log when force
        if status["ntp_synchronized"] == "no":
            log.info("System time is not NTP synchronized")

        # Disable automatic time synchronization 
        # NOTE: This is done now to minimize time between get network time and adjust system clock 
        if status["network_time_on"] == "yes":
            __salt__["time.ntp"](enable=False)

        try:

            time = None

            # First try to get time from module's RTC
            res = _exec("AT+CCLK?")
            if not "error" in res:
                match = rtc_time_regex.match(res["data"])
                if match:
                    time = "{year:}-{month:}-{day:} {hour:}:{minute:}:{second:}".format(**match.groupdict())

                    # Validate time is within acceptable range otherwise discard it
                    if abs((datetime.utcnow() - datetime.strptime(time, "%y-%m-%d %H:%M:%S")).days) > 365:
                        log.info("Skipping invalid time retrieved from module's RTC: {:}".format(time))

                        time = None
                    else:
                        ret["source"] = "rtc"
                else:
                    log.warning("Failed to match time result from module's RTC: {:}".format(res["data"]))                
            else:
                log.warning("Unable to retrieve time from module's RTC: {:}".format(res["error"]))

            # Alternatively, try to get time from module network
            if time == None:

                # Get current UTC network time
                res = _exec("AT+QLTS=1")
                if "error" in res:
                    raise Exception("Unable to retrieve module network time: {:}".format(res["error"]))

                match = network_time_regex.match(res["data"])
                if not match:
                    raise Exception("Failed to match time result from module network: {:}".format(res["data"]))

                time = "{year:}-{month:}-{day:} {hour:}:{minute:}:{second:}".format(**match.groupdict())
                ret["source"] = "network"

            # Set old time before we adjust clock
            ret["old"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            # Set sytem time manually
            __salt__["time.set"](time, adjust_system_clock=True)

            ret["new"] = time

            log.info("Synchronized system time with time from module source '{:}'".format(ret["source"]))

            ctx["state"] = "synced"

        except:
            if ctx["state"] != "uncertain":
                ctx["state"] = "uncertain"

                # Trigger time uncertain event
                edmp.trigger_event({}, "system/time/{:}".format(ctx["state"]))

            raise

        finally:

            # Re-enable automatic time synchronization
            __salt__["time.ntp"](enable=True)

    # Trigger time synced event
    edmp.trigger_event(
        ret,
        "system/time/{:}".format(ctx["state"])
    )

    # Always update module's RTC time if synchronized from different source
    if ret["source"] != "rtc":
        res = _exec("AT+CCLK=\"{0:%y/%m/%d,%H:%M:%S}+00\"".format(datetime.utcnow()))
        if not "error" in res:
            log.info("Updated time of module's RTC")
        else:
            log.warning("Unable to update time of module's RTC: {:}".format(res["error"]))

    return ret


def start(serial_conn, **kwargs):
    try:
        log.debug("Starting EC2X manager")

        # Initialize serial connection
        conn.init(serial_conn)

        # TODO: Get workers from pillar data instead of hardcoded here (but wait until all units have engine that accept **kwargs to prevent error)
        workers = [{
            "name": "sync_time",
            "interval": 5,  # Run every 5 seconds
            "kill_upon_success": True,  # Kill after first successful run
            "messages": [
                {
                    "handler": "sync_time",
                    "kwargs": {
                        "force": False
                    }
                }
            ]
        }]

        # Initialize and run message processor
        edmp.init(__salt__, __opts__, workers=workers)
        edmp.run()

    except Exception:
        log.exception("Failed to start EC2X manager")
        raise
    finally:
        log.info("Stopping EC2X manager")
