import logging
import RPi.GPIO as gpio
import time

from retrying import retry


log = logging.getLogger(__name__)


class GPIOSPIConn(object):

    def __init__(self, clk_pin, mosi_pin, miso_pin, num_bits=8, gpio_mode=gpio.BOARD):
        self._clk_pin = clk_pin
        self._mosi_pin = mosi_pin
        self._miso_pin = miso_pin
        self._num_bits = num_bits
        self._gpio_mode = gpio_mode

    def setup(self):
        log.info("Setting up GPIO SPI connection")

        gpio.setwarnings(False)
        gpio.setmode(self._gpio_mode)

        # Set all pins as an output except MISO (Master Input, Slave Output)
        gpio.setup(self._clk_pin, gpio.OUT)
        gpio.setup(self._mosi_pin, gpio.OUT)
        gpio.setup(self._miso_pin, gpio.IN)

    def send(self, data):
        """
        Sends 1 byte of data or less.
        """

        log.debug("TX: {:}".format(data))

        data <<= (8 - self._num_bits)

        for bit in range(self._num_bits):
            # Set RPi's output bit high or low depending on highest bit of data field
            if data & 0x80:
                gpio.output(self._mosi_pin, gpio.HIGH)
            else:
                gpio.output(self._mosi_pin, gpio.LOW)

            # Advance data to the next bit
            data <<= 1

            # Pulse the clock pin high then immediately low
            gpio.output(self._clk_pin, gpio.HIGH)
            gpio.output(self._clk_pin, gpio.LOW)

    @retry(stop_max_attempt_number=3, wait_fixed=500)
    def recv(self, ack=None):
        """
        Receives arbitrary number of bits.
        """

        ret = 0

        # Give ATtiny time to be ready (for RPi3 compatibility)
        time.sleep(10)

        for bit in range(self._num_bits):
            # Pulse clock pin
            gpio.output(self._clk_pin, gpio.HIGH)
            gpio.output(self._clk_pin, gpio.LOW)

            # Read 1 data bit in
            if gpio.input(self._miso_pin):
                ret |= 0x1

            # Advance input to next bit
            ret <<= 1

        # Divide by two to drop the NULL bit
        ret = ret/2

        log.debug("RX: {:}".format(ret))

        # TODO: We always need to receive an ack first to see if we got what we expected?
        if ack != None and ack != ret:
            msg = "Expected ack '{:d}' but got '{:d}'".format(ack, ret)
            log.warn(msg)

            raise Exception(msg)

        return ret
