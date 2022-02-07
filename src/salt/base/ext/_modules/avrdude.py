import logging
import salt.exceptions

from collections import OrderedDict
from six import string_types


# Define the module's virtual name
__virtualname__ = "avrdude"

log = logging.getLogger(__name__)


def __virtual__():
    return __virtualname__


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"](__virtualname__)


def fuse(name, part_id="t88", prog_id="autopi", value=None):
    """
    Get or set fuse value of MCU.

    WARNING: Only use this command with caution as it can misconfigure the MCU and leave it in an unusable state.

    Arguments:
      - name (str): Name of the fuse.

    Optional arguments:
      - part_id (str): Part ID. Default is 't88'.
      - prog_id (str): ID of programmer. Default is 'autopi'.
      - value (str): Fuse byte value to write.
    """

    ret = {}

    if not name in ["e", "h", "l"]:
        raise ValueError("Unsupported fuse name")

    if value != None:
        if isinstance(value, string_types):
            value = int(value, 16)

        if not 0x00 <= value <= 0xFF:
            raise ValueError("Value {:02x} is out of range (0x00-0xFF)".format(value))

        oper = "{:}fuse:w:0x{:02x}:m".format(name, value)

        log.warning("Writing {:}fuse value 0x{:02x}".format(name, value))
    else:
        oper = "{:}fuse:r:-:h".format(name)

    res = __salt__["cmd.run_all"]("avrdude -q -p {:} -c {:} -s -U {:}".format(part_id, prog_id, oper))
    if res["retcode"] != 0:
        raise salt.exceptions.CommandExecutionError(res["stderr"])

    if res["stdout"]:
        ret["value"] = res["stdout"]

    return ret


def flash(hex_file, part_id="t88", prog_id="autopi", raise_on_error=True, no_write=True):
    """
    Flash hex file to MCU.

    WARNING: Only use this command with caution as it can misconfigure the MCU and leave it in an unusable state.

    Arguments:
      - hex_file (str): Path of hex file.

    Optional arguments:
      - part_id (str): Part ID. Default is 't88'.
      - prog_id (str): ID of programmer. Default is 'autopi'.
      - raise_on_error (bool): Raise an error upon failure. Default is 'True'.
      - no_write (bool): No actual write to MCU. Default is 'True'.
    """

    ret = {}

    params = ["avrdude", "-p {:}".format(part_id), "-c {:}".format(prog_id), "-U flash:w:{:s}".format(hex_file)]
    if no_write:
        params.append("-n")

    res = __salt__["cmd.run_all"](" ".join(params))

    if res["retcode"] == 0:
        ret["output"] = res["stderr"]
    else:
        if raise_on_error:
            raise salt.exceptions.CommandExecutionError(res["stderr"])

        ret["error"] = res["stderr"]
        ret["output"] = res["stdout"]

    return ret
