import datetime
import decimal
import logging
import nmea_util
import os
import pynmea2

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack
from pynmea2 import nmea_utils


log = logging.getLogger(__name__)

client = EventDrivenMessageClient("ec2x")


def __init__(opts):
    client.init(opts)


# TODO: Move to _utils/parsing.py?
def _parse_dict(data, separator=": ", multiline=False):
    ret = {}

    lines = data if isinstance(data, list) else [data]
    pairs = (l.split(separator) for l in lines)
    for k, v in pairs:
        if k in ret:
            if isinstance(ret[k], list):
                ret[k].append(v)
            else:
                ret[k] = [ret[k], v]
        else:
            ret[k] = v if not multiline and not isinstance(v, list) else [v]

    return ret


def help():
    """
    Shows this help information.
    """
    
    return __salt__["sys.doc"]("ec2x")


def context(**kwargs):
    """
    Gets current context.
    """

    return client.send_sync(_msg_pack(_handler="context", **kwargs))


def connection(**kwargs):
    """
    Manages current connection.

    Optional arguments:
      - close (bool): Close serial connection? Default value is 'False'. 

    Examples:
      - 'ec2x.connection'
      - 'ec2x.connection close=True'
    """

    return client.send_sync(_msg_pack(_handler="connection", **kwargs))


def query(cmd, cooldown_delay=None, **kwargs):
    """
    Low-level function to execute AT commands.
    """

    return client.send_sync(_msg_pack(cmd, cooldown_delay=cooldown_delay, **kwargs))

    # TODO Sanity check
    #assert res.get("command", None) == cmd, "Received command '{:}' is not equal to sent command '{:}'".format(res.get("command", None), cmd)


def power(cmd, **kwargs):
    """
    Low-level function to run power command.
    """

    return client.send_sync(_msg_pack(cmd, _handler="power", **kwargs), timeout=60)


def upload(cmd, src, **kwargs):
    """
    Low-level function to upload files.
    """

    return client.send_sync(_msg_pack(cmd, src, _handler="upload", **kwargs))


def download(cmd, size, dest, **kwargs):
    """
    Low-level function to download files.
    """

    return client.send_sync(_msg_pack(cmd, size, dest, _handler="download", **kwargs))


def product_info():
    """
    Display product identification information.
    """

    return query("ATI")


def firmware_rev():
    """
    Revision identification of software release.
    """

    return query("AT+QGMR")


def imei():
    """
    Returns the International Mobile Equipment Identity (IMEI).
    """

    return query("AT+GSN")


def time(mode=1):
    """
    Obtain the latest time synchronized through network

    Query network time mode:
      - '0' = Query the latest time that has been synchronized through network
      - '1' = Query the current GMT time calculated from the latest time that has been synchronized through network
      - '2' = Query the current LOCAL time calculated from the latest time that has been synchronized through network
    """

    res = query("AT+QLTS={:d}".format(mode))
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QLTS"].strip('"').split(",")
        res.update({
            "date": row[0],
            "time": row[1],
            "dst": row[2]
        })

    return res


def sync_time(force=False, **kwargs):
    """
    Synchronize system time with network time.
    """

    return client.send_sync(_msg_pack(force=force, _handler="sync_time", **kwargs))


def error_format_config(value=None):
    """
    Controls the format of error result codes: 'ERROR', error numbers or
    verbose messages as '+CME ERROR: <err>' and '+CMS ERROR: <err>'.
    """

    if value != None:
        return query("AT+CMEE={:d}".format(value))

    res = query("AT+CMEE?")
    if "data" in res:
        res["value"] = int(_parse_dict(res.pop("data"))["+CMEE"])

    return res


def urc_port_config(value=None):
    """
    Configure the output port of URC (Unsolicited Result Code).

    Port options:
      - 'usbat' (USB AT port)
      - 'usbmodem' (USB modem port)
      - 'uart1' (Main UART)
    """

    if value != None:
        return query('AT+QURCCFG="urcport","{:s}"'.format(value))

    res = query('AT+QURCCFG="urcport"')
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QURCCFG"].split(",")
        res["value"] = row[1].strip('"')

    return res


def power_off(normal=True, **kwargs):
    """
    Used to shut down the entire EC2x module. The module will restart automatically.
    A 30-second wait is included after power off to allow the module time to recover before receiving any new command requests.
    """

    res = power("AT+QPOWD={:d}".format(normal), **kwargs)

    return res


