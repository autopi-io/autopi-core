import binascii
import can
import collections
import datetime
import logging

from obd import OBD, OBDStatus, commands, OBDCommand, ECU, decoders
from obd.utils import bytes_to_int
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

        self._port.setup(
            channel=channel or getattr(protocol_cls, "INTERFACE", "can0"),
            bitrate=protocol_dict.get("baudrate", None) or getattr(protocol_cls, "DEFAULT_BAUDRATE", 500000))

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

        self.close()

        self.open(channel=self._port or getattr(protocol_cls, "INTERFACE", "can0"),
            protocol={
                "id": getattr(self._protocol, "ID", None),
                "baudrate": getattr(self._protocol, "baudrate", None)
            } if not getattr(self._protocol, "autodetected", True) else None
        )

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

    #def set_can_extended_address(self, value):

    #def set_can_priority(self, value):

    #def set_print_spaces(self, value):

    #def query(self, cmd, header=None, parse=True, read_timeout=None):

    def relay(self, cmd, raw_response=False):
        raise NotImplementedError("Not supported by SocketCAN interface")

    def send(self, cmd, delay=None, read_timeout=None, interrupt_delay=None, raw_response=False):
        ret = []

        # Respond OK on all AT/ST commands
        if cmd[:2].upper() in ["AT", "ST"]:
            if cmd.upper() == "ATRV":
                res = __salt__["spm.query"]("volt_readout")
                ret.append("{:.2f}V".format(res["value"]))
            else:
                ret.append(self.OK)

            log.info("Returning {:} to AT/ST command '{:}'".format(ret, cmd))

            return ret

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

            # Configure formatter
            msg_formatter = lambda msg : can_message_formatter (
                msg, 
                include_spaces=self._runtime_settings.get("print_spaces", True),
                include_hashtag=False
            )

            kwargs = {}

            # CAN extended address (flow control)
            extended_address = self._runtime_settings.get("can_extended_address", None)
            if extended_address != None:
                kwargs["extended_address"] = int(str(extended_address), 16)

            res = self._port.query(self._build_can_msg(cmd),
                replies=replies,
                timeout=timeout,
                flow_control=[self._port.FLOW_CONTROL_CUSTOM, self._port.FLOW_CONTROL_OBD],
                zero_padding=(8 if self._runtime_settings.get("can_auto_format", True) else 0),
                strict=False,
                **kwargs)
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

        if auto_format:
            ValueError("CAN auto formatting is currently not supported by SocketCan OBD connection")

        # Ensure CAN automatic formatting
        self.set_can_auto_format(auto_format)

        # Ensure CAN monitoring mode
        self.set_can_monitor_mode(mode)

        if not filtering:
            self.clear_filters()

        format_response = kwargs.pop("format_response", False)
        if not formatter:
            formatter = lambda msg : can_message_formatter(msg, include_spaces=self._runtime_settings.get("print_spaces", True), include_hashtag=format_response)

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
            raise NotImplementedError("Not supported by SocketCAN interface - only pass filters are supported")

    def can_flow_control_filters(self, clear=False, add=None):
        """
        From the little research that could be done for this task, it looks like the can flow control filters are just
        standard pass filters. The can_flow_control_id_pairs is what actually does the matching and communication on
        the CAN bus, the filters just allow those headers to show up.

        For now, this function just passes the arguments `clear` and `add` down to can_pass_filters function.
        """

        self.can_pass_filters(clear=clear, add=add)

    def j1939_pgn_filters(self, clear=False, add=None):
        """
        NOTE NV: So far, it looks like J1939 only cares about the PGN itself being
        the same in order to match the header. For example, we've seen that RPM comes
        from header 0x0CF00400, but also from 0x1CF004FC - i.e. the identifier is 0xF004.

        This is also the reasoning for the mask added below -> 0x00FFFF00, we care only for the PGN.
        This might need to be changed depending on what other behaviour we see from J1939 enabled vehicles.

        NOTE NV: After investigating J1939 further, it looks like the mask might need to be 0x03FFFF00, because
        of the extended data page and data page bits that are located in those bit locations. Will leave the code
        bellow as is for right now, but we might need to change it later
        """

        if isinstance(add, string_types):
            # Only format the 'add' parameter if it is passed as a stirng
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Adding J1939 filter mask to filter {}".format(add))

            add = "{:x},00FFFF00".format(int(add, 16) << 8)

        self.can_pass_filters(clear=clear, add=add)

    def can_flow_control_id_pairs(self, clear=False, add=None):

        if clear:
            self._port.flow_control_id_mappings.clear()

        if add:
            tx_id, rx_id = str(add).replace(" ", "").split(",")
            self._port.flow_control_id_mappings[int(rx_id, 16)] = int(tx_id, 16)

        super(SocketCANInterface, self).can_flow_control_id_pairs(clear=clear, add=add)

    def _verify_protocol(self, ident, test=False):

        if isinstance(ident, string_types):
            protocol_cls = self.supported_protocols()[ident]
        else:
            protocol_cls = ident

        res_0100 = self._port.obd_query(0x01, 0x00, is_ext_id=protocol_cls.HEADER_BITS > 11, strict=False, skip_error_frames=True)
        if not res_0100:
            msg = "No data received when trying to verify connectivity of protocol '{:}'".format(ident)
            if test:
                logger.warning(msg)

                return []
            else:
                raise SocketCANError(msg)

        return [can_message_formatter(r) for r in res_0100]

    def _manual_protocol(self, ident, verify=False, baudrate=None):
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
        log.info("Initiates autodetection of OBD protocol")

        if not verify:
            ValueError("SocketCAN interface cannot autodetect OBD protocol without verify")

        res_0100 = []
        for protocol_cls in self.CAN_TRY_PROTOCOLS:
            log.info("Trying with protocol '{:}' on SocketCAN interface '{:}'".format(protocol_cls.ID, protocol_cls.INTERFACE))

            self._port.setup(channel=protocol_cls.INTERFACE, bitrate=protocol_cls.DEFAULT_BAUDRATE)

            # Verify protocol connectivity
            try:
                res_0100 = self._verify_protocol(protocol_cls, test=not verify)
                if res_0100:
                    log.info("Got reply using protocol '{:}' on SocketCAN interface '{:}'".format(protocol_cls.ID, protocol_cls.INTERFACE))

                    # Instantiate the corresponding protocol parser
                    protocol = protocol_cls(res_0100)
                    protocol.baudrate = protocol_cls.DEFAULT_BAUDRATE

                    return protocol
            except Exception as ex:
                log.info("Unable to verify OBD protocol '{:}' on SocketCAN interface '{:}': {:}".format(protocol_cls.ID, protocol_cls.INTERFACE, ex))

        raise SocketCANError("Unable to autodetect OBD protocol")

    def _interrupt(self, *args, **kwargs):
        raise NotImplementedError("Not supported by SocketCAN interface")

    def _write(self, *args, **kwargs):
        raise NotImplementedError("Not supported by SocketCAN interface")

    def _read(self, *args, **kwargs):
        raise NotImplementedError("Not supported by SocketCAN interface")

    def _read_line(self, *args, **kwargs):
        raise NotImplementedError("Not supported by SocketCAN interface")

    def _build_can_msg(self, cmd):

        header = self._runtime_settings.get("header", None)
        if header == None:
            header = "18DB33F1" if self._protocol.HEADER_BITS > 11 else "7DF"
        else:
            header = header.strip()

            # CAN priority
            prio = self._runtime_settings.get("can_priority", None)
            if prio != None:
                header = str(prio) + str(header)

        data = bytearray.fromhex(cmd)

        # CAN automatic formatting
        can_auto_format = self._runtime_settings.get("can_auto_format", True)
        if can_auto_format:
            data = bytearray([len(data)]) + data

        # CAN extended address
        extended_address = self._runtime_settings.get("can_extended_address", None)
        if extended_address != None:
            data = bytearray([int(str(extended_address), 16)]) + data

        is_extended_id=len(header) > 3

        return can.Message(arbitration_id=int(header, 16),
            data=data.ljust(8, "\0") if can_auto_format else data,
            is_extended_id=is_extended_id)

    def _ensure_auto_filtering(self):
        if self._protocol.HEADER_BITS > 11:
            self._port.ensure_filter(id=0x18DAF100, is_ext_id=True, mask=0x1FFFFF00, clear=True)
        else:
            self._port.ensure_filter(id=0x7E8, is_ext_id=False, mask=0x7F8, clear=True)


