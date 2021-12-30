import croniter
import logging
import salt.exceptions
import salt_more
import time

from common_util import dict_get, fromisoformat 
from datetime import datetime, timedelta


log = logging.getLogger(__name__)


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"]("power")


def status():
    """
    Get status and debug information regarding power management.
    """

    ret = {
        "spm": {},
        "rpi": {},
    }

    # SPM status
    res = __salt__["spm.query"]("status")
    ret["spm"].update({k: v for k, v in res.iteritems() if not k.startswith("_")})

    # SPM sleep interval
    res = __salt__["spm.query"]("sleep_interval")
    ret["spm"]["sleep_interval"] = res["value"]

    # SPM version
    res = __salt__["spm.query"]("version")
    ret["spm"]["version"] = res["value"]

    if __opts__.get("spm.version", 2.0) < 3.0:

        # STN config
        res = __salt__["stn.power_config"]()
        ret["stn"]["trigger_config"] = {
            k: v.split(",")[1] for k, v in res.iteritems() \
                if (k.endswith("_wake") or k.endswith("_sleep")) and v.startswith("ON")
        }

        # STN trigger
        res = __salt__["stn.power_trigger_status"]()
        ret["stn"]["last_trigger"] = {
            k: v for k, v in res.iteritems() if not k.startswith("_")
        }

        # STN battery
        res = __salt__["obd.battery"]()
        ret["stn"]["battery"] = {
            k: v for k, v in res.iteritems() if not k.startswith("_")
        }

    else:

        # SPM battery
        res = __salt__["obd.battery"]()  # Same command as above
        ret["spm"]["battery"] = {
            k: v for k, v in res.iteritems() if not k.startswith("_")
        }

    # RPI uptime
    res = __salt__["status.uptime"]()
    ret["rpi"]["uptime"] = res

    return ret


def sleep(interval=60, delay=60, modem_off=False, acc_off=False, confirm=False, reason="unknown", allow_auto_update=True, **kwargs):
    """
    Power down system and put device into sleep state.

    Optional arguments:
      - interval (int): Sleep interval in seconds. Default is '60'.
      - delay (str): Delay in seconds before powering down. Default is '60'.
      - modem_off (bool): Power off 3V3 supply to modem on mPCIe slot. Default is 'False'.
      - acc_off (bool): Put accelerometer into standby. Default is 'False'.
      - confirm (bool): Acknowledge the execution of this command. Default is 'False'.
      - reason (str): Reason code that tells why we decided to sleep. Default is 'unknown'.
    """

    # Validate dynamic keyword arguments
    if [k for k in kwargs.keys() if not k.startswith("__")]:
        raise salt.exceptions.CommandExecutionError(
            "Unsupported keyword argument(s): {:}".format(", ".join([k for k in kwargs.keys() if not k.startswith("__")]))
        )

    if __salt__["saltutil.is_running"]("power.sleep"):
        raise salt.exceptions.CommandExecutionError("Sleep is already running")

    ret = {
        "result": True,
        "comment": ""
    }

    # Check if called from sleep timer scheduled job
    schedule = kwargs.get("__pub_schedule", None)
    if schedule and schedule.startswith("_sleep_timer"):
        try:

            # Check to bypass sleep timer
            if __salt__["minionutil.run_job"]("pillar.get", "power:sleep_timer:bypass", default=False, _timeout=30):
                log.warn("Intentionally bypassing sleep timer '{:}' according to pillar 'power:sleep_timer:bypass'".format(schedule))

                ret["result"] = False
                ret["comment"] = "Sleep timer bypassed"

                return ret

        except:
            log.exception("Failed to get pillar 'power:sleep_timer:bypass'")

    elif not confirm:
        raise salt.exceptions.CommandExecutionError(
            "This command will power down the device - add parameter 'confirm=true' to continue anyway")

    log.info("Preparing to sleep {:} in {:} second(s)".format(
        "{:} second(s)".format(interval) if interval > 0 else "infinite",
        delay))

    # First set SPM sleep interval
    try:
        __salt__["spm.query"]("sleep_interval", value=interval)
    except:
        log.exception("Failed to set sleep interval")
        interval = 0  # Assume interval is unset

    # Run shutdown SLS
    try:
        __salt__["minionutil.run_job"]("state.sls", "shutdown", pillar={"allow_auto_update": allow_auto_update}, _timeout=600)
    except:
        log.exception("Failed to run shutdown SLS")

    # Kill heartbeat worker thread to enforce RPi power off if something goes south/hangs
    try:
        res = __salt__["spm.manage"]("worker", "kill", "_heartbeat")
        if not "_heartbeat" in res.get("killed", []):
            log.warn("No heartbeat worker thread found to kill")
    except:
        log.exception("Failed to kill heartbeat worker")

    # TODO: Power off audio amp (if not done when shutting down RPi?)

    # Power off 3V3 for modem/mPCIe if requested
    #if modem_off:
    #    __salt__["spm.query"]("stop_3v3")

    # Set accelerometer in standby mode
    if acc_off:
        try:
            __salt__["acc.query"]("active", value=False)
        except:
            log.exception("Failed to put accelerometer into standby mode")

    # Plan a system shutdown in case STN never sleeps
    # (it could get interrupted by another STN wake trigger)
    try:

        if __opts__.get("spm.version", 2.0) < 3.0:
            __salt__["system.shutdown"](int(delay / 60) + 2)
        else:
            __salt__["system.shutdown"](max(int(delay / 60), 1))

        # Broadcast reason to all terminals
        __salt__["cmd.run"]("wall -n 'Reason: {:}'".format(reason))
    except:
        log.exception("Failed to plan system shutdown")

    try:

        if __opts__.get("spm.version", 2.0) < 3.0:
            # Put STN to sleep (and thereby shutdown RPi when STN power pin goes low)
            # NOTE: This is not required for SPM 2.0 but we still do it for backward compatibility.
            #       The only consequence is that the SPM down trigger is registered as 'STN' instead of 'RPI'.
            __salt__["stn.sleep"](delay)

    finally:  # If STN command fails we still want to send below event

        if interval > 0:
            log.warn("Intentionally going to sleep for {:} second(s) because of reason '{:}'".format(interval, reason))
        else:
            log.warn("Intentionally going to hibernate until next engine start because of reason '{:}'".format(reason))

        # Trigger a sleep or hibernate event
        __salt__["minionutil.trigger_event"](
            "system/power/{:}".format("sleep" if interval > 0 else "hibernate"),
            data={
                "delay": delay,
                "interval": interval,
                "reason": reason,
                "uptime": __salt__["status.uptime"]()["seconds"]
            }
        )

    ret["comment"] = "Planned shutdown in {:d} second(s)".format(delay)
    
    return ret


