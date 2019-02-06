from __future__ import division

import logging

from i2c_conn import I2CConn
from retrying import retry


log = logging.getLogger(__name__)


# Registers
WRITE         = 0x40
WRITE_EEPROM  = 0x60


class MCP4725Conn(I2CConn):

    def voltage(self, value, persist=False):
        """
        Set the output voltage to specified value.  Value is a 12-bit number
        (0-4095) that is used to calculate the output voltage from:
          Vout =  (VDD*value)/4096
        I.e. the output voltage is the VDD reference scaled by value/4096.
        If persist is true it will save the voltage value in EEPROM so it
        continues after reset (default is false, no persistence).
        """

        # Clamp value to an unsigned 12-bit value.
        if value > 4095:
            value = 4095
        if value < 0:
            value = 0

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Setting value to {0:04}".format(value))

        # Generate the register bytes and send them.
        # See datasheet figure 6-2: https://www.adafruit.com/datasheets/mcp4725.pdf 
        block = [(value >> 4) & 0xFF, (value << 4) & 0xFF]
        if persist:
            self.write_block(WRITE_EEPROM, block)
        else:
            self.write_block(WRITE, block)
