from __future__ import division

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

# Available system modes
MODE_STANDBY = 0
MODE_WAKE    = 1
MODE_SLEEP   = 2

# Available oversampling modes for both wake mode (MOD) and sleep mode (SMOD)
MODS_NORMAL = 0
MODS_LNLP   = 1
MODS_HR     = 2
MODS_LP     = 3

# Available data sampling rates
DATA_RATE_800HZ = (0 << 3)  # 800  Hz Ouput Data Rate in WAKE mode
DATA_RATE_400HZ = (1 << 3)  # 400  Hz Ouput Data Rate in WAKE mode
DATA_RATE_200HZ = (2 << 3)  # 200  Hz Ouput Data Rate in WAKE mode
DATA_RATE_100HZ = (3 << 3)  # 100  Hz Ouput Data Rate in WAKE mode
DATA_RATE_50HZ  = (4 << 3)  # 50   Hz Ouput Data Rate in WAKE mode
DATA_RATE_1HZ25 = (5 << 3)  # 12.5 Hz Ouput Data Rate in WAKE mode
DATA_RATE_6HZ25 = (6 << 3)  # 6.25 Hz Ouput Data Rate in WAKE mode
DATA_RATE_1HZ56 = (7 << 3)  # 1.56 Hz Ouput Data Rate in WAKE mode

DATE_RATE_DEFAULT = DATA_RATE_200HZ

# Available auto sleep rates
ASLP_RATE_50HZ  = (0 << 6)
ASLP_RATE_12HZ5 = (1 << 6)
ASLP_RATE_6HZ25 = (2 << 6)
ASLP_RATE_1HZ56 = (3 << 6)

# Available interrupt pins
INT2 = 0
INT1 = 1


def concat_bytes(bytes, bits=10):
    words = []
    for idx in range(0, len(bytes), 2): # Only loop on even numbers
        # Concat bytes
        word = bytes[idx] << 8 | bytes[idx + 1]
        # Shorten word to match specified bit length
        word = word >> 16 - bits
        words.append(word)
    return words


def signed_int(word, bits=8):
    # Calculate signed integer value
    return word - (word >> bits-1) * pow(2, bits)


def calc_g(word, bits=8, g_range=2, decimals=4):
    s_int = signed_int(word, bits=bits)
    div = pow(2, bits - 1) / g_range
    return round(s_int / div, decimals)


def update_bits(byte, mask, val):
    # First clear the bits indicated by the mask
    byte &= ~mask
    if val:
        # Then set the bits indicated by the value
        byte |= val
    return byte


def range_as_g(val):
    return 1 << (val + 1)
