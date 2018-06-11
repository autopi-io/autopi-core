import logging
import mma8x5x_helper as mma8x5x

from messaging import EventDrivenMessageClient, msg_pack


# Define the module's virtual name
__virtualname__ = "acc"

MODES = {
    mma8x5x.MODE_STANDBY: "standby",
    mma8x5x.MODE_WAKE:    "wake",
    mma8x5x.MODE_SLEEP:   "sleep",
}

RANGES = {
    mma8x5x.RANGE_2G: "2G",
    mma8x5x.RANGE_4G: "4G",
    mma8x5x.RANGE_8G: "8G",
}

DATA_RATES = {
    mma8x5x.DATA_RATE_800HZ: "800Hz",
    mma8x5x.DATA_RATE_400HZ: "400Hz",
    mma8x5x.DATA_RATE_200HZ: "200Hz",
    mma8x5x.DATA_RATE_100HZ: "100Hz",
    mma8x5x.DATA_RATE_50HZ:  "50Hz",
    mma8x5x.DATA_RATE_1HZ25: "12.5Hz",
    mma8x5x.DATA_RATE_6HZ25: "6.25Hz",
    mma8x5x.DATA_RATE_1HZ56: "1.56Hz",
}

ASLP_RATES = {
    mma8x5x.ASLP_RATE_50HZ:  "50Hz",
    mma8x5x.ASLP_RATE_12HZ5: "12.5Hz",
    mma8x5x.ASLP_RATE_6HZ25: "6.25Hz",
    mma8x5x.ASLP_RATE_1HZ56: "1.56Hz",
}

INTERRUPT_SOURCES = {
    mma8x5x.INT_SOURCE_DRDY:   "data",
    mma8x5x.INT_SOURCE_FF_MT:  "motion",
    mma8x5x.INT_SOURCE_PULSE:  "pulse",
    mma8x5x.INT_SOURCE_LNDPRT: "orientation",
    mma8x5x.INT_SOURCE_TRANS:  "transient",
    mma8x5x.INT_SOURCE_FIFO:   "fifo",
    mma8x5x.INT_SOURCE_ASLP:   "wake",
}

INTERRUPT_PINS = {
    mma8x5x.INT1: "int1",
    mma8x5x.INT2: "int2",
}

WAKE_SOURCES = {
    mma8x5x.CTRL_REG3_WAKE_FF_MT:  "motion",
    mma8x5x.CTRL_REG3_WAKE_PULSE:  "pulse",
    mma8x5x.CTRL_REG3_WAKE_LNDPRT: "orientation",
    mma8x5x.CTRL_REG3_WAKE_TRANS:  "transient",
}

log = logging.getLogger(__name__)

client = EventDrivenMessageClient("mma8x5x")


def __virtual__():
    return __virtualname__


def __init__(opts):
    client.init(opts)


def _key_by_val(dict, val):
    kv = { k:v for k, v in dict.items() if v.lower() == val.lower() }
    return next(iter(kv))


def help():
    """
    This command.
    """

    return __salt__["sys.doc"](__virtualname__)


def _read(register, length=1, **kwargs):
    """
    Low-level command to read value of register or a range of registers.
    """

    return client.send_sync(msg_pack(register, length, **kwargs))


def _write(register, value, **kwargs):
    """
    Low-level command to write a value to a specified register.
    """

    return client.send_sync(msg_pack(register, value, _handler="write", **kwargs))


def _read_write(register, mask, value, **kwargs):
    """
    Low-level command to update a value within a specified register.
    """

    return client.send_sync(msg_pack(register, mask, value, _handler="read_write", **kwargs))


def active(enabled=None):
    """
    Get or set active mode, this enables/disables periodic measurements.
    """

    res = None
    if enabled == None:
        res = _read(mma8x5x.CTRL_REG1)
    else:
        val = mma8x5x.CTRL_REG1_ACTIVE if bool(enabled) else 0
        res = _read_write(mma8x5x.CTRL_REG1, mma8x5x.CTRL_REG1_ACTIVE, val)

    res["_raw"] = res["_raw"] & mma8x5x.CTRL_REG1_ACTIVE
    res["enabled"] = res["_raw"] == mma8x5x.CTRL_REG1_ACTIVE

    return res


def mode():
    """
    Indicates the current device operating mode.
    """

    res = _read(mma8x5x.SYSMOD)

    res["value"] = MODES.get(res["_raw"])
    return res


def auto_sleep(enabled=None):
    """
    If the auto-sleep is disabled, then the device can only toggle between standby and wake mode.
    If auto-sleep interrupt is enabled, transitioning from active mode to auto-sleep mode and vice versa generates an interrupt.
    """

    res = None
    if enabled == None:
        res = _read(mma8x5x.CTRL_REG2)
    else:
        val = mma8x5x.CTRL_REG2_SLPE if bool(enabled) else 0
        res = _read_write(mma8x5x.CTRL_REG2, mma8x5x.CTRL_REG2_SLPE, val,
            _validator="in_standby_mode")

    res["_raw"] = res["_raw"] & mma8x5x.CTRL_REG2_SLPE
    res["enabled"] = res["_raw"] == mma8x5x.CTRL_REG2_SLPE

    return res


