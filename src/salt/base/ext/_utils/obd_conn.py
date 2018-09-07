import gpio_pin
import logging
import obd
import RPi.GPIO as gpio

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

            return decorator

    def __init__(self):
        self._device = None
        self._baudrate = None

        self._obd = None

        self.is_permanently_closed = False

        self.on_closing = None
        self.on_closed = None

    def setup(self, settings):
        log.debug("Configuring OBD connection using settings: %s", settings)

        if not "device" in settings:
            raise ValueError("Setting 'device' must be specified")
        self._device = settings["device"]

        if not "baudrate" in settings:
            raise ValueError("Setting 'baudrate' must be specified")
        if not settings["baudrate"] in STN11XX.TRY_BAUDRATES:
            raise ValueError("Setting 'baudrate' has unsupported value")
        self._baudrate = settings["baudrate"]

        # Prepare GPIO to listen on STN power pin
        gpio.setmode(gpio.BOARD)
        gpio.setup(gpio_pin.STN_PWR, gpio.IN)

    @retry(stop_max_attempt_number=3, wait_fixed=1000)
    def open(self, force=False):

        if self.is_permanently_closed and not force:
            raise Warning("OBD connection is no longer available as it has been permanently closed")
        
        # Reset flag
        self.is_permanently_closed = False

        log.debug("Opening OBD connection")
        try :
            self._obd = obd.OBD(portstr=self._device, baudrate=self._baudrate, interface_cls=STN11XX)

            return self
        except Exception:
            log.exception("Failed to open OBD connection")

            raise

    def is_open(self):
        return self._obd != None \
            and self._obd.status() != obd.OBDStatus.NOT_CONNECTED

    def ensure_open(self):
        if self.is_open():

            # Check if STN has powered down (might be due to low battery)
            if gpio.input(gpio_pin.STN_PWR) == 0:
                log.warn("Closing OBD connection permanently because STN has powered off")

                self.close(permanent=True)

                raise Warning("OBD connection closed permanently because STN has powered off")
        else:
            self.open()

    def close(self, permanent=False):
        if self.on_closing:
            try:
                self.on_closing()
            except:
                log.exception("Error in 'on_closing' event handler")

        self.is_permanently_closed = permanent

        self._obd.close()
        self._obd = None

        if self.on_closed:
            try:
                self.on_closed()
            except:
                log.exception("Error in 'on_closed' event handler")

    @Decorators.ensure_open
    def info(self):
        return {
            "status": self._obd.status(),
            "serial": self._obd.connection_info(),
            "protocol": self._obd.protocol_info()
        }

    @Decorators.ensure_open
    def protocol_info(self):
        return self._obd.protocol_info()

    @Decorators.ensure_open
    def supported_protocols(self):
        return {k: v.NAME for k, v in self._obd.supported_protocols().iteritems()}

    @Decorators.ensure_open
    def change_protocol(self, id, **kwargs):        
        return self._obd.change_protocol(id, **kwargs)

    @Decorators.ensure_open
    def query(self, cmd, **kwargs):
        return self._obd.query(cmd, **kwargs)

    @Decorators.ensure_open
    def supported_commands(self):
        return {c.name: c.desc for c in self._obd.supported_commands}

    @Decorators.ensure_open
    def send(self, msg, **kwargs):

        # Parse out header if found
        hash_pos = msg.find("#")
        if hash_pos > 0:
            kwargs["header"] = msg[:hash_pos]
            msg = msg[hash_pos + 1:]

        return self._obd.send(msg, **kwargs)

    # Ensure open decorator not needed here
    def send_all(self, msgs, delay=None):
        for msg in msgs:
            self.send(msg, auto_format=False)

            if delay:
                time.sleep(delay / 1000.0)

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
    def monitor_all(self, **kwargs):

        # Format messages
        return [l.replace(" ", "#", 1).replace(" ", "") for l in self._obd.interface.monitor_all(**kwargs)]
