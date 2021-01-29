from __future__ import division

import datetime
import logging
import time

from common_util import dict_key_by_value
from i2c_conn import I2CConn
from retrying import retry


log = logging.getLogger(__name__)

DEBUG = log.isEnabledFor(logging.DEBUG)


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

# FIFO status register
F_STATUS_CNT_MASK  = 0x3F
F_STATUS_WMRK_FLAG = (1 << 6)
F_STATUS_OVF       = (1 << 7)

# FIFO setup register
F_SETUP_MODE_MASK = 0xC0
F_SETUP_WMRK_MASK = 0x3F

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

# Transient configuration register
TRANSIENT_CFG_HPF_BYP = (1 << 0)
TRANSIENT_CFG_XTEFE   = (1 << 1)
TRANSIENT_CFG_YTEFE   = (1 << 2)
TRANSIENT_CFG_ZTEFE   = (1 << 3)
TRANSIENT_CFG_ELE     = (1 << 4)

# Transient source register
TRANSIENT_SRC_X_TRANS_POL = (1 << 0)
TRANSIENT_SRC_XTRANSE     = (1 << 1)
TRANSIENT_SRC_Y_TRANS_POL = (1 << 2)
TRANSIENT_SRC_YTRANSE     = (1 << 3)
TRANSIENT_SRC_Z_TRANS_POL = (1 << 4)
TRANSIENT_SRC_ZTRANSE     = (1 << 5)
TRANSIENT_SRC_EA          = (1 << 6)

# Transient threshold registers
TRANSIENT_THS_MASK   = 0x7F     # 0x01111111
TRANSIENT_THS_DBCNTM = (1 << 7) # 0x10000000

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

# Available FIFO modes and more
FIFO_MODE_DISABLED = (0 << 6)
FIFO_MODE_CIRCULAR = (1 << 6)
FIFO_MODE_FILL     = (2 << 6)
FIFO_MODE_TRIGGER  = (3 << 6)

FIFO_MODE_DEFAULT = FIFO_MODE_DISABLED

FIFO_MODES = {
    FIFO_MODE_DISABLED: "disabled",
    FIFO_MODE_CIRCULAR: "circular",
    FIFO_MODE_FILL:     "fill",
    FIFO_MODE_TRIGGER:  "trigger"
}

FIFO_WATERMARK_DEFAULT = 0

FIFO_EMPTY_XYZ = [0x80, 0x80, 0x80, 0x80, 0x80, 0x80]


