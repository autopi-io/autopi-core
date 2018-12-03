from __future__ import division

import logging

from common_util import dict_key_by_value
from i2c_conn import I2CConn
from retrying import retry


log = logging.getLogger(__name__)


# See: https://github.com/intel-iot-devkit/upm/blob/1a0bdf00cf892fd7090d28d8937aea8969efcdf9/src/mma8x5x/mma8x5x.hpp

# Registers
STATUS           = 0x00  # Data or FIFO Status
OUT_X_MSB        = 0x01  # [7:0] are 8 MSBs of X data
OUT_X_LSB        = 0x02  # [7:4] are 4 LSBs of X data
OUT_Y_MSB        = 0x03  # [7:0] are 8 MSBs of Y data
OUT_Y_LSB        = 0x04  # [7:4] are 4 LSBs of Y data
OUT_Z_MSB        = 0x05  # [7:0] are 8 MSBs of Z data
OUT_Z_LSB        = 0x06  # [7:4] are 8 LSBs of Z data
F_SETUP          = 0x09  # FIFO setup
TRIG_CFG         = 0x0A  # Map of FIFO data capture events
SYSMOD           = 0x0B  # Current System mode
INT_SOURCE       = 0x0C  # Interrupt status
WHO_AM_I         = 0x0D  # Device ID (0x1A)
XYZ_DATA_CFG     = 0x0E  # Dynamic Range Settings
HP_FILTER_CUTOFF = 0x0F  # High-Pass Filter Selection
PL_STATUS        = 0x10  # Landscape/Portrait orientation status
PL_CFG           = 0x11  # Landscape/Portrait configuration
PL_COUNT         = 0x12  # Landscape/Portrait debounce counter
PL_BF_ZCOMP      = 0x13  # Back/Front, Z-Lock Trip threshold
P_L_THS_REG      = 0x14  # Portrait/Landscape Threshold and Hysteresis
FF_MT_CFG        = 0x15  # Freefall/Motion functional block configuration
FF_MT_SRC        = 0x16  # Freefall/Motion event source register
FF_MT_THS        = 0x17  # Freefall/Motion threshold register
FF_MT_COUNT      = 0x18  # Freefall/Motion debounce counter
TRANSIENT_CFG    = 0x1D  # Transient functional block configuration
TRANSIENT_SRC    = 0x1E  # Transient event status register
TRANSIENT_THS    = 0x1F  # Transient event threshold
TRANSIENT_COUNT  = 0x20  # Transient debounce counter
PULSE_CFG        = 0x21  # Pulse enable configuration
PULSE_SRC        = 0x22  # Pulse detection source
PULSE_THSX       = 0x23  # X pulse threshold
PULSE_THSY       = 0x24  # Y pulse threshold
PULSE_THSZ       = 0x25  # Z pulse threshold
PULSE_TMLT       = 0x26  # Time limit for pulse
PULSE_LTCY       = 0x27  # Latency time for 2nd pulse
PULSE_WIND       = 0x28  # Window time for 2nd pulse
ASLP_COUNT       = 0x29  # Counter setting for Auto-SLEEP
CTRL_REG1        = 0x2A  # Data rates and modes setting
CTRL_REG2        = 0x2B  # Sleep Enable, OS modes, RST, ST
CTRL_REG3        = 0x2C  # Wake from Sleep, IPOL, PP_OD
CTRL_REG4        = 0x2D  # Interrupt enable register
CTRL_REG5        = 0x2E  # Interrupt pin (INT1/INT2) map
OFF_X            = 0x2F  # X-axis offset adjust
OFF_Y            = 0x30  # Y-axis offset adjust
OFF_Z            = 0x31  # Z-axis offset adjust

# Status register
STATUS_XDR   = (1 << 0)  # X-axis new data available
STATUS_YDR   = (1 << 1)  # Y-axis new data available
STATUS_ZDR   = (1 << 2)  # Z-axis new data available
STATUS_ZYXDR = (1 << 3)  # X, Y, Z-axis new data ready
STATUS_XOW   = (1 << 4)  # X-axis data overwrite
STATUS_YOW   = (1 << 5)  # Y-axis data overwrite
STATUS_ZOW   = (1 << 6)  # Z-axis data overwrite
STATUS_ZYXOW = (1 << 7)  # X, Y, Z-axis data overwrite

