import gpio_pin
import inspect
import logging
import RPi.GPIO as gpio
import salt.loader
import threading

from messaging import EventDrivenMessageProcessor
from mma8x5x_conn import MMA8X5XConn


log = logging.getLogger(__name__)

# Message processor
edmp = EventDrivenMessageProcessor("acc",
    default_hooks={"handler": "query"})

# MMA8X5X I2C connection
conn = MMA8X5XConn()

returner_func = None

interrupt_event = threading.Event()

context = {
    "interrupt": {
        "total": 0,
        "timeout": 0,
    },
    "readout": {},
}


@edmp.register_hook(synchronize=False)
def context_handler():
    """
    Gets current context.
    """

    return context


@edmp.register_hook()
def query_handler(cmd, *args, **kwargs):
    """
    Query/call an accelerometer function.
    """

    ret = {
        "_type": cmd.lower(),
    }

    try:
        func = getattr(conn, cmd)
    except AttributeError:
        if cmd == "help":
            ret["values"] = [k for k, v in inspect.getmembers(conn, predicate=inspect.ismethod) if not k.startswith("_")]
        else:
            ret["error"] = "Unsupported command: {:s}".format(cmd)

        return ret

    res = func(*args, **kwargs)
    if res != None:
        if isinstance(res, dict):
            ret.update(res)
        else:
            ret["value"] = res

    return ret


@edmp.register_hook(synchronize=False)  # Prevents lockup while waiting on data ready interrupt
def interrupt_query_handler(cmd, *args, **kwargs):

    # Wait for data ready interrupt if not already set
    if not interrupt_event.wait(timeout=2/conn._data_rate):
        context["interrupt"]["timeout"] += 1

    interrupt_event.clear()
    context["interrupt"]["total"] += 1

    # Perform a normal data read
    return query_handler(cmd, *args, **kwargs)


@edmp.register_hook(synchronize=False)
def alternating_readout_returner(message, result):
    """
    Returns alternating/changed values to configured Salt returner module.
    """

    # TODO: Move this function to 'messaging.py' and make it reusable?

    if "error" in result:
        return

    if not "_type" in result:
        log.warn("Skipping result without any type: {:}".format(result))

        return

    ctx = context["readout"]

    old_read = ctx.get(result["_type"], None)
    new_read = result

    # Update context with new read result
    ctx[result["_type"]] = result

    # Check if value is unchanged
    if old_read != None and old_read == new_read:
        return

    # Call Salt returner module
    returner_func(new_read, "acc")


def start(mma8x5x_conn, returner, workers, **kwargs):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting accelerometer manager")

        # Prepare returner function
        global returner_func
        returner_func = salt.loader.returners(__opts__, __salt__)["{:s}.returner_raw".format(returner)]

        # Setup interrupt GPIO pin
        gpio.setmode(gpio.BOARD)
        gpio.setup(gpio_pin.ACC_INT1, gpio.IN)
        gpio.add_event_detect(gpio_pin.ACC_INT1, gpio.FALLING, callback=lambda ch: interrupt_event.set())

        # Configure connection
        conn.setup(mma8x5x_conn)

        # Initialize and run message processor
        edmp.init(__opts__, workers=workers)
        edmp.run()

    except Exception:
        log.exception("Failed to start accelerometer manager")

        raise
    finally:
        log.info("Stopping accelerometer manager")
