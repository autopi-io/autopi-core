import logging
import salt_more


__virtualname__ = "stn"

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def _parse_trigger(value):
    ret = {}

    parts = value.split(",")
    ret["enable"] = parts[0].strip() == "ON"
    ret["rule"] = parts[1].strip()

    return ret


def power_trigger(name, enable=None, rule=None):
    """
    Ensure STN power trigger is configured.
    """

    ret = {
        "name": name,
        "result": None,
        "changes": {},
        "comment": ""
    }

    res = salt_more.call_error_safe(__salt__["stn.{:s}".format(name)])
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get current status of trigger: {:}".format(res["error"])
        return ret

    old = _parse_trigger(res["value"])
    new = {
        "enable": enable,
        "rule": rule
    }

    if old["enable"] == new["enable"] and old["rule"].upper() == new["rule"].upper():
        ret["result"] = True
        ret["comment"] = "Trigger is already up-to-date"
        return ret

    if __opts__["test"]:
        ret["comment"] = "Trigger will be updated"
        return ret

    res = salt_more.call_error_safe(__salt__["stn.{:s}".format(name)], enable=enable, rule=rule)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to update trigger: {:}".format(res["error"])
        return ret

    ret["result"] = True
    ret["comment"] = "Sucessfully updated trigger"
    ret["changes"]["old"] = old
    ret["changes"]["new"] = new
    return ret


def voltage_calibrated(name, url, samples=3):
    """
    Ensure STN voltage is calibrated to the reference value provided by the given HTTP endpoint.
    """

    ret = {
        "name": name,
        "result": None,
        "changes": {},
        "comment": ""
    }

    # First get reference voltage level
    res = salt_more.call_error_safe(__salt__["http.query"], url, decode=True, decode_type="json")
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get reference voltage level by URL '{:}': {:}".format(url, res["error"])
        return ret

    expected = res["dict"]["value"]

    # Then get actual voltage level
    res = salt_more.call_error_safe(__salt__["stn.volt_level"], samples=samples)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get actual voltage level: {:}".format(url, res["error"])
        return ret

    actual = res["average"]

    # Check if actual voltage matches expected
    if round(actual, 1) == round(expected, 1):
        ret["result"] = True
        ret["comment"] = "Voltage is already calibrated"
        return ret

    ret["changes"]["before"] = {
        "expected": expected,
        "actual": actual
    }

    if __opts__["test"]:
        ret["comment"] = "Voltage will be calibrated"
        return ret

    # Perform calibration
    res = salt_more.call_error_safe(__salt__["stn.volt_calibrate"], value=int("{:}{:0<2}".format(*str(round(expected, 2)).split("."))), confirm=True)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to calibrate voltage: {:}".format(res["error"])
        return ret

    # Get reference voltage level again
    res = salt_more.call_error_safe(__salt__["http.query"], url, decode=True, decode_type="json")
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get reference voltage level by URL '{:}': {:}".format(url, res["error"])
        return ret

    expected = res["dict"]["value"]

    # Then get actual voltage level again
    res = salt_more.call_error_safe(__salt__["stn.volt_level"], samples=samples)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get actual voltage level: {:}".format(url, res["error"])
        return ret

    actual = res["average"]

    ret["changes"]["after"] = {
        "expected": expected,
        "actual": actual
    }

    # Check if actual voltage does not match expected
    if round(actual, 1) != round(expected, 1):
        ret["result"] = False
        ret["comment"] = "Inaccurate voltage level after calibration"
        return ret

    return ret