def cell_location():
    """
    Get location by triangulation (QuecLocator).
    """

    res = query("AT+QCELLLOC")
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QCELLLOC"].split(",")
        res.update({
            "lon": row[0],
            "lat": row[1]
        })

    return res


def cell_signal():
    """
    Signal quality report indicates the received signal strength and the channel bit error rate.
    """

    res = query("AT+CSQ")
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+CSQ"].split(",")
        res.update({
            "rssi": row[0],
            "bit_error_rate": "{:s}%".format(row[1])
        })

    return res


def ri_sms_config(value=None, pulse_duration=120, pulse_count=1):
    """
    Specifies the RI (Ring Indicator) behavior when incoming SMS URCs are presented.

    Optional arguments:
      - value (str):
      - pulse_duration (int): Default value is '120'.
      - pulse_count (int): Default value is '1'.
    """

    if value != None:
        return query('AT+QCFG="urc/ri/smsincoming","{:s}",{:d},{:d}'.format(value, pulse_duration, pulse_count))

    res = query('AT+QCFG="urc/ri/smsincoming"')
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QCFG"].split(",")
        res.update({
            "value": row[1].strip('"'),
            "pulse_duration": int(row[2]),
            "pulse_count": int(row[3]),
        })

    return res


def ri_other_config(value=None, pulse_duration=120, pulse_count=1):
    """
    Specifies the RI (Ring Indicator) behavior when other URCs are presented.

    Optional arguments:
      - value (str):
      - pulse_duration (int): Default value is '120'.
      - pulse_count (int): Default value is '1'.
    """

    if value != None:
        return query('AT+QCFG="urc/ri/other","{:s}",{:d},{:d}'.format(value, pulse_duration, pulse_count))

    res = query('AT+QCFG="urc/ri/other"')
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QCFG"].split(",")
        res.update({
            "value": row[1].strip('"'),
            "pulse_duration": int(row[2]),
            "pulse_count": int(row[3]),
        })

    return res


def ri_signal_config(value=None):
    """
    Specifies the RI (Ring Indicator) signal output carrier.

    Optional arguments:
      - value (str):
    """

    if value != None:
        return query('AT+QCFG="risignaltype","{:s}"'.format(value))

    res = query('AT+QCFG="risignaltype"')
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QCFG"].split(",")
        res.update({
            "value": row[1].strip('"'),
        })

    return res


def data_usage(reset=False):
    """
    Check how many bytes are sent to and received by the module.
    """

    res = query("AT+QGDCNT?")
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QGDCNT"].split(",")
        res.update({
            "sent": int(row[0]),
            "recv": int(row[1])
        })

    if reset:
        query("AT+QGDCNT=0")

    return res


def gnss(enable=None, mode=1, fix_max_time=30, fix_max_dist=50, fix_count=0, fix_rate=1):
    """
    The command is used to turn on GNSS function. Currently <mode> only supports
    turning on GNSS in Stand-alone Solution. When <fixcount> is 0, GNSS will fix
    position continuously, and it can be turned off via 'AT+QGPSEND'. When <fixcount>
    is non-zero and reaches the specified value, GNSS will be turned off automatically.

    When GNSS is turned on and <fixcount> is 0, GNSS fixes position continuously.
    In this case, GNSS can be turned off compulsorily via this command. When
    <fixcount> is non-zero, GNSS will be turned off automatically when the
    parameter reaches the specified value, and thus the command can be ignored.

    Optional arguments:
      - enable (bool):
      - mode (int): Default value is '1'.
      - fix_max_time (int): Default value is '30'.
      - fix_max_dist (int): Default value is '50'.
      - fix_count (int): Default value is '0'.
      - fix_rate (int): Default value is '1'.
    """

    if enable == None:
        res = query("AT+QGPS?")
        if "data" in res:
            if bool(int(_parse_dict(res.pop("data"))["+QGPS"])):
                res["value"] = "on"
            else:
                res["value"] = "off"
        return res
    elif enable:
        return query("AT+QGPS={:d},{:d},{:d},{:d},{:d}".format(
            mode, fix_max_time, fix_max_dist, fix_count, fix_rate))
    else:
        return query("AT+QGPSEND")


