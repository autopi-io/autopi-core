import binascii
import logging
import salt.exceptions

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack
from retrying import retry


__virtualname__ = "cryptoauth"

log = logging.getLogger(__name__)

client = EventDrivenMessageClient("crypto", default_timeout=15)

def __virtual__():
    return __virtualname__

def __init__(opts):
    client.init(opts)

def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"](__virtualname__)

def query(cmd, *args, **kwargs):
    """
    Queries a given SPM command.

    Arguments:
      - cmd (str): The SPM command to query.
    """
    return client.send_sync(_msg_pack(cmd, *args, **kwargs))

def provision(*args, **kwargs):
    return client.send_sync(_msg_pack(*args, _handler="provision", **kwargs))

def sign_sha256_digest(*args, **kwargs):
    return client.send_sync(_msg_pack(*args, _handler="sign_sha256_digest", **kwargs))

# -------------------------

# def provision(lock_config=False, lock_data=False):
#     ret = {}

#     import cryptoauthlib

#     # Get the target default config
#     cfg = cryptoauthlib.cfg_ateccx08a_i2c_default()
#     cfg.cfg.atcai2c.bus = 1

#     # Initialize the stack
#     if not cryptoauthlib.atcab_init(cfg) == ATCA_SUCCESS:
#         assert ATCA_SUCCESS == cryptoauthlib.atcab_release(),  "Failed to release stack"
#         log.warning('Failed to initialize secure element. Retrying once after 100ms.')
#         time.sleep(0.1)
#         assert cryptoauthlib.atcab_init(cfg) == ATCA_SUCCESS, "Failed to initialize stack"

#     # _config = bytearray.fromhex(
#     #     # '01 23 96 10 00 00 10 05 1A C5 87 A2 EE C0 BD 00' # byte 0-15 - Un-writeable, contains serial number and other stuff.
#     #     'C0 00 55 00 87 20 C4 44 87 20 87 20 8F 0F C4 36' # byte 16-31
#     #     '9F 0F 82 20 0F 0F C4 44 0F 0F 0F 0F 0F 0F 0F 0F' # byte 32-47
#     #     '0F 0F 0F 0F FF FF FF FF 00 00 00 00 FF FF FF FF' # byte 48-63
#     #     '00 00 00 00 FF FF FF FF FF FF FF FF FF FF FF FF' # byte 64-79
#     #     'FF FF FF FF 00 00 55 55 FF FF 00 00 00 00 00 00' # byte 80-95
#     #     '33 00 1C 00 1C 00 1C 00 1C 00 1C 00 1C 00 1C 00' # byte 96-111
#     #     '3C 00 3C 00 3C 00 3C 00 3C 00 3C 00 3C 00 3C 00') # byte 112-127

#     _config = bytearray.fromhex(
#         'C0'                                                # 16        : I2C Address
#         '00'                                                # 17        : Reserved - must be 0
#         '55'                                                # 18        : OTP Mode - Consumption
#         '00'                                                # 19        : ChipMode - Defaults (recommended)
#         '87 20'                                             # 20-21     : Slot 0 ECC P256 *10000111 00100000*
#         '87 20'                                             # 22-23     : Slot 1 ECC P256 *10000111 00100000*
#         '87 20'                                             # 24-25     : Slot 2 ECC P256 *10000111 00100000*
#         '87 20'                                             # 26-27     : Slot 3 ECC P256 *10000111 00100000*
#         '8F 0F'                                             # 28-29     : Slot 4
#         'C4 36'                                             # 30-31     : Slot 5
#         '9F 0F'                                             # 32-33     : Slot 6
#         '82 20'                                             # 34-35     : Slot 7
#         '0F 0F'                                             # 36-37     : Slot 8
#         'C4 44'                                             # 38-39     : Slot 9
#         '0F 0F'                                             # 40-41     : Slot 10
#         '0F 0F'                                             # 42-43     : Slot 11
#         '0F 0F'                                             # 44-45     : Slot 12
#         '0F 0F'                                             # 46-47     : Slot 13
#         '0F 0F'                                             # 48-49     : Slot 14
#         '0F 0F'                                             # 50-51     : Slot 15
#         '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00'   # 52-67     : UseFlag 52,54,56,58,60,62,64,66, UpdateCount 53,55,57,59,61,63,65,67
#         'FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF'   # 68-83     : LastKeyUse
#         '00'                                                # 84        : UserExtra
#         '00'                                                # 85        : Selector
#         '55'                                                # 86        : Lock Value - Set via Lock Command
#         '55'                                                # 87        : LockConfig - Set via Lock Command
#         'FF FF'                                             # 88-89     : SlotLocked - Default to every slot unlocked
#         '00 00'                                             # 90-91     : RFU - Must be zero
#         '00 00 00 00'                                       # 92-95     : X509Format
#         '33 00'                                             # 96-97     : Key 0 - ECC Key P283, lockable
#         '33 00'                                             # 98-99     : Key 1 - ECC Key P283, lockable
#         '33 00'                                             # 100-101   : Key 2 - ECC Key P283, lockable
#         '33 00'                                             # 102-103   : Key 3 - ECC Key P283, lockable
#         '1C 00'                                             # 104-105   : Key 4 - NOT an ecc key, 
#         '1C 00'                                             # 106-107   : Key 5 - NOT an ecc key, 
#         '1C 00'                                             # 108-109   : Key 6 - NOT an ecc key, 
#         '1C 00'                                             # 110-111   : Key 7 - NOT an ecc key, 
#         '3C 00'                                             # 112-113   : Key 8 - ECC, lockable
#         '3C 00'                                             # 114-115   : Key 9 - ECC, lockable
#         '3C 00'                                             # 116-117   : Key 10 - ECC, lockable
#         '3C 00'                                             # 118-119   : Key 11 - ECC, lockable
#         '3C 00'                                             # 120-121   : Key 12 - ECC, lockable
#         '3C 00'                                             # 122-123   : Key 13 - ECC, lockable
#         '3C 00'                                             # 124-125   : Key 14 - ECC, lockable
#         '3C 00'                                             # 126-127   : Key 15 - ECC, lockable
#     )

