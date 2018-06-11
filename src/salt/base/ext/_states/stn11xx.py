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