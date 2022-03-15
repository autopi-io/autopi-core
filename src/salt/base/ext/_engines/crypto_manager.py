import logging
import os
import psutil
import time

from common_util import call_retrying
from messaging import EventDrivenMessageProcessor
from cryptoauth_conn import CryptoAuthConn
from threading_more import intercept_exit_signal
import cryptoauthlib
from retrying import retry

log = logging.getLogger(__name__)

context = {
    "state": None
}

# Message processor
edmp = EventDrivenMessageProcessor("crypto", context=context, default_hooks={"handler": "query"})

# CRYPTO connection is instantiated during start
conn = None

# Any command should handle 
#   - CRC or Other Communications Error 0xFF
#   - Watchdog About to Expire 0xEE

def retry_if_ecc_error(exception):
    return isinstance(exception, cryptoauthlib.EccFaultError)

@retry(retry_on_exception=retry_if_ecc_error, stop_max_attempt_number=3, wait_fixed=50)
def generate_key(slot=0):
    public_key = bytearray(64)
    res = cryptoauthlib.atcab_genkey(slot, public_key)
    conn.handle_res(res)

    return cryptoauthlib.convert_ec_pub_to_pem(public_key)

@edmp.register_hook()
def provision_handler(lock_config=False, lock_data=False):
    # Provision / Genkey should handle ECC Fault 0x05 and retry...
    ret = {}

    conn.ensure_open()
    # _config = bytearray.fromhex(
    #     # '01 23 96 10 00 00 10 05 1A C5 87 A2 EE C0 BD 00' # byte 0-15 - Un-writeable, contains serial number and other stuff.
    #     'C0 00 55 00 87 20 C4 44 87 20 87 20 8F 0F C4 36' # byte 16-31
    #     '9F 0F 82 20 0F 0F C4 44 0F 0F 0F 0F 0F 0F 0F 0F' # byte 32-47
    #     '0F 0F 0F 0F FF FF FF FF 00 00 00 00 FF FF FF FF' # byte 48-63
    #     '00 00 00 00 FF FF FF FF FF FF FF FF FF FF FF FF' # byte 64-79
    #     'FF FF FF FF 00 00 55 55 FF FF 00 00 00 00 00 00' # byte 80-95
    #     '33 00 1C 00 1C 00 1C 00 1C 00 1C 00 1C 00 1C 00' # byte 96-111
    #     '3C 00 3C 00 3C 00 3C 00 3C 00 3C 00 3C 00 3C 00') # byte 112-127

    _config = bytearray.fromhex(
        'C0'                                                # 16        : I2C Address
        '00'                                                # 17        : Reserved - must be 0
        '55'                                                # 18        : OTP Mode - Consumption
        '00'                                                # 19        : ChipMode - Defaults (recommended)
        '87 20'                                             # 20-21     : Slot 0 ECC P256 *10000111 00100000*
        '87 20'                                             # 22-23     : Slot 1 ECC P256 *10000111 00100000*
        '87 20'                                             # 24-25     : Slot 2 ECC P256 *10000111 00100000*
        '87 20'                                             # 26-27     : Slot 3 ECC P256 *10000111 00100000*
        '8F 0F'                                             # 28-29     : Slot 4
        'C4 36'                                             # 30-31     : Slot 5
        '9F 0F'                                             # 32-33     : Slot 6
        '82 20'                                             # 34-35     : Slot 7
        '0F 0F'                                             # 36-37     : Slot 8
        'C4 44'                                             # 38-39     : Slot 9
        '0F 0F'                                             # 40-41     : Slot 10
        '0F 0F'                                             # 42-43     : Slot 11
        '0F 0F'                                             # 44-45     : Slot 12
        '0F 0F'                                             # 46-47     : Slot 13
        '0F 0F'                                             # 48-49     : Slot 14
        '0F 0F'                                             # 50-51     : Slot 15
        '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00'   # 52-67     : UseFlag 52,54,56,58,60,62,64,66, UpdateCount 53,55,57,59,61,63,65,67
        'FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF'   # 68-83     : LastKeyUse
        '00'                                                # 84        : UserExtra
        '00'                                                # 85        : Selector
        '55'                                                # 86        : Lock Value - Set via Lock Command
        '55'                                                # 87        : LockConfig - Set via Lock Command
        'FF FF'                                             # 88-89     : SlotLocked - Default to every slot unlocked
        '00 00'                                             # 90-91     : RFU - Must be zero
        '00 00 00 00'                                       # 92-95     : X509Format
        '33 00'                                             # 96-97     : Key 0 - ECC Key P283, lockable
        '33 00'                                             # 98-99     : Key 1 - ECC Key P283, lockable
        '33 00'                                             # 100-101   : Key 2 - ECC Key P283, lockable
        '33 00'                                             # 102-103   : Key 3 - ECC Key P283, lockable
        '1C 00'                                             # 104-105   : Key 4 - NOT an ecc key, 
        '1C 00'                                             # 106-107   : Key 5 - NOT an ecc key, 
        '1C 00'                                             # 108-109   : Key 6 - NOT an ecc key, 
        '1C 00'                                             # 110-111   : Key 7 - NOT an ecc key, 
        '3C 00'                                             # 112-113   : Key 8 - ECC, lockable
        '3C 00'                                             # 114-115   : Key 9 - ECC, lockable
        '3C 00'                                             # 116-117   : Key 10 - ECC, lockable
        '3C 00'                                             # 118-119   : Key 11 - ECC, lockable
        '3C 00'                                             # 120-121   : Key 12 - ECC, lockable
        '3C 00'                                             # 122-123   : Key 13 - ECC, lockable
        '3C 00'                                             # 124-125   : Key 14 - ECC, lockable
        '3C 00'                                             # 126-127   : Key 15 - ECC, lockable
    )

    # Check if can be provisioned, if unlocked, provision.

    is_locked = cryptoauthlib.AtcaReference(False)
    res = cryptoauthlib.atcab_is_locked(0, is_locked)
    conn.handle_res(res)
    config_zone_locked = bool(is_locked.value)

    # res = cryptoauthlib.atcab_is_locked(1, is_locked)
    # conn.handle_res(res)
    # data_zone_locked = bool(is_locked.value)

    is_slot0_locked = cryptoauthlib.AtcaReference(False)
    res = cryptoauthlib.atcab_is_slot_locked(0, is_slot0_locked)
    conn.handle_res(res)
    slot0_data_locked = bool(is_slot0_locked.value)

    provisioned = config_zone_locked and slot0_data_locked

    # Scenarios
    # Not provisioned = provision and lock shit up.
    # Already provisioned = return public key?
    # Some other state where config is locked

    if not provisioned:
        # Write configuration
        res = cryptoauthlib.atcab_write_bytes_zone(0, 0, 16, _config, len(_config))
        conn.handle_res(res)

        # Verify Config Zone
        config_qa = bytearray(len(_config))
        res = cryptoauthlib.atcab_read_bytes_zone(0, 0, 16, config_qa, len(config_qa))
        conn.handle_res(res)

        if config_qa != _config:
            raise ValueError('Configuration read from the device does not match')
        else:
            log.info('Secure element config matches!')

        # Optional: Lock config zone
        if lock_config:
            res = cryptoauthlib.atcab_lock_config_zone()
            conn.handle_res(res)

        # It config zone locked, generate certificate, retry if ECC exception (EccFaultError)
        public_key = None
        if lock_config:
            public_key = generate_key(0)

        # Optional: Lock slot 1 data zone
        if lock_data:
            res = cryptoauthlib.atcab_lock_data_slot(0)
            conn.handle_res(res)

        # Report back with public key
        ret["result"] = True
        ret["publickey"] = public_key
    else:
        # Already provisioned?
        compatible = config_zone_locked and slot0_data_locked

        ret["state"] = "already_provisioned"
        ret["config_locked"] = config_zone_locked
        ret["slot0_data_locked"] = slot0_data_locked
        ret["publickey"] = conn.publickey()
        
        ret["result"] = compatible
    
    return ret

