import logging
import obd

from retrying import retry
from serial_conn import SerialConn


log = logging.getLogger(__name__)


class ELM327Conn(SerialConn):

    def __init__(self):
        self._device = None
        self._baudrate = None

        self._obd = None

    def init(self, settings):
        log.info("Initializing ELM327 connection using settings: %s", settings)

        if not "device" in settings:
            raise ValueError("ELM327 'device' must be specified in settings")
        self._device = settings["device"]

        if not "baudrate" in settings:
            raise ValueError("ELM327 'baudrate' must be specified in settings")
        self._baudrate = settings["baudrate"]

    @retry(stop_max_attempt_number=3, wait_fixed=1000)
    def open(self):
        log.info("Opening ELM327 connection")

        try :
            self._obd = obd.OBD(portstr=self._device, baudrate=self._baudrate)
            self._serial = _obd.interface._ELM327__port

            return self
        except Exception:
            log.exception("Failed to open ELM327 connection")

            raise

    def is_open(self):
        return self._obd != None \
            and self._obd.status() != obd.OBDStatus.NOT_CONNECTED

    def close(self):
        self._obd.close()

    def settings(self):
        return {
            "device": self._device,
            "baudrate": self._baudrate
        }

    def protocol(self):
        self.ensure_open()

        return {
            "name": self._obd.protocol_name(),
            "id": self._obd.protocol_id()
        }

    def status(self):
        self.ensure_open()

        return self._obd.status()

    def query(self, cmd, force=False):
        self.ensure_open()

        return self._obd.query(cmd, force=force)

    def commands(self):
        self.ensure_open()

        return self._obd.supported_commands

    def switch_baudrate(self, value, timeout=2000):
        self.ensure_open()

        old = self._baudrate
        new = value

        # First check if already switched
        if old == new:
            return

        # Switch UART baudrate in terminal-friendly way
        self.write_line("STSBR {:d}".format(new))
        log.info("Switched baudrate from {:} to {:}".format(old, new))

        # Close connection
        self.close()

        # Open connection again with new baudrate
        try:
            self._baudrate = new
            self.open()
        except:
            self._baudrate = old

            log.exception("Failed to switch to new baudrate {:} - now reverted back to {:}".format(new, old))

