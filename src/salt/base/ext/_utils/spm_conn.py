import gpio_pin
import logging
import time

from gpio_spi_conn import GPIOSPIConn
from retrying import retry


log = logging.getLogger(__name__)


# Commands
CMD_NOOP                  = 100
CMD_GET_VERSION           = 101
CMD_GET_STATUS            = 102
CMD_GET_HEARTBEAT_TIMEOUT = 110
CMD_SET_HEARTBEAT_TIMEOUT = 111
CMD_GET_SLEEP_INTERVAL    = 120
CMD_SET_SLEEP_INTERVAL    = 121
CMD_START_3V3             = 130
CMD_STOP_3V3              = 131

# Acks/errors
ACK_NOOP                  = 200
ACK_SET_HEARTBEAT_TIMEOUT = 211
ACK_SET_SLEEP_INTERVAL    = 221
ACK_START_3V3             = 230
ACK_STOP_3V3              = 231
ERROR_CMD                 = 255

# Prototocol commands
CMD_MESSAGE_BEGIN         = 11
ACK_MESSAGE_BEGIN         = 12
ACK_DATA_LENGTH           = 13
CMD_SEND_NEXT_BYTE        = 14

STATES = {
    0: "none",
    1: "off",
    2: "booting",
    3: "on",
    4: "sleeping",
    5: "hibernating",
}

TRIGGERS = {
    0: "none",
    1: "spm",
    2: "rpi",
    3: "stn",
    4: "acc",
    5: "modem",
    6: "timer",
    7: "boot_timeout",
    8: "heartbeat_timeout",
}


class SPMConn(GPIOSPIConn):

    def __init__(self):
        super(SPMConn, self).__init__(gpio_pin.SPI_CLK, gpio_pin.SPI_MOSI, gpio_pin.SPI_MISO, gpio_mode=gpio_pin.MODE)

    def _begin_message(self, length=1):

        log.debug("Sending begin message command")
        self.send(CMD_MESSAGE_BEGIN)
        self.recv(ack=ACK_MESSAGE_BEGIN)

        log.debug("Sending message length: %d", length)
        self.send(length)
        self.recv(ack=ACK_DATA_LENGTH)

    @retry(stop_max_attempt_number=3, wait_fixed=500)
    def noop(self):
        try:
            self._begin_message()

            self.send(CMD_NOOP)
            self.recv(ack=ACK_NOOP)
        except Exception as ex:
            log.warning("Unable to send noop: {:}".format(ex))

            raise

    def heartbeat(self):
        self.noop()

    @retry(stop_max_attempt_number=3, wait_fixed=500)
    def version(self):
        try:
            self._begin_message()

            self.send(CMD_GET_VERSION)

            bytes = []
            for i in range(4):
                bytes.append(self.recv())

            ret = "{:d}.{:d}.{:d}.{:d}".format(*bytes)

            return ret
        except Exception as ex:
            log.warning("Unable to get version: {:}".format(ex))

            raise

    @retry(stop_max_attempt_number=3, wait_fixed=500)
    def status(self):
        try:
            self._begin_message()

            self.send(CMD_GET_STATUS)

            bytes = []
            for i in range(4):
                bytes.append(self.recv())

            up_state = bytes[0] & 0x0F
            down_state = (bytes[0] & 0xF0) >> 4
            up_trigger = bytes[1] & 0x0F
            down_trigger = (bytes[1] & 0xF0) >> 4

            ret = {
                "last_state": {
                    "up": STATES.get(up_state, "unknown"),
                    "down": STATES.get(down_state, "unknown"),
                },
                "last_trigger": {
                    "up": TRIGGERS.get(up_trigger, "unknown"),
                    "down": TRIGGERS.get(down_trigger, "unknown"),
                },
                "port_a": "{:08b}".format(bytes[2]),
                "port_b": "{:08b}".format(bytes[3]),
            }

            return ret
        except Exception as ex:
            log.warning("Unable to get status: {:}".format(ex))

            raise

    @retry(stop_max_attempt_number=3, wait_fixed=500)
    def heartbeat_timeout(self):
        try:
            self._begin_message()

            self.send(CMD_GET_HEARTBEAT_TIMEOUT)
            ret = self.recv()

            return ret
        except Exception as ex:
            log.warning("Unable to send heartbeat timeout: {:}".format(ex))

            raise

    @retry(stop_max_attempt_number=3, wait_fixed=500)
    def sleep_interval(self, value=None):
        try:
            if value != None:

                if not isinstance(value, int):
                    raise ValueError("Sleep interval must be an integer value")
                elif value > 86400:
                    raise ValueError("Max sleep interval is 24 hours (86400 secs)")

                self._begin_message(length=5)

                log.info("Setting sleep interval to %d second(s)", value)
                self.send(CMD_SET_SLEEP_INTERVAL)

                bytes = [0 for x in range(4)]
                bytes[0] = (value >> 24) & 0xFF;
                bytes[1] = (value >> 16) & 0xFF;
                bytes[2] = (value >> 8) & 0xFF;
                bytes[3] = value & 0xFF;

                for byte in bytes:
                    self.send(byte)

                self.recv(ack=ACK_SET_SLEEP_INTERVAL)

            self._begin_message()

            self.send(CMD_GET_SLEEP_INTERVAL)

            bytes = []
            for i in range(4):
                bytes.append(self.recv())

            ret = (bytes[0] << 24) + (bytes[1] << 16) + (bytes[2] << 8) + (bytes[3] << 0)

            return ret
        except Exception as ex:
            log.warning("Unable to set sleep interval: {:}".format(ex))

            raise

    @retry(stop_max_attempt_number=3, wait_fixed=500)
    def start_3v3(self):
        try:
            self._begin_message()

            log.info("Starting 3V3")
            self.send(CMD_START_3V3)
            self.recv(ack=ACK_START_3V3)
        except Exception as ex:
            log.warning("Unable to start 3v3: {:}".format(ex))

            raise

    @retry(stop_max_attempt_number=3, wait_fixed=500)
    def stop_3v3(self):
        try:
            self._begin_message()

            log.warn("Stopping 3V3")
            self.send(CMD_STOP_3V3)
            self.recv(ack=ACK_STOP_3V3)
        except Exception as ex:
            log.warning("Unable to stop 3v3: {:}".format(ex))

            raise

    def restart_3v3(self):
        self.stop_3v3()
        self.start_3v3()
