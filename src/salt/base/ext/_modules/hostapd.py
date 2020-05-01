import logging
import os
import re
import salt.exceptions
import subprocess


log = logging.getLogger(__name__)


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"]("hostapd")


def _cli(cmd, interface="uap0"):
    p = subprocess.Popen(["hostapd_cli", "-i", interface, cmd],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    out = p.stdout.read()
    err = p.stderr.read()
    if err:
      raise Exception(err)

    return out


def clients(interface="uap0"):
    """
    Returns all connected clients indexed by their MAC address.

    Optional arguments:
      - interface (str): Specific network interface. Default is 'uap0'
    """

    ret = {}

    res = _cli("all_sta", interface=interface)
    if not res:
        return ret

    regex = re.compile(
        "^(?P<mac>{mac:})\s(?P<info>.+?(?=\Z|^{mac:}\s))".format(
            mac="([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]){2}"
        ),
        re.MULTILINE | re.DOTALL
    )

    for match in regex.finditer(res):
        ret[match.group("mac")] = {k: int(v) if v.isdigit() else v for k, v in [l.split("=") for l in match.group("info").split(os.linesep) if l]}

    if not ret:
        raise salt.exceptions.CommandExecutionError("Failed to parse result with pattern: {:}".format(regex.pattern))

    return ret
