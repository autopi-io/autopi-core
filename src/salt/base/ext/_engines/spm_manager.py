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
edmp = EventDrivenMessageProcessor("spm", context=context, default_hooks={"workflow": "extended", "handler": "query"})

gpio_pins = {}

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

    # TODO HN: Support query of multiple commands in one call.

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
            status = call_retrying(conn.status, limit=10, wait=0.2, context=context.setdefault("errors", {}))

            old_state = context["state"]
            new_state = status["last_state"]["up"]

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
                if status["last_trigger"]["down"] not in ["none", "rpi"]:
                    log.warning("Recovery due to SPM trigger '{:}'".format(status["last_trigger"]["down"]))

                    edmp.trigger_event({
                        "trigger": status["last_trigger"]["down"]
                    }, "system/power/recover")

                # Check if any config params have failed (SPM3 only)
                if conn.revision >= 3:
                    try:
                        config_flags = call_retrying(conn.volt_config_flags, limit=10, wait=0.2, context=context.setdefault("errors", {}))
                        failed_params = [k for k, v in config_flags["failed"].iteritems() if v]
                        if failed_params:
                            edmp.trigger_event({
                                "params": failed_params
                            }, "system/power/config_failed")
                    except:
                        log.exception("Failed to determine if any configuration parameters have failed")

            # Check if state has changed
            if old_state != new_state:
                context["state"] = new_state

                # Trigger state event
                edmp.trigger_event({
                    "trigger": status["last_trigger"]["up"],
                    "awaken": status["last_state"]["down"]
                }, "system/power/{:}{:}".format("_" if new_state in ["booting"] else "", new_state))

    finally:

        # Trigger heartbeat as normal
        call_retrying(conn.heartbeat, limit=10, wait=0.2, context=context.setdefault("errors", {}))


@edmp.register_hook()
def reset_handler():
    """
    Reset/restart ATtiny. 
    """

    ret = {}

    hold_pwr_pin = gpio_pins.get("hold_pwr", gpio_pin.HOLD_PWR)
    reset_pin = gpio_pins.get("reset", gpio_pin.SPM_RESET)
    try:

        log.info("Setting GPIO output pin {:} high".format(hold_pwr_pin))
        gpio.output(hold_pwr_pin, gpio.HIGH)

        log.warn("Resetting ATtiny")
        gpio.output(reset_pin, gpio.LOW)

        # Keep pin low for a while
        time.sleep(.1)

        gpio.output(reset_pin, gpio.HIGH)

    finally:

        log.info("Sleeping for 1 sec to give ATtiny time to recover")
        time.sleep(1)

        log.info("Setting GPIO output pin {:} low".format(hold_pwr_pin))
        gpio.output(hold_pwr_pin, gpio.LOW)

    return ret


@edmp.register_hook()
def flash_firmware_handler(hex_file, part_id, no_write=True):
    """
    Flashes new SPM firmware to the ATtiny.
    """

    ret = {}

    if part_id == "rb2040":
        raise NotImplementedError("Sorry, not yet implemented - ask HN")


    if not os.path.exists(hex_file):
        raise ValueError("Hex file does not exist")

    hold_pwr_pin = gpio_pins.get("hold_pwr", gpio_pin.HOLD_PWR)
    try:

        log.info("Setting GPIO output pin {:} high".format(hold_pwr_pin))
        gpio.output(hold_pwr_pin, gpio.HIGH)

        ret = __salt__["avrdude.flash"](hex_file, part_id=part_id, prog_id="autopi", raise_on_error=False, no_write=no_write)

        if not no_write:
            log.info("Flashed firmware release '{:}'".format(hex_file))

    finally:

        log.info("Sleeping for 5 secs to give ATtiny time to recover")
        time.sleep(5)

        log.info("Setting GPIO output pin {:} low".format(hold_pwr_pin))
        gpio.output(hold_pwr_pin, gpio.LOW)

    return ret


@edmp.register_hook()
def fuse_handler(name, part_id, value=None):
    """
    Manage fuse of the ATtiny.
    """

    if __opts__.get("spm.version", 1.0) >= 4.0:
        raise Exception("Not supported by SPM version 4.0 and above")

    ret = {}

    hold_pwr_pin = gpio_pins.get("hold_pwr", gpio_pin.HOLD_PWR)
    try:

        log.info("Setting GPIO output pin {:} high".format(hold_pwr_pin))
        gpio.output(hold_pwr_pin, gpio.HIGH)

        ret = __salt__["avrdude.fuse"](name, part_id=part_id, prog_id="autopi", value=value)

    finally:

        log.info("Sleeping for 2 secs to give ATtiny time to recover")
        time.sleep(2)

        log.info("Setting GPIO output pin {:} low".format(hold_pwr_pin))
        gpio.output(hold_pwr_pin, gpio.LOW)

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
        gpio.setmode(settings.get("gpio", {}).get("mode", gpio_pin.MODE))

        global gpio_pins
        gpio_pins = settings.get("gpio", {}).get("pins", {})

        gpio.setup(gpio_pins.get("hold_pwr", gpio_pin.HOLD_PWR), gpio.OUT, initial=gpio.LOW)        
        gpio.setup(gpio_pins.get("reset", gpio_pin.SPM_RESET), gpio.OUT, initial=gpio.HIGH)

        has_led = True

        # Initialize SPM connection
        global conn
        if "spm4_conn" in settings:  # Version 4.X
            from spm4_conn import SPM4Conn

            conn = SPM4Conn()
            conn.init(settings["spm4_conn"])

        elif "spm3_conn" in settings:  # Version 3.X
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
            led_pin = gpio_pins.get("led", gpio_pin.LED)
            gpio.setup(led_pin, gpio.OUT)

            global led_pwm
            led_pwm = gpio.PWM(led_pin, settings.get("led_pwm", {}).get("frequency", 2))
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