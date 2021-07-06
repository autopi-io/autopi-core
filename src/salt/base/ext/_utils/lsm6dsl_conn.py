import ctypes
import logging
import RPi.GPIO as gpio
import time
import yaml

from common_util import dict_key_by_value
from i2c_conn import I2CConn


log = logging.getLogger(__name__)

DEBUG = log.isEnabledFor(logging.DEBUG)


### Registers ###
FIFO_CTRL1 = 0x06 # FIFO configuration registers
FIFO_CTRL2 = 0x07
FIFO_CTRL3 = 0x08
FIFO_CTRL4 = 0x09
FIFO_CTRL5 = 0x0A

INT1_CTRL = 0x0D # INT1 pin control
INT2_CTRL = 0x0E # INT2 pin control
WHO_AM_I  = 0x0F # Who I Am ID

CTRL1_XL = 0x10 # Accelerometer and gyroscope control registers
CTRL2_G  = 0x11
CTRL3_C  = 0x12
CTRL4_C  = 0x13
CTRL5_C  = 0x14
CTRL6_C  = 0x15
CTRL7_G  = 0x16
CTRL8_XL  = 0x17
CTRL9_XL  = 0x18
CTRL10_C  = 0x19

OUTX_L_G = 0x22 # Gyroscope outpur registers for user interface
OUTX_H_G = 0x23
OUTY_L_G = 0x24
OUTY_H_G = 0x25
OUTZ_L_G = 0x26
OUTZ_H_G = 0x27

OUTX_L_XL = 0x28 # Accelerometer output registers
OUTX_H_XL = 0x29
OUTY_L_XL = 0x2A
OUTY_H_XL = 0x2B
OUTZ_L_XL = 0x2C
OUTZ_H_XL = 0x2D

FIFO_STATUS1 = 0x3A # FIFO status registers
FIFO_STATUS2 = 0x3B
FIFO_STATUS3 = 0x3C
FIFO_STATUS4 = 0x3D

FIFO_DATA_OUT_L = 0x3E # FIFO data output registers
FIFO_DATA_OUT_H = 0x3F

### Masks ###
FIFO_CTRL2_FTH_MASK  = 0x07

FIFO_CTRL3_DEC_FIFO_GYRO_MASK = 0x38
FIFO_CTRL3_DEC_FIFO_XL_MASK = 0x07

FIFO_CTRL5_ODR_MASK  = 0x78
FIFO_CTRL5_MODE_MASK = 0x07

CTRL1_XL_ODR_MASK = 0xF0
CTRL1_XL_FS_MASK  = 0x0C

CTRL3_C_BOOT_MASK      = (0x01 << 7)
CTRL3_C_BDU_MASK       = (0x01 << 6)
CTRL3_C_H_LACTIVE_MASK = (0x01 << 5)
CTRL3_C_PP_OD_MASK     = (0x01 << 4)
CTRL3_C_SIM_MASK       = (0x01 << 3)
CTRL3_C_IF_INC_MASK    = (0x01 << 2)
CTRL3_C_BLE_MASK       = (0x01 << 1)
CTRL3_C_SW_RESET_MASK  = 0x01

FIFO_STATUS2_WATERM_MASK          = 0x80
FIFO_STATUS2_OVER_RUN_MASK        = 0x40
FIFO_STATUS2_FIFO_FULL_SMART_MASK = 0x20
FIFO_STATUS2_FIFO_EMPTY           = 0x10
FIFO_STATUS2_DIFF_FIFO_MASK       = 0x07

### Maps ###

# Accelerometer Output Data Rate (ODR)
XL_ODR_OFF     = (0x0 << 4)
XL_ODR_12_5HZ  = (0x1 << 4)
XL_ODR_26HZ    = (0x2 << 4)
XL_ODR_52HZ    = (0x3 << 4)
XL_ODR_104HZ   = (0x4 << 4)
XL_ODR_208HZ   = (0x5 << 4)
XL_ODR_416HZ   = (0x6 << 4)
XL_ODR_833HZ   = (0x7 << 4)
XL_ODR_1_66KHZ = (0x8 << 4)
XL_ODR_3_33KHZ = (0x9 << 4)
XL_ODR_6_66KHZ = (0xA << 4)
XL_ODR_DEFAULT = XL_ODR_OFF

