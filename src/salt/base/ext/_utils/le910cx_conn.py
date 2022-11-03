import datetime
import logging
import re
import time
import pynmea2
import salt.exceptions

from serial_conn import SerialConn
from retrying import retry
from common_util import dict_key_by_value

log = logging.getLogger(__name__)

# +CME ERROR: unknown
error_regex = re.compile("ERROR|\+(?P<type>.+) ERROR: (?P<reason>.+)")


class LE910CXException(Exception):
    pass


class NoFixException(LE910CXException):
    def __init__(self, message="No fix"):
        self.message = message
        super(NoFixException, self).__init__(message)


class InvalidResponseException(LE910CXException):
    pass


class CommandExecutionException(LE910CXException):
    pass


class NoSimPresentException(LE910CXException):
    def __init__(self, message="No SIM present"):
        self.message = message
        super(NoSimPresentException, self).__init__(message)


SMS_FORMAT_MODE_PUD = 0
SMS_FORMAT_MODE_TEXT = 1

SMS_FORMAT_MODES = {
    SMS_FORMAT_MODE_PUD:  "PUD",
    SMS_FORMAT_MODE_TEXT: "TXT"
}

SMS_DELETE_ALL = 1

GNSS_LOCATION_FIX_INVALID_FIX = 0
GNSS_LOCATION_FIX_NO_FIX      = 1
GNSS_LOCATION_FIX_2D_FIX      = 2
GNSS_LOCATION_FIX_3D_FIX      = 3

GNSS_LOCATION_FIX_MAP = {
    GNSS_LOCATION_FIX_INVALID_FIX: "invalid_fix",
    GNSS_LOCATION_FIX_NO_FIX:      "no_fix",
    GNSS_LOCATION_FIX_2D_FIX:      "2D",
    GNSS_LOCATION_FIX_3D_FIX:      "3D",
}

NMEA_MODE_DISABLED   = 0
NMEA_MODE_FIRST_FMT  = 1
NMEA_MODE_SECOND_FMT = 2
NMEA_MODE_PORT_LOCK  = 3

NMEA_MODE_MAP = {
    NMEA_MODE_DISABLED:   "disabled",
    NMEA_MODE_FIRST_FMT:  "first_format",
    NMEA_MODE_SECOND_FMT: "second_format",
    NMEA_MODE_PORT_LOCK:  "port_lock",
}

ME_ERROR_MODE_DISABLED = 0
ME_ERROR_MODE_NUMERIC  = 1
ME_ERROR_MODE_VERBOSE  = 2

ME_ERROR_MODE_MAP = {
    ME_ERROR_MODE_DISABLED: "disabled",
    ME_ERROR_MODE_NUMERIC:  "numeric",
    ME_ERROR_MODE_VERBOSE:  "verbose",
}

PERIODIC_RESET_MODE_DISABLED = 0
PERIODIC_RESET_MODE_ONE_SHOT = 1
PERIODIC_RESET_MODE_PERIODIC = 2

PERIODIC_RESET_MODE_MAP = {
    PERIODIC_RESET_MODE_DISABLED: "disabled",
    PERIODIC_RESET_MODE_ONE_SHOT: "one_shot",
    PERIODIC_RESET_MODE_PERIODIC: "periodic",
}

FW_NET_CONF_ATT     = 0
FW_NET_CONF_VERIZON = 1
FW_NET_CONF_BELL    = 3
FW_NET_CONF_TELUS   = 4
FW_NET_CONF_GLOBAL  = 40

FW_NET_CONF_MAP = {
    FW_NET_CONF_ATT:     "att",
    FW_NET_CONF_VERIZON: "verizon",
    FW_NET_CONF_BELL:    "bell",
    FW_NET_CONF_TELUS:   "telus",
    FW_NET_CONF_GLOBAL:  "global",
}

FW_STORAGE_CONF_RAM = 0
FW_STORAGE_CONF_NVM = 1

FW_STORAGE_CONF_MAP = {
    FW_STORAGE_CONF_RAM: "ram",
    FW_STORAGE_CONF_NVM: "nvm",
}

QSS_STATUS_NOT_INSERTED              = 0
QSS_STATUS_INSERTED                  = 1
QSS_STATUS_INSERTED_AND_PIN_UNLOCKED = 2
QSS_STATUS_INSERTED_AND_READY        = 3

QSS_MAP = {
    QSS_STATUS_NOT_INSERTED:              "not-inserted",
    QSS_STATUS_INSERTED:                  "inserted",
    QSS_STATUS_INSERTED_AND_PIN_UNLOCKED: "inserted-and-pin-unlocked",
    QSS_STATUS_INSERTED_AND_READY:        "inserted-and-ready",
}

# EVMONI_GPIOX_WATCH_STATUS_LOW     = "high"
# EVMONI_GPIOX_WATCH_STATUS_HIGH    = "low"

# EVMONI_GPIOX_WATCH_STATUS_MAP = {
#     EVMONI_GPIOX_WATCH_STATUS_LOW: False,
#     EVMONI_GPIOX_WATCH_STATUS_HIGH: True
# }

SUPPORTED_DATATYPES = (bool, int, str)
PARAM_TYPES = {'indexed': 1, 'indexed_readonly': 2, 'numbered': 3}
MULTILINE_TYPES = {'dictionary': 1, 'array': 2}

