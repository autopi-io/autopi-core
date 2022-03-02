import logging
import re
import subprocess

from messaging import extract_error_from

log = logging.getLogger(__name__)

LSUSB_OUTPUT_REGEX = "^Bus (?P<bus>[0-9]{3}) Device (?P<device>[0-9]{3}): ID (?P<vendor>[a-z0-9]{4}):(?P<product>[a-z0-9]{4}) (?P<name>.*)$"
pattern = None


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"]("usbutil")


def devices():
    """
    Returns the lsusb bash command result as a list of dictionaries, each dict is a separete device.
    An example dict structure is presented below:

    - bus: '001'                          # the linux system bus number
      device: '001'                       # the linux system device number
      name: Linux Foundation 2.0 root hub # the name of the device
      product: '0002'                     # the product number (hex) of the device
      vendor: 1d6b                        # the vendor number (hex) of the device
    """

    p = subprocess.Popen(["lsusb"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    out = p.stdout.read()
    err = p.stderr.read()

    if err:
        raise salt.exceptions.CommandExecutionError("Failed to run lsusb: {}".format(err))

    # Ensure pattern is compiled
    global pattern
    if not pattern:
        log.info("Compiling regex pattern {}".format(LSUSB_OUTPUT_REGEX))
        pattern = re.compile(LSUSB_OUTPUT_REGEX)

    # Parse output
    devices = []
    for dev_line in out.split("\n"):
        if dev_line == "":
            # empty line, skip
            continue

        match = pattern.match(dev_line)
        if not match:
            log.warning("Couldn't match line {}".format(dev_line))
            continue

        devices.append({
            "bus":     match.group("bus"),
            "device":  match.group("device"),
            "vendor":  match.group("vendor"),
            "product": match.group("product"),
            "name":    match.group("name"),
        })

    return {
        "values": devices
    }


def devices_changed_trigger(result):
    """
    Triggers 'system/usb/<vendor>/<product>/connected' and 'system/usb/<vendor>/<product>/disconnected'
    events when USB devices are connected or disconnected.

    Expects the result to be in the format as `usbutil.devices` return format.
    """

    # Error handling
    error = extract_error_from(result)
    if error:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Devices changed trigger got error result: {}".format(result))
        return

    ctx = __context__.setdefault("usbutil.devices_changed_trigger", {})

    previous_devices = ctx.get("devices", [])
    current_devices = result["values"]

    for dev in previous_devices:
        if dev not in current_devices:
            # Device disconnected
            tag = "system/usb/{}/{}/disconnected".format(dev["vendor"], dev["product"])
            __salt__["minionutil.trigger_event"](tag, data={
                "bus": dev["bus"],
                "device": dev["device"],
                "name": dev["name"],
            })

    for dev in current_devices:
        if dev not in previous_devices:
            # Device connected
            tag = "system/usb/{}/{}/connected".format(dev["vendor"], dev["product"])
            __salt__["minionutil.trigger_event"](tag, data={
                "bus": dev["bus"],
                "device": dev["device"],
                "name": dev["name"],
            })

    # Update state
    ctx["devices"] = result["values"]


def check_expected_devices():
    """
    Triggers 'system/usb/<vendor>/<product>/not_connected' events when specified (must be present) devices
    are missing, i.e. not seen for whatever reason when running the `usbutil.devices` command.
    """

    res = devices()
    error = extract_error_from(res)
    if error:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Check expected devices got error result: {}".format(res))
        return

    expected_usb_devices = __opts__.get("expected_usb_devices", [])
    vendors_products = [ "{}:{}".format(dev["vendor"], dev["product"]) for dev in res["values"] ]

    for dev in expected_usb_devices:
        if dev not in vendors_products:
            vendor, product = dev.split(":")
            tag = "system/usb/{}/{}/not_connected".format(vendor, product)
            __salt__["minionutil.trigger_event"](tag)