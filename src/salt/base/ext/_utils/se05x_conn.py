import func_timeout
import logging
import binascii
import base64
from cryptography.hazmat.primitives.serialization import load_der_public_key, PublicFormat, Encoding
from cryptography.hazmat.backends import default_backend
from Cryptodome.Hash import keccak

import asn1
import ecdsa

from cli.cli import Context, do_open_session
from sss import const
from sss.const import AUTH_TYPE_MAP, ECC_CURVE_TYPE
from sss.se05x import Se05x
from sss.genkey import Generate
from sss.getkey import Get
from sss.session import Session
from sss.sign import Sign
from sss.policy import Policy

TIME_OUT = 15  # Time out in seconds

log = logging.getLogger(__name__)
DEBUG = log.isEnabledFor(logging.DEBUG)

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

        func_timeout.func_timeout(TIME_OUT, self.sss_context.session.session_open, None)

    def close(self):
        return self.sss_context.session.session_close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        return self.close()

    def _serial_number(self):
        se05x_obj = Se05x(self.sss_context.session)
        unique_id = func_timeout.func_timeout(TIME_OUT, se05x_obj.get_unique_id, None)
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

    def sign_string(self, data, keyid=None, hashalgo="KECCAK256", encoding="PEM"):

        keyid_int = self.get_key_id_or_default(keyid)

        log.info("Signing {} with key {}".format(data, keyid_int))

        sign_obj = Sign(self.sss_context.session)

        # When getting the RS values, get the DER format and decode that
        if encoding == "RS_HEX":
            sig_encoding = "DER"
        else:
            sig_encoding = encoding

        # Execute signing
        signature = func_timeout.func_timeout(TIME_OUT, sign_obj.do_signature_and_return, (keyid_int, data, sig_encoding, hashalgo))

        if not isinstance(signature, str):
            raise Exception("do_signature_and_return returned a non-string value: {}".format(signature))
        
        if encoding == "RS_HEX":
            try:
                decoder = asn1.Decoder()

                # .read() gets the next element in the sequence in a tuple (tag, value)
                # Structure of the encoded signature is [[{r}{s}]]
                decoder.start(signature)
                value = decoder.read()[1]

                # Decode nested r and s values
                decoder.start(value)
                r = hex(decoder.read()[1]).lstrip("0x").rstrip("L")
                s = hex(decoder.read()[1]).lstrip("0x").rstrip("L")

                # Convert to HEX
                signature = "0x{}{}".format(r, s)

            except Exception as ex:
                log.error(ex)
                raise Exception("Could not convert signature to RS_HEX format. Does the cypher support it?")

        if DEBUG:
            log.debug("Final signature: {}".format(signature))

        return signature

    def generate_key(self, keyid=None, confirm=False, key_type="ecc", ecc_curve="Secp256k1", policy_name=None):
        if not confirm == True:
            raise Exception("This action will generate a new key on the secure element. This could overwrite an existing key. Add 'confirm=true' to continue the operation")
        
        supported_types = ["ecc"]
        if not key_type in supported_types:
            raise Exception("This key type is not supported. Supported: {}".format(supported_types))

        supported_curves = ["Secp256k1"]
        if key_type == "ecc" and not ecc_curve in supported_curves:
            raise Exception("This curve is not supported. Supported: {}".format(supported_curves))

        # Apply find security policy if one is specified
        if policy_name != None:
            policy_obj = Policy()
            policy_params = policy_obj.get_object_policy(policy_name)
            policy = policy_obj.convert_obj_policy_to_ctype(policy_params)
        else:
            policy = None

        keyid_int = self.get_key_id_or_default(keyid)

        gen_obj = Generate(self.sss_context.session)
        func_timeout.func_timeout(TIME_OUT, gen_obj.gen_ecc_pair, (keyid_int, ECC_CURVE_TYPE[ecc_curve], policy))

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
        func_timeout.func_timeout(TIME_OUT, get_object.get_key, (keyid_int, None, "PEM"))        
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
        key_pem = key_crypto.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

        return key_pem.decode("UTF-8")

    def _key_exists(self, keyid=None):
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
            pub_address1 = binascii.unhexlify(
                keccak.new(digest_bits=256).update(vk.to_string()).hexdigest())[-20:]

            address = "0x"+binascii.hexlify(pub_address1).decode("utf-8")
            if DEBUG:
                log.debug("Address: {}".format(address))

            return address

    def _device(self):
        return 'NXPS05X'
