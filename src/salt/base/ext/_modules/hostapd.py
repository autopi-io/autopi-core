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


def check_clients():
    """
    Checks which clients have connected or disconnected since the last check.

    Needs to be used in a process with a long living context (e.g. a service - *event_reactor*).
    If the command is run seperately it won't remember which clients were connected since the last
    time it was ran.
    """

    ctx_connected_clients = __context__.get("hostapd.connected_clients", set())
    res = clients()

    currently_connected_clients = set(mac for mac in res.keys())

    ret = {
        "newly_connected_clients": list(currently_connected_clients - ctx_connected_clients),
        "newly_disconnected_clients": list(ctx_connected_clients - currently_connected_clients),
    }

    __context__["hostapd.connected_clients"] = currently_connected_clients

    return ret


def clients_changed_trigger(result):
    """
    Triggers 'system/hostapd/connected' and 'system/hostapd/disconnected' events.
    """

    connected_event_tag = "system/hostapd/connected"
    disconnected_event_tag = "system/hostapd/disconnected"

    if len(result.get("newly_connected_clients", [])) > 0:
        connected_clients_data = { "values": result["newly_connected_clients"] }
        __salt__["minionutil.trigger_event"](connected_event_tag, data=connected_clients_data)

    if len(result.get("newly_disconnected_clients", [])) > 0:
        disconnected_clients_data = { "values": result["newly_disconnected_clients"] }
        __salt__["minionutil.trigger_event"](disconnected_event_tag, data=disconnected_clients_data)