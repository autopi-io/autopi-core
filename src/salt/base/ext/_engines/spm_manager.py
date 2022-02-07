import gpio_pin
import logging
import os
import psutil
import RPi.GPIO as gpio
import time

from common_util import call_retrying
from messaging import EventDrivenMessageProcessor
from threading_more import intercept_exit_signal


log = logging.getLogger(__name__)

context = {
    "state": None
}

# Message processor
edmp = EventDrivenMessageProcessor("spm", context=context, default_hooks={"handler": "query"})

# SPM connection is instantiated during start
conn = None

# PWM instance to control LED (only available for version >=2.X)
led_pwm = None


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

    res = call_retrying(func, kwargs=kwargs, limit=3, wait=0.2, context=context.setdefault("errors", {}))
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
            res = call_retrying(conn.status, limit=3, wait=0.2, context=context.setdefault("errors", {}))

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
        call_retrying(conn.heartbeat, limit=3, wait=0.2, context=context.setdefault("errors", {}))


@edmp.register_hook()
def  reset_handler():
    """
    Reset/restart ATtiny. 
    """

    ret = {}

    try:

        log.info("Setting GPIO output pin {:} high".format(gpio_pin.HOLD_PWR))
        gpio.output(gpio_pin.HOLD_PWR, gpio.HIGH)

        log.warn("Resetting ATtiny")
        gpio.output(gpio_pin.SPM_RESET, gpio.LOW)

        # Keep pin low for a while
        time.sleep(.1)

        gpio.output(gpio_pin.SPM_RESET, gpio.HIGH)

    finally:

        log.info("Sleeping for 1 sec to give ATtiny time to recover")
        time.sleep(1)

        log.info("Setting GPIO output pin {:} low".format(gpio_pin.HOLD_PWR))
        gpio.output(gpio_pin.HOLD_PWR, gpio.LOW)

    return ret


@edmp.register_hook()
def flash_firmware_handler(hex_file, part_id, no_write=True):
    """
    Flashes new SPM firmware to ATtiny.
    """

    ret = {}

    try:

        log.info("Setting GPIO output pin {:} high".format(gpio_pin.HOLD_PWR))
        gpio.output(gpio_pin.HOLD_PWR, gpio.HIGH)

        ret = __salt__["avrdude.flash"](hex_file, part_id=part_id, raise_on_error=False, no_write=no_write)

        if not no_write:
            log.info("Flashed firmware release '{:}'".format(hex_file))

    finally:

        log.info("Sleeping for 5 secs to give ATtiny time to recover")
        time.sleep(5)

        log.info("Setting GPIO output pin {:} low".format(gpio_pin.HOLD_PWR))
        gpio.output(gpio_pin.HOLD_PWR, gpio.LOW)

    return ret


@edmp.register_hook(synchronize=False)
def led_pwm_handler(frequency=None, duty_cycle=None):
    """
    Change PWM frequency and/or duty cycle for LED.

    Optional arguments:
      - frequency (float): Change to frequency in Hz.
      - duty_cycle (float): Change to duty cycle in percent.
    """

    ret = {}

    if frequency != None:
        led_pwm.ChangeFrequency(frequency)  # Hz

    if duty_cycle != None:
        led_pwm.ChangeDutyCycle(duty_cycle)  # %

    return ret


@intercept_exit_signal
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting SPM manager with settings: {:}".format(settings))

        # Give process higher priority
        psutil.Process(os.getpid()).nice(-1)

        # Initialize GPIO
        gpio.setwarnings(False)
        gpio.setmode(gpio.BOARD)

        gpio.setup(gpio_pin.HOLD_PWR, gpio.OUT, initial=gpio.LOW)
        gpio.setup(gpio_pin.SPM_RESET, gpio.OUT, initial=gpio.HIGH)

        has_led = True

        # Initialize SPM connection
        global conn
        if "spm3_conn" in settings:  # Version 3.X
            from spm3_conn import SPM3Conn

            conn = SPM3Conn()
            conn.init(settings["spm3_conn"])

        elif "i2c_conn" in settings:  # Version 2.X
            from spm2_conn import SPM2Conn

            conn = SPM2Conn()
            conn.init(settings["i2c_conn"])

        else:  # Version 1.X
            from spm_conn import SPMConn

            conn = SPMConn()
            conn.setup()

            has_led = False

        # Initialize LED GPIO, if available
        if has_led:
            gpio.setup(gpio_pin.LED, gpio.OUT)

            global led_pwm
            led_pwm = gpio.PWM(gpio_pin.LED, settings.get("led_pwm", {}).get("frequency", 2))
            led_pwm.start(settings.get("led_pwm", {}).get("duty_cycle", 50))

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