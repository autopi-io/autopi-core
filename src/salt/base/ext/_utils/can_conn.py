import binascii
import can
import logging
import Queue
import subprocess

from six import string_types
from timeit import default_timer as timer


log = logging.getLogger(__name__)

DEBUG = log.isEnabledFor(logging.DEBUG)

INTERFACE_STATE_UP   = "up"
INTERFACE_STATE_DOWN = "down"

BUS_STATES = {
    can.bus.BusState.ACTIVE:  "active",
    can.bus.BusState.PASSIVE: "passive",
    can.bus.BusState.ERROR:   "error"
}

FRAME_TYPE_SF = 0x00  # Single frame
FRAME_TYPE_FF = 0x10  # First frame of multi-frame message
FRAME_TYPE_CF = 0x20  # Consecutive frame(s) of multi-frame message

FRAME_TYPES = {
    FRAME_TYPE_SF: "single",
    FRAME_TYPE_FF: "first",
    FRAME_TYPE_CF: "consecutive"
}


class CANConn(object):

    FLOW_CONTROL_CUSTOM = "custom"
    FLOW_CONTROL_OBD = "obd"

    class Decorators(object):

        @staticmethod
        def ensure_open(func):

            def decorator(self, *args, **kwargs):

                # Ensure connection is open
                self.ensure_open()

                try:
                    return func(self, *args, **kwargs)
                except can.CanError as err:

                    # Store last error on bus
                    if self._bus:
                        self._bus.last_error = err

                    raise

            # Add reference to the original undecorated function
            decorator.undecorated = func

            return decorator

    class ReplyReader(object):

        def __init__(self, outer):
            self.outer = outer

            self._listener = None

        def __enter__(self):
            self._listener = BufferedReader()
            self.outer._notifier.add_listener(self._listener)

            return self

        def __exit__(self, ex_type, ex_val, tb):
            try:
                self.outer._notifier.remove_listener(self._listener)
            except:
                log.exception("Failed to remove listener from bus notifier")

        def await_replies(self, timeout=0.2, flow_control=False, replies=None, strict=True, **kwargs):
            ret = []

            if isinstance(flow_control, list):
                for name in flow_control:
                    func = self.outer._flow_control_id_resolvers.get(name, None)
                    if not func:
                        raise ValueError("No flow control ID resolver found for '{:}'".format(name))

                    kwargs.setdefault("id_resolvers", []).append(func)

            count = 0
            while True:
                count += 1

                msg = self._listener.next(timeout=timeout)
                if msg == None:  # Timeout
                    if strict:
                        if replies > 0:
                            raise Exception("No CAN message reply ({:}/{:}) received within timeout of {:} second(s)".format(count, replies, timeout))
                        elif count == 1:
                            raise Exception("No CAN message reply received within timeout of {:} second(s)".format(timeout))

                    break

                frame_type = None
                if msg.is_error_frame:
                    log.warning("Received CAN reply message marked as an error frame: {:}".format(msg))
                elif msg.is_remote_frame:
                    log.info("Received CAN reply message marked as a remote frame: {:}".format(msg))
                else:  # Data frame
                    frame_type = msg.data[0] & 0xF0

                    # TODO HN
                    #if DEBUG:
                    log.info("Received CAN reply message considered as a data frame of type '{:}': {:}".format(FRAME_TYPES.get(frame_type, "unknown"), msg))

                ret.append(msg)

                # Stop if replies is met
                if replies > 0 and count >= replies:
                    break

                if flow_control and frame_type == FRAME_TYPE_FF:
                    self.outer.send_flow_control_reply_for(msg, **kwargs)

            return ret

    def __init__(self, __salt__):
        globals()["__salt__"] = __salt__

        self.flow_control_id_mappings = {}

        self._settings = {
            "channel": "can0",
            "bitrate": 500000
        }

        self._bus = None
        self._notifier = None
        self._filters = []
        self._is_filters_dirty = False
        self._flow_control_id_resolvers = {
            self.FLOW_CONTROL_CUSTOM: lambda msg: self.flow_control_id_mappings.get(msg.arbitration_id, None),
            self.FLOW_CONTROL_OBD: obd_reply_id_for
        }
        self._monitor_listener = None
        self._is_autodetecting = False

    @property
    def settings(self):
        return dict(self._settings)

    @property
    def channel(self):
        return self._settings["channel"]

    @property
    def bus_metadata(self):
        return dict(self._bus.metadata) if self._bus else {}

    def setup(self, **settings):
        log.info("Applying settings {:}".format(settings))

        # Check for changes
        has_changes = False
        for key, val in settings.iteritems():
            if val != self._settings.get(key, None):
                has_changes = True
                break

        # Skip if no changes
        if not has_changes:
            return

        # Ensure closed before updating settings
        if self.is_open():
            log.info("Closing current CAN connection because settings have changed")

            self.close()

        # Update settings
        self._settings.update(settings)

    def open(self):

        # Ensure closed
        self.close()

        local_settings = self._settings.copy()
        channel = local_settings.pop("channel", "can0")
        receive_own_messages = local_settings.pop("receive_own_messages", False)
        notifier_timeout = local_settings.pop("notifier_timeout", 1.0)
        autodetect = self._settings.pop("autodetect", False)

        if not self._is_autodetecting and autodetect:
            if autodetect == True:
                self.autodetect()
            elif isinstance(autodetect, list):
                self.autodetect(*autodetect)
            elif isinstance(autodetect, dict):
                for key, val in autodetect.iteritems():
                    if self.autodetect(key, **val):
                        break
        else:
            log.info("Opening CAN connection using settings {:}".format(self._settings))

            # Bring up interface
            __salt__["socketcan.up"](interface=channel, **local_settings)

            self._bus = can.interfaces.socketcan.SocketcanBus(
                channel=channel,
                receive_own_messages=receive_own_messages,
                fd=local_settings.get("dbitrate", None) != None)
            self._notifier = can.Notifier(self._bus, [], timeout=notifier_timeout)  # No listeners for now
            setattr(self._bus, "metadata", {})
            setattr(self._bus, "last_error", None)

    def is_open(self):
        if self._bus != None:
            if self._bus.last_error != None:
                try:
                    log.warning("Checking the state of the interface due to the latest CAN connection error: {:}".format(self._bus.last_error))

                    if self.interface_state() != INTERFACE_STATE_UP:
                        return False
                finally:
                    self._bus.last_error = None
            
            return self._bus.state != can.bus.BusState.ERROR

        return False

    def ensure_open(self):
        if not self.is_open():
            self.open()

    def close(self, force=False):

        # Shut down bus, if present
        if self._bus:
            if DEBUG:
                log.debug("Shutting down bus")

            try:
                self._bus.shutdown()
            finally:
                self._bus = None
                self._notifier = None

        # Bring down interface
        if force or self.interface_state() != INTERFACE_STATE_DOWN:
            __salt__["socketcan.down"](interface=self.channel)

    def autodetect(self, *args, **kwargs):
        ret = False

        args = args or ["passive", "obd"]

        if DEBUG:
            log.debug("Autodetecting using arguments {:} and keyword arguments {:}".format(args, kwargs))

        # Keep a copy of original settings
        settings = dict(self._settings)

        try:
            self._is_autodetecting = True

            for arg in args:
                func = getattr(self, "_{:}_autodetect".format(arg), None)
                if not func:
                    raise ValueError("No autodetect method found for '{:}'".format(arg))

                if func(**kwargs):
                    ret = True

                    break
        finally:
            self._is_autodetecting = False

            # Restore settings if unsuccessful
            if not ret:
                self._settings = settings

        return ret

    def _passive_autodetect(self, channel=None, try_bitrates=[500000, 250000, 125000, 1000000], receive_timeout=0.2):
        channel = channel or self.channel

        for bitrate in try_bitrates:
            self.setup(channel=channel, bitrate=bitrate)

            try:
                msg = self.receive(timeout=receive_timeout, expect=False)
                if msg:
                    self._bus.metadata["is_autodetected"] = True
                    self._bus.metadata["is_extended_id"] = msg.is_extended_id

                    log.info("Passive autodetect was successful using settings {:}".format(self._settings))

                    return True
                else:
                    log.info("Passive autodetect did not receive any messages within timeout of {:} second(s) using settings {:}".format(receive_timeout, self._settings))
            except Exception as ex:
                log.info("Passive autodetect failed to receive CAN message using settings {:}: {:}".format(self._settings, ex))

        log.warning("Passive autodetect failed")
        self.close()

        return False

    def _obd_autodetect(self, channel=None, try_bitrates=[500000, 250000], receive_timeout=0.2):
        channel = channel or self.channel

        for bitrate in try_bitrates:
            self.setup(channel=channel, bitrate=bitrate)

            # Query for supported OBD PIDs
            for id_bits in [11, 29]:
                try:
                    msgs = self.obd_query(0x01, 0x00, is_ext_id=id_bits > 11, timeout=receive_timeout, strict=False, skip_error_frames=True)
                    if msgs:
                        self._bus.metadata["is_autodetected"] = True
                        self._bus.metadata["is_extended_id"] = id_bits > 11
                        self._bus.metadata["is_obd_supported"] = True

                        log.info("OBD autodetect for {:}bit CAN ID was successful using settings {:}".format(id_bits, self._settings))

                        return True
                    else:
                        log.info("OBD autodetect for {:}bit CAN ID did not receive any reply messages within timeout of {:} second(s) using settings {:}".format(id_bits, receive_timeout, self._settings))

                except Exception as ex:
                    log.info("OBD autodetect for {:}bit CAN ID failed to query for supported PIDs using settings {:}: {:}".format(id_bits, self._settings, ex))

        log.warning("OBD autodetect failed")
        self.close()

        return False

    def interface_state(self, channel=None):
        channel = channel or self.channel
        state = __salt__["socketcan.show"](interface=channel).get("operstate", "").lower()

        if DEBUG:
            log.debug("CAN interface '{:}' is currently in operation state '{:}'".format(channel, state))

        return state

    def bus_state(self):
        ret = None

        if self._bus:
            ret = BUS_STATES.get(self._bus.state, None)

        return ret

    def list_filters(self):
        return [{"id": f["can_id"], "is_ext_id": f["extended"], "mask": f["can_mask"]} for f in self._filters]

    def clear_filters(self, apply=True):
        ret = False

        if self._filters:
            log.info("Clearing {:} CAN filter(s)".format(len(self._filters)))

            self._filters = []
            self._is_filters_dirty = True

            ret = True

        if apply and self._is_filters_dirty:
            self.apply_filters()

        return ret

    def ensure_filter(self, id=0x00, is_ext_id=False, mask=None, clear=False, apply=True):
        ret = False

        # Set default mask if undefined
        if mask == None:
            if is_ext_id:
                mask = 0x1FFFFFFF
            else:
                mask = 0x7FF

        filter = {"can_id": id, "can_mask": mask, "extended": is_ext_id}
        if filter in self._filters:
            if clear and len(self._filters) > 1:
                self.clear_filters(apply=False)

                ret = True
        else:
            ret = True

            if clear and self._filters:
                self.clear_filters(apply=False)

        if ret:
            log.info("Adding CAN filter: {{'id': '{:x}', 'is_ext_id': {:}, 'mask': '{:x}'}}".format(id, is_ext_id, mask))  # NOTE: Outputs hex values

            self._filters.append(filter)
            self._is_filters_dirty = True
        elif DEBUG:
            log.debug("CAN filter is already added: {{'id': '{:x}', 'is_ext_id': {:}, 'mask': '{:x}'}}".format(id, is_ext_id, mask))  # NOTE: Outputs hex values

        if apply and self._is_filters_dirty:
            self.apply_filters()

        return ret

    @Decorators.ensure_open
    def apply_filters(self):
        if DEBUG:
            log.debug("Applying {:} filter(s) to CAN bus instance".format(len(self._filters)))

        self._bus.set_filters(list(self._filters))
        self._is_filters_dirty = False

    @Decorators.ensure_open
    def receive(self, timeout=1, expect=True):
        msg = self._bus.recv(timeout=timeout)
        if expect and not msg:
            raise Exception("No CAN message received within timeout of {:} second(s)".format(timeout))

        return msg

    @Decorators.ensure_open
    def send(self, *messages, **kwargs):
        for msg in messages:
            # TODO HN
            #if DEBUG:
            log.info("Sending CAN message {:}".format(msg))

            self._bus.send(msg, **kwargs)

    def send_flow_control_reply_for(self, message, accept_frames=0x00, separation_time=0x00, id_resolvers=[]):
        if message.data[0] & 0xF0 != FRAME_TYPE_FF:
            raise ValueError("CAN message must be of frame type '{:}'".format(FRAME_TYPES[FRAME_TYPE_FF]))

        for id_resolver in id_resolvers or [self._custom_flow_control_id_resolver]:
            arb_id = id_resolver(message)
            if arb_id != None:
                msg = can.Message(
                    is_extended_id=message.is_extended_id,
                    arbitration_id=arb_id,
                    data=bytearray([0x30, accept_frames, separation_time]))

                self.send(msg)

                return True

        log.warning("Unable to resolve flow control ID for CAN message {:}".format(message))

        return False

    @Decorators.ensure_open
    def query(self, *messages, **kwargs):
        ret = []

        skip_error_frames = kwargs.pop("skip_error_frames", False)
        skip_remote_frames = kwargs.pop("skip_remote_frames", False)

        with self.ReplyReader(self) as reader:

            # Send all messages
            self.send.undecorated(self, *messages)  # No need to call the 'ensure_open' decorator again

            # Await replies
            for msg in reader.await_replies(**kwargs):
                if msg.is_error_frame and skip_error_frames:
                    log.warning("Query is skipping error frame {:}".format(msg))
                elif msg.is_remote_frame and skip_remote_frames:
                    log.info("Query is skipping remote frame {:}".format(msg))
                else:
                    ret.append(msg)

        return ret

    @Decorators.ensure_open
    def obd_query(self, mode, pid, id=None, is_ext_id=None, auto_format=True, auto_filter=True, **kwargs):

        if is_ext_id == None:
            is_ext_id = self._bus.metadata.get("is_extended_id", False)

        if id == None:
            if is_ext_id:
                id = 0x18DB33F1
            else:
                id = 0x7DF

        data = bytearray([mode, pid])
        if auto_format:
            data = bytearray([len(data)]) + data

        # Ensure filter to listen for OBD responses only
        if auto_filter:
            if is_ext_id:
                self.ensure_filter(id=0x18DAF100, is_ext_id=is_ext_id, mask=0x1FFFFF00, clear=True)
            else:
                self.ensure_filter(id=0x7E8, is_ext_id=is_ext_id, mask=0x7F8, clear=True)  # IDs in range 0x7E8-0x7EF

        # Setup default flow control
        kwargs.setdefault("flow_control", [self.FLOW_CONTROL_CUSTOM, self.FLOW_CONTROL_OBD])

        msg = can.Message(arbitration_id=id, data=data, is_extended_id=is_ext_id)
        res = self.query.undecorated(self, msg, **kwargs)  # No need to call the 'ensure_open' decorator again

        return res

    @Decorators.ensure_open
    def j1939_query():
        raise NotImplementedError("Not yet available")

    @Decorators.ensure_open
    def monitor_until(self, on_msg_func, duration=1, limit=None, receive_timeout=0.2, skip_error_frames=False, keep_listening=False, buffer_size=0):

        if not duration and not limit:
            raise ValueError("Duration and/or limit must be specified")

        if duration and receive_timeout > duration:
            raise ValueError("Receive timeout cannot exceed duration")

        if self._monitor_listener == None:
            log.info("Creating monitor listener buffer of size {:}".format(buffer_size))

            # Create and add listener
            self._monitor_listener = BufferedReader(capacity=buffer_size)
            self._notifier.add_listener(self._monitor_listener)
        else:
            if self._monitor_listener.capacity != buffer_size:
                if self._monitor_listener.is_empty():
                    log.info("Changing buffer size of monitor listener from {:} to {:}".format(self._monitor_listener.capacity, buffer_size))

                    # Remove listener if currently added
                    if self._monitor_listener in self._notifier.listeners:
                        self._notifier.remove_listener(self._monitor_listener)

                    # Create and add listener with changed buffer size
                    self._monitor_listener = BufferedReader(capacity=buffer_size)
                    self._notifier.add_listener(self._monitor_listener)
                else:
                    log.warning("Unable to change buffer size of monitor listener from {:} to {:} because queue is not empty".format(self._monitor_listener.capacity, buffer_size))

        try:
            start = timer()
            count = 0
            while True:
                msg = self._monitor_listener.next(block=duration > 0 or count == 0, timeout=receive_timeout)  # Always wait for the first frame
                if msg == None:
                    if not duration:
                        log.info("Monitor reached end of buffer - received {:} frame(s) in total".format(count))

                        break
                else:

                    # Skip error frames?
                    if msg.is_error_frame and skip_error_frames:
                        log.warning("Monitor is skipping error frame: {:}".format(msg))
                    else:
                        on_msg_func(msg)

                    # Check if limit has been reached (including any skipped error frames)
                    count += 1
                    if limit and count >= limit:
                        log.info("Monitor limit of {:} frame(s) is reached".format(limit))

                        break

                # Check if duration has been reached
                if duration and (timer() - start) >= duration:
                    log.info("Monitor duration of {:} second(s) is reached - received {:} frame(s) in total".format(duration, count))

                    break
        finally:
            if not keep_listening:
                if self._monitor_listener in self._notifier.listeners:
                    self._notifier.remove_listener(self._monitor_listener)
                    log.info("Monitor listener removed")

                self._monitor_listener = None


    @Decorators.ensure_open
    def dump_until(self, file, duration=2, limit=None, receive_timeout=0.5, skip_error_frames=False, keep_listening=False, buffer_size=0, **kwargs):

        if file.endswith(".asc"):
            writer = can.io.ASCWriter(file, **kwargs)
        elif file.endswith(".blf"):
            writer = can.io.BLFWriter(file, **kwargs)
        elif file.endswith(".csv"):
            writer = can.io.CSVWriter(file, **kwargs)
        elif file.endswith(".db"):
            writer = can.io.SqliteWriter(file, **kwargs)
        elif file.endswith(".log"):
            writer = can.io.CanutilsLogWriter(file, **kwargs)
        else:
            ValueError("Unsupported file extension")

        try:
            return self.monitor_until.undecorated(self, writer,  # No need to call the 'ensure_open' decorator again
                duration=duration,
                limit=limit,
                receive_timeout=receive_timeout,
                skip_error_frames=skip_error_frames,
                keep_listening=keep_listening,
                buffer_size=buffer_size)
        finally:
            writer.stop()

    @Decorators.ensure_open
    def play(self, *files, **kwargs):

        ignore_timestamps    = kwargs.get("ignore_timestamps", False)
        min_gap              = kwargs.get("min_gap", 0.0001)
        skip_gaps_gt         = kwargs.get("skip_gaps_gt", 60*60*24),
        include_error_frames = kwargs.get("include_error_frames", True)

        total = 0
        sent = 0
        for file in files:

            reader = can.io.LogReader(file)
            try:
                in_sync = can.io.MessageSync(reader,
                    timestamps=ignore_timestamps,
                    gap=min_gap,
                    skip=skip_gaps_gt)

                for msg in in_sync:
                    total += 1

                    if msg.is_error_frame and not include_error_frames:
                        continue

                    self._bus.send(msg)
                    sent += 1
            finally:
                reader.stop()

        return total, sent


