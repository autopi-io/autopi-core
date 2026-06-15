import json
import logging
import os
import salt.exceptions
import time

from collections import OrderedDict

from socketcan_lib import dump_async


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


def up(interface="can0", bitrate=500000, dbitrate=None, listen_only=False, **kwargs):
    """
    Bring up CAN interface.

    Optional arguments:
      - interface (str): CAN interface. Default is 'can0'.
      - bitrate (int): Default is '500000'.
      - dbitrate (int): CAN-FD data bitrate.
      - listen_only (bool): Only receive and not transmit CAN messages. Default is 'False'.
    """

    params = OrderedDict([("bitrate", bitrate)])

    # NOTE: Always specified because once turned on/set, the value might stick until explicitly turned off!
    params["listen-only"] = "on" if listen_only else "off"

    if __salt__["config.get"]("hw.version", 0.0) >= 7.1:  # CAN-FD interface is always explicitly set to on or off
        params["dbitrate"] = dbitrate or 0
        params["fd"] = "on" if dbitrate or 0 > 0 else "off"
    else:  # Old behavior, CAN-FD intertface must be turned off explicitly
        if dbitrate != None:
            params["dbitrate"] = dbitrate
            params["fd"] = "on" if dbitrate > 0 else "off"

    for key, val in kwargs.iteritems():
        if not key.startswith("__"):

            # Convert bool to on/off string
            if isinstance(val, bool):
                val = "on" if val else "off"

            params[key] = val

    log.info("Bringing up CAN interface '{:}' using parameters: {:}".format(interface, dict(params)))
    res = __salt__["cmd.run_all"]("ip link set {:} up type can {:}".format(interface, " ".join(["{:} {:}".format(k, v) for k, v in params.iteritems()])))
    if res["retcode"] != 0:
        raise salt.exceptions.CommandExecutionError(res["stderr"])

    return res


def dump(*filters, **options):
    """
    TODO HN: Write documentation

    Example: 'socketcan.dump can0,18F00000:1FF00000'
    """

    ret = {}

    duration = options.pop("duration", 1)
    limit = options.setdefault("limit", 0)
    options.setdefault("timestamp", "A")

    if not duration and not limit:
        raise ValueError("Either a duration or limit must be specified")

    process = dump_async(*filters, **options)
    if duration:
        time.sleep(duration)
        process.kill()

    stdout, stderr = process.communicate()

    if stderr:
        ret["error"] = stderr

    if stdout:
        lines = [l.lstrip() for l in stdout.split(os.linesep) if l]
        ret["count"] = len(lines)
        ret["values"] = lines

    return ret


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
