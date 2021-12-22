import binascii
import can
import collections
import datetime
import logging

from obd import OBD, OBDStatus, commands
from obd.protocols import UnknownProtocol, CANProtocol
from obd.interfaces.stn11xx import STN11XX, STN11XXError
from six import string_types

from obd_conn import OBDConn
from can_conn import CANConn


log = logging.getLogger(__name__)

DEBUG = log.isEnabledFor(logging.DEBUG)


# ELM327: CAN

class ISO_15765_4_11bit_500k(CANProtocol):
    NAME = "ISO 15765-4 (CAN 11/500)"
    ID = "6"
    HEADER_BITS = 11
    DEFAULT_BAUDRATE = 500000
    INTERFACE = "can0"
    def __init__(self, lines_0100):
        CANProtocol.__init__(self, lines_0100)

class ISO_15765_4_29bit_500k(CANProtocol):
    NAME = "ISO 15765-4 (CAN 29/500)"
    ID = "7"
    HEADER_BITS = 29
    DEFAULT_BAUDRATE = 500000
    INTERFACE = "can0"
    def __init__(self, lines_0100):
        CANProtocol.__init__(self, lines_0100)

class ISO_15765_4_11bit_250k(CANProtocol):
    NAME = "ISO 15765-4 (CAN 11/250)"
    ID = "8"
    HEADER_BITS = 11
    DEFAULT_BAUDRATE = 250000
    INTERFACE = "can0"
    def __init__(self, lines_0100):
        CANProtocol.__init__(self, lines_0100)

class ISO_15765_4_29bit_250k(CANProtocol):
    NAME = "ISO 15765-4 (CAN 29/250)"
    ID = "9"
    HEADER_BITS = 29
    DEFAULT_BAUDRATE = 250000
    INTERFACE = "can0"
    def __init__(self, lines_0100):
        CANProtocol.__init__(self, lines_0100)

# STN11XX: High Speed CAN

class HSC_ISO_11898_11bit_500k(CANProtocol):
    NAME = "HS CAN (ISO 11898, 11bit, 500kbps, var DLC)"
    ID = "31"
    HEADER_BITS = 11
    DEFAULT_BAUDRATE = 500000
    INTERFACE = "can0"
    def __init__(self, lines_0100):
        CANProtocol.__init__(self, lines_0100)

class HSC_ISO_11898_29bit_500k(CANProtocol):
    NAME = "HS CAN (ISO 11898, 29bit, 500kbps, var DLC)"
    ID = "32"
    HEADER_BITS = 29
    DEFAULT_BAUDRATE = 500000
    INTERFACE = "can0"
    def __init__(self, lines_0100):
        CANProtocol.__init__(self, lines_0100)

class HSC_ISO_15765_11bit_500k(CANProtocol):
    NAME = "HS CAN (ISO 15765, 11bit, 500kbps, DLC=8)"
    ID = "33"
    HEADER_BITS = 11
    DEFAULT_BAUDRATE = 500000
    INTERFACE = "can0"
    def __init__(self, lines_0100):
        CANProtocol.__init__(self, lines_0100)

class HSC_ISO_15765_29bit_500k(CANProtocol):
    NAME = "HS CAN (ISO 15765, 29bit, 500kbps, DLC=8)"
    ID = "34"
    HEADER_BITS = 29
    DEFAULT_BAUDRATE = 500000
    INTERFACE = "can0"
    def __init__(self, lines_0100):
        CANProtocol.__init__(self, lines_0100)

class HSC_ISO_15765_11bit_250k(CANProtocol):
    NAME = "HS CAN (ISO 15765, 11bit, 250kbps, DLC=8)"
    ID = "35"
    HEADER_BITS = 11
    DEFAULT_BAUDRATE = 250000
    INTERFACE = "can0"
    def __init__(self, lines_0100):
        CANProtocol.__init__(self, lines_0100)

class HSC_ISO_15765_29bit_250k(CANProtocol):
    NAME = "HS CAN (ISO 15765, 29bit, 250kbps, DLC=8)"
    ID = "36"
    HEADER_BITS = 29
    DEFAULT_BAUDRATE = 250000
    INTERFACE = "can0"
    def __init__(self, lines_0100):
        CANProtocol.__init__(self, lines_0100)

