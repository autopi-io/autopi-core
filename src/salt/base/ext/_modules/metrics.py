#!/usr/bin/env python
# -*- coding: utf-8 -*-

import psutil, time, os, subprocess, re, logging, redis, json, datetime, socket
log = logging.getLogger(__name__)
r = redis.Redis(host='localhost', port=6379, db=6)

"""
    Gather statistics about salt device, including cpu usage, 
    Ram usage, and disk usage - WiFi and cellular usage and signal strength
    Memory avg calc is done every 15 mins, stores in redis, overwrites on each call
    limits to max 3 values, oldest is removed
"""


def collect():
    ret_val = {}
    ret_val["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ret_val["deviceMetrics"] = device_metrics()
    ret_val["connections"] = connections()
    ret_val["version"] = 1

    return ret_val

def _redis_get_list(r, key):
    """
       Made both py2 and py3 compatible
    """
    raw = r.get(key)
    if not raw:
        return []
    # redis-py on py3 returns bytes py2 returns str
    if not isinstance(raw, str):
        raw = raw.decode("utf-8", "replace")
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:  # if anything fails just return empty list
        return []

def _redis_set_list(r, key, value):
    r.set(key, json.dumps(value))

def device_metrics():
    now = time.time()
    cpu_usage = psutil.cpu_percent(interval=1)
    cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True)
    load_average_1, load_average_5, load_average_15 = os.getloadavg()

    vm = psutil.virtual_memory()
    memory_usage_percent = vm.percent
    memory_usage_gb = round(vm.used / 1e9, 2)
    memory_capacity_gb = round(vm.total / 1e9, 2)

    mem_samples = _redis_get_list(r, "memory_avg")  # list of [usage_gb, timestamp]
    mem_samples.append([memory_usage_gb, now])

    cutoff = now - 900
    mem_samples = [s for s in mem_samples if len(s) == 2 and s[1] >= cutoff]

    _redis_set_list(r, "memory_avg", mem_samples)

    if mem_samples:
        memory_avg_gb = sum(s[0] for s in mem_samples) / float(len(mem_samples))
    else:
        memory_avg_gb = memory_usage_gb

    du = psutil.disk_usage("/")
    storage_usage_percent = du.percent
    storage_capacity_gb = round(du.total / 1e9, 2)

    temperature = None
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            first_group = next(iter(temps.values()))
            if first_group:
                temperature = first_group[0].current
    except Exception:
        pass

    uptime_seconds = int(time.time() - psutil.boot_time())
    uptime = {
        "days": uptime_seconds // 86400,
        "hours": (uptime_seconds % 86400) // 3600,
        "minutes": (uptime_seconds % 3600) // 60,
        "seconds": uptime_seconds % 60,
    }

    return {
        "cpu": {"value": cpu_usage, "cores": cpu_cores, "unit": "percent"},
        "memory": {
            "value": memory_usage_percent,
            "avg_15m_gb": round(memory_avg_gb, 2),  # rename if you keep 60s
            "capacity": memory_capacity_gb,
            "unit": "gb",
        },
        "storage": {"value": storage_usage_percent, "capacity": storage_capacity_gb, "unit": "gb"},
        "temperature": {"value": temperature, "unit": "celsius"},
        "loadAverage": {"value": load_average_15, "interval": "15m", "component": "cpu_average_load"},
        "uptime": uptime,
    }

