import logging
import re


log = logging.getLogger(__name__)

_gpu_temp_regex = re.compile("^temp=(?P<value>[-+]?[0-9]*\.?[0-9]*)'(?P<unit>.+)$")


def help():
    """
    This command.
    """

    return __salt__["sys.doc"]("rpi")


def temp():
    """
    Current temperature readings.
    """

    return {
        "cpu": temp_cpu(),
        "gpu": temp_gpu()
    }


def temp_cpu():
    """
    Current temperature of the ARM CPU.
    """

    raw = __salt__["cp.get_file_str"]("/sys/class/thermal/thermal_zone0/temp")

    return {
        "value": float(raw) / 1000,
        "unit": "C"
    }


def temp_gpu():
    """
    Current temperature of the GPU.
    """

    raw = __salt__["cmd.run"]("vcgencmd measure_temp")
    match = _gpu_temp_regex.match(raw)
    
    ret = match.groupdict()
    ret["value"] = float(ret["value"])

    return ret


def hw_serial():
    """
    Get hardware serial.
    """

    return __salt__["cmd.run"]("grep -Po '^Serial\s*:\s*\K[[:xdigit:]]{16}' /proc/cpuinfo")

