import datetime
import logging
import re
import salt.exceptions


log = logging.getLogger(__name__)

_gpu_temp_regex = re.compile("^temp=(?P<value>[-+]?[0-9]*\.?[0-9]*)'(?P<unit>.+)$")
_fake_hwclock_regex = re.compile("^.* fake-hwclock\[\d+\]: (?P<timestamp>.+)$")


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


def last_off_time():
    """
    Attempts to determine timestamp for last time system powered off.
    """

    ret = {"value": None}

    res = __salt__["cmd.shell"]("grep 'fake-hwclock' /var/log/syslog | tail -1")
    if not res:
        return ret

    match = _fake_hwclock_regex.match(res)
    if not match:
        raise salt.exceptions.CommandExecutionError("Unable to parse log line: {:}".format(res))

    ret["value"] = datetime.datetime.strptime(match.group("timestamp"), "%a %d %b %H:%M:%S %Z %Y").isoformat()

    return ret