@edmp.register_hook()
def sign_sha256_digest_handler(message, slot=0):
    ret = {}
    
    signature = bytearray(64)
    # res = cryptoauthlib.atcab_sign(slot, bytearray(digest, 'utf-8'), signature)
    res = cryptoauthlib.atcab_sign(slot, message, signature)
    conn.handle_res(res)
    ret["signature"] = signature
    ret["test"] = True

    return ret

@edmp.register_hook()
def query_handler(cmd, **kwargs):
    """
    Queries a given CryptoAuth command.

    Arguments:
      - cmd (str): The CryptoAuth command to query.
    """

    ret = {
        "_type": cmd.lower(),
    }

    try:
        func = getattr(conn, cmd)
    except AttributeError:
        ret["error"] = "Unsupported command: {:s}".format(cmd)
        return ret

    res = call_retrying(func, kwargs=kwargs, limit=3, wait=0.2, context=context.setdefault("errors", {}))
    if res != None:
        if isinstance(res, dict):
            ret.update(res)
        else:
            ret["value"] = res

    return ret

@intercept_exit_signal
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting CRYPTO manager with settings: {:}".format(settings))

        # Give process higher priority
        psutil.Process(os.getpid()).nice(-1)

        # Initialize connection
        global conn
        # conn = CryptoAuthConn(settings.get("atecc180a_conn"))
        conn = CryptoAuthConn(settings.get("atecc"))
        conn.open()
        # TODO: Handle if connection closes or something.

        # Initialize and run message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        edmp.run()

    except Exception:
        log.exception("Failed to start CRYPTO manager")
        
        raise
    finally:
        log.info("Stopping CRYPTO manager")

        if getattr(conn, "is_open", False) and conn.is_open():
            try:
                conn.close()
            except:
                log.exception("Failed to close SPM connection")