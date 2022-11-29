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


def program(elf_file, *cfg_files, **kwargs):
    """
    Loads a program onto a MCU.

    Arguments:
      - elf_file (str): Path of program binary file.
      - interface_cfg (str): Path of interface configuration file.
      - target_cfg (str): Path of target configuration file.

    Optional arguments:
      - raise_on_error (bool): Raise an error upon failure. Default is 'True'.
    """

    ret = {}

    cmd = "program {:} verify reset exit".format(elf_file)

    params = ["openocd"]
    params.extend(["-f {:}".format(c) for c in cfg_files])
    params.append("-c \"{:}\"".format(cmd))

    res = __salt__["cmd.run_all"](" ".join(params))

    if res["retcode"] == 0:
        out = res["stderr"]

        err = ""
        if out.find("** Programming Finished **") < 0:
            err = "Programming did not finish"
        elif out.find("** Verified OK **") < 0:
            err = "Verification failed"

        if err:
            log.error("Failed to program due to error: {:}".format(err))
            log.error("Output:\n{:}".format(out))

            if kwargs.get("raise_on_error", True):
                raise salt.exceptions.CommandExecutionError(err)

            ret["error"] = err

        ret["output"] = out
    else:
        log.error("Failed to program due to error code: {:}".format(res["retcode"]))
        log.error("Output:\n{:}".format(res["stderr"]))

        if kwargs.get("raise_on_error", True):
            raise salt.exceptions.CommandExecutionError(res["stderr"])

        ret["error"] = res["stderr"]
        ret["output"] = res["stdout"]

    return ret
