#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
# Modified by AutoPi 2022

"""License text"""

import os
import ctypes
import binascii
import logging
from . import sss_api as apis
from .keystore import KeyStore
from .keyobject import KeyObject
from .asymmetric import Asymmetric
from .symmetric import Symmetric
from .util import hash_convert, hash_convert_raw, save_to_file, \
    load_certificate, transform_key_to_list, encode_to_pem
from .const import HASH
log = logging.getLogger(__name__)


class Sign:  # pylint: disable=too-few-public-methods
    """
    Sign operation
    """

    def __init__(self, session_obj):
        """
        Constructor
        :param session_obj: Instance of session
        """
        self._session = session_obj
        self._ctx_ks = KeyStore(self._session)
        self._ctx_key = KeyObject(self._ctx_ks)
        self.signature_data = None
        self.hash_algo = apis.kAlgorithm_None
        self.symmetric_sign_mac_one_go = True

    def do_signature(self, key_id, input_file, filename,  # pylint: disable=too-many-locals, too-many-arguments
                     in_encode_format="", out_encode_format="", hash_algo=""):
        """
        DO sign operation
        :param key_id: Key index
        :param input_file: Input data to be signed
        :param filename: File name to store the signature data
        :param in_encode_format: Input data file encode format
        :param out_encode_format: Output Signature file encode format
        :param hash_algo: Hash algorithm to sign
        :return: Status
        """
        status, object_type, cipher_type = self._ctx_key.get_handle(key_id)  # pylint: disable=unused-variable
        if status != apis.kStatus_SSS_Success:
            return status

        if hash_algo == '':
            # Default hash algorithm
            if cipher_type in [apis.kSSS_CipherType_RSA, apis.kSSS_CipherType_RSA_CRT]:
                log.debug("Considering Algorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA256 "
                          "as Default hash algorithm for RSA")
                self.hash_algo = apis.kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA256
            elif cipher_type in [apis.kSSS_CipherType_EC_TWISTED_ED]:
                log.debug("Considering Algorithm_SSS_SHA512 as Default hash algorithm")
                self.hash_algo = apis.kAlgorithm_SSS_SHA512
            elif cipher_type == apis.kSSS_CipherType_HMAC:
                log.debug("Considering kAlgorithm_SSS_HMAC_SHA512 as Default hash algorithm")
                self.hash_algo = apis.kAlgorithm_SSS_HMAC_SHA512
            elif cipher_type == apis.kSSS_CipherType_AES:
                log.debug("Considering kAlgorithm_SSS_CMAC_AES as Default hash algorithm")
                self.hash_algo = apis.kAlgorithm_SSS_CMAC_AES
            elif cipher_type == apis.kSSS_CipherType_DES:
                log.debug("Considering kAlgorithm_SSS_DES_CMAC8 as Default hash algorithm")
                self.hash_algo = apis.kAlgorithm_SSS_DES_CMAC8
            else:
                log.debug("Considering Algorithm_SSS_SHA256 as Default hash algorithm")
                self.hash_algo = apis.kAlgorithm_SSS_SHA256
        else:
            # Take hash algorithm from user
            self.hash_algo = HASH[hash_algo]

        try:
            if not os.path.isfile(input_file):
                raise Exception("Incorrect input file, try signing with correct input file !!")

            if cipher_type in [apis.kSSS_CipherType_EC_TWISTED_ED]:
                digest, digest_len = load_certificate(input_file)
            elif cipher_type in [apis.kSSS_CipherType_HMAC, apis.kSSS_CipherType_AES, apis.kSSS_CipherType_DES]:
                with open(input_file, 'rb') as raw_data:
                    digest = raw_data.read()
                digest_len = len(digest)
            else:
                (digest, digest_len) = hash_convert(input_file, in_encode_format, self.hash_algo)
        except Exception as exc:  # pylint: disable=broad-except
            # If input data is not certificate, then load it as binary data
            if 'Unable to load certificate' in str(exc) or 'error parsing asn1 value' in str(exc):
                if os.path.isfile(input_file):
                    with open(input_file, 'rb') as raw_data:
                        src_data = raw_data.read()
                    if cipher_type in [apis.kSSS_CipherType_EC_TWISTED_ED]:
                        cert_hex = binascii.hexlify(src_data)
                        digest = transform_key_to_list(cert_hex)
                        digest_len = len(digest)
                    else:
                        (digest, digest_len) = hash_convert_raw(src_data, self.hash_algo)
                else:
                    raise Exception("Incorrect input file, try signing with correct input file !!")  # pylint: disable=raise-missing-from
            else:
                raise exc

        digest = (ctypes.c_ubyte * digest_len)(*digest)
        mode = apis.kMode_SSS_Sign
        # Signature length set to 1024 to support all EC curves and RSA key size
        signature_len = 1024
        data_buf = (ctypes.c_uint8 * signature_len)(0)
        signature_len = ctypes.c_size_t(signature_len)

        if cipher_type in [apis.kSSS_CipherType_HMAC, apis.kSSS_CipherType_AES, apis.kSSS_CipherType_DES]:
            ctx = Symmetric(self._session)
            ctx.algorithm = self.hash_algo
        else:
            ctx = Asymmetric(self._session, self._ctx_key, self.hash_algo, mode)
        if cipher_type in [apis.kSSS_CipherType_HMAC, apis.kSSS_CipherType_AES, apis.kSSS_CipherType_DES]:
            if self.symmetric_sign_mac_one_go:
                status = ctx.mac_one_go(self._ctx_key, digest, digest_len)
            else:
                status = ctx.mac_multi_step(self._ctx_key, digest, digest_len)
            signature_ctype = ctx.out_data
            signature_len = ctx.out_data_size
        elif cipher_type in [apis.kSSS_CipherType_EC_TWISTED_ED]:
            (signature_ctype, status) = ctx.se05x_sign(digest, digest_len, data_buf, signature_len)
        else:
            (signature_ctype, status) = ctx.sign(digest, digest_len, data_buf, signature_len)
        if signature_ctype is None:
            log.error("Received signature data is empty")
            return status
        signature_full_list = list(signature_ctype)
        signature_list = signature_full_list[:int(signature_len.value)]
        if filename is not None:
            status = save_to_file(signature_list, filename,
                                  apis.kSSS_KeyPart_NONE, out_encode_format)
        der = ""
        for signature_item in signature_list:
            der += str(signature_item)
        self.signature_data = binascii.unhexlify(der)
        return status


    def do_signature_and_return(self, key_id, input_data, out_encode_format="", hash_algo=""):
        """
        DO sign operation on a string and return the signature
        :param key_id: Key index
        :param input_data: String data to be signed 
        :param out_encode_format: Output Signature file encode format (DER or PEM)
        :param hash_algo: Hash algorithm to sign
        :return: signature
        """
        status, object_type, cipher_type = self._ctx_key.get_handle(key_id)  
        if status != apis.kStatus_SSS_Success:
            return status

        if hash_algo == '':
            # Default hash algorithm
            if cipher_type in [apis.kSSS_CipherType_RSA, apis.kSSS_CipherType_RSA_CRT]:
                log.debug("Considering Algorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA256 "
                          "as Default hash algorithm for RSA")
                self.hash_algo = apis.kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA256
            elif cipher_type in [apis.kSSS_CipherType_EC_TWISTED_ED]:
                log.debug("Considering Algorithm_SSS_SHA512 as Default hash algorithm")
                self.hash_algo = apis.kAlgorithm_SSS_SHA512
            elif cipher_type == apis.kSSS_CipherType_HMAC:
                log.debug("Considering kAlgorithm_SSS_HMAC_SHA512 as Default hash algorithm")
                self.hash_algo = apis.kAlgorithm_SSS_HMAC_SHA512
            elif cipher_type == apis.kSSS_CipherType_AES:
                log.debug("Considering kAlgorithm_SSS_CMAC_AES as Default hash algorithm")
                self.hash_algo = apis.kAlgorithm_SSS_CMAC_AES
            elif cipher_type == apis.kSSS_CipherType_DES:
                log.debug("Considering kAlgorithm_SSS_DES_CMAC8 as Default hash algorithm")
                self.hash_algo = apis.kAlgorithm_SSS_DES_CMAC8
            else:
                log.debug("Considering Algorithm_SSS_SHA256 as Default hash algorithm")
                self.hash_algo = apis.kAlgorithm_SSS_SHA256
        else:
            # Take hash algorithm from user
            self.hash_algo = HASH[hash_algo]

        (digest, digest_len) = hash_convert_raw(input_data, self.hash_algo)

        digest = (ctypes.c_ubyte * digest_len)(*digest)
        mode = apis.kMode_SSS_Sign
        # Signature length set to 1024 to support all EC curves and RSA key size
        signature_len = 1024
        data_buf = (ctypes.c_uint8 * signature_len)(0)
        signature_len = ctypes.c_size_t(signature_len)

        if cipher_type in [apis.kSSS_CipherType_HMAC, apis.kSSS_CipherType_AES, apis.kSSS_CipherType_DES]:
            ctx = Symmetric(self._session)
            ctx.algorithm = self.hash_algo
        else:
            # The library apparently uses the hash_algo to know how long the digest is.
            # When using KECCAK256 (not supported by default), pass SHA256, which is the same length
            ctx = Asymmetric(self._session, self._ctx_key, apis.kAlgorithm_SSS_SHA256 if self.hash_algo == "KECCAK256" else self.hash_algo, mode)
        if cipher_type in [apis.kSSS_CipherType_HMAC, apis.kSSS_CipherType_AES, apis.kSSS_CipherType_DES]:
            if self.symmetric_sign_mac_one_go:
                status = ctx.mac_one_go(self._ctx_key, digest, digest_len)
            else:
                status = ctx.mac_multi_step(self._ctx_key, digest, digest_len)
            signature_ctype = ctx.out_data
            signature_len = ctx.out_data_size
        elif cipher_type in [apis.kSSS_CipherType_EC_TWISTED_ED]:
            (signature_ctype, status) = ctx.se05x_sign(digest, digest_len, data_buf, signature_len)
        else:
            (signature_ctype, status) = ctx.sign(digest, digest_len, data_buf, signature_len)
        if signature_ctype is None:
            log.error("Received signature data is empty")
            return status
        signature_full_list = list(signature_ctype)
        signature_list = signature_full_list[:int(signature_len.value)]

        pem_data = encode_to_pem(signature_list, apis.kSSS_KeyPart_NONE, out_encode_format)
        return pem_data