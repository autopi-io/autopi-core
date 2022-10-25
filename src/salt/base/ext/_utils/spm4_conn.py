import logging
import struct
import time

from i2c_conn import I2CConn
from common_util import call_retrying

# Registers
REG_HEARTBEAT             = 0x00  # Read-only
REG_STATUS                = 0x01  # Read-only
REG_VOLT_READOUT          = 0x02  # Read-only
REG_VOLT_CONFIG_FLAGS     = 0x03  # Read-only
REG_STATS                 = 0x04  # Read-only
REG_VERSION               = 0x05  # Read-only
REG_BOARD_ID              = 0x06  # Read-only
REG_SLEEP_DURATION        = 0x10  # Read/write
REG_SHUTDOWN_DELAY        = 0x11  # Read/write
REG_SYS_PINS              = 0x12  # Read/write
REG_USR_PINS              = 0x13  # Read/write
REG_EXT_PINS              = 0x14  # Read/write
REG_WAKE_VOLT_CHANGE      = 0x15  # Read/write
REG_WAKE_VOLT_LEVEL       = 0x16  # Read/write
REG_HIBERNATE_VOLT_LEVEL  = 0x17  # Read/write
REG_VOLT_LIMIT            = 0x18  # Read/write
REG_VOLT_FACTOR           = 0x19  # Read/write
REG_VOLT_EWMA_ALPHA       = 0x1A  # Read/write
REG_WAKE_FLAGS            = 0x20  # Read/write
REG_HIBERNATE_FLAGS       = 0x21  # Read/write
REG_BUTTON_PRESS          = 0x22  # Read/write
REG_DEBUG_FLAGS           = 0x23  # Read/write

# Wake flags
WAKE_FLAG_UNKNOWN      = (1 << 0x00)
WAKE_FLAG_VOLT_CHANGE  = (1 << 0x01)
WAKE_FLAG_VOLT_LEVEL   = (1 << 0x02)
WAKE_FLAG_RTC          = (1 << 0x03)
WAKE_FLAG_ACC          = (1 << 0x04)
WAKE_FLAG_EXT          = (1 << 0x05)
WAKE_FLAG_MODEM        = (1 << 0x06)

# Hibernate flags
HIBERNATE_FLAG_UNKNOWN     = (1 << 0x00)
HIBERNATE_FLAG_VOLT_LEVEL  = (1 << 0x01)

# Volt meter parameters
VOLT_METER_LIMIT       = (1 << 0x00)
VOLT_METER_FACTOR      = (1 << 0x01)
VOLT_METER_EWMA_ALPHA  = (1 << 0x02)

# Volt triggers
VOLT_TRIGGER_HIBERNATE_LEVEL  = (1 << 0x00)
VOLT_TRIGGER_WAKE_LEVEL       = (1 << 0x01)
VOLT_TRIGGER_WAKE_CHANGE      = (1 << 0x02)

# Sys pins
SYS_PIN_IN_RPI_PWR      = (1 << 0x00)
SYS_PIN_OUT_SW_5V       = (1 << 0x01)
SYS_PIN_OUT_SW_3V3      = (1 << 0x02)
SYS_PIN_OUT_SW_AMP      = (1 << 0x03)
SYS_PIN_OUT_RPI_SHUTDN  = (1 << 0x04)

# Usr pins
USR_PIN_OUT_CAN0_RESET  = (1 << 0x00)
USR_PIN_OUT_CAN0_TERM   = (1 << 0x01)
USR_PIN_OUT_CAN1_RESET  = (1 << 0x02)
USR_PIN_OUT_CAN1_TERM   = (1 << 0x03)
USR_PIN_OUT_DOIP_ACT    = (1 << 0x04)

# Ext pins
EXT_PIN_IN_WAKE     = (1 << 0x00)
EXT_PIN_OUT_SW_3V3  = (1 << 0x01)
EXT_PIN_OUT_SW_5V   = (1 << 0x02)
EXT_PIN_OUT_MISC1   = (1 << 0x03)
EXT_PIN_OUT_MISC2   = (1 << 0x04)