#     # Check if can be provisioned
#     is_locked = cryptoauthlib.AtcaReference(False)
#     assert cryptoauthlib.atcab_is_locked(0, is_locked) == ATCA_SUCCESS
#     config_zone_lock = bool(is_locked.value)

#     assert cryptoauthlib.atcab_is_locked(1, is_locked)  == ATCA_SUCCESS
#     data_zone_lock = bool(is_locked.value)

#     is_slot0_locked = cryptoauthlib.AtcaReference(False)
#     assert cryptoauthlib.atcab_is_slot_locked(0, is_slot0_locked) == ATCA_SUCCESS
#     slot0_data_locked = bool(is_slot0_locked.value)

#     try:
#         # Write configuration
#         # Verify configuration!!!!

#         # Optional: Lock config zone
#         # Generate certificate
#         # Optional: Lock slot 1
#         pass
#     except Exception as ex:
#         pass
#     finally:
#         # Free the library
#         cryptoauthlib.atcab_release()


# def sign_payload(payload_hash, slot=0, i2c_address=0x60):
#     pass

# def get_public_key(private_key_slot=0, i2c_address=0x60):
#     pass

# @retry(stop_max_attempt_number=3, wait_fixed=500)
# def query(*args, **kwargs):
#     """
#     """

#     ret = {}

#     import cryptoauthlib

#     # Get the target default config
#     cfg = cryptoauthlib.cfg_ateccx08a_i2c_default()

#     # Set interface parameters
#     # if kwargs is not None:
#     #     for k, v in kwargs.items():
#     #         icfg = getattr(cfg.cfg, "atcai2c")
#     #         setattr(icfg, k, int(v, 16))

#     cfg.cfg.atcai2c.bus = 1

#     # Initialize the stack
#     # assert cryptoauthlib.atcab_init(cfg) == ATCA_SUCCESS, "Failed to initialize stack"

#     try:
#         for arg in args:
#             if arg == "device":
#                 res = bytearray(4)
#                 assert cryptoauthlib.atcab_info(res) == ATCA_SUCCESS, "Failed to get info"
#                 ret[arg] = cryptoauthlib.get_device_name(res)
#             elif arg == "provisioned":
#                 is_locked = cryptoauthlib.AtcaReference(False)
#                 assert ATCA_SUCCESS == cryptoauthlib.atcab_is_locked(0, is_locked)
#                 config_zone_lock = bool(is_locked.value)

#                 is_slot0_locked = cryptoauthlib.AtcaReference(False)
#                 assert ATCA_SUCCESS == cryptoauthlib.atcab_is_slot_locked(0, is_slot0_locked)
#                 slot0_data_locked = bool(is_slot0_locked.value)

#                 ret[arg] = (config_zone_lock and slot0_data_locked)
#             elif arg == "publickey":
#                 res = bytearray(64)
#                 assert cryptoauthlib.atcab_get_pubkey(0, res) == ATCA_SUCCESS, "Failed to get public key, might not be provisioned yet!"
#                 ret[arg] = binascii.hexlify(res)
#             elif arg == "serial":
#                 res = bytearray(9)
#                 assert cryptoauthlib.atcab_read_serial_number(res) == ATCA_SUCCESS, "Failed to read serial number"
#                 ret[arg] = binascii.hexlify(res)
#             else:
#                 raise ValueError("Unsupported argument '{:}'".format(arg))
#     finally:
#         # Free the library
#         cryptoauthlib.atcab_release()

#     return ret