# Accelerometer ODR map
CTRL1_XL_ODR_MAP = {
    XL_ODR_OFF:     0,
    XL_ODR_12_5HZ:  12.5,
    XL_ODR_26HZ:    26,
    XL_ODR_52HZ:    52,
    XL_ODR_104HZ:   104,
    XL_ODR_208HZ:   208,
    XL_ODR_416HZ:   416,
    XL_ODR_833HZ:   833,
    XL_ODR_1_66KHZ: 1660,
    XL_ODR_3_33KHZ: 3330,
    XL_ODR_6_66KHZ: 6660,
}

# Accelerometer Full Scale
XL_FS_2G  = (0x0 << 2)
XL_FS_4G  = (0x2 << 2)
XL_FS_8G  = (0x3 << 2)
XL_FS_16G = (0x1 << 2) # odd, I know. Look at the DS
XL_FS_DEFAULT = XL_FS_2G

CTRL1_XL_FS_MAP = {
    XL_FS_2G:  2,
    XL_FS_4G:  4,
    XL_FS_8G:  8,
    XL_FS_16G: 16,
}

XL_FS_SCALE_MAP = {
    2:  0.061,
    4:  0.122,
    8:  0.244,
    16: 0.488,
}

# FIFO gyro decimations
DEC_FIFO_GYRO_NOT_IN_FIFO = (0x0 << 3)
DEC_FIFO_GYRO_NO_DEC      = (0x1 << 3)
DEC_FIFO_GYRO_FAC_2       = (0x2 << 3)
DEC_FIFO_GYRO_FAC_3       = (0x3 << 3)
DEC_FIFO_GYRO_FAC_4       = (0x4 << 3)
DEC_FIFO_GYRO_FAC_8       = (0x5 << 3)
DEC_FIFO_GYRO_FAC_16      = (0x6 << 3)
DEC_FIFO_GYRO_FAC_32      = (0x7 << 3)

# FIFO gyro decimation map
FIFO_CTRL3_DEC_FIFO_GYRO_MAP = {
    DEC_FIFO_GYRO_NOT_IN_FIFO: -1,
    DEC_FIFO_GYRO_NO_DEC:       0,
    DEC_FIFO_GYRO_FAC_2:        2,
    DEC_FIFO_GYRO_FAC_3:        3,
    DEC_FIFO_GYRO_FAC_4:        4,
    DEC_FIFO_GYRO_FAC_8:        8,
    DEC_FIFO_GYRO_FAC_16:       16,
    DEC_FIFO_GYRO_FAC_32:       32,
}

# FIFO acc decimations
DEC_FIFO_XL_NOT_IN_FIFO = 0x0
DEC_FIFO_XL_NO_DEC      = 0x1
DEC_FIFO_XL_FAC_2       = 0x2
DEC_FIFO_XL_FAC_3       = 0x3
DEC_FIFO_XL_FAC_4       = 0x4
DEC_FIFO_XL_FAC_8       = 0x5
DEC_FIFO_XL_FAC_16      = 0x6
DEC_FIFO_XL_FAC_32      = 0x7

# FIFO acc decimation map
FIFO_CTRL3_DEC_FIFO_XL_MAP = {
    DEC_FIFO_XL_NOT_IN_FIFO: -1,
    DEC_FIFO_XL_NO_DEC:       0,
    DEC_FIFO_XL_FAC_2:        2,
    DEC_FIFO_XL_FAC_3:        3,
    DEC_FIFO_XL_FAC_4:        4,
    DEC_FIFO_XL_FAC_8:        8,
    DEC_FIFO_XL_FAC_16:       16,
    DEC_FIFO_XL_FAC_32:       32,
}