def hibernate(delay=60, confirm=False, reason="unknown", allow_auto_update=True, **kwargs):
    """
    Power down system and put device into hibernate state.

    Optional arguments:
      - delay (str): Delay in seconds before powering down. Default is '60'.
      - confirm (bool): Acknowledge the execution of this command. Default is 'False'.
      - reason (str): Reason code that tells why we decided to hibernate. Default is 'unknown'.
    """

    return sleep(interval=0, delay=delay, acc_off=True, confirm=confirm, reason=reason, allow_auto_update=allow_auto_update, **kwargs)


def sleep_timer(enable=None, period=1800, add=None, clear=None, refresh=None, **kwargs):
    """
    Setup sleep timer to schedule power off upon inactivity.

    NOTE: Do not access pillar data in this function as they will not be available when called from engines (separate processes).

    Optional arguments:
      - add (str): Add a timer with the given name.
      - clear (str): Clear sleep timer(s) matching the given name. Use '*' to clear all.
      - enable (bool): Enable or disable timer. __DEPRECATED__: Use 'add' or 'clear' instead.
      - period (int): Timer period in seconds before performing sleep. Default is '1800'.
      - reason (str): Reason code that tells why we decided to sleep. Default is 'unknown'.
    """

    reason = kwargs.setdefault("reason", "unknown")

    if enable != None:
        log.warning("Using deprecated argument 'enable' - use 'add' or 'clear' instead")

    # Helper function to get all scheduled sleep timers
    def timers():
        res = __salt__["schedule.list"](return_yaml=False)
        ret = {k: dict(v, _stamp=datetime.utcnow().isoformat(), job_args=v.pop("args", []), job_kwargs=v.pop("kwargs", {})) for k, v in res.iteritems() if k.startswith("_sleep_timer")}

        return ret

    # Load configuration file if present
    config = {}
    try:
        config = __salt__["fileutil.load_yaml"]("/opt/autopi/power/sleep_timer.yml")
    except:
        log.exception("Failed to load sleep timer configuration file")

    # Clear timer(s) if requested
    if clear != None or enable == False:

        # Clear matching timers
        for name in timers():
            if clear not in [None, "*"]:
                if "_sleep_timer/{:}".format(clear) != name:
                    continue

            res = __salt__["schedule.delete"](name)

            # Trigger a cleared event
            __salt__["minionutil.trigger_event"]("system/{:}/cleared".format(name.lstrip("_")), data={"reason": reason})

    # Add timer if requested
    if add != None or enable == True:
        name = "_sleep_timer/{:}".format(add or reason)

        # Always try to delete existing timer
        res = __salt__["schedule.delete"](name)

        # Prepare keyword arguments
        kwargs = salt_more.clean_kwargs(kwargs)  # Clean up unwanted entries
        kwargs["confirm"] = True  # Ensure confirm is set

        now = datetime.utcnow()
        expiry = now + timedelta(seconds=period)

        # Add fresh timer
        res = __salt__["schedule.add"](name,
            function="power.sleep",
            job_kwargs=kwargs,
            seconds=period,
            maxrunning=1,
            return_job=False,  # Do not return info to master upon job completion
            persist=False,  # Do not persist schedule (actually this is useless because all schedules might be persisted when modified later on)
            metadata={
                "created": now.isoformat(),
                "expires": expiry.isoformat(),
                "transient": True,  # Enforce schedule is never persisted on disk and thereby not surviving minion restarts (see patch 'salt/utils/schedule.py.patch')
                "revision": 2
            })

        if res.get("result", False):

            # Ensure to adjust
            if refresh == None:
                refresh = add or reason

            # Trigger an added event
            __salt__["minionutil.trigger_event"](
                "system/{:}/added".format(name.lstrip("_")),
                data={"reason": reason} if not name.endswith("/{:}".format(reason)) else {}
            )

            # Broadcast notification to all terminals
            try:
                __salt__["cmd.run"]("wall -n \"\nATTENTION ({:}):\n\nSleep timer '{:}' added which is scheduled to trigger at {:}.\nRun command 'autopi power.sleep_timer' to list active sleep timers.\n\n(Press ENTER to continue)\"".format(now, name[name.rindex("/")+1:], expiry))
            except:
                log.exception("Failed to broadcast sleep timer added notification")

        else:
            log.error("Failed to add sleep timer '{:}': {:}".format(name, res))

    # Refresh timer(s) if requested
    if refresh != None:

        boot_delay = dict_get(config, "suppress", "boot_delay", default=60)

        # Loop through all matching sleep timers
        for name, schedule in timers().iteritems():
            if refresh not in [None, "*"]:
                if "_sleep_timer/{:}".format(refresh) != name:
                    continue

            # Adjust according to suppress schedules
            for entry in dict_get(config, "suppress", "schedule", default=[]):
                try:
                    if not "|" in entry:
                        raise ValueError("No pipe sign separator found in schedule entry")

                    expression, duration = entry.split("|")

                    # Generate suppress start and end times 
                    expiry = fromisoformat(schedule["metadata"]["expires"])
                    for suppress_start in [croniter.croniter(expression.strip(), expiry).get_prev(datetime), croniter.croniter(expression.strip(), expiry).get_next(datetime)]:
                        # NOTE: If a datetime is given to croniter which exactly matches the expression, the same datetime will be returned for both get_prev and get_next.
                        suppress_end = suppress_start + timedelta(seconds=int(duration.strip()))

                        # Caluclate sleep start and end times
                        sleep_start = expiry
                        sleep_end = expiry + timedelta(seconds=schedule["job_kwargs"].get("interval", 86400) + boot_delay)  # Also add time for booting

                        # Proceed if we have an overlap
                        if sleep_start < suppress_end and sleep_end > suppress_start:
                            log.info("Sleep timer '{:}' sleep period from {:} to {:} overlaps with sleep suppress period from {:} to {:}".format(name, sleep_start, sleep_end, suppress_start, suppress_end))

                            now = datetime.utcnow()

                            # Is it possible to reduce sleeping time?
                            if schedule["job_kwargs"].get("interval", 0) > 0 and sleep_start < suppress_start and (suppress_start - sleep_start).total_seconds() > boot_delay:
                                state = "reduced"

                                old_interval = schedule["job_kwargs"]["interval"]
                                new_interval = int((suppress_start - sleep_start).total_seconds() - boot_delay)  # Subtract time for booting from the sleeping time
                                log.warning("Reducing sleeping time of sleep timer '{:}' from {:} to {:} seconds due to suppress schedule: {:}".format(name, old_interval, new_interval, entry))

                                # Set reduced sleeping time
                                schedule["job_kwargs"]["interval"] = new_interval

                                # Also update fire time to match originally scheduled
                                schedule["seconds"] = (expiry - now).total_seconds()

                            # Or must sleep be postponed?
                            else:
                                state = "postponed"

                                old_period = schedule["seconds"]
                                new_period = (suppress_end - now).total_seconds()
                                log.warning("Postponing sleep timer '{:}' from {:} to {:} seconds due to suppress schedule: {:}".format(name, old_period, new_period, entry))

                                # Set postponed fire time
                                schedule["seconds"] = new_period
                            
                            # Calculate expiry time (may be unchanged)
                            expiry = now + timedelta(seconds=schedule["seconds"])

                            # Update metadata
                            schedule["metadata"]["updated"] = now.isoformat()
                            schedule["metadata"]["expires"] = expiry.isoformat()
                            
                            # Modify existing timer
                            res = __salt__["schedule.modify"](**schedule)
                            if res.get("result", False):

                                # Trigger an modified event
                                __salt__["minionutil.trigger_event"](
                                    "system/{:}/{:}".format(name.lstrip("_"), state)
                                )

                                # Broadcast notification to all terminals
                                try:
                                    __salt__["cmd.run"]("wall -n \"\nATTENTION ({:}):\n\nSleep timer '{:}' has been {:} due to sleep suppress rule and is scheduled to trigger at {:}.\nRun command 'autopi power.sleep_timer' to list active sleep timers.\n\n(Press ENTER to continue)\"".format(now, name[name.rindex("/")+1:], state, expiry))
                                except:
                                    log.exception("Failed to broadcast sleep timer modified notification")
                            else:
                                log.error("Failed to modify sleep timer '{:}': {:}".format(name, res))

                        elif log.isEnabledFor(logging.DEBUG):
                            log.debug("Sleep timer '{:}' does not overlap with suppress schedule: {:}".format(name, entry))

                except:
                    log.exception("Failed to process suppress schedule for sleep timer '{:}': {:}".format(name, entry))

    # Return all existing timer(s)
    return timers()


