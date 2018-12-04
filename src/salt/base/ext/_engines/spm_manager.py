import gpio_pin
import logging
import os
import psutil
import RPi.GPIO as gpio
import time

from messaging import EventDrivenMessageProcessor
from spm_conn import SPMConn


log = logging.getLogger(__name__)

# Message processor
edmp = EventDrivenMessageProcessor("spm", default_hooks={"handler": "query"})

# SPM connection
conn = SPMConn()

context = {
    "state": None
}


@edmp.register_hook()
def query_handler(cmd, **kwargs):
    """
    Query/call a SPM function.
    """

    ret = {
        "_type": cmd.lower(),
    }

    try:
        func = getattr(conn, cmd)
    except AttributeError:
        ret["error"] = "Unsupported command: {:s}".format(cmd)
        return ret

    res = func(**kwargs)
    if res != None:
        if isinstance(res, dict):
            ret.update(res)
        else:
            ret["value"] = res

    return ret


@edmp.register_hook()
def heartbeat_handler():
    """
    Trigger heartbeat and fire power on event when booting.
    """

    try:

        # Check if not in state on
        if context["state"] != "on":

            # Get current status
            res = conn.status()

            old_state = context["state"]
            new_state = res["last_state"]["up"]

            # On first time only
            if old_state == None:

                # Trigger last off state event if last boot time is found
                try:
                    boot_time = __salt__["rpi.boot_time"]().get("value", None)
                    if boot_time == None:
                        log.warning("Last boot time could not be determined")
                    else:
                       # Last boot time is considered identical to last power off time because of 'fake-hwclock'
                        edmp.trigger_event({
                            "timestamp": boot_time
                        }, "system/power/last_off")
                except:
                    log.exception("Failed to trigger last system off event")

                # Trigger recover state event
                if res["last_trigger"]["down"] not in ["none", "rpi"]:
                    edmp.trigger_event({
                        "trigger": res["last_trigger"]["down"]
                    }, "system/power/recover")

            # Check if state has changed
            if old_state != new_state:
                context["state"] = new_state

                # Trigger state event
                edmp.trigger_event({
                    "trigger": res["last_trigger"]["up"]
                }, "system/power/{:}{:}".format("_" if new_state in ["booting"] else "", new_state))

    finally:

        # Trigger heartbeat as normal
        conn.noop()


@edmp.register_hook()
def flash_firmware_handler(hex_file, no_write=True):
    """
    Flash new SPM firmware to ATtiny.
    """

    ret = {}

    gpio.setmode(gpio.BOARD)
    gpio.setup(gpio_pin.HOLD_PWR, gpio.OUT)

    try:

        log.info("Setting GPIO output pin {:} high".format(gpio_pin.HOLD_PWR))
        gpio.output(gpio_pin.HOLD_PWR, gpio.HIGH)

        params = ["avrdude", "-p t24", "-c autopi", "-U flash:w:{:s}".format(hex_file)]
        if no_write:
            params.append("-n")

        res = __salt__["cmd.run_all"](" ".join(params))

        if res["retcode"] == 0:
            ret["output"] = res["stderr"]
        else:
            ret["error"] = res["stderr"]
            ret["output"] = res["stdout"]

        if not no_write:
            log.info("Flashed firmware release '{:}'".format(hex_file))

    finally:

        log.info("Sleeping for 5 secs to give ATtiny time to recover")
        time.sleep(5)

        log.info("Setting GPIO output pin {:} low".format(gpio_pin.HOLD_PWR))
        gpio.output(gpio_pin.HOLD_PWR, gpio.LOW)

        # Re-setup SPM connection
        conn.setup()

    return ret


def start(workers, **kwargs):
    try:
        log.debug("Starting SPM manager")

        # Give process highest 'nice' priority
        psutil.Process(os.getpid()).nice(-20)

        # Setting up SPM connection
        conn.setup()

        # Initialize and run message processor
        edmp.init(__opts__, workers=workers)
        edmp.run()

    except Exception:
        log.exception("Failed to start SPM manager")
        raise
    finally:
        log.info("Stopping SPM manager")