# FIFO Output Data Rate (ODR) values
FIFO_ODR_DISABLED = (0x0 << 3)
FIFO_ODR_12_5HZ   = (0x1 << 3)
FIFO_ODR_26HZ     = (0x2 << 3)
FIFO_ODR_52HZ     = (0x3 << 3)
FIFO_ODR_104HZ    = (0x4 << 3)
FIFO_ODR_208HZ    = (0x5 << 3)
FIFO_ODR_416HZ    = (0x6 << 3)
FIFO_ODR_833HZ    = (0x7 << 3)
FIFO_ODR_1_66KHZ  = (0x8 << 3)
FIFO_ODR_3_33KHZ  = (0x9 << 3)
FIFO_ODR_6_66KHZ  = (0xA << 3)

# FIFO ODR map
FIFO_CTRL5_ODR_MAP = {
    FIFO_ODR_DISABLED: 0,
    FIFO_ODR_12_5HZ:   12.5,
    FIFO_ODR_26HZ:     26,
    FIFO_ODR_52HZ:     52,
    FIFO_ODR_104HZ:    104,
    FIFO_ODR_208HZ:    208,
    FIFO_ODR_416HZ:    416,
    FIFO_ODR_833HZ:    833,
    FIFO_ODR_1_66KHZ:  1660,
    FIFO_ODR_3_33KHZ:  3330,
    FIFO_ODR_6_66KHZ:  6660,
}

# FIFO Modes
FIFO_MODE_BYPASS     = 0x0 # aka disabled mode
FIFO_MODE_FIFO       = 0x1
FIFO_MODE_CONTINUOUS = 0x6
# there's more, but I have no clue how they work or how to describe them

# FIFO Mode map
FIFO_CTRL5_MODE_MAP = {
    FIFO_MODE_BYPASS:     'bypass', # aka disabled mode
    FIFO_MODE_FIFO:       'fifo',
    FIFO_MODE_CONTINUOUS: 'continuous',
}

### Interrupts ###
INT1_DRDY_XL       = (1 << 0)
INT1_DRDY_G        = (1 << 1)
INT1_BOOT          = (1 << 2)
INT1_FTH           = (1 << 3)
INT1_FIFO_OVR      = (1 << 4)
INT1_FULL_FLAG     = (1 << 5)
INT1_SIGN_MOT      = (1 << 6)
INT1_STEP_DETECTOR = (1 << 7)

INT1_SOURCES = {
    INT1_DRDY_XL:       "acc_data",
    INT1_DRDY_G:        "gyro_data",
    INT1_BOOT:          "boot",
    INT1_FTH:           "fifo_threshold",
    INT1_FIFO_OVR:      "fifo_overrun",
    INT1_FULL_FLAG:     "fifo_full_flag",
    INT1_SIGN_MOT:      "motion",
    INT1_STEP_DETECTOR: "step",
}

INT2_DRDY_XL       = (1 << 0)
INT2_DRDY_G        = (1 << 1)
INT2_DRDY_TEMP     = (1 << 2)
INT2_FTH           = (1 << 3)
INT2_FIFO_OVR      = (1 << 4)
INT2_FULL_FLAG     = (1 << 5)
INT2_STEP_COUNT_OV = (1 << 6)
INT2_STEP_DELTA    = (1 << 7)

INT2_SOURCES = {
    INT2_DRDY_XL:       "acc_data",
    INT2_DRDY_G:        "gyro_data",
    INT2_DRDY_TEMP:     "temp_data",
    INT2_FTH:           "fifo_threshold",
    INT2_FIFO_OVR:      "fifo_overrun",
    INT2_FULL_FLAG:     "fifo_full_flag",
    INT2_STEP_COUNT_OV: "step_counter_overflow",
    INT2_STEP_DELTA:    "step_delta",
}