# STN11XX: J1939

class HSC_J1939_11bit_250k(UnknownProtocol):
    NAME = "J1939 (11bit, 250kbps)"
    ID = "41"
    HEADER_BITS = 11
    DEFAULT_BAUDRATE = 250000
    INTERFACE = "can0"
    def __init__(self, lines_0100):
        UnknownProtocol.__init__(self, lines_0100)

class HSC_J1939_29bit_250k(UnknownProtocol):
    NAME = "J1939 (29bit, 250kbps)"
    ID = "42"
    HEADER_BITS = 29
    DEFAULT_BAUDRATE = 250000
    INTERFACE = "can0"
    def __init__(self, lines_0100):
        UnknownProtocol.__init__(self, lines_0100)

# STN11XX: Medium Speed CAN

class MSC_ISO_11898_11bit_125k(CANProtocol):
    NAME = "MS CAN (ISO 11898, 11bit, 125kbps, var DLC)"
    ID = "51"
    HEADER_BITS = 11
    DEFAULT_BAUDRATE = 125000
    INTERFACE = "can1"
    def __init__(self, lines_0100):
        CANProtocol.__init__(self, lines_0100)

class MSC_ISO_11898_29bit_125k(CANProtocol):
    NAME = "MS CAN (ISO 11898, 29bit, 125kbps, var DLC)"
    ID = "52"
    HEADER_BITS = 29
    DEFAULT_BAUDRATE = 125000
    INTERFACE = "can1"
    def __init__(self, lines_0100):
        CANProtocol.__init__(self, lines_0100)

class MSC_ISO_15765_11bit_125k(CANProtocol):
    NAME = "MS CAN (ISO 15765, 11bit, 125kbps, DLC=8)"
    ID = "53"
    HEADER_BITS = 11
    DEFAULT_BAUDRATE = 125000
    INTERFACE = "can1"
    def __init__(self, lines_0100):
        CANProtocol.__init__(self, lines_0100)

class MSC_ISO_15765_29bit_125k(CANProtocol):
    NAME = "MS CAN (ISO 15765, 29bit, 125kbps, DLC=8)"
    ID = "54"
    HEADER_BITS = 29
    DEFAULT_BAUDRATE = 125000
    INTERFACE = "can1"
    def __init__(self, lines_0100):
        CANProtocol.__init__(self, lines_0100)


class SocketCANError(STN11XXError):

    def __init__(self, *args, **kwargs):
        super(SocketCANError, self).__init__(*args, **kwargs)