class BufferedReader(can.listener.Listener):

    def __init__(self, capacity=0):
        self._buffer = Queue.Queue(maxsize=capacity)
        self._overflows = 0

    @property
    def capacity(self):
        return self._buffer.maxsize

    def on_message_received(self, msg):
        try:
            if DEBUG:
                log.debug("CAN buffered reader got message {:}".format(msg))

            self._buffer.put(msg, False)

            # Reset overflow counter
            if self._overflows > 0:
                log.warning("CAN buffered reader with capacity of {:} recovered from overflow - {:} message(s) was lost".format(self.capacity, self._overflows))

                self._overflows = 0

        except Queue.Full:

            # Only log once when changing state
            if self._overflows == 0:
                log.warning("CAN buffered reader with capacity of {:} is full and messages are overflowing".format(self.capacity))

            self._overflows += 1

    def is_full(self):
        return self._buffer.full()

    def is_empty(self):
        return self._buffer.empty()

    def next(self, block=True, timeout=0.5):
        try:
            return self._buffer.get(block, timeout)
        except Queue.Empty:
            return None


MSG_MAP = {
    "id": "arbitration_id",
    "ts": "timestamp",
}

def msg_to_dict(src):
    ret = {}

    for key, val in MSG_MAP.iteritems():
        ret[key] = getattr(src, val)

    ret["data"] = binascii.hexlify(src.data)

    return ret

