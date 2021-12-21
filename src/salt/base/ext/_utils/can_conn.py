import binascii
import can
import logging
import Queue
import subprocess

from six import string_types
from timeit import default_timer as timer


log = logging.getLogger(__name__)

BUS_STATES = {
    can.bus.BusState.ACTIVE:  "active",
    can.bus.BusState.PASSIVE: "passive",
    can.bus.BusState.ERROR:   "error"
}


class CANConn(object):

    def __init__(self, __salt__):
        globals()["__salt__"] = __salt__

        self._settings = {}

        self._bus = None
        self._notifier = None
        self._filters = []
        self._monitor_listener = None

    @property
    def channel(self):
        return self._settings.get("channel", "can0")

    def setup(self, **settings):
        self._settings.update(settings)

    def open(self, **settings):
        self.setup(**settings)

        settings = self._settings.copy()
        channel = settings.pop("channel", "can0")
        receive_own_messages = settings.pop("receive_own_messages", False)
        notifier_timeout = settings.pop("notifier_timeout", 1.0)

        # TODO HN: Handle restart on error

        # Bring up interface
        __salt__["socketcan.up"](interface=channel, **settings)

        self._bus = can.interfaces.socketcan.SocketcanBus(channel=channel, receive_own_messages=receive_own_messages)
        self._notifier = can.Notifier(self._bus, [], timeout=notifier_timeout)  # No listeners for now

    def close(self):

        # Shut down bus if present
        if self._bus:
            self._bus.shutdown()

        # Get current state of interface
        channel = self.channel
        state = __salt__["socketcan.show"](interface=channel).get("operstate", None)
        log.info("CAN interface '{:}' is currently in operation state '{:}'".format(channel, state))

        # Bring down interface if not already
        if state != "DOWN":
            __salt__["socketcan.down"](interface=channel)

    def reopen(self, **settings):
        try:
            self.close()
        finally:
            self.open(**settings)

    def bus_state(self):
        if not self._bus:
            raise Exception("No CAN bus object present")

        res = BUS_STATES.get(self._bus.state, None)
        if not res:
            raise Exception("CAN bus is in unknown state")

        return res

    def list_filters(self):
        return self._filters

    def clear_filters(self):

        if self._filters:
            log.info("Clearing {:} CAN filter(s)".format(len(self._filters)))

        self._filters = []
        self.apply_filters()

    def add_filter(self, id=0, is_ext_id=False, mask=None):

        # Ensure hex strings are converted to integers
        if isinstance(id, string_types):
            id = int(id, 16)
        if isinstance(mask, string_types):
            mask = int(mask, 16)

        # Set mask if undefined
        if mask == None:
            if is_ext_id:
                mask = 0x1FFFFFFF
            else:
                mask = 0x7FF

        log.info("Adding CAN pass filter: {{'id': '{:x}', 'is_ext_id': {:}, 'mask': '{:x}'}}".format(id, is_ext_id, mask))

        self._filters.append({"can_id": id, "can_mask": mask, "extended": is_ext_id})
        self.apply_filters()

    def apply_filters(self):
        self._bus.set_filters(self._filters)

    def receive(self, timeout=1):
        """
        """

        msg = self._bus.recv(timeout=timeout)
        if not msg:
            raise Exception("No CAN message received within timeout of {:} second(s)".format(timeout))

        return msg

    """
    def receive_until(self, on_msg_func, duration=1, limit=100, timeout=0.2, skip_error_frames=False):
        #TODO HN: Might not make any sense without a listener?

        count = 0
        start = timer()
        while True:
            msg = self._bus.recv(timeout=timeout)
            if msg != None:
                if not msg.is_error_frame or not skip_error_frames:
                    on_msg_func(msg)
                    count += 1

                    if limit and count >= limit:
                        break

            if timer() - start >= duration:
                break

        return count
    """

    def send(self, *messages, **kwargs):
        """
        """

        for msg in messages:

            log.info("Sending CAN message: {}".format(msg))
            self._bus.send(msg, **kwargs)

    def query(self, *messages, **kwargs):
        """
        """

        with self.ReplyReader(self._notifier) as reader:

            # Send all messages
            for message in messages:
                self.send(message)

            # Await replies
            return reader.await(**kwargs)

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

                if self.obd_query("01", "00", is_ext_id=profile.get("is_ext_id", False))
                    self._obd_profile = profile

                    break

            if not self._obd_profile:
                raise Exception("Unable to autodetect an OBD profile")

        return self._obd_profile
    """

    def obd_query(self, service, pid, id="7DF", is_ext_id=None, auto_format=True, **kwargs):
        """
        """

        if is_ext_id == None:
            is_ext_id = self._obd_profile.get("is_ext_id", False)

        data = bytearray([int(service, 16), int(pid, 16)])
        if auto_format:
            data = bytearray([len(data)]) + data

        msg = can.Message(arbitration_id=int(str(id), 16), data=data, is_extended_id=is_ext_id)

        # TODO HN: Setup filters to listen for OBD responses only
        self.add_filter(id=0x7E0, is_ext_id=is_ext_id)
        self.add_filter(id=0x7E8, is_ext_id=is_ext_id)

        res = self.query(msg, **kwargs)

        return res

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
            return self.monitor_until(writer,
                duration=duration,
                limit=limit,
                receive_timeout=receive_timeout,
                skip_error_frames=skip_error_frames,
                keep_listening=keep_listening,
                buffer_size=buffer_size)
        finally:
            writer.stop()

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

        def await(self, timeout=0.2, replies=None, strict=True):
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


class BufferedReader(can.listener.Listener):

    def __init__(self, capacity=0):
        self._buffer = Queue.Queue(maxsize=capacity)
        self._overflows = 0

    @property
    def capacity(self):
        return self._buffer.maxsize

    def on_message_received(self, msg):
        try:
            # TODO HN: Remove this
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

def msg_to_str(src):
    # TODO HN: Also support CAN-FD

    return "{:02x}#{:}".format(src.arbitration_id, binascii.hexlify(src.data))

def str_to_msg(src):
    # TODO HN: Also support CAN-FD

    id_str, data_str = src.split("#", 1)

    id = int(id_str, 16)
    data = bytearray.fromhex(data_str)

    # If ID is more than 11 bits, use extended ID (29bit headers)
    is_ext_id = len(bin(id)) - 2 > 11

    return can.Message(
        is_extended_id=is_ext_id,
        arbitration_id=id,
        data=data)

def decode_msg_from(val):
    if isinstance(val, can.Message):
        return val
    elif isinstance(val, string_types):
        return str_to_msg(val)
    elif isinstance(val, dict):
        return dict_to_msg(val)
    else:
        raise ValueError("Unsupported type")

def encode_msg_to(kind, msg):
    if kind == "obj":
        return msg
    elif kind == "str":
        return msg_to_str(msg)
    elif kind == "dict":
        return msg_to_dict(msg)
    else:
        raise ValueError("Unsupported type")
