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

    # Check if system time is already NTP synchronized
    res = __salt__["time.status"]()
    if not force and res["ntp_synchronized"] == "yes":
        log.info("System time is already NTP synchronized")
    else:

        if res["ntp_synchronized"] == "no":
            log.info("System time is not NTP synchronized")

        ret["old"] = " ".join(res["universal_time"].split(" ")[1:2])

        # Disable automatic time synchronization
        if res["network_time_on"] == "yes":
            __salt__["time.ntp"](enable=False)

        try:

            # Get current UTC network time
            pattern = re.compile('^\+QLTS: "(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2}),(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?P<tz>[+|-]\d+),(?P<dst>\d+)"$')
            res = _exec("AT+QLTS=1")
            if "error" in res:
                raise Exception("Unable to retrieve network time: {:}".format(res["error"]))

            match = pattern.match(res["data"])
            if not match:
                raise Exception("Failed to match network time result: {:}".format(res["data"]))

            time = "{year:d}-{month:d}-{day:d} {hour:d}:{minute:d}:{second:d}".format(**match.groupdict())

            __salt__["time.set"](time, adjust_system_clock=True)
            log.info("Synchronized system time with network time")

            ret["new"] = time

        finally:

            # Re-enable automatic time synchronization
            __salt__["time.ntp"](enable=True)

    return ret


def start(serial_conn):
    try:
        log.debug("Starting EC2X manager")

        # Initialize serial connection
        conn.init(serial_conn)

        # Attempt to sync system time with network time
        # TODO: Run in worker with an interval of 1 min?
        try
            sync_time_handler(force=False)
        except:
            log.exception("System time may be inaccurate because it could not be synchronized with network time")

        # Initialize and run message processor
        edmp.init(__opts__)
        edmp.run()

    except Exception:
        log.exception("Failed to start EC2X manager")
        raise
    finally:
        log.info("Stopping EC2X manager")