class LE910CXConn(SerialConn):
    """
    Connection class that implements the communication with a LE910CX modem.

    A pattern that is required throughout this connection class is the use of a 'force' argument on get/set commands.
    This means that the modem should always query the command's current status and then, only if needed or forced by
    the 'force' argument, the set command should be run.
    """

    def __init__(self):
        super(LE910CXConn, self).__init__()

    def init(self, settings):
        super(LE910CXConn, self).init(settings)

    def open(self):
        super(LE910CXConn, self).open()
        self.config(self._settings)
        
    def config(self, settings):
        """
        Configure the modem with passed settings.
        """

        # NOTE NV: We have seen instances where the modem is rebooted, but then
        # isn't ready quick enough to get configured correctly. This causes the
        # GNSS manager to fail, so we have this sort of check here.
        try:
            # Ensure modem is ready to receive commands
            ready = False
            max_retries = 5
            for i in range(max_retries):
                try:
                    self.execute("ATI")
                    ready = True
                    break
                except CommandExecutionException as e:
                    log.exception("Received error {} while waiting for modem to be ready".format(e))
                    time.sleep(.5) # Sleep to give time for modem to be ready?

            if not ready:
                raise Exception("Modem isn't ready to receive commands yet")

            # Configure echo on/off
            self.execute("ATE{:d}".format(settings.get("echo_on", True)))

            # Configure GNSS
            if "error_config" in settings:
                self.error_config(mode=settings["error_config"])

            if "gnss_session" in settings:
                self.gnss_session(status=settings["gnss_session"])

        except Exception as e:
            log.exception("Error occurred while configuring LE910CX modem, closing connection")
            self.close()

    def execute(self, cmd, ready_words=["OK"], keep_conn=True, cooldown_delay=None, timeout=None, raise_on_error=True):
        """
        Execute a custom AT command.

        Arguments:
        - cmd (string): The command to be executed.

        Optional arguments:
        - ready_words (list of strings): The ready words to look for - if the function sees those messages from the modem, the command will
          be considered completed and return. Default: `["OK"]`.
        - keep_conn (bool): Whether or not to keep the connection alive after the command has been executed. Default: True.
        - cooldown_delay (number): A number in seconds for which to wait after the command has been executed. Default: None.
        - timeout (number): A timeout in seconds after which the function will terminate. Default: None (falls back to the default timeout for the class).
        - raise_on_error (bool): Set this to true to raise an error when the modem responds with an error. Default: True.
        """

        log.debug("Executing AT command: %s", cmd)
        res = None

        try:
            self.write_line(cmd)

            for ready_word in ready_words:
                res = self.read_until(ready_word, error_regex, timeout=timeout, echo_on=self._settings.get("echo_on", True))

                if "error" in res:
                    log.error("Command {} returned error {}".format(cmd, res["error"]))
                    break

            log.debug("Got result: %s", res)

        finally:
            if not keep_conn:
                log.info("Closing serial connection")
                self.close()

        # Wait if cooldown delay is defined
        if cooldown_delay != None:
            log.info("Sleeps for {:f} seconds according to specified cooldown delay".format(cooldown_delay))
            time.sleep(cooldown_delay)

        # Raise on error
        if raise_on_error and "error" in res:
            raise CommandExecutionException("Command {} returned error {}".format(cmd, res["error"]))

        return res

    def error_config(self, mode=None, force=False):
        """
        Configures the error values the modem returns.

        Optional parameters:
        - mode (string): The mode that should be set to the modem. Passing no mode will read the current configuration.
          Read available modes below. Default: None
        - force (bool): Force apply the configuration to the modem.

        Available modes:
        - disabled: Disable verbose error logging. Modem will return just `ERROR` responses.
        - numeric: Modem will return numerical error values.
        - verbose: Modem will return verbose error values.
        """

        ret = {}
        res = self.execute("AT+CMEE?")

        res_regex = re.compile("\+CMEE: (?P<mode>[0-2])")
        match = res_regex.match(res.get("data", ""))

        if not match:
            log.error("Didn't receive expected response from modem: {}".format(res))
            raise InvalidResponseException("Didn't receive expected response")

        ret["mode"] = ME_ERROR_MODE_MAP[int(match.group("mode"))]

        if mode != None:
            # Validate mode
            if type(mode) != str or mode not in ME_ERROR_MODE_MAP.values():
                raise ValueError("'mode' argument needs to be one of {}".format(ME_ERROR_MODE_MAP.values()))

            if ret["mode"] != mode or force:
                mode_val = dict_key_by_value(ME_ERROR_MODE_MAP, mode)
                self.execute("AT+CMEE={:d}".format(mode_val))

                ret["mode"] = mode

        return ret

    def imei(self):
        res = self.execute("AT+GSN=1")
        return re.compile("\\+GSN: (?P<value>[0-9]+)").match(res.get("data", "")).groupdict()

    def manufacturer_id(self):
        ret = {}

        res = self.execute("AT+GMI")
        ret["value"] = res.get("data", None)

        return ret

    def model_id(self):
        ret = {}

        res = self.execute("AT+GMM")
        ret["value"] = res.get("data", None)

        return ret

    def soft_reset(self):
        ret = {}

        self.execute("ATZ")

        return ret

    def reset(self, mode=None, delay=0):
        """
        Enable or disable the one shot or periodic unit reset.

        Optional parameters:
        - mode (string): The mode in which to operate the command. For available values, look below. Default: None.
        - delay (number): Time interval in minutes after that the unit reboots. Default: 0.

        Available modes:
        - disabled: Disables unit reset.
        - one_shot: Enables the unit reset only one time (one shot reset).
        - periodic: Enables periodic resets of the unit.
        """

        if mode == None:
            # We only query here
            ret = {}

            res_regex = re.compile("^#ENHRST: (?P<mode>[0-2])(,(?P<delay>[0-9]+),(?P<remain_time>[0-9]+))?$")
            res = self.execute("AT#ENHRST?")

            match = res_regex.match(res.get("data", ""))
            if not match:
                log.error("Didn't receive expected response: {}".format(res))
                raise InvalidResponseException("Didn't receive expected response")

            ret["mode"] = match.group("mode")

            if match.group("delay"):
                ret["delay"] = match.group("delay")

            if match.group("remain_time"):
                ret["remain_time"] = match.group("remain_time")

            return ret

        # Otherwise, lets set it
        # Validate first
        if type(mode) != str or mode not in PERIODIC_RESET_MODE_MAP.values():
            raise ValueError("'mode' parameter must be one of {}".format(PERIODIC_RESET_MODE_MAP.values()))

        if type(delay) != int:
            raise TypeError("'delay' parameter must be an integer")

        # Construct AT command
        mode_val = dict_key_by_value(PERIODIC_RESET_MODE_MAP, mode)
        cmd = "AT#ENHRST={:d}".format(mode_val)

        # Do we need to add the delay?
        if mode_val in [PERIODIC_RESET_MODE_ONE_SHOT, PERIODIC_RESET_MODE_PERIODIC]:
            cmd += ",{:d}".format(delay)

        # Don't keep connection if we're immediately resetting, wait for modem to come back up
        if mode_val in [PERIODIC_RESET_MODE_ONE_SHOT, PERIODIC_RESET_MODE_PERIODIC] and delay == 0:
            return self.execute(cmd, keep_conn=False, cooldown_delay=10)

        # Keep connection otherwise, we might want to execute more commands
        return self.execute(cmd)

    def time(self):
        # TODO NV: Improve to be consistent with the rest of the class implementation

        return self.execute("AT+CCLK?")

    def cell_location(self):
        # TODO NV: Improve to be consistent with the rest of the class implementation

        return self.execute("AT#GTP")

    def sms_storage(self):
        # TODO NV: Improve to be consistent with the rest of the class implementation
        ret = {}

        res = self.execute("AT+CPMS?")
        re.compile("\\+CPMS: \"(?P<read_mem>[0-1])\"").match(res.get("data", ""))


        ret["mode"] = SMS_FORMAT_MODES.get(int(re.compile("\\+CMGF: (?P<mode>[0-1])").match(res.get("data", "")).group("mode")), None)

    def sms_format(self, mode=None, force=False):
        """
        Configures the SMS format.

        Possible modes:
        - 'pud': PUD mode
        - 'txt': Text mode
        """
        # TODO NV: Improve to be consistent with the rest of the class implementation

        ret = {}

        if not force:
            res = self.execute("AT+CMGF?")
            ret["mode"] = SMS_FORMAT_MODES.get(int(re.compile("\\+CMGF: (?P<mode>[0-1])").match(res.get("data", "")).group("mode")), None)
        elif mode == None:
            raise ValueError("Mode must be specified")

        if mode != None:
            mode = mode.upper()

            if not mode in SMS_FORMAT_MODES.values():
                raise ValueError("Unsupported mode")

            if force or mode != ret["mode"]:
                self.execute("AT+CMGF={:d}".format(dict_key_by_value(SMS_FORMAT_MODES, mode)))
                ret["mode"] = mode

        return ret

    def sms_list(self, status="ALL", clear=False, format_mode="TXT"):
        """
        Returns a list of all SMS messages currently stored on the modem.

        Optional parameters:
        - status (str): The status of the messages that are to be returned. Look below for avalable options. Default: "ALL".
        - clear (bool): Should the returned messages be removed from the modem as well?
        - format_mode (str): The format in which the messages should be processed. Currently, only TXT mode is supported. Default: "TXT".

        Available options (status):
        - "REC UNREAD" - new messages
        - "REC READ" - read messages
        - "STO UNSENT" - stored messages not sent yet
        - "STO SENT" - stored messages already sent
        - "ALL" - all messages
        """

        # First check if the SIM is present
        sim = self.query_sim_status()
        if sim["status"] == QSS_MAP[QSS_STATUS_NOT_INSERTED]:
            raise NoSimPresentException()

        ret = {"values": []}

        # Ensure message format mode
        prev_format_mode = self.sms_format().get("mode", "PUD")
        if prev_format_mode != format_mode:
            self.sms_format(mode=format_mode)

        try:
            res = self.execute("AT+CMGL=\"{:s}\"".format(status))
            if not res.get("data", None):
                return ret

            # Structure (per SMS) as per AT commands reference:
            # +CMGL:<index>,<stat>,<oa/da>,<alpha>,<scts>[,<tooa/toda>,<length>]<CR><LF>
            # <data>
            meta_regex = re.compile("^\+CMGL: (?P<index>[0-9]+)," + \
                    "\"(?P<status>[A-Z\s]+)\"," + \
                    "\"(?P<sender>\+?[0-9]+)\"," + \
                    "\"(?P<alpha>[a-zA-Z0-9]*)\"," + \
                    "\"(?P<scts>.+)\"" + \
                    ".*") # have to cover for some extra stuff that could occur here, look at structure above

            scts_regex = re.compile("^(?P<date>[0-9]{2}\/[0-9]{2}\/[0-9]{2})," + \
                    "(?P<time>[0-9]{2}:[0-9]{2}:[0-9]{2})(?P<offset_sign>[+-])(?P<offset>[0-9]{2})")

            # NOTE NV: This could potentially cause problems if the output is unexpected, we don't check it before
            # actually starting the loop...
            for i in range(0, len(res["data"]), 2): # Process every second one - one message is two entries in here
                meta = res["data"][i]
                data = res["data"][i+1]

                # Parse meta
                meta_match = meta_regex.match(meta)
                if not meta_match:
                    log.error("Didn't receive expected response from modem: {}".format(meta))
                    raise InvalidResponseException("Didn't receive expected response")

                # Parse timestamp (https://stackoverflow.com/a/35444511)
                scts_match = scts_regex.match(meta_match.group("scts"))
                if not scts_match:
                    log.error("Didn't receive expected Service Center Time Stamp from modem: {}. Full meta line: {}".format(scts, meta))
                    raise InvalidResponseException("Didn't receive expected response")

                # NOTE NV: Since the modem stores a time offset value (timezone info) we need to use that
                # to calculate the timestamp to be in UTC. Keep in mind that this calculation has only been
                # tested in a single timezone and more testing might need to be done.

                # example timestamp from modem:    21/11/16,14:10:00+04 (each offset increment equals 15 minutes)
                # utc timestamp after calculation: 2021-11-16T13:10:00
                offset_sign = scts_match.group("offset_sign")
                offset = int(scts_match.group("offset"))
                offset_duration = datetime.timedelta(minutes=(15 * offset))

                msg_timestamp = datetime.datetime.strptime("{}T{}".format(scts_match.group("date"), scts_match.group("time")), "%y/%m/%dT%H:%M:%S")

                # NOTE: When offset is positive, we need to go back in time to get to UTC
                # NOTE: When offset is negative, we need to go forward in time to get to UTC
                if offset_sign == "+":
                    msg_timestamp = msg_timestamp - offset_duration
                elif offset_sign == "-":
                    msg_timestamp = msg_timestamp + offset_duration
                else:
                    raise Exception("Received an unexpected time offset sign: {}".format(offset_sign))

                msg = {
                    "index": int(meta_match.group("index")), # Casting this, other functions relying on this parameter expect it to be an integer
                    "status": meta_match.group("status"),
                    "sender": meta_match.group("sender"),
                    "sender_alpha": meta_match.group("alpha"),
                    "timestamp": msg_timestamp.isoformat(),
                    "data": data,
                }

                ret["values"].append(msg)

            # Finally clear messages if required
            if bool(clear):
                res = self.sms_delete(*[m["index"] for m in ret["values"]], confirm=True)
                ret["clear"] = res

        finally:
            try:
                self.sms_format(mode=prev_format_mode)
            except:
                log.exception("Failed to restore SMS format mode")

        return ret

    def sms_delete(self, *indexes, **kwargs):
        """
        Deletes SMS message(s) stored on the modem.

        Parameters:
        - indexes (list[number]): The indexes of the messages that should be deleted.

        Optional parameters:
        - delete_all (bool): If all messages stored should be deleted. If this parameter is set
          the `indexes` parameter is ignored. Default: False.
        - confirm (bool): A confirmation flag needed to delete messages. Default: False.
        """
        #NOTE NV: This could definitely be improved to cover all possible operations of the AT+CMGD command

        delete_all = kwargs.pop("delete_all", False)
        confirm = kwargs.pop("confirm", False)

        ret = {}

        # Always confirm first!
        if not confirm:
            raise salt.exceptions.CommandExecutionError(
                "This command will delete SMS messages stored on the modem - add parameter 'confirm=true' to continue anyway.")

        if delete_all:
            log.info("Deleting *ALL* SMS messages in storage!")
            self.execute("AT+CMGD=1,4")
            ret["deleted"] = "All stored messages deleted"

        else:
            # Delete indexes only
            ret["deleted"] = {}

            for i in indexes:
                # Skip non int indexes
                if type(i) is not int:
                    ret["deleted"][i] = False
                    log.warning("Skipping provided index {} as it's not a number".format(i))
                    continue

                log.info("Deleting message with index {}".format(i))
                self.execute("AT+CMGD={},0".format(i))
                ret["deleted"][i] = True

        return ret

    def gnss_location(self, decimal_degrees=False):
        """
        Fetches current GPS location and other GPS related metadata from the modem.

        Parameters:
        - decimal_degrees (bool): Whether to return the lat/lon data in DD (decimal degrees) format as opposed to the default
          DMS (degrees, minutes, seconds) format.
        """

        ret = {}
        res = self.execute("AT$GPSACP")

        # Example responses (you can use these for testing)
        # $GPSACP: 093446.000,5702.1608N,00956.1064E,1.4,-30.6,3,0.0,0.0,0.0,140622,04,04
        # $GPSACP: 123748.004,5702.1860N,00956.1058E,2.2,21.1,3,0.0,0.0,0.0,130622,06,00
        # $GPSACP: ,,,,,1,,,,,,           NOTE: Nofix
        res_regex = re.compile("^\$GPSACP: " + \
            "(?P<utc>[0-9]{6}\.[0-9]{3})?," + \
            "(?P<lat>[0-9]{4}\.[0-9]{4}(N|S))?," + \
            "(?P<lon>[0-9]{5}\.[0-9]{4}(W|E))?," + \
            "(?P<hdop>[0-9]+\.?[0-9]*)?," + \
            "(?P<altitude>-?[0-9]+\.?[0-9]*)?," + \
            "(?P<fix>[0-3])," + \
            "(?P<cog>[0-9]+\.[0-9]+)?," + \
            "(?P<spkm>[0-9]+\.[0-9]+)?," + \
            "(?P<spkn>[0-9]+\.[0-9]+)?," + \
            "(?P<date>[0-9]{6})?," + \
            "(?P<nsat_gps>[0-9]{2})?," + \
            "(?P<nsat_glonass>[0-9]{2})?")

        match = res_regex.match(res.get("data", ""))

        if not match:
            log.error("Didn't receive expected response from modem: {}".format(res))
            raise InvalidResponseException("Didn't receive expected response")

        if int(match.group("fix")) in [ GNSS_LOCATION_FIX_INVALID_FIX, GNSS_LOCATION_FIX_NO_FIX ]:
            raise NoFixException()

        # Parse response
        time_utc = match.group("utc")
        date_utc = match.group("date")
        ret = {
            "time_utc":     "{}:{}:{}".format(time_utc[0:2], time_utc[2:4], time_utc[4:6]),
            "date_utc":     "20{}-{}-{}".format(date_utc[4:6], date_utc[2:4], date_utc[0:2]), # NOTE: Date can only start from year 2000
            "hdop":         float(match.group("hdop")),
            "alt":          float(match.group("altitude")),
            "fix":          GNSS_LOCATION_FIX_MAP[int(match.group("fix"))],
            "cog":          float(match.group("cog")),
            "sog_km":       float(match.group("spkm")),
            "sog_kn":       float(match.group("spkn")),
            "nsat_gps":     int(match.group("nsat_gps")),
            "nsat_glonass": int(match.group("nsat_glonass")),
        }

        """
        Calculate decimal degrees if requested
        The calculation is based on the formula below
        (https://stackoverflow.com/questions/33997361/how-to-convert-degree-minute-second-to-degree-decimal)

        dd = deg + min/60 + sec/3600

        Keep in mind that the last character (N|S for latitude and W|E for longitude) defines if the decimal degree
        needs to be positive or negative. More info in the link above.
        """
        if decimal_degrees:
            # Calculate latitude
            lat = match.group("lat")
            lat_deg = float(lat[:2])
            lat_min = float(lat[2:-1])
            lat_direction = lat[-1]

            lat_dd = lat_deg + (lat_min/60)
            if lat_direction == "S": # multiply by -1
                lat_dd = lat_dd * -1

            # Calculate longitude
            lon = match.group("lon")
            lon_deg = float(lon[:3])
            lon_min = float(lon[3:-1])
            lon_direction = lon[-1]

            lon_dd = lon_deg + (lon_min/60)
            if lon_direction == "W": # multiply by -1
                lon_dd = lon_dd * -1

            # TODO NV: Maybe round them?
            ret["lat"] = lat_dd
            ret["lon"] = lon_dd

        else:
            ret["lat"] = match.group("lat")
            ret["lon"] = match.group("lon")

        return ret

    def gnss_session(self, status=None, force=False):
        """
        Gets or sets the GNSS session status (i.e. is the dedicated GPS enabled).

        Optional parameters:
        - status (bool): Set this parameter to a boolean to enable or disable the GNSS session.
        - force (bool): Force setting the settings to the modem.
        """

        ret = {}
        res = self.execute("AT$GPSP?")

        res_regex = re.compile("\\$GPSP: (?P<status>[0-1])")
        match = res_regex.match(res.get("data", ""))

        if not match:
            log.error("Didn't receive expected response from modem: {}".format(res))
            raise InvalidResponseException("Didn't receive expected response")

        # NOTE: Have to parse to int first, as any non-empty string will result in a truthy value
        ret["status"] = bool(int(match.group("status")))

        if status != None:
            if type(status) != bool:
                raise TypeError("'status' parameter needs to be of type 'bool'")

            if status != ret["status"] or force:
                self.execute("AT$GPSP={:d}".format(status))
                ret["status"] = status

        return ret

    def gnss_nmea_data_config(self, mode=None, gga=False, gll=False, gsa=False, gsv=False, rmc=False, vtg=False, force=False):
        """
        Gets or sets the NMEA data configuration of the modem.

        Optional arguments:
        - mode (string): One of four available modes: `disabled`, `first_format`, `second_format` or `first_format_lock_port`. The different values are explained
          below. Set this value to `None` (default) to get the current NMEA data configuration.
        - gga (bool): Enables/disables the presence of the Global Positioning System Fix Data NMEA sentence (GGA) in the GNSS data stream.
        - gll (bool): Enable/disable the presence of the Geographic Position - Latitude/Longitude NMEA sentence (GLL) in the GNSS data stream.
        - gsa (bool): Enable/disable the presence of the GNSS DOP and Active Satellites NMEA sentence (GSA) in the GNSS data stream.
        - gsv (bool): Enable/disable the presence of the Satellites in View NMEA sentence (GSV) in the GNSS data stream.
        - rmc (bool): Enable/disable the presence of the Recommended Minimum Specific GNSS Data NMEA sentence (RMC) in the GNSS data stream.
        - vtg (bool): Enable/disable the presence of the GNSS Course Over Ground and Ground Speed NMEA sentence (VTG) in the GNSS data stream.
        - force (bool): Force applying the settings to the modem.

        Available modes:
        - disabled: Disable NMEA data stream.
        - first_format: Enable the first NMEA data stream format.
        - second_format: Enable the second NMEA data stream format.
        - port_lock: Enable the first NMEA data stream format and reserve the interface port only for the NMEA data stream.
        """

        ret = {}
        res = self.execute("AT$GPSNMUN?")

        res_regex = re.compile("^\$GPSNMUN: " + \
                "(?P<mode>[0-3])," + \
                "(?P<gga>[0-1])," + \
                "(?P<gll>[0-1])," + \
                "(?P<gsa>[0-1])," + \
                "(?P<gsv>[0-1])," + \
                "(?P<rmc>[0-1])," + \
                "(?P<vtg>[0-1])"
        )
        match = res_regex.match(res.get("data", ""))

        if not match:
            log.error("Didn't receive expected response from modem: {}".format(res))
            raise InvalidResponseException("Didn't receive expected response")

        # Construct return value
        # NOTE: We need to parse to int first, as any non-empty string will result in a truthy value: bool('0') == True
        ret["mode"] = NMEA_MODE_MAP[int(match.group("mode"))]
        ret["gga"] = bool(int(match.group("gga")))
        ret["gll"] = bool(int(match.group("gll")))
        ret["gsa"] = bool(int(match.group("gsa")))
        ret["gsv"] = bool(int(match.group("gsv")))
        ret["rmc"] = bool(int(match.group("rmc")))
        ret["vtg"] = bool(int(match.group("vtg")))

        if mode != None:
            # Validate mode
            if type(mode) != str or mode not in NMEA_MODE_MAP.values():
                raise ValueError("'mode' argument needs to be one of {}".format(NMEA_MODE_MAP.values()))

            # Validate services
            if type(gga) != bool or \
            type(gll) != bool or \
            type(gsa) != bool or \
            type(gsv) != bool or \
            type(rmc) != bool or \
            type(vtg) != bool:
                raise ValueError("'gga', 'gll', 'gsa', 'gsv', 'rmc' and 'vtg' parameters all need to be of type 'bool'")

            # Determine if we need to execute an extra command
            if ret["mode"] != mode or \
            ret["gga"] != gga or \
            ret["gll"] != gll or \
            ret["gsa"] != gsa or \
            ret["gsv"] != gsv or \
            ret["rmc"] != rmc or \
            ret["vtg"] != vtg or \
            force:
                mode_val = dict_key_by_value(NMEA_MODE_MAP, mode)
                cmd = "AT$GPSNMUN={:d},{:d},{:d},{:d},{:d},{:d},{:d}".format(
                    dict_key_by_value(NMEA_MODE_MAP, mode), bool(gga), bool(gll), bool(gsa), bool(gsv), bool(rmc), bool(vtg))

                if mode_val == NMEA_MODE_PORT_LOCK:
                    res = self.execute(cmd, ready_words=["CONNECT"])
                else:
                    res = self.execute(cmd)

                # Construct return value
                ret["mode"] = mode
                ret["gga"] = bool(gga)
                ret["gll"] = bool(gll)
                ret["gsa"] = bool(gsa)
                ret["gsv"] = bool(gsv)
                ret["rmc"] = bool(rmc)
                ret["vtg"] = bool(vtg)

        return ret

    def nmea_messages(self, timeout=5):
        """
        Read all NMEA messages that have been sent by the modem.

        Optional parameters:
        - timeout (number): The amount of time in seconds to wait for the first message.
          Default 5.
        """

        raw_lines = self.read_lines(timeout)

        if not raw_lines:
            return []

        lines = [ line.strip() for line in raw_lines ]
        return lines

    def send_nmea_escape_sequence(self, wait=False, timeout=3):
        """
        Send NMEA escape sequence to stop unsolicited NMEA messages and unlock
        the ability to send AT commands again.

        Optional parameters:
        - wait (bool): Should the function wait for the modem to send the expected
          response back? If this argument is set to true, the function will
          return all buffered NMEA sentences. Default: False.
        - timeout (number): The amount of time in seconds to wait for the expected
          response. Default 3.
        """

        # Send escape sequence
        self.write("+++")

        if wait:
            # Wait for the port to become available again
            res = self.read_until("NO CARRIER", error_regex, timeout=timeout, echo_on=self._settings.get("echo_on", True))
            return res

    def active_firmware_image(self, net_conf=None, storage_conf=None, force=False, cooldown_delay=20):
        """
        Gets or sets the active firmware configuration on the modem. Don't pass any arguments to query (get) the
        current configuration. If the command results in changing the firmware configuration it will reboot the modem.
        You can specify the `cooldown_delay` parameter to set the amount of time the function waits after the modem
        reboots.

        Optional parameters:
        - net_conf (string): The configuration that the modem should be set to. Check below for available configurations.
          Default: None.
        - storage_conf (string): The storage configuration. As per modem AT command documentation, this is just a dummy
          argument preserved for backwards compatibility. Default: None.
        - force (bool): Force apply the configuration to the modem. Default: False.
        - cooldown_delay (int): How long should this function wait after dropping the connection to the modem.

        Available configurations:
        - att: AT&T
        - verizon: Verizon
        - bell: Bell
        - telus: Telus
        - global: Global
        """

        # NOTE NV: It looks like, as per modem's AT command reference, there is an extra argument available on the
        # command (restore_user_conf). However, while testing this on an LE910C4-WWXD modem, I wasn't able to get that
        # argument to work, it always came back with an error. So, I've ommited it.

        ret = {}
        res = self.execute("AT#FWSWITCH?")

        # Response format:
        # #FWSWITCH: <net_conf>,<storage_conf>
        # #FWSWITCH: <net_conf>,<storage_conf>,<restore_user_conf>??? <- look at note above
        res_regex = re.compile("^#FWSWITCH: (?P<net_conf>[0-9]+),(?P<storage_conf>[0-2])")
        match = res_regex.match(res.get("data", ""))

        if not match:
            log.error("Didn't receive expected response from modem: {}".format(res))
            raise InvalidResponseException("Didn't receive expected response")

        ret["net_conf"] = FW_NET_CONF_MAP[int(match.group("net_conf"))]
        ret["storage_conf"] = FW_STORAGE_CONF_MAP[int(match.group("storage_conf"))]

        if storage_conf != None and net_conf == None:
            raise ValueError("You must set 'net_conf' value if you're also setting 'storage_conf' value")

        if net_conf != None:
            if type(net_conf) != str or net_conf not in FW_NET_CONF_MAP.values():
                raise ValueError("'net_conf' needs to be one of {}".format(FW_NET_CONF_MAP.values()))

            if ret["net_conf"] != net_conf or force:
                net_conf_val = dict_key_by_value(FW_NET_CONF_MAP, net_conf)
                cmd = "AT#FWSWITCH={:d}".format(net_conf_val)
                ret["net_conf"] = net_conf

                # Also decide storage method, although as per AT command spec, this is just a dummy parameter
                if storage_conf != None:
                    # Use passed value
                    if type(storage_conf) != str or storage_conf not in FW_STORAGE_CONF_MAP.values():
                        raise ValueError("'storage_conf' needs to be one of {}".format(FW_STORAGE_CONF_MAP.values()))

                    storage_conf_val = dict_key_by_value(FW_STORAGE_CONF_MAP, storage_conf)
                    cmd = "{},{:d}".format(cmd, storage_conf_val)
                    ret["storage_conf"] = storage_conf

                else:
                    # Otherwise, just use the one set currently
                    cmd = "{},{:d}".format(cmd, int(match.group("storage_conf")))

                # Since the modem will restart, we give up the connection and give it time to reboot
                self.execute(cmd, keep_conn=False, cooldown_delay=cooldown_delay)

        return ret

    def query_sim_status(self):
        """
        Queries for the current SIM status.

        Possible return values:
        - not-inserted
        - inserted
        - inserted-and-pin-unlocked
        - inserted-and-ready
        """


        # NOTE NV: It is possible to setup unsolicited messages (<mode>), however I skipped it for this implementation
        # since we're not listening to those anyways.

        ret = {}
        res = self.execute("AT#QSS?")

        # Response format
        # #QSS: <mode>,<status>
        res_regex = re.compile("^#QSS: (?P<mode>[0-2]),(?P<status>[0-3])")
        match = res_regex.match(res.get("data", ""))

        if not match:
            log.error("Didn't receive expected response from modem: {}".format(res))
            raise InvalidResponseException("Didn't receive expected response")

        ret["status"] = QSS_MAP[int(match.group("status"))]

        return ret

    def generate_regex(self, at_command, params, multiline_identifier):
        """
        Generates a regex with named params for interpreting an AT command response

        Arguments:
        at_command (string): AT command beginning (without proceding ? or =...)
        params (tuple/list of Param objects): ordered parameters expected to be retrieved from the command
        multiline_identifier (MultilineIdentifier object): object to determine which line to read in a multi-line response. None if single line expected.
        """
        rx_string = ''

        # Prepend the identifier to dictionary type
        if multiline_identifier != None and multiline_identifier.multilineType == MULTILINE_TYPES["dictionary"]:
            rx_param_string = ''
            for param in params: 
                rx_param_string = '{},{}'.format(rx_param_string, param.get_named_regex_string())

            rx_string = '^#[A-Z]*: "{}"{}$'.format(multiline_identifier.label.desired_value, rx_param_string)
        
        else:
            for i in range(len(params)): 
                param = params[i]
                if i == 0:
                    rx_param_string = param.get_named_regex_string()
                else:
                    rx_param_string = '{},{}'.format(rx_param_string, param.get_named_regex_string())

            rx_string = '^#[A-Z]*: {}$'.format(rx_param_string)

        return rx_string

    def read_modem_config(self, at_command, params, multiline_identifier=None):
        """
        Reads an AT command based on a given command signature and parameter list/tuple and formats to dictionary

        Arguments:
        at_command (string): AT command beginning (without proceding ? or =...)
        params (tuple/list of Param objects): ordered parameters expected to be retrieved from the command

        Optional arguments:
        multiline_identifier (MultilineIdentifier object): object to determine which line to read in a multi-line response.

        Returns:
        Dictionary formatted as { param.name: param.datatype(value), ... }
        """
        res = self.execute(at_command + '?')
        config_line = ''
        rx_string = ''

        # Find correct string in response data 

        if multiline_identifier == None:
            if not type(res["data"]) == str:
                raise Exception("Got multiple lines in response data, without a specified line identifier")
            config_line = res.get("data")
        else:
            if not type(res["data"]) == list:
                raise Exception("Got single line in response data, when expecting multiple")

            if multiline_identifier.multilineType == MULTILINE_TYPES["array"]:
                index = multiline_identifier.index
                if not multiline_identifier.zero_indexed:
                    index -= 1
                
                config_line = res.get("data")[index]                

            elif multiline_identifier.multilineType == MULTILINE_TYPES["dictionary"]:
                config_line = [line for line in res.get("data") if multiline_identifier.label.desired_value in line][0]
            
        # Compile and match regex string

        rx_string = self.generate_regex(at_command, params, multiline_identifier)
        match = re.match(rx_string, config_line)
        if not match:
            raise Exception('Could not match generated regex')
        match_dict = match.groupdict()

        log.info("Match Dict: {}".format(match_dict))

        # Convert to correct types

        converted_data = {}
        for param in params:
            try:
                retrieved_value = match_dict.get(param.name)
                converted_data[param.name] = param.to_native_datatype_from_AT_string(retrieved_value)  # param.datatype(match_dict.get(param.name))
            except ValueError:
                raise ValueError("Data '{}' for '{}' could not be converted to {}".format(match_dict.get(param.name),
                                 param.name, param.datatype))

        return converted_data

    def update_modem_config(self, at_command, params, current_values, multiline_identifier=None, force=False):
        """
        Updates configs where the current_values do not match the desired ones

        Arguments:
        - at_command (string): AT command beginning (without proceding ? or =...)
        - params (tuple/list of Param objects): ordered parameters expected to be retrieved from the command
        - current_values (dictionary): currently active config values
        - multiline_identifier (MultilineIdentifier object): object to determine which line to read in a multi-line response. None if single line expected.
        - force (bool): Force applying the settings to the modem.
        """
        update_commands = []
        numbered_index = 0
        indexed_index = 0
        base_command = ''

        # Generate the commands necessary to do the update
        if multiline_identifier == None:
            base_command = '{}='.format(at_command)
        elif multiline_identifier.multilineType == MULTILINE_TYPES["dictionary"]:
            base_command = '{}={}'.format(at_command, multiline_identifier.label.get_AT_formatted_named_value())
        elif multiline_identifier.multilineType == MULTILINE_TYPES["array"]:
            base_command = '{}={}'.format(at_command, multiline_identifier.index)

        for i in range(len(params)):
            param = params[i]
            if param.paramtype == PARAM_TYPES['indexed']:

                # Handle first comma not being needed on first param
                if indexed_index == 0 and multiline_identifier == None:
                    base_command = '{}{}'.format(base_command, param.get_AT_formatted_named_value())
                else:
                    base_command = '{},{}'.format(base_command, param.get_AT_formatted_named_value())

                # Ensure indexed configs are all updated at once
                if len(update_commands) > 0:
                    update_commands[0] = base_command

                # Ensure config is updated when there are no numbered params to update.
                elif current_values.get(param.name) != param.desired_value or len(update_commands) > 0 or force:
                    update_commands.append(base_command)
                
                indexed_index += 1
                
            elif param.paramtype == PARAM_TYPES['numbered']:
                if current_values.get(param.name) != param.desired_value or force:
                    update_commands.append('{},{},{}'.format(base_command, numbered_index, param.get_AT_formatted_named_value()))

                numbered_index += 1
            
        for cmd in update_commands:
            self.execute(cmd)

    def is_update_requested_raise_on_error(self, params):
        """
        Check if an update has been requested based on parameter list's/tuple's desired values
        """
        has_none_type = False
        has_value_type = False

        for param in params:
            if param.paramtype != PARAM_TYPES["indexed_readonly"]:
                if param.desired_value == None:
                    has_none_type = True
                else:
                    has_value_type = True

        if has_value_type and has_none_type:
            raise ValueError('All params are required when updating: {}'.format([param.name
                             + ': ' + str(param.datatype) for param in
                             params]))

        return has_value_type

    def query(self, at_command, params, confirm=False, force=False, multiline_identifier=None):
        """
        Query given AT command. If params have desired_values and they don't match the real data, update the modem config.

        Arguments:
        - at_command (string): AT command beginning (without proceding ? or =...)
        - params (tuple/list of Param objects): ordered parameters expected to be retrieved from the command
        - multiline_identifier (MultilineIdentifier object): object to determine which line to read in a multi-line response. None if single line expected.
        - confirm (bool): confirm updates
        - force (bool): Force applying the settings to the modem.
        """
        ret = {}

        update = self.is_update_requested_raise_on_error(params)

        if update and not confirm:
            raise Exception("This command will modify configuration directly on the Modem - add parameter 'confirm=true' to continue anyway.")

        current_data = self.read_modem_config(at_command, params, multiline_identifier=multiline_identifier)

        if update:
            update_res = self.update_modem_config(at_command, params, current_data, multiline_identifier=multiline_identifier)
            ret['data'] = self.read_modem_config(at_command, params, multiline_identifier=multiline_identifier)
        else:
            ret['data'] = current_data

        return ret


    def evmoni_smsin_config(self, enabled=None, command=None, match_content=None, confirm=False, force=False):
        """
        Sets the configuration of sms received event

        Arguments:
        - enabled (bool):  Enables/disables the SMSIN event monitor
        - command (str): AT command that gets run on received SMS
        - match_content (str): text that has to be matched in the SMS. Empty string for no match
        - confirm (bool): confirm updates
        - force (bool): Force applying the settings to the modem.
        """
        params = (
            Param('enabled', PARAM_TYPES['indexed'], bool, enabled), 
            Param('command', PARAM_TYPES['numbered'], str, command), 
            Param('match_content',PARAM_TYPES['numbered'], str, match_content)
        )

        idfr = MultilineIdentifier(
            MULTILINE_TYPES["dictionary"], 
            label=Param('label', PARAM_TYPES['indexed'], str, "SMSIN")
        )

        res = self.query('AT#EVMONI', params, multiline_identifier=idfr, confirm=confirm, force=force)

        return res


    def evmoni_gpio_config(self, peripheral_num, enabled=None, command=None, gpio_pin=None, watch_status=None, delay=None, confirm=False, force=False):
        """
        Sets the configuration of gpio change event

        Required arguments:
        - peripheral_num (int): number of the GPIO peripheral to update

        Optional Arguments:
        - enabled (bool):  Enables/disables the GPIOX event monitor
        - command (str): AT command that gets run on event match
        - gpio_pin (int): gpio pin on which to listen for the change
        - watch_status (bool): watch for rising edge (true) or falling edge (false)
        - delay (int): how many seconds after triggering will the command be executed
        - confirm (bool): confirm updates
        - force (bool): Force applying the settings to the modem.
        """
        params = (
            Param('enabled', PARAM_TYPES['indexed'], bool, enabled), 
            Param('command', PARAM_TYPES['numbered'], str, command), 
            Param('gpio_pin',PARAM_TYPES['numbered'], int, gpio_pin),
            Param('watch_status', PARAM_TYPES['numbered'], bool, watch_status),
            Param('delay', PARAM_TYPES['numbered'], int, delay)
        )

        label = "GPIO" + str(peripheral_num)
        idfr = MultilineIdentifier(
            MULTILINE_TYPES["dictionary"], 
            label=Param('label', PARAM_TYPES['indexed'], str, label)
        )

        res = self.query('AT#EVMONI', params, multiline_identifier=idfr, confirm=confirm, force=force)

        return res

    def evmoni_enabled(self, enabled=None, confirm=False, force=False):
        """
        Sets the configuration of gpio change event
        
        Optional Arguments:
        - enabled (bool):  Enables/disables the event monitor
        - confirm (bool): confirm updates
        - force (bool): Force applying the settings to the modem.
        """
        params = (
            Param("mode", PARAM_TYPES['indexed_readonly'], bool, None),
            Param("status", PARAM_TYPES['indexed'], bool, enabled)
        )

        res = self.query("AT#ENAEVMONI", params, confirm=confirm, force=force)

        return res

    def evmoni_config(self, instance=None, timeout=None, urcmod=None, confirm=False, force=False):
        """
        Configures the event monitor
        
        Optional Arguments:
        - instance (int): AT instance used by the service to run the AT command (1-3)
        - urcmod (bool): enable/disable unsolicited message
        - timeout (int): timeout in minutes for AT command execution
        - confirm (bool): confirm updates
        - force (bool): Force applying the settings to the modem.
        """
        params = (
            Param("instance", PARAM_TYPES["indexed"], int, instance),
            Param("urcmod", PARAM_TYPES["indexed"], bool, urcmod),
            Param("timeout", PARAM_TYPES["indexed"], int, timeout)
        )

        res = self.query("AT#ENAEVMONICFG", params, confirm=confirm, force=force)

        return res


