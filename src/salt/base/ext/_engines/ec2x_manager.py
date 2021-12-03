import logging
import re
import time
import salt.exceptions

from datetime import datetime, timedelta
from messaging import EventDrivenMessageProcessor
from serial_conn import SerialConn
from threading_more import intercept_exit_signal
from parsing import _parse_dict


log = logging.getLogger(__name__)

context = {
    "time": {
        "state": None
    }
}

# Message processor
edmp = EventDrivenMessageProcessor("ec2x", context=context, default_hooks={"handler": "exec"})

# Serial connection
conn = SerialConn()

error_regex = re.compile("ERROR|\+(?P<type>.+) ERROR: (?P<reason>.+)")

rtc_time_regex = re.compile('^\+CCLK: "(?P<year>\d{2})/(?P<month>\d{2})/(?P<day>\d{2}),(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?P<tz>[+|-]\d+)"$')
# Example: +CCLK: "08/01/04,00:19:43+00"

network_time_regex = re.compile('^\+QLTS: "(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2}),(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?P<tz>[+|-]\d+),(?P<dst>\d+)"$')
# Example: +QLTS: "2017/01/13,03:40:48+32,0"


@edmp.register_hook(synchronize=False)
def connection_handler(close=False):
    """
    Manages current connection.

    Optional arguments:
      - close (bool): Close serial connection? Default value is 'False'. 
    """

    ret = {}

    if close:
        log.warning("Closing serial connection")

        conn.close()

    ret["is_open"] = conn.is_open()
    ret["settings"] = conn.settings

    return ret


def _exec(cmd, ready_words=["OK"], keep_conn=True, cooldown_delay=None, timeout=None):
    log.debug("Executing: %s", cmd)

    res = None

    try:
        conn.write_line(cmd)

        for ready_word in ready_words:
            res = conn.read_until(ready_word, error_regex, timeout=timeout)

            if "error" in res:
                break

        log.debug("Got result: %s", res)

    finally:
        if not keep_conn:
            log.debug("Closing AT serial connection")
            conn.close()

    # Wait if cooldown delay is defined
    if cooldown_delay != None:
        log.info("Sleeps for {:f} seconds according to specified cooldown delay".format(cooldown_delay))
        time.sleep(cooldown_delay)

    return res


@edmp.register_hook()
def exec_handler(cmd, **kwargs):
    """
    Runs an AT command against the EC2X device.

    Arguments:
      - cmd (str): AT command to execute.
    """

    return _exec(cmd, **kwargs)


@edmp.register_hook()
def power_handler(cmd, reason="unknown"):
    """
    Powers down the EC2X device. Afterwards the module will start automatically.
    A 30-second wait is included after power off to allow the module time to recover before receiving any new requests.

    Arguments:
      - cmd (str): AT command to perform the power down.

    Optional arguments:
      - reason (str): Reason code that tells why we decided to power down. Default is 'unknown'.
    """

    # We need to give the module a cooldown period of 30 secs to power off completely and prevent
    # new requests when not ready. If an open serial connection exists during power off it will block
    # everything when using an USB hub connected to the RPi's built-in USB - yup, go figure!

    # TODO: We also need to close NMEA serial connection to prevent system freeze
    #global nmea_conn
    #nmea_conn.close()
    #nmea_conn = None

    log.warn("Powering down EC2X module - will restart momentarily")

    # TODO: Sometimes raises SerialException: device reports readiness to read but returned no data (device disconnected or multiple access on port?)
    res = _exec(cmd, ready_words=["OK", "POWERED DOWN"], keep_conn=False, cooldown_delay=30)

    # Trigger power off event
    edmp.trigger_event({
        "reason": reason,
    }, "system/device/ec2x/powered_off")

    return res


@edmp.register_hook()
def upload_handler(cmd, src):
    """
    Uploads a file to the EC2X device.

    Arguments:
      - cmd (str): AT command to perform the actual upload.
      - src (str): Destination path to the file to be uploaded.
    """

    content = None
    with open(src, mode="rb") as f:
        content = f.read()

    conn.write_line(cmd)
    res = conn.read_until("CONNECT", error_regex)

    if "error" in res:
        return res

    conn.write(content)

    res = conn.read_until("OK", error_regex, echo_on=False)

    return res


@edmp.register_hook()
def download_handler(cmd, size, dest):
    """
    Downloads a file from the EC2X device.

    Arguments:
      - cmd (str): AT command to perform the actual download.
      - size (int): Size of the file to download.
      - dest (str): Destination path to which the downloaded file is to be written.
    """

    conn.write_line(cmd)
    res = conn.read_until("CONNECT", error_regex)

    if "error" in res:
        return res

    content = conn.read(size)

    res = conn.read_until("OK", error_regex, echo_on=False)
    if not "error" in res:
        with open(dest, mode="wb") as f:
            f.write(content)

    return res


