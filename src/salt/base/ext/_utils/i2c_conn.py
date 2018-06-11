import logging
import smbus

from retrying import retry


log = logging.getLogger(__name__)


class I2CConn:

    def __init__(self):
        self._port = None
        self._address = None

        self._bus = None
        self._is_open = False

        self.on_written = None

    def init(self, settings):
        log.info("Initializing I2C connection using settings: %s", settings)

        if not "port" in settings:
            raise ValueError("I2C 'port' must be specified in settings")
        self._port = settings["port"]

        if not "address" in settings:
            raise ValueError("I2C 'address' must be specified in settings")
        self._address = settings["address"]

        self._bus = smbus.SMBus()

    @retry(stop_max_attempt_number=3, wait_fixed=1000)
    def open(self):
        log.info("Opening I2C connection on port: %d", self._port)

        try :
            self._bus.open(self._port)
            self._is_open = True

            return self
        except Exception:
            log.exception("Failed to open I2C connection")
            self._is_open = False

            raise

    def is_open(self):
        return self._is_open

    def ensure_open(self):
        if not self.is_open():
            self.open()

    def close(self):
        self._bus.close()
        self._is_open = False

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

    def read(self, register):
        self.ensure_open()

        byte = self._bus.read_byte_data(self._address, register)

        log.info("Read register {:d}: {:08b}".format(register, byte))

        return byte

    def read_block(self, register, length):
        self.ensure_open()

        block = self._bus.read_i2c_block_data(self._address, register, length)

        return block

    def write(self, register, byte):
        self.ensure_open()

        self._bus.write_byte_data(self._address, register, byte)

        log.info("Wrote register {:d}: {:08b}".format(register, byte))

        if self.on_written:
            self.on_written(register, byte)