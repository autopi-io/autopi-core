import cryptoauthlib
import binascii
import time
import logging

from retrying import retry

log = logging.getLogger(__name__)

ATCA_SUCCESS = 0x00

class CryptoAuthConn(object):

    class Decorators(object):

        @staticmethod
        def ensure_open(func):

            def decorator(self, *args, **kwargs):

                # Ensure connection is open
                self.ensure_open()

                return func(self, *args, **kwargs)

            # Add reference to the original undecorated function
            decorator.undecorated = func

            return decorator

    # Any command should handle 
    #   - CRC or Other Communications Error 0xFF
    #   - Watchdog About to Expire 0xEE

    def handle_res(self, res):
        cryptoauthlib.status.check_status(res)

    def device(self):
        device_name = bytearray(4)
        res = cryptoauthlib.atcab_info(device_name)
        self.handle_res(res)
        return cryptoauthlib.get_device_name(device_name)

    def provisioned(self):
        is_locked = cryptoauthlib.AtcaReference(False)
        res = cryptoauthlib.atcab_is_locked(0, is_locked)
        self.handle_res(res)
        config_zone_lock = bool(is_locked.value)

        is_slot0_locked = cryptoauthlib.AtcaReference(False)
        res = cryptoauthlib.atcab_is_slot_locked(0, is_slot0_locked)
        self.handle_res(res)
        slot0_data_locked = bool(is_slot0_locked.value)

        return config_zone_lock and slot0_data_locked

    def publickey(self, slot=0):
        publickey = bytearray(64)
        res = cryptoauthlib.atcab_get_pubkey(slot, publickey)
        self.handle_res(res)
        return binascii.hexlify(publickey)

    def serialnumber(self):
        serialnumber = bytearray(9)
        res = cryptoauthlib.atcab_read_serial_number(serialnumber)
        self.handle_res(res)
        return binascii.hexlify(serialnumber)

    def __init__(self, settings):
        cryptoauthlib.load_cryptoauthlib()
        log.info('Loaded cryptoauthlib')
        self._is_open = False
        self.init(settings)

    def init(self, settings):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Initializing cryptoauth connection using settings: {:}".format(settings))

        # Should this be bus instead?
        if not "port" in settings:
            raise ValueError("I2C 'port' must be specified in settings")
        self._port = settings["port"]

        if not "address" in settings:
            raise ValueError("I2C 'address' must be specified in settings")
        self._address = int(settings.get("address", None), 16)

        return self

    @retry(stop_max_attempt_number=3, wait_fixed=500)
    def open(self):
        log.info("Opening cryptoauth connection.")

        try:
            cfg = cryptoauthlib.cfg_ateccx08a_i2c_default()
            cfg.cfg.atcai2c.bus = self._port
            if self._address:
                cfg.cfg.atcai2c.slave_address = self._address

            if not cryptoauthlib.atcab_init(cfg) == ATCA_SUCCESS:
                release_res = cryptoauthlib.atcab_release()
                cryptoauthlib.status.check_status(release_res)

                log.warning('Failed to initialize secure element. Retrying once after 100ms.')
                time.sleep(0.05)

                init_res = cryptoauthlib.atcab_init(cfg)
                cryptoauthlib.status.check_status(init_res)

            self._is_open = True

            return self
        except Exception:
            log.exception("Failed to open cryptoauth connection")
            self._is_open = False

            raise

    def is_open(self):
        return self._is_open

    def ensure_open(self):
        if not self.is_open():
            self.open()

    def close(self):
        cryptoauthlib.atcab_release()
        self._is_open = False

    def __enter__(self):
        return self.open()

    def __exit__(self, type, value, traceback):
        self.close()