# States
STATE_NONE              = 0x00
STATE_OFF               = 0x01
STATE_BOOTING           = 0x02
STATE_ON                = 0x03
STATE_SHUTDOWN_PLANNED  = 0x04
STATE_SHUTTING_DOWN     = 0x05
STATE_SLEEPING          = 0x06
STATE_HIBERNATING       = 0x07
STATE_SETUP             = 0x08
STATE_EMMC_FLASHING     = 0x09

# Triggers
TRIGGER_NONE               = 0x00
TRIGGER_PLUG               = 0x01
TRIGGER_BUTTON             = 0x02
TRIGGER_RPI                = 0x03
TRIGGER_VOLT_CHANGE        = 0x04
TRIGGER_VOLT_LEVEL         = 0x05
TRIGGER_RTC                = 0x06
TRIGGER_ACC                = 0x07
TRIGGER_EXT                = 0x08
TRIGGER_MODEM              = 0x09
TRIGGER_TIMER              = 0x0A
TRIGGER_BOOT_TIMEOUT       = 0x0B
TRIGGER_HEARTBEAT_TIMEOUT  = 0x0C
TRIGGER_SHUTDOWN_TIMEOUT   = 0x0D
TRIGGER_WATCHDOG           = 0x0E
TRIGGER_UNKNOWN            = 0xFE

STATES = {
    STATE_NONE:              "none",
    STATE_OFF:               "off",
    STATE_BOOTING:           "booting",
    STATE_ON:                "on",
    STATE_SHUTDOWN_PLANNED:  "shutdown_planned",
    STATE_SHUTTING_DOWN:     "shutting_down",
    STATE_SLEEPING:          "sleeping",
    STATE_HIBERNATING:       "hibernating",
    STATE_SETUP:             "setup",
    STATE_EMMC_FLASHING:     "emmc_flashing"
}

TRIGGERS = {
    TRIGGER_NONE:               "none",
    TRIGGER_PLUG:               "plug",
    TRIGGER_BUTTON:             "button",
    TRIGGER_RPI:                "rpi",
    TRIGGER_VOLT_CHANGE:        "volt_change",
    TRIGGER_VOLT_LEVEL:         "volt_level",
    TRIGGER_RTC:                "rtc",
    TRIGGER_ACC:                "acc",
    TRIGGER_EXT:                "ext",
    TRIGGER_MODEM:              "modem",
    TRIGGER_TIMER:              "timer",
    TRIGGER_BOOT_TIMEOUT:       "boot_timeout",
    TRIGGER_HEARTBEAT_TIMEOUT:  "heartbeat_timeout",
    TRIGGER_SHUTDOWN_TIMEOUT:   "shutdown_timeout",
    TRIGGER_WATCHDOG:           "watchdog",
    TRIGGER_UNKNOWN:            "unknown"
}

WAKE_FLAGS = {
    "unknown":      WAKE_FLAG_UNKNOWN,
    "volt_change":  WAKE_FLAG_VOLT_CHANGE,
    "volt_level":   WAKE_FLAG_VOLT_LEVEL,
    "rtc":          WAKE_FLAG_RTC,
    "acc":          WAKE_FLAG_ACC,
    "ext":          WAKE_FLAG_EXT,
    "modem":        WAKE_FLAG_MODEM
}

# TODO HN:
HIBERNATE_FLAGS = {
    "unknown":     HIBERNATE_FLAG_UNKNOWN,
    "volt_level":  HIBERNATE_FLAG_VOLT_LEVEL
}

VOLT_METER_FLAGS = {
    "limit":       VOLT_METER_LIMIT,
    "factor":      VOLT_METER_FACTOR,
    "ewma_alpha":  VOLT_METER_EWMA_ALPHA
}

VOLT_TRIGGER_FLAGS = {
    "wake_change":      VOLT_TRIGGER_WAKE_CHANGE,
    "wake_level":       VOLT_TRIGGER_WAKE_LEVEL,
    "hibernate_level":  VOLT_TRIGGER_HIBERNATE_LEVEL
}

SYS_PINS_IN = {
    "rpi_pwr":  SYS_PIN_IN_RPI_PWR
}
SYS_PINS_OUT = {
    "sw_5v":       SYS_PIN_OUT_SW_5V,
    "sw_3v3":      SYS_PIN_OUT_SW_3V3,
    "sw_amp":      SYS_PIN_OUT_SW_AMP,
    "rpi_shutdn":  SYS_PIN_OUT_RPI_SHUTDN
}

