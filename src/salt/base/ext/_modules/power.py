import logging
import salt.exceptions
import salt_more

from datetime import datetime


log = logging.getLogger(__name__)


def help():
    """
    This command.
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


def sleep(interval=60, delay=10, modem_off=False, acc_off=False, confirm=False, reason="unknown"):
    """
    Power down system and put device into sleep state.

    Args:
        interval (int): Sleep interval in seconds.
        delay (str): Delay in seconds before powering down.
        modem_off (bool): Power off 3V3 supply to modem on mPCIe slot.
        acc_off (bool): Put accelerometer into standby.
        confirm (bool): Acknowledge the execution of this command.
        reason (str): Reason code that tells why we decided to sleep.
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

    # Auto update release if enabled
    if __salt__["pillar.get"]("release:auto_update", default=False):
        try:
            __salt__["minionutil.run_job"]("minionutil.update_release", _timeout=600)
        except:
            log.exception("Failed to update release")
    else:
        log.warn("Release auto update is disabled")

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
            __salt__["acc.active"](enabled=False)
        except:
            log.exception("Failed to put accelerometer into standby mode")

    # Plan a system shutdown after 1 minute in case STN never sleeps
    # (it could get interrupted by another STN wake trigger)
    try:
        __salt__["system.shutdown"](1)
    except:
        log.exception("Failed to plan system shutdown")

    # Put STN to sleep (and thereby shutdown RPi when STN power pin goes low)
    __salt__["stn.sleep"](delay)

    if interval > 0:
        log.warn("Intentionally going to sleep for %d second(s)", interval)
    else:
        log.warn("Intentionally going to hibernate until next engine start")

    # Fire a sleep or hibernate event
    __salt__["event.fire"]({
            "delay": delay,
            "interval": interval,
            "reason": reason
        },
        "power/{:}".format("sleep" if interval > 0 else "hibernate")
    )

    ret["comment"] = "Planned shutdown in {:d} second(s)".format(delay)
    ret["result"] = True

    return ret


def hibernate(delay=10, confirm=False, reason="unknown"):
    """
    Power down system and put device into hibernate state.

    Args:
        delay (str): Delay in seconds before powering down.
        confirm (bool): Acknowledge the execution of this command.
        reason (str): Reason code that tells why we decided to hibernate.
    """

    return sleep(interval=0, delay=delay, acc_off=True, confirm=confirm, reason=reason)


def sleep_timer(enable=None, period=1800, **kwargs):
    """
    Setup sleep timer to schedule power off upon inactivity.

    NOTE: Do not access pillar data in this function as they will not be available when called from engines (separate processes).

    Args:
        enable (bool): Enable or disable timer.
        period (int): Timer period in seconds before performing sleep.
        reason (str): Reason code that tells why we decided to sleep.
    """

    # Helper function to get all sleep timers
    def timers():
        res = __salt__["schedule.list"](return_yaml=False)
        return {k: v for k, v in res.iteritems() if k.startswith("_sleep_timer")}

    if enable == True:

        name = "_sleep_timer/{:}".format(kwargs.get("reason", "unknown"))

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
            return_job=False,  # Do not return info to master upon job completion
            persist=False,  # Do not persist schedule (actually this is useless because all schedules might be persisted when modified later on)
            metadata={
                "created": now.isoformat(),
                "transient": True  # Enforce schedule is never persisted on disk and thereby not surviving minion restarts (see patch 'salt/utils/schedule.py.patch')
            })

    elif enable == False:

        # Delete all existing timers
        for name in timers():
            res = __salt__["schedule.delete"](name)

    # Return all existing timer(s)
    return timers()


def reboot():
    """
    Reboot system immediately.
    """

    return request_reboot(immediately=True)


def request_reboot(pending=True, immediately=False, reason="unknown"):
    """
    Request for a future system reboot.
    """

    if pending or __context__.get("power.request_reboot", False):
        log.info("Request for system reboot is pending")

        if immediately:
            log.warn("Performing system reboot immediately")

            # Fire a reboot event
            __salt__["event.fire"]({
                    "reason": reason
                },
                "power/reboot"
            )

            # TODO: Delay reboot 10 secs to allow cloud upload of above event

            # Ensure a heatbeat has just been sent to prevent heartbeat timeout during reboot
            __salt__["spm.query"]("noop")

            # Perform reboot
            return __salt__["system.reboot"]()
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

