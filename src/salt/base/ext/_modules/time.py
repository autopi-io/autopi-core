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
        ret[k.strip().lower().replace(" ", "_")] = v.strip()

    return ret


def set(value, adjust_system_clock=False):
    """
    Set system time.
    """

    ret = {}

    cmd = ["timedatectl"]
    if adjust_system_clock:
        cmd.append("--adjust-system-clock")
    cmd.append("set-time '{:s}'".format(value))

    res = __salt__["cmd.run_all"](" ".join(cmd))
    if res["retcode"] != 0:
        raise salt.exceptions.CommandExecutionError(res["stderr"])

    return ret


def ntp(enable=True):
    """
    Enable or disable network time synchronization.
    """

    ret = {}

    res = __salt__["cmd.run_all"]("timedatectl set-ntp '{:d}'".format(enable))
    if res["retcode"] != 0:
        raise salt.exceptions.CommandExecutionError(res["stderr"])

    return ret
