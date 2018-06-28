import gpio_pin
import logging
import mma8x5x_helper as mma8x5x
import RPi.GPIO as gpio
import threading
import time

from messaging import EventDrivenMessageProcessor
from i2c_conn import I2CConn


log = logging.getLogger(__name__)

# Message processor
edmp = EventDrivenMessageProcessor("mma8x5x",
    default_hooks={"handler": "read", "workflow": "extended"})

# I2C connection
conn = I2CConn()

interrupt_gpio_pin = gpio_pin.ACC_INT1
interrupt_event = threading.Event()

# Cached values used when calculating G-forces
curr_g_range = mma8x5x.range_as_g(mma8x5x.RANGE_DEFAULT)
data_bits = 10  # TODO: Set from settings or something


# Callback function triggered for each write on I2C connection
def _on_written(register, byte):
    if register == mma8x5x.XYZ_DATA_CFG:
        fs = byte & mma8x5x.XYZ_DATA_CFG_FS_MASK
        g_range = range_as_g(fs)

        global curr_g_range
        if g_range != curr_g_range:
            log.info("Cached G-range changed from %dG to %dG", curr_g_range, g_range)

            curr_g_range = g_range


@edmp.register_hook()
def in_standby_mode_validator(*args, **kwargs):
    mode = conn.read(mma8x5x.SYSMOD)
    if mode != mma8x5x.MODE_STANDBY:
        return "Must be in standby mode"


@edmp.register_hook()
def read_handler(register, length):
    raw = None
    if length > 1:
        log.debug("Reading block with a length of %d starting from register: %s", length, register)
        raw = conn.read_block(register, length)

        for i,b in enumerate(raw):
            log.info("{:d} {:08b}".format(i,b))

    else:
        log.debug("Reading from register: %s", register)
        raw = conn.read(register)

    log.debug("Got raw result: %s", raw)

    return {
        "_raw": raw
    }


@edmp.register_hook(synchronize=False)  # Prevents lockup while waiting on data ready interrupt
def interrupt_read_handler(register, length):

    # TODO: This needs to be tested more

    # Wait for data ready interrupt if not already set
    interrupt_event.wait(timeout=.2)
    interrupt_event.clear()

    # Perform a normal data read
    return read_handler(register, length)


@edmp.register_hook()
def write_handler(register, value):
    conn.write(register, value)

    return {
        "_raw": value
    }


@edmp.register_hook()
def read_write_handler(register, mask, value):
    byte = conn.read(register)

    log.info("Updating byte {:08b} using mask {:d} and value {:d}".format(byte, mask, value))
    byte = mma8x5x.update_bits(byte, mask, value)

    conn.write(register, byte)

    return {
        "_raw": byte
    }


@edmp.register_hook()
def g_block_converter(result):
    bytes = result["_raw"]

    words = mma8x5x.concat_bytes(bytes, bits=data_bits)

    for word in words:
        log.debug("Calculating G for block: {:016b}".format(word))

    result["g_range"] = curr_g_range
    result["conv"] = [mma8x5x.calc_g(word, g_range=curr_g_range, bits=data_bits) for word in words]

    return result


def start(i2c_conn, **kwargs):
    try:
        log.debug("Starting MMA8X5X manager")

        # Setup interrupt GPIO pin
        gpio.setmode(gpio.BOARD)
        gpio.setup(interrupt_gpio_pin, gpio.IN)  # TODO: pull_up_down=GPIO.PUD_UP) ??
        gpio.add_event_detect(interrupt_gpio_pin, gpio.FALLING, callback=lambda ch: interrupt_event.set())

        # Initialize I2C connection
        conn.init(i2c_conn)
        conn.on_written = _on_written

        # Initialize and run message processor
        edmp.init(__opts__)
        edmp.run()

    except Exception:
        log.exception("Failed to start MMA8X5X manager")
        raise
    finally:
        log.info("Stopping MMA8X5X manager")