USR_PINS_IN = {}
USR_PINS_OUT = {
    "can0_reset":  USR_PIN_OUT_CAN0_RESET,
    "can0_term":  USR_PIN_OUT_CAN0_TERM,
    "can1_reset":  USR_PIN_OUT_CAN1_RESET,
    "can1_term":  USR_PIN_OUT_CAN1_TERM,
    "doip_act":   USR_PIN_OUT_DOIP_ACT
}

EXT_PINS_IN = {
    "ext_wake":  EXT_PIN_IN_WAKE
}
EXT_PINS_OUT = {
    "ext_sw_3v3":  EXT_PIN_OUT_SW_3V3,
    "ext_sw_5v":   EXT_PIN_OUT_SW_5V,
    "ext_misc1":   EXT_PIN_OUT_MISC1,
    "ext_misc2":   EXT_PIN_OUT_MISC2
}

CRC8_PRECOMPILED_2F = [
    0x00, 0x2F, 0x5E, 0x71, 0xBC, 0x93, 0xE2, 0xCD,
    0x57, 0x78, 0x09, 0x26, 0xEB, 0xC4, 0xB5, 0x9A,
    0xAE, 0x81, 0xF0, 0xDF, 0x12, 0x3D, 0x4C, 0x63,
    0xF9, 0xD6, 0xA7, 0x88, 0x45, 0x6A, 0x1B, 0x34,
    0x73, 0x5C, 0x2D, 0x02, 0xCF, 0xE0, 0x91, 0xBE,
    0x24, 0x0B, 0x7A, 0x55, 0x98, 0xB7, 0xC6, 0xE9,
    0xDD, 0xF2, 0x83, 0xAC, 0x61, 0x4E, 0x3F, 0x10,
    0x8A, 0xA5, 0xD4, 0xFB, 0x36, 0x19, 0x68, 0x47,
    0xE6, 0xC9, 0xB8, 0x97, 0x5A, 0x75, 0x04, 0x2B,
    0xB1, 0x9E, 0xEF, 0xC0, 0x0D, 0x22, 0x53, 0x7C,
    0x48, 0x67, 0x16, 0x39, 0xF4, 0xDB, 0xAA, 0x85,
    0x1F, 0x30, 0x41, 0x6E, 0xA3, 0x8C, 0xFD, 0xD2,
    0x95, 0xBA, 0xCB, 0xE4, 0x29, 0x06, 0x77, 0x58,
    0xC2, 0xED, 0x9C, 0xB3, 0x7E, 0x51, 0x20, 0x0F,
    0x3B, 0x14, 0x65, 0x4A, 0x87, 0xA8, 0xD9, 0xF6,
    0x6C, 0x43, 0x32, 0x1D, 0xD0, 0xFF, 0x8E, 0xA1,
    0xE3, 0xCC, 0xBD, 0x92, 0x5F, 0x70, 0x01, 0x2E,
    0xB4, 0x9B, 0xEA, 0xC5, 0x08, 0x27, 0x56, 0x79,
    0x4D, 0x62, 0x13, 0x3C, 0xF1, 0xDE, 0xAF, 0x80,
    0x1A, 0x35, 0x44, 0x6B, 0xA6, 0x89, 0xF8, 0xD7,
    0x90, 0xBF, 0xCE, 0xE1, 0x2C, 0x03, 0x72, 0x5D,
    0xC7, 0xE8, 0x99, 0xB6, 0x7B, 0x54, 0x25, 0x0A,
    0x3E, 0x11, 0x60, 0x4F, 0x82, 0xAD, 0xDC, 0xF3,
    0x69, 0x46, 0x37, 0x18, 0xD5, 0xFA, 0x8B, 0xA4,
    0x05, 0x2A, 0x5B, 0x74, 0xB9, 0x96, 0xE7, 0xC8,
    0x52, 0x7D, 0x0C, 0x23, 0xEE, 0xC1, 0xB0, 0x9F,
    0xAB, 0x84, 0xF5, 0xDA, 0x17, 0x38, 0x49, 0x66,
    0xFC, 0xD3, 0xA2, 0x8D, 0x40, 0x6F, 0x1E, 0x31,
    0x76, 0x59, 0x28, 0x07, 0xCA, 0xE5, 0x94, 0xBB,
    0x21, 0x0E, 0x7F, 0x50, 0x9D, 0xB2, 0xC3, 0xEC,
    0xD8, 0xF7, 0x86, 0xA9, 0x64, 0x4B, 0x3A, 0x15,
    0x8F, 0xA0, 0xD1, 0xFE, 0x33, 0x1C, 0x6D, 0x42
]


