import logging
import salt_more


__virtualname__ = "spm"

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def firmware_flashed(name, version):
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
    new = version

    if old == new:
        ret["result"] = True
        ret["comment"] = "Firmware is already up-to-date"
        return ret

    if __opts__["test"]:
        ret["comment"] = "Firmware will be flashed"
        return ret

    res = salt_more.call_error_safe(__salt__["spm.flash_firmware"], name, confirm=True, check_only=False)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to flash firmware: {:}".format(res["error"])
        return ret

    ret["result"] = True
    ret["comment"] = "Sucessfully updated firmware"
    ret["changes"]["old"] = old
    ret["changes"]["new"] = new

    return ret

