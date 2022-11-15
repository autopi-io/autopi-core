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
import math

from common_util import abs_file_path, factory_rendering, min_max
from messaging import EventDrivenMessageProcessor, extract_error_from, filter_out_unchanged
from threading_more import intercept_exit_signal, TimedEvent
from timeit import default_timer as timer


log = logging.getLogger(__name__)

DEBUG = log.isEnabledFor(logging.DEBUG)

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
            __salt__["audio.aplay"]("/opt/autopi/audio/sound/bleep.wav")

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
            __salt__["audio.aplay"]("/opt/autopi/audio/sound/beep.wav")

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
def motion_event_trigger(result, jolt_g_threshold=0.3, jolt_duration=1, shake_g_threshold=0.01, shake_duration=3, shake_percentage=90, debounce_delay=1):
    """
    Triggers 'vehicle/motion/jolting', 'vehicle/motion/shaking' and 'vehicle/motion/steady' events based on accelerometer XYZ readings.

    Optional arguments:
      - jolt_g_threshold (float): G force threshold for jolting detection. Disabled when set to zero. Default value is '0.3'.
      - jolt_duration (float): How long in seconds should the G force threshold be observed over? Default value is '1'.
      - shake_g_threshold (float): G force threshold for shaking detection. Disabled when set to zero. Default value is '0.01'.
      - shake_duration (float): How long in seconds should the G force threshold be observed over? Default value is '3'.
      - shake_percentage (float): Percentage of positive motion detections required within duration period to conclude shaking. Default value is '90'.
      - debounce_delay (float): Minimum delay in seconds between triggering events. Default value is '1'.
    """

    # Check for error result
    error = extract_error_from(result)
    if error:
        if DEBUG:
            log.debug("Motion event trigger got error result: {:}".format(result))

        return

    if result.get("_type", None) not in ["xyz", "acc_xyz", "gyro_acc_xyz"]:
        log.error("Motion event trigger got unsupported XYZ type result: {:}".format(result))

        return

    # Use only accelerometer data, skip gyro
    data = result["acc"] if result["_type"] == "gyro_acc_xyz" else result

    # Prepare settings
    settings = context.get("settings", {}).get("motion_event_trigger", {})

    jolt_g_threshold = settings.get("jolt_g_threshold", jolt_g_threshold)
    jolt_duration = settings.get("jolt_duration", jolt_duration)
    shake_g_threshold = settings.get("shake_g_threshold", shake_g_threshold)
    shake_duration = settings.get("shake_duration", shake_duration)
    shake_percentage = settings.get("shake_percentage", shake_percentage)
    debounce_delay = settings.get("debounce_delay", debounce_delay)
    
    reinit = settings.pop("reinit", False)

    ctx = context.setdefault("motion_event_trigger", {})

    # Prepare context (re-initializes if data rate has changed)
    data_rate = conn.rate  # In Hz
    if reinit or data_rate != ctx.get("data_rate", 0):
        ctx["data_rate"] = data_rate

        data_window_size = max(int(data_rate * jolt_duration), 2)  # NOTE: Minimum size is 2
        ctx["data_window"] = {
            "size": data_window_size,
            "axes": {k: [0.0] * data_window_size for k in ["x", "y", "z"]},
            "cursor": 0,
            "full": False
        }

        diff_window_size = max(int(data_rate * shake_duration), 2)  # NOTE: Minimum size is 2
        ctx["diff_window"] = {
            "size": diff_window_size,
            "axes": {k: [0.0] * diff_window_size for k in ["x", "y", "z"]},
            "cursor": 0
        }

        ctx["shake_point"] = {
            "sum": 0,
            "limit": int(diff_window_size * (shake_percentage / 100.0))
        }

        if DEBUG:
            log.debug("(Re)initialized motion context: {:}".format(ctx))

    # Reset window cursors
    if ctx["data_window"]["cursor"] >= ctx["data_window"]["size"]:
        ctx["data_window"]["cursor"] = 0
        ctx["data_window"]["full"] = True
    if ctx["diff_window"]["cursor"] >= ctx["diff_window"]["size"]:
        ctx["diff_window"]["cursor"] = 0

    is_jolting = False

    # Store and calculate results in FIFO windows for each axis
    for axis in ["x", "y", "z"]:

        # Update data window
        data_axis = ctx["data_window"]["axes"][axis]
        data_cursor = ctx["data_window"]["cursor"]
        data_axis[data_cursor] = data[axis]

        # Calculate the difference between min and max of the data axis
        if jolt_g_threshold > 0 and ctx["data_window"]["full"] and not is_jolting:
            min_val, max_val = min_max(data_axis)
            is_jolting = abs(max_val - min_val) >= jolt_g_threshold

        if shake_g_threshold > 0:

            # Calculate absolute difference since last measurement
            data_cursor_prev = (ctx["data_window"]["size"] if data_cursor == 0 else data_cursor) - 1
            abs_diff = abs(data_axis[data_cursor] - data_axis[data_cursor_prev])

            # Update diff window
            diff_axis = ctx["diff_window"]["axes"][axis]
            diff_cursor = ctx["diff_window"]["cursor"]
            ctx["shake_point"]["sum"] += (1 if abs_diff >= shake_g_threshold else 0) - (1 if diff_axis[diff_cursor] >= shake_g_threshold else 0)  # Add new and subtract old diff value
            diff_axis[diff_cursor] = abs_diff

    # NOTE: For every diff window entry the shake point can potentially be 3 (one for each axis)
    is_shaking = shake_g_threshold > 0 and ctx["shake_point"]["sum"] >= ctx["shake_point"]["limit"]

    # Increment window cursors
    ctx["data_window"]["cursor"] += 1
    ctx["diff_window"]["cursor"] += 1

    # Check if state has chaged since last known state
    old_state = ctx.get("state", "")
    new_state = "jolting" if is_jolting else "shaking" if is_shaking else "steady"

    if old_state != new_state:

        if debounce_delay:
            now = timer()
            if now >= ctx.get("debounce_timeout", now):

                # Set next debounce timeout
                ctx["debounce_timeout"] = now + debounce_delay
            else:
                if DEBUG:
                    log.debug("Suppressing state change from '{:}' to '{:}' due to debounce delay".format(old_state, new_state))

                return

        ctx["state"] = new_state

        # Trigger event
        __salt__["minionutil.trigger_event"](
            "vehicle/motion/{:s}".format(ctx["state"]))


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


