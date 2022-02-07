import json
import logging
import salt.exceptions

from collections import OrderedDict


# Define the module's virtual name
__virtualname__ = "socketcan"

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"](__virtualname__)


def show(interface="can0", details=False, stats=False):
    """
    Show current information for CAN interface.

    Optional arguments:
      - interface (str): CAN interface. Default is 'can0'.
      - details (bool): Include details. Default is 'False'.
      - stats (bool): Include statistics. Default is 'False'.
    """

    opts = ["-json"]
    if details:
        opts.append("-details") 
    if stats:
        opts.append("-stats") 

    res = __salt__["cmd.run_all"]("ip {:} link show {:}".format(" ".join(opts), interface))
    if res["retcode"] != 0:
        raise salt.exceptions.CommandExecutionError(res["stderr"])

    return json.loads(res["stdout"])[0]


def up(interface="can0", bitrate=500000, dbitrate=None, **kwargs):
    """
    Bring up CAN interface.

    Optional arguments:
      - interface (str): CAN interface. Default is 'can0'.
      - bitrate (int): Default is '500000'.
      - dbitrate (int): CAN-FD data bitrate.
    """

    params = OrderedDict([("bitrate", bitrate)])
    if dbitrate != None:
        params["dbitrate"] = dbitrate
        params["fd"] = "on"

    for key, val in kwargs.iteritems():
        params[key] = val

    log.info("Bringing up CAN interface '{:}' using parameters: {:}".format(interface, dict(params)))
    res = __salt__["cmd.run_all"]("ip link set {:} up type can {:}".format(interface, " ".join(["{:} {:}".format(k, v) for k, v in params.iteritems()])))
    if res["retcode"] != 0:
        raise salt.exceptions.CommandExecutionError(res["stderr"])

    return res


def down(interface="can0"):
    """
    Bring down CAN interface.

    Optional arguments:
      - interface (str): CAN interface. Default is 'can0'.
    """

    log.info("Bringing down CAN interface '{:}'".format(interface))
    res = __salt__["cmd.run_all"]("ip link set {:} down".format(interface))
    if res["retcode"] != 0:
        raise salt.exceptions.CommandExecutionError(res["stderr"])

    return res