def reboot(reason="unknown"):
    """
    Reboot system immediately.

    Optional arguments:
      - reason (str): Reason code that tells why we decided to reboot. Default is 'unknown'.
    """

    return request_reboot(immediately=True, reason=reason)


def request_reboot(pending=True, immediately=False, delay=10, reason="unknown"):
    """
    Request for a future system reboot.

    Optional arguments:
      - pending (bool): Default is 'True'.
      - immediately (bool): Default is 'False'.
      - reason (str): Reason code that tells why we decided to reboot. Default is 'unknown'.
    """

    if pending or __context__.get("power.request_reboot", False):
        if immediately:
            log.warn("Performing system reboot immediately because of reason '{:}'".format(reason))

            # Trigger a reboot event
            __salt__["minionutil.trigger_event"](
                "system/power/reboot",
                data={
                    "reason": reason,
                    "uptime": __salt__["status.uptime"]()["seconds"]
                }
            )

            # Ensure a heatbeat has just been sent to prevent heartbeat timeout during reboot
            __salt__["spm.query"]("heartbeat")

            if delay > 0:
                 time.sleep(delay)

            # Perform reboot
            return __salt__["system.reboot"]()
        else:
            log.info("Request for system reboot is pending because of reason '{:}'".format(reason))
    else:
        log.debug("No pending system reboot request")

    # Set pending in context
    __context__["power.request_reboot"] = pending

    return {
        "pending": pending,
    }


def restart_3v3(confirm=False, reason="unknown"):
    """
    Restart the 3V3 power supply. This will restart the modem and also the accelerometer the hard way.

    WARNING: Any open serial connections to the modem (eg. in ec2x_manager and tracking_manager) may cause the system to freeze or block the TTYs and make new numbering after modem is re-initialized. It is recommended to use 'ec2x.power_off' to restart modem.
    
    Optional arguments:
      - confirm (bool): Acknowledge the execution of this command. Default is 'False'.
      - reason (str): Reason code that tells why the 3V3 supply is restarted. Default is 'unknown'.
    """

    if not confirm:
        raise salt.exceptions.CommandExecutionError(
            "This command should be used with caution and only if the description in the documentation is understood - add parameter 'confirm=true' to continue anyway")

    ret = __salt__["spm.query"]("restart_3v3")

    # Trigger a 3V3 restarted event
    __salt__["minionutil.trigger_event"]("system/power/3v3/restarted", data={"reason": reason})

    return ret
