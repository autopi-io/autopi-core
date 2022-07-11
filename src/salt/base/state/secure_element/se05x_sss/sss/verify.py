#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import os
import ctypes
import logging
import binascii
from . import sss_api as apis
from .keystore import KeyStore
from .keyobject import KeyObject
from .asymmetric import Asymmetric
from .symmetric import Symmetric
from .const import HASH
from .util import hash_convert, hash_convert_raw, parse_signature, \
    load_certificate, transform_key_to_list

log = logging.getLogger(__name__)


class Verify:  # pylint: disable=too-few-public-methods
    """
    Verify operation
    """

    def __init__(self, session_obj):
        """
        Constructor
        :param session_obj: Instance of session
        """
        self._session = session_obj
        self._ctx_ks = KeyStore(self._session)
        self._ctx_key = KeyObject(self._ctx_ks)
        self.hash_algo = apis.kAlgorithm_None
        self.symmetric_verify_mac_one_go = True

    def do_verification(self, key_id, input_file, signature_file,  # pylint: disable=too-many-locals, too-many-arguments
                        encode_format="", hash_algo=''):
        """
        Do verify operation
        :param key_id: Key index
        :param input_file: Input data to verify with signature
        :param signature_file: Input signed data to verify with raw data
        :param encode_format: file Encode format. Eg: PEM, DER
        :param hash_algo: hash algorithm for verify
        :return: Status
        """

        status, object_type, cipher_type = self._ctx_key.get_handle(key_id)  # pylint: disable=unused-variable
        if status != apis.kStatus_SSS_Success:
            return status

        if hash_algo == '':
            # Default hash algorithm
            if cipher_type in [apis.kSSS_CipherType_RSA, apis.kSSS_CipherType_RSA_CRT]:
                log.debug("Considering Algorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA256"
                          " as Default hash algorithm for RSA")
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
                raise Exception("Incorrect input file, try verifying with correct input file !!")  # pylint: disable=raise-missing-from

            if cipher_type in [apis.kSSS_CipherType_EC_TWISTED_ED]:
                digest, digest_len = load_certificate(input_file)
            elif cipher_type in [apis.kSSS_CipherType_HMAC, apis.kSSS_CipherType_AES, apis.kSSS_CipherType_DES]:
                with open(input_file, 'rb') as raw_data:
                    digest = raw_data.read()
                digest_len = len(digest)
            else:
                (digest, digest_len) = hash_convert(input_file, encode_format, self.hash_algo)

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
                    raise Exception("Incorrect input file, try verifying with correct input file !!")  # pylint: disable=raise-missing-from
            else:
                raise exc
        try:
            (signature, signature_len) = parse_signature(signature_file, encode_format)
        except IOError as exc:
            log.error(exc)
            return apis.kStatus_SSS_Fail
        digest_ctype = (ctypes.c_ubyte * digest_len)(*digest)
        mode = apis.kMode_SSS_Verify
        signature_ctype = (ctypes.c_uint8 * signature_len)(*signature)
        signature_len_ctype = ctypes.c_size_t(signature_len)

        if cipher_type in [apis.kSSS_CipherType_HMAC, apis.kSSS_CipherType_AES, apis.kSSS_CipherType_DES]:
            ctx = Symmetric(self._session)
            ctx.algorithm = self.hash_algo
            ctx.mode = apis.kMode_SSS_Mac_Validate
        else:
            ctx = Asymmetric(self._session, self._ctx_key, self.hash_algo, mode)

        if cipher_type in [apis.kSSS_CipherType_HMAC, apis.kSSS_CipherType_AES, apis.kSSS_CipherType_DES]:
            if self.symmetric_verify_mac_one_go:
                status = ctx.mac_validate_one_go(self._ctx_key, digest_ctype, digest_len, signature_ctype, signature_len_ctype)
            else:
                status = ctx.mac_multi_step(self._ctx_key, digest_ctype, digest_len, signature_ctype, signature_len_ctype)
        elif cipher_type in [apis.kSSS_CipherType_EC_TWISTED_ED]:
            status = ctx.se05x_verify(
                digest_ctype, digest_len, signature_ctype, signature_len_ctype)
        else:
            status = ctx.verify(
                digest_ctype, digest_len, signature_ctype, signature_len_ctype)
        return status
