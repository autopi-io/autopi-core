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


def flash_firmware(hex_file, confirm=False, check_only=True, timeout=90):
    """
    Flashes new SPM firmware to ATtiny.
    """

    ret = {}

    if not confirm:
        raise salt.exceptions.CommandExecutionError(
            "This command will flash firmware release '{:s}' onto the ATtiny - add parameter 'confirm=true' to continue anyway".format(hex_file))

    # TODO: It is only possible to test flash an already installed version without getting verification errors from avrdude!
    # Test flash firmware in read-only mode
    #res = client.send_sync(_msg_pack(hex_file, no_write=True, _handler="flash_firmware"), timeout=timeout)
    #ret["output"] = res.get("output", None)

    # Flash firmware
    if not check_only:
        res = client.send_sync(_msg_pack(hex_file, no_write=False, _handler="flash_firmware"), timeout=timeout)
        ret["output"] = res.get("output", None)

    return ret


def manage(*args, **kwargs):
    """
    Examples:
      - 'spm.manage handler'        Lists all available handlers.
      - 'spm.manage worker list *'  Lists all existing worker threads.
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))

