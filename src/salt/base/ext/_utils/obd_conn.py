import collections
import datetime
import logging
import obd
import obd.utils
import time

from obd.interfaces import STN11XX
from retrying import retry


log = logging.getLogger(__name__)


class OBDConn(object):

    class Decorators(object):

        @staticmethod
        def ensure_open(func):

            def decorator(self, *args, **kwargs):

                # Ensure connection is open
                self.ensure_open()

                return func(self, *args, **kwargs)

            # Add reference to the original undecorated function
            decorator.undecorated = func

            return decorator

    def __init__(self):

        # Settings
        self._device = None
        self._baudrate = None
        self._timeout = None
        self._protocol_id = "AUTO"
        self._protocol_baudrate = None
        self._protocol_verify = True

        self._obd = None

        self._can_runtime_settings = collections.OrderedDict([  # Maintain order to ensure correct call sequence
            ("can_flow_control_clear", lambda v: [self._obd.interface.can_flow_control_filters(clear=v), self._obd.interface.can_flow_control_id_pairs(clear=v)]),  # Must be called before adding, if present
            ("can_flow_control_filter", lambda v: self._obd.interface.can_flow_control_filters(add=v)),
            ("can_flow_control_id_pair", lambda v: self._obd.interface.can_flow_control_id_pairs(add=v)),
            ("can_extended_address", lambda v: self._obd.interface.set_can_extended_address(v))
        ])

        self.is_permanently_closed = False

        self.on_ensure_open = None
        self.on_status = None
        self.on_closing = None
        self.on_closed = None

        # Keep an up-to-date reference to protocol instance received from interface
        self.cached_protocol = None

        # Flag indicating if filters are applied or not
        self.has_filters = False
    
    def setup(self, **settings):

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Configuring OBD connection using settings: %s", settings)

        if not "device" in settings:
            raise ValueError("Setting 'device' must be specified")
        self._device = settings["device"]

        if not "baudrate" in settings:
            raise ValueError("Setting 'baudrate' must be specified")
        if not settings["baudrate"] in STN11XX.TRY_BAUDRATES:
            raise ValueError("Setting 'baudrate' has unsupported value")
        self._baudrate = settings["baudrate"]

        if "timeout" in settings:
            self._timeout = settings["timeout"]

        if "protocol" in settings:
            if "id" in settings["protocol"]:
                self._protocol_id = str(settings["protocol"]["id"]).upper() if settings["protocol"]["id"] not in [None, str(None), "null"] else None
            else:
                self._protocol_id = self._protocol_id
            self._protocol_baudrate = settings["protocol"].get("baudrate", self._protocol_baudrate)
            self._protocol_verify = settings["protocol"].get("verify", self._protocol_verify)

    @retry(stop_max_attempt_number=3, wait_fixed=1000)
    def open(self, force=False):

        if self.is_permanently_closed and not force:
            raise Warning("OBD connection is no longer available as it has been permanently closed")

        # Reset flag
        self.is_permanently_closed = False

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Opening OBD connection")

        try :
            self._obd = obd.OBD(
                portstr=self._device,
                baudrate=self._baudrate,
                timeout=self._timeout,
                protocol={
                    "id": self._protocol_id if self._protocol_id != "AUTO" else None,  # None value will result in autodetection
                    "baudrate": self._protocol_baudrate,
                    "verify": self._protocol_verify
                },
                load_commands=self._protocol_verify,  # Only load supported commands when protocol is verified
                interface_cls=STN11XX,
                status_callback=self._status_callback,
                fast=False
            )

            return self

        except Exception:
            log.exception("Failed to open OBD connection")

            raise

    def is_open(self):
        return self._obd != None \
            and self._obd.status() != obd.OBDStatus.NOT_CONNECTED

    def ensure_open(self):
        is_open = self.is_open()

        if self.on_ensure_open:
            self.on_ensure_open(is_open)

        if not is_open:
            self.open()

    def close(self, permanent=False):

        if not self.is_open():
            raise Exception("Already closed")

        if self.on_closing:
            try:
                self.on_closing()
            except:
                log.exception("Error in 'on_closing' event handler")

        self._obd.close()
        self._obd = None
        self.is_permanently_closed = permanent

        if self.on_closed:
            try:
                self.on_closed()
            except:
                log.exception("Error in 'on_closed' event handler")

    @Decorators.ensure_open
    def serial(self):
        return self._obd.connection()

    @Decorators.ensure_open
    def interface(self):
        return self._obd.interface

    @Decorators.ensure_open
    def status(self):
        serial = self._obd.connection()

        return {
            "status": self._obd.status(),
            "serial": {
                "port": serial.portstr,
                "baudrate": serial.baudrate,
            },
        }

    @Decorators.ensure_open
    def runtime_settings(self):
        return self._obd.interface.runtime_settings()

    @Decorators.ensure_open
    def protocol(self, verify=False):
        protocol = self._obd.protocol(verify=verify)

        return {
            "id": protocol.ID,
            "name": protocol.NAME,
            "autodetected": protocol.autodetected,
            "ecus": protocol.ecu_map.values(),
            "baudrate": getattr(protocol, "baudrate", None),  # Only available for 'STN11XX' interface
        }

    @Decorators.ensure_open
    def supported_protocols(self):
        ret = collections.OrderedDict({"AUTO": {"name": "Autodetect", "interface": "ELM327"}})
        ret.update({k: {"name": v.NAME, "interface": v.__module__[v.__module__.rfind(".") + 1:].upper()} for k, v in self._obd.supported_protocols().iteritems()})

        return ret

    @Decorators.ensure_open
    def change_protocol(self, ident, baudrate=None, verify=True):
        if ident == None:
            raise ValueError("Protocol must be specified")

        # Enforce type and formatting
        ident = str(ident).upper()
        baudrate = int(baudrate) if baudrate != None else None

        if not ident in self.supported_protocols.undecorated(self):  # No need to call the 'ensure_open' decorator again
            raise ValueError("Unsupported protocol specified")

        if ident == "AUTO":
            ident = None
            verify = True  # Force verify when autodetecting protocol

        self._obd.change_protocol(ident, baudrate=baudrate, verify=verify)

        # When protocol is changed we assume that any existing filters are lost
        self.has_filters = False

    @Decorators.ensure_open
    def ensure_protocol(self, ident, baudrate=None, verify=True):

        # Validate input
        if ident == None:
            if baudrate != None:
                raise ValueError("Protocol must also be specified when baudrate is specified")

            # No protocol given - use protocol from settings as default if defined
            if self._protocol_id != None:
                ident = self._protocol_id
                baudrate = self._protocol_baudrate
                # IMPORTANT: We do not use verify from settings but always the given value
            else:

                # No protocol requested and no default available
                return

        # Enforce type and formatting
        ident = str(ident).upper()
        baudrate = int(baudrate) if baudrate != None else None

        # Check current protocol
        try:
            protocol = self._obd.protocol(verify=verify)  # Default is to verify protocol on each call

            # Check if already autodetected
            if ident == "AUTO" and protocol.autodetected \
                or ident == protocol.ID:  # Or if already set

                # Finally check if baudrate matches
                if baudrate == None or baudrate == getattr(protocol, "baudrate", None):

                    return  # No changes
        except:
            log.exception("Failed to determine current protocol")

        # We need to change protocol and/or baudrate
        self.change_protocol.undecorated(self, ident, baudrate=baudrate, verify=verify)  # No need to call the 'ensure_open' decorator again

    @Decorators.ensure_open
    def ensure_runtime_settings(self, settings, filter=False):

        # Apply CAN settings in correct order
        for name, func in self._can_runtime_settings.iteritems():
            if name in settings:
                func(settings.pop(name) if filter else settings[name])

    @Decorators.ensure_open
    def query(self, cmd, formula=None, **kwargs):
        res = self._obd.query(cmd, **kwargs)

        # Calculate formula if given
        if formula != None:
            res.value = self._calc_formula(formula, res.messages)

        return res

    @Decorators.ensure_open
    def supported_commands(self):
        return self._obd.supported_commands

    @Decorators.ensure_open
    def send(self, msg, **kwargs):

        # Filter out and apply advanced runtime settings if any
        self.ensure_runtime_settings.undecorated(self, kwargs, filter=True)  # No need to call the 'ensure_open' decorator

        # Parse out header if found
        hash_pos = msg.find("#")
        if hash_pos > 0:
            kwargs["header"] = msg[:hash_pos]
            msg = msg[hash_pos + 1:]

        res = self._obd.send(msg, **kwargs)

        return res

    @Decorators.ensure_open
    def send_all(self, msgs, delay=None, **kwargs):

        ret = []

        # Filter out and apply advanced runtime settings if any
        self.ensure_runtime_settings.undecorated(self, kwargs, filter=True)  # No need to call the 'ensure_open' decorator

        for msg in msgs:

            # Parse out header if found
            hash_pos = msg.find("#")
            if hash_pos > 0:
                kwargs["header"] = msg[:hash_pos]
                res = self._obd.send(msg[hash_pos + 1:], **kwargs)
            else:
                res = self._obd.send(msg, **kwargs)

            if res:
                ret.append((msg, res))

            if delay:
                time.sleep(delay / 1000.0)

        return ret

    @Decorators.ensure_open
    def execute(self, cmd, **kwargs):
        return self._obd.execute(cmd, **kwargs)

    @Decorators.ensure_open
    def reset(self, **kwargs):
        self._obd.reset(**kwargs) 

    @Decorators.ensure_open
    def change_baudrate(self, value):
        if not value in STN11XX.TRY_BAUDRATES:
            raise ValueError("Invalid baudrate - supported values are: {:}".format(
                ", ".join([str(b) for b in STN11XX.TRY_BAUDRATES])
            ))

        return self._obd.interface.set_baudrate(value)

    @Decorators.ensure_open
    def monitor(self, **kwargs):
        format_response = kwargs.pop("format_response", True)

        res = self._obd.interface.monitor(**kwargs)

        # Format response
        if format_response:
            return [r.replace(" ", "#", 1).replace(" ", "") for r in res]

        return res

    @Decorators.ensure_open
    def monitor_continuously(self, **kwargs):
        return self._obd.interface.monitor_continuously(enrich=self._enrich_monitor_entry, **kwargs)

    @Decorators.ensure_open
    def list_filters(self, *args, **kwargs):
        return self._obd.interface.list_filters(*args, **kwargs)

    @Decorators.ensure_open
    def add_filter(self, *args, **kwargs):
        self._obd.interface.add_filter(*args, **kwargs)

        # Set flag indicating filters are present
        self.has_filters = True

    @Decorators.ensure_open
    def clear_filters(self, *args, **kwargs):
        self._obd.interface.clear_filters(*args, **kwargs)

        # Set flag indicating filters are absent
        self.has_filters = False

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Cleared filters")

    @Decorators.ensure_open
    def sync_filters(self, can_db, continue_on_error=False):

        # First ensure any existing filters are cleared
        try:
            self.clear_filters.undecorated(self)  # No need to call the 'ensure_open' decorator again
        except Exception as ex:
            log.exception("Failed to clear filters".format(msg))

            if not continue_on_error:
                raise Exception("Failed clear filters: {:}".format(ex))

        # Add pass filter for each message ID
        # NOTE: Can only be added when protocol is set and active/verified
        for msg in can_db.messages:
            try:
                # TODO HN: How to handle 29 bit headers here?
                self.add_filter.undecorated(self, "PASS", "{:03X}".format(msg.frame_id), "7FF")  # No need to call the 'ensure_open' decorator again
            except Exception as ex:
                log.exception("Failed to add pass filter for CAN message '{:}'".format(msg))

                if not continue_on_error:
                    raise Exception("Failed to add pass filter for CAN message '{:}': {:}".format(msg, ex))

        log.info("Synced filters with CAN DB")

    def _enrich_monitor_entry(self, res):
        ret = {
            "_stamp": datetime.datetime.utcnow().isoformat()
        }

        val = res.decode().rstrip()
        if val in self._obd.interface.ERRORS:
            ret["error"] = self._obd.interface.ERRORS[val]
        else:
            # No formatting
            #ret["value"] = val.replace(" ", "#", 1).replace(" ", "")
            ret["value"] = val

        return ret

    def _status_callback(self, status, **kwargs):
        if self.on_status:
            try:
                data = {}

                if "protocol" in kwargs:
                    data["protocol"] = kwargs["protocol"].ID
                    data["autodetected"] = kwargs["protocol"].autodetected

                    # Update cached protocol instance
                    self.cached_protocol = kwargs["protocol"]

                self.on_status(status, data)
            except:
                log.exception("Error in 'on_status' event handler")

    def _calc_formula(self, expression, messages, default=None):

        if not messages:
            log.warn("No messages found to calculate formula: {:}".format(expression))

            return default

        try:
            return eval(expression, {}, {
                # Helper functions
                "bytes_to_int": obd.utils.bytes_to_int,
                "bytes_to_hex": obd.utils.bytes_to_hex,
                "twos_comp": obd.utils.twos_comp,
                # Message data
                "message": messages[0],
                "messages": messages
            })
        except Exception as ex:
            log.exception("Failed to calculate formula")

            raise Exception("Failed to calculate formula: {:}".format(ex))