def gnss_auto_start(enable=None):
    """
    Enable/disable GNSS to run automatically after the module is powered on.
    Configuration parameter will be automatically saved to NVRAM. The default value is 0.
    """

    if enable != None:
        return query('AT+QGPSCFG="autogps",{:d}'.format(enable))

    res = query('AT+QGPSCFG="autogps"')
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QGPSCFG"].split(",")
        res["value"] = bool(int(row[1]))

    return res


def gnss_config(value=None):
    """
    Configure supported GNSS constellation.

    NOTE: Requires restart of EC2x module to take effect.

    Supported GNSS constellation (GPS is always on):
      - '0' = GLONASS off/BeiDou off/Galileo off
      - '1' = GLONASS on/BeiDou on/Galileo on
      - '2' = GLONASS on/BeiDou on/Galileo off
      - '3' = GLONASS on/BeiDou off/Galileo on
      - '4' = GLONASS on/BeiDou off/Galileo off
      - '5' = GLONASS off/BeiDou on/Galileo on
      - '6' = GLONASS off/BeiDou off/Galileo on
    """

    if value != None:
        return query('AT+QGPSCFG="gnssconfig",{:d}'.format(value))

    res = query('AT+QGPSCFG="gnssconfig"')
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QGPSCFG"].split(",")
        res["value"] = int(row[1])

    return res


def gnss_nmea_port(value=None):
    """
    Configure the output port of NMEA sentences, and the configuration parameter will be automatically saved to NVRAM.

    Port options:
      - 'none' = Close NMEA sentence output 
      - 'usbnmea' = Output via USB NMEA port
      - 'uartdebug' = Output via UART debug port
    """

    if value != None:
        return query('AT+QGPSCFG="outport","{:s}"'.format(value))

    res = query('AT+QGPSCFG="outport"')
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QGPSCFG"].split(",")
        res["value"] = row[1].strip('"')

    return res


def gnss_nmea_req(enable=None):
    """
    Enables/disables acquisition of NMEA sentences on request via commands.
    """

    if enable != None:
        return query('AT+QGPSCFG="nmeasrc",{:d}'.format(enable))

    res = query('AT+QGPSCFG="nmeasrc"')
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QGPSCFG"].split(",")
        res["value"] = bool(int(row[1]))

    return res


def gnss_nmea_raw(type, verbose=False):
    """
    Acquire NMEA sentence(s) data on request.

    Available types:
      - 'GGA' (Fix information)
      - 'RMC' (Recommended minimum data for GPS)
      - 'GSV' (Detailed satellite data)
      - 'GSA' (Overall satellite data)
      - 'VTG' (Vector track an speed over the ground)
      - 'GNS'
    """

    res = query('AT+QGPSGNMEA="{:s}"'.format(type))
    if "data" in res:
        sentences = _parse_dict(res.pop("data"), multiline=True)["+QGPSGNMEA"]
        if len(sentences) == 1:
            res["value"] = nmea_util.parse_as_dict(sentences[0], verbose=verbose)
        else:
            res["values"] = [nmea_util.parse_as_dict(s, verbose=verbose) for s in sentences]

    return res


def gnss_nmea_gga():
    """
    Get NMEA GGA data parsed into dict.
    """

    res = query('AT+QGPSGNMEA="{:s}"'.format("gga"))
    if "data" in res:
        sentence = _parse_dict(res.pop("data"))["+QGPSGNMEA"]

        obj = pynmea2.parse(sentence, check=True)
#        if obj.is_valid:
        res.update({
            "utc": obj.timestamp.isoformat(),
            "latitude": obj.latitude,
            "longitude": obj.longitude,
            "altitude": float(obj.altitude),
        })

    return res


def gnss_nmea_gsa():
    """
    Get NMEA GSA data parsed into dict.
    """

    res = query('AT+QGPSGNMEA="{:s}"'.format("gsa"))
    if "data" in res:
        sentence = _parse_dict(res.pop("data"))["+QGPSGNMEA"]

        obj = pynmea2.parse(sentence, check=True)
        fix_prns = [getattr(obj, "sv_id{:02d}".format(idx)) for idx in range(1, 13)]
        fix_sat_count = len(fix_prns)

        res.update({
            "mode": obj.mode,
            "fix": "{:}D".format(obj.mode_fix_type),
            "fix_prns": fix_prns,
            "fix_sat_count": fix_sat_count,
            "pdop": float(obj.pdop) if obj.pdop else None,
            "hdop": float(obj.hdop) if obj.hdop else None,
            "vdop": float(obj.vdop) if obj.vdop else None,
        })

    return res


