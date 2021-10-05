import datetime
import logging
import salt.exceptions
import salt.utils.event
import salt.utils.jid
import time
import os

from retrying import retry
from salt.utils.network import host_to_ips as _host_to_ips
from salt.utils.network import remote_port_tcp as _remote_port_tcp


log = logging.getLogger(__name__)


def help():
    """
    Shows this help information.
    """
    
    return __salt__["sys.doc"]("minionutil")


def trigger_event(tag, data={}):
    """
    Triggers an event on the minion event bus.
    """

    log.info("Triggering event '{:s}': {:}".format(tag, data))

    return __salt__["event.fire"](data, tag)


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

    Optional arguments:
      - reason (str): Reason code that tells why we decided to restart. Default is 'unknown'.
    """

    return request_restart(immediately=True, reason=reason)


def request_restart(pending=True, immediately=False, delay=10, expiration=1200, reason="unknown"):
    """
    Request for a future restart of the minion service.

    Optional arguments:
      - pending (bool): Default is 'True'.
      - immediately (bool): Default is 'False'.
      - delay (int): Default is '10'.
      - expiration (int): Default is '1200'.
      - reason (str): Reason code that tells why we decided to restart. Default is 'unknown'.
    """

    if pending or __context__.get("minionutil.request_restart", False):
        if immediately:
            log.warn("Performing minion restart in {:} second(s) because of reason '{:}'".format(delay, reason))

            # Trigger a restarting event
            trigger_event("system/minion/restarting", data={"reason": reason})

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

    Optional arguments:
      - force (bool): Default is 'False'.
      - dry_run (bool): Default is 'False'.
      - only_retry (bool): Default is 'False'.
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
        if log.isEnabledFor(logging.DEBUG):
            log.debug("No failed update is pending for retry")

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

            # Pause worker threads in order to release resources during update
            if __salt__["pillar.get"]("update_release:pause_workers", default=False):

                # Pause all OBD workers
                try:
                    __salt__["obd.manage"]("worker", "pause", "*")
                except:
                    log.exception("Failed to pause all OBD workers before update")

                # Also ensure any OBD exporter is stopped
                try:
                    __salt__["obd.file_export"](run=False)
                except:
                    log.exception("Failed to stop OBD exporter before update")

                # Pause all accelerometer workers
                try:
                    __salt__["acc.manage"]("worker", "pause", "*")
                except:
                    log.exception("Failed to pause all accelerometer workers before update")

            # Log what is going to happen
            if new["state"] == "pending":
                log.info("Updating release '{:}' => '{:}'".format(old["id"], new["id"]))
            else:
                log.warn("{:} update of release '{:}' => '{:}'".format(new["state"].title(), old["id"], new["id"]))

            # Register 'pending' or 'retrying' release in grains
            res = __salt__["grains.setval"]("release", new, destructive=True)
            if not res:
                log.error("Failed to store {:} release '{:}' in grains data".format(new["state"], new["id"]))

            # Trigger a release event with initial state
            trigger_event("system/release/{:}".format(new["state"]), data={"id": new["id"]})

            # Broadcast notification to all terminals
            try:
                __salt__["cmd.run"]("wall -n \"\nATTENTION ({:}):\n\nUpdate release initiated in state '{:}'.\nPlease do not power off the device until the update is completed.\n\n(Press ENTER to continue)\"".format(datetime.datetime.utcnow(), new["state"]))
            except:
                log.exception("Failed to broadcast update release initiated notification")

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

            # Trigger a release event with final state
            trigger_event("system/release/{:}".format(new["state"]), data={"id": new["id"]})

            # Broadcast notification to all terminals
            try:
                __salt__["cmd.run"]("wall -n \"\nATTENTION ({:}):\n\nUpdate release completed in state '{:}'.\n\n(Press ENTER to continue)\"".format(datetime.datetime.utcnow(), new["state"]))
            except:
                log.exception("Failed to broadcast update release completed notification")

        finally:

            # Ensure scheduled jobs are re-enabled
            res = __salt__["schedule.enable"]()
            if not res.get("result", False):
                log.error("Unable to re-enable schedule: {:}".format(res))

            # Resume worker threads again
            if __salt__["pillar.get"]("update_release:pause_workers", default=False):

                # Resume all OBD workers
                try:
                    __salt__["obd.manage"]("worker", "resume", "*")
                except:
                    log.exception("Failed to resume all OBD workers after update")

                # Resume all accelerometer workers
                try:
                    __salt__["acc.manage"]("worker", "resume", "*")
                except:
                    log.exception("Failed to resume all accelerometer workers after update")

    return ret


def change_master(host, confirm=False, show_changes=False):
    """
    Change to different master host.

    Arguments:
      - host (str): Hostname of the new master to change to.

    Optional arguments:
      - confirm (bool): Acknowledge the execution of this command. Default is 'False'.
      - show_changes (bool): Show the changes made in the files '/etc/salt/minion' and '/boot/host.aliases'. Default is 'False'.

    NOTE: When the master (hub) is changed, the API endpoint URL won't be updated automatically
    unless there is a pending sync (for example coming from an update) that will execute the
    minion.config state.

    NOTE: When moving back and forth between envs and the key hasn't been accepted,
    the device will keep retrying to connect to the master. If then the salt-minion service
    is restarted, the service won't shutdown until a SIGKILL is sent to the process (i.e. the
    salt-minion service will keep retrying to connect to the salt-master)
    """

    if not confirm:
        raise salt.exceptions.CommandExecutionError(
            "This command will replace your current master host to '{:s}' - add parameter 'confirm=true' to continue anyway".format(host))

    ret = {}

    # remove master keys
    # NOTE: The removal of the pki keys will make it lose connection to the master, i.e. it's
    # not possible to reach the minion after the command is executed
    ret["master_key_removed"] = __salt__["file.remove"]("/etc/salt/pki/minion/minion_master.pub")

    # change master in minion config to "hub"
    ret["config_changed"] = __salt__["file.replace"]("/etc/salt/minion", "^master:.*$", "master: hub", show_changes=show_changes)

    # set host.aliases to the actual host
    ret["host_aliases_changed"] = __salt__["file.replace"]("/boot/host.aliases", "^hub .*$", "hub {}".format(host), show_changes=show_changes)

    return ret


def master_status(master=None, **kwargs):
    """
    Get status of connection to master.
    Implementation originates from the 'status.master' command but without the logic to trigger events.
    """

    ret = {
        "online": False,
        "ip": None
    }

    if master == None:
        master = __salt__["config.get"]("master", default="hub")

    master_ips = None
    if master:
        master_ips = _host_to_ips(master)

    if not master_ips:
        return ret

    port = __salt__["config.get"]("publish_port", default=4505)
    connected_ips = _remote_port_tcp(port)

    # Get connection status for master
    for master_ip in master_ips:
        if master_ip in connected_ips:
            ret["online"] = True
            ret["ip"] = master_ip

            break

    return ret


@retry(stop_max_attempt_number=5, wait_fixed=1000)  # Commands 'schedule.*' are seen to have failed during startup
def status_schedule(name=None, **kwargs):
    """
    Dedicated to be called from schedule and trigger minion status events.
    """

    # Determine name of schedule
    name = kwargs.get("__pub_schedule", name)
    if not name:
        raise salt.exceptions.CommandExecutionError("No schedule name could be determined")

    # Get enabled schedule details
    schedule = __salt__["schedule.is_enabled"](name)
    if not schedule:
        raise salt.exceptions.CommandExecutionError("No enabled schedule found by name '{:}'".format(name))

    # Get previous status if available
    old = schedule.get("metadata", {}).get("status", None)
    if not old:

        # Trigger a ready event
        trigger_event("system/minion/ready")

    # Get current status
    new = master_status()
    if not old or old["online"] != new["online"]:

        # Update scheduled job with new status
        schedule.setdefault("metadata", {})["status"] = new
        schedule["run_on_start"] = False  # Prevents from running right after modify

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Modifing schedule: {:}".format(schedule))

        __salt__["schedule.modify"](**dict(persist=False, **schedule))

        # Trigger an online/offline event
        trigger_event("system/minion/online" if new["online"] else "system/minion/offline")


def log_files():
    """
    List all minion log files.
    """

    return __salt__["cmd.shell"]("ls -lA /var/log/salt/minion*")


def last_logs(file="minion", until="$", match=".*", count=0, before=0, after=0, limit=100):
    """
    Get last log lines from minion log.

    Optional arguments:
      - file (str): Default is 'minion'.
      - until (str): Default is '$'.
      - match (str): Default is '.*'.
      - count (int): Default is '0'.
      - before (int): Default is '0'.
      - after (int): Default is '0'.
      - limit (int): Default is '100'.
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

    Optional arguments:
      - file (str): Default is 'minion'.
      - until (str): Default is '$'.
      - level (str): Default is 'error'.
      - count (int): Default is '0'.
      - before (int): Default is '0'.
      - after (int): Default is '0'.
      - limit (int): Default is '100'.
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

    Optional arguments:
      - file (str): Default is 'minion'.
      - until (str): Default is '$'.
      - match (str): Default is 'Setting up the Salt Minion'.
      - limit (int): Default is '100'.
    """

    return last_logs(
        file=file,
        until=until,
        match=match,
        count=1,
        after=limit,
        limit=limit + 1)