class SocketCANInterface(STN11XX):

    CAN_SUPPORTED_PROTOCOLS = collections.OrderedDict({

        # ELM327: CAN
        ISO_15765_4_11bit_500k.ID:    ISO_15765_4_11bit_500k,
        ISO_15765_4_29bit_500k.ID:    ISO_15765_4_29bit_500k,
        ISO_15765_4_11bit_250k.ID:    ISO_15765_4_11bit_250k,
        ISO_15765_4_29bit_250k.ID:    ISO_15765_4_29bit_250k,

        # STN11XX: High Speed CAN
        HSC_ISO_11898_11bit_500k.ID:  HSC_ISO_11898_11bit_500k,  # HS CAN (ISO 11898, 11bit, 500kbps, var DLC)
        HSC_ISO_11898_29bit_500k.ID:  HSC_ISO_11898_29bit_500k,  # HS CAN (ISO 11898, 29bit, 500kbps, var DLC)
        HSC_ISO_15765_11bit_500k.ID:  HSC_ISO_15765_11bit_500k,  # HS CAN (ISO 15765, 11bit, 500kbps, DLC=8)
        HSC_ISO_15765_29bit_500k.ID:  HSC_ISO_15765_29bit_500k,  # HS CAN (ISO 15765, 29bit, 500kbps, DLC=8)
        HSC_ISO_15765_11bit_250k.ID:  HSC_ISO_15765_11bit_250k,  # HS CAN (ISO 15765, 11bit, 250kbps, DLC=8)
        HSC_ISO_15765_29bit_250k.ID:  HSC_ISO_15765_29bit_250k,  # HS CAN (ISO 15765, 29bit, 250kbps, DLC=8)

        #STN11XX: J1939 
        HSC_J1939_11bit_250k.ID:      HSC_J1939_11bit_250k,      # J1939 (11bit, 250kbps)
        HSC_J1939_29bit_250k.ID:      HSC_J1939_29bit_250k,      # J1939 (29bit, 250kbps)

        # STN11XX: Medium Speed CAN
        MSC_ISO_11898_11bit_125k.ID:  MSC_ISO_11898_11bit_125k,  # MS CAN (ISO 11898, 11bit, 125kbps, var DLC)
        MSC_ISO_11898_29bit_125k.ID:  MSC_ISO_11898_29bit_125k,  # MS CAN (ISO 11898, 29bit, 125kbps, var DLC)
        MSC_ISO_15765_11bit_125k.ID:  MSC_ISO_15765_11bit_125k,  # MS CAN (ISO 15765, 11bit, 125kbps, DLC=8)
        MSC_ISO_15765_29bit_125k.ID:  MSC_ISO_15765_29bit_125k,  # MS CAN (ISO 15765, 29bit, 125kbps, DLC=8)
    })

    CAN_TRY_PROTOCOLS = [

        # ELM327: CAN
        ISO_15765_4_11bit_500k,
        ISO_15765_4_29bit_500k,
        ISO_15765_4_11bit_250k,
        ISO_15765_4_29bit_250k,
    ]

    def __init__(self, status_callback=None):
        self._status              = OBDStatus.NOT_CONNECTED
        self._status_callback     = status_callback
        self._protocol            = UnknownProtocol([])
        
        self._echo_off            = True

        # Cached settings that have been changed runtime
        self._runtime_settings    = {}

        self._port = CANConn(__salt__)

    def open(self, channel=None, protocol=None, echo_off=True, print_headers=True):

        log.info("Opening SocketCAN interface connection: Channel={:}, Protocol={:}".format(
            channel,
            "auto" if protocol is None else protocol
        ))

        protocol_dict = protocol if isinstance(protocol, dict) else {"id": protocol}
        protocol_cls = self.supported_protocols().get(protocol_dict.get("id", None), None)

        self._port.setup(channel=channel, bitrate=protocol_dict.get("baudrate", getattr(protocol_cls, "DEFAULT_BAUDRATE", 500000)))

        # Open connection
        try:
            self._port.open()
        except:
            log.exception("Failed to open SocketCAN connection")

            # Remember to report back status
            self._trigger_status_callback()

            raise

        # By now, we've successfuly communicated with the SocketCAN interface, but not the car
        self._status = OBDStatus.ITF_CONNECTED

        # Remember to report back status
        self._trigger_status_callback()

        # Try to communicate with the car, and load the correct protocol parser
        try:
            self.set_protocol(protocol_dict.pop("id", None), **protocol_dict)
        except Exception as ex:
            log.warning(str(ex))

            return

        log.info("Connected successfully to vehicle: Channel={:}, Protocol={:}".format(
            channel,
            self._protocol.ID
        ))

    #def close(self):

    def reopen(self):
        # TODO HN: Take CAN connection down and up - and ensure runtime_settings is cleared?

        raise NotImplementedError("Not supported by SocketCAN interface")

    #def restore_defaults(self):

    #def warm_reset(self):

    #def reset(self):

    def connection(self):
        raise NotImplementedError("Not supported by SocketCAN interface")

    #def status(self):

    #def runtime_settings(self):

    @classmethod
    def supported_protocols(cls):
        return cls.CAN_SUPPORTED_PROTOCOLS

    #def protocol(self, verify=True):

    #def ecus(self):

    def set_protocol(self, ident, **kwargs):
        ret = super(STN11XX, self).set_protocol(ident, **kwargs)  # NOTE: Calls ELM327's method (skipping STN11XX's)

        # Automatic filtering mode is on per default
        self._runtime_settings["auto_filtering"] = True
        self._ensure_auto_filtering()

        # No custom filters are set
        self._runtime_settings.pop("can_pass_filters", None)
        self._runtime_settings.pop("can_block_filters", None)
        self._runtime_settings.pop("can_flow_control_filters", None)
        self._runtime_settings.pop("j1939_pgn_filters", None)

        return ret

    def set_baudrate(self, baudrate):
        raise NotImplementedError("Not supported by SocketCAN interface")

    #def set_expect_responses(self, value):

    #def set_response_timeout(self, value):

    #def set_adaptive_timing(self, value):

    #def set_header(self, value):

    #def set_can_auto_format(self, value):

    # TODO HN: Find out how to support this!
    #def set_can_extended_address(self, value):

    #def set_can_priority(self, value):

    #def set_print_spaces(self, value):

    #def query(self, cmd, header=None, parse=True, read_timeout=None):

    def relay(self, cmd, raw_response=False):
        raise NotImplementedError("Not supported by SocketCAN interface")

    def send(self, cmd, delay=None, read_timeout=None, interrupt_delay=None, raw_response=False):
        
        # Respond OK on all AT/ST commands
        if cmd[:2].upper() in ["AT", "ST"]:
            log.info("Returning OK to AT/ST command: {:}".format(cmd))

            return [self.OK]

        ret = []

        if self._runtime_settings.get("expect_responses", True):

            # Determine how many reply messages, if specified
            replies = None
            if cmd[-2] == " ":
                replies = int(cmd[-1], 16)
                cmd = cmd[:-2]

            # Response timing
            timeout = 0.2  # 200ms
            if self._runtime_settings.get("adaptive_timing", 1) == 0:  # Adaptive timing off (fixed timeout)
                 timeout = self._runtime_settings.get("response_timeout", 50) * 4 / 1000

            # Print spaces
            msg_formatter = can_message_formatter
            if self._runtime_settings.get("print_spaces", True):
                msg_formatter = can_message_with_spaces_formatter

            res = self._port.query(self._build_can_msg(cmd), replies=replies, timeout=timeout, strict=False)
            if res:
                ret = [msg_formatter(r) for r in res]
            elif not raw_response:
                raise SocketCANError(self.ERRORS["NO DATA"], code="NO DATA")  # Same behaviour as old

        else:
            self._port.send(self._build_can_msg(cmd))

        return ret

    #def set_can_monitor_mode(self, value):

    def monitor(self, mode=0, auto_format=False, filtering=False, raw_response=False, formatter=None, **kwargs):
        ret = []

        # TODO HN: How to support CAN auto formatting?
        if auto_format:
            ValueError("CAN auto formatting is currently not supported by SocketCan OBD connection")

        # Ensure CAN automatic formatting
        self.set_can_auto_format(auto_format)

        # Ensure CAN monitoring mode
        self.set_can_monitor_mode(mode)

        if not filtering:
            self.clear_filters()

        if not formatter:
            if self._runtime_settings.get("print_spaces", True):
                formatter = can_message_with_spaces_formatter
            else:
                formatter = can_message_formatter

        # Setup mode
        current_mode = self._runtime_settings.get("can_monitor_mode", 0)
        if current_mode == 0:
            skip_error_frames = True            
        elif current_mode == 2:
            skip_error_frames = False
        else:
            raise ValueError("Monitor mode {:} is currently not supported by SocketCan OBD connection".format(current_mode))

        # Monitor for specified duration
        self._port.monitor_until(lambda msg: ret.append(formatter(msg)), skip_error_frames=skip_error_frames, **kwargs)
        if not ret and not raw_response:
            raise SocketCANError(self.ERRORS["NO DATA"], code="NO DATA")  # Same behaviour as old

        return ret

    def monitor_continuously(self, wait=False, enrich=None, **kwargs):

        if wait:
            raise ValueError("Set duration to enforce wait when using SocketCAN interface")

        return self.monitor(
            receive_timeout=kwargs.pop("receive_timeout", 1),
            keep_listening=kwargs.pop("keep_listening", True),
            buffer_size=kwargs.pop("buffer_size", 5000),
            formatter=enrich,
            **kwargs)

    def auto_filtering(self, enable=None):
        ret = super(SocketCANInterface, self).auto_filtering(enable=enable)
        if ret:
            self._ensure_auto_filtering()

        return ret

    #def list_filters(self, type="ALL"):

    #def list_filters_by(self, type):

    #def add_filter(self, type, value):

    def clear_filters(self, type="ALL"):
        if type.upper() == self.FILTER_TYPE_ALL:
            self._port.clear_filters()

        super(SocketCANInterface, self).clear_filters(type=type)

    def can_pass_filters(self, clear=False, add=None):

        if clear:
            self._port.clear_filters()

        if add:
            filter = {}

            if isinstance(add, dict):
                filter = add
            else:
                val = str(add)
                if "," in val:
                    id, mask = val.split(",")
                    filter["id"] = id
                    filter["mask"] = mask
                else:
                    filter["id"] = val

            # Ensure hex strings are converted to integers
            if "id" in filter and isinstance(filter["id"], string_types):
                filter["id"] = int(filter["id"], 16)
            if "mask" in filter and isinstance(filter["mask"], string_types):
                filter["mask"] = int(filter["mask"], 16)

            filter.setdefault("is_ext_id", self._protocol.HEADER_BITS > 11)

            # Clear before adding if automatic filtering is enabled
            if self._runtime_settings.get("auto_filtering", True):
                self._port.clear_filters()

            self._port.ensure_filter(**filter)

        super(SocketCANInterface, self).can_pass_filters(clear=clear, add=add)

    def can_block_filters(self, clear=False, add=None):
        if add:
            raise NotImplementedError("Not supported by SocketCAN interface")

    def can_flow_control_filters(self, clear=False, add=None):

        # TODO HN: Find out if we should support this?

        if add:
            raise NotImplementedError("Not supported by SocketCAN interface")

    def j1939_pgn_filters(self, clear=False, add=None):

        # TODO HN: We should support this!

        if add:
            raise NotImplementedError("Not supported by SocketCAN interface")

    def can_flow_control_id_pairs(self, clear=False, add=None):

        # TODO HN: Find out if we should support this?

        if add:
            raise NotImplementedError("Not supported by SocketCAN interface")

    def _verify_protocol(self, ident, test=False):

        if isinstance(ident, string_types):
            protocol_cls = self.supported_protocols()[ident]
        else:
            protocol_cls = ident

        res_0100 = self._port.obd_query(0x01, 0x00, is_ext_id=protocol_cls.HEADER_BITS > 11)
        if not res_0100:
            msg = "No data received when trying to verify connectivity of protocol '{:}'".format(ident)
            if test:
                logger.warning(msg)

                return []
            else:
                raise SocketCANError(msg)

        return [can_message_formatter(r) for r in res_0100]

    def _manual_protocol(self, ident, verify=False, baudrate=None):
        log.info("############### MANUAL PROTOCOL")

        protocol_cls = self.supported_protocols()[ident]
        baudrate = baudrate or protocol_cls.DEFAULT_BAUDRATE

        self._port.setup(channel=protocol_cls.INTERFACE, bitrate=baudrate)

        if verify:

            # Verify protocol connectivity
            res_0100 = self._verify_protocol(protocol_cls, test=not verify)

            # Initialize protocol parser
            protocol = protocol_cls(res_0100)
        else:
            protocol = protocol_cls([])

        # Remember to set the used baudrate
        protocol.baudrate = baudrate

        return protocol

    def _auto_protocol(self, verify=True, **kwargs):
        log.info("############### AUTODETECTING PROTOCOL")

        if not verify:
            ValueError("SocketCAN interface cannot autodetect protocol without verify")

        res_0100 = []
        for protocol_cls in self.CAN_TRY_PROTOCOLS:
            log.info("Trying with protocol '{:}' on SocketCAN interface '{:}'".format(protocol_cls.ID, protocol_cls.INTERFACE))

            self._port.setup(channel=protocol_cls.INTERFACE, bitrate=protocol_cls.DEFAULT_BAUDRATE)

            # TODO HN: Try to listen for activity before sending anything based on verify?
            # Also 'socketcan.show' might give indication of protocol state before receiving/verify?

            # Verify protocol connectivity
            try:
                res_0100 = self._verify_protocol(protocol_cls, test=not verify)
                if res_0100:
                    log.info("Got reply using protocol '{:}' on SocketCAN interface '{:}'".format(protocol_cls.ID, protocol_cls.INTERFACE))

                    # Instantiate the corresponding protocol parser
                    protocol = protocol_cls(res_0100)
                    protocol.baudrate = protocol_cls.DEFAULT_BAUDRATE

                    return protocol
            except SocketCANError as ex:
                log.info("Unable to verify protocol '{:}' on SocketCAN interface '{:}': {:}".format(protocol_cls.ID, protocol_cls.INTERFACE, ex))

        raise SocketCANError("Unable to autodetect protocol")

    def _interrupt(self, *args, **kwargs):
        raise NotImplementedError("Not supported by SocketCAN interface")

    def _write(self, *args, **kwargs):
        raise NotImplementedError("Not supported by SocketCAN interface")

    def _read(self, *args, **kwargs):
        raise NotImplementedError("Not supported by SocketCAN interface")

    def _read_line(self, *args, **kwargs):
        raise NotImplementedError("Not supported by SocketCAN interface")

    def _build_can_msg(self, cmd):

        header = self._runtime_settings.get("header", self.OBDII_HEADER)

        # CAN priority
        prio = self._runtime_settings.get("can_priority", None)
        if prio != None:
            header = str(prio) + str(header)

        # CAN automatic formatting
        data = bytearray.fromhex(cmd)
        if self._runtime_settings.get("can_auto_format", True):
            data = bytearray([len(data)]) + data

        return can.Message(arbitration_id=int(header, 16),
            data=data,
            is_extended_id=self._protocol.HEADER_BITS > 11)

    def _ensure_auto_filtering(self):
        self._port.ensure_filter(id=0x7E8, is_ext_id=self._protocol.HEADER_BITS > 11, mask=0x7F8, clear=True)
        # TODO HN: 29bit: 18DAF100,1FFFFF00


