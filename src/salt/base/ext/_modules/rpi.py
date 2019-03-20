import datetime
import logging
import re
import salt.exceptions


log = logging.getLogger(__name__)

_gpu_temp_regex = re.compile("^temp=(?P<value>[-+]?[0-9]*\.?[0-9]*)'(?P<unit>.+)$")
_linux_boot_log_regex = re.compile("^(?P<timestamp>.+) raspberrypi kernel: .+$")


def help():
    """
    Shows this help information.
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


def boot_time():
    """
    Get timestamp for last boot of system.
    """

    ret = {"value": None}

    res = __salt__["cmd.shell"]("grep 'Booting Linux' /var/log/syslog | tail -1")
    if not res:
        return ret

    match = _linux_boot_log_regex.match(res)
    if not match:
        raise salt.exceptions.CommandExecutionError("Unable to parse log line: {:}".format(res))

    now = datetime.datetime.now()
    last_off = datetime.datetime.strptime(match.group("timestamp"), "%b %d %H:%M:%S").replace(year=now.year)
    if last_off > now:
        last_off = last_off.replace(year=now.year-1)

    ret["value"] = last_off.isoformat()

    return ret
