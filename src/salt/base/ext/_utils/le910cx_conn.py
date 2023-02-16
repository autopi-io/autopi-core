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


class LE910CXWarning(Warning):
    pass


class NoFixWarning(LE910CXWarning):
    """
    NoFixWarning is only a warning because it's an expected behavior from the modem. It can very often be the
    case that the modem doesn't have a fix. Warnings are handled differently than Exceptions in Core.
    """

    def __init__(self, message="No fix"):
        self.message = message
        super(NoFixWarning, self).__init__(message)


class InvalidResponseException(LE910CXException):
    pass


class CommandExecutionException(LE910CXException):
    pass


class NoSimPresentWarning(LE910CXWarning):
    """
    NoSimPresentWarning is only a warning because it's an expected behavior from the modem. Customers can decide if
    they are going to have SIMs inserted.
    """

    def __init__(self, message="No SIM present"):
        self.message = message
        super(NoSimPresentWarning, self).__init__(message)


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

CGDCONT_PDP_TYPE_IP     = "IP"
CGDCONT_PDP_TYPE_PPP    = "PPP"
CGDCONT_PDP_TYPE_IPV6   = "IPV6"
CGDCONT_PDP_TYPE_IPV4V6 = "IPV4V6"

CGDCONT_PDP_TYPE_MAP = {
    CGDCONT_PDP_TYPE_IP:     "ip",
    CGDCONT_PDP_TYPE_PPP:    "ppp",
    CGDCONT_PDP_TYPE_IPV6:   "ipv6",
    CGDCONT_PDP_TYPE_IPV4V6: "ipv4v6",
}

