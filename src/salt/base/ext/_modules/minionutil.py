import datetime
import logging
import salt.exceptions
import salt.utils.event
import salt.utils.jid
import time


log = logging.getLogger(__name__)


def run_job(name, *args, **kwargs):
    """
    Run a job by passing it to the minion process.
    This function makes it possible to run states and also get pillar data from external processes (engines etc.).
    """

    # Prepare event bus handle
    event_bus = salt.utils.event.get_event("minion",
        opts=__opts__,
        transport=__opts__["transport"],
        listen=True)

    # Wait for reply until timeout
    timeout = kwargs.pop("_timeout", 60)

    # Use the event result returner as default
    returner  = kwargs.pop("_returner", "event_result")

    jid = salt.utils.jid.gen_jid()

    if (kwargs):
        kwargs['__kwarg__'] = True
        args = args + (kwargs,)

    # Send job event to minion process
    data = {
        "jid": jid,
        "fun": name,
        "arg": args,
        "ret": returner
    }
    event_bus.fire_event(data, "minion_job")

    reply = event_bus.get_event(wait=timeout, tag="salt/job/{:}/ret".format(jid), match_type="startswith")
    if not reply:
        log.warn("No reply for job %s received within timeout of %d secs", jid, timeout)

        raise salt.exceptions.CommandExecutionError(
            "No reply for JID {:s} received within timeout of {:d} secs".format(jid, timeout))

    ret = reply.get("return", None)

    if not reply.get("success", False):
        raise salt.exceptions.CommandExecutionError(
            "Job unsuccessful: {:}".format(ret))

    return ret


def restart(reason="unknown"):
    """
    Restart the minion service immediately.
    """

    return request_restart(immediately=True, reason=reason)


def request_restart(pending=True, immediately=False, delay=10, expiration=1200, reason="unknown"):
    """
    Request for a future restart of the minion service.
    """

    if pending or __context__.get("minionutil.request_restart", False):
        if immediately:
            log.warn("Performing minion restart in {:} second(s) because of reason '{:}'".format(delay, reason))

            # Fire a restart event
            __salt__["event.fire"]({
                    "reason": reason
                },
                "system/minion/restart"
            )

            # Give some time for event to get cached
            time.sleep(delay)

            # Perform restart of service
            return __salt__["service.restart"]("salt-minion")
        else:
            if expiration > 0:
                __salt__["schedule.add"]("_restart_timer/{:}".format(reason),
                    function="minionutil.restart",
                    job_kwargs={"reason": reason},
                    seconds=expiration,
                    maxrunning=1,
                    return_job=False,  # Do not return info to master upon job completion
                    persist=False,  # Do not persist schedule (actually this is useless because all schedules might be persisted when modified later on)
                    metadata={
                        "created": datetime.datetime.utcnow().isoformat(),
                        "transient": True  # Enforce schedule is never persisted on disk and thereby not surviving minion restarts (see patch 'salt/utils/schedule.py.patch')
                    })

                log.info("Pending request for minion restart because of reason '{:}' is scheduled to be performed automatically in {:} second(s)".format(reason, expiration))
            else:
                log.info("Request for minion restart is pending because of reason '{:}'".format(reason))
    else:
        log.debug("No pending minion restart request")

    # Set pending in context
    __context__["minionutil.request_restart"] = pending

    return {
        "pending": pending,
    }