def gnss_nmea_gsv():
    """
    Get list where entries are grouped by all available satellites in NMEA GSV data.
    """

    res = query('AT+QGPSGNMEA="{:s}"'.format("gsv"))
    if "data" in res:
        values = []

        sentences = _parse_dict(res.pop("data"), multiline=True)["+QGPSGNMEA"]
        for sentence in sentences:
            obj = pynmea2.parse(sentence, check=True)

            msg_idx = int(obj.msg_num)
            msg_count = int(obj.num_messages)
            sat_count = int(obj.num_sv_in_view)

            for idx in range(1, 5): # Max 4 satellites in each sentence
                prn = getattr(obj, "sv_prn_num_{:d}".format(idx))
                if not prn:
                    continue

                azimuth = getattr(obj, "azimuth_{:d}".format(idx))
                elevation = getattr(obj, "elevation_deg_{:d}".format(idx))
                snr = getattr(obj, "snr_{:d}".format(idx))

                values.append({
                    "msg_idx": msg_idx,
                    "msg_count": msg_count,
                    "sat_count": sat_count,
                    "prn": prn,
                    "azimuth": float(azimuth) if azimuth else None,
                    "elevation": float(elevation) if elevation else None,
                    "snr": float(snr) if snr else None,
                })

        res["values"] = values

    return res


def gnss_nmea_gsv_ext(enable=None):
    """
    Enable/disable output of extended GSV information. Elevation/Azimuth/SNR (C/No) will
    be displayed as decimals when extended information is enabled, otherwise they will be
    displayed as integers. The configuration parameter will be automatically saved to NVRAM.
    """

    if enable != None:
        return query('AT+QGPSCFG="gsvextnmeatype",{:d}'.format(enable))

    res = query('AT+QGPSCFG="gsvextnmeatype"')
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QGPSCFG"].split(",")
        res["value"] = bool(int(row[1]))

    return res


def gnss_nmea_output_gps(value=None):
    """
    Configure output type of GPS NMEA sentences.

    NOTE: Requires restart of EC2x module to take effect.

    Output type of GPS NMEA sentences by ORed, and the configuration parameter will be automatically saved to NVRAM.
    The default value is 31 which means that all the five types of sentences will be output.

      - '0' = Disable
      - '1' = GGA (Essential fix data which provide 3D location and accuracy data)
      - '2' = RMC (Recommended minimum data for GPS)
      - '4' = GSV (Detailed satellite data)
      - '8' = GSA (Overall satellite data)
      - '16' = VTG (Vector track and speed over the ground)
    """

    if value != None:
        return query('AT+QGPSCFG="gpsnmeatype",{:d}'.format(value))

    res = query('AT+QGPSCFG="gpsnmeatype"')
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QGPSCFG"].split(",")
        res["value"] = int(row[1])

    return res


def gnss_nmea_output_glonass(value=None):
    """
    Configure output type of GLONASS NMEA sentences.

    NOTE: Requires restart of EC2x module to take effect.

    Configure output type of GLONASS NMEA sentences by ORed, and the configuration parameter will be automatically saved to NVRAM.
    The default value is 0.

      - '0' = Disable
      - '1' = GSV
      - '2' = GSA
      - '4' = GNS
    """

    if value != None:
        return query('AT+QGPSCFG="glonassnmeatype",{:d}'.format(value))

    res = query('AT+QGPSCFG="glonassnmeatype"')
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QGPSCFG"].split(",")
        res["value"] = int(row[1])

    return res


def gnss_nmea_output_galileo(value=None):
    """
    Configure output type of Galileo NMEA sentences.

    NOTE: Requires restart of EC2x module to take effect.

    Configure output type of Galileo NMEA sentences by ORed, and the configuration parameter will be automatically saved to NVRAM.
    The default value is 0.

      - '0' = Disable
      - '1' = GSV
    """

    if value != None:
        return query('AT+QGPSCFG="galileonmeatype",{:d}'.format(value))

    res = query('AT+QGPSCFG="galileonmeatype"')
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QGPSCFG"].split(",")
        res["value"] = int(row[1])

    return res


