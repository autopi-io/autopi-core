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

from common_util import abs_file_path, factory_rendering, min_max
from messaging import EventDrivenMessageProcessor, extract_error_from, filter_out_unchanged
from threading_more import intercept_exit_signal, TimedEvent
from timeit import default_timer as timer


log = logging.getLogger(__name__)

context = {
    "interrupt": {
        "total": 0,
        "timeout": 0,
    },
    "buffer": {},  # Updated by MMA8X5X connection
    "readout": {},
}

# Message processor
edmp = EventDrivenMessageProcessor("acc", context=context, default_hooks={"workflow": "extended", "handler": "query"})

# Connection is instantiated during start
conn = None

interrupt_event = TimedEvent()


@edmp.register_hook(synchronize=False)
def connection_handler(close=False):
    """
    Manages current connection.

    Optional arguments:
      - close (bool): Close connection? Default value is 'False'. 
    """

    ret = {}

    if close:
        log.warning("Closing connection")

        conn.close()

    ret["is_open"] = conn.is_open()
    ret["settings"] = conn.settings

    return ret


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
            raise ValueError("Unsupported query command: {:s}".format(cmd))

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
    # NOTE: Use short timeout when real time mode and long when FIFO mode
    timeout = kwargs.pop("interrupt_timeout", 2.0/conn.rate)
    if not interrupt_event.wait(timeout=timeout):
        context["interrupt"]["timeout"] += 1

        if timeout >= 1:
            log.warning("Timeout after {:} second(s) waiting for interrupt".format(timeout))

    # Pass on interrupt timestamp if requested
    if kwargs.get("interrupt_timestamp", False):
        kwargs["interrupt_timestamp"] = interrupt_event.timestamp
    
    interrupt_event.clear()
    context["interrupt"]["total"] += 1
    
    # Perform a normal data read
    return query_handler(cmd, *args, **kwargs)