def update_release(force=False, dry_run=False, only_retry=False):
    """
    Update a minion to newest release by running a highstate if not already up-to-date.
    """

    old = __salt__["grains.get"]("release", default={"id": None, "state": None})
    if not "state" in old:  # Added for backwards compatibility
        old["state"] = None
    new = {"id": __salt__["pillar.get"]("latest_release_id"), "state": None}

    # Determine if latest release is already updated or pending
    if old["state"] == "updated" and old["id"] == new["id"]:
        if force:
            new["state"] = "forcing"
        else:
            new["state"] = "updated"

            log.info("Current release '{:}' is the latest and already updated".format(old["id"]))
    else:
        if old["state"] in ["pending", "forcing", "retrying", "failed"]:
            new["state"] = "retrying"
        else:
            new["state"] = "pending"

        log.info("Release '{:}' is pending for update".format(new["id"]))

    # Prepare return value
    ret = {
        "release": {
            "old": old,
            "new": new,
        }
    }

    if dry_run:
        return ret

    if only_retry and new["state"] != "retrying":
        log.info("No failed update is pending for retry")

        return ret

    if new["state"] in ["pending", "forcing", "retrying"]:

        # Check if already running
        if __salt__["saltutil.is_running"]("minionutil.update_release"):
            raise salt.exceptions.CommandExecutionError("Update is already running - please wait and try again later")
        # If started through startup states we also need to check this
        if __salt__["saltutil.is_running"]("state.*"):
            raise salt.exceptions.CommandExecutionError("Another state run is currently active - please wait and try again later")

        try:

            # Disable all scheduled jobs to prevent restart, shutdown etc. during update
            res = __salt__["schedule.disable"]()
            if not res.get("result", False):
                log.error("Unable to disable schedule: {:}".format(res))

            # Log what is going to happen
            if new["state"] == "pending":
                log.info("Updating release '{:}' => '{:}'".format(old["id"], new["id"]))
            else:
                log.warn("{:} update of release '{:}' => '{:}'".format(new["state"].title(), old["id"], new["id"]))

            # Register 'pending' or 'retrying' release in grains
            res = __salt__["grains.setval"]("release", new, destructive=True)
            if not res:
                log.error("Failed to store {:} release '{:}' in grains data".format(new["state"], new["id"]))

            # Fire a release event with initial state
            __salt__["event.fire"]({
                    "id": new["id"]
                },
                "system/release/{:}".format(new["state"])
            )

            # Ensure dynamic modules are updated (refresh of modules is done in highstate)
            res = __salt__["saltutil.sync_all"](refresh=False)
            ret["dynamic"] = res

            # Run highstate
            res = __salt__["state.highstate"]()
            if not isinstance(res, dict):
                raise salt.exceptions.CommandExecutionError("Failed to run highstate: {:}".format(res))

            ret["highstate"] = res

            # Pillar data has been refreshed during highstate so latest release ID might have changed
            new["id"] = __salt__["pillar.get"]("latest_release_id")

            # TODO: If above highstate chooses to restart below code will not run
            # (another update/highstate will run afterwards that will set release id)
            if all(v.get("result", False) for k, v in ret["highstate"].iteritems()):
                log.info("Completed highstate for release '{:}'".format(new["id"]))

                new["state"] = "updated"

            else:
                log.warn("Unable to complete highstate for release '{:}'".format(new["id"]))

                new["state"] = "failed"

            # Register 'updated' or 'failed' release in grains
            res = __salt__["grains.setval"]("release", new, destructive=True)
            if not res:
                log.error("Failed to store {:} release '{:}' in grains data".format(new["state"], new["id"]))

            # Fire a release event with final state
            __salt__["event.fire"]({
                    "id": new["id"]
                },
                "system/release/{:}".format(new["state"])
            )

        finally:

            # Always ensure scheduled jobs are re-enabled
            res = __salt__["schedule.enable"]()
            if not res.get("result", False):
                log.error("Unable to re-enable schedule: {:}".format(res))

    return ret


def change_master(host, confirm=False):
    """
    Change to different master host.
    """

    if not confirm:
        raise salt.exceptions.CommandExecutionError(
            "This command will replace your current master host to '{:s}' - add parameter 'confirm=true' to continue anyway".format(host))

    ret = {}

    ret["master_key_removed"] = __salt__["file.remove"]("/etc/salt/pki/minion/minion_master.pub")

    ret["config_changed"] = __salt__["file.replace"]("/etc/salt/minion", "^master:.*$", "master: {:s}".format(host))

    ret["restart"] = restart()

    return ret


def log_files():
    """
    List all minion log files.
    """

    return __salt__["cmd.shell"]("ls -lA /var/log/salt/minion*")


def last_logs(file="minion", until="$", match=".*", count=0, before=0, after=0, limit=100):
    """
    Get last log lines from minion log.

    Uses params:
        (file="minion", until="$", match=".*", count=50, before=0, after=0, limit=100)
    """

    return __salt__["log.query"]("/var/log/salt/{:s}".format(file),
        end=until,
        match=match,
        count=count,
        reverse=True,
        before=before,
        after=after,
        last=limit)


def last_errors(file="minion", until="$", level="error", count=0, before=0, after=0, limit=100):
    """
    Get last errors from minion log.

    Uses params:
        (file="minion", until="$", level="error", count=50, before=0, after=0, limit=100)
    """

    return last_logs(
        file=file,
        until=until,
        match="\[{: <8}\]".format(level),
        count=count,
        before=before,
        after=after,
        limit=limit)


def last_startup(file="minion", until="$", match="Setting up the Salt Minion", limit=100):
    """
    Get log lines for last startup sequence.

    Uses params:
        (file="minion", until="$", match="Setting up the Salt Minion", limit=100)
    """

    return last_logs(
        file=file,
        until=until,
        match=match,
        count=1,
        after=limit,
        limit=limit + 1)

