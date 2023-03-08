import base64
import bluenrg.codes
import bluenrg.commands
import bluenrg.events
import re
import datetime
import json
import logging
import RPi.GPIO as gpio
import time
import _strptime  # Attempt to avoid: Failed to import _strptime because the import lockis held by another thread

from jwcrypto import jwk, jwe
from messaging import EventDrivenMessageProcessor
from common_util import fromisoformat
from threading_more import intercept_exit_signal

from bluenrg.connection import SerialConnection
from bluenrg.interface import GATTTerminalInterface


READY_PIN = 22


log = logging.getLogger(__name__)

context = {}

# Message processor
edmp = EventDrivenMessageProcessor("ble", context=context, default_hooks={"workflow": "extended", "handler": "query"})

conn = SerialConnection()
iface = GATTTerminalInterface(conn)


@edmp.register_hook()
def query_handler(cmd, **kwargs):
    """
    Queries a given BlueNRG ACI command.
    """

    ret = {}

    timeout = kwargs.pop("_timeout", 1)

    # Find command class
    cmd_cls = getattr(bluenrg.commands, str(cmd).upper(), None)
    if cmd_cls == None:
        raise ValueError("No command found by name '{:}'".format(cmd))

    # Instantiate object
    cmd_obj = cmd_cls(**kwargs)

    res = conn.exec_sync(cmd_obj, timeout=timeout)

    # Add type to result
    ret["_type"] = "{:}.{:}.{:}".format(
        cmd_cls.__module__,
        cmd_cls.__name__,
        res.__class__.__name__
    )

    # Add parameter values to result
    ret.update(res.as_dict())

    return ret


@edmp.register_hook()
def interface_handler(*args):
    """
    Manages the interface to the BlueNRG device.
    """

    ret = {}

    for arg in args:
        func = getattr(iface, arg, None)

        if arg == "reset":
            iface.stop()

            # Reset device
            mode_handler(value="reset")

            # Give device some time to recover
            time.sleep(.1)

            _start_interface()
        elif arg == "history":
            ret["history"] = {
                "commands": [cmd.as_dict() for cmd in iface.command_history],
                "events": [evt.as_dict() for evt in iface.event_history]
            }
        elif func != None:
            res = func()

            if res:
                ret[arg] = res
        else:
            raise ValueError("Unsupported argument '{:}'".format(arg))

    ret["state"] = "started" if iface.is_running else "stopped"
    
    ret["connection"] = {
        "state": "opened" if conn.is_open else "closed",
        "device": conn.device
    }

    return ret


@edmp.register_hook()
def mode_handler(value=None):
    """
    Manages the low-level modes of the BlueNRG device.
    """

    ret = {}

    BOOT_PIN = "ext_misc2"
    RESET_PIN = "ext_misc1"

    kwargs = {}
    if value != None:
        if value == "boot":
            log.warning("Entering boot mode")

            kwargs["low"] = RESET_PIN   # Active low
            kwargs["high"] = ",".join([
                BOOT_PIN,               # Active high
                RESET_PIN               # Inactive high
            ])
        elif value == "reset":
            kwargs["low"] = RESET_PIN   # Active low
            kwargs["high"] = RESET_PIN  # Inactive high
        elif value == "normal":
            kwargs["low"] = BOOT_PIN    # Inactive low
            kwargs["high"] = RESET_PIN  # Inactive high
        else:
            raise ValueError("Unsupported mode")

    res = __salt__["spm.query"]("ext_pins", **kwargs)

    ret["boot"] = res["output"][BOOT_PIN] == True     # Active high
    ret["reset"] = res["output"][RESET_PIN] == False  # Active low
    
    return ret