def can_message_formatter(msg, include_hashtag=False, include_spaces=False):
    """
    Formats a raw python-can Message object to a string.
    """

    # This is how obd_conn would handle the formatting. Remove the following 2 lines to allow both spaces and hashtags
    if include_hashtag:
        include_spaces=False

    # Data
    data_hex = binascii.hexlify(msg.data)
    if include_spaces:
        data_string = " ".join(data_hex[i:i+2] for i in range(0, len(data_hex), 2))
    else:
        data_string = data_hex

    # Seperator
    seperator_string = "#" if include_hashtag else ""
    if include_spaces:
        seperator_string = " " + seperator_string + (" " if include_hashtag else "")

    # Header
    header_string = ("{:08x}" if msg.is_extended_id else "{:02x}").format(msg.arbitration_id)

    # Return value
    return header_string + seperator_string + data_string

def vin_decoder(messages):
    return messages[0].data[3:].decode("ascii")

def odometer_decoder(messages):
    return bytes_to_int(messages[0].data[2:6])/10

def add_commands_if_not_there(mode_number, pids):
    mode_list = commands.modes[mode_number]
    existing_names = [p.name for p in mode_list]
    for pid in pids:
        if not (pid.name in existing_names):
            mode_list.append(pid)

        if not pid.name in commands.__dict__.keys():
            commands.__dict__[pid.name] = pid

