#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import ctypes
import os
import logging
from .keystore import KeyStore
from .keyobject import KeyObject
from . import sss_api as apis
from .util import key_der_to_list, get_ecc_cypher_type, from_file_dat, \
    transform_key_to_list, to_cert_dat, ecc_curve_type_from_key, is_hex

log = logging.getLogger(__name__)


class Set:
    """
    Inject keys and certificates
    """

    def __init__(self, session_obj):
        """
        Constructor
        :param session_obj: Instance of session
        """
        self._session = session_obj
        self._ctx_ks = KeyStore(self._session)
        self._ctx_key = KeyObject(self._ctx_ks)
        self._ctx_kek_key = KeyObject(self._ctx_ks)
        self.key_len = 0
        self._key_object_mode = apis.kKeyObject_Mode_Persistent

    def do_set_ecc_pub_key(self, key_id, key, policy, encode_format=""):
        """
        Inject ECC public key
        :param key_id: Key Index to set key
        :param key: Key value
        :param policy: Policy to be applied
        :param encode_format: Encode format of the key value. Eg: PEM, DER
        :return: status
        """
        try:
            key_type = apis.kSSS_KeyPart_Public
            if not os.path.isfile(key):
                curve_type, key_bit_len = ecc_curve_type_from_key(key, key_type)
                key_int_list = transform_key_to_list(key)
                data_len = len(key_int_list)
            else:
                key_int_list, data_len, key_bit_len, curve_type = from_file_dat(key,
                                                                                key_type,
                                                                                encode_format)
            if self._session.is_auth and \
                curve_type not in [apis.kSE05x_ECCurve_NIST_P256, apis.kSE05x_ECCurve_NIST_P384]:
                raise Exception("ERROR! Only NIST_P256 and NIST_P384 are supported for AUTH")
            cypher_type, key_len = get_ecc_cypher_type(curve_type)  # pylint: disable=unused-variable
        except Exception as exc:  # pylint: disable=broad-except
            if 'Could not deserialize key data' in str(exc):
                log.error("Incorrect key, try with correct ECC public key")
            elif 'Non-hexadecimal digit found' in str(exc) or 'Odd-length string' in str(exc):
                log.error('Incorrect file or path, try with correct ECC public key file')
            else:
                raise exc
            return apis.kStatus_SSS_Fail
        key_ctype = (ctypes.c_uint8 * data_len)(*key_int_list)
        status = self._set_key(key_id, key_ctype, data_len, key_bit_len,
                               key_type, cypher_type, policy)
        return status

    def do_set_ecc_key_pair(self, key_id, key, policy, encode_format=""):
        """
        Inject ECC Key pair
        :param key_id: Key Index to set key
        :param key: Key value
        :param policy: Policy to be applied
        :param encode_format: Encode format of the key value. Eg: PEM, DER
        :return: Status
        """
        key_type = apis.kSSS_KeyPart_Pair
        try:
            if not os.path.isfile(key):
                curve_type, key_bit_len = ecc_curve_type_from_key(key, key_type)
                key_int_list = transform_key_to_list(key)
                data_len = len(key_int_list)
            else:
                key_int_list, data_len, key_bit_len, curve_type = from_file_dat(key,
                                                                                key_type,
                                                                                encode_format)
            if self._session.is_auth and \
                curve_type not in [apis.kSE05x_ECCurve_NIST_P256, apis.kSE05x_ECCurve_NIST_P384]:
                raise Exception("ERROR! Only NIST_P256 and NIST_P384 are supported for AUTH")
            cypher_type, key_len = get_ecc_cypher_type(curve_type)  # pylint: disable=unused-variable
        except Exception as exc:  # pylint: disable=broad-except
            if 'Could not deserialize key data' in str(exc):
                log.error("Incorrect key pair, try with correct ECC key pair")
            elif 'Non-hexadecimal digit found' in str(exc) or 'Odd-length string' in str(exc):
                log.error('Incorrect file or path, try with correct ECC key pair file')
            else:
                raise exc
            return apis.kStatus_SSS_Fail

        key_ctype = (ctypes.c_uint8 * data_len)(*key_int_list)
        status = self._set_key(key_id, key_ctype, data_len, key_bit_len,
                               key_type, cypher_type, policy)
        return status

    def do_set_aes_key(self, key_id, key, policy):
        """
        Inject Symmetric key
        :param key_id: Key Index to set key
        :param key: Key value
        :param policy: Policy to be applied
        :return: Status
        """
        key_type = apis.kSSS_KeyPart_Default
        cypher_type = apis.kSSS_CipherType_AES

        key_ctype = self._parse_key(key)

        if self.key_len not in [16, 24, 32]:
            log.warning("Unsupported key length: %s", (self.key_len * 8))
            log.warning("Supported key lengths are 128, 192 and 256 bit")
            return apis.kStatus_SSS_Fail

        status = self._set_key(key_id, key_ctype, self.key_len, self.key_len * 8,
                               key_type, cypher_type, policy)
        return status

    def do_set_des_key(self, key_id, key, policy):
        """
        Inject Symmetric DES key
        :param key_id: Key Index to set key
        :param key: Key value
        :param policy: Policy to be applied
        :return: Status
        """
        key_type = apis.kSSS_KeyPart_Default
        cypher_type = apis.kSSS_CipherType_DES

        if os.path.isfile(key):
            with open(key, 'rb') as aes_in:
                des_data = aes_in.read()
        else:
            des_data = key

        if is_hex(des_data):
            if isinstance(des_data, bytes):
                des_data = bytes.decode(des_data)
            des_data = des_data.replace("0x", "")
            des_key = transform_key_to_list(des_data)
        else:
            if isinstance(des_data, str):
                des_data = str.encode(des_data)
            des_key = key_der_to_list(des_data)

        self.key_len = len(des_key)

        if self.key_len not in [8, 16, 24]:
            log.warning("Unsupported key length: %s", (self.key_len * 8))
            log.warning("Supported key lengths are 128, 192 and 256 bit")
            return apis.kStatus_SSS_Fail
        key_ctype = (ctypes.c_uint8 * self.key_len)(*des_key)
        status = self._set_key(key_id, key_ctype, self.key_len, self.key_len * 8,
                               key_type, cypher_type, policy)
        return status

    def do_set_hmac_key(self, key_id, key, policy):
        """
        Inject hmac key
        :param key_id: Key Index to set key
        :param key: Key value
        :param policy: Policy to be applied
        :return: Status
        """
        key_type = apis.kSSS_KeyPart_Default
        cypher_type = apis.kSSS_CipherType_HMAC

        if os.path.isfile(key):
            with open(key, 'rb') as hmac_in:
                hmac_data = hmac_in.read()
        else:
            hmac_data = key

        if is_hex(hmac_data):
            if isinstance(hmac_data, bytes):
                hmac_data = bytes.decode(hmac_data)
            hmac_data = hmac_data.replace("0x", "")
            hmac_key = transform_key_to_list(hmac_data)
        else:
            if isinstance(hmac_data, str):
                hmac_data = str.encode(hmac_data)
            hmac_key = key_der_to_list(hmac_data)

        self.key_len = len(hmac_key)
        if self.key_len > 256:
            log.warning("Unsupported key length: %s", (self.key_len))
            log.warning("Supported key lengths are between 1 to 256 bytes")
            return apis.kStatus_SSS_Fail

        key_ctype = (ctypes.c_uint8 * self.key_len)(*hmac_key)
        status = self._set_key(key_id, key_ctype, self.key_len, self.key_len * 8,
                               key_type, cypher_type, policy)
        return status

    def do_set_rsa_pub_key(self, key_id, key, policy, encode_format=""):
        """
        Inject RSA Public key
        :param key_id: Key Index to set key
        :param key: Key value
        :param policy: Policy to be applied
        :param encode_format: Encode format of the key value. Eg: PEM, DER
        :return: Status
        """
        key_type = apis.kSSS_KeyPart_Public
        cypher_type = apis.kSSS_CipherType_RSA_CRT
        try:
            if not os.path.isfile(key):
                key_int_list = transform_key_to_list(key)
                data_len = len(key)
                key_bit_len = data_len * 8
            else:
                key_int_list, data_len, key_bit_len, curve_type = from_file_dat(key,  # pylint: disable=unused-variable
                                                                                key_type,
                                                                                encode_format)
        except Exception as exc:  # pylint: disable=broad-except
            if 'Could not deserialize key data' in str(exc):
                log.error("Incorrect key, try with correct RSA public key")
            elif 'invalid literal for int' in str(exc):
                log.error('Incorrect file or path, try with correct RSA public key file')
            else:
                raise exc
            return apis.kStatus_SSS_Fail
        if self._session.is_auth:
            raise Exception("ERROR! RSA is not supported for AUTH")
        key_ctype = (ctypes.c_uint8 * data_len)(*key_int_list)
        status = self._set_key(key_id, key_ctype, data_len, key_bit_len,
                               key_type, cypher_type, policy)
        return status

    def do_set_rsa_key_pair(self, key_id, key, policy, encode_format=""):
        """
        Inject RSA key pair
        :param key_id: Key index to set key
        :param key: Key value
        :param policy: Policy to be applied
        :param encode_format: Encode format of the key value. Eg: PEM, DER
        :return: Status
        """
        key_type = apis.kSSS_KeyPart_Pair
        cypher_type = apis.kSSS_CipherType_RSA_CRT
        try:
            if not os.path.isfile(key):
                key_int_list = transform_key_to_list(key)
                data_len = len(key)
                key_bit_len = data_len * 8
            else:

                key_int_list, data_len, key_bit_len, curve_type = from_file_dat(key,  # pylint: disable=unused-variable
                                                                                key_type,
                                                                                encode_format)
        except Exception as exc:  # pylint: disable=broad-except
            if 'Could not deserialize key data' in str(exc):
                log.error("Incorrect key pair, try with correct RSA key pair")
            elif 'invalid literal for int' in str(exc):
                log.error('Incorrect file or path, try with correct RSA key pair file')
            else:
                raise exc
            return apis.kStatus_SSS_Fail

        if self._session.is_auth:
            raise Exception("ERROR! RSA is not supported for AUTH")
        key_ctype = (ctypes.c_uint8 * data_len)(*key_int_list)
        status = self._set_key(key_id, key_ctype, data_len, key_bit_len,
                               key_type, cypher_type, policy)
        return status

    def do_set_cert(self, cert_id, raw_cert, policy, encode_format=""):
        """
        Inject Certificate
        :param cert_id: Index to set certificate
        :param raw_cert: Certificate value
        :param policy: Policy to be applied
        :param encode_format: Encode format of the key value. Eg: PEM, DER
        :return: Status
        """
        key_type = apis.kSSS_KeyPart_Default
        cypher_type = apis.kSSS_CipherType_Binary
        if not os.path.isfile(raw_cert):
            cert_data = to_cert_dat(raw_cert)
            cert_len = len(cert_data)
            key_bit_len = cert_len * 8
        else:

            cert_data, cert_len, key_bit_len, curve = from_file_dat(raw_cert,  # pylint: disable=unused-variable
                                                                    key_type,
                                                                    encode_format)

        cert_ctype = (ctypes.c_uint8 * cert_len)(*cert_data)

        status = self._set_key(cert_id, cert_ctype, cert_len, key_bit_len, key_type,
                               cypher_type, policy)

        return status

    def do_create_counter(self, counter_id, counter_size, policy):
        """
        Inject Counter
        :param counter_id: Index to set counter, passing existing counter leads to increment of counter if possible.
        :param counter_size: Size of counter, no value required for existing counter
        :param counter_val: Initial value of counter, no value needed for existing couter
        :param policy: Policy to be applied, no value needed for existing coutner.
        :return: Status
        """
        key_type = apis.kSSS_KeyPart_Default
        cypher_type = apis.kSSS_CipherType_Count

        status = self._ctx_key.allocate_handle(counter_id, key_type, cypher_type, counter_size,
                                               self._key_object_mode)
        if status != apis.kStatus_SSS_Success:
            return status

        status = apis.Se05x_API_CreateCounter(ctypes.byref(self._session.session_ctx.s_ctx), policy, counter_id, counter_size)
        if status != apis.kSE05x_SW12_NO_ERROR:
            log.error("failed")
            return apis.kStatus_SSS_Fail
        return apis.kStatus_SSS_Success

    def do_set_counter(self, counter_id, counter_size, counter_val):
        """
        Inject Counter
        :param counter_id: Index to set counter, passing existing counter leads to increment of counter if possible.
        :param counter_val: Initial value of counter, no value needed for existing couter
        :return: Status
        """
        status = apis.Se05x_API_SetCounterValue(ctypes.byref(self._session.session_ctx.s_ctx), counter_id, counter_size, counter_val)
        if status != apis.kSE05x_SW12_NO_ERROR:
            log.error("failed")
            return apis.kStatus_SSS_Fail
        return apis.kStatus_SSS_Success

    def do_increment_counter(self, counter_id):
        """
        Inject Counter
        :param counter_id: Index to set counter.
        :return: Status
        """
        status = apis.Se05x_API_IncCounter(ctypes.byref(self._session.session_ctx.s_ctx), counter_id)
        if status != apis.kSE05x_SW12_NO_ERROR:
            log.error("failed")
            return apis.kStatus_SSS_Fail
        return apis.kStatus_SSS_Success

    def do_read_counter(self, counter_id, counter_size):
        """
        Inject Counter
        :param counter_id: Index to set counter
        :param counter_size: Size of counter
        :return: Status
        """
        key_type = apis.kSSS_KeyPart_Default
        cypher_type = apis.kSSS_CipherType_Count

        status = apis.sss_key_store_get_key(ctypes.byref(self._session.session_ctx.s_ctx), counter_id, counter_size/8)
        return status

    def do_write_userid(self, key_id, userid, max_attempts, policy):
        """
        Write userid
        :param key_id: Index to set userid
        :param userid: Value of userid
        :param policy: Policy to be applied
        :return: Status
        """
        key_type = apis.kSSS_KeyPart_Default
        cypher_type = apis.kSSS_CipherType_UserID

        status = self._ctx_key.allocate_handle(key_id, key_type, cypher_type, len(userid),
                                               self._key_object_mode)
        if status != apis.kStatus_SSS_Success:
            return status

        # userid_list = list()
        # for i in range(len(userid)):
        #     userid_list.append(i)
        b = bytearray()
        b.extend(userid.encode())
        userid_ctype = (ctypes.c_ubyte * len(b))(*b)
        status = apis.Se05x_API_WriteUserID(ctypes.byref(self._session.session_ctx.s_ctx), None, 0, key_id, ctypes.byref(userid_ctype), len(b), apis.kSE05x_AttestationType_AUTH)
        if status != apis.kSE05x_SW12_NO_ERROR:
            log.error("failed")
            return apis.kStatus_SSS_Fail
        return apis.kStatus_SSS_Success

    def do_set_bin(self, key_id, bin_data_in, policy):
        """
        Inject Binary
        :param key_id: Index to set binary data
        :param bin_data_in: binary data value
        :param policy: Policy to be applied
        :return: Status
        """
        key_type = apis.kSSS_KeyPart_Default
        cypher_type = apis.kSSS_CipherType_Binary

        # Extract contents if file
        if os.path.isfile(bin_data_in):
            with open(bin_data_in, 'rb') as file_in:
                bin_data_raw = file_in.read()
        else:
            bin_data_raw = bin_data_in

        # If data is in bytes then convert it to hex
        if isinstance(bin_data_raw, bytes):
            bin_data = bin_data_raw.hex()
        else:
            bin_data = bin_data_raw

        # Hex values convert it to integer list
        if is_hex(bin_data):
            key_data = transform_key_to_list(bin_data)
        else:
            key_data = to_cert_dat(bin_data)
        key_len = len(key_data)
        key_bit_len = key_len * 8
        bin_ctype = (ctypes.c_uint8 * key_len)(*key_data)

        status = self._set_key(key_id, bin_ctype, key_len, key_bit_len, key_type,
                               cypher_type, policy)

        return status

    def _set_key(self, key_id, data, data_len, key_bit_len,  # pylint: disable=too-many-arguments
                 key_type, cypher_type, policy):
        """
        Inject keys and certificate
        :param key_id: Index to set key/certificate
        :param data: key value to set
        :param data_len: length of the key value
        :param key_bit_len: bit length of the key value
        :param key_type: key type
        :param cypher_type: cipher type
        :param policy: Policy to be applied
        :return: Status
        """

        status = self._ctx_key.allocate_handle(key_id, key_type, cypher_type, data_len,
                                               self._key_object_mode)
        if status != apis.kStatus_SSS_Success:
            return status

        status = self._ctx_ks.set_key(self._ctx_key, data, data_len, key_bit_len, policy, 0)

        if status != apis.kStatus_SSS_Success:
            return status

        status = self._ctx_ks.save_key_store()
        return status

    def _parse_key(self, key):
        if os.path.isfile(key):
            with open(key, 'rb') as aes_in:
                key_data = aes_in.read()
        else:
            key_data = key

        if is_hex(key_data):
            if isinstance(key_data, bytes):
                key_data = bytes.decode(key_data)
            key_data = key_data.replace("0x", "")
            key_val = transform_key_to_list(key_data)
        else:
            if isinstance(key_data, str):
                key_data = str.encode(key_data)
            key_val = key_der_to_list(key_data)

        self.key_len = len(key_val)

        return (ctypes.c_uint8 * self.key_len)(*key_val)

    def do_set_wrapped_aes_key(self, key_id, wrapped_key, kek_id, policy):
        """
        Inject Wrapped AES key
        :param key_id: Key Index to set key
        :param wrapped_key: Key value
        :param policy: Policy to be applied
        :return: Status
        """
        key_type = apis.kSSS_KeyPart_Default
        cipher_type = apis.kSSS_CipherType_AES
        wrap_key_ctype = self._parse_key(wrapped_key)
        return self._set_wrapped_key(key_id, key_type, cipher_type, wrap_key_ctype, kek_id, policy)

    def do_set_wrapped_des_key(self, key_id, wrapped_key, kek_id, policy):
        """
        Inject Wrapped AES key
        :param key_id: Key Index to set key
        :param wrapped_key: Key value
        :param policy: Policy to be applied
        :return: Status
        """
        key_type = apis.kSSS_KeyPart_Default
        cipher_type = apis.kSSS_CipherType_DES
        wrap_key_ctype = self._parse_key(wrapped_key)
        return self._set_wrapped_key(key_id, key_type, cipher_type, wrap_key_ctype, kek_id, policy)

    def do_set_wrapped_hmac_key(self, key_id, wrapped_key, kek_id, policy):
        """
        Inject Wrapped AES key
        :param key_id: Key Index to set key
        :param wrapped_key: Key value
        :param policy: Policy to be applied
        :return: Status
        """
        key_type = apis.kSSS_KeyPart_Default
        cipher_type = apis.kSSS_CipherType_HMAC
        wrap_key_ctype = self._parse_key(wrapped_key)
        return self._set_wrapped_key(key_id, key_type, cipher_type, wrap_key_ctype, kek_id, policy)

    def _set_wrapped_key(self, key_id, key_type, cipher_type, wrap_key_ctype, kek_id, policy):

        status = self._ctx_key.allocate_handle(key_id, key_type, cipher_type, self.key_len,
                                               self._key_object_mode)
        if status != apis.kStatus_SSS_Success:
            return status

        status, key_type_kek, cipher_type_kek = self._ctx_kek_key.get_handle(kek_id)
        if status != apis.kStatus_SSS_Success:
            return status

        status = self._ctx_ks.open_key(None)
        if status != apis.kStatus_SSS_Success:
            return status

        status = self._ctx_ks.open_key(self._ctx_kek_key)
        if status != apis.kStatus_SSS_Success:
            return status

        status = self._ctx_ks.set_key(self._ctx_key, wrap_key_ctype,
            self.key_len, self.key_len * 8, policy, 0)

        if status != apis.kStatus_SSS_Success:
            return status

        status = self._ctx_ks.save_key_store()
        return status