class LSM6DSLConn(I2CConn):

    def __init__(self, settings):
        super(LSM6DSLConn, self).__init__()

        self._settings = settings

        self._xl_fs = None
        self._xl_scale = None

        self._xl_odr = None

        self.init(settings)

    @property
    def settings(self):
        return self._settings

    @property
    def range(self):
        """
        Added for backward compatibility.
        """

        return self._xl_fs or self._settings.get("range", self._settings.get("acc_full_scale", CTRL1_XL_FS_MAP[XL_FS_DEFAULT]))

    @property
    def rate(self):
        """
        Added for backward compatibility.
        """

        return self._xl_odr or self._settings.get("rate", self._settings.get("acc_output_data_rate", CTRL1_XL_ODR_MAP[XL_ODR_DEFAULT]))

    def open(self):
        super(LSM6DSLConn, self).open()

        try:

            # Reset if requested
            if self._settings.get("reset", False):
                self.reset(confirm=True)

                # Give time to recover after reset
                time.sleep(.1)

            self.configure()
        except:
            log.exception("Failed to configure after opening connection")

            # Ensure connection is closed again
            self.close()

            raise

    def configure(self, **settings):
        """
        Applies specific settings.
        """

        self._settings.update(settings)

        if "block_data_update" in self._settings:
            self.block_data_update(value=self._settings["block_data_update"])

        if "intr_activation_level" in self._settings:
            self.intr_activation_level(value=self._settings["intr_activation_level"])

        # Setup interrupts if available
        if self._settings.get("interrupts", None):
            for pin, enabled_sources in self._settings["interrupts"].items():
                for source in enabled_sources:
                    self.intr(source, pin, value=True)

        self.acc_full_scale(value=self._settings.get("range", self._settings.get("acc_full_scale", CTRL1_XL_FS_MAP[XL_FS_DEFAULT])))

        self.acc_output_data_rate(value=self._settings.get("rate", self._settings.get("acc_output_data_rate", CTRL1_XL_ODR_MAP[XL_ODR_DEFAULT])))

    def reset(self, confirm=False):
        if not confirm:
            raise Exception("This action will reset the LSM6DSL chip. This loses all settings applied. Add 'confirm=true' to force the operation")

        log.info("Performing software reset of device")

        self.read_write(CTRL3_C, CTRL3_C_SW_RESET_MASK, 1)

    def block_data_update(self, value=None):
        """
        Get or set block data update setting.

        value = False: Continuous update
        value = True: Output registers not updated until MSB and LSB have been read
        """
        if value == None:
            res = self.read(CTRL3_C) & CTRL3_C_BDU_MASK
        else:
            val = CTRL3_C_BDU_MASK if bool(value) else 0
            res = self.read_write(CTRL3_C, CTRL3_C_BDU_MASK, val) & CTRL3_C_BDU_MASK

        return bool(res)

    def intr_activation_level(self, value=None):
        """
        Get or set interrupt activation level

        value = False: Interrupt output pads active high
        value = True: Interrupt output pads active low
        """
        if value == None:
            res = self.read(CTRL3_C) & CTRL3_C_H_LACTIVE_MASK
        else:
            val = CTRL3_C_H_LACTIVE_MASK if bool(value) else 0
            res = self.read_write(CTRL3_C, CTRL3_C_H_LACTIVE_MASK, val) & CTRL3_C_H_LACTIVE_MASK
        
        return bool(res)

    def intr(self, source, pin, value=None):
        """
        Get or set interrupt registers.
        
        Parameters:
          - source (string): the name of the interrupt source. Take a look at INT1_SOURCES and
            INT2_SOURCES
          - pin (string): The name of the pin. One of 'int1' or 'int2'.
          - value (bool): Default None. Whether the interrupt source should be active. If no value
            provided, the current value is queried and returned.
        """
        if pin == 'int1':
            mask = dict_key_by_value(INT1_SOURCES, source)
            register = INT1_CTRL
        elif pin == 'int2':
            mask = dict_key_by_value(INT2_SOURCES, source)
            register = INT2_CTRL
        else:
            raise ValueError('Unrecognized pin {}.'.format(pin))

        if value == None:
            res = self.read(register) & mask
        else:
            val = mask if bool(value) else 0
            res = self.read_write(register, mask, val) & mask

        return bool(res)

    def xyz(self, **kwargs):
        return self.acc_xyz(**kwargs)

    def acc_xyz(self, decimals=4):
        ret = {}

        buf = self.read(OUTX_L_XL, length=6)

        x = self._signed_int((buf[0] | (buf[1] << 8)), bits=16) * self._xl_scale / 1000.0
        y = self._signed_int((buf[2] | (buf[3] << 8)), bits=16) * self._xl_scale / 1000.0
        z = self._signed_int((buf[4] | (buf[5] << 8)), bits=16) * self._xl_scale / 1000.0

        ret["x"] = round(x, decimals)
        ret["y"] = round(y, decimals)
        ret["z"] = round(z, decimals)

        return ret

    def acc_output_data_rate(self, value=None):
        """
        Gets or sets the output data rate (ODR) for the accelerometer. If value is not provided, the
        current ODR will be read. Otherwise, the value will be set as the new ODR. Returns the
        ODR value.

        Parameters:
        - value: None or a number. View possible values in `CTRL1_XL_ODR_MAP`
        """

        if value == None:
            # read current value
            res = self.read(CTRL1_XL) & CTRL1_XL_ODR_MASK
        else:
            # set new value
            val = dict_key_by_value(CTRL1_XL_ODR_MAP, value)
            res = self.read_write(CTRL1_XL, CTRL1_XL_ODR_MASK, val) & CTRL1_XL_ODR_MASK

        self._xl_odr = CTRL1_XL_ODR_MAP[res]
        return self._xl_odr

    def acc_full_scale(self, value=None):
        """
        Gets or sets the full scale (FS) for the accelerometer. If value is not provided, the current
        FS will be read.

        Parameters:
        - value: None or a number. View possible values in `CTRL1_XL_FS_MAP`
        """

        if value == None:
            # read current value
            res = self.read(CTRL1_XL) & CTRL1_XL_FS_MASK
        else:
            # set new value
            val = dict_key_by_value(CTRL1_XL_FS_MAP, value)
            res = self.read_write(CTRL1_XL, CTRL1_XL_FS_MASK, val) & CTRL1_XL_FS_MASK

        self._xl_fs = CTRL1_XL_FS_MAP[res]
        self._xl_scale = XL_FS_SCALE_MAP[self._xl_fs]

        return self._xl_fs

    def fifo_status(self):
        """
        Get current FIFO status. Returns a dictionary with the following keys:
        - unread_words (number): The number of unread FIFO entries
        - watermark_raised (bool): Whether the FIFO threshold value has been reached.
          Check out fifo_threshold function.
        - overrun (bool): Is FIFO full?
        - empty (bool): Is FIFO empty?
        """
        ret = {}

        res_status_1 = self.read(FIFO_STATUS1)
        res_status_2 = self.read(FIFO_STATUS2)

        ret['unread_words']  = res_status_1 | ( (res_status_2 & FIFO_STATUS2_DIFF_FIFO_MASK) << 8 )
        ret['watermark_raised'] = bool(res_status_2 & FIFO_STATUS2_WATERM_MASK)
        ret['overrun']       = bool(res_status_2 & FIFO_STATUS2_OVER_RUN_MASK)
        ret['empty']         = bool(res_status_2 & FIFO_STATUS2_FIFO_EMPTY)

        return ret

    def fifo_threshold(self, value=None):
        """
        Get or set FIFO threshold. Watermark flag rises when the number of bytes written to FIFO
        after the next write is greater than or equal to the threshold level.

        - value (number): a number between 0 and 2047, the number of entries which will raise the
          watermark flag
        """
        
        if value == None:
            res_1 = self.read(FIFO_CTRL1)
            res_2 = self.read(FIFO_CTRL2) & FIFO_CTRL2_FTH_MASK

            res = res_1 | (res_2 << 8)
        else:
            if type(value) != int or value < 0 or value > 2047:
                raise ValueError('Value must be an integer between 0 and 2047, inclusive.')
            
            ctrl_1_val = value & 0x0FF
            ctrl_2_val = (value & 0x700) >> 8

            res_1 = self.read_write(FIFO_CTRL1, 0xFF, ctrl_1_val) # accept all, we just want the new value back
            res_2 = self.read_write(FIFO_CTRL2, FIFO_CTRL2_FTH_MASK, ctrl_2_val) & FIFO_CTRL2_FTH_MASK

            res = res_1 | (res_2 << 8)
        
        return res

    def fifo_acc_decimation(self, value=None):
        """
        Get or set FIFO accelerometer decimation. Look at FIFO_CTRL3_DEC_XL_MAP for available values.
        """

        if value == None:
            res = self.read(FIFO_CTRL3) & FIFO_CTRL3_DEC_FIFO_XL_MASK
        else:
            val = dict_key_by_value(FIFO_CTRL3_DEC_FIFO_XL_MAP, value)
            res = self.read_write(FIFO_CTRL3, FIFO_CTRL3_DEC_FIFO_XL_MASK, val) & FIFO_CTRL3_DEC_FIFO_XL_MASK
            
        return FIFO_CTRL3_DEC_FIFO_XL_MAP[res]

    def fifo_gyro_decimation(self, value=None):
        """
        Get or set FIFO gyroscope decimation. Look at FIFO_CTRL3_DEC_GYRO_MAP for available values.
        """
        raise NotImplementedError('Not implemented.')

    def fifo_odr(self, value=None):
        """
        Get or set FIFO ODR setting.
        Look at FIFO_CTRL5_ODR_MAP for available values.
        """

        if value == None:
            res = self.read(FIFO_CTRL5) & FIFO_CTRL5_ODR_MASK
        else:
            val = dict_key_by_value(FIFO_CTRL5_ODR_MAP, value)
            res = self.read_write(FIFO_CTRL5, FIFO_CTRL5_ODR_MASK, val) & FIFO_CTRL5_ODR_MASK

        return FIFO_CTRL5_ODR_MAP[res]

    def fifo_mode(self, value=None):
        """
        Get or set FIFO mode setting.
        Look at FIFO_CTRL_5_MODE_MAP for available values.
        """

        if value == None:
            res = self.read(FIFO_CTRL5) & FIFO_CTRL5_MODE_MASK
        else:
            val = dict_key_by_value(FIFO_CTRL5_MODE_MAP, value)
            res = self.read_write(FIFO_CTRL5, FIFO_CTRL5_MODE_MASK, val) & FIFO_CTRL5_MODE_MASK
        
        return FIFO_CTRL5_MODE_MAP[res]

    """
    def gyro_xyz(self):
        ret = {}

        buf = self.read(OUTX_L_G, length=6)

        x = self._signed_int((buf[0] | (buf[1] << 8)), bits=16) / 1000.0
        y = self._signed_int((buf[2] | (buf[3] << 8)), bits=16) / 1000.0
        z = self._signed_int((buf[4] | (buf[5] << 8)), bits=16) / 1000.0

        ret['x'] = round(x, 2)
        ret['y'] = round(y, 2)
        ret['z'] = round(z, 2)

        return ret


    def gyro_mode(self, active=None):
        if active == None:
            result = self.read(CTRL2_G)
            return result
        
        if active:
            ### 250 dps
            #self.write(CTRL2_G, 0x50)

            ### 500 dps
            #self.write(CTRL2_G, 0x54)

            ### 1000 dps
            #self.write(CTRL2_G, 0x58)

            ### 2000 dps
            self.write(CTRL2_G, 0x5C)
        else:
            self.write(CTRL2_G, 0)
    """