def dict_to_msg(src):
    kwargs = {MSG_MAP.get(k, k): v for k, v in src.iteritems()}

    kwargs["data"] = binascii.unhexlify(kwargs["data"])

    return can.Message(**kwargs)

def msg_to_str(src, separator="#"):
    return "{:02x}{:}{:}".format(
        src.arbitration_id,
        separator * (2 if src.is_fd else 1),
        binascii.hexlify(src.data))

def str_to_msg(src, separator="#"):
    arb_id_str, data_str = src.split(separator, 1)

    arb_id = int(arb_id_str, 16)
    is_fd = data_str.startswith(separator)
    data = bytearray.fromhex(data_str[1:] if is_fd else data_str)

    # If ID is more than 11 bits, use extended ID (29bit header)
    is_ext_id = len(bin(arb_id)) - 2 > 11

    return can.Message(
        is_extended_id=is_ext_id,
        arbitration_id=arb_id,
        is_fd=is_fd,
        data=data)

def decode_msg_from(val, **kwargs):
    if isinstance(val, can.Message):
        return val
    elif isinstance(val, string_types):
        return str_to_msg(val, **kwargs)
    elif isinstance(val, dict):
        return dict_to_msg(val, **kwargs)
    else:
        raise ValueError("Unsupported type")

def encode_msg_to(kind, msg, **kwargs):
    if kind == "obj":
        return msg
    elif kind == "str":
        return msg_to_str(msg, **kwargs)
    elif kind == "dict":
        return msg_to_dict(msg, **kwargs)
    else:
        raise ValueError("Unsupported type")

def obd_reply_id_for(msg):
    ret = None

    if msg.is_extended_id:
        if (msg.arbitration_id & 0x1FFFFF00) == 0x18DAF100:
            ret = 0x18DA00F1 + ((msg.arbitration_id & 0xFF) << 8)
    else:
        if (msg.arbitration_id & 0x7F8) == 0x7E8:
            ret = msg.arbitration_id - 0x08

    if not ret:
        log.info("Unable to determine OBD reply ID for CAN message {:}".format(msg))

    return ret
