import logging
import parsing

import qmilib


log = logging.getLogger(__name__)


def _run(name, device="/dev/cdc-wdm0"):
    return __salt__["cmd.run"]("qmicli --silent -d {:s} --{:s}".format(device, name))


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"]("qmi")


def operator_name():
    """
    Get operator name data.
    """

    # TODO: Complete this
    out = _run("nas-get-operator-name")
    #ret = parsing.into_dict_parser(out)

    return out


def system_info():
    """
    Get system info.
    """

    # TODO: Complete this
    out = _run("nas-get-system-info")
    #ret = parsing.into_dict_parser(out)

    return out


def cell_info():
    """
    Get cell location info.
    """

    # TODO: Complete this
    out = _run("nas-get-cell-location-info")
    #ret = parsing.into_dict_parser(out)

    return out


def signal_strength(rated_only=False):
    """
    Current signal strength values.

    Optional arguments:
      - rated_only (bool): Default is 'False'.
    """

    out = _run("nas-get-signal-strength")
    ret = qmilib.parse_signal_strength(out, skip_unrated=rated_only)

    return ret


# TODO: Remove this command becasue above is better?
def nas_get_signal_info():
    """
    """

    out = _run("nas-get-signal-info")
    lines = parsing.lines_parser(out)

    ret = {}

    if not re.search("success", lines[0], re.IGNORECASE):
        ret["error"] = lines[0]
        return ret

    parsing.into_dict_parser(lines[1:], root=ret, value_parser=parsing.number_parser)

    return ret
