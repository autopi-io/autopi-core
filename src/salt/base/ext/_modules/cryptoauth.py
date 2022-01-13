import binascii
import logging

from retrying import retry


__virtualname__ = "cryptoauth"

log = logging.getLogger(__name__)

ATCA_SUCCESS = 0x00


def __virtual__():
    return __virtualname__


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"](__virtualname__)


@retry(stop_max_attempt_number=3, wait_fixed=500)
def query(*args, **kwargs):
    """
    """

    ret = {}

    import cryptoauthlib

    # Get the target default config
    cfg = cryptoauthlib.cfg_ateccx08a_i2c_default()

    # Set interface parameters
    if kwargs is not None:
        for k, v in kwargs.items():
            icfg = getattr(cfg.cfg, "atcai2c")
            setattr(icfg, k, int(v, 16))

    cfg.cfg.atcai2c.bus = 1

    # Initialize the stack
    assert cryptoauthlib.atcab_init(cfg) == ATCA_SUCCESS, "Failed to initialize stack"

    try:
        for arg in args:
            if arg == "device":
                res = bytearray(4)
                assert cryptoauthlib.atcab_info(res) == ATCA_SUCCESS, "Failed to get info"
                ret[arg] = cryptoauthlib.get_device_name(res)
            elif arg == "serial":
                res = bytearray(9)
                assert cryptoauthlib.atcab_read_serial_number(res) == ATCA_SUCCESS, "Failed to read serial number"
                ret[arg] = binascii.hexlify(res)
            else:
                raise ValueError("Unsupported argument '{:}'".format(arg))
    finally:

        # Free the library
        cryptoauthlib.atcab_release()

    return ret
