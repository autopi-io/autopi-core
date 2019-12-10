import logging
import salt.exceptions
import salt_more

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
        "stn": {},
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

    # RPI uptime
    res = __salt__["status.uptime"]()
    ret["rpi"]["uptime"] = res

    return ret


def sleep(interval=60, delay=10, modem_off=False, acc_off=False, confirm=False, reason="unknown", allow_auto_update=True):
    """
    Power down system and put device into sleep state.

    Optional arguments:
      - interval (int): Sleep interval in seconds. Default is '60'.
      - delay (str): Delay in seconds before powering down. Default is '10'.
      - modem_off (bool): Power off 3V3 supply to modem on mPCIe slot. Default is 'False'.
      - acc_off (bool): Put accelerometer into standby. Default is 'False'.
      - confirm (bool): Acknowledge the execution of this command. Default is 'False'.
      - reason (str): Reason code that tells why we decided to sleep. Default is 'unknown'.
    """

    if __salt__["saltutil.is_running"]("power.sleep"):
        raise salt.exceptions.CommandExecutionError("Sleep is already running")

    if not confirm:
        raise salt.exceptions.CommandExecutionError(
            "This command will power down the system - add parameter 'confirm=true' to continue anyway")

    ret = {}

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
        __salt__["system.shutdown"](int(delay / 60) + 2)
    except:
        log.exception("Failed to plan system shutdown")

    # Put STN to sleep (and thereby shutdown RPi when STN power pin goes low)
    __salt__["stn.sleep"](delay)

    if interval > 0:
        log.warn("Intentionally going to sleep for {:} second(s) because of reason '{:}'".format(interval, reason))
    else:
        log.warn("Intentionally going to hibernate until next engine start because of reason '{:}'".format(reason))

    # Fire a sleep or hibernate event
    __salt__["event.fire"]({
            "delay": delay,
            "interval": interval,
            "reason": reason,
            "uptime": __salt__["status.uptime"]()["seconds"]
        },
        "system/power/{:}".format("sleep" if interval > 0 else "hibernate")
    )

    ret["comment"] = "Planned shutdown in {:d} second(s)".format(delay)
    ret["result"] = True

    return ret


def hibernate(delay=10, confirm=False, reason="unknown", allow_auto_update=True):
    """
    Power down system and put device into hibernate state.

    Optional arguments:
      - delay (str): Delay in seconds before powering down. Default is '10'.
      - confirm (bool): Acknowledge the execution of this command. Default is 'False'.
      - reason (str): Reason code that tells why we decided to hibernate. Default is 'unknown'.
    """

    return sleep(interval=0, delay=delay, acc_off=True, confirm=confirm, reason=reason, allow_auto_update=allow_auto_update)


def sleep_timer(enable=None, period=1800, add=None, clear=None, **kwargs):
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
        ret = {k: dict(v, _stamp=datetime.utcnow().isoformat()) for k, v in res.iteritems() if k.startswith("_sleep_timer")}

        return ret

    if clear != None or enable == False:

        # Clear matching timers
        for name in timers():
            if clear not in [None, "*"]:
                if "_sleep_timer/{:}".format(clear) != name:
                    continue

            res = __salt__["schedule.delete"](name)

            # Fire a cleared event
            __salt__["event.fire"]({
                    "reason": reason,
                },
                "system/{:}/cleared".format(name.lstrip("_"))
            )

    if add != None or enable == True:
        name = "_sleep_timer/{:}".format(add or reason)

        # Always try to delete existing timer
        res = __salt__["schedule.delete"](name)

        # Prepare keyword arguments
        kwargs = salt_more.clean_kwargs(kwargs)  # Clean up unwanted entries
        kwargs["confirm"] = True  # Ensure confirm is set

        now = datetime.utcnow()

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
                "expires": (now + timedelta(seconds=period)).isoformat(),
                "transient": True,  # Enforce schedule is never persisted on disk and thereby not surviving minion restarts (see patch 'salt/utils/schedule.py.patch')
                "revision": 2
            })

        # Fire an added event
        __salt__["event.fire"](
            {"reason": reason} if not name.endswith("/{:}".format(reason)) else {},
            "system/{:}/added".format(name.lstrip("_"))
        )

    # Return all existing timer(s)
    return timers()


def reboot(reason="unknown"):
    """
    Reboot system immediately.

    Optional arguments:
      - reason (str): Reason code that tells why we decided to reboot. Default is 'unknown'.
    """

    return request_reboot(immediately=True, reason=reason)


def request_reboot(pending=True, immediately=False, reason="unknown"):
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

            # Fire a reboot event
            __salt__["event.fire"]({
                    "reason": reason,
                    "uptime": __salt__["status.uptime"]()["seconds"]
                },
                "system/power/reboot"
            )

            # TODO: Delay reboot 10 secs to allow cloud upload of above event

            # Ensure a heatbeat has just been sent to prevent heartbeat timeout during reboot
            __salt__["spm.query"]("noop")

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


def restart_modem():
    """
    Restart modem the hard way by stopping and starting its power supply.
    """

    # TODO: We also need to close all open serial conenctions to modem to prevent system freeze

    return __salt__["spm.query"]("restart_3v3")

