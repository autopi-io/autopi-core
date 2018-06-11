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


def start(serial_conn):
    try:
        log.debug("Starting EC2X manager")

        # Initialize serial connection
        conn.init(serial_conn)

        # Initialize and run message processor
        edmp.init(__opts__)
        edmp.run()

    except Exception:
        log.exception("Failed to start EC2X manager")
        raise
    finally:
        log.info("Stopping EC2X manager")
