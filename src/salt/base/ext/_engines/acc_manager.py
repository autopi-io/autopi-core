import datetime
import gpio_pin
import inspect
import json
import logging
import math
import os
import psutil
import RPi.GPIO as gpio
import salt.loader
import threading

from common_util import abs_file_path, factory_rendering
from messaging import EventDrivenMessageProcessor
from mma8x5x_conn import MMA8X5XConn
from threading_more import TimedEvent
from timeit import default_timer as timer


log = logging.getLogger(__name__)

# Message processor
edmp = EventDrivenMessageProcessor("acc", default_hooks={"workflow": "extended", "handler": "query"})

# MMA8X5X I2C connection
conn = MMA8X5XConn()

interrupt_event = TimedEvent()

context = {
    "interrupt": {
        "total": 0,
        "timeout": 0,
    },
    "buffer": {},
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
    Queries a given accelerometer command.

    Arguments:
      - cmd (str): The command to query.
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
        elif isinstance(res, list):
            ret["values"] = res
        else:
            ret["value"] = res

    return ret


@edmp.register_hook(synchronize=False)  # Prevents lockup while waiting on data ready interrupt
def interrupt_query_handler(cmd, *args, **kwargs):

    # Wait for data ready interrupt if not already set
    # TODO HN: Low timeout when real time mode and long when FIFO mode
    timeout = kwargs.pop("interrupt_timeout", 2/conn._data_rate)
    if not interrupt_event.wait(timeout=timeout):
        context["interrupt"]["timeout"] += 1

        if timeout >= 1:
            log.warning("Timed out waiting for interrupt")

    # TODO HN: Fix this
    kwargs["interrupt_timestamp"] = interrupt_event.timestamp
    
    interrupt_event.clear()
    context["interrupt"]["total"] += 1

    # TODO HN: Fix this
    kwargs["stats"] = context.setdefault("buffer", {})
    
    # Perform a normal data read
    return query_handler(cmd, *args, **kwargs)


@edmp.register_hook()
def dump_handler(duration=1, range=8, rate=50, decimals=4, timestamp=True, sound=True, interrupt_driven=False, file=None):
    """
    Dumps raw XYZ readings to screen or file.

    Optional arguments:
      - duration (int): How many seconds to record data? Default value is '1'.
      - file (str): Write data to a file with the given name.
      - range (int): Maximum number of g-forces being measured. Default value is '8'.
      - rate (float): How many Hz (samples per second)? Default value is '50'.
      - decimals (int): How many decimals to calculate? Default value is '4'.
      - timestamp (bool): Add timestamp to each sample? Default value is 'True'.
      - sound (bool): Play sound when starting and stopping recording? Default value is 'True'.
      - interrupt_driven (bool): Await hardware data ready signal before reading a sample? Default value is 'False'.
    """

    # Validate input
    if duration > 300:
        raise ValueError("Maximum duration is 300 seconds")

    if duration * rate > 100 and file == None:
        raise ValueError("Too much data to return - please adjust parameters 'duration' and 'rate' or instead specify a file to write to")

    file_path = abs_file_path(file, "/opt/autopi/acc", ext="json") if file != None else None
    if file_path != None and os.path.isfile(file_path):
        raise ValueError("File already exists: {:}".format(file_path)) 

    ret = {
        "range": range,
        "rate": rate,
        "decimals": decimals,
    }

    if interrupt_driven:
        ret["interrupt_timeouts"] = 0

    data = []

    # Remember settings to restore when done
    orig_range = conn._range
    orig_rate = conn._data_rate

    try:

        # Play sound to indicate recording has begun
        if sound:
            __salt__["cmd.run"]("aplay /opt/autopi/audio/sound/bleep.wav")

        # Apply specified settings
        conn.config({
            "range": range,
            "data_rate": rate,
        })

        # Run for specified duration
        start = timer()
        stop = start + duration
        while timer() < stop:

            if interrupt_driven:

                # Wait for data ready interrupt if not already set
                if not interrupt_event.wait(timeout=2/conn._data_rate):
                    ret["interrupt_timeouts"] += 1

                interrupt_event.clear()

            res = conn.xyz(decimals=decimals)
            if timestamp:
                res["_stamp"] = datetime.datetime.utcnow().isoformat()

            data.append(res)

        ret["duration"] = timer() - start
        ret["samples"] = len(data)

    finally:

        # Restore original settings
        conn.config({
            "range": orig_range,
            "data_rate": orig_rate,
        })

        # Play sound to indicate recording has ended
        if sound:
            __salt__["cmd.run"]("aplay /opt/autopi/audio/sound/beep.wav")

    # Write data to file if requested
    if file_path != None:

        # Ensure folders are created
        __salt__["file.mkdir"](os.path.dirname(file_path))

        with open(file_path, "w") as f:
            res = ret.copy()
            res["data"] = data

            json.dump(res, f, indent=4)

            ret["file"] = f.name
    else:
        ret["data"] = data

    return ret


@edmp.register_hook(synchronize=False)
def roll_pitch_converter(result):
    """
    Calculates roll and pitch for a XYZ reading and appends it to the result.

    TODO HN: Ideally this should be done after filtering
    """

    # Skip failed results
    if "error" in result:
        return

    # Check for supported type
    if not result.get("_type", "").startswith("xyz"):
        log.warning("Unable to calculate roll and pitch for result of type '{:}'".format(result.get("_type", None)))

        return result

    # TODO HN: Figure out how to do this better when multiple values in same result
    if "values" in result:

        # TODO HN: Enforce type
        result["_type"] = "xyz"

        for res in result["values"]:

            # Perform calculations
            res["roll"] = math.atan2(res["y"], res["z"]) * 57.3
            res["pitch"] = math.atan2(-res["x"], math.sqrt(res["y"] * res["y"] + res["z"] * res["z"])) * 57.3
    else:

        # Perform calculations
        result["roll"] = math.atan2(result["y"], result["z"]) * 57.3
        result["pitch"] = math.atan2(-result["x"], math.sqrt(result["y"] * result["y"] + result["z"] * result["z"])) * 57.3

    return result


@edmp.register_hook(synchronize=False)
def alternating_readout_filter(result):
    """
    Filter that only returns alternating/changed values.
    """

    # TODO: Move this function to 'messaging.py' and make it reusable?

    # Skip failed results
    if "error" in result:
        return

    if not "_type" in result:
        log.warn("Skipping result without any type: {:}".format(result))

        return

    # TODO HN: Make this better when multiple values in same result
    # Handle multiple results when used together with FIFO buffer
    if "values" in result:
        ret = []

        for res in result["values"]:
            res["_type"] = result["_type"]
            r = alternating_readout_filter(res)
            if r != None:
                ret.append(r)

        return ret

    ctx = context["readout"]

    old_read = ctx.get(result["_type"], None)
    new_read = result

    # Update context with new read result
    ctx[result["_type"]] = result

    # Check if value is unchanged
    if old_read != None and old_read == new_read:
        return

    # Return changed value
    return new_read


@factory_rendering
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting accelerometer manager with settings: {:}".format(settings))

        # Give process higher priority - this can lead to process starvation on RPi Zero (single core)
        psutil.Process(os.getpid()).nice(settings.get("process_nice", -2))

        # Setup interrupt GPIO pin
        gpio.setmode(gpio.BOARD)
        gpio.setup(gpio_pin.ACC_INT1, gpio.IN)
        gpio.add_event_detect(gpio_pin.ACC_INT1, gpio.FALLING, callback=lambda ch: interrupt_event.set())

        # Configure connection
        conn.setup(settings["mma8x5x_conn"])

        # Initialize and run message processor
        edmp.init(__salt__, __opts__, returners=settings.get("returners", []), workers=settings.get("workers", []))
        edmp.run()

    except Exception:
        log.exception("Failed to start accelerometer manager")

        raise
    finally:
        log.info("Stopping accelerometer manager")
