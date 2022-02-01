import logging
import os
import re
import salt.exceptions
import subprocess

from messaging import extract_error_from

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


def clients_changed_trigger(result):
    """
    Triggers 'system/hostapd/connected' and 'system/hostapd/disconnected' events.

    Expect response to be in the format given as the hostapd.clients function's return format.

    Events are triggered based on previously connected hostapd clients which are kept track of in
    the context.
    """

    error = extract_error_from(result)
    if error:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Motion event trigger got error result: {}".format(result))
        return

    ctx = __context__.setdefault("hostapd.clients_changed_trigger", {})

    previously_connected_clients = ctx.get("connected_clients", set())
    currently_connected_clients = set(mac for mac in result.keys())

    newly_connected_clients = list(currently_connected_clients - previously_connected_clients)
    newly_disconnected_clients = list(previously_connected_clients - currently_connected_clients)

    for mac in newly_connected_clients:
        tag = "system/hostapd/client/{}/connected".format(mac)
        __salt__["minionutil.trigger_event"](tag)

    for mac in newly_disconnected_clients:
        tag = "system/hostapd/client/{}/disconnected".format(mac)
        __salt__["minionutil.trigger_event"](tag)

    # update context
    ctx["connected_clients"] = currently_connected_clients
