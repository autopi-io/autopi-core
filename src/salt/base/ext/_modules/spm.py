import logging
import salt.exceptions

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack


log = logging.getLogger(__name__)

client = EventDrivenMessageClient("spm")


def __init__(opts):
    client.init(opts)


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"]("spm")


def query(cmd, *args, **kwargs):
    """
    Queries a given SPM command.

    Arguments:
      - cmd (str): The SPM command to query.
    """

    return client.send_sync(_msg_pack(cmd, *args, **kwargs))


def battery(**kwargs):
    """
    Gets current battery voltage
    """

    if __opts__.get("spm.version", 2.0) < 3.0:
        raise salt.exceptions.CommandExecutionError("Only supported by SPM version 3.0 and above")

    return client.send_sync(_msg_pack("volt_readout", _converter="battery", **kwargs))


def reset():
    """
    Reset/restart the MCU. 
    """

    return client.send_sync(_msg_pack(_handler="reset"))



def flash_firmware(file, part_id, confirm=False, timeout=90):
    """
    Flashes new SPM firmware to the MCU.
    """

    ret = {}

    if not confirm:
        raise salt.exceptions.CommandExecutionError(
            "This command will flash firmware release '{:s}' onto the MCU - add parameter 'confirm=true' to continue anyway".format(file))

    # Flash firmware
    res = client.send_sync(_msg_pack(file, part_id, _handler="flash_firmware"), timeout=timeout)
    ret["output"] = res.get("output", None)

    return ret


def fuse(name, part_id, value=None, confirm=False):
    """
    Manages the fuse of the MCU.
    """

    if value != None and not confirm:
        raise salt.exceptions.CommandExecutionError(
            "This command will set the '{:}fuse' of the MCU - add parameter 'confirm=true' to continue anyway".format(name))

    return client.send_sync(_msg_pack(name, part_id, value=value, _handler="fuse"))


def led_pwm(**kwargs):
    """
    Change PWM frequency and/or duty cycle for LED.

    Optional arguments:
      - frequency (float): Change to frequency in Hz.
      - duty_cycle (float): Change to duty cycle in percent.
    """

    return client.send_sync(_msg_pack(_handler="led_pwm", **kwargs))


def manage(*args, **kwargs):
    """
    Runtime management of the underlying service instance.

    Supported commands:
      - 'hook list|call <name> [argument]... [<key>=<value>]...'
      - 'worker list|show|start|pause|resume|kill <name>'
      - 'reactor list|show <name>'
      - 'run <key>=<value>...'

    Examples:
      - 'spm.manage hook list'
      - 'spm.manage hook call query_handler status'
      - 'spm.manage worker list *'
      - 'spm.manage worker show *'
      - 'spm.manage worker start *'
      - 'spm.manage worker pause *'
      - 'spm.manage worker resume *'
      - 'spm.manage worker kill *'
      - 'spm.manage reactor list'
      - 'spm.manage reactor show *'
      - 'spm.manage run handler="query" args="[\"status\"]"'
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))