@edmp.register_hook()
def flash_firmware_handler(bin_file, write=False, erase=False, verify=True):
    """
    Flashes new firmware to the BlueNRG device.
    """

    ret = {}

    try:

        # Ensure interface is stopped
        iface.stop()

        # Enter boot mode
        mode_handler(value="boot")

        # Give device some time to be ready (just to be safe)
        time.sleep(.1)

        params = ["stm32loader", "-p {:s}".format(conn.device), "-P none", "-a 0x10040000", "-g 0x10040000"]
        if write:
            params.append("-w")
        if erase:
            params.append("-e")
        if verify:
            params.append("-v")
        params.append(bin_file)

        res = __salt__["cmd.run_all"](" ".join(params))

        if res["retcode"] == 0:
            ret["warning"] = res["stderr"]
            ret["result"] = res["stdout"]

            if write:
                log.warning("Flashed firmware release '{:}' to device '{:}'".format(bin_file, conn.device))

        else:
            ret["error"] = res["stderr"]
            ret["result"] = res["stdout"]

            if write:
                log.error("Failed to flash firmware release '{:}' to device '{:}'".format(bin_file, conn.device))

    finally:

        log.info("Returning to normal mode")
        mode_handler(value="normal")

        # Ensure interface is started
        _start_interface()

    return ret


def _start_interface(retries=6, reset_on=4):
    """
    This handler will attempt to start the interface with some retry functionality.

    Parameters:
    - retries (int): The number of retries this function will do. Default: 6
    - reset_on (int): The retry attempt that this function will attempt to reset the BLE chip. Default: 4
    """
    if type(retries) != int or type(reset_on) != int:
        raise TypeError("Retries and reset_on needs to be integer numbers")

    for i in range(retries):
        # Ensure interface is stopped before attempting to start or reset mode
        iface.stop()

        # Reset interface on the fourth attempt
        if i == reset_on-1:
            log.warning("Resetting GATTTerminalInterface during startup sequence")
            mode_handler(value="reset")
            time.sleep(.2)

        try:
            iface.start()
            break # If above statement doesn't throw an error, we're good to go
        except Exception as e:
            if i == retries-1:
                # Last attempt, give full stack trace of exception
                log.exception("GATTTerminalInterface failed to start {} time(s).".format(i+1))
            else:
                log.warning("GATTTerminalInterface failed to start {} time(s). {}".format(i+1, e))


@intercept_exit_signal
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting BLE manager with settings: {:}".format(settings))

        # Initialize GPIO ready pin
        gpio.setwarnings(False)
        gpio.setmode(gpio.BCM)
        gpio.setup(READY_PIN, gpio.OUT, initial=gpio.LOW)  # Not yet ready

        # Set normal mode
        mode_handler(value="normal")
        
        # Configure serial connection
        for key, val in settings.get("serial_conn", {}).iteritems():
            setattr(conn, key, val)

        # Get specific settings for GATT terminal
        term_settings = settings.get("gatt_terminal", {})

        # Prepare authentication handler for terminal interface
        def on_authenticate(token):
            if not "auth_rsa_key_b64" in term_settings:
                raise Exception("No RSA key defined in settings")

            private_key = jwk.JWK()
            private_key.import_from_pem(base64.b64decode(term_settings["auth_rsa_key_b64"]))

            jwetoken = jwe.JWE()
            jwetoken.deserialize(token, key=private_key)
            decrypted_token = json.loads(jwetoken.payload)

            valid = fromisoformat(decrypted_token["valid_from_utc"]) <= datetime.datetime.utcnow() <= fromisoformat(decrypted_token["valid_to_utc"])

            return valid

        # Prepare command execute handler for terminal interface
        def on_execute(command, *args, **kwargs):

            # Check if command is allowed
            if not term_settings.get("cmd_allow_regex", None) or not re.match(term_settings["cmd_allow_regex"], command):
                raise ValueError("Command not allowed")

            res = __salt__[command](*args, **kwargs)

            return res

        # Setup terminal interface
        iface.on_authenticate = on_authenticate
        iface.on_execute = on_execute

        # Start the interface
        _start_interface()

        gpio.output(READY_PIN, iface.is_running)

        # Initialize and run message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        edmp.run()

    except Exception as ex:
        log.exception("Failed to start BLE manager")

        if settings.get("trigger_events", True):
            edmp.trigger_event({
                "reason": str(ex),
            }, "system/service/{:}/failed".format(__name__.split(".")[-1]))

        raise

    finally:
        log.info("Stopping BLE manager")

        # Signal no longer ready
        gpio.output(READY_PIN, gpio.LOW)
