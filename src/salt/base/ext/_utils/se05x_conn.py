unsupported_exc_type = NotImplementedError
unsupported_exc_text = "This method is not supported by this device connection"

import func_timeout
import logging
import binascii
from pkg_resources import load_entry_point
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

TIME_OUT = 60  # Time out in seconds

log = logging.getLogger(__name__)


class CryptoKey(object):
    def __init__(self):
        None

# Probably will be removed :(
class CryptoConnection(object):
    def __init__(self, *args, **kwargs):
        None

    def get_name(self):
        raise unsupported_exc_type(unsupported_exc_text)

    def get_serial(self):
        raise unsupported_exc_type(unsupported_exc_text)

    def provision(self):
        raise unsupported_exc_type(unsupported_exc_text)

    def is_provisioned(self):
        raise unsupported_exc_type(unsupported_exc_text)

    def sign_string(self, data, key):
        raise unsupported_exc_type(unsupported_exc_text)

    def create_key(self, key_type, curve=None): 
        raise unsupported_exc_type(unsupported_exc_text)

    def get_pub_key_pem(self, key):
        raise unsupported_exc_type(unsupported_exc_text)

    def __enter__(self):
        raise unsupported_exc_type(unsupported_exc_text)

class Se05xCryptoConnection(CryptoConnection):

    def __init__(self, *args, **kwargs):
        super(Se05xCryptoConnection, self).__init__(args, kwargs)

        # Create and configure the context used by the SSS python wrapper
        self.sss_context = Context()
        self.sss_context.verbose = False
        self.sss_context.logger = log

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
        return self.session.session_close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self):
        return self.close()

    def get_serial(self):
        se05x_obj = Se05x(self.sss_context.session)
        unique_id = func_timeout.func_timeout(TIME_OUT, se05x_obj.get_unique_id, None)
        return unique_id

    def sign_string(self, data, key):
        outformat = ""
        hashalgo = "SHA256"

        keyid = int(key.keyid, 16)
        sign_obj = Sign(self.sss_context.session)
        signature = func_timeout.func_timeout(TIME_OUT, sign_obj.do_signature_and_return, (keyid, data, outformat, hashalgo))

        return signature.decode("UTF-8")

    def generate_key(self, keyid, key_type="ecc", ecc_curve="Secp256k1"):
    
        supported_types = ["ecc"]
        if not key_type in supported_types:
            raise unsupported_exc_type("This key type is not supported. Supported: {}".format(supported_types))

        supported_curves = ["Secp256k1"]
        if key_type == "ecc" and not ecc_curve in supported_curves:
            raise unsupported_exc_type("This curve is not supported. Supported: {}".format(supported_curves))

        keyid_int = int(keyid, 16)
        policy = None

        gen_obj = Generate(self.sss_context.session)
        func_timeout.func_timeout(TIME_OUT, gen_obj.gen_ecc_pair, (keyid_int, ECC_CURVE_TYPE[ecc_curve], policy))

        keyObj = CryptoKey()
        keyObj.keyid = keyid
        return keyObj

    def get_public_key(self, key):
        """
        Retrieve a previously generated ECC key
        """
        keyid = key.keyid # "12312312"
        keyid = int(keyid, 16)

        get_object = Get(self.sss_context.session)
        func_timeout.func_timeout(TIME_OUT, get_object.get_key, (keyid, None, "PEM"))        
        keylist = get_object.key

        # Encode a key retrieved from a Get object to a PEM format
        key_pem = None
        key_hex_str = ""

        for i in range(len(keylist)):  # pylint: disable=consider-using-enumerate
            keylist[i] = format(keylist[i], 'x')
            if len(keylist[i]) == 1:
                keylist[i] = "0" + keylist[i]
            key_hex_str += keylist[i]
        key_der_str = binascii.unhexlify(key_hex_str)
        key_crypto = load_der_public_key(key_der_str, default_backend())
        key_pem = key_crypto.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        return key_pem.decode("UTF-8")


# data = "Alice"
# key = CryptoKey()
# key.keyid = "12312312"


# con = Se05xCryptoConnection()
# con.open()
# serial = con.get_serial()
# key = con.generate_key("12312312")
# signature = con.sign_string(data, key)
# public_key = con.get_public_key(key)

# print("On device {}:".format(serial))
# print("{} \n + \n{} = \n{}".format(data, public_key, signature))



# print(atcCon.get_serial())
# print(atcCon.get_name())