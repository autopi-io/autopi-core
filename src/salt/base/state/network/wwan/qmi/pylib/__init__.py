import string
import subprocess

from .parser import parse, parse_signal_strength


def cli(option, device="/dev/cdc-wdm0"):
    """
    Call QMI command line interface.

    Arguments:
      - option (str): Command option.

    Optional arguments:
      - device (str): Default is '/dev/cdc-wdm0'.
    """

    p = subprocess.Popen(["qmicli", "--silent", "--device={:s}".format(device), "--{:s}".format(option)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = p.stdout.read()
    err = p.stderr.read()

    if err:
        raise Exception(err)

    # Filter out any non printable characters
    printable = set(string.printable)
    return filter(lambda c: c in printable, out)


#
# Network Access Service
#

def nas_get_cell_location_info():
    """
    Get cell location info.
    """

    out = cli("nas-get-cell-location-info")

    return parse(out, skip_first=1)

def nas_get_home_network():
    """
    Get home network.
    """

    out = cli("nas-get-home-network")

    return parse(out, skip_first=1)

def nas_get_operator_name():
    """
    Get operator name data.
    """

    out = cli("nas-get-operator-name")

    return parse(out)

def nas_get_system_info():
    """
    Get system info.
    """

    out = cli("nas-get-system-info")

    return parse(out, skip_first=1)

def nas_get_serving_system():
    """
    Get serving system.
    """

    out = cli("nas-get-serving-system")

    return parse(out, skip_first=1)

def nas_get_signal_info():
    """
    Get signal strength.
    """

    out = cli("nas-get-signal-info")

    return parse(out, skip_first=1)

def nas_get_signal_strength(rated_only=False, include_desc=False):
    """
    Get signal strength.

    Optional arguments:
      - rated_only (bool): Default is 'False'.
      - include_desc (bool): Default is 'False'.
    """

    out = cli("nas-get-signal-strength")

    return parse_signal_strength(out, skip_unrated=rated_only, include_desc=include_desc)


#
# Wireless Data Service
#

def wds_get_packet_service_status():
    """
    Get packet service status.
    """

    out = cli("wds-get-packet-service-status")

    return parse(out)


def wds_get_packet_statistics():
    """
    Get packet statistics.
    """

    out = cli("wds-get-packet-statistics")

    return parse(out, skip_first=1)
