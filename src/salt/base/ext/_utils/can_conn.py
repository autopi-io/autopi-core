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


class CANConn(object):

    class Decorators(object):

        @staticmethod
        def ensure_open(func):

            def decorator(self, *args, **kwargs):

                # Ensure connection is open
                self.ensure_open()

                try:
                    return func(self, *args, **kwargs)
                except:
                    # TODO HN: Figure out if we should close here?
                    raise

            # Add reference to the original undecorated function
            decorator.undecorated = func

            return decorator

    class ReplyReader(object):

        def __init__(self, notifier):
            self._notifier = notifier
            self._listener = None

        def __enter__(self):
            self._listener = BufferedReader()

            self._notifier.add_listener(self._listener)

            return self

        def __exit__(self, ex_type, ex_val, tb):
            try:
                self._notifier.remove_listener(self._listener)
            except:
                log.exception("Failed to remove listener from bus notifier")

        def await_replies(self, timeout=0.2, replies=None, strict=True):
            ret = []

            count = 0
            while True:
                count += 1

                reply = self._listener.next(timeout=timeout)
                if reply != None:
                    if reply.is_error_frame:
                        log.warning("Received CAN reply message marked as error frame: {:}".format(reply))

                    ret.append(reply)
                else:  # Timeout
                    if strict:
                        if replies > 0:
                            raise Exception("No CAN message reply ({:}/{:}) received within timeout of {:} second(s)".format(count, replies, timeout))
                        elif count == 1:
                            raise Exception("No CAN message reply received within timeout of {:} second(s)".format(timeout))

                    break

                # Stop if replies is met
                if replies > 0 and count >= replies:
                    break

            return ret

    def __init__(self, __salt__):
        globals()["__salt__"] = __salt__

        self._settings = {
            "channel": "can0",
            "bitrate": 500000
        }

        self._bus = None
        self._notifier = None
        self._filters = []
        self._is_filters_dirty = False
        self._monitor_listener = None

    @property
    def channel(self):
        return self._settings["channel"]

    def setup(self, **settings):

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
        settings = self._settings.copy()
        log.info("Opening CAN connection using settings: {:}".format(settings))

        channel = settings.pop("channel", "can0")
        receive_own_messages = settings.pop("receive_own_messages", False)
        notifier_timeout = settings.pop("notifier_timeout", 1.0)

        # Ensure interface is down
        if self.interface_state() != INTERFACE_STATE_DOWN:
            __salt__["socketcan.down"](interface=channel)

        # Bring up interface
        __salt__["socketcan.up"](interface=channel, **settings)

        self._bus = can.interfaces.socketcan.SocketcanBus(channel=channel, receive_own_messages=receive_own_messages)
        self._notifier = can.Notifier(self._bus, [], timeout=notifier_timeout)  # No listeners for now

        # TODO HN: Handle restart on error

    def is_open(self):
        # TODO HN: Figure out how to do this
        return self._bus != None \
            and self._bus.state != can.bus.BusState.ERROR

    def ensure_open(self):
        if not self.is_open():
            self.open()

    def close(self):

        # Shut down bus, if present
        if self._bus:
            self._bus.shutdown()

        # Bring down interface, if not already
        if self.interface_state() != INTERFACE_STATE_DOWN:
            __salt__["socketcan.down"](interface=self.channel)

    def interface_state(self, channel=None):

        # Get current state of interface
        channel = channel or self.channel
        state = __salt__["socketcan.show"](interface=channel).get("operstate", "").lower()
        log.info("CAN interface '{:}' is currently in operation state '{:}'".format(channel, state))

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
    def receive(self, timeout=1):
        """
        """

        msg = self._bus.recv(timeout=timeout)
        if not msg:
            raise Exception("No CAN message received within timeout of {:} second(s)".format(timeout))

        return msg

    @Decorators.ensure_open
    def send(self, *messages, **kwargs):
        """
        """

        for msg in messages:
            # TODO HN
            #if DEBUG:
            log.info("Sending CAN message: {}".format(msg))

            self._bus.send(msg, **kwargs)

    @Decorators.ensure_open
    def query(self, *messages, **kwargs):
        """
        """

        with self.ReplyReader(self._notifier) as reader:

            # Send all messages
            self.send.undecorated(self, *messages)  # No need to call the 'ensure_open' decorator again

            # Await replies
            return reader.await_replies(**kwargs)

    """
    obd_profiles = [
        {"bitrate": 500000, "is_ext_id": False}
        {"bitrate": 500000, "is_ext_id": True}
        {"bitrate": 250000, "is_ext_id": False}
        {"bitrate": 250000, "is_ext_id": True}
    ]

    def obd_profile(self, autodetect=False):
        if autodetect:
            for profile in obd_profiles:

                self.setup(bitrate=profile.get("bitrate", 500000))

                if self.obd_query(0x01, 0x00, is_ext_id=profile.get("is_ext_id", False))
                    self._obd_profile = profile

                    break

            if not self._obd_profile:
                raise Exception("Unable to autodetect an OBD profile")

        return self._obd_profile
    """

    @Decorators.ensure_open
    def obd_query(self, mode, pid, id=None, is_ext_id=None, auto_format=True, auto_filter=True, **kwargs):
        """
        """

        if is_ext_id == None:
            is_ext_id = self._settings.get("is_ext_id", False)  # TODO HN: Where to get this from?

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

        msg = can.Message(arbitration_id=id, data=data, is_extended_id=is_ext_id)
        res = self.query.undecorated(self, msg, **kwargs)  # No need to call the 'ensure_open' decorator again

        return res

    @Decorators.ensure_open
    def j1939_query():
        """
        """

        pass

    @Decorators.ensure_open
    def monitor_until(self, on_msg_func, duration=1, limit=None, receive_timeout=0.2, skip_error_frames=False, keep_listening=False, buffer_size=0):
        """
        """

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
        """
        """

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
        """
        """

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
            # TODO HN
            #if DEBUG:
            log.info("CAN buffered reader got message: {:}".format(msg))

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
    # TODO HN: Also support CAN-FD

    return "{:02x}{:}{:}".format(src.arbitration_id, separator, binascii.hexlify(src.data))

def str_to_msg(src, separator="#"):
    # TODO HN: Also support CAN-FD

    id_str, data_str = src.split(separator, 1)

    id = int(id_str, 16)
    data = bytearray.fromhex(data_str)

    # If ID is more than 11 bits, use extended ID (29bit headers)
    is_ext_id = len(bin(id)) - 2 > 11

    return can.Message(
        is_extended_id=is_ext_id,
        arbitration_id=id,
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
