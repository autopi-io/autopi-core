import datetime
import logging
import re
import salt.exceptions

import command_util as cutil
from command_util import normalizers, validators


log = logging.getLogger(__name__)

_gpu_temp_regex = re.compile("^temp=(?P<value>[-+]?[0-9]*\.?[0-9]*)'(?P<unit>.+)$")
_linux_boot_log_regex = re.compile("^(?P<timestamp>.+) raspberrypi kernel: .+$")
_get_throttled_regex = re.compile("^throttled=(?P<value>0x[0-9]+)$")


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

    raw = __salt__["file.read"]("/sys/class/thermal/thermal_zone0/temp")

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


def throttled():
    """
    Get throttled flags.
    """

    ARM_FREQUENCY_CAPPED                 = 1
    ARM_FREQUENCY_CAPPED_HAS_OCCURRED    = 17
    CURRENTLY_THROTTLED                  = 2
    THROTTLING_HAS_OCCURRED              = 18
    SOFT_TEMPERATURE_LIMIT_ACTIVE        = 3
    SOFT_TEMPERATURE_LIMIT_HAS_OCCURRED  = 19
    UNDER_VOLTAGE_DETECTED               = 0
    UNDER_VOLTAGE_HAS_OCCURRED           = 16

    FLAGS = {
        "arm_frequency_capped":                 (1 << 1),
        "arm_frequency_capped_has_occurred":    (1 << 17),
        "currently_throttled":                  (1 << 2),
        "throttling_has_occurred":              (1 << 18),
        "soft_temperature_limit_active":        (1 << 3),
        "soft_temperature_limit_has_occurred":  (1 << 19),
        "undervoltage_detected":                (1 << 0),
        "undervoltage_has_occurred":            (1 << 16)
    }

    raw = __salt__["cmd.run"]("vcgencmd get_throttled")
    match = _get_throttled_regex.match(raw)

    ret = match.groupdict()
    ret["flags"] = [k for k, v in FLAGS.iteritems() if bool(int(ret["value"], 16) & v)]

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

def connection_status(ip=None, port=None):
    
    ret = {}
    conns = []
    
    try:
        peer_filter = "{}:{}\\s*$".format(ip or "", port or "[0-9]+")
        cmd = "ss -nt | egrep '{}' | awk '{{$1=$1}};1'".format(peer_filter)
        res = __salt__["cmd.shell"](cmd)
        
        if res:
            res_lines = res.split("\n")
            for line in res_lines:   
                split = line.split(" ")
                address, port = split[4].split(":")
                
                conns.append({
                    "address": address,
                    "port": port,
                    "status": split[0],
                    "recvq": int(split[1]),
                    "sendq": int(split[2])
                })
    except Exception as ex:
        ret["exception"] = str(ex)

    ret["values"] = conns
    ret["_stamp"] = datetime.datetime.now().isoformat()
    return ret

def salt_pub_connection():
    """
    Get connection status to Salt's publishing service (port 4505)
    """
    PORT = 4505
    
    res = connection_status(port=PORT)
    
    return res

def salt_req_connection():
    """
    Get connection status to Salt's request service (port 4506)
    """
    PORT = 4506
    
    res = connection_status(port=PORT)
    
    return res

def ping(url, count=3, packet_size=20):
    """
    Try pinging url with <count> packets of <packet_size> bytes
    """
    
    ret = {
        "value": {
            "status": "FAIL"
        },
        "_stamp": datetime.datetime.now().isoformat()
    }
    
    count = int(count)
    packet_size = int(packet_size)
    
    try:
        res = __salt__["cmd.shell"]("ping -qc{} -s {} {} 2>&1 | grep rtt".format(
            count,
            packet_size,
            url
        ))

        if res:
            rx = r"^.*\s(?P<min>\d+.\d+)/(?P<avg>\d+.\d+)/(?P<max>\d+.\d+)/(?P<mdev>\d+.\d+) ms$"
            match = re.search(rx, res)
            match_dict = match.groupdict()
            
            ret["value"] = {
                "status": "SUCCESS",
                "min": float(match_dict["min"]),
                "avg": float(match_dict["avg"]),
                "max": float(match_dict["max"]),
            }
    except Exception as ex:
        ret["exception"] = str(ex)
            
    return ret
    

