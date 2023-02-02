import logging
import RPi.GPIO as gpio
import time
import datetime
import persistence

from messaging import EventDrivenMessageProcessor
from threading_more import intercept_exit_signal

PERSISTENCE_ACTION_HISTORY_OBJECT_NAME = "keyfob_action_history"

log = logging.getLogger(__name__)

context = {
    "pin_wires": {},
    "action_history": [],   # Store last 10 attempted actions, lowest index = most recent
}

# Message processor
edmp = EventDrivenMessageProcessor("key_fob", context=context)


def _init_pins():
    """
    Helper function to ensure that GPIO pins are initialized.
    """

    ret = False

    # Only initialize/setup pins if not already
    if not context.get("pins_initialized", False):

        for action in context.get("actions", {}).values():
            gpio_pin = context["pin_wires"][action["pin"]["wire"]]

            if log.isEnabledFor(logging.DEBUG):
                log.debug("Initializing GPIO output pin {:}".format(gpio_pin))

            try:
                gpio.setup(gpio_pin, gpio.OUT, initial=action["pin"].get("initial", True))
            except:
                log.exception("Failed to initialize GPIO pin for action: {:}".format(action))

        # Indicate that pins are initialized
        context["pins_initialized"] = True

        ret = True

        log.info("GPIO pins initialized")

    # Or else re-initialize if reset
    elif context.get("pins_reset", False):

        # Ensure all pins are set to initial values
        for action in context.get("actions", {}).values():
            gpio_pin = context["pin_wires"][action["pin"]["wire"]]
            
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Re-initializing GPIO output pin {:}".format(gpio_pin))

            gpio.output(gpio_pin, action["pin"].get("initial", True))

        # Indicate that pins are no longer reset
        context["pins_reset"] = False

        ret = True

        log.info("GPIO pins re-initialized")

    # After (re-)initialization check for delay 
    if ret:
        delay = context.get("settings", {}).get("delay_after_init_pins", 0)
        if delay > 0:

            # Sleep for the specified delay
            log.info("Sleeping for {:} seconds(s) after (re-)initializing GPIO output pins".format(delay))
            time.sleep(delay)

    return ret


def _deinit_pins():
    """
    Helper function to ensure that GPIO pins are reset.
    """

    # We can skip if not already initialized
    if not context.get("pins_initialized", False):
        return False

    # Check if reset is enabled
    delay = context.get("settings", {}).get("reset_pins_after_delay", -1)
    if delay > -1:

        # Sleep for the specified delay
        log.info("Sleeping for {:} seconds(s) before resetting GPIO output pins".format(delay))
        time.sleep(delay)

        # Ensure all pins are reset (set low)
        for action in context.get("actions", {}).values():
            gpio_pin = context["pin_wires"][action["pin"]["wire"]]

            if log.isEnabledFor(logging.DEBUG):
                log.debug("Resetting GPIO output pin {:}".format(gpio_pin))

            gpio.output(gpio_pin, False)

        # Indicate that pins are in reset state
        context["pins_reset"] = True

        log.info("GPIO pins reset")

        return True

    return False


def add_action_to_history(action):
    history = context["action_history"]
    history.insert(0, action)
    context["action_history"] = history[:10]

    try:
        persistence.save_object(PERSISTENCE_ACTION_HISTORY_OBJECT_NAME, context["action_history"])
    except Exception as err:
        log.error("Failed to save keyfob action history. Exception: {}".format(err))


@edmp.register_hook()
def power_handler(value=None):
    """
    Powers on/off key fob.

    Optional arguments:
      - value (bool): Power on or off. 
    """

    ret = {}

    if not context["power_managed"]:
        raise Exception("Only supported for port ext port 2")

    kwargs = {}
    if value != None:
        kwargs["high" if value else "low"] = "ext_sw_3v3"

    res = __salt__["spm.query"]("ext_pins", **kwargs)

    ret["value"] = res["output"]["ext_sw_3v3"]

    if ret["value"]:  # Power is on

        # Ensure pins are initialized
        _init_pins()

    else:  # Power is off

        # Ensure pins are deinitialized
        _deinit_pins()

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

    # Always check power state
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

        # Add action to the history
        history_entry = {
            "name": name,
            "timestamp": datetime.datetime.utcnow(),
        }
        add_action_to_history(history_entry)

        # Trigger key fob action event
        edmp.trigger_event(
            {},
            "vehicle/key_fob/action/{:}".format(name)
        )

    return ret


@edmp.register_hook(synchronize=False)
def toggle_action_handler(action_name, default=False):
    """
    Toggle an action. The action that's being toggled needs to be defined with an 'opposite' field
    containing the name of the opposite action. The function will toggle the two actions each
    time it is called with either name.

    Parameters:
      - default (bool) - What should the default state of these actions be set to. (default False)
    """

    actions = context.get("actions", {})

    # action exists?
    if action_name not in actions:
        raise Exception("No key fob action found by name '{:}'".format(name))

    # does the action have an opposite action?
    if not actions[action_name].get("opposite", None):
        raise Exception("Action must specify an 'opposite' action")

    # ensure keyfob is powered
    keyfob_power_res = power_handler()
    if not keyfob_power_res["value"]:
        power_handler(value=True)

    # execute the current or opposite action based on action_states
    toggle_actions = context.setdefault("toggle_actions", {})
    opposite_action_name = actions[action_name]["opposite"]

    toggle_actions.setdefault(action_name, default)
    toggle_actions.setdefault(opposite_action_name, default)

    if toggle_actions[action_name]:
        # opposite action needs to be executed
        action_handler(opposite_action_name)

        # update context
        toggle_actions[action_name] = False
        toggle_actions[opposite_action_name] = True

    else:
        # action name needs to be executed
        action_handler(action_name)

        # update context
        toggle_actions[action_name] = True
        toggle_actions[opposite_action_name] = False


    context["toggle_actions"] = toggle_actions


@intercept_exit_signal
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting key fob manager with settings: {:}".format(settings))

        # Also store settings in context
        context["settings"] = settings

        if not settings.get("pin_wires", None):
            raise Exception("Unsupported pin_wires passed in settings. Settings: {}".format(settings))

        context["pin_wires"] = settings["pin_wires"]
        context["power_managed"] = settings.get("power_managed", False)

        for action in settings.get("actions", []):
            if not action["pin"]["wire"] in context["pin_wires"]:
                log.error("Pin wire '{:}' not supported - omitting action: {:}".format(action["pin"]["wire"], action))

                continue

            # Add action to context
            context.setdefault("actions", {})[action["name"]] = action

        # Initialize GPIO
        gpio.setwarnings(False)
        gpio.setmode(gpio.BCM)
        if not settings.get("lazy_init_pins", False):
            _init_pins()
        else:
            log.info("Postpones initialization of GPIO pins")

        # Load persistent context
        context["action_history"] = persistence.load_object(PERSISTENCE_ACTION_HISTORY_OBJECT_NAME, default=[])

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
