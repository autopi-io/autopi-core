import logging
import socket
import _thread
import random


DATA = {
    # ELM327
    "ATZ":      "OBDSIM",       # Reset
    "ATRV":     "{:d}.{:d}V".format(random.randint(11,13), random.randint(0,9)),        # Voltage

    # OBD
    "010C":     "00 00 00 00",  # RPM
    "010D":     "00 00 00",     # Speed
}


log = logging.getLogger(__name__)


def start():
    log.info("Starting Accelerometer simulator")

    sys.modules['smbus'] = smbus




class SMBus():

    def write_byte_data(self, i2c_addr, register, value):
        pass

    def write_byte(self, i2c_addr, value):
        pass
    
    def read_byte_data(self, i2c_addr, register):
        return randint(0, 2**8)

    def read_byte(self, i2c_addr):
        return randint(0, 2**8)

    def read_word_data(self, i2c_addr, register):
        return [randint(0, 2**8)]*2

    def write_word_data(self, i2c_addr, register, value):
        pass
    def read_i2c_block_data(self, a, b, c):
        return [randint(0, 2**8)]*c

    def write_i2c_block_data(self, i2c_addr, register, data):
        pass

    def open(self, bus):
        pass

    def close(self):
        pass