@edmp.register_hook()
def dump_handler(duration=1, range=8, rate=12.5, decimals=4, timestamp=True, sound=True, interrupt_driven=True, file=None):
    """
    Dumps raw XYZ readings to screen or file.

    Optional arguments:
      - duration (int): How many seconds to record data? Default value is '1'.
      - file (str): Write data to a file with the given name.
      - range (int): Maximum number of g-forces being measured. Default value is '8'.
      - rate (float): How many Hz (samples per second)? Default value is '12.5'.
      - decimals (int): How many decimals to calculate? Default value is '4'.
      - timestamp (bool): Add timestamp to each sample? Default value is 'True'.
      - sound (bool): Play sound when starting and stopping recording? Default value is 'True'.
      - interrupt_driven (bool): Await hardware data ready signal before reading a sample? Default value is 'True'.
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
    orig_range = conn.range
    orig_rate = conn.rate

    try:

        # Play sound to indicate recording has begun
        if sound:
            __salt__["cmd.run"]("aplay /opt/autopi/audio/sound/bleep.wav")

        # Apply specified settings
        conn.configure(range=range, rate=rate)

        interrupt_timeout = 2.0 / rate

        # Run for specified duration
        start = timer()
        stop = start + duration
        while timer() < stop:

            if interrupt_driven:

                # Wait for data ready interrupt if not already set
                if not interrupt_event.wait(timeout=interrupt_timeout):
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
        conn.configure(range=orig_range, rate=orig_rate)

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
def alternating_readout_filter(result):
    """
    Filter that only returns alternating/changed results.
    """

    return filter_out_unchanged(result, context=context["readout"])


@edmp.register_hook(synchronize=False)
def motion_event_trigger(result, g_change=0.075, duration=1):
    """
    Triggers 'vehicle/motion/jolting' and 'vehicle/motion/steady' events based on accelerometer XYZ readings.

    Optional arguments:
      - g_change (float): The amount of change in G force that will trigger a 'vehicle/motion/jolting' event. Default value is 0.075.
      - duration (float): How long in seconds should the G force change be observed over? Default value is 1.
    """

    # Check for error result
    error = extract_error_from(result)
    if error:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Motion event trigger got error result: {:}".format(result))

        return

    if result.get("_type", None) != "xyz":
        log.error("Motion event trigger got unsupported XYZ type result: {:}".format(key, result))

        return

    ctx = __context__.setdefault("motion", {})

    # Prepare context
    data_rate = conn.rate  # In Hz
    if data_rate != ctx.get("data_rate", 0):
        window_size = max(int(data_rate * duration), 2)  # Minimum buffer size is 2

        # (Re)initialize context
        ctx["data_rate"] = data_rate
        ctx["window_size"] = window_size
        ctx["axis_windows"] = {k: [None] * window_size for k in ["x", "y", "z"]}
        ctx["window_cursor"] = 0

        if log.isEnabledFor(logging.DEBUG):
            log.debug("(Re)initialized motion context: {:}".format(ctx))

    changes = {}

    # Reset window cursor
    if ctx["window_cursor"] >= ctx["window_size"]:
        ctx["window_cursor"] = 0

    # Store result in FIFO window for each axis
    for axis, window in ctx["axis_windows"].iteritems():
        window[ctx["window_cursor"]] = result[axis]

        # Calculate the largest possible difference within window
        min_val, max_val = min_max(window)
        diff = round(max_val - min_val, 2)
        if abs(diff) >= g_change:
            changes[axis] = diff

    # Increment window cursor
    ctx["window_cursor"] += 1

    # Check if state has chaged since last known state
    old_state = ctx.get("state", "")
    new_state = "jolting" if changes else "steady"

    if old_state != new_state:
        ctx["state"] = new_state

        # Trigger event
        __salt__["minionutil.trigger_event"](
            "vehicle/motion/{:s}".format(ctx["state"]),
            data=changes)


@edmp.register_hook(synchronize=False)
def roll_pitch_enricher(result):
    """
    Calculates roll and pitch for a XYZ reading and appends it to the result.
    This enricher supports both single value results as well as multiple values results.
    """

    # Check for supported type
    if not result.get("_type", "").startswith("xyz"):
        log.error("Unable to calculate roll and pitch for result of type '{:}': ".format(result.get("_type", None), result))

        return result

    # Check for multiple values in result
    if "values" in result:

        for res in result["values"]:

            # Perform calculations
            res["roll"] = math.atan2(res["y"], res["z"]) * 57.3
            res["pitch"] = math.atan2(-res["x"], math.sqrt(res["y"] * res["y"] + res["z"] * res["z"])) * 57.3

    # Check for single value in result
    else:

        # Perform calculations
        result["roll"] = math.atan2(result["y"], result["z"]) * 57.3
        result["pitch"] = math.atan2(-result["x"], math.sqrt(result["y"] * result["y"] + result["z"] * result["z"])) * 57.3

    return result


@factory_rendering
@intercept_exit_signal
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting accelerometer manager with settings: {:}".format(settings))

        # Give process higher priority - this can lead to process starvation on RPi Zero (single core)
        psutil.Process(os.getpid()).nice(settings.get("process_nice", -2))

        # Setup interrupt GPIO pin
        gpio.setwarnings(False)
        gpio.setmode(gpio.BOARD)
        gpio.setup(gpio_pin.ACC_INT, gpio.IN)
        gpio.add_event_detect(gpio_pin.ACC_INT, gpio.FALLING, callback=lambda ch: interrupt_event.set())

        # Initialize connection
        global conn
        if "lsm6dsl_conn" in settings:
            from lsm6dsl_conn import LSM6DSLConn

            conn = LSM6DSLConn(settings["lsm6dsl_conn"])
        elif "mma8x5x_conn" in settings:
            from mma8x5x_conn import MMA8X5XConn

            conn = MMA8X5XConn(stats=context)
            conn.init(settings["mma8x5x_conn"])
        else:
            log.error("No supported connection found in settings")

            return;

        # Initialize and run message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        edmp.run()

    except Exception:
        log.exception("Failed to start accelerometer manager")

        raise
    finally:
        log.info("Stopping accelerometer manager")

        if conn.is_open():
            try:
                conn.close()
            except:
                log.exception("Failed to close connection")