def gnss_nmea_output_beidou(value=None):
    """
    Configure output type of BeiDou NMEA sentences.

    NOTE: Requires restart of EC2x module to take effect.

    Configure output type of BeiDou NMEA sentences via ORed, and the configuration parameter will be automatically saved to NVRAM.
    The default value is 0.

      - '0' = Disable
      - '1' = GSA
      - '2' = GSV
    """

    if value != None:
        return query('AT+QGPSCFG="beidounmeatype",{:d}'.format(value))

    res = query('AT+QGPSCFG="beidounmeatype"')
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QGPSCFG"].split(",")
        res["value"] = int(row[1])

    return res


def gnss_nmea_fix_stats():
    """
    """

    # TODO
    # quality_id
    # quality

    pass


def gnss_nmea_sat_stats(fix_use=None, has_snr=None):
    """
    Get list of summarized information about each satellite currently in view.
    """

    fix_prns = gnss_nmea_gsa()["fix_prns"]

    res = gnss_nmea_gsv()

    if not "values" in res:
        return res

    for v in res["values"]:
        v["fix_use"] = v["prn"] in fix_prns
        v.pop("msg_idx")
        v.pop("msg_count")

    # Filter based on input
    if fix_use != None:
        res["values"] = [v for v in res["values"] if v["fix_use"] == fix_use]
    if has_snr != None:
        res["values"] = [v for v in res["values"] if (has_snr and v["snr"] != None) or (not has_snr and v["snr"] == None)]

    return res


def gnss_location(mode=2):
    """
    Acquire positioning information on request.

    Mode controls latitude and longitude display format:
      - '0' = ddmm.mmmm N/S,dddmm.mmmm E/W
      - '1' = ddmm.mmmmmm N/S,dddmm.mmmmmm E/W
      - '2' = (-)dd.ddddd,(-)ddd.ddddd
    """

    res = query("AT+QGPSLOC={:d}".format(mode))
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QGPSLOC"].split(",")
        res.update({
            "time_utc": nmea_utils.timestamp(row[0]).isoformat(),
            "lat": float(row[1]) if mode == 2 else row[1],
            "lon": float(row[2]) if mode == 2 else row[2],
            "hdop": float(row[3]),
            "alt": float(row[4]),
            "fix": "{:}D".format(row[5]),
            "cog": float(row[6]),
            "sog_km": float(row[7]),
            "sog_kn": float(row[8]),
            "date_utc": nmea_utils.datestamp(row[9]).isoformat(),
            "nsat": int(row[10])
        })

    return res


def gnss_assist(enable=None):
    """
    This command can be used to enable gpsOneXTRA Assistance function, and the
    function can be activated after restarting the module.
    """

    if enable != None:
        return query("AT+QGPSXTRA={:d}".format(enable))

    res = query("AT+QGPSXTRA?")
    if "data" in res:
        res["enabled"] = bool(int(_parse_dict(res.pop("data"))["+QGPSXTRA"]))

    return res


def gnss_assist_time(timestamp=datetime.datetime.utcnow(), operation=0, utc=True, force=False, uncertainty_ms=0):
    """
    This command can be used to inject gpsOneXTRA time to GNSS engine. Before using it,
    customers must enable gpsOneXTRA Assistance function via AT+QGPSXTRA=1 command.
    After activating the function, the GNSS engine will ask for gpsOneXTRA time and
    assistance data file. Before injecting gpsOneXTRA data file, gpsOneXTRA time must
    be injected first via this command.
    """

    return query('AT+QGPSXTRATIME={:d},"{:%Y/%m/%d,%H:%M:%S}",{:d},{:d},{:d}'.format(
        operation, timestamp, utc, force, uncertainty_ms))


def gnss_assist_data(filename=None, storage="ufs"):
    """
    Query the status or specify gpsOneXTRA data file.
    """

    if filename:
        res = query('AT+QGPSXTRADATA="{:s}"'.format(_qf_name(filename, storage)), cooldown_delay=1)  # The module needs some time to be ready after
                                                                                                     # this command before a new status query can be made.
        return res

    res = query("AT+QGPSXTRADATA?")
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QGPSXTRADATA"].split(",", 1)

        dur_mins = int(row[0])
        start_dt = datetime.datetime.strptime(row[1].strip('"'), "%Y/%m/%d,%H:%M:%S")

        # Calculated values
        end_dt = start_dt + datetime.timedelta(minutes=dur_mins)
        exp_mins = (end_dt - datetime.datetime.now()).total_seconds() / 60

        res.update({
            "valid_duration_mins": dur_mins,
            "valid_start": start_dt.isoformat(),
            "valid_end": end_dt.isoformat(),
            "expire_mins": exp_mins,
            "valid_mins": dur_mins - exp_mins
        })

    return res


