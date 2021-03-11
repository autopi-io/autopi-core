import logging
import RPi.GPIO as gpio
import time

from messaging import EventDrivenMessageProcessor
from threading_more import intercept_exit_signal


USER_EXT1_PIN_WIRES = {
    "green":   7,
    "white":   8,
    "grey":    9,
    "red":    10,
    "black":  11
}

USER_EXT2_PIN_WIRES = {
    "green":  23,
    "white":  24,
    "grey":   27,
    "red":     1,
    "black":   0
}


log = logging.getLogger(__name__)

context = {
    "pin_wires": {}
}

# Message processor
edmp = EventDrivenMessageProcessor("key_fob", context=context)


@edmp.register_hook(synchronize=False)
def context_handler():
    """
    Gets current context.
    """

    return context


@edmp.register_hook()
def power_handler(value=None):
    """
    Powers on/off key fob.

    Optional arguments:
      - value (bool): Power on or off. 
    """

    ret = {}

    if context["pin_wires"] != USER_EXT2_PIN_WIRES:
        raise Exception("Only supported for port ext port 2")

    kwargs = {}
    if value != None:
        kwargs["high" if value else "low"] = "ext_sw_3v3"

    res = __salt__["spm.query"]("ext_pins", **kwargs)

    ret["value"] = res["output"]["ext_sw_3v3"]

    # Trigger key fob power event
    if value != None:
        edmp.trigger_event(
            {},
            "vehicle/key_fob/power/{:}".format("on" if value else "off")
        )

    return ret


@edmp.register_hook()
def action_handler(*names):
    """
    Performs a key fob button action.

    Arguments:
      - *name (str): Name(s) of the action(s) to perform.
    """

    ret = {}

    ctx = context.get("actions", {})

    if not names:
        ret["values"] = ctx.keys()

        return ret
    else:
        for name in names:
            if not name in ctx:
                raise Exception("No key fob action found by name '{:}'".format(name))

    res = power_handler()
    if not res["value"]:
        raise Exception("Key fob is powered off")

    for name in names:
        log.info("Performing key fob action '{:}'".format(name))

        action = ctx[name]
        gpio_pin = context["pin_wires"][action["pin"]["wire"]]
        initial = gpio.input(gpio_pin)

        try:
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Setting GPIO output pin {:} to {:d}".format(gpio_pin, not initial))
            gpio.output(gpio_pin, not initial)

            time.sleep(action.get("duration", 0.25))
        finally:
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Setting GPIO output pin {:} to {:d}".format(gpio_pin, initial))
            gpio.output(gpio_pin, initial)

        # Perform any repetitions
        for count, repetition in enumerate(action.get("repetitions", [])):
            log.info("Performing key fob action '{:}' repetition #{:}".format(name, count + 1))

            time.sleep(repetition.get("delay", 0.25))
            try:
                if log.isEnabledFor(logging.DEBUG):
                    log.debug("Setting GPIO output pin {:} to {:d}".format(gpio_pin, not initial))
                gpio.output(gpio_pin, not initial)

                time.sleep(repetition.get("duration", action.get("duration", 0.25)))
            finally:
                if log.isEnabledFor(logging.DEBUG):
                    log.debug("Setting GPIO output pin {:} to {:d}".format(gpio_pin, initial))
                gpio.output(gpio_pin, initial)

        # Trigger key fob action event
        edmp.trigger_event(
            {},
            "vehicle/key_fob/action/{:}".format(name)
        )

    return ret


@intercept_exit_signal
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting key fob manager with settings: {:}".format(settings))

        # Determine which ext port to use 
        ext_port = settings.get("ext_port", 2)
        if ext_port == 1:
            context["pin_wires"] = USER_EXT1_PIN_WIRES
        elif ext_port == 2:
            context["pin_wires"] = USER_EXT2_PIN_WIRES
        else:
            raise Exception("Unsupported user ext port {:}".format(ext_port))

        # Initialize GPIO
        gpio.setwarnings(False)
        gpio.setmode(gpio.BCM)

        for action in settings.get("actions", []):
            try:

                if not action["pin"]["wire"] in context["pin_wires"]:
                    raise Exception("Pin wire '{:}' not supported".format(action["pin"]["wire"]))

                gpio.setup(
                    context["pin_wires"][action["pin"]["wire"]],
                    gpio.OUT,
                    initial=action["pin"].get("initial", True)
                )

                # Add action to context
                context.setdefault("actions", {})[action["name"]] = action
            except:
                log.exception("Failed to setup GPIO pin for action: {:}".format(action))

        # Initialize and run message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        edmp.run()

    except Exception:
        log.exception("Failed to start key fob manager")

        raise
    finally:
        log.info("Stopping key fob manager")