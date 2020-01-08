import subprocess

from .parser import parse_signal_strength


def cli(option, device="/dev/cdc-wdm0"):
    """
    Call QMI command line interface.

    Arguments:
      - option (str): Command option.

    Optional arguments:
      - device (str): Default is '/dev/cdc-wdm0'.
    """

    p = subprocess.Popen(["qmicli", "--silent", "--device={:s}".format(device), "--{:s}".format(name)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = p.stdout.read()
    err = p.stderr.read()

    if err:
        raise Exception(err)

    return out


#
# Network Access Service
#

def nas_get_cell_location_info():
    """
    Get cell location info.
    """

    out = cli("nas-get-cell-location-info")

    return out

def nas_get_operator_name():
    """
    Get operator name data.
    """

    out = cli("nas-get-operator-name")

    return out

def nas_get_system_info():
    """
    Get system info.
    """

    out = cli("nas-get-system-info")

    return out

def nas_get_serving_system():
    """
    Get serving system.
    """

    out = cli("nas-get-serving-system")

    return out

def nas_get_signal_info():
    """
    Get signal strength.
    """

    out = cli("nas-get-signal-info")

    """
    lines = parsing.lines_parser(out)

    ret = {}

    parsing.into_dict_parser(lines[1:], root=ret, value_parser=parsing.number_parser)

    return ret
    """

    return out

def nas_get_signal_strength(rated_only=False):
    """
    Get signal strength.

    Optional arguments:
      - rated_only (bool): Default is 'False'.
    """

    out = cli("nas-get-signal-strength")

    return parse_signal_strength(out, skip_unrated=rated_only)


#
# Wireless Data Service
#

def wds_get_packet_service_status():
    """
    Get packet service status.
    """

    out = cli("wds-get-packet-service-status")

    return out


def wds_get_packet_statistics():
    """
    Get packet statistics.
    """

    out = cli("wds-get-packet-statistics")

    return out