def gnss_assist_data_reset(type=1):
    """
    Delete assistance data to operate cold start, hot start and warm start of GNSS. The command
    can only be executed when GNSS is turned off. After deleting the assistance data via this
    command, cold start of GNSS can be enforced via AT+QGPS. Hot/warm start can also be performed
    if the corresponding conditions are satisfied.

      - '0' = Delete all assistance data except gpsOneXTRA data. Enforce cold start after starting GNSS.
      - '1' = Do not delete any data. Perform hot start if the conditions are permitted after starting GNSS.
      - '2' = Delete some related data. Perform warm start if the conditions are permitted after starting GNSS.
      - '3' = Delete the gpsOneXTRA assistance data injected into GNSS engine.
    """

    return query('AT+QGPSDEL={:d}'.format(type))


def _qf_name(name, storage):
    if storage.lower() == "ufs":
        return name
    return "{:s}:{:s}".format(storage.upper(), name)


def list_files(pattern="*", storage="ufs"):
    """
    lists the information of a single file or all files in the required storage medium.
    """

    res = query('AT+QFLST="{:s}"'.format(_qf_name(pattern, storage)))
    if "data" in res:
        data = res.pop("data")

        files = []
        data = data if isinstance(data, list) else data
        for row in _parse_dict(data, multiline=True)["+QFLST"]:
            fields = row.split(",")
            qf_name = fields[0].strip('"').split(":", 1)
            files.append({
                "name": qf_name[1] if len(qf_name) > 1 else qf_name[0],
                "storage": qf_name[0] if len(qf_name) > 1 else "UFS",
                "size": fields[1]
            })

        res["values"] = files

    return res


def upload_file(path, storage="ufs", timeout=5):
    """
    """

    name = os.path.basename(path)
    size = os.path.getsize(path)

    res = upload('AT+QFUPL="{:s}",{:d},{:d}'.format(_qf_name(name, storage), size, timeout), path)
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QFUPL"].split(",")
        res.update({
            "name": name,
            "storage": storage,
            "size": row[0],
            "checksum": row[1]
        })

    return res


def download_file(name, dest, storage="ufs"):
    """
    """

    # First we need to get file size
    res = list_files(pattern=name, storage=storage)
    size = int(res["data"][0]["size"])

    # Append filename if 'dest' is a directory
    if os.path.isdir(dest):
        dest = os.path.join(dest, name)

    res = download('AT+QFDWL="{:s}"'.format(_qf_name(name, storage)), size, dest)
    if "data" in res:
        row = _parse_dict(res.pop("data"))["+QFDWL"].split(",")
        res.update({
            "path": dest,
            "size": row[0],
            "checksum": row[1]
        })

    return res


def delete_file(name, storage="ufs"):
    """
    Deletes a single file or all the files in the specified storage.
    """

    return query('AT+QFDEL="{:s}"'.format(_qf_name(name, storage)))


def sms_format_config(value=None):
    """
    """

    if value != None:
        return query("AT+CMGF={:d}".format(value))

    res = query("AT+CMGF?")
    if "data" in res:
        res["value"] = int(_parse_dict(res.pop("data"))["+CMGF"])

    return res


def list_sms():
    """
    List all messages from message storage.
    """

    res = query('AT+CMGL="all"')

    return res


def manage(*args, **kwargs):
    """
    Runtime management of the underlying service instance.

    Supported commands:
      - 'hook list|call <name> [argument]... [<key>=<value>]...'
      - 'worker list|show|start|pause|resume|kill <name>'
      - 'reactor list|show <name>'
      - 'run <key>=<value>...'

    Examples:
      - 'ec2x.manage hook list'
      - 'ec2x.manage hook call exec_handler ATI'
      - 'ec2x.manage worker list *'
      - 'ec2x.manage worker show *'
      - 'ec2x.manage worker start *'
      - 'ec2x.manage worker pause *'
      - 'ec2x.manage worker resume *'
      - 'ec2x.manage worker kill *'
      - 'ec2x.manage reactor list'
      - 'ec2x.manage reactor show *'
      - 'ec2x.manage run handler="exec" args="[\"ATI\"]" returner="cloud"' 
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))