def default_interface():
    """
    Get default internet interface stats
    """
    interface = None
    gateway = None
    ret = {
        "value": None,
        "_stamp": datetime.datetime.now().isoformat()
    }
    
    try:
        # Get inteface name and gateway
        netstat_res = __salt__["cmd.shell"]('netstat -rn').split("\n")[2:]
        
        for line in netstat_res:
            split = re.sub(" +", " ", line).split(" ")
            flags = split[3]
            
            if "G" in flags:
                interface = split[7]
                gateway = split[1]
                ret["value"] = {
                    "name": interface,
                    "gateway": gateway
                }
                break
        
        # Exit if no default interface
        if not interface:
            return ret

        # Get traffic since boot stats
        cmd = ("ip -s l show {} "
            "| sed -n '/RX.*/,$p' "
            "| sed -n '0~2p' "
            "| awk '{{$1=$1}};1'").format(interface)

        ip_res = __salt__["cmd.shell"](cmd).split("\n")

        rx_line = ip_res[0].split(" ")
        tx_line = ip_res[1].split(" ")

        ret["value"]["rx_kb"] = int(rx_line[0]) / 1024
        ret["value"]["rx_packets"] = int(rx_line[1])
        ret["value"]["tx_kb"] = int(tx_line[0]) / 1024
        ret["value"]["tx_packets"] = int(tx_line[1])
    except Exception as ex:
        ret["exception"] = str(ex)
    
    return ret

def uptime():
    """
    Get system uptime in seconds
    """
    ret = {
        "value": None,
        "_stamp": datetime.datetime.now().isoformat()
    }

    try:
        ret["value"] = float(__salt__["cmd.shell"]("awk '{print $1}' /proc/uptime"))
    except Exception as ex:
        ret["exception"] = str(ex)

    return ret

def storage():
    ret = {
        "value": {},
        "_stamp": datetime.datetime.now().isoformat()
    }

    # Size of log dir
    try:
        du_log_cmd = "du /var/log -s -BK | awk '{print $1}' | egrep -o '[0-9]+'"
        du_log_res = __salt__["cmd.shell"](du_log_cmd)
        ret["value"]["log_dir_mb"] = (int(du_log_res) * 1024) / 1024**2
        
        # Size of redis dir
        du_redis_cmd = ("du /var/lib/redis -s -BK "
                        "| awk '{print $1}' "
                        "| egrep -o '[0-9]+'")
        du_redis_res = __salt__["cmd.shell"](du_redis_cmd)
        ret["value"]["redis_dir_mb"] = (int(du_redis_res) * 1024) / 1024**2
    
        df_res = __salt__["status.diskusage"]("/")
        if df_res:
            avail = df_res["/"]["available"]
            total = df_res["/"]["total"]
            used_prc = 100 - int(100 * avail / total)
            ret["value"]["available_mb"] = avail / 1024**2
            ret["value"]["total_mb"] = total / 1024**2
            ret["value"]["used_prc"] = used_prc 
    except Exception as ex:
        ret["exception"] = str(ex)

    return ret

def _memory_res_to_bytes(res):
    type_multiplier_dict = {
        "b": 1,
        "kb": 10**3,
        "mb": 10**6,
        "gb": 10**9,
        "tb": 10**12
    }
    
    val_type = res["unit"].lower()
    return int(res["value"]) * type_multiplier_dict[val_type]

def memory():
    """
    Get memory stats
    """
    ret = {
        "value": {},
        "_stamp": datetime.datetime.now().isoformat()
    }
    
    try:
        res = __salt__["status.meminfo"]()
        
        avail = _memory_res_to_bytes(res["MemAvailable"])
        total = _memory_res_to_bytes(res["MemTotal"])
        used_prc = 100 - int(100 * avail / total)

        ret["value"]["total_mb"] = total / 1024**2
        ret["value"]["available_mb"] = avail / 1024**2
        ret["value"]["used_prc"] = used_prc
    except Exception as ex:
        ret["exception"] = str(ex)
    
    return ret

def stats(*args, **kwargs):
    """
    Get system and connection stats.
    """

    master = __salt__["grains.get"]("master")

    SUPPORTED_ARGS = {
        "uptime": lambda: uptime()["value"],
        "default_inteface": lambda: default_interface()["value"],
        "salt_pub_conn": lambda: salt_pub_connection()["values"],
        "salt_req_conn": lambda: salt_req_connection()["values"],
        "storage": lambda: storage()["value"],
        "memory": lambda: memory()["value"],
        "ping": lambda: ping(master)["value"],
        "temp": lambda: temp(),
        "throttled": lambda: throttled()
    }

    sanitize = kwargs.pop("sanitize", True)
    if sanitize:
        args = cutil.sanitize(args or None, "args", normalizers.nested.list_or_tuple(normalizers.string_unicode), [validators.per_item(validators.choice(SUPPORTED_ARGS.keys()))], default=SUPPORTED_ARGS.keys())
    cutil.sanitize_kwargs(sanitize, kwargs, (
        ("exclude", [], normalizers.nested.list_or_tuple(normalizers.string_unicode), [], ()),
    ))

    arg_funcs = {k: v for k, v in SUPPORTED_ARGS.iteritems() if k in args}
    ret = {
        "value": {k: v() for k, v in arg_funcs.iteritems() if not k in kwargs.get("exclude", [])},
        "_stamp": datetime.datetime.now().isoformat()
    }

    return ret