@edmp.register_hook(synchronize=False)
def orientation_enricher(result):
    """
    Adds device orientation (in degrees) which attempts to report back the exact orientation of the
    device to the ground.

    NOTE: This enricher is still a work-in-progress and is not considered stable. The calculations
    here are based on this article: http://www.starlino.com/imu_guide.html
    """

    error = extract_error_from(result)
    if error:
        if DEBUG:
            log.debug("Motion event trigger got error result: {:}".format(result))
        return

    if result.get("_type", None) != "xyz":
        log.error("Motion event trigger got unsupported XYZ type result: {:}".format(result))
        return

    R = math.sqrt(
        math.pow(result["x"], 2) + \
        math.pow(result["y"], 2) + \
        math.pow(result["z"], 2))

    cos_x = result["x"] / R
    cos_y = result["y"] / R
    cos_z = result["z"] / R

    acos_x = math.acos(cos_x)
    acos_y = math.acos(cos_y)
    acos_z = math.acos(cos_z)

    result["deg_x"] = math.degrees(acos_x)
    result["deg_y"] = math.degrees(acos_y)
    result["deg_z"] = math.degrees(acos_z)

    return result


@factory_rendering
@intercept_exit_signal
def start(**settings):
    try:
        if DEBUG:
            log.debug("Starting accelerometer manager with settings: {:}".format(settings))

        # Store settings in context
        context["settings"] = settings

        # Give process higher priority - this can lead to process starvation on RPi Zero (single core)
        psutil.Process(os.getpid()).nice(settings.get("process_nice", -2))

        # Setup interrupt GPIO pin
        gpio.setwarnings(False)
        gpio.setmode(settings.get("gpio", {}).get("mode", gpio_pin.MODE))
        data_int_pin = settings.get("gpio", {}).get("pins", {}).get("data_int", gpio_pin.ACC_INT)
        gpio.setup(data_int_pin, gpio.IN)
        gpio.add_event_detect(data_int_pin, gpio.FALLING, callback=lambda ch: interrupt_event.set())

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
