import gpio_pin
import logging
import os
import psutil
import RPi.GPIO as gpio
import time

from messaging import EventDrivenMessageProcessor


log = logging.getLogger(__name__)

context = {
    "state": None
}

# Message processor
edmp = EventDrivenMessageProcessor("spm", context=context, default_hooks={"handler": "query"})

# SPM connection is instantiated during start
conn = None


@edmp.register_hook()
def query_handler(cmd, **kwargs):
    """
    Queries a given SPM command.

    Arguments:
      - cmd (str): The SPM command to query.
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
    Triggers SPM heartbeat and fires power on event when booting.
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
                except Exception as ex:
                    log.warning("Unable to trigger last system off event: {:}".format(ex))

                # Trigger recover state event
                if res["last_trigger"]["down"] not in ["none", "rpi"]:
                    log.warning("Recovery due to SPM trigger '{:}'".format(res["last_trigger"]["down"]))

                    edmp.trigger_event({
                        "trigger": res["last_trigger"]["down"]
                    }, "system/power/recover")

            # Check if state has changed
            if old_state != new_state:
                context["state"] = new_state

                # Trigger state event
                edmp.trigger_event({
                    "trigger": res["last_trigger"]["up"],
                    "awaken": res["last_state"]["down"]
                }, "system/power/{:}{:}".format("_" if new_state in ["booting"] else "", new_state))

    finally:

        # Trigger heartbeat as normal
        conn.heartbeat()


@edmp.register_hook()
def flash_firmware_handler(hex_file, part_id, no_write=True):
    """
    Flashes new SPM firmware to ATtiny.
    """

    ret = {}

    gpio.setmode(gpio.BOARD)
    gpio.setup(gpio_pin.HOLD_PWR, gpio.OUT)

    try:

        log.info("Setting GPIO output pin {:} high".format(gpio_pin.HOLD_PWR))
        gpio.output(gpio_pin.HOLD_PWR, gpio.HIGH)

        params = ["avrdude", "-p {:s}", "-c autopi", "-U flash:w:{:s}".format(part_id, hex_file)]
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

    return ret


def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting SPM manager with settings: {:}".format(settings))

        # Give process higher priority
        psutil.Process(os.getpid()).nice(-1)

        # Initialize SPM connection
        global conn
        if "i2c_conn" in settings:
            from spm2_conn import SPM2Conn

            conn = SPM2Conn()
            conn.init(settings["i2c_conn"])
        else:
            from spm_conn import SPMConn

            conn = SPMConn()
            conn.setup()

        # Initialize and run message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        edmp.run()

    except Exception:
        log.exception("Failed to start SPM manager")
        
        raise
    finally:
        log.info("Stopping SPM manager")

        if getattr(conn, "is_open", False) and conn.is_open():
            try:
                conn.close()
            except:
                log.exception("Failed to close SPM connection")