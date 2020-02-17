import logging
import smbus

from retrying import retry


log = logging.getLogger(__name__)


class I2CConn(object):

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
        self._port = None
        self._address = None

        self._bus = None
        self._is_open = False

        self.on_written = None

    def init(self, settings):
        log.debug("Initializing I2C connection using settings: %s", settings)

        if not "port" in settings:
            raise ValueError("I2C 'port' must be specified in settings")
        self._port = settings["port"]

        if not "address" in settings:
            raise ValueError("I2C 'address' must be specified in settings")
        self._address = settings["address"]

        self._bus = smbus.SMBus()

        return self

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

    @Decorators.ensure_open
    def read_byte(self, register):
        byte = self._bus.read_byte_data(self._address, register)

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Read register {:d}: {:08b}".format(register, byte))

        return byte

    @Decorators.ensure_open
    def read_block(self, register, length):

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Reading block with a length of {:d} starting from register {:d}".format(length, register))

        block = self._bus.read_i2c_block_data(self._address, register, length)

        if log.isEnabledFor(logging.DEBUG):
            for idx, byt in enumerate(block):
                log.debug("Read byte {:d}/{:d} in block: {:08b}".format(idx, len(block), byt))

        return block

    @Decorators.ensure_open
    def read(self, register, length=1):
        ret = None
        
        if length > 1:
            ret = self.read_block.undecorated(self, register, length)
        else:
            ret = self.read_byte.undecorated(self, register)

        return ret

    @Decorators.ensure_open
    def write(self, register, byte):
        self._bus.write_byte_data(self._address, register, byte)

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Wrote register {:d}: {:08b}".format(register, byte))

        if self.on_written:
            self.on_written(register, byte)

    @Decorators.ensure_open
    def write_block(self, register, block):
        self._bus.write_i2c_block_data(self._address, register, block)

        if log.isEnabledFor(logging.DEBUG):
            for idx, byt in enumerate(block):
                log.debug("Wrote byte {:d}/{:d} of block to register {:d}: {:08b}".format(idx, len(block), register, byt))

        if self.on_written:
            self.on_written(register, block)

    @Decorators.ensure_open
    def read_write(self, register, mask, value):
        byte = self.read_byte.undecorated(self, register)

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Updating byte {:08b} using mask {:d} and value {:d}".format(byte, mask, value))

        byte = self._update_bits(byte, mask, value)

        self.write.undecorated(self, register, byte)

        return byte

    def _update_bits(self, byte, mask, value):

        # First clear the bits indicated by the mask
        byte &= ~mask

        # Then set the bits indicated by the value
        if value:
            byte |= value

        return byte

    def _concat_bytes(self, bytes, bits=10):
        words = []

        for idx in range(0, len(bytes), 2): # Only loop on even numbers

            # Concat bytes
            word = bytes[idx] << 8 | bytes[idx + 1]

            # Shorten word to match specified bit length
            word = word >> 16 - bits
            words.append(word)

        return words

    def _signed_int(self, word, bits=8):
        """
        Calculate signed integer as a two's complement number.

        Examples:

            127  -> 127
            1    -> 1
            0    -> 0
            255  -> -1
            128  -> -128

            127  -> 127 (01111111)
            1    -> 1   (00000001)
            -1   -> 255 (11111111)
            -128 -> 128 (10000000)
        """

        return word - (word >> bits-1) * (2 ** bits)