def status():
    """
    Check for new set of measurement data.
    """

    res = _read(mma8x5x.STATUS)

    byte = res["_raw"]
    res["ready"] = {
        "x":   bool(byte & mma8x5x.STATUS_XDR),
        "y":   bool(byte & mma8x5x.STATUS_YDR),
        "z":   bool(byte & mma8x5x.STATUS_ZDR),
        "any": bool(byte & mma8x5x.STATUS_ZYXDR),
    }
    res["overwrite"] = {
        "x":   bool(byte & mma8x5x.STATUS_XOW),
        "y":   bool(byte & mma8x5x.STATUS_YOW),
        "z":   bool(byte & mma8x5x.STATUS_ZOW),
        "any": bool(byte & mma8x5x.STATUS_ZYXOW),
    }

    return res


def xyz():
    """
    Read and calculate accelerometer data.
    """

    # TODO: Prevent using validator when running XYZ_LOGGER?
    # Ex: validator="no_worker?name=xyz_logger"
    res = _read(mma8x5x.OUT_X_MSB, length=6, _converter="g_block")

    vals = res.pop("conv")
    res["x"] = vals[0]
    res["y"] = vals[1]
    res["z"] = vals[2]

    return res


def xyz_logger(enabled=None):
    """
    Enable/disable accelerometer data logger.
    """

    WORKER_NAME = "xyz_logger"

    if enabled == None:
        res = client.send_sync(msg_pack("worker", "query", WORKER_NAME, _workflow="admin"))

        res["status"] = "running" if len(res.pop("result")) else "stopped"
    elif enabled:
        res = client.send_sync(msg_pack(mma8x5x.OUT_X_MSB, 6,
            _workflow="simple",
            _worker="infinite?name={:s}".format(WORKER_NAME),
            _handler="interrupt_read",
            _converter="g_block",
            _returner="redis"))

        res["status"] = res.pop("notif", {}).get("status", "unknown")
    else:
        res = client.send_sync(msg_pack("worker", "kill", WORKER_NAME, _workflow="admin"))

        res["status"] = "stopped" if res.pop("result") else "unknown"

    return res


def range(value=None):
    """
    Get or set dynamic range.
    """

    res = None
    if value == None:
        res = _read(mma8x5x.XYZ_DATA_CFG)
    else:
        val = _key_by_val(RANGES, value)
        res = _read_write(mma8x5x.XYZ_DATA_CFG, mma8x5x.XYZ_DATA_CFG_FS_MASK, val)

    res["_raw"] = res["_raw"] & mma8x5x.XYZ_DATA_CFG_FS_MASK
    res["value"] = RANGES.get(res["_raw"])

    return res


def fast_read(enabled=None):
    """
    """

    res = None
    if enabled == None:
        res = _read(mma8x5x.CTRL_REG1)
    else:
        val = mma8x5x.CTRL_REG1_F_READ if bool(enabled) else 0
        res = _read_write(mma8x5x.CTRL_REG1, mma8x5x.CTRL_REG1_F_READ, val,
            _validator="in_standby_mode")

    res["_raw"] = res["_raw"] & mma8x5x.CTRL_REG1_F_READ
    res["enabled"] = res["_raw"] == mma8x5x.CTRL_REG1_F_READ

    return res


def data_rate(value=None):
    """
    """

    res = None
    if value == None:
        res = _read(mma8x5x.CTRL_REG1)
    else:
        val = _key_by_val(DATA_RATES, value)
        res = _read_write(mma8x5x.CTRL_REG1, mma8x5x.CTRL_REG1_DR_MASK, val,
            _validator="in_standby_mode")

    res["_raw"] = res["_raw"] & mma8x5x.CTRL_REG1_DR_MASK
    res["value"] = DATA_RATES.get(res["_raw"])

    return res


def auto_sleep_rate(value=None):
    """
    """

    res = None
    if value == None:
        res = _read(mma8x5x.CTRL_REG1)
    else:
        val = _key_by_val(ASLP_RATES, value)
        res = _read_write(mma8x5x.CTRL_REG1, mma8x5x.CTRL_REG1_ASLP_RATE_MASK, val,
            _validator="in_standby_mode")

    res["_raw"] = res["_raw"] & mma8x5x.CTRL_REG1_ASLP_RATE_MASK
    res["value"] = ASLP_RATES.get(res["_raw"])

    return res


def offset(x=None, y=None, z=None):
    """
    Set user offset correction.
    Offset correction register will be erased after accelerometer reset.
    """

    # TODO
    pass


def intr_status():
    """
    Interrupt status of the various embedded features.
    """

    res = _read(mma8x5x.INT_SOURCE)

    for mask, src in INTERRUPT_SOURCES.iteritems():
        res[src] = bool(res["_raw"] & mask)

    return res


