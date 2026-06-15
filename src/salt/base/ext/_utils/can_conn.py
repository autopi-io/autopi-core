import binascii
import can
import logging
import Queue
import struct
import subprocess
from abc import abstractmethod
from enum import Enum

from can_exceptions import CANDisallowedByConfigurationWarning
from j1939_util import J1939Query, QueryObject

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


class ConfigurableSocketcanBus(can.interfaces.socketcan.SocketcanBus):
    def __init__(self, allow_sending_can_frames, *args, **kwargs):
        super(ConfigurableSocketcanBus, self).__init__(*args, **kwargs)
        self._allow_sending_can_frames = allow_sending_can_frames

    @property
    def allow_sending_can_frames(self):
        return self._allow_sending_can_frames

    @allow_sending_can_frames.setter
    def allow_sending_can_frames(self, value):
        self._allow_sending_can_frames = value

    def send(self, *args, **kwargs):
        if self._allow_sending_can_frames:
            return super(ConfigurableSocketcanBus, self).send(*args, **kwargs)
        else:
            raise CANDisallowedByConfigurationWarning("Sending CAN frames not allowed. allow_sending_can_frames is False")

    def send_periodic(self, *args, **kwargs):
        if self._allow_sending_can_frames:
            return super(ConfigurableSocketcanBus, self).send_periodic(*args, **kwargs)
        else:
            raise CANDisallowedByConfigurationWarning("Sending CAN frames not allowed. allow_sending_can_frames is False")


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
                        self._bus.stats["last_error"] = err

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
                if self.outer._notifier:
                    self.outer._notifier.remove_listener(self._listener)
            except:
                log.exception("Failed to remove listener from bus notifier")

        def await_replies(self, 
                          nice_flow_control=None, 
                          timeout=0.2, 
                          flow_control=False, 
                          query_instance=None,
                          replies=None, 
                          skip_error_frames=True, 
                          skip_remote_frames=True, 
                          strict=True, 
                          ensure_filtering=True, 
                          **kwargs):
            ret = []

            if query_instance:
                total_count = 0
                while True:
                    msg = self._listener.next(timeout=timeout)
                    if msg == None:  # Timeout
                        query_instance.receive(msg)
                        break

                    if msg.is_error_frame:
                        if skip_error_frames:
                            log.info("Skipping received CAN reply message marked as an error frame: {:}".format(msg))

                            continue
                        else:
                            log.info("Received CAN reply message marked as an error frame: {:}".format(msg))

                    elif msg.is_remote_frame:
                        if skip_remote_frames:
                            log.info("Skipping received CAN reply message marked as a remote frame: {:}".format(msg))

                            continue
                        else:
                            log.info("Received CAN reply message marked as a remote frame: {:}".format(msg))

                    # Ensure that we do not get messages not matching filters
                    if ensure_filtering:
                        if not self.outer._bus.filters:
                            log.warning("Received CAN message reply without any filters applied: {:}".format(msg))
                        elif not self.outer._bus._matches_filters(msg):
                            log.warning("Skipping received CAN message reply which should have already been filtered out: {:}".format(msg))

                            continue

                    query_state, frame_action = query_instance.receive(msg, **kwargs)

                    if frame_action == query_instance.FrameAction.KEEP:
                        ret.append(msg)

                    total_count += 1

                    if query_state == QueryObject.QueryState.COMPLETE:
                        break

                    # Stop if replies is met
                    if replies > 0 and total_count >= replies:
                        break
            else:
                if isinstance(flow_control, list):
                    for name in flow_control:
                        func = self.outer._flow_control_id_resolvers.get(name, None)
                        if not func:
                            raise ValueError("No flow control ID resolver found for '{:}'".format(name))

                        kwargs.setdefault("id_resolvers", []).append(func)

                count = 0
                while True:
                    msg = self._listener.next(timeout=timeout)
                    if msg == None:  # Timeout
                        if strict:
                            if replies > 0:
                                raise Exception("No CAN message reply ({:}/{:}) received within timeout of {:} second(s)".format(count, replies, timeout))
                            elif count == 0:
                                raise Exception("No CAN message reply received within timeout of {:} second(s)".format(timeout))

                        break

                    frame_type = None
                    if msg.is_error_frame:
                        if skip_error_frames:
                            log.info("Skipping received CAN reply message marked as an error frame: {:}".format(msg))

                            continue
                        else:
                            log.info("Received CAN reply message marked as an error frame: {:}".format(msg))

                    elif msg.is_remote_frame:
                        if skip_remote_frames:
                            log.info("Skipping received CAN reply message marked as a remote frame: {:}".format(msg))

                            continue
                        else:
                            log.info("Received CAN reply message marked as a remote frame: {:}".format(msg))

                    else:  # Data frame

                        # Determine frame type
                        frame_type = msg.data[0] & 0xF0

                        if DEBUG:
                            log.debug("Received CAN reply message considered as a data frame of type '{:}': {:}".format(FRAME_TYPES.get(frame_type, "unknown"), msg))

                    # Ensure that we do not get messages not matching filters
                    if ensure_filtering:
                        if not self.outer._bus.filters:
                            log.warning("Received CAN message reply without any filters applied: {:}".format(msg))
                        elif not self.outer._bus._matches_filters(msg):
                            log.warning("Skipping received CAN message reply which should have already been filtered out: {:}".format(msg))

                            continue

                    ret.append(msg)
                    count += 1

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
            "bitrate": 500000,
            "allow_interface_changes": True,
            "allow_sending_can_frames": True
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

    @property
    def allow_sending_can_frames(self):
        return self._settings.get("allow_sending_can_frames")

    @allow_sending_can_frames.setter
    def allow_sending_can_frames(self, value):
        if value != self.allow_sending_can_frames:
            self._settings["allow_sending_can_frames"] = value
            self._bus.allow_sending_can_frames = value

    def setup(self, **settings):

        if DEBUG:
            log.debug("Applying settings {:}".format(settings))

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
        log.info("Updated settings {:}".format(settings))

    def open(self):

        # Retrieve settings to open with
        local_settings = self._settings.copy()
        channel = local_settings.pop("channel", "can0")
        receive_own_messages = local_settings.pop("receive_own_messages", False)
        notifier_timeout = local_settings.pop("notifier_timeout", 1.0)
        autodetect = self._settings.pop("autodetect", False)
        allow_interface_changes = local_settings.pop("allow_interface_changes")
        allow_sending_can_frames = local_settings.pop("allow_sending_can_frames")

        # Ensure closed
        self.close()

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
            self._ensure_interface_up(
                channel, 
                **local_settings
            )

            # Set up cantools instances
            self._ensure_bus(
                channel, 
                receive_own_messages,
                local_settings.get("dbitrate", None) != None,
                notifier_timeout,
                allow_sending_can_frames
            )

    def _bring_interface_up_if_allowed(self, **kwargs):
        if self._settings.get("allow_interface_changes"):
            __salt__["socketcan.up"](**kwargs)
        else:
            log.debug("Disallowing socketcan.up due to allow_interface_changes flag")

    def _bring_interface_down_if_allowed(self, **kwargs):
        if self._settings.get("allow_interface_changes"):
            __salt__["socketcan.down"](**kwargs)
        else:
            log.info("Disallowing socketcan.down due to allow_interface_changes flag")

    def _all_threads_alive(self, thread_list):
        all_alive = True
        for thread in thread_list:
            all_alive = all_alive & thread.is_alive()
        return all_alive

    def _is_notifier_alive(self):
        return bool(self._notifier) and self._all_threads_alive(self._notifier._readers)

    def _ensure_interface_up(self, interface, **settings):
        try:
            self._bring_interface_up_if_allowed(interface=interface, **settings)
        except:
            log.exception("Failed to bring up '{:}' interface - forcing it down before trying again".format(interface))

            self._bring_interface_down_if_allowed(interface=interface)
            self._bring_interface_up_if_allowed(interface=interface, **settings)

    def _ensure_bus(self, channel, receive_own_messages, fd, notifier_timeout, allow_sending_can_frames):

        if not self._bus:
            self._bus = ConfigurableSocketcanBus(
                allow_sending_can_frames,
                channel=channel,
                receive_own_messages=receive_own_messages,
                fd=fd
            )
            setattr(self._bus, "metadata", {})
            setattr(self._bus, "stats", {})

        if self._filters:
            log.info("Re-applying {:} filter(s) to CAN bus instance".format(len(self._filters)))
            self._bus.set_filters(list(self._filters))
            self._is_filters_dirty = False

        if not self._notifier:
            self._notifier = can.Notifier(self._bus, [], timeout=notifier_timeout)  # No listeners for now

    def is_open(self):
        if self._bus != None:

            if not self._is_notifier_alive():
                return False

            # Check for any last error
            if "last_error" in self._bus.stats:
                last_err_msg = str(self._bus.stats.pop("last_error", None))

                # Keep track of consecutive errors
                consec_errs = self._bus.stats.setdefault("consecutive_errors", {})
                consec_errs[last_err_msg] = consec_errs.get(last_err_msg, 0) + 1
                if sum(consec_errs.values()) >= 5:
                    log.warning("The CAN connection is no longer considered open due to 5 consecutive CAN errors, digest: {:}".format(consec_errs))

                    return False

                log.warning("Checking the state of the interface due to the latest CAN connection error: {:}".format(last_err_msg))
                if self.interface_state() != INTERFACE_STATE_UP:
                    return False

            # Clear any consecutive errors
            elif "consecutive_errors" in self._bus.stats:
                self._bus.stats.pop("consecutive_errors", None)

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

        # Bring down interface if not already or force
        if force or self.interface_state() != INTERFACE_STATE_DOWN:
            self._bring_interface_down_if_allowed(interface=self.channel)
            
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
                    msgs = self.obd_query(0x01, 0x00, is_ext_id=id_bits > 11, timeout=receive_timeout, strict=False, skip_error_frames=True, skip_remote_frames=True)
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

    def _j1939_autodetect(self, channel=None, try_bitrates=[250000, 500000], receive_timeout=0.2):
        channel = channel or self.channel

        for bitrate in try_bitrates:
            self.setup(channel=channel, bitrate=bitrate)

            # Query for DM1 PGN
            try:
                msgs = self.j1939_query(65226, timeout=receive_timeout, strict=False, skip_error_frames=True, skip_remote_frames=True)
                if msgs:
                    self._bus.metadata["is_autodetected"] = True
                    self._bus.metadata["is_extended_id"] = True
                    self._bus.metadata["is_j1939_supported"] = True

                    log.info("J1939 autodetect was successful using settings {:}".format(self._settings))

                    return True
                else:
                    log.info("J1939 autodetect did not receive any reply messages within timeout of {:} second(s) using settings {:}".format(receive_timeout, self._settings))

            except Exception as ex:
                log.info("J1939 autodetect failed to query for DM1 PGN using settings {:}: {:}".format(self._settings, ex))

        log.warning("J1939 autodetect failed")
        self.close()

        return False

    def interface_state(self, channel=None):
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
    def receive(self, timeout=1, expect=True):
        msg = self._bus.recv(timeout=timeout)
        if expect and not msg:
            raise Exception("No CAN message received within timeout of {:} second(s)".format(timeout))

        return msg

    @Decorators.ensure_open
    def send(self, *messages, **kwargs):
        """
        Sends one or more messages on the CAN bus.

        Arguments:
          - *messages (can.Message): CAN messages to send.
        """

        for msg in messages:
            if DEBUG:
                log.debug("Sending CAN message {:}".format(msg))

            self._bus.send(msg, **kwargs)

    def send_flow_control_reply_for(self, message, accept_frames=0x00, separation_time=0x00, extended_address=None, zero_padding=None, id_resolvers=[]):
        if message.data[0] & 0xF0 != FRAME_TYPE_FF:
            raise ValueError("CAN message must be of frame type '{:}'".format(FRAME_TYPES[FRAME_TYPE_FF]))

        for id_resolver in id_resolvers or [self._custom_flow_control_id_resolver]:
            arb_id = id_resolver(message)
            if arb_id != None:

                data = [0x30, accept_frames, separation_time]
                if extended_address != None:
                    data = [extended_address] + data

                msg = can.Message(
                    is_extended_id=message.is_extended_id,
                    arbitration_id=arb_id,
                    data=bytearray(data).ljust(zero_padding, "\0") if zero_padding else bytearray(data))

                self.send(msg)

                return True

        log.warning("Unable to resolve flow control ID for CAN message {:}".format(message))

        return False

    @Decorators.ensure_open
    def query(self, *messages, **kwargs):
        """
        Queries by sending one or more request messages on the CAN bus and then waits for one or more reply messages.

        Arguments:
          - *messages (can.Message): CAN request messages to send.

        Optional arguments:
          - ensure_filtering (bool): Ensure that reply messages not matching the filters are excluded. Default value is 'True'.
          - flow_control (list): List of flow control ID resolvers to enable. Options are 'obd' and 'custom'. Default value is 'False' (disabled).
          - replies (int): The amount of reply messages to wait for within a timeout.
          - skip_error_frames (bool): Skip any reply message marked as an error frame. Default value is 'True'.
          - skip_remote_frames (bool): Skip any reply message marked as a remote frame. Default value is 'True'.
          - strict (bool): Raise an error when no reply messages are received or if the amount of expected reply messages is not met within the timeout. Default value is 'True'.
          - timeout (float): The amount of time in seconds to wait for a reply message. Default value is '0.2'.
        """

        ret = []

        try:
            with self.ReplyReader(self) as reader:

                # Send all messages
                self.send.undecorated(self, *messages)  # No need to call the 'ensure_open' decorator again

                # Await replies
                for msg in reader.await_replies(**kwargs):
                    ret.append(msg)
        finally:
            if not ret:
                if DEBUG:
                    log.debug("Flushing transmit buffer due to no query response")

                # NOTE: Does not appear to be implemented in the SocketCAN interface, so probably no effect
                self._bus.flush_tx_buffer()

        return ret

    @Decorators.ensure_open
    def obd_query(self, mode, pid, id=None, is_ext_id=None, auto_format=True, auto_filter=True, **kwargs):
        """
        Queries an OBD-II PID on the CAN bus.

        Arguments:
          - mode (str): Service section of the PID.
          - pid (str): Code section of the PID.

        Optional arguments, OBD-II specific:
          - auto_filter (bool): Ensure to apply filtering to only include OBD-II reply messages. Default value is 'True'.
          - auto_format (bool): Ensure that the PID request message always has a fixed data length of 8 bytes (zero padding). Default value is 'True'.
          - id (int): Use a custom CAN arbitration ID for the PID request message. 
          - is_ext_id (int): Enforce to use extended CAN arbitration ID or not (29 or 11 bit) for the PID request message.

        Optional arguments, general:
          - ensure_filtering (bool): Ensure that reply messages not matching the filters are excluded. Default value is 'True'.
          - flow_control (list): List of flow control ID resolvers to enable. Options are 'obd' and 'custom'. Default value is 'False' (disabled).
          - replies (int): The amount of reply messages to wait for within a timeout.
          - skip_error_frames (bool): Skip any reply message marked as an error frame. Default value is 'True'.
          - skip_remote_frames (bool): Skip any reply message marked as a remote frame. Default value is 'True'.
          - strict (bool): Raise an error when no reply messages are received or if the amount of expected reply messages is not met within the timeout. Default value is 'True'.
          - timeout (float): The amount of time in seconds to wait for a reply message. Default value is '0.2'.
        """

        if is_ext_id == None:
            is_ext_id = self._bus.metadata.get("is_extended_id", False)

        if id == None:
            if is_ext_id:
                id = 0x18DB33F1
            else:
                id = 0x7DF

        data = [mode, pid]
        if auto_format:
            data = [len(data)] + data
            kwargs.setdefault("zero_padding", 8)

        if "extended_address" in kwargs:
            data = [kwargs["extended_address"]] + data

        # Ensure filter to listen for OBD responses only
        if auto_filter:
            if is_ext_id:
                self.ensure_filter(id=0x18DAF100, is_ext_id=is_ext_id, mask=0x1FFFFF00, clear=True)
            else:
                self.ensure_filter(id=0x7E8, is_ext_id=is_ext_id, mask=0x7F8, clear=True)  # IDs in range 0x7E8-0x7EF

        # Setup default flow control
        kwargs.setdefault("flow_control", [self.FLOW_CONTROL_CUSTOM, self.FLOW_CONTROL_OBD])

        data = bytearray(data)
        if "zero_padding" in kwargs:
            data = data.ljust(kwargs["zero_padding"], "\0")
        
        msg = can.Message(
            arbitration_id=id,
            data=data,
            is_extended_id=is_ext_id)
    
        # No need to call the 'ensure_open' decorator again
        res = self.query.undecorated(self, 
                                     msg, 
                                     **kwargs)
        return res

    @Decorators.ensure_open
    def j1939_query(self, 
                    pgn, 
                    priority=6, 
                    destination_address=0, 
                    source_address=249, 
                    auto_filter=True, 
                    auto_filter_mask=0x00FFFF00, 
                    auto_tp=True,
                    **kwargs):
        """
        Queries a J1939 PGN on the CAN bus.

        Arguments:
          - pgn (int): Number of the PGN to query.

        Optional arguments, J1939 specific:
          - priority (int): The priority to use for the request message. Default value is '6'.
          - destination_address (int): The destination address of the request message. Default value is '0'.
          - source_address (int): The source address of the request message. Default value is '249' (Service Tool).
          - auto_filter (bool): Ensure to apply filtering to only include reply message for the specific PGN. Default value is 'True'.
          - auto_filter_mask (int): The bitmask to use when the filter is applied (to all frame types including TP). Default value is '0x00FFFF00'.
          - auto_tp (bool): Automatically enable Transport Protocol (TP) for multi-frame messages

        Optional arguments, general:
          - ensure_filtering (bool): Ensure that reply messages not matching the filters are excluded. Default value is 'True'.
          - flow_control (list): List of flow control ID resolvers to enable. Options are 'obd' and 'custom'. Default value is 'False' (disabled).
          - replies (int): The amount of reply messages to wait for within a timeout.
          - skip_error_frames (bool): Skip any reply message marked as an error frame. Default value is 'True'.
          - skip_remote_frames (bool): Skip any reply message marked as a remote frame. Default value is 'True'.
          - strict (bool): Raise an error when no reply messages are received or if the amount of expected reply messages is not met within the timeout. Default value is 'True'.
          - timeout (float): The amount of time in seconds to wait for a reply message. Default value is '0.2'.
        """
        j1939_query = J1939Query(pgn,
                                self.send,
                                priority=priority,
                                own_address=source_address,
                                ecu_address=destination_address,
                                auto_tp=auto_tp,
                                auto_filter_mask=auto_filter_mask,
                                strict=kwargs.get("strict", True))

        if auto_filter:
            filters = j1939_query.get_filters()
            for f in filters:
                self.ensure_filter(**f)

        msg = j1939_query.get_query_msg()

        # No need to call the 'ensure_open' decorator again
        res = self.query.undecorated(self, 
                                     msg, 
                                     query_instance=j1939_query,
                                     **kwargs)  

        return res

    @Decorators.ensure_open
    def monitor_until(self, on_msg_func, duration=1, limit=None, receive_timeout=0.2, skip_error_frames=False, keep_listening=False, buffer_size=0):
        """
        Monitors messages on the CAN bus until a limit and/or duration is reached.

        Arguments:
          - on_msg_func (func): Function that will be called on each received message.

        Optional arguments:
          - duration (int): How many seconds to record data? Default value is '1'.
          - limit (int): The maximum number of messages to read.
          - receive_timeout (float): The amount of time in seconds to wait for a reply message. Default value is '0.2'.
          - skip_error_frames (bool): Skip any reply message marked as an error frame. Default value is 'False'.
          - keep_listening (bool): Continue listening for messages in the background? Default value is 'False'.
          - buffer_size (int): The limit of messages that the internal queue can hold. If the value is less than or equal to zero, the queue size is infinite. Default value is '0'.
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
            # First make sure that the listener is actually added to the notifier
            if self._monitor_listener not in self._notifier.listeners:
                """
                NOTE NV: Sometimes, it can happen that the connection class needs to get reconfigured. This causes
                the notifier to also get recreated, which in turn causes the _monitor_listener entity to disappear
                from the notifier causing workers such as the can_logger (in this debugging case) to not receive any
                of the messages that are actually being pushed to the bus. This is the reasoning behind this code.
                This shouldn't occur that often, usually caused by the autodetect mechanism or any other reconfiguring
                or switching of protocol/channel/can interface.
                """

                self._notifier.add_listener(self._monitor_listener)

            # Then proceed to make any other changes we might need to make to the listner
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
        Stores messages from the CAN bus to a file until a limit or duration is reached.

        Arguments:
          - file (str): Write data to a file with the given name. Supported file extensions are '.asc', '.blf', '.csv', '.db' and '.log'.

        Optional arguments:
          - duration (int): How many seconds to record data? Default value is '1'.
          - limit (int): The maximum number of messages to read.
          - receive_timeout (float): The amount of time in seconds to wait for a reply message. Default value is '0.2'.
          - skip_error_frames (bool): Skip any reply message marked as an error frame. Default value is 'False'.
          - keep_listening (bool): Continue listening for messages in the background? Default value is 'False'.
          - buffer_size (int): The limit of messages that the internal queue can hold. If the value is less than or equal to zero, the queue size is infinite. Default value is '0'.

        Optional arguments for ASC and BLF files:
          - channel (int): The default value to use when a message does not have a channel set. Default value is '1'.

        Optional arguments for CSV file:
          - append (bool): Append messages to an existing file where no header line is written or truncate and start with a newly written header line? Default value is 'False'.


        Optional arguments for DB file (SQLite):
          - table_name (str): The name of the table to store messages in. Default value is 'messages'.

        Optional arguments for log file:
          - channel (str): The default value to use when a message does not have a channel set. Default value is 'vcan0'.
          - append (bool): Append messages to any existing file or truncate it?  Default value is 'False'.
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
        Sends all messages from one or more dump files on the CAN bus.

        Arguments:
          - *files (str): Specify one or more dump files for playback.

        Optional arguments:
          - ignore_timestamps (bool): Ignore the timestamps of the messages and use the 'min_gap' parameter as the time between messages instead. Default value is 'False'.
          - min_gap (float): Minimum time between sent messages in seconds. Default value is '0.0001'.
          - skip_gaps_gt (float): Skip periods of inactivity greater than this (in seconds). Default value is '86400'.
          - include_error_frames (bool): Also send messages marked as error frames? Default value is 'True'.
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
    """
    Formats a raw python-can Message object to a string with a separator between the header and data sections.
    """

    format_string = "{:03x}{:}{:}"

    if src.is_extended_id:
        format_string = "{:08x}{:}{:}"

    return format_string.format(
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
    # TODO HN: More correct to just use:
    #is_ext_id = len(arb_id_str) > 3

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
