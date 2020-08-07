import os
import salt.ext.six as six
import salt_more
import urllib


def gnss_on(name):
    """
    """

    ret = {
        "name": name,
        "result": None,
        "changes": {},
        "comment": ""
    }

    res = salt_more.call_error_safe(__salt__["ec2x.gnss"])
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get current GNSS state: {:}".format(res["error"])
        return ret

    if res["value"] == "on":
        ret["result"] = True
        ret["comment"] = "GNSS is already turned on"
        return ret

    if __opts__["test"]:
        ret["comment"] = "GNSS will be turned on"
        return ret

    res = salt_more.call_error_safe(__salt__["ec2x.gnss"], enable=True)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to turn on GNSS: {:}".format(res["error"])
        return ret

    ret["result"] = True
    ret["comment"] = "Sucessfully turned on GNSS"
    ret["changes"]["old"] = "off"
    ret["changes"]["new"] = "on"
    return ret


def gnss_off(name):
    """
    """

    ret = {
        "name": name,
        "result": None,
        "changes": {},
        "comment": ""
    }

    res = salt_more.call_error_safe(__salt__["ec2x.gnss"])
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get current GNSS state: {:}".format(res["error"])
        return ret

    if res["value"] == "off":
        ret["result"] = True
        ret["comment"] = "GNSS is already turned off"
        return ret

    if __opts__["test"]:
        ret["comment"] = "GNSS will be turned off"
        return ret

    res = salt_more.call_error_safe(__salt__["ec2x.gnss"], enable=False)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to turn off GNSS: {:}".format(res["error"])
        return ret

    ret["result"] = True
    ret["comment"] = "Sucessfully turned off GNSS"
    ret["changes"]["old"] = "on"
    ret["changes"]["new"] = "off"
    return ret


def gnss_auto_start(name, enable=True):
    """
    """

    ret = {
        "name": name,
        "result": None,
        "changes": {},
        "comment": ""
    }

    res = salt_more.call_error_safe(__salt__["ec2x.gnss_auto_start"])
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get current GNSS auto start mode: {:}".format(res["error"])
        return ret

    old = res["value"]
    new = enable

    if old == new:
        ret["result"] = True
        ret["comment"] = "GNSS auto start is already {:}".format("enabled" if new else "disabled")
        return ret

    if __opts__["test"]:
        ret["comment"] = "GNSS auto start will be {:}".format("enabled" if new else "disabled")
        return ret

    res = salt_more.call_error_safe(__salt__["ec2x.gnss_auto_start"], enable=new)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to change GNSS auto start mode: {:}".format(res["error"])
        return ret

    ret["result"] = True
    ret["comment"] = "Sucessfully changed GNSS auto start mode"
    ret["changes"]["old"] = old
    ret["changes"]["new"] = new
    return ret


def gnss_assist_enabled(name):
    """
    """

    ret = {
        "name": name,
        "result": None,
        "changes": {},
        "comment": ""
    }

    # Check if enabled
    res = salt_more.call_error_safe(__salt__["ec2x.gnss_assist"])
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get current GNSS assist state: {:}".format(res["error"])
        return ret

    # If enabled do nothing
    if res["enabled"]:
        ret["result"] = True
        ret["comment"] = "GNSS assist is already enabled"
        return ret

    # Return now if in test mode
    if __opts__["test"]:
        ret["comment"] = "GNSS assist will be enabled"
        return ret

    # Go ahead and enable
    res = salt_more.call_error_safe(__salt__["ec2x.gnss_assist"], enable=True)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to enable GNSS assist: {:}".format(res["error"])
        return ret

    # Restart required
    res = salt_more.call_error_safe(__salt__["ec2x.power_off"], normal=True)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to power off EC2X module: {:}".format(res["error"])
        return ret

    ret["result"] = True
    ret["comment"] = "Sucessfully enabled GNSS assist"
    ret["changes"]["old"] = "disabled"
    ret["changes"]["new"] = "enabled"
    return ret