def intr(source, enabled=None):
    """
    Enable/disable interrupts.
    """

    mask = _key_by_val(INTERRUPT_SOURCES, source)

    res = None
    if enabled == None:
        res = _read(mma8x5x.CTRL_REG4)
    else:
        val = mask if bool(enabled) else 0
        res = _read_write(mma8x5x.CTRL_REG4, mask, val,
            _validator="in_standby_mode")

    res["_raw"] = res["_raw"] & mask
    res["enabled"] = bool(res["_raw"])

    return res


def intr_pin(source, value=None):
    """
    Configures output pin of interrupts.
    """

    mask = _key_by_val(INTERRUPT_SOURCES, source)

    res = None
    if value == None:
        res = _read(mma8x5x.CTRL_REG5)
    else:
        val = _key_by_val(INTERRUPT_PINS, value)
        res = _read_write(mma8x5x.CTRL_REG5, mask, val * mask,
            _validator="in_standby_mode")

    res["_raw"] = res["_raw"] & mask
    res["value"] = INTERRUPT_PINS.get(res["_raw"] / mask)

    return res


def intr_pin_pol(inverted=None):
    """
    Interrupt polarity active high, or active low.
    """

    res = None
    if inverted == None:
        res = _read(mma8x5x.CTRL_REG3)
    else:
        val = mma8x5x.CTRL_REG3_IPOL if not bool(inverted) else 0
        res = _read_write(mma8x5x.CTRL_REG3, mma8x5x.CTRL_REG3_IPOL, val,
            _validator="in_standby_mode")

    res["_raw"] = res["_raw"] & mma8x5x.CTRL_REG3_IPOL
    res["inverted"] = not (res["_raw"] == mma8x5x.CTRL_REG3_IPOL)

    return res


def wake(source, enabled=None):
    """
    Enable/disable wake up sources.
    """

    mask = _key_by_val(WAKE_SOURCES, source)

    res = None
    if enabled == None:
        res = _read(mma8x5x.CTRL_REG3)
    else:
        val = mask if bool(enabled) else 0
        res = _read_write(mma8x5x.CTRL_REG3, mask, val,
            _validator="in_standby_mode")

    res["_raw"] = res["_raw"] & mask
    res["enabled"] = bool(res["_raw"])

    return res


def motion_config(freefall=None, event_latch=False, x=False, y=False, z=False):
    """
    Freefall/motion configuration for setting up the conditions of the freefall or motion function.
    """

    res = None
    if freefall == None:
        res = _read(mma8x5x.FF_MT_CFG)
    else:
        val = mma8x5x.FF_MT_CFG_OAE * int(freefall) \
            | mma8x5x.FF_MT_CFG_ELE * int(event_latch) \
            | mma8x5x.FF_MT_CFG_XEFE * int(x) \
            | mma8x5x.FF_MT_CFG_YEFE * int(y) \
            | mma8x5x.FF_MT_CFG_ZEFE * int(z)
        res = _write(mma8x5x.FF_MT_CFG, val,
            _validator="in_standby_mode")

    res["freefall"] = not bool(mma8x5x.FF_MT_CFG_OAE & res["_raw"])
    res["event_latch"] = bool(mma8x5x.FF_MT_CFG_ELE & res["_raw"])
    res["x"] = bool(mma8x5x.FF_MT_CFG_XEFE & res["_raw"])
    res["y"] = bool(mma8x5x.FF_MT_CFG_YEFE & res["_raw"])
    res["z"] = bool(mma8x5x.FF_MT_CFG_ZEFE & res["_raw"])

    return res


def motion_event():
    """
    Read freefall and motion source register that keeps track of acceleration events.
    """

    res = _read(mma8x5x.FF_MT_SRC)

    res["active"] = bool(mma8x5x.FF_MT_SRC_EA & res["_raw"])
    res["x"] = bool(mma8x5x.FF_MT_SRC_XHE & res["_raw"])
    res["x_neg"] = bool(mma8x5x.FF_MT_SRC_XHP & res["_raw"])
    res["y"] = bool(mma8x5x.FF_MT_SRC_YHE & res["_raw"])
    res["y_neg"] = bool(mma8x5x.FF_MT_SRC_YHP & res["_raw"])
    res["z"] = bool(mma8x5x.FF_MT_SRC_ZHE & res["_raw"])
    res["z_neg"] = bool(mma8x5x.FF_MT_SRC_ZHP & res["_raw"])

    return res


def motion_threshold(value=None, counter=False):
    """
    Freefall and motion threshold configuration.
    """

    # TODO: Enable write also
    res = _read(mma8x5x.FF_MT_THS)

    return res


def motion_debounce(value=None):
    """
    Set the number of debounce sample counts for the event trigger.
    """

    # TODO: Enable write also
    res = _read(mma8x5x.FF_MT_COUNT)

    return res