SUPPORTED_DATATYPES = (bool, int, str)
PARAM_TYPES = {'rdInline_wrInline': 1, 'inline_readonly': 2, 'rdInline_wrIndexed': 3}
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
            raise NoSimPresentWarning()

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
            raise NoFixWarning()

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

    def pdp_context(self, cid=None, pdp_type=None, apn=None, delete_cid=False, force=False):
        """
        Optional parameters:
          - cid (number): The context ID to change. Default: None.
          - pdp_type (string): The type of the PDP context. Check available options below. Default: None.
          - apn (string): The APN to be set on the context cid. Default: None.
          - delete_cid (bool): Should the cid be unset? Default: False.
          - force (bool): Force set the parameters, even if they have already been set. Default: False.

        pdp_types:
          - "ip": Internet Protocol
          - "ppp": Point to Point Protocol
          - "ipv6": Internet Protocol, Version 6
          - "ipv4v6" (default): Virtual <PDP_type> introduced to handle dual IP stack UE capability
        """

        # First check if the SIM is present
        sim_status = self.query_sim_status()
        if sim_status["status"] == QSS_MAP[QSS_STATUS_NOT_INSERTED]:
            raise NoSimPresentWarning()

        ret = []
        res = self.execute("AT+CGDCONT?")

        # Response format
        # +CGDCONT: <cid>,<PDP_type>,<APN>,<PDP_addr>,<d_comp>,<h_comp>,<IPv4AddrAlloc>,<Emergency_ind><CR><LF>[...]

        # Example response:
        # +CGDCONT: 1,"IPV4V6","","",0,0,0,0
        # +CGDCONT: 2,"IPV4V6","ims","",0,0,0,0

        # Example response:
        # +CGDCONT: 1,"IPV4V6","","",0,0,0,0

        # Prepare response data to be processed
        res_data = [] # Allocate
        if type(res.get("data")) == str: # Single line res
            res_data = [res.get("data", "")]
        elif type(res.get("data")) == list: # Multiple line res
            res_data = res.get("data", [])
        else: # Invalid response?
            log.error("Didn't receive expected response from modem: {}".format(res))
            raise InvalidResponseException("Didn't receive expected response")

        # Process response data
        res_regex = re.compile("^\+CGDCONT: " + \
            "(?P<cid>[0-9]+)," + \
            "\"(?P<pdp_type>[a-zA-Z0-9]+)\"," + \
            "\"(?P<apn>[a-zA-Z0-9\.-]+)?\"," + \
            "\"(?P<pdp_addr>[a-zA-Z0-9]+)?\"," + \
            "(?P<d_comp>[0-9])," + \
            "(?P<h_comp>[0-9])," + \
            "(?P<ipv4addralloc>[0-9])," + \
            "(?P<emergency_ind>[0-9])"
        )

        # Construct
        for line in res_data:
            match = res_regex.match(line)

            if not match:
                log.error("Didn't receive expected response from modem: {}".format(res))
                raise InvalidResponseException("Didn't receive expected response")

            ret.append({
                "cid": int(match.group("cid")),
                "pdp_type": match.group("pdp_type"),
                "apn": match.group("apn") if match.group("apn") else "",
                #"pdp_addr": match.group("pdp_addr") if match.group("pdp_addr") else "", # Not implemented
                #"d_comp": int(match.group("d_comp")), # Not implemented
                #"h_comp": int(match.group("h_comp")), # Not implemented
                #"ipv4addralloc": int(match.group("ipv4addralloc")), # Not implemented
                #"emergency_ind": int(match.group("emergency_ind")), # Not implemented
            })

        # Make any changes if necessary
        if cid != None:
            if type(cid) != int:
                raise ValueError("'cid' argument needs to be a number")

            # Find the pdp_entry that the cid references
            pdp_entry = None
            for entry in ret:
                if entry["cid"] == cid:
                    pdp_entry = entry
                    break

            if pdp_entry: # PDP already exists
                if delete_cid == True: # User wants to unset this CID
                    if log.isEnabledFor(logging.DEBUG):
                        log.debug("Going to unset cid {}".format(cid))
                    self.execute("AT+CGDCONT={:d}".format(cid))
                    ret = [pdp_entry for pdp_entry in ret if pdp_entry["cid"] != cid]

                else: # User wants to change the pdp context
                    if pdp_type == None or apn == None:
                        raise ValueError("Both 'pdp_type' and 'apn' arguments needs to be set when changing an existing PDP context")

                    if pdp_entry["pdp_type"] != pdp_type or pdp_entry["apn"] != apn or force:
                        # Difference in PDP, set it
                        if type(pdp_type) != str or pdp_type not in CGDCONT_PDP_TYPE_MAP.values():
                            raise ValueError("'pdp_type' needs to be one of {}".format(CGDCONT_PDP_TYPE_MAP.values()))

                        pdp_type_val = dict_key_by_value(CGDCONT_PDP_TYPE_MAP, pdp_type)
                        if log.isEnabledFor(logging.DEBUG):
                            log.debug("Going to change a PDP context. CID: {}, new pdp_type: {}, new apn: {}".format(cid, pdp_type_val, apn))
                        self.execute("AT+CGDCONT={:d},\"{:s}\",\"{:s}\"".format(cid, pdp_type_val, apn))

                        new_pdp_context = {
                            "cid": cid,
                            "pdp_type": pdp_type,
                            "apn": apn,
                            #"pdp_addr": "",
                            #"d_comp": 0, # Not implemented
                            #"h_comp": 0, # Not implemented
                            #"ipv4addralloc": 0, # Not implemented
                            #"emergency_ind": 0, # Not implemented
                        }

                        ret = [ new_pdp_context if pdp_context["cid"] == cid else pdp_context for pdp_context in ret ]

            else: # PDP doesn't exist
                if delete_cid == True:
                    if log.isEnabledFor(logging.DEBUG):
                        log.debug("CID {} already doesn't exist. Noop due to delete_cid == {}".format(cid, delete_cid))
                    return ret

                if pdp_type == None or apn == None:
                    raise ValueError("cid {} doesn't exist. Both 'pdp_type' and 'apn' arguments needs to be set when defining a new PDP context".format(cid))

                if type(pdp_type) != str or pdp_type not in CGDCONT_PDP_TYPE_MAP.values():
                    raise ValueError("'pdp_type' needs to be one of {}".format(CGDCONT_PDP_TYPE_MAP.values()))

                pdp_type_val = dict_key_by_value(CGDCONT_PDP_TYPE_MAP, pdp_type)
                if log.isEnabledFor(logging.DEBUG):
                    log.debug("Going to set new PDP context. CID: {}, new pdp_type: {}, new apn: {}".format(cid, pdp_type_val, apn))
                self.execute("AT+CGDCONT={:d},\"{}\",\"{}\"".format(cid, pdp_type_val, apn))

                ret.append({
                    "cid": cid, # already ensured to be an int
                    "pdp_type": pdp_type,
                    "apn": apn,
                    #"pdp_addr": "",
                    #"d_comp": 0, # Not implemented
                    #"h_comp": 0, # Not implemented
                    #"ipv4addralloc": 0, # Not implemented
                    #"emergency_ind": 0, # Not implemented
                })

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
        indexed_index = 0
        inline_index = 0
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
            if param.paramtype == PARAM_TYPES['rdInline_wrInline']:

                # Handle first comma not being needed on first param
                if inline_index == 0 and multiline_identifier == None:
                    base_command = '{}{}'.format(base_command, param.get_AT_formatted_named_value())
                else:
                    base_command = '{},{}'.format(base_command, param.get_AT_formatted_named_value())

                # Ensure inline configs are all updated at once
                if len(update_commands) > 0:
                    update_commands[0] = base_command

                # Ensure config is updated when there are no rdInline_wrIndexed params to update.
                elif current_values.get(param.name) != param.desired_value or len(update_commands) > 0 or force:
                    update_commands.append(base_command)
                
                inline_index += 1
                
            elif param.paramtype == PARAM_TYPES['rdInline_wrIndexed']:
                if current_values.get(param.name) != param.desired_value or force:
                    update_commands.append('{},{},{}'.format(base_command, indexed_index, param.get_AT_formatted_named_value()))

                indexed_index += 1
            
        for cmd in update_commands:
            self.execute(cmd)

    def is_update_requested_raise_on_error(self, params):
        """
        Check if an update has been requested based on parameter list's/tuple's desired values
        """
        has_none_type = False
        has_value_type = False

        for param in params:
            if param.paramtype != PARAM_TYPES["inline_readonly"]:
                if param.desired_value == None:
                    has_none_type = True
                else:
                    has_value_type = True

        if has_value_type and has_none_type:
            raise ValueError('All params are required when updating: {}'.format([param.name
                             + ': ' + str(param.datatype) for param in
                             params]))

        return has_value_type

    def query(self, at_command, params, confirm=False, force=False, multiline_identifier=None, pre_update_task=None, post_update_task=None):
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
            if pre_update_task:
                pre_update_task()

            self.update_modem_config(at_command, params, current_data, multiline_identifier=multiline_identifier, force=force)

            if post_update_task:
                post_update_task()

            ret = self.read_modem_config(at_command, params, multiline_identifier=multiline_identifier)
        else:
            ret = current_data

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
            Param('enabled', PARAM_TYPES['rdInline_wrInline'], bool, enabled), 
            Param('command', PARAM_TYPES['rdInline_wrIndexed'], str, command), 
            Param('match_content',PARAM_TYPES['rdInline_wrIndexed'], str, match_content)
        )

        idfr = MultilineIdentifier(
            MULTILINE_TYPES["dictionary"], 
            label=Param('label', PARAM_TYPES['rdInline_wrInline'], str, "SMSIN")
        )

        res = self.query(
            'AT#EVMONI', 
            params, 
            multiline_identifier=idfr, 
            confirm=confirm, 
            force=force,
            pre_update_task=lambda : self.evmoni_enabled(enabled=False, confirm=confirm, force=force),
            post_update_task=lambda : self.evmoni_enabled(enabled=True, confirm=confirm, force=force)
        )

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
            Param('enabled', PARAM_TYPES['rdInline_wrInline'], bool, enabled), 
            Param('command', PARAM_TYPES['rdInline_wrIndexed'], str, command), 
            Param('gpio_pin',PARAM_TYPES['rdInline_wrIndexed'], int, gpio_pin),
            Param('watch_status', PARAM_TYPES['rdInline_wrIndexed'], bool, watch_status),
            Param('delay', PARAM_TYPES['rdInline_wrIndexed'], int, delay)
        )

        label = "GPIO" + str(peripheral_num)
        idfr = MultilineIdentifier(
            MULTILINE_TYPES["dictionary"], 
            label=Param('label', PARAM_TYPES['rdInline_wrInline'], str, label)
        )

        res = self.query(
            'AT#EVMONI', 
            params, 
            multiline_identifier=idfr, 
            confirm=confirm, 
            force=force,
            pre_update_task=lambda : self.evmoni_enabled(enabled=False, confirm=confirm, force=force),
            post_update_task=lambda : self.evmoni_enabled(enabled=True, confirm=confirm, force=force)
        )

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
            Param("_mode", PARAM_TYPES['inline_readonly'], bool, None),
            Param("_status", PARAM_TYPES['rdInline_wrInline'], bool, enabled)
        )

        res = self.query(
            "AT#ENAEVMONI", 
            params, 
            confirm=confirm, 
            force=force
        )

        res["enabled"] = res.get("_status") and res.get("_mode")

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
            Param("instance", PARAM_TYPES['rdInline_wrInline'], int, instance),
            Param("urcmod", PARAM_TYPES['rdInline_wrInline'], bool, urcmod),
            Param("timeout", PARAM_TYPES['rdInline_wrInline'], int, timeout)
        )

        res = self.query(
            "AT#ENAEVMONICFG", 
            params, 
            confirm=confirm, 
            force=force,
            pre_update_task=lambda : self.evmoni_enabled(enabled=False, confirm=confirm, force=force),
            post_update_task=lambda : self.evmoni_enabled(enabled=True, confirm=confirm, force=force)
        )

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
    def __init__(self, name, paramtype, datatype, desired_value):
        if datatype not in SUPPORTED_DATATYPES:
            raise ValueError('Unsupported type. Supported types: {}'.format(SUPPORTED_DATATYPES))

        if desired_value != None and type(desired_value) != datatype:
            raise ValueError("Type mismatch for {}. Expected: {}, got: {}".format(name, datatype, type(desired_value)))

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
            raise Exception("Can not convert from {} to native type of {}".format(type(value), self.datatype))

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