class SocketCAN_OBD(OBD):

    def __init__(self, channel=None, protocol=None, load_commands=True, status_callback=None, reset_callback=None):
        #                      name                             description                         cmd  bytes       decoder                    ECU          fast
        __mode1__ = [
            OBDCommand("ODOMETER"                   , "Current odometer value"                  , b"01A6", 8,   odometer_decoder,               ECU.ENGINE,  True),
        ]
        __mode9__ = [
            OBDCommand("PIDS_9A"                    , "Supported PIDs [01-20]"                  , b"0900", 4,   decoders.pid,                   ECU.ENGINE,  True),
            OBDCommand("VIN_MESSAGE_COUNT"          , "VIN Message Count"                       , b"0901", 1,   decoders.uas(0x01),             ECU.ENGINE,  True),
            OBDCommand("VIN"                        , "Get Vehicle Identification Number"       , b"0902", 20,  vin_decoder,                    ECU.ENGINE,  True),
        ]

        add_commands_if_not_there(1, __mode1__)
        add_commands_if_not_there(9, __mode9__)

        # Add the 0900 to default supported commands, so it can be queried during discovery
        supported_commands = commands.base_commands()
        supported_commands.append(__mode9__[0])

        self.interface = SocketCANInterface(status_callback=status_callback)
        self.supported_commands = set(supported_commands)
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

    def ensure_protocol(self, ident, baudrate=None, verify=True):
        super(SocketCAN_OBDConn, self).ensure_protocol(ident, baudrate=baudrate, verify=self._protocol_verify or verify)

    def supported_protocols(self):
        return SocketCANInterface.supported_protocols()

    def _enrich_monitor_entry(self, msg):
        return {
            "_stamp": datetime.datetime.fromtimestamp(msg.timestamp).isoformat(),
            "value": can_message_formatter(msg)
        }

    # @Decorators.ensure_open
    def monitor(self, **kwargs):
        return self._obd.interface.monitor(**kwargs)
