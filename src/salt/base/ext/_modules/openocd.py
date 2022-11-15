import logging
import salt.exceptions


# Define the module's virtual name
__virtualname__ = "openocd"

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"](__virtualname__)


def program(file, *cfg_files, **kwargs):
    """
    Loads a program onto a MCU.

    Arguments:
      - file (str): Path of program binary file.
      - interface_cfg (str): Path of interface configuration file.
      - target_cfg (str): Path of target configuration file.

    Optional arguments:
      - raise_on_error (bool): Raise an error upon failure. Default is 'True'.
      - start_address (string): Flash memory start address in hex format (required for .bin files)
    """

    ret = {}

    start_address = kwargs.get("start_address")

    cmd = "program {:} verify reset exit {:}".format(file, start_address if start_address else "")

    params = ["openocd"]
    params.extend(["-f {:}".format(c) for c in cfg_files])
    params.append("-c \"{:}\"".format(cmd))

    res = __salt__["cmd.run_all"](" ".join(params))

    if res["retcode"] == 0:
        ret["output"] = res["stderr"]
    else:
        if kwargs.get("raise_on_error", True):
            raise salt.exceptions.CommandExecutionError(res["stderr"])

        ret["error"] = res["stderr"]
        ret["output"] = res["stdout"]

    return ret
