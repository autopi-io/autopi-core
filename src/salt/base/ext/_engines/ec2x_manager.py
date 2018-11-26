import datetime
import logging
import re
import time

from messaging import EventDrivenMessageProcessor
from serial_conn import SerialConn


log = logging.getLogger(__name__)

# Message processor
edmp = EventDrivenMessageProcessor("ec2x",
    default_hooks={"handler": "exec"})

# Serial connection
conn = SerialConn()

error_regex = re.compile("ERROR|\+(?P<type>.+) ERROR: (?P<reason>.+)")
network_time_regex = re.compile('^\+QLTS: "(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2}),(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?P<tz>[+|-]\d+),(?P<dst>\d+)"$')

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
def power_handler(cmd):
    # We need to give the module a cooldown period of 30 secs to power off completely and prevent
    # new requests when not ready. If an open serial connection exists during power off it will block
    # everything when using an USB hub connected to the RPi's built-in USB - yup, go figure!

    # TODO: We also need to close NMEA serial connection to prevent system freeze
    #global nmea_conn
    #nmea_conn.close()
    #nmea_conn = None

    # Trigger power off event
    edmp.trigger_event({}, "system/device/ec2x/power_off")

    return _exec(cmd, ready_words=["OK", "POWERED DOWN"], keep_conn=False, cooldown_delay=30)


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

    # Check if system time is already NTP synchronized
    status = __salt__["time.status"]()
    if not force and status["ntp_synchronized"] == "yes":
        log.info("System time is already NTP synchronized")

        ctx["state"] = "synced"

        # Trigger time synced event
        edmp.trigger_event(
            {"source": "ntp"},
            "system/time/{:}".format(ctx["state"])
        )

    else:

        # We do not want below log when force
        if status["ntp_synchronized"] == "no":
            log.info("System time is not NTP synchronized")

        # Disable automatic time synchronization 
        # NOTE: This is done now to minimize time between get network time and adjust system clock 
        if status["network_time_on"] == "yes":
            __salt__["time.ntp"](enable=False)

        try:

            # Get current UTC network time
            res = _exec("AT+QLTS=1")
            if "error" in res:
                raise Exception("Unable to retrieve network time: {:}".format(res["error"]))

            match = network_time_regex.match(res["data"])
            if not match:
                raise Exception("Failed to match network time result: {:}".format(res["data"]))

            time = "{year:}-{month:}-{day:} {hour:}:{minute:}:{second:}".format(**match.groupdict())

            # Set old time before we adjust clock
            ret["old"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Set time manually
            __salt__["time.set"](time, adjust_system_clock=True)

            ret["new"] = time

            log.info("Synchronized system time with network time")

            ctx["state"] = "synced"

            # Trigger time synced event
            edmp.trigger_event({
                    "source": "ec2x",
                    "old": ret["old"],
                    "new": ret["new"],
                },
                "system/time/{:}".format(ctx["state"])
            )

        except:
            if ctx["state"] != "uncertain":
                ctx["state"] = "uncertain"

                # Trigger time uncertain event
                edmp.trigger_event({}, "system/time/{:}".format(ctx["state"]))

            raise

        finally:

            # Re-enable automatic time synchronization
            __salt__["time.ntp"](enable=True)

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
        edmp.init(__opts__, workers=workers)
        edmp.run()

    except Exception:
        log.exception("Failed to start EC2X manager")
        raise
    finally:
        log.info("Stopping EC2X manager")
