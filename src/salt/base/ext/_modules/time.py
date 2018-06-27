import logging
import salt.exceptions


# Define the module's virtual name
__virtualname__ = "time"

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def help():
    """
    This command.
    """

    return __salt__["sys.doc"](__virtualname__)


def status():
    """
    Show current time settings.
    """

    ret = {}

    res = __salt__["cmd.run"]("timedatectl status")

    pairs = (l.split(": ") for l in res.splitlines())
    for k, v in pairs:
        ret[k] = v

    return ret


def set(value):
    """
    Set system time.
    """

    res = __salt__["cmd.run_all"]("timedatectl set-time {:s}".format(value))
    if res["retcode"] == 0:
        return res
    else:
        raise salt.exceptions.CommandExecutionError(res["stderr"])