class MultilineIdentifier:
    def __init__(self, multilineType, index=None, label=None, zero_indexed=True):
        if multilineType not in MULTILINE_TYPES.values():
            raise ValueError("Type must be one of (MULTILINE_TYPES.values)")
        
        if multilineType == MULTILINE_TYPES["dictionary"]:
            if not isinstance(label, Param):
                raise ValueError("Dictionary identifier must have a label of type <Param>")
            self.label = label

        elif multilineType == MULTILINE_TYPES["array"]:
            if not isinstance(index, int):
                raise ValueError("Array identifier must have an index of type <int>")
            self.index = index
            self.zero_indexed = zero_indexed

        self.multilineType = multilineType


class Param:
    def __init__(self, name, paramtype, datatype, desired_value, value_map=None):
        if datatype not in SUPPORTED_DATATYPES:
            raise ValueError('Unsupported type. Supported types: {}'.format(SUPPORTED_DATATYPES))

        if desired_value != None and type(desired_value) != datatype:
            raise ValueError("Provided type's ({}) and expected value's types ({}) don't match for {}".format(datatype, type(desired_value), name))

        self.datatype = datatype
        self.desired_value = desired_value
        self.name = name
        self.paramtype = paramtype

    def to_native_datatype_from_AT_string(self, value):
        if type(value) == str:
            if self.datatype == str:
                return value
            elif self.datatype == bool:
                return bool(int(value))
            elif self.datatype == int:
                return int(value)
        else:
            raise Exception("Can not convert to native type of {} from {}".format(type(value), self.datatype))

    def get_named_regex_string(self):
        if self.datatype == str:
            return '"(?P<{}>[^"]*)"'.format(self.name)
        elif self.datatype == bool:
            return '(?P<{}>[0-1])'.format(self.name)
        elif self.datatype == int:
            return '(?P<{}>[0-9]*)'.format(self.name)

    def get_AT_formatted_named_value(self):
        if self.datatype == str:
            if self.desired_value == None:
                raise Exception('Can not format None to <str>')

            return '"{}"'.format(self.desired_value)

        elif self.datatype == bool:
            if self.desired_value == None:
                raise Exception('Can not format None to <bool>')

            return str(int(self.desired_value))

        elif self.datatype == int:
            if self.desired_value == None:
                raise Exception('Can not format None to <int>')

            return str(self.desired_value)

    











    # def sms_wake_enabled(self, enabled=None, confirm=False, force=False):
    #     ret = {}

    #     smsin_config_data = self.evmoni_smsin_config().get("data")
    #     gpio_config_data = self.evmoni_gpio_config(1).get("data")
    #     evmoni_enabled_data = self.evmoni_config().get("data")  

    #     if force:
    #         self.evmoni_enabled(enabled=False, confirm=confirm, force=force)
    #         self.evmoni_config(instance=3, urcmod=1, timeout=5, confirm=confirm, force=force)
    #         self.evmoni_smsin_config(enabled=True, command="AT#GPIO=3,1,1", content_match="", confirm=confirm, force=force)
    #         self.evmoni_gpio_config(1, enabled=True, command="AT#GPIO=3,0,1", gpio_pin=3, watch_status=True, confirm=confirm, force=force)
    #         self.evmoni_enabled(enabled=True, confirm=confirm, force=force)

    #     return ret

    # EVMONI_LABEL_GPIO1      = "GPIO1"
    # EVMONI_LABEL_GPIO2      = "GPIO2"
    # EVMONI_LABEL_GPIO3      = "GPIO3"
    # EVMONI_LABEL_GPIO4      = "GPIO4"
    # EVMONI_LABEL_GPIO5      = "GPIO5"
    # EVMONI_LABEL_SMSIN      = "SMSIN"

    # EVMONI_LABEL_LIST = [
    #     EVMONI_LABEL_GPIO1,
    #     EVMONI_LABEL_GPIO2,
    #     EVMONI_LABEL_GPIO3,
    #     EVMONI_LABEL_GPIO4,
    #     EVMONI_LABEL_GPIO5,
    #     EVMONI_LABEL_SMSIN,
    # ]

    # def update_test(self, enabled=None):
    #     params = (
    #         Param("mode", PARAM_TYPES['indexed_readonly'], bool, None),
    #         Param("status", PARAM_TYPES['indexed'], bool, enabled)
    #     )
    #     res = self.read_modem_config("AT#ENAEVMONI", params)
    #     # res = self.read_modem_config("AT#EVMONI")

    #     log.info("Current Result: {}".format(res))

    #     self.update_modem_config("AT#ENAEVMONI", params, res)
    
    #     res = self.read_modem_config("AT#ENAEVMONI", params)

    #     log.info("Updated Result: {}".format(res))

    #     return res

    # def gpio(self, gpio_pin, direction=None, mode=None, confirm=False, force=False):
    #     ret = {}

    #     if gpio_pin < 1 or gpio_pin > 10:
    #         raise ValueError("GPIOs indexed from 1 to 10")
        
    #     param_mode = Param("mode", PARAM_TYPES["indexed"], int, mode)
    #     param_direction = Param("direction", PARAM_TYPES["indexed"], int, direction)
    #     param_save = Param("save", PARAM_TYPES["indexed"], bool, True)
    #     param_state = Param("state", PARAM_TYPES["indexed"], bool, None)

    #     GPIO_DIR_IN = 0
    #     GPIO_DIR_OUT = 1
        
    #     GPIO_MODE_OUT_LOW = 0
    #     GPIO_MODE_OUT_HIGH = 1


    #     # The GPIO command used a different parameter order for reads and writes
    #     read_params = (
    #         param_direction,
    #         param_state,
    #     )
    #     write_params = (
    #         param_mode,
    #         param_direction,    
    #         param_save
    #     )

    #     idfr = MultilineIdentifier(MULTILINE_TYPES["array"], index=gpio_pin, zero_indexed=False)

    #     read_res = self.read_modem_config("AT#GPIO", read_params, multiline_identifier=idfr)

    #     update = False
    #     if (direction != read_res.get("direction") or mode != read_res.get("state")) and (direction != None or mode != None):
    #         if direction == None or mode == None:
    #             raise ValueError("Both direction (IN/OUT) and mode (LOW/HIGH) are required")
    #         if not confirm:
    #             raise Exception("This command will modify configuration directly on the Modem - add parameter 'confirm=true' to continue anyway.")

    #         self.update_modem_config("AT#GPIO", write_params, read_res, multiline_identifier=idfr, force=force)

    #         ret["data"] = self.read_modem_config("AT#GPIO", read_params, multiline_identifier=idfr)

    #     else:
    #         ret["data"] = read_res

    #     return ret


    # def read_simple_config(self, at_command, params):
    #     res = self.execute(at_command + '?')

    #     rx_param_string = ''


    #     # Compile and match regex string

    #     match = re.match(rx_string, res["data"])
    #     if not match:
    #         raise Exception('Could not match generated regex')
    #     match_dict = match.groupdict()

    #     log.info("Match Dict: {}".format(match_dict))

    #     # Convert to correct types

    #     converted_data = {}
    #     for param in params:
    #         try:
    #             retrieved_value = match_dict.get(param.name)
    #             converted_data[param.name] = param.to_native_datatype_from_AT_string(retrieved_value)  # param.datatype(match_dict.get(param.name))
    #         except ValueError:
    #             raise ValueError("Data '{}' for '{}' could not be converted to {}".format(match_dict.get(param.name),
    #                              param.name, param.datatype))
        
    #     log.info("Converted Dict: {}".format(converted_data))

    #     return converted_data



    # def read_nested_config(self, at_command, config_label, params):
    #     res = self.execute(at_command + '?')

    #     matched_line = [line for line in res['data'] if config_label in line][0]

    #     log.info("Line: {}".format(matched_line))

    #     # Build regex string

    #     rx_param_string = ''
    #     for param in params: 
    #         rx_param_string = '{},{}'.format(rx_param_string, param.get_named_regex_string())

    #     rx_string = '^#[A-Z]*: "{}"{}$'.format(config_label,
    #             rx_param_string)

    #     log.info("Rx string: {}".format(rx_string))

    #     # Compile and match regex string

    #     match = re.match(rx_string, matched_line)
    #     if not match:
    #         raise Exception('Could not match generated regex')
    #     match_dict = match.groupdict()

    #     log.info("Match Dict: {}".format(match_dict))

    #     # Convert to correct types

    #     converted_data = {}
    #     for param in params:
    #         try:
    #             retrieved_value = match_dict.get(param.name)
    #             converted_data[param.name] = param.to_native_datatype_from_AT_string(retrieved_value)  # param.datatype(match_dict.get(param.name))
    #         except ValueError:
    #             raise ValueError("Data '{}' for '{}' could not be converted to {}".format(match_dict.get(param.name),
    #                              param.name, param.datatype))
        
    #     log.info("Converted Dict: {}".format(converted_data))

    #     return converted_data



    # def nested_config(self, at_command, config_label, params, confirm=False, force=False):
    #     ret = {}

    #     update = self.is_update_requested_raise_on_error(params)

    #     current_data = self.read_nested_config(at_command,
    #             config_label, params)

    #     if update:
    #         update_res = self.update_nested(at_command,
    #                 config_label, params, current_data)

    #         # TODO EP: Check if succeeded

    #         ret['data'] = self.read_nested_config(at_command,
    #                 config_label, params)
    #     else:
    #         ret['data'] = current_data

    #     return ret


    # def update_nested(self, at_command, config_label, params, current_values, force=False):
    #     update_commands = []
    #     numbered_index = 0
    #     base_command = '{}="{}"'.format(at_command, config_label)

    #     for param in params:
    #         if param.paramtype == PARAM_TYPES['indexed']:
    #             base_command = '{},{}'.format(base_command,
    #                     param.get_AT_formatted_named_value())

    #     # Ran to ensure value is updated even when numbered values are not updated

    #             if current_values.get(param.name) \
    #                 != param.desired_value or force:
    #                 update_commands.append(base_command)
    #         elif param.paramtype == PARAM_TYPES['numbered']:

    #             if current_values.get(param.name) \
    #                 != param.desired_value or force:
    #                 update_commands.append('{},{},{}'.format(base_command,
    #                         numbered_index,
    #                         param.get_AT_formatted_named_value()))

    #             numbered_index += 1

    #     for cmd in update_commands:
    #         self.execute(cmd)




    # def evmoni_config(self, config_label, *args, **kwargs):
    #     force = kwargs.get("force", False)
    #     confirm = kwargs.get("confirm", False)

    #     ret = {}
    #     ret["label"] = config_label
        
    #     at_command = "AT#EVMONI"

    #     # Query command
    #     # response = {'data': ['#EVMONI: "VBATT",0,"",0,0', '#EVMONI: "DTR",0,"",0,0', '#EVMONI: "ROAM",0,""', '#EVMONI: "CONTDEACT",0,""', '#EVMONI: "RING",0,"",1', '#EVMONI: "STARTUP",0,""', '#EVMONI: "REGISTERED",0,""', '#EVMONI: "GPIO1",0,"",1,0,0', '#EVMONI: "GPIO2",0,"",1,0,0', '#EVMONI: "GPIO3",0,"",1,0,0', '#EVMONI: "GPIO4",0,"",1,0,0', '#EVMONI: "GPIO5",0,"",1,0,0', '#EVMONI: "ADCH1",0,"",1,0,0', '#EVMONI: "ADCL1",0,"",1,0,0', '#EVMONI: "DTMF1",0,"","",1000', '#EVMONI: "DTMF2",0,"","",1000', '#EVMONI: "DTMF3",0,"","",1000', '#EVMONI: "DTMF4",0,"","",1000', '#EVMONI: "SMSIN",0,"AT#GPIO=3,1,1",""']}
    #     response = self.execute("AT#EVMONI?")

    #     # TODO: handle error

    #     log.info("CURRENT. Retrieved {:} total lines".format(len(response["data"])))
    #     log.info(response)

    #     # Find the line matching the config label
    #     config_lines = [line for line in response["data"] if config_label in line]
    #     if len(config_lines) != 1:
    #         raise Exception("Got unexpected number of lines from modem that match the label")
    #     config_line = config_lines[0]

    #     log.info("Matched {:} lines".format(len(config_lines)))
    #     log.info(config_line)
        

    #     # Processing for the SMSIN label
    #     if (config_label == EVMONI_LABEL_SMSIN):
    #         res_regex = re.compile('^#EVMONI: "{:}",(?P<enabled>[0-1]),"(?P<command>[^"]*)","(?P<content_match>[^"]*)"$'.format(config_label))
            
    #         # response_values = res_regex.match(config_lines[0], "").groupdict()
    #         match = res_regex.match(config_line)
    #         if not match:
    #             log.info("Didn't receive expected response from modem: {}".format(response))
    #             # raise InvalidResponseException("Didn't receive expected response")
    #             raise Exception("Didn't receive expected response")

    #         log.info("Response values: {}".format(match.groupdict()))

    #         # Convert to correct types
    #         ret["enabled"] = bool(int(match.group("enabled")))
    #         ret["content_match"] = str(match.group("content_match"))
    #         ret["command"] = str(match.group("command"))

    #         desired_enabled = kwargs.get("enabled", False)
    #         desired_content_match = kwargs.get("content_match", None)
    #         desired_command = kwargs.get("command", None)

    #         if desired_enabled != False \
    #                 or desired_content_match != None \
    #                 or desired_command != None:

    #             if type(desired_enabled) != bool \
    #                     or type(desired_content_match) != str \
    #                     or type(desired_command) != str:
    #                 raise ValueError("Parameters need to be of types:\t enabled: bool, content_match: str, command: str")

    #             if ret["enabled"] != desired_enabled \
    #                     or ret["content_match"] != desired_content_match \
    #                     or ret["command"] != desired_command \
    #                     or force:

    #                 commands = (
    #                     'AT#EVMONI="{:s}",{:d},{:d},"{:s}"'.format(config_label,desired_enabled,0,desired_command),
    #                     'AT#EVMONI="{:s}",{:d},{:d},"{:s}"'.format(config_label,desired_enabled,1,desired_content_match)
    #                 )
    #                 for command in commands:
    #                     log.info(command)
    #                     config_cmd_response = self.execute(command)

    #                 ret = self.evmoni_config(config_label)

    #     return ret



    # def evmoni_config(self, config_label, *args, **kwargs):

    #     at_command = "AT#EVMONI"

    #     # Query command
    #     response = self.execute(at_command + "?")

    #     # TODO: handle error

    #     log.info("CURRENT. Retrieved {:} total lines".format(len(response["data"])))
    #     log.info(response)

    #     # Find the line matching the config label
    #     matched_lines = [line for line in response["data"] if config_label in line]

    #     log.info("CURRENT. Matched {:} lines".format(len(matched_lines)))
    #     log.info(matched_lines)
        
    #     if len(matched_lines) != 1:
    #         raise Exception("Got unexpected number of lines from modem that match the label")
        
    #     if (config_label == EVMONI_LABEL_SMSIN):
    #         res_regex = re.compile('^#EVMONI: {:},(?P<enabled>[0-1]),(?P<command>"[^"]*"),(?P<content_match>"[^"]*")$'.format(config_label))
    #         response_values = res_regex.match(response.get["data"], "").groupdict()

    #         for (name, value) in response_values.items():
    #             expected_value = kwargs.get(name)
    #             if expected_value == None:
    #                 raise "Kwarg '{}' is required".format(name)

    #     if config_label == EVMONI_LABEL_GPIO1 
    #         || config_label == EVMONI_LABEL_GPIO2 
    #         || config_label == EVMONI_LABEL_GPIO3 
    #         || config_label == EVMONI_LABEL_GPIO4 
    #         || config_label == EVMONI_LABEL_GPIO5:
    #         res_regex = re.compile('^#EVMONI: {:},(?P<enabled>[0-1]),(?P<command>"[^"]*"),(?P<gpio_pin>[0-9]+),(?P<stat>[0-1])$'.format(config_label))
    #         values = res_regex.match(response.get["data"], "").groupdict()
        
    #     param_values = matched_lines[0].split(": ")[1].split(",")[1:]

    #     log.info(param_values)
    #     log.info("Number of args: {}".format(len(args)))
    #     log.info("Args: {}".format(args))

    #     if len(args) != 0:  
    #         log.info("Updating value")

    #         if len(args) != len(param_values):
    #             raise Exception("Argument count does not match the one returned by command.")

    #         formatted_args = []
    #         match = True
    #         for i in range(len(args)):

    #             if isinstance(args[i], str):
    #                 log.info("{} string".format(args[i]))
    #                 formatted_args.append('"{}"'.format(args[i]))
    #             else:
    #                 log.info("{} not String".format(args[i]))
    #                 formatted_args.append(args[i])

    #             if args[i] != param_values[i]:
    #                 log.info("Mismatch on arg {} ({} != {})".format(i, formatted_args[i], param_values[i]))
    #                 match = False

    #         log.info("Args after formatting: {}".format(formatted_args)) 

    #         if not match:
    #             # Construct the command
    #             command = "{}={}".format(at_command, '"{}"'.format(config_label))

    #             for arg in formatted_args:
    #                 log.info("Adding config {}".format(arg))
    #                 command = command + ",{}".format(arg)
 
    #             log.info("Constructed command '{}'".format(command))
    #             update_response = self.execute(command)

    #             log.info(update_response)

        

            



        # If len of args > 0
        # Comapare each value in sequence of comma_seperated_values

        # If don't match, update with at_command=config_label,*args 

        # return param_values

        # return ("GPIO1", 1, 0, 40, "AT#GPIO=1,1,1")





    # def evmoni_config(label, command=None, enabled=None):
    

        
        
    #     if len(matched_lines) != 1:
    #         raise Exception("Got unexpected number of lines from modem that match the label")

    #     line = matched_lines[0]


    #     for line in res_lines:
    #         res_regex = re.compile("^#EVMONI: (?P<mode>[0-1])(?P<stat>[0-1])f?$")


    #     None


    # def evmoni_enabled(self, value):
    #     res = self.execute("AT#ENAEVMONI")

    #     res_regex = res_regex = re.compile("^#ENAEVMONI: (?P<mode>[0-1])(?P<stat>[0-1])?$")
    #     mode = res_regex.match(res.get("mode", ""))
    #     stat = res_regex.match(res.get("stat", ""))

    #     if mode == 0


    # AT#ENAEVMONI=0
    # AT#GPIO=3,0,1
    # AT#ENAEVMONICFG=3,1,2
    # AT#EVMONI="SMSIN",0,1,""     (Text to match for event trigger (empty brackets = doesn't care about text))
    # AT#EVMONI="SMSIN",0,0,"AT#GPIO=3,1,1"    (command to execute when SMS arrives)
    # AT#EVMONI="SMSIN",1
    # AT#EVMONI="GPIO1",1,1,3    (GPIO #3)
    # AT#EVMONI="GPIO1",1,2,1    (monitor GPIO #3 for HIGH)
    # AT#EVMONI="GPIO1",1,3,1    (last number is how many seconds to activate the pin for)
    # AT#EVMONI="GPIO1",1,0,"AT#GPIO=3,0,1"    (Command that's executed a specified time after GPIO 3 goes high)
    # AT#EVMONI="GPIO1",1
    # AT#ENAEVMONI=1
