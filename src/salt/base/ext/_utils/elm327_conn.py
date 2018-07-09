import logging
import obd

from retrying import retry


log = logging.getLogger(__name__)


class ELM327Conn:

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

            return self
        except Exception:
            log.exception("Failed to open ELM327 connection")

            raise

    def is_open(self):
        return self._obd != None \
            and self._obd.status() != obd.OBDStatus.NOT_CONNECTED

    def ensure_open(self):
        if not self.is_open():
            self.open()

    def close(self):
        self._obd.close()

    def __enter__(self):
        return self.open()

    def __exit__(self, type, value, traceback):
        self.close()

    def ensured(self, func):
        '''
        Decorater method.
        '''

        def func_wrapper():
            self.ensure_open()
            return func()

        return func_wrapper

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

        # First check if already switched
        if value == self._baudrate:
            return

        # Set the baud switch timeout
        res = self._obd.interface.send_and_parse("STBRT {:d}".format(timeout))
        log.info("Set baud switch timeout: {:}".format(res))

        # Switch UART baudrate in software-friendly way
        res = self._obd.interface.send_and_parse("STBR {:d}".format(value))
        log.info("Set baudrate: {:}".format(res))

        # Close current connection and open new with switched baudrate
        self._obd.close()
        self._obd = obd.OBD(portstr=self._device, baudrate=value)

        # Update baudrate if no exception was raised
        self._baudrate = value