@edmp.register_hook()
def sync_time_handler(force=False):
    """
    Synchronizes the system clock with the EC2X device.

    Optional arguments:
      - force (bool): Default is 'False'.
    """

    def get_clock_status():
        """
        Ensures following keys for return value:

        clock_synced: boolean
        npt_enabled: boolean
        """

        ret = {}

        res = __salt__["clock.status"]()

        # Try old values first (Raspbian 9)
        if "ntp_synchronized" in res:
            # actually assign value
            ret["clock_synced"] = res["ntp_synchronized"] == "yes"

        # Try new value now (RPi OS 10)
        elif "system_clock_synchronized" in res:
            # actually assign value
            ret["clock_synced"] = res["system_clock_synchronized"] == "yes"

        else:
            raise KeyError("Could not find clock synchronization key-value pair")

        # Repeat as above
        if "network_time_on" in res:
            ret["ntp_enabled"] = res["network_time_on"] == "yes"
        elif "ntp_service" in res:
            ret["ntp_enabled"] = res["ntp_service"] == "active"
        else:
            raise KeyError("Could not find NTP service key-value pair")

        return ret


    ret = {}

    ctx = context["time"]

    # Skip if time has already been synchronized
    if ctx["state"] == "synced":
        log.info("System time has already been synchronized")

        return ret

    # Check if system time is already NTP synchronized
    status = get_clock_status()
    if not force and status["clock_synced"]:
        log.info("System time is already NTP synchronized")

        ret["source"] = "ntp"

        ctx["state"] = "synced"

    else:

        # We do not want below log when force
        if not status["clock_synced"]:
            log.info("System time is not NTP synchronized")

        # Disable automatic time synchronization 
        # NOTE: This is done now to minimize time between get network time and adjust system clock 
        if status["ntp_enabled"]:
            __salt__["clock.ntp"](enable=False)

        try:

            time = None

            # First try to get time from module's RTC
            res = _exec("AT+CCLK?")
            if not "error" in res:
                match = rtc_time_regex.match(res["data"])
                if match:
                    time = "{year:}-{month:}-{day:} {hour:}:{minute:}:{second:}".format(**match.groupdict())

                    # Validate time is within acceptable range otherwise discard it
                    if abs((datetime.utcnow() - datetime.strptime(time, "%y-%m-%d %H:%M:%S")).days) > 365:
                        log.info("Skipping invalid time retrieved from module's RTC: {:}".format(time))

                        time = None
                    else:
                        ret["source"] = "rtc"
                else:
                    log.warning("Failed to match time result from module's RTC: {:}".format(res["data"]))                
            else:
                log.warning("Unable to retrieve time from module's RTC: {:}".format(res["error"]))

            # Alternatively, try to get time from module network
            if time == None:

                # Get current UTC network time
                res = _exec("AT+QLTS=1")
                if "error" in res:
                    raise Exception("Unable to retrieve module network time: {:}".format(res["error"]))

                match = network_time_regex.match(res["data"])
                if not match:
                    raise Exception("Failed to match time result from module network: {:}".format(res["data"]))

                time = "{year:}-{month:}-{day:} {hour:}:{minute:}:{second:}".format(**match.groupdict())
                ret["source"] = "network"

            # Set old time before we adjust clock
            ret["old"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            # Set system time manually
            __salt__["clock.set"](time, adjust_system_clock=True)

            ret["new"] = time

            log.info("Synchronized system time with time from module source '{:}'".format(ret["source"]))

            ctx["state"] = "synced"

        except:
            if ctx["state"] != "uncertain":
                ctx["state"] = "uncertain"

                # Trigger time uncertain event
                edmp.trigger_event({}, "system/time/{:}".format(ctx["state"]))

            raise

        finally:

            # Re-enable automatic time synchronization
            __salt__["clock.ntp"](enable=True)

    # Trigger time synced event
    edmp.trigger_event(
        ret,
        "system/time/{:}".format(ctx["state"])
    )

    # Always update module's RTC time if synchronized from different source
    if ret["source"] != "rtc":
        res = _exec("AT+CCLK=\"{0:%y/%m/%d,%H:%M:%S}+00\"".format(datetime.utcnow()))
        if not "error" in res:
            log.info("Updated time of module's RTC")
        else:
            log.warning("Unable to update time of module's RTC: {:}".format(res["error"]))

    return ret


@edmp.register_hook()
def sms_format_config_handler(value=None):
    """
    Gets or sets the SMS format configuration.

    Possible values:
      - 0: PDU mode - entire TP data units used (hex responses). This is the default value.
      - 1: Text mode - headers and body of the message given as separate parameters.
    """

    if value != None:
        return exec_handler("AT+CMGF={:d}".format(value))

    res = exec_handler("AT+CMGF?")
    if "data" in res:
        res["value"] = int(_parse_dict(res.pop("data"))["+CMGF"])

    return res


@edmp.register_hook()
def list_sms_handler():
    """
    List all messages from message storage.

    NOTE: In order to use this function, you need to first execute `ec2x.sms_format_config value=1`
    to set the correct format of the SMS messages.
    """
    res = exec_handler('AT+CMGL="all"')

    return res


@edmp.register_hook()
def delete_sms_handler(index=None, delete_all=False, confirm=False):
    """
    Delete messages from message storage.

    It is possible to list possible for deleting if no indexes are passed and the 'delete_all' kwarg is not passed (or set to 'False').

    Keyword argumnets:
      - index (int): The index of the message to be deleted. Default None.
      - delete_all (bool): Set this boolean to true if all messages stored in the modem should be deleted. Default 'False'.
      - confirm (bool): A confirm flag when deleting messages. Default 'False'.
    """

    # list delete-able messages
    if index == None and delete_all == False:
        res = exec_handler("AT+CMGD=?")
        return res

    # or actually delete messages
    if not confirm:
        raise salt.exceptions.CommandExecutionError(
            "This command will delete SMS messages stored on the modem - add parameter 'confirm=true' to continue anyway.")

    if delete_all:
        log.info("Deleting all SMS messages stored in the modem's memory")
        res = exec_handler("AT+CMGD=1,4")
    else:
        log.info("Deleting a single SMS message with index {}".format(index))
        res = exec_handler("AT+CMGD={},0".format(index))

    return res


@edmp.register_hook()
def read_sms_handler():
    """
    Reads SMS messages stored in the modem and processes them into 'system/sms/received' events.
    Those events hold information such as the timestamp of the message (when it was received by the
    modem), the sender and the text. Messages will be deleted from the modem after being processed.

    NOTE: This function will configure the SMS format to text mode. This is necessary in order to read
    the messages correctly. If necessary, revert the configuration with the 'ec2x.sms_format_config'
    command.
    """

    # read messages
    if log.isEnabledFor(logging.DEBUG):
        log.debug("Configuring the SMS format to text mode")

    sms_format_config_handler(value=1) # make SMS messages readable
    list_sms_res = list_sms_handler()

    if not list_sms_res.get("data", None):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("No SMS messages to process, skipping read_sms_handler execution")
        return

    new_sms = list_sms_res["data"]
    log.info("New SMS have been received and will be processed: {}".format(new_sms))

    # go through new messages, trigger events for those
    sms_to_process = []
    for i in range(0, len(new_sms), 2):
        message_meta = new_sms[i]
        message_text = new_sms[i+1]

        index, message_status, sender, _, date, time = [m.strip("\"") for m in message_meta[7:].split(",")]

        # NV NOTE: Since the modem stores a time offset value (timezone info) we need to use that
        # to calculate the timestamp to be in UTC. Keep in mind that this calculation has only been
        # tested in a single timezone and more testing might need to be done.

        # example timestamp from modem:    21/11/16,14:10:00+04 (each offset increment equals 15 minutes)
        # utc timestamp after calculation: 2021-11-16T13:10:00
        time_offset_sign = time[-3:-2]
        time_offset = int(time[-2:])
        offset_duration = timedelta(minutes=(15 * time_offset))

        sms_timestamp = datetime.strptime(
            "{}T{}".format(date, time[:-3]),
            "%y/%m/%dT%H:%M:%S")

        if time_offset_sign == "+":
            sms_timestamp = sms_timestamp - offset_duration
        elif time_offset_sign == "-":
            sms_timestamp = sms_timestamp + offset_duration
        else:
            raise Exception("Received an unexpected time offset sign: {}".format(time_offset_sign))

        # timestamp calculation done

        sms = {
            "index": index,
            "message_status": message_status,
            "sender": sender,
            "timestamp": sms_timestamp.isoformat(),
            "text": message_text,
        }

        sms_to_process.append(sms)

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Preparing to delete SMS messages from modem: {}".format(sms_to_process))

    # process SMS
    sms_to_delete = []
    for sms in sms_to_process:
        # trigger event
        __salt__["minionutil.trigger_event"]("system/sms/received", data={
            "sender": sms["sender"],
            "timestamp": sms["timestamp"],
            "text": sms["text"],
        })

        # delete SMS from modem
        delete_sms_handler(index=sms["index"], confirm=True)


@intercept_exit_signal
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting EC2X manager with settings: {:}".format(settings))

        # Initialize serial connection
        conn.init(settings["serial_conn"])

        # Initialize and run message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        edmp.run()

    except Exception:
        log.exception("Failed to start EC2X manager")

        raise

    finally:
        log.info("Stopping EC2X manager")

        if conn.is_open():
            try:
                conn.close()
            except:
                log.exception("Failed to close serial connection")