log = logging.getLogger(__name__)


class SPM4Conn(I2CConn):

    @property
    def revision(self):
        return 3

    def read_block(self, register, length, check_crc=True):
        res = super(SPM4Conn, self).read_block(register, length)

        # Validate response
        if not res:
            log.warn("Empty response received when reading register {:}".format(register))

            raise Exception("Empty response received when reading register {:}".format(register))

        if res == [r for r in res if r == 0xFF]:  # Are all bytes 0xFF?
            log.warn("Received seemingly invalid response when reading register {:}: {:}".format(register, res))

            raise Exception("Received seemingly invalid response when reading register {:}: {:}".format(register, res))

        if check_crc:
            crc8_validate(res)

        return res

    def heartbeat(self):
        """
        Send heartbeat.
        """

        res = self.read_block(REG_HEARTBEAT, 2)
        ret, crc8 = struct.unpack("<BB", bytearray(res))

        return ret

    def status(self):
        """
        Get current status.
        """

        res = self.read_block(REG_STATUS, 6)

        ret = {
            "current_state": STATES.get(res[0], "invalid"),
            "last_state": {
                "up": STATES.get(res[1], "invalid"),
                "down": STATES.get(res[2], "invalid")
            },
            "last_trigger": {
                "up": TRIGGERS.get(res[3], "invalid"),
                "down": TRIGGERS.get(res[4], "invalid")
            }
        }

        return ret

    def stats(self):
        """
        Get life cycle statistics.
        """

        res = self.read_block(REG_STATS, 11)
        completed_cycles, last_boot_retries, last_boot_duration, forced_shutdowns, watchdog_resets, crc = struct.unpack("<HBLHBB", bytearray(res))

        ret = {
            "completed_cycles": completed_cycles,
            "last_boot": {
                "retries": last_boot_retries,
                "duration": last_boot_duration
            },
            "forced_shutdowns": forced_shutdowns,
            "watchdog_resets": watchdog_resets
        }

        return ret

    def version(self):
        """
        Get the firmware version.
        """

        res = self.read_block(REG_VERSION, 3)
        major, minor, crc8 = struct.unpack("<BBB", bytearray(res))

        return "{:d}.{:d}".format(major, minor)

    def board_id(self):
        """
        Get the unique board ID.
        """

        res = self.read_block(REG_BOARD_ID, 11)
        ret, crc16, crc8 = struct.unpack("<QHB", bytearray(res))

        return ret

    def volt_readout(self, reset=False, samples=1):
        """
        Readout of current, minimum and maximum voltage.
        """

        ret = {}

        if reset:
            self.write_block(REG_VOLT_READOUT, [reset])

        current_readings = []
        maximum_readings = []
        minimum_readings = []

        for i in range(samples):
            res = self.read_block(REG_VOLT_READOUT, 7)
            current, minimum, maximum, crc = struct.unpack("<HhhB", bytearray(res))

            current_readings.append(float(current)/100)
            if minimum > 0:
                minimum_readings.append(float(minimum)/100)
            if maximum > 0:
                maximum_readings.append(float(maximum)/100)

        ret["value"] = round(sum(current_readings)/len(current_readings), 2)
        ret["min"] = round(sum(minimum_readings)/len(minimum_readings), 2) if len(minimum_readings) > 0 else None
        ret["max"] = round(sum(maximum_readings)/len(maximum_readings), 2) if len(maximum_readings) > 0 else None

        return ret

    def volt_config_flags(self):
        """
        Get status flags related to voltage configuration.
        """

        ret = {
            "failed": {},
            "unsaved": {}
        }

        res = self.read_block(REG_VOLT_CONFIG_FLAGS, 5)
        vmeter_failed, vmeter_unsaved, vtrigger_failed, vtrigger_unsaved, crc = struct.unpack("<BBBBB", bytearray(res))

        ret["failed"].update({k: bool(vmeter_failed & v) for k, v in VOLT_METER_FLAGS.iteritems()})
        ret["failed"].update({k: bool(vtrigger_failed & v) for k, v in VOLT_TRIGGER_FLAGS.iteritems()})

        ret["unsaved"].update({k: bool(vmeter_unsaved & v) for k, v in VOLT_METER_FLAGS.iteritems()})
        ret["unsaved"].update({k: bool(vtrigger_unsaved & v) for k, v in VOLT_TRIGGER_FLAGS.iteritems()})

        return ret

    def volt_limit(self, value=None):
        """
        Get or set maximum voltage limit.
        """

        if value != None:
            if not 0 < value <= 30.8:
                raise ValueError("Invalid range")

            self.write_block(REG_VOLT_LIMIT, list(bytearray(struct.pack("<I", int(value*100000000)))))

        res = call_retrying(self.read_block, args=[REG_VOLT_LIMIT, 7], limit=3, wait=0.1)
        val, crc16, crc8 = struct.unpack("<IHB", bytearray(res))

        ret = round(float(val)/100000000, 2)

        if value != None:
            assert value == ret, "Return value mismatch"

        return ret

    def volt_factor(self, value=None):
        """
        Get or set factor to correct voltage readout values. Disabled when set to zero.
        """

        if value != None:
            if not 0 <= value < 2:
                raise ValueError("Invalid range")

            self.write_block(REG_VOLT_FACTOR, list(bytearray(struct.pack("<H", int(value*1000)))))

        res = call_retrying(self.read_block, args=[REG_VOLT_FACTOR, 5], limit=3, wait=0.1)
        val, crc16, crc8 = struct.unpack("<HHB", bytearray(res))

        ret = round(float(val)/1000, 3)

        if value != None:
            assert value == ret, "Return value mismatch"

        return ret

    def volt_ewma_alpha(self, value=None):
        """
        Get or set alpha variable of EWMA (Exponentially Weighted Moving Average) filter used when calculating voltage. Disabled when set to zero.
        """

        if value != None:
            if not 0 <= value <= 1:
                raise ValueError("Invalid range")

            self.write_block(REG_VOLT_EWMA_ALPHA, list(bytearray(struct.pack("<B", int(value*100)))))

        res = call_retrying(self.read_block, args=[REG_VOLT_EWMA_ALPHA, 4], limit=3, wait=0.1)
        val, crc16, crc8 = struct.unpack("<BHB", bytearray(res))

        ret = round(float(val)/100, 2)

        if value != None:
            assert value == ret, "Return value mismatch"

        return ret

    def sys_pins(self, **kwargs):
        """
        Get current system input/output pin states or toggle output pins.
        """

        return self._pins(REG_SYS_PINS, SYS_PINS_IN, SYS_PINS_OUT, **kwargs)

    def usr_pins(self, **kwargs):
        """
        Get current user input/output pin states or toggle output pins.
        """

        return self._pins(REG_USR_PINS, USR_PINS_IN, USR_PINS_OUT, **kwargs)

    def ext_pins(self, **kwargs):
        """
        Get current extension input/output pin states or toggle output pins.
        """

        return self._pins(REG_EXT_PINS, EXT_PINS_IN, EXT_PINS_OUT, **kwargs)

    def wake_volt_change(self, difference=None, period=None):
        """
        Get or set trigger to wake up by voltage change.
        """

        ret = {}

        if difference != None or period != None:
            if difference == None or period == None:
                raise ValueError("Both difference and period must be specified")

            self.write_block(REG_WAKE_VOLT_CHANGE, list(bytearray(struct.pack("<hH", int(difference*100), period))))

        res = call_retrying(self.read_block, args=[REG_WAKE_VOLT_CHANGE, 7], limit=3, wait=0.1)
        dif, per, crc16, crc8 = struct.unpack("<hHHB", bytearray(res))

        ret["difference"] = round(float(dif)/100, 2)
        ret["period"] = per

        if difference != None:
            assert difference == ret["difference"], "Difference value mismatch"
        if period != None:
            assert period == ret["period"], "Period value mismatch"

        return ret

    def wake_volt_level(self, threshold=None, duration=None):
        """
        Get or set trigger to wake up when above voltage level.
        """

        ret = {}

        if threshold != None or duration != None:
            if threshold == None or duration == None:
                raise ValueError("Both threshold and duration must be specified")

            self.write_block(REG_WAKE_VOLT_LEVEL, list(bytearray(struct.pack("<HL", int(threshold*100), duration))))

        res = call_retrying(self.read_block, args=[REG_WAKE_VOLT_LEVEL, 9], limit=3, wait=0.1)
        thr, dur, crc16, crc8 = struct.unpack("<HLHB", bytearray(res))

        ret["threshold"] = round(float(thr)/100, 2)
        ret["duration"] = dur

        if threshold != None:
            assert threshold == ret["threshold"], "Threshold value mismatch"
        if duration != None:
            assert duration == ret["duration"], "Duration value mismatch"

        return ret

    def hibernate_volt_level(self, threshold=None, duration=None):
        """
        Get or set trigger to hibernate when below voltage level.
        """

        ret = {}

        if threshold != None or duration != None:
            if threshold == None or duration == None:
                raise ValueError("Both threshold and duration must be specified")

            self.write_block(REG_HIBERNATE_VOLT_LEVEL, list(bytearray(struct.pack("<HL", int(threshold*100), duration))))

        res = call_retrying(self.read_block, args=[REG_HIBERNATE_VOLT_LEVEL, 9], limit=3, wait=0.1)
        thr, dur, crc16, crc8 = struct.unpack("<HLHB", bytearray(res))

        ret["threshold"] = round(float(thr)/100, 2)
        ret["duration"] = dur

        if threshold != None:
            assert threshold == ret["threshold"], "Threshold value mismatch"
        if duration != None:
            assert duration == ret["duration"], "Duration value mismatch"

        return ret

    def shutdown_delay(self, value=None):
        """
        Get or set shutdown delay (in milliseconds).
        """

        if value != None:
            self.write_block(REG_SHUTDOWN_DELAY, list(bytearray(struct.pack("<H", value))))
        
        res = self.read_block(REG_SHUTDOWN_DELAY, 3)
        ret, crc8 = struct.unpack("<HB", bytearray(res))

        if value != None:
            assert value == ret, "Return value mismatch"

        return ret

    def sleep_duration(self, value=None):
        """
        Get or set sleep duration (in milliseconds).
        """

        if value != None:
            self.write_block(REG_SLEEP_DURATION, list(bytearray(struct.pack("<L", value))))
        
        res = self.read_block(REG_SLEEP_DURATION, 5)
        ret, crc8 = struct.unpack("<LB", bytearray(res))

        if value != None:
            assert value == ret, "Return value mismatch"

        return ret

    def sleep_interval(self, value=None):
        """
        Helper method to set sleep duration in seconds.
        Added for backwards compatibility with SPM 1.0.
        """

        if value != None:

            if not isinstance(value, int):
                raise ValueError("Sleep interval must be an integer value")
            elif value > 86400:
                raise ValueError("Max sleep interval is 24 hours (86400 secs)")

            log.info("Setting sleep interval to %d second(s)", value)

            value *= 1000

        res = self.sleep_duration(value=value)

        return int(res / 1000)

    def restart_3v3(self, toggle_delay=1):
        """
        Helper method to restart the 3V3 power supply.
        """

        # Check current state
        res = self.sys_pins()
        if not res["output"]["sw_3v3"]:
            raise Exception("The 3V3 power supply is currently switched off")

        # Power off
        res = self.sys_pins(toggle="sw_3v3")
        if res["output"]["sw_3v3"]:
            raise Exception("The 3V3 power supply did not switch off")

        # Wait for toggle delay
        time.sleep(toggle_delay)

        # Power on again
        res = self.sys_pins(toggle="sw_3v3")
        if not res["output"]["sw_3v3"]:
            raise Exception("The 3V3 power supply did not switch on again")

    def wake_flags(self, value=None):
        """
        Get or set current wake event flags. 
        """

        if value != None:
            self.write_block(REG_WAKE_FLAGS, list(bytearray(struct.pack("<B", value))))

        res = self.read_block(REG_WAKE_FLAGS, 2)
        val, crc8 = struct.unpack("<BB", bytearray(res))

        if value != None:
            assert value == val, "Return value mismatch"

        ret = {k: bool(val & v) for k, v in WAKE_FLAGS.iteritems()}
        ret["value"] = val

        return ret

    def hibernate_flags(self, value=None):
        """
        Get or set current hibernate event flags. 
        """

        if value != None:
            self.write_block(REG_HIBERNATE_FLAGS, list(bytearray(struct.pack("<B", value))))

        res = self.read_block(REG_HIBERNATE_FLAGS, 2)
        val, crc8 = struct.unpack("<BB", bytearray(res))

        if value != None:
            assert value == val, "Return value mismatch"

        ret = {k: bool(val & v) for k, v in HIBERNATE_FLAGS.iteritems()}
        ret["value"] = val

        return ret

    def button_press(self, value=None):
        """
        Get or set current button press. 
        """

        if value != None:
            self.write_block(REG_BUTTON_PRESS, list(bytearray(struct.pack("<B", value))))

        res = self.read_block(REG_BUTTON_PRESS, 2)
        ret, crc8 = struct.unpack("<BB", bytearray(res))

        if value != None:
            assert value == ret, "Return value mismatch"

        return ret

    def debug_flags(self, value=None):
        """
        Get or set debug flags. 
        """

        if value != None:
            self.write_block(REG_DEBUG_FLAGS, list(bytearray(struct.pack("<B", value))))

        res = self.read_block(REG_DEBUG_FLAGS, 2)
        ret, crc8 = struct.unpack("<BB", bytearray(res))

        if value != None:
            assert value == ret, "Return value mismatch"

        return ret

    def test(self, register=0, length=1, loops=20):
        for i in range(1, loops):
            try:
                res = self.read_block(register, length)
                if crc8_sum(res) != 0:
                    log.error("Got CRC mismatch for result: {:}".format(res))

                    raise ValueError("CRC mismatch")

                log.info("Got successful result: {:}".format(res))

            except Exception as ex:
                raise Exception("Failed in attempt {}/{}: {}".format(i, loops, ex))

    def _pins(self, register, in_pins, out_pins, toggle=None, low=None, high=None):
        """
        Helper method to get current input/output pin states or toggle output pins.
        """

        ret = {}

        if toggle != None:
            val = 0
            for pin in toggle.split(","):
                if not pin in out_pins:
                    raise ValueError("Invalid output pin '{:}'".format(pin))

                val |= out_pins[pin]

            self.write_block(register, [val])

        if low != None:
            res = self.read_block(register, 2)
            val = 0
            for pin in low.split(","):
                if not pin in out_pins:
                    raise ValueError("Invalid output pin '{:}'".format(pin))

                # Only toggle if already high
                if res[0] & out_pins[pin] > 0:
                    val |= out_pins[pin]

            if val > 0:
                self.write_block(register, [val])

        if high != None:
            res = self.read_block(register, 2)
            val = 0
            for pin in high.split(","):
                if not pin in out_pins:
                    raise ValueError("Invalid output pin '{:}'".format(pin))

                # Only toggle if already low
                if res[0] & out_pins[pin] == 0:
                    val |= out_pins[pin]

            if val > 0:
                self.write_block(register, [val])

        res = self.read_block(register, 2)

        if in_pins:
            ret["input"] = {k: bool(res[0] & v) for k, v in in_pins.iteritems()}
        if out_pins:
            ret["output"] = {k: bool(res[0] & v) for k, v in out_pins.iteritems()}

        return ret


def crc8_sum(bytes):
    ret = 0

    for byte in bytes:
        ret = CRC8_PRECOMPILED_2F[ret^byte]

    return ret


def crc8_validate(bytes):
    if crc8_sum(bytes) != 0:
        raise ValueError("CRC mismatch")