def gnss_assist_data_valid(name, force=False, valid_mins=-1, expire_mins=180, keep_cache=False, temp_storage="ram"):
    """
    Update GNSS assist data if no longer valid according to specified thresholds.
    """

    ret = {
        "name": name,
        "result": None,
        "changes": {},
        "comment": ""
    }

    # Get status of assist data
    res = salt_more.call_error_safe(__salt__["ec2x.gnss_assist_data"])
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get current state of GNSS assist data: {:}".format(res["error"])
        return ret

    if not force:

        # Check if assist data is valid according to thresholds
        valid = True
        if valid_mins > 0 and res["valid_mins"] >= valid_mins:
            valid = False
        if expire_mins > 0 and res["expire_mins"] <= expire_mins:
            valid = False

        if valid:
            ret["result"] = True
            ret["comment"] = "Existing GNSS assist data is still valid"
            return ret

    old = res

    # Return now if in test mode
    if __opts__["test"]:
        ret["comment"] = "GNSS assist data will be updated"
        return ret

    # Download new assist data file to cache
    cache_dir = os.path.join(__opts__["cachedir"], "extrn_files", __env__, "ec2x")
    __salt__["file.mkdir"](cache_dir)

    cached_file = os.path.join(cache_dir, urllib.quote_plus(name))
    res = __salt__["cmd.run_all"]("wget -O {:} {:}".format(cached_file, name))
    if res["retcode"] != 0:
        ret["result"] = False
        ret["comment"] = "Failed to download assist data file: {:}".format(res["stderr"])
        return ret

    filename = None
    storage = None

    try:
        # Upload cached assist data file to device
        res = salt_more.call_error_safe(__salt__["ec2x.upload_file"], cached_file, storage=temp_storage)
        if "error" in res:
            ret["result"] = False
            ret["comment"] = "Failed to upload GNSS assist data file to EC2X module: {:}".format(res["error"])
            return ret

        filename = res["name"]
        storage = res["storage"]
    finally:
        # Clean up cached file
        if not keep_cache:
            os.unlink(cached_file)

    try:
        # Inject assist time
        res = salt_more.call_error_safe(__salt__["ec2x.gnss_assist_time"])
        if "error" in res:
            ret["result"] = False
            ret["comment"] = "Failed to inject GNSS assist time into GNSS engine: {:}".format(res["error"])
            return ret

        # Inject assist data file
        res = salt_more.call_error_safe(__salt__["ec2x.gnss_assist_data"], filename=filename, storage=storage)
        if "error" in res:
            ret["result"] = False
            ret["comment"] = "Failed to inject GNSS assist data file '{:s}' into GNSS engine: {:}".format(filename, res["error"])
            return ret

    finally:
        # Delete assist data file from device
        res = salt_more.call_error_safe(__salt__["ec2x.delete_file"], filename, storage=storage)
        if "error" in res and ret["result"] == None:  # Do not overwrite other result if present
            ret["result"] = False
            ret["comment"] = "Failed to delete GNSS assist data file '{:s}' from EC2X module: {:}".format(filename, res["error"])
            return ret

    # Check again status of assist data
    res = salt_more.call_error_safe(__salt__["ec2x.gnss_assist_data"])
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get state of GNSS assist data after update: {:}".format(res["error"])
        return ret

    # Trigger event to notify that GNSS assist data has been updated
    __salt__["minionutil.trigger_event"]("system/device/ec2x/gnss/assist_data_updated")

    new = res

    ret["result"] = True
    ret["comment"] = "Successfully updated GNSS assist data"
    ret["changes"]["old"] = old
    ret["changes"]["new"] = new
    return ret


def gnss_assist_data_reset(name, type=3):
    """
    """

    ret = {
        "name": name,
        "result": None,
        "changes": {},
        "comment": ""
    }

    # Return now if in test mode
    if __opts__["test"]:
        ret["comment"] = "GNSS assist data will be reset"
        return ret

    # Go ahead and reset
    res = salt_more.call_error_safe(__salt__["ec2x.gnss_assist_data_reset"], type=type)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to reset GNSS assist data: {:}".format(res["error"])
        return ret

    ret["result"] = True
    ret["comment"] = "Sucessfully reset GNSS assist data"
    ret["changes"]["reset"] = True
    return ret


def gnss_set_fix_frequency(value):
    """
    """

    ret = {
        "value": value,
        "result": None,
        "changes": {},
        "comment": ""
    }


    res = salt_more.call_error_safe(__salt__["ec2x.gnss_fix_frequency"])
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get current GNSS fix frequency: {:}".format(res["error"])
        return ret

    old_fixfreq = res["fixfreq"]
    if res["fixfreq"] == value:
        ret["result"] = True
        ret["comment"] = "GNSS fix frequency already set to {:}".format(value)
        return ret

    if __opts__["test"]:
        ret["result"] = True
        ret["comment"] = "GNSS fix frequency will be set to {:}".format(value)
        return ret

    res = salt_more.call_error_safe(__salt__["ec2x.gnss_fix_frequency"], value=value)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to set GNSS fix frequency: {:}".format(res["error"])
        return ret

    # do we need to restart GNSS engine?
    res = salt_more.call_error_safe(__salt__["ec2x.gnss"])
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get GNSS power state: {:}".format(res["error"])
        return ret

    if res["value"] == "on":
        # yes we do
        res = salt_more.call_error_safe(__salt__["ec2x.gnss"], enable=False)
        if "error" in res:
            ret["result"] = False
            ret["comment"] = "Failed to restart GNSS: {:}".format(ret["error"])
            return ret

        res = salt_more.call_error_safe(__salt__["ec2x.gnss"], enable=True)
        if "error" in res:
            ret["result"] = False
            ret["comment"] = "Failed to restart GNSS: {:}".format(ret["error"])
            return ret

    ret["result"] = True
    ret["comment"] = "Sucessfully set GNSS fix frequency"
    ret["changes"]["old"] = old_fixfreq
    ret["changes"]["new"] = value
    return ret
