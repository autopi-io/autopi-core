import func_timeout
import logging
import binascii
import base64
from cryptography.hazmat.primitives.serialization import load_der_public_key, PublicFormat, Encoding
from cryptography.hazmat.backends import default_backend
from cli.cli import Context, do_open_session
from sss import const
from sss.const import AUTH_TYPE_MAP, ECC_CURVE_TYPE
from sss.se05x import Se05x
from sss.genkey import Generate
from sss.getkey import Get
from sss.session import Session
from sss.sign import Sign
from sss.policy import Policy

from sha3 import keccak_256
import asn1
import struct
import ecdsa
import ecc
from ecc import ecdsa_raw_recover, encode_int32
import time


TIME_OUT = 15  # Time out in seconds

SECP256K1_HALF = ecc.N // 2

log = logging.getLogger(__name__)
DEBUG = log.isEnabledFor(logging.DEBUG)


def hex_string_to_number(string):
    return int(binascii.hexlify(string), 16)


def int_to_big_endian(value):
    return value.to_bytes((value.bit_length() + 7) // 8 or 1, "big")


def pub_key_to_eth_address(pub_key):
    return binascii.hexlify(binascii.unhexlify(
        keccak_256(pub_key).hexdigest())[-20:])


class CryptoKey(object):
    def __init__(self):
        None


class Se05xCryptoConnection():

    def __init__(self, settings):
        # Create and configure the context used by the SSS python wrapper
        self.sss_context = Context()
        self.sss_context.verbose = False
        self.sss_context.logger = log
        self.settings = settings

    def open(self):
        """
        Opens an I2C session with the se05x chip
        """
        # Tries to create and open an SSS session
        # If first time, create the configuration
        connect_max_retry = 1
        connect_retry = 0

        # Load the session configuration
        while connect_retry <= connect_max_retry and not hasattr(self.sss_context, "session"):
            try:
                self.sss_context.session = Session()
            except Exception as err:
                connect_retry += 1

                # If first time, create the configuration file
                log.error("Could not open the SSS session. Trying to configure")
                do_open_session(subsystem=const.SUBSYSTEM_TYPE["se05x"],
                                connection_method=const.CONNECTION_TYPE["t1oi2c"],
                                port_name="none",
                                host_session=False,
                                auth_type=AUTH_TYPE_MAP["None"][0],
                                scpkey="",
                                tunnel=AUTH_TYPE_MAP["None"][2],
                                is_auth=False)

        if not hasattr(self.sss_context, "session"):
            raise Exception("Could not create connection with Secure Element")

        func_timeout.func_timeout(
            TIME_OUT, self.sss_context.session.session_open, None)

    def close(self):
        return self.sss_context.session.session_close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        return self.close()

    def _serial_number(self):
        se05x_obj = Se05x(self.sss_context.session)
        unique_id = func_timeout.func_timeout(
            TIME_OUT, se05x_obj.get_unique_id, None)
        return unique_id

    def get_key_object(self, keyid):
        keyObj = CryptoKey()
        keyObj.keyid = keyid
        return keyObj

    # Necessary when the key is numbers only
    def ensure_key_is_string(self, keyid):
        if not isinstance(keyid, str) and keyid != None:
            keyid = format(keyid, '#x')
        return keyid

    def get_key_id_or_default(self, keyid):
        key = self.settings['keyid']
        if keyid:
            key = keyid

        key = self.ensure_key_is_string(key)
        log.info('Using key: {}'.format(key))
        return int(key, 16)

    def sign_string(self, data, expected_address, keyid=None):
        start_time = time.time()
        keyid_int = self.get_key_id_or_default(keyid)
        log.info("Signing {} with key {}".format(keyid_int, data))

        sign_obj = Sign(self.sss_context.session)

        # Execute signing
        hex_signature = func_timeout.func_timeout(
            TIME_OUT, sign_obj.sign_hash_and_return, (keyid_int, data))
        signature_bytes = binascii.unhexlify(hex_signature)
        if not isinstance(hex_signature, str):
            raise Exception(
                "do_signature_and_return returned a non-string value: {}".format(hex_signature))

        # Remove 0x from the address if exists
        if expected_address[:2] == "0x":
            expected_address = expected_address[2:]

        decoder = asn1.Decoder()
        digest = hex_string_to_number(data)
        decoder.start(signature_bytes)
        value = decoder.read()[1]

        # Decode nested r and s values
        decoder.start(value)

        r = decoder.read()[1]
        s = decoder.read()[1]

        if s > SECP256K1_HALF:
            s = ecc.N - s

        v_ = 27
        pub_address = None
        V = None
        for i in range(2):
            v = v_ + i
            digest_bytes = binascii.unhexlify(data)
            x, y = ecdsa_raw_recover(digest_bytes, (v, r, s))
            public_key = int_to_big_endian(x) + int_to_big_endian(y)
            pub_address_test = pub_key_to_eth_address(public_key)
            if(pub_address_test == expected_address):
                pub_address = pub_address_test
                V = v
                break

        if(not pub_address):
            raise Exception("Cannot find valid v")

        signature = "0x{}{}{}".format('{:064x}'.format(
            r), '{:064x}'.format(s), '{:02x}'.format(V))

        if DEBUG:
            log.debug("Final signature: {}".format(signature))
            log.debug("Address: {}".format("0x"+pub_address))
        log.info("Duration: %2f seconds" % (time.time() - start_time))
        return signature

    def generate_key(self, keyid=None, confirm=False, key_type="ecc", ecc_curve="Secp256k1", policy_name=None):
        if not confirm == True:
            raise Exception(
                "This action will generate a new key on the secure element. This could overwrite an existing key. Add 'confirm=true' to continue the operation")

        supported_types = ["ecc"]
        if not key_type in supported_types:
            raise Exception(
                "This key type is not supported. Supported: {}".format(supported_types))

        supported_curves = ["Secp256k1"]
        if key_type == "ecc" and not ecc_curve in supported_curves:
            raise Exception(
                "This curve is not supported. Supported: {}".format(supported_curves))

        # Apply find security policy if one is specified
        if policy_name != None:
            policy_obj = Policy()
            policy_params = policy_obj.get_object_policy(policy_name)
            policy = policy_obj.convert_obj_policy_to_ctype(policy_params)
        else:
            policy = None

        keyid_int = self.get_key_id_or_default(keyid)

        gen_obj = Generate(self.sss_context.session)
        func_timeout.func_timeout(
            TIME_OUT, gen_obj.gen_ecc_pair, (keyid_int, ECC_CURVE_TYPE[ecc_curve], policy))

        keyObj = CryptoKey()
        keyObj.keyid = keyid_int
        return keyObj

    def _public_key(self, keyid=None):
        """
        Retrieve a previously generated ECC key, will use default keyid if not specified.
        """
        # with self:
        keyid_int = self.get_key_id_or_default(keyid)

        get_object = Get(self.sss_context.session)
        func_timeout.func_timeout(
            TIME_OUT, get_object.get_key, (keyid_int, None, "PEM"))
        keylist = get_object.key

        if not keylist:
            return keylist

        # Encode a key retrieved from a Get object to a PEM format
        key_pem = None
        key_hex_str = ""

        for i in range(len(keylist)):  # pylint: disable=consider-using-enumerate
            keylist[i] = format(keylist[i], 'x')
            if len(keylist[i]) == 1:
                keylist[i] = "0" + keylist[i]
            key_hex_str += keylist[i]

        key_der_str = binascii.unhexlify(key_hex_str)
        # log.info(key_der_str)
        key_crypto = load_der_public_key(key_der_str, default_backend())
        key_pem = key_crypto.public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        return key_pem.decode("UTF-8")

    def key_exists(self, keyid=None):
        key = self._public_key(keyid=keyid)
        return bool(key)

    def _ethereum_address(self, keyid=None):
        """
        Retrieve a previously generated ECC key, will use default keyid if not specified.
        """
        with self:
            keyid_int = self.get_key_id_or_default(keyid)
            get_object = Get(self.sss_context.session)
            func_timeout.func_timeout(
                TIME_OUT, get_object.get_key, (keyid_int, None, "PEM"))
            keylist = get_object.key

            if not keylist:
                return keylist

            # Encode a key retrieved from a Get object to a PEM format
            key_pem = None
            key_hex_str = ""

            for i in range(len(keylist)):  # pylint: disable=consider-using-enumerate
                keylist[i] = format(keylist[i], 'x')
                if len(keylist[i]) == 1:
                    keylist[i] = "0" + keylist[i]
                key_hex_str += keylist[i]

            key_der_str = binascii.unhexlify(key_hex_str)
            # log.info(key_der_str)
            key_crypto = load_der_public_key(key_der_str, default_backend())
            key_pem = key_crypto.public_bytes(
                Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
            PEM_KEY = key_pem.decode("UTF-8")
            if DEBUG:
                log.debug("PEM public key: {}".format(PEM_KEY))

            vk = ecdsa.VerifyingKey.from_pem(PEM_KEY)
            eth_address = pub_key_to_eth_address(vk.to_string())

            address = "0x"+eth_address
            if DEBUG:
                log.debug("Address: {}".format(address))
            return address

    def _device(self):
        return 'NXPS05X'


if __name__ == "__main__":
    print("Hello")
    con = Se05xCryptoConnection({"keyid": "3dc586a1"})
    con.open()
    # print(con._ethereum_address())
    sig = con.sign_string(
        "3013fe9c3167130f8fd9fdac026b7b2e6ddd3662aa6f275f88d66072033e73b3", "bd4c64b2ee316ba81799b6b294a8c082d99f3871")
    print(sig)