class MMA8X5XConn(I2CConn):

    def __init__(self, stats={}):
        super(MMA8X5XConn, self).__init__()

        self._stats = stats
        self._settings = {}

        # Default values
        self._data_bits = 10
        self._range = RANGES[RANGE_DEFAULT]
        self._data_rate = DATA_RATES[DATA_RATE_DEFAULT]
        self._fifo_mode = FIFO_MODES[FIFO_MODE_DEFAULT]
        self._fifo_watermark = FIFO_WATERMARK_DEFAULT

    def init(self, settings):
        super(MMA8X5XConn, self).init(settings)

        self._data_bits = settings.get("data_bits", self._data_bits)
        self._settings = settings

    @property
    def settings(self):
        return self._settings

    def configure(self, **settings):
        """
        Applies specific settings.
        """

        try:

            # Ensure in standby mode
            self.active(value=False)

            # Set specified range or use default
            self.range(value=settings.get("range", self._range))

            # Set specified data rate or use default
            self.data_rate(value=settings.get("data_rate", self._data_rate))

            # Set specified FIFO mode or use default
            # NOTE: Must be disabled before able to change between two enabled modes
            self.fifo_mode(value=self._fifo_mode)  # Always disable
            if "fifo_mode" in settings and settings["fifo_mode"] != self._fifo_mode:
                self.fifo_mode(value=settings["fifo_mode"])

            # Configure specified FIFO watermark or use default
            self.fifo_watermark(value=settings.get("fifo_watermark", self._fifo_watermark))

            # Configure transient detector
            if "transient_detector" in settings:
                td_settings = settings.get("transient_detector")
                self.transient_threshold(value=td_settings.get("sensitivity"))
                self.transient_config(
                    mode=td_settings.get("transient"),
                    x=td_settings.get("x_enabled"),
                    y=td_settings.get("y_enabled"),
                    z=td_settings.get("z_enabled"),
                    event_latch=False,
                )

            # Configure interrupts if defined
            for name, pin in settings.get("interrupts", {}).iteritems():
                self.intr_pin(name, value=pin)
                self.intr(name, value=True)

            # Ensure settings are updated
            self._settings.update(settings)

        finally:
            self.active(value=True)

    def open(self):
        super(MMA8X5XConn, self).open()

        try:

            # Reset if requested
            if self._settings.get("reset", False):
                self.reset(value=True)

                # Give time to recover after reset
                time.sleep(.1)

            self.configure(**self._settings)
        except:
            log.exception("Failed to configure after opening connection")

            # Ensure connection is closed again
            self.close()

            raise

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

        if self._fifo_mode != FIFO_MODES[FIFO_MODE_DISABLED]:
            raise Exception("FIFO mode is enabled - only FIFO status is available")

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

    def fifo_status(self):
        """
        Information about the current FIFO status if enabled.
        """

        if self._fifo_mode == FIFO_MODES[FIFO_MODE_DISABLED]:
            raise Exception("FIFO mode is disabled - only real time status is available")

        ret = {}

        res = self.read(STATUS)
        ret["overflowed"] = bool(res & F_STATUS_OVF),
        ret["watermark_reached"] = bool(res & F_STATUS_WMRK_FLAG),
        ret["sample_count"] = int(res & F_STATUS_CNT_MASK)

        return ret

    def xyz(self, decimals=4, empty_readout=None):
        """
        Read out and calculate real time accelerometer data.
        """

        ret = {}

        bytes = self.read(OUT_X_MSB, length=6)

        # Check if empty readout
        if empty_readout and bytes == empty_readout:
            if DEBUG:
                log.debug("Skipping empty XYZ readout")

            return

        words = self._concat_bytes(bytes, bits=self._data_bits)
        if DEBUG:
            for word in words:
                log.debug("Calculating G for block: {:016b}".format(word))

        res = [self._calc_g(word, decimals=decimals) for word in words]

        ret["x"] = res[0]
        ret["y"] = res[1]
        ret["z"] = res[2]

        return ret

    def xyz_buffer(self, decimals=4, limit=128, interrupt_timestamp=None):
        """
        Read out and calculate accelerometer data from FIFO buffer until empty or limit reached.
        """

        ret = []

        # Get FIFO status in order to reset interrupt
        status = self.fifo_status()

        # Update buffer statistics
        stats = self._stats.setdefault("buffer", {})
        stats["await_readout"] = status["sample_count"]
        if status["overflowed"]:
            stats["overflow"] = stats.get("overflow", 0) + 1

            # TODO HN: This happens every time on interrupt
            #log.warning("Overflow in FIFO buffer detected")

        if status["watermark_reached"]:
            stats["watermark"] = stats.get("watermark", 0) + 1

        # Ensure that we have a reference timestamp
        if interrupt_timestamp == None:
            log.warning("No interrupt timestamp given as reference - uses current timestamp which can give an inaccurate offset")

            interrupt_timestamp = datetime.datetime.utcnow()

        # Read from buffer until empty
        count = 0
        while True:
            res = self.xyz(decimals=decimals, empty_readout=FIFO_EMPTY_XYZ)

            # Stop when buffer returns empty readout
            if not res:
                if DEBUG:
                    log.debug("FIFO buffer is empty after {:} XYZ readout(s)".format(count))

                break

            # Increment counter
            count += 1

            # Calculate and set timestamp
            timestamp = interrupt_timestamp - datetime.timedelta(
                milliseconds=((self._fifo_watermark or 32) - count) * (1000 / self._data_rate))
            res["_stamp"] = timestamp.isoformat()

            # Enforce type
            res["_type"] = "xyz"

            ret.append(res)

            # Check if limit has been reached
            if limit and count >= limit:
                log.warning("FIFO buffer readout limit of {:} reached - this may indicate that more data is being produced than can be handled".format(limit))

                break

        stats["last_readout"] = count
        stats["total_readout"] = stats.get("total_readout", 0) + count

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

    def reset(self, value=None):
        """
        When the reset is enabled, all registers are reset and are loaded with default values, no matter whether it is in active/wake, active/sleep, or standby mode.
        The I2C communication system is reset to avoid accidental corrupted data access.
        """

        if value == None:
            res = self.read(CTRL_REG2) & CTRL_REG2_RST
        else:
            log.info("Performing software reset of device")

            val = CTRL_REG2_RST if bool(value) else 0
            res = self.read_write(CTRL_REG2, CTRL_REG2_RST, val) & CTRL_REG2_RST

        ret = res == CTRL_REG2_RST

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

    def fifo_mode(self, value=None):
        """
        Setup FIFO buffer overflow mode.
        """

        if value == None:
            res = self.read(F_SETUP) & F_SETUP_MODE_MASK
        else:
            if value != FIFO_MODES[FIFO_MODE_DISABLED] and self._fifo_mode != FIFO_MODES[FIFO_MODE_DISABLED]:
                raise Exception("Must be disabled first before changing to different mode")

            val = dict_key_by_value(FIFO_MODES, value)
            res = self.read_write(F_SETUP, F_SETUP_MODE_MASK, val) & F_SETUP_MODE_MASK
 
        # Always update FIFO mode instance variable
        self._fifo_mode = FIFO_MODES.get(res)

        return self._fifo_mode

    def fifo_watermark(self, value=None):
        """
        Setup FIFO event sample count watermark.
        """

        if value == None:
            res = self.read(F_SETUP) & F_SETUP_WMRK_MASK
        else:
            self._require_standby_mode()

            val = int(value)
            res = self.read_write(F_SETUP, F_SETUP_WMRK_MASK, val) & F_SETUP_WMRK_MASK
 
        # Always update FIFO watermark instance variable
        self._fifo_watermark = res

        return res

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

    def transient_config(self, mode=None, x=None, y=None, z=None, event_latch=None):
        """
        Configure transient detector or read data.

        Optional arguments:
          - mode (string): The mode the transient detector should work in. Possible options are 'transient' and 'motion'
          - x (bool): Should events trigger when X axis change is detected above threshold (default: False)
          - y (bool): Should events trigger when Y axis change is detected above threshold (default: False)
          - z (bool): Should events trigger when Z axis change is detected above threshold (default: False)
          - event_latch (bool): Should event data be kept in the source register until read (default: True)
        """

        if mode == None:
            res = self.read(TRANSIENT_CFG)
        else:
            if mode not in ["transient", "motion"]:
                raise ValueError("'mode' must be 'transient' or 'motion'.")

            bypass_high_pass_filter = 0 if mode == "transient" else 1

            mask = TRANSIENT_CFG_HPF_BYP
            val = TRANSIENT_CFG_HPF_BYP * int(bypass_high_pass_filter)

            if x != None:
                mask |= TRANSIENT_CFG_XTEFE
                val  |= TRANSIENT_CFG_XTEFE * int(x)
            if y != None:
                mask |= TRANSIENT_CFG_YTEFE
                val  |= TRANSIENT_CFG_YTEFE * int(y)
            if z != None:
                mask |= TRANSIENT_CFG_ZTEFE
                val  |= TRANSIENT_CFG_ZTEFE * int(z)
            if event_latch != None:
                mask |= TRANSIENT_CFG_ELE
                val  |= TRANSIENT_CFG_ELE * int(event_latch)

            self._require_standby_mode()
            res = self.read_write(TRANSIENT_CFG, mask, val)

        ret = {}
        ret["mode"] = "motion" if bool(TRANSIENT_CFG_HPF_BYP & res) else "transient" # 0 == transient, 1 == motion
        ret["event_latch"] = bool(TRANSIENT_CFG_ELE & res)
        ret["x_enabled"] = bool(TRANSIENT_CFG_XTEFE & res)
        ret["y_enabled"] = bool(TRANSIENT_CFG_YTEFE & res)
        ret["z_enabled"] = bool(TRANSIENT_CFG_ZTEFE & res)
        return ret

    def transient_threshold(self, value=None, debounce_mode=None):
        """
        Configure the threshold at which the transient detector will fire an event.

        Formula is the following:

            `value * 0.063 = g`

        where `g` is the amount of acceleration that needs to happen in order to activate
        the trigger. The maximum value you can pass is 127.

        Optional arguments:
          - value (int): The value to be assigned as the threshold value.
          - debounce_mode (int): 0 or 1. Defines the mode of the debounce counter.
            - 0: increments or decrements debounce counter
            - 1: increments or clears debounce counter
        """

        if not value:
            res = self.read(TRANSIENT_THS)
        else:
            if type(value) != int or value < 0 or value > 127:
                raise ValueError("'value' must be an int between 0 and 127")
            if debounce_mode != None and debounce_mode != 0 and debounce_mode != 1:
                raise ValueError("'debounce_mode' must be a value of 0 or 1")

            self._require_standby_mode()

            mask = TRANSIENT_THS_MASK
            val = TRANSIENT_THS_MASK & value

            if debounce_mode != None:
                mask |= TRANSIENT_THS_DBCNTM
                val  |= TRANSIENT_THS_DBCNTM * int(debounce_mode)

            res = self.read_write(TRANSIENT_THS, mask, val)

        ret = {}
        ret["debounce_mode"] = 1 if bool(TRANSIENT_THS_DBCNTM & res) else 0
        ret["value"] = (TRANSIENT_THS_MASK & res)
        return ret

    def transient_event(self):
        """
        Read transient event data.
        """

        ret = {}
        res = self.read(TRANSIENT_SRC)

        ret["event_triggered"] = bool(TRANSIENT_SRC_EA & res)
        ret["x"] = bool(TRANSIENT_SRC_XTRANSE & res)
        ret["x_neg"] = bool(TRANSIENT_SRC_X_TRANS_POL & res)
        ret["y"] = bool(TRANSIENT_SRC_YTRANSE & res)
        ret["y_neg"] = bool(TRANSIENT_SRC_Y_TRANS_POL & res)
        ret["z"] = bool(TRANSIENT_SRC_ZTRANSE & res)
        ret["z_neg"] = bool(TRANSIENT_SRC_Z_TRANS_POL & res)

        return ret

    def _require_standby_mode(self):
        res = self.read(SYSMOD)
        if res != MODE_STANDBY:
            raise Exception("Standby mode is required to perform this change")

    def _range_as_g(self, value):
        return 1 << (value + 1)

    def _calc_g(self, word, decimals=4):
        s_int = self._signed_int(word, bits=self._data_bits)
        div = pow(2, self._data_bits - 1) / self._range
        return round(s_int / div, decimals) + 0  # Adding zero will prevent '-0.0'