def can_message_formatter(msg):
    return "{:02x}{:}".format(msg.arbitration_id, binascii.hexlify(msg.data))


def can_message_with_spaces_formatter(msg):
    data = binascii.hexlify(msg.data)
    return "{:02x} {:}".format(msg.arbitration_id, " ".join(data[i:i+2] for i in range(0, len(data), 2)))


class SocketCAN_OBD(OBD):

    def __init__(self, channel=None, protocol=None, load_commands=True, status_callback=None, reset_callback=None):
        self.interface = SocketCANInterface(status_callback=status_callback)
        self.supported_commands = set(commands.base_commands())
        self.reset_callback = reset_callback
        self.fast = False
        self._last_command = b""
        self._frame_counts = {}

        self.interface.open(channel, protocol=protocol)

        if load_commands:
            try:
                self._load_commands()
            except:
                log.exception("Unable to load OBD commands")


class SocketCAN_OBDConn(OBDConn):

    def __init__(self, __salt__):
        globals()["__salt__"] = __salt__

        super(SocketCAN_OBDConn, self).__init__()

    @property
    def protocol_autodetect_interface(self):
        return "can0"

    def setup(self, **settings):
        channel = settings.pop("channel", "can0")
        super(SocketCAN_OBDConn, self).setup(device=channel, baudrate=9600, **settings)  # NOTE: Reused device parameter for channel selection

    def open(self, force=False):
        if self.is_permanently_closed and not force:
            raise Warning("SocketCAN OBD connection is no longer available as it has been permanently closed")

        # Reset flag
        self.is_permanently_closed = False

        if DEBUG:
            log.debug("Opening SocketCAN OBD connection")

        try :
            self._obd = SocketCAN_OBD(
                channel=self._device,  # NOTE: Reused device parameter for channel selection
                protocol={
                    "id": self._protocol_id if self._protocol_id != "AUTO" else None,  # None value will result in autodetection
                    "baudrate": self._protocol_baudrate,
                    "verify": self._protocol_verify
                },
                load_commands=self._protocol_verify,  # Only load supported commands when protocol is verified
                status_callback=self._status_callback,
                reset_callback=self._reset_callback
            )

            if self._advanced_initial:
                self.ensure_advanced_settings.undecorated(self, self._advanced_initial)  # No need to call the 'ensure_open' decorator

            return self

        except Exception:
            log.exception("Failed to open SocketCAN OBD connection")

            raise

    def supported_protocols(self):
        return SocketCANInterface.supported_protocols()

    def _enrich_monitor_entry(self, msg):
        return {
            "_stamp": datetime.datetime.fromtimestamp(msg.timestamp).isoformat(),
            "value": can_message_formatter(msg)
        }