# Data configuration register
XYZ_DATA_CFG_FS_MASK = 0x3
XYZ_DATA_CFG_HPF_OUT = (1 << 4)

# Freefall/motion configuration register
FF_MT_CFG_XEFE = (1 << 3)
FF_MT_CFG_YEFE = (1 << 4)
FF_MT_CFG_ZEFE = (1 << 5)
FF_MT_CFG_OAE  = (1 << 6)
FF_MT_CFG_ELE  = (1 << 7)

# Freefall/motion source register
FF_MT_SRC_XHP = (1 << 0)
FF_MT_SRC_XHE = (1 << 1)
FF_MT_SRC_YHP = (1 << 2)
FF_MT_SRC_YHE = (1 << 3)
FF_MT_SRC_ZHP = (1 << 4)
FF_MT_SRC_ZHE = (1 << 5)
FF_MT_SRC_EA  = (1 << 7)

# Freefall/motion threshold register
FF_MT_THS_MASK   = 0x7F
FF_MT_THS_DBCNTM = (1 << 7)

# Interrupt status register
INT_SOURCE_DRDY   = (1 << 0)  # Data-ready interrupt status
INT_SOURCE_FF_MT  = (1 << 2)  # Freefall/motion interrupt status
INT_SOURCE_PULSE  = (1 << 3)  # Pulse interrupt status
INT_SOURCE_LNDPRT = (1 << 4)  # Landscape/portrait orientation interrupt status
INT_SOURCE_TRANS  = (1 << 5)  # Transient interrupt status
INT_SOURCE_FIFO   = (1 << 6)  # FIFO interrupt status
INT_SOURCE_ASLP   = (1 << 7)  # Auto-sleep/wake interrupt status

INTERRUPT_SOURCES = {
    INT_SOURCE_DRDY:   "data",
    INT_SOURCE_FF_MT:  "motion",
    INT_SOURCE_PULSE:  "pulse",
    INT_SOURCE_LNDPRT: "orientation",
    INT_SOURCE_TRANS:  "transient",
    INT_SOURCE_FIFO:   "fifo",
    INT_SOURCE_ASLP:   "wake",
}

# System control register #1
CTRL_REG1_ACTIVE         = (1 << 0)
CTRL_REG1_F_READ         = (1 << 1)
CTRL_REG1_DR_MASK        = 0x38
CTRL_REG1_DR_SHIFT       = 3
CTRL_REG1_ASLP_RATE_MASK = 0xC0

# System control register #2
CTRL_REG2_MODS_MASK  = 0x3      # Active mode power scheme selection
CTRL_REG2_SLPE       = (1 << 2) # Auto-sleep enable
CTRL_REG2_SMODS_MASK = 0x18     # Sleep mode power scheme selection
CTRL_REG2_RST        = (1 << 6) # Software reset
CTRL_REG2_ST         = (1 << 7) # Self-test enable

# System control register #3
CTRL_REG3_PP_OD       = (1 << 0)  # Push-pull/open drain selection on interrupt pad
CTRL_REG3_IPOL        = (1 << 1)  # Interrupt polarity active high, or active low
CTRL_REG3_WAKE_FF_MT  = (1 << 3)  # Freefall/motion function interrupt can wake up
CTRL_REG3_WAKE_PULSE  = (1 << 4)  # Pulse function interrupt can wake up system
CTRL_REG3_WAKE_LNDPRT = (1 << 5)  # Orientation function interrupt can wake up system
CTRL_REG3_WAKE_TRANS  = (1 << 6)  # Transient function interrupt can wake up system
CTRL_REG3_FIFO_GATE   = (1 << 7)  #

WAKE_SOURCES = {
    CTRL_REG3_WAKE_FF_MT:  "motion",
    CTRL_REG3_WAKE_PULSE:  "pulse",
    CTRL_REG3_WAKE_LNDPRT: "orientation",
    CTRL_REG3_WAKE_TRANS:  "transient",
}

# System control register #4
CTRL_REG4_INT_EN_DRDY   = INT_SOURCE_DRDY    # Data-ready interrupt enabled
CTRL_REG4_INT_EN_FF_MT  = INT_SOURCE_FF_MT   # Freefall/motion interrupt enabled
CTRL_REG4_INT_EN_PULSE  = INT_SOURCE_PULSE   # Pulse detection interrupt enabled
CTRL_REG4_INT_EN_LNDPRT = INT_SOURCE_LNDPRT  # Orientation (landscape/portrait) interrupt enabled
CTRL_REG4_INT_EN_TRANS  = INT_SOURCE_TRANS   # Transient interrupt enabled
CTRL_REG4_INT_EN_FIFO   = INT_SOURCE_FIFO    # FIFO interrupt enabled
CTRL_REG4_INT_EN_ASLP   = INT_SOURCE_ASLP    # Auto-sleep/wake interrupt enabled

# System control register #5
CTRL_REG5_INT_CFG_DRDY   = INT_SOURCE_DRDY    # Data-ready interrupt pin (INT1/INT2)
CTRL_REG5_INT_CFG_FF_MT  = INT_SOURCE_FF_MT   # Freefall/motion interrupt pin (INT1/INT2)
CTRL_REG5_INT_CFG_PULSE  = INT_SOURCE_PULSE   # Pulse detection interrupt pin (INT1/INT2)
CTRL_REG5_INT_CFG_LNDPRT = INT_SOURCE_LNDPRT  # Orientation (landscape/portrait) interrupt pin (INT1/INT2)
CTRL_REG5_INT_CFG_TRANS  = INT_SOURCE_TRANS   # Transient interrupt pin (INT1/INT2)
CTRL_REG5_INT_CFG_FIFO   = INT_SOURCE_FIFO    # FIFO interrupt pin (INT1/INT2)
CTRL_REG5_INT_CFG_ASLP   = INT_SOURCE_ASLP    # Auto-sleep/wake interrupt pin (INT1/INT2)

# Available range options
RANGE_2G = 0
RANGE_4G = 1
RANGE_8G = 2

RANGE_DEFAULT = RANGE_2G

RANGES = {
    RANGE_2G: 2,
    RANGE_4G: 4,
    RANGE_8G: 8,
}

# Available system modes
MODE_STANDBY = 0
MODE_WAKE    = 1
MODE_SLEEP   = 2

MODES = {
    MODE_STANDBY: "standby",
    MODE_WAKE:    "wake",
    MODE_SLEEP:   "sleep",
}

# Available oversampling modes for both wake mode (MOD) and sleep mode (SMOD)
MODS_NORMAL = 0
MODS_LNLP   = 1
MODS_HR     = 2
MODS_LP     = 3

# Available data sampling rates
DATA_RATE_800HZ = (0 << 3)  #  800 Hz Ouput Data Rate in WAKE mode
DATA_RATE_400HZ = (1 << 3)  #  400 Hz Ouput Data Rate in WAKE mode
DATA_RATE_200HZ = (2 << 3)  #  200 Hz Ouput Data Rate in WAKE mode
DATA_RATE_100HZ = (3 << 3)  #  100 Hz Ouput Data Rate in WAKE mode
DATA_RATE_50HZ  = (4 << 3)  #   50 Hz Ouput Data Rate in WAKE mode
DATA_RATE_1HZ25 = (5 << 3)  # 12.5 Hz Ouput Data Rate in WAKE mode
DATA_RATE_6HZ25 = (6 << 3)  # 6.25 Hz Ouput Data Rate in WAKE mode
DATA_RATE_1HZ56 = (7 << 3)  # 1.56 Hz Ouput Data Rate in WAKE mode

DATA_RATE_DEFAULT = DATA_RATE_50HZ

DATA_RATES = {
    DATA_RATE_800HZ: 800,
    DATA_RATE_400HZ: 400,
    DATA_RATE_200HZ: 200,
    DATA_RATE_100HZ: 100,
    DATA_RATE_50HZ:  50,
    DATA_RATE_1HZ25: 12.5,
    DATA_RATE_6HZ25: 6.25,
    DATA_RATE_1HZ56: 1.56,
}

