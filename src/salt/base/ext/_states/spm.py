import logging
import salt_more
import time


__virtualname__ = "spm"

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def firmware_flashed(name, part_id, version):
    """
    Ensures a specific SPM firmware version is flashed onto the ATtiny.
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

    if old == new:
        ret["result"] = True
        ret["comment"] = "Firmware is already up-to-date"
        return ret

    if __opts__["test"]:
        ret["comment"] = "Firmware will be flashed"
        return ret

    res = salt_more.call_error_safe(__salt__["spm.flash_firmware"], name, part_id, confirm=True, check_only=False)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to flash firmware: {:}".format(res["error"])
        return ret

    ret["result"] = True
    ret["comment"] = "Sucessfully updated firmware"
    ret["changes"]["old"] = old
    ret["changes"]["new"] = new

    return ret


def voltage_calibrated(name, url, checks=10):
    """
    Ensure SPM voltage is calibrated to the expected value provided by the given HTTP endpoint.
    """

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

        # Reset volt_readout, expect None on minimum and maximum values
        res = salt_more.call_error_safe(__salt__["spm.query"], "volt_readout", reset=True)
        if "error" in res:
            res["error"] = "Error resetting volt_readout: {}".format(res["error"])
            return res

        # Wait for new, correct value to appear
        # TODO NV/HN: Should this have a maximum loop count?
        while True:
            time.sleep(.05)
            res = salt_more.call_error_safe(__salt__["spm.query"], "volt_readout")
            if "error" in res:
                res["error"] = "Error calling volt_readout: {}".format(res["error"])
                return res

            if res["maximum"] != None and res["minimum"] != None:
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
    res = salt_more.call_error_safe(__salt__["spm.query"], "volt_readout")
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get actual voltage level: {}".format(res["error"])
        return ret

    actual_V = res["current"]

    # Check if actual voltage matches expected voltage
    if round(actual_V, 1) == round(expected_V, 1):
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
    res = salt_more.call_error_safe(__salt__["spm.query"], "volt_readout")
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get actual voltage level: {}".format(res["error"])
        return ret

    actual_V = res["current"]

    # Perform calibration
    calculated_volt_factor = round(expected_V / actual_V, 3)
    res = change_volt_factor_and_wait(calculated_volt_factor)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to calibrate voltage: {}".format(res["error"])
        return ret

    # Double check calibration
    for i in range(checks):
        # NOTE NV: Maybe there should be time.sleep or waiting for a new value between every check?
        # It looks like the voltage reported is the same if the attempts are too quick, it kind of
        # makes the loop redundant

        # Get expected voltage
        res = salt_more.call_error_safe(__salt__["http.query"], url, decode=True, decode_type="json")
        if "error" in res:
            ret["result"] = False
            ret["comment"] = "Failed to get expected voltage level by URL '{}': {}".format(url, res["error"])
            return ret

        expected_V = res["dict"]["value"]

        # Get actual voltage
        res = salt_more.call_error_safe(__salt__["spm.query"], "volt_readout")
        if "error" in res:
            ret["result"] = False
            ret["comment"] = "Failed to get actual voltage level: {}".format(res["error"])
            return ret

        actual_V = res["current"]

        ret["changes"]["after"] = {
            "volt_factor": calculated_volt_factor,
            "expected": expected_V,
            "actual": actual_V,
            "checks_attempted": i+1,
        }

        # Check if voltages match
        if round(actual_V, 1) != round(expected_V, 1):
            ret["result"] = False
            ret["comment"] = "Inaccurate voltage level after calibration"
            return ret

    ret["result"] = True
    return ret