def connections():
    has_cellular_connection = os.path.exists("/sys/class/net/wwan0")
    has_wifi_connection = os.path.exists("/sys/class/net/wlan0")
    has_ethernet_connection = connection_status("eth0")

    signal_strength = {}
    interfaces = {}

    if has_cellular_connection:
        scores = parse_qmi_cli()
        score, weights, net_type = _combine(scores)
        interfaces["wwan0"] = {
            "score": score,
            "connection": "cellular",
            "type": net_type,
        }

    if has_wifi_connection:
        interfaces["wlan0"] = {
            "score": wifi_signal_percent(),
            "connection": "wifi",
        }

    if_addrs = psutil.net_if_addrs()
    if_stats = psutil.net_if_stats()

    for iface in os.listdir("/sys/class/net"):
        if iface == "lo":
            continue
        if iface not in interfaces:
            interfaces[iface] = {}

        interfaces[iface]["status"] = connection_status(iface)

        # IP addresses
        addrs = if_addrs.get(iface, [])
        ipv4 = [a.address for a in addrs if a.family == socket.AF_INET]
        ipv6 = [a.address for a in addrs if a.family == socket.AF_INET6]
        if ipv4:
            interfaces[iface]["ipv4"] = ipv4
        if ipv6:
            interfaces[iface]["ipv6"] = ipv6

        # Interface stats
        stats = if_stats.get(iface)
        if stats:
            interfaces[iface]["mtu"] = stats.mtu
            interfaces[iface]["speed"] = stats.speed  # Mbps, 0 if unknown
            _duplex = {1: "half", 2: "full"}
            if stats.duplex != psutil.NIC_DUPLEX_UNKNOWN:
                interfaces[iface]["duplex"] = _duplex.get(int(stats.duplex), "unknown")

    signal_strength["interfaces"] = interfaces
    signal_strength["active_internet_interfaces"] = (
        "ethernet" if has_ethernet_connection
        else "wifi" if "wlan0" in interfaces and interfaces["wlan0"].get("score", 0) > 0
        else "cellular" if "wwan0" in interfaces and interfaces["wwan0"].get("score", 0) > 0
        else "none"
    )

    master = __salt__["grains.get"]("master")
    signal_strength["salt_pub_connection"] = salt_pub_connection()
    signal_strength["salt_req_connection"] = salt_req_connection()
    signal_strength["ping"] = ping(master)

    return signal_strength

def connection_status(iface="eth0"):
    try:
        with open("/sys/class/net/{}/operstate".format(iface)) as f:
            state = f.read().strip()
        if state == "up":
            return True
        # Some interfaces (e.g. wwan0, loopback) report "unknown" even when active;
        # check the carrier file to distinguish truly up from administratively unknown.
        if state == "unknown":
            try:
                with open("/sys/class/net/{}/carrier".format(iface)) as f:
                    return f.read().strip() == "1"
            except Exception:
                return False
        return False
    except Exception as e:
        log.error(e)
        return False


def wifi_signal_percent(iface="wlan0"):
    cmd = ["iw", "dev", iface, "link"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()

    if p.returncode != 0:
        return None

    if not isinstance(out, str):
        out = out.decode("utf-8", "replace")

    match = re.search(r"signal:\s*(-\d+)\s*dBm", out)
    if not match:
        return 0

    dbm = int(match.group(1))
    # Uses windows stadard quality to rssi conversion
    # https://stackoverflow.com/questions/15797920/how-to-convert-wifi-signal-strength-from-quality-percent-to-rssi-dbm#:~:text=You%20can%20calculate%20the%20RSSI%20signal%20strength,between%201%20and%2099%20using%20linear%20interpolation.
    percent = 2 * (dbm + 100)
    percent = max(0, min(100, percent))

    return round(percent, 1)

def _clamp01(x):
    return max(0.0, min(1.0, x))

def _norm_linear(value, vmin, vmax):
    """
    Linearly normalizes a value between vmin and vmax.
    calls clamp01 to ensure that the value is between 0 and 1.
    """
    return _clamp01((value - vmin) / (vmax - vmin))

def _combine(scores):
    """
    Weighted combination. Prefer RSRP for "bars", then SINR/RSRQ for quality.
    Falls back if some metrics are missing.
    """
    # Primary strategy (LTE-ish):
    # - If RSRP exists: 0.60 RSRP, 0.25 SINR (or SNR), 0.15 RSRQ
    # - Else: 0.50 RSSI, 0.30 SINR/SNR, 0.20 RSRQ
    # - Else: average whatever remains
    weights = {}
    net_type = scores.pop("net_type", None)

    has_rsrp = "rsrp" in scores
    has_rssi = "rssi" in scores
    has_rsrq = "rsrq" in scores
    has_sinr = "sinr" in scores
    has_snr = "snr" in scores

    quality_key = "sinr" if has_sinr else ("snr" if has_snr else None)

    if has_rsrp:
        weights["rsrp"] = 0.60
        if quality_key:
            weights[quality_key] = 0.25
        if has_rsrq:
            weights["rsrq"] = 0.15
    elif has_rssi:
        weights["rssi"] = 0.50
        if quality_key:
            weights[quality_key] = 0.30
        if has_rsrq:
            weights["rsrq"] = 0.20
    else:
        n = len(scores)
        if n == 0:
            return 0.0, {}
        for k in scores:
            weights[k] = 1.0 / n - 1

    wsum = sum(weights.values())
    if wsum <= 0:
        return 0.0, {}, "unknown"
    weights = {k: v / wsum for k, v in weights.items()} 

    combined = sum(scores[k] * weights[k] for k in weights if k in scores)
    combined = max(0.0, min(100.0, combined))
    return combined, weights, net_type

def parse_qmi_cli():
    cmd = ["sudo", "qmicli", "-d", "/dev/cdc-wdm0", "--nas-get-signal-strength"]
    try:
        output = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = output.communicate()
    except Exception as e:
        log.error(e)
        return {}
    if not isinstance(stdout, str):
        stdout = stdout.decode("utf-8")
    if not isinstance(stderr, str):
        stderr = stderr.decode("utf-8")

    def grab(pattern, text, cast=True):
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if not cast:
            return m.group(1) if m else None
        return float(m.group(1)) if m else None

    TEXT = (stdout or "") + "\n" + (stderr or "")
    raw_output = {
        "RSSI": grab(r"(?ms)^RSSI:\s*\n\s*Network\s+'[^']+':\s*'(-?\d+(?:\.\d+)?)\s*dBm'", TEXT),
        "RSRP": grab(r"(?ms)^RSRP:\s*\n\s*Network\s+'[^']+':\s*'(-?\d+(?:\.\d+)?)\s*dBm'", TEXT),
        "ECIO": grab(r"(?ms)^ECIO:\s*\n\s*Network\s+'[^']+':\s*'(-?\d+(?:\.\d+)?)\s*dBm'", TEXT),
        "IO":   grab(r"(?m)^IO:\s*'(-?\d+(?:\.\d+)?)\s*dBm'", TEXT),
        "SINR": grab(r"(?m)^SINR(?:\s*\(\d+\))?:\s*'(-?\d+(?:\.\d+)?)\s*dB'", TEXT),
        "RSRQ": grab(r"(?ms)^RSRQ:\s*\n\s*Network\s+'[^']+':\s*'(-?\d+(?:\.\d+)?)\s*dB'", TEXT),
        "SNR":  grab(r"(?ms)^SNR:\s*\n\s*Network\s+'[^']+':\s*'(-?\d+(?:\.\d+)?)\s*dB'", TEXT),
        "NETTYPE": grab(r"(?m)^\s*Network\s+'([^']+)':", TEXT, cast=False),
    }
    scores = {}
    if raw_output["RSRP"] is not None:
        # LTE RSRP(Received Signal Reporting Power): -140 (dead) -80 (strong)
        scores["rsrp"] = 100.0 * _norm_linear(raw_output["RSRP"], -140.0, -80.0)
    if raw_output["RSSI"] is not None:
        # RSSI(Received Signal Strength Indication): -110 (poor) -50 (strong)
        scores["rssi"] = 100.0 * _norm_linear(raw_output["RSSI"], -110.0, -50.0)

    # Quality
    if raw_output["RSRQ"] is not None:
        # RSRQ(Recieved Signal Quality): -20 (bad) -3 (great)
        scores["rsrq"] = 100.0 * _norm_linear(raw_output["RSRQ"], -20.0, -3.0)
    if raw_output["SINR"] is not None:
        # SINR(Signal to Interference and Noise Ratio): -5 (bad) 25 (great)
        scores["sinr"] = 100.0 * _norm_linear(raw_output["SINR"], -5.0, 25.0)
    if raw_output["SNR"] is not None:
        # SNR(Signal to Noise Ratio): 0 (bad) 30 (great)
        scores["snr"] = 100.0 * _norm_linear(raw_output["SNR"], 0.0, 30.0)

    if raw_output["ECIO"] is not None:
        # ECIO(Error Count Indicator): -15 (bad) 0 (great)
        scores["ecio"] = 100.0 * _norm_linear(raw_output["ECIO"], -15.0, 0.0)
    scores["net_type"] = raw_output["NETTYPE"]
    return scores

def _port_connection_status(port):
    """
    Returns True if there is an ESTABLISHED TCP connection on the given port.
    Works on both Python 2 and Python 3 using 'ss' (iproute2).
    """
    try:
        cmd = ["ss", "-tn", "state", "established", "dport", ":{:d}".format(port)]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, _ = p.communicate()
        if not isinstance(out, str):
            out = out.decode("utf-8", "replace")
        # ss prints a header line; any additional line means a connection exists
        lines = [l for l in out.splitlines() if l.strip()]
        return len(lines) > 1
    except Exception as e:
        log.error(e)
        return False

def salt_pub_connection():
    """
    Get connection status to Salt's publishing service (port 4505)
    """
    PORT = 4505
    return _port_connection_status(PORT)

def salt_req_connection():
    """
    Get connection status to Salt's request service (port 4506)
    """
    PORT = 4506
    return _port_connection_status(PORT)

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
