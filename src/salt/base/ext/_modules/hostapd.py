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
    Triggers 'system/hostapd/client/<mac>/connected' and 'system/hostapd/client/<mac>/disconnected' events.

    The trigger expects the result to be given in the format of what hostapd.clients returns,
    which is also the main use case for this trigger.
    """

    if result: # No need to check for errors in empty results
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

    # Update context
    ctx["connected_clients"] = currently_connected_clients


def expect_allow_list_handler():
    """
    This handler triggers 'system/hostapd/client/<mac>/not_connected' events for clients that aren't
    connected from the hostapd allow list.

    In order for the handler to work properly the allow list must be stored in the default hostapd.accept
    file, which will be the case if the allow list is set through the Advanced Settings in the Cloud.
    """

    hostapd_allow_list_path = "/etc/hostapd/hostapd.accept"

    if not os.path.exists(hostapd_allow_list_path):
        raise salt.exceptions.CommandExecutionError("File {} doesn't exist".format(hostapd_allow_list_path))

    with open(hostapd_allow_list_path, 'r') as fd:
        # Avoid adding an empty line to the allow list
        allow_list = [ line for line in fd.read().split("\n") if line != "" ]

    currently_connected_clients = clients()

    for mac in allow_list:
        if mac not in currently_connected_clients:
            tag = "system/hostapd/client/{}/not_connected".format(mac)
            __salt__["minionutil.trigger_event"](tag)