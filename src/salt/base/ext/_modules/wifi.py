import logging
import parsing
import salt.exceptions

from iw_parse import get_interfaces


# Define the module's virtual name
__virtualname__ = "wifi"

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"](__virtualname__)


def status(interface="wlan0"):
    """
    Get current WPA/EAPOL/EAP status.

    Optional arguments:
      - interface (str): Default is 'wlan0'.
    """

    res = __salt__["cmd.run_all"]("wpa_cli -i {:} status".format(interface))
    if res["retcode"] != 0:
        raise salt.exceptions.CommandExecutionError(res["stderr"])

    ret = parsing.into_dict_parser(res["stdout"], separator="=")
    return ret


def scan(interface="wlan0"):
    """
    Give the list of Access Points and Ad-Hoc cells in range.

    Optional arguments:
      - interface (str): Default is 'wlan0'.
    """

    return get_interfaces(interface=interface)