# Available auto sleep rates
ASLP_RATE_50HZ  = (0 << 6)
ASLP_RATE_12HZ5 = (1 << 6)
ASLP_RATE_6HZ25 = (2 << 6)
ASLP_RATE_1HZ56 = (3 << 6)

ASLP_RATES = {
    ASLP_RATE_50HZ:  50,
    ASLP_RATE_12HZ5: 12.5,
    ASLP_RATE_6HZ25: 6.25,
    ASLP_RATE_1HZ56: 1.56,
}

# Available interrupt pins
INT2 = 0
INT1 = 1

INTERRUPT_PINS = {
    INT1: "int1",
    INT2: "int2",
}


class MMA8X5XConn(I2CConn):

    def __init__(self):
        super(MMA8X5XConn, self).__init__()

        # Default values
        self._data_bits = 10
        self._range = RANGES[RANGE_DEFAULT]
        self._data_rate = DATA_RATES[DATA_RATE_DEFAULT]

    def setup(self, settings):
        super(MMA8X5XConn, self).setup(settings)

        self._data_bits = settings.get("data_bits", self._data_bits)

        self.config(settings)

    def config(self, settings):
        try:
            self.active(value=False)

            # Setup specified range or use default
            self.range(value=settings.get("range", self._range))

            # Setup specified data rate or use default
            self.data_rate(value=settings.get("data_rate", self._data_rate))

            # Setup interrupts if defined
            for name, pin in settings.get("interrupts", {}).iteritems():
                self.intr_pin(name, value=pin)
                self.intr(name, value=True)

        finally:
            self.active(value=True)

    def mode(self):
        """
        Indicates the current device operating mode.
        """

        res = self.read(SYSMOD)

        return MODES.get(res)

    def status(self):
        """
        Check for new set of measurement data.
        """

        ret = {}

        res = self.read(STATUS)
        ret["ready"] = {
            "x":   bool(res & STATUS_XDR),
            "y":   bool(res & STATUS_YDR),
            "z":   bool(res & STATUS_ZDR),
            "any": bool(res & STATUS_ZYXDR),
        }
        ret["overwrite"] = {
            "x":   bool(res & STATUS_XOW),
            "y":   bool(res & STATUS_YOW),
            "z":   bool(res & STATUS_ZOW),
            "any": bool(res & STATUS_ZYXOW),
        }

        return ret

    def xyz(self, decimals=4):
        """
        Read and calculate accelerometer data.
        """

        ret = {}

        bytes = self.read(OUT_X_MSB, length=6)
        words = self._concat_bytes(bytes, bits=self._data_bits)

        if log.isEnabledFor(logging.DEBUG):
            for word in words:
                log.debug("Calculating G for block: {:016b}".format(word))

        res = [self._calc_g(word, decimals=decimals) for word in words]

        ret["x"] = res[0]
        ret["y"] = res[1]
        ret["z"] = res[2]

        return ret

    def active(self, value=None):
        """
        Get or set active mode, this enables/disables periodic measurements.
        """

        ret = False

        if value == None:
            res = self.read(CTRL_REG1) & CTRL_REG1_ACTIVE 
        else:
            val = CTRL_REG1_ACTIVE if bool(value) else 0
            res = self.read_write(CTRL_REG1, CTRL_REG1_ACTIVE, val) & CTRL_REG1_ACTIVE 

        ret = res == CTRL_REG1_ACTIVE

        return ret

    def range(self, value=None):
        """
        Get or set dynamic range.
        """

        if value == None:
            res = self.read(XYZ_DATA_CFG) & XYZ_DATA_CFG_FS_MASK
        else:
            self._require_standby_mode()

            val = dict_key_by_value(RANGES, value)
            res = self.read_write(XYZ_DATA_CFG, XYZ_DATA_CFG_FS_MASK, val) & XYZ_DATA_CFG_FS_MASK
 
        # Always update range instance variable
        self._range = RANGES.get(res)

        return self._range

    def fast_read(self, value=None):
        """
        """

        if value == None:
            res = self.read(CTRL_REG1) & CTRL_REG1_F_READ
        else:
            self._require_standby_mode()

            val = CTRL_REG1_F_READ if bool(value) else 0
            res = self.read_write(CTRL_REG1, CTRL_REG1_F_READ, val) & CTRL_REG1_F_READ

        ret = res == CTRL_REG1_F_READ

        return ret

    def data_rate(self, value=None):
        """
        """

        if value == None:
            res = self.read(CTRL_REG1) & CTRL_REG1_DR_MASK
        else:
            self._require_standby_mode()

            val = dict_key_by_value(DATA_RATES, value)
            res = self.read_write(CTRL_REG1, CTRL_REG1_DR_MASK, val) & CTRL_REG1_DR_MASK

        # Always update data rate instance variable
        self._data_rate = DATA_RATES.get(res)

        return self._data_rate

    def auto_sleep(self, value=None):
        """
        If the auto-sleep is disabled, then the device can only toggle between standby and wake mode.
        If auto-sleep interrupt is enabled, transitioning from active mode to auto-sleep mode and vice versa generates an interrupt.
        """

        if value == None:
            res = self.read(CTRL_REG2) & CTRL_REG2_SLPE
        else:
            self._require_standby_mode()

            val = CTRL_REG2_SLPE if bool(value) else 0
            res = self.read_write(CTRL_REG2, CTRL_REG2_SLPE, val) & CTRL_REG2_SLPE

        ret = res == CTRL_REG2_SLPE

        return ret

    def auto_sleep_rate(self, value=None):
        """
        """

        if value == None:
            res = self.read(CTRL_REG1) & CTRL_REG1_ASLP_RATE_MASK
        else:
            self._require_standby_mode()

            val = dict_key_by_value(ASLP_RATES, value)
            res = self.read_write(CTRL_REG1, CTRL_REG1_ASLP_RATE_MASK, val) & CTRL_REG1_ASLP_RATE_MASK

        ret = ASLP_RATES.get(res)

        return ret

    def offset(self, x=None, y=None, z=None):
        """
        Set user offset correction in mg.
        Offset correction register will be erased after accelerometer reset.

        TODO: This function needs to be tested more.
        TODO: Offset might need to be adjusted according to current range?
        """

        if x != None and not -.256 <= x <= .254:
            raise ValueError("X axis offset must be between -0.256g and 0.254g")
        if y != None and not -.256 <= y <= .254:
            raise ValueError("Y axis offset must be between -0.256g and 0.254g")
        if z != None and not -.256 <= z <= .254:
            raise ValueError("Z axis offset must be between -0.256g and 0.254g")

        if x != None or y != None or z != None:
            self._require_standby_mode()

        ret = {}

        if x != None:
            self.write(OFF_X, self._signed_int(int(x * 1000 / 2)))

            # Also seems to work:
            #self.write(OFF_X, int(x * 1000 / 2))

        if y != None:
            self.write(OFF_Y, self._signed_int(int(y * 1000 / 2)))

            # Also seems to work:
            #self.write(OFF_Y, int(y * 1000 / 2))

        if z != None:
            self.write(OFF_Z, self._signed_int(int(z * 1000 / 2)))

            # Also seems to work:
            #self.write(OFF_Z, int(z * 1000 / 2))

        res = self.read(OFF_X, length=3)

        ret["x"] = self._signed_int(res[0]) * 2 / 1000
        ret["y"] = self._signed_int(res[1]) * 2 / 1000
        ret["z"] = self._signed_int(res[2]) * 2 / 1000

        return ret

    def intr_status(self):
        """
        Interrupt status of the various embedded features.
        """

        ret = {}

        res = self.read(INT_SOURCE)
        for mask, src in INTERRUPT_SOURCES.iteritems():
            ret[src] = bool(res & mask)

        return ret

    def intr(self, source, value=None):
        """
        Enable/disable interrupts.
        """

        mask = dict_key_by_value(INTERRUPT_SOURCES, source)

        if value == None:
            res = self.read(CTRL_REG4) & mask
        else:
            self._require_standby_mode()

            val = mask if bool(value) else 0
            res = self.read_write(CTRL_REG4, mask, val) & mask

        ret = bool(res)

        return ret

    def intr_pin(self, source, value=None):
        """
        Configures output pin of interrupts.
        """

        mask = dict_key_by_value(INTERRUPT_SOURCES, source)

        if value == None:
            res = self.read(CTRL_REG5) & mask
        else:
            self._require_standby_mode()

            val = dict_key_by_value(INTERRUPT_PINS, value)
            res = self.read_write(CTRL_REG5, mask, val * mask) & mask

        ret = INTERRUPT_PINS.get(res / mask)

        return ret

    def intr_pin_pol(self, invert=None):
        """
        Interrupt polarity active high, or active low.
        """

        if invert == None:
            res = self.read(CTRL_REG3) & CTRL_REG3_IPOL
        else:
            self._require_standby_mode()

            val = CTRL_REG3_IPOL if not bool(invert) else 0
            res = self.read_write(CTRL_REG3, CTRL_REG3_IPOL, val) & CTRL_REG3_IPOL

        ret = res == CTRL_REG3_IPOL

        return ret

    def wake(self, source, value=None):
        """
        Enable/disable wake up sources.
        """

        mask = dict_key_by_value(WAKE_SOURCES, source)

        if value == None:
            res = self.read(CTRL_REG3) & mask
        else:
            self._require_standby_mode()

            val = mask if bool(value) else 0
            res = self.read_write(CTRL_REG3, mask, val) & mask

        ret = bool(res)

        return ret

    def motion_config(self, freefall=None, event_latch=False, x=False, y=False, z=False):
        """
        Freefall/motion configuration for setting up the conditions of the freefall or motion function.
        """

        ret = {}

        if freefall == None:
            res = self.read(FF_MT_CFG)
        else:
            self._require_standby_mode()

            val = FF_MT_CFG_OAE * int(freefall) \
                | FF_MT_CFG_ELE * int(event_latch) \
                | FF_MT_CFG_XEFE * int(x) \
                | FF_MT_CFG_YEFE * int(y) \
                | FF_MT_CFG_ZEFE * int(z)
            res = self.write(FF_MT_CFG, val)

        ret["freefall"] = not bool(FF_MT_CFG_OAE & res)
        ret["event_latch"] = bool(FF_MT_CFG_ELE & res)
        ret["x"] = bool(FF_MT_CFG_XEFE & res)
        ret["y"] = bool(FF_MT_CFG_YEFE & res)
        ret["z"] = bool(FF_MT_CFG_ZEFE & res)

        return ret

    def motion_event(self):
        """
        Read freefall and motion source register that keeps track of acceleration events.
        """

        ret = {}

        res = self.read(FF_MT_SRC)
        ret["active"] = bool(FF_MT_SRC_EA & res)
        ret["x"] = bool(FF_MT_SRC_XHE & res)
        ret["x_neg"] = bool(FF_MT_SRC_XHP & res)
        ret["y"] = bool(FF_MT_SRC_YHE & res)
        ret["y_neg"] = bool(FF_MT_SRC_YHP & res)
        ret["z"] = bool(FF_MT_SRC_ZHE & res)
        ret["z_neg"] = bool(FF_MT_SRC_ZHP & res)

        return ret

    def motion_threshold(self, value=None, counter=False):
        """
        Freefall and motion threshold configuration.
        """

        # TODO: Enable write also
        res = self.read(FF_MT_THS)

        return res

    def motion_debounce(self, value=None):
        """
        Set the number of debounce sample counts for the event trigger.
        """

        # TODO: Enable write also
        res = self.read(FF_MT_COUNT)

        return res

    def _require_standby_mode(self):
        res = self.read(SYSMOD)
        if res != MODE_STANDBY:
            raise Exception("Standby mode is required to perform this change")

    def _range_as_g(self, value):
        return 1 << (value + 1)

    def _calc_g(self, word, decimals=4):
        s_int = self._signed_int(word, bits=self._data_bits)
        div = pow(2, self._data_bits - 1) / self._range
        return round(s_int / div, decimals)
