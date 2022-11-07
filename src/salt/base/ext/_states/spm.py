import logging
import salt_more
import time


__virtualname__ = "spm"

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def firmware_flashed(name, part_id, version, force=False):
    """
    Ensures a specific SPM firmware version is flashed onto the MCU.
    """

    ret = {
        "name": name,
        "result": None,
        "changes": {},
        "comment": ""
    }

    res = salt_more.call_error_safe(__salt__["spm.query"], "version")
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get version of installed firmware: {:}".format(res["error"])
        return ret

    old = res["value"]
    new = str(version)

    if old == new and not force:
        ret["result"] = True
        ret["comment"] = "Firmware is already up-to-date"
        return ret

    if __opts__["test"]:
        ret["comment"] = "Firmware will be flashed"
        return ret

    res = salt_more.call_error_safe(__salt__["spm.flash_firmware"], name, part_id, confirm=True)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to flash firmware: {:}".format(res["error"])
        return ret

    ret["result"] = True
    ret["comment"] = "Sucessfully updated firmware"
    ret["changes"]["old"] = old
    ret["changes"]["new"] = new

    return ret


def voltage_calibrated(name, url, checks=10, acceptable_difference=0.02, factor_precision=3, volt_readout_samples=10):
    """
    Ensure SPM voltage is calibrated to the expected value provided by the given HTTP endpoint.
    """

    def get_new_volt_readout():
        """
        Resets the SPM in order to get a fresh voltage readout.
        """

        res = salt_more.call_error_safe(__salt__["spm.query"], "volt_readout", reset=True)
        if "error" in res:
            return res

        for i in range(checks):
            time.sleep(.2)
            res = salt_more.call_error_safe(__salt__["spm.query"], "volt_readout")
            if "error" in res:
                return res

            if res["max"] != None and res["min"] != None:
                return res

        res["error"] = "Maximum number of retries ({}) exceeded, SPM couldn't get a new voltage reading.".format(checks)
        return res

    def get_average_volt_readout():
        """
        Resets the SPM readings and awaits for a new readout in order to get a fresh value.
        """

        values = []

        for i in range(volt_readout_samples):
            res = get_new_volt_readout()
            if "error" in res:
                return res

            values.append(res["value"])

        # Calculate average after all samples have been gotten
        avg = sum(values) / len(values)

        return {
            "value": round(avg, 2), # Need to round?
        }

    def compare_voltage(expected_V, actual_V):
        """
        Checks the actual voltage against an expected voltage.
        Returns True if voltage is in acceptable range or False otherwise.
        """

        diff = expected_V - actual_V

        if diff < 0:
            # Don't accept the device readings to be higher than actual voltage
            return False

        if diff > acceptable_difference:
            return False

        return True

    def change_volt_factor_and_wait(new_volt_factor):
        """
        Changes the volt_factor to the new value and then waits until the SPM can report a new,
        correct voltage. Returns the new volt_readout.
        """
        # Set volt_factor
        res = salt_more.call_error_safe(__salt__["spm.query"], "volt_factor", value=new_volt_factor)
        if "error" in res:
            res["error"] = "Error updating volt_factor: {}".format(res["error"])
            return res

        res = get_new_volt_readout()
        return res

    ret = {
        "name": name,
        "result": None,
        "changes": {},
        "comment": "",
    }

    # Get current volt_factor
    res = salt_more.call_error_safe(__salt__["spm.query"], "volt_factor")
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get current volt_factor value: {}".format(res["error"])
        return ret

    current_volt_factor = res["value"]

    # Get expected voltage level
    res = salt_more.call_error_safe(__salt__["http.query"], url, decode=True, decode_type="json")
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get expected voltage level by URL '{}': {}".format(url, res["error"])
        return ret

    expected_V = res["dict"]["value"]

    # Get actual voltage level from device
    #res = salt_more.call_error_safe(__salt__["spm.query"], "volt_readout")
    res = get_average_volt_readout()
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get actual voltage level: {}".format(res["error"])
        return ret

    actual_V = res["value"]

    # Check if actual voltage matches expected voltage
    if compare_voltage(expected_V, actual_V):
        ret["result"] = True
        ret["comment"] = "Voltage is already calibrated"
        return ret

    ret["changes"]["before"] = {
        "volt_factor": current_volt_factor,
        "expected": expected_V,
        "actual": actual_V
    }

    if __opts__["test"]:
        ret["comment"] = "Voltage will be calibrated"
        return ret

    # Reset volt_factor to be able to make proper calculation
    res = change_volt_factor_and_wait(0.0)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to reset volt_factor: {}".format(res["error"])
        return ret

    # Make sure to mention change of volt_factor to 0.0 if the execution fails prematurely
    ret["changes"]["after"] = {
        "volt_factor": 0.0,
    }

    # Read new actual voltage
    #res = salt_more.call_error_safe(__salt__["spm.query"], "volt_readout")
    res = get_average_volt_readout()
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get actual voltage level: {}".format(res["error"])
        return ret

    actual_V = res["value"]

    # Perform calibration
    calculated_volt_factor = round(expected_V / actual_V, factor_precision)
    res = change_volt_factor_and_wait(calculated_volt_factor)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to calibrate voltage: {}".format(res["error"])
        return ret

    # Double check calibration
    checks_attempted = 0
    previous_ts = None
    while checks_attempted < checks:
        # Get expected voltage
        res = salt_more.call_error_safe(__salt__["http.query"], url, decode=True, decode_type="json")
        if "error" in res:
            ret["result"] = False
            ret["comment"] = "Failed to get expected voltage level by URL '{}': {}".format(url, res["error"])
            return ret

        if previous_ts == None:
            # First iteration
            previous_ts = res["dict"]["ts"]

        elif previous_ts >= res["dict"]["ts"]:
            time.sleep(.25) # Approx. the amount of time sigrok takes to get a new value
            continue

        else:
            # Otherwise save the ts for next iteration
            previous_ts = res["dict"]["ts"]

        expected_V = res["dict"]["value"]

        # Get actual voltage
        #res = salt_more.call_error_safe(__salt__["spm.query"], "volt_readout")
        res = get_average_volt_readout()
        if "error" in res:
            ret["result"] = False
            ret["comment"] = "Failed to get actual voltage level: {}".format(res["error"])
            return ret

        actual_V = res["value"]

        checks_attempted += 1
        ret["changes"]["after"] = {
            "volt_factor": calculated_volt_factor,
            "expected": expected_V,
            "actual": actual_V,
            "checks_attempted": checks_attempted,
        }

        # Ensure voltage matches
        if not compare_voltage(expected_V, actual_V):
            ret["result"] = False
            ret["comment"] = "Inaccurate voltage level after calibration"
            return ret

    ret["result"] = True
    return ret