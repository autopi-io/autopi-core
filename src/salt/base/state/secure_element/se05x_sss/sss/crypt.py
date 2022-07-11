#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import os
import sys
import ctypes
import logging
import binascii
from . import sss_api as apis
from .keystore import KeyStore
from .keyobject import KeyObject
from .asymmetric import Asymmetric
from .symmetric import Symmetric
from . import util

log = logging.getLogger(__name__)


class Crypt:
    """
    Encrypt and Decypt operation
    """

    def __init__(self, session_obj):
        """
        constructor
        :param session_obj: Instance of session
        """
        self._session = session_obj
        self._ctx_ks = KeyStore(session_obj)
        self._ctx_key = KeyObject(self._ctx_ks)
        self.encrypt_data = None
        self.decrypt_data = None
        self.algorithm = apis.kAlgorithm_None
        self.crypt_data_len = 1024
        self.use_aead = False
        self.cipher_one_go = True
        self.aead_one_go = True
        self.nonce = None
        self.tag = None
        self.aad = None
        self.iv = None
        self.encrypt_data_list = None

    def do_encryption(self, key_id, pre_encrypted_data, encrypted_data_file):  # pylint: disable=too-many-locals
        """
        Perform Encryption
        :param key_id: Key index
        :param pre_encrypted_data: Input data to encrypt
        :param encrypted_data_file: File name to store encrypted data
        :return: Status
        """
        if not os.path.isfile(pre_encrypted_data):
            src_data = str.encode(pre_encrypted_data)
        else:
            with open(pre_encrypted_data, 'rb') as raw_data:
                src_data = raw_data.read()
        src_data_len = len(src_data)

        mode = apis.kMode_SSS_Encrypt
        encrypt_data_buf = (ctypes.c_uint8 * self.crypt_data_len)(0)
        encrypt_data_len_ctype = ctypes.c_size_t(self.crypt_data_len)

        status, obj_type, cypher_type = self._ctx_key.get_handle(key_id)  # pylint: disable=unused-variable
        if status != apis.kStatus_SSS_Success:
            return status

        if cypher_type in [apis.kSSS_CipherType_RSA_CRT, apis.kSSS_CipherType_RSA]:
            # convert pre encrypted data format to list
            src_data_list = []
            for ch in src_data:
                if sys.hexversion < 0x3000000:
                    src_data_list.append(ord(ch))
                else:
                    src_data_list.append(ord(chr(ch)))
            src_data_ctype = (ctypes.c_ubyte * src_data_len)(*src_data_list)
            if self.algorithm == apis.kAlgorithm_None:
                self.algorithm = apis.kAlgorithm_SSS_RSAES_PKCS1_V1_5
            ctx_asymm = Asymmetric(self._session, self._ctx_key, self.algorithm, mode)
            status, encrypt_data = ctx_asymm.encrypt(
                src_data_ctype, src_data_len, encrypt_data_buf, encrypt_data_len_ctype)
            if status != apis.kStatus_SSS_Success:
                return status
            if encrypt_data is None:
                log.error("Received encrypted data is empty")
                return status

            encrypt_data_full_list = list(encrypt_data)
            # remove extra zero padding
            self.encrypt_data_list = encrypt_data_full_list[:int(encrypt_data_len_ctype.value)]

            self.encrypt_data = (ctypes.c_uint8 * int(encrypt_data_len_ctype.value))(*self.encrypt_data_list)


        elif cypher_type in [apis.kSSS_CipherType_HMAC, apis.kSSS_CipherType_AES, apis.kSSS_CipherType_DES]:
            ctx_symm = Symmetric(self._session)
            if self.algorithm == apis.kAlgorithm_None:
                if cypher_type == apis.kSSS_CipherType_AES:
                    ctx_symm.algorithm = apis.kAlgorithm_SSS_AES_CTR
                elif cypher_type == apis.kSSS_CipherType_DES:
                    ctx_symm.algorithm = apis.kAlgorithm_SSS_DES_ECB
                elif cypher_type == apis.kSSS_CipherType_HMAC:
                    ctx_symm.algorithm = apis.kAlgorithm_SSS_HMAC_SHA256
            else:
                ctx_symm.algorithm = self.algorithm
            ctx_symm.mode = mode
            ctx_symm.iv = self.iv
            if self.use_aead and cypher_type == apis.kSSS_CipherType_AES:
                ctx_symm.nonce = self.nonce
                ctx_symm.aad = self.aad
                if self.aead_one_go:
                    status = ctx_symm.aead_one_shot(self._ctx_key, src_data, self.tag, len(self.tag))
                else:
                    status = ctx_symm.aead_init(self._ctx_key, src_data, self.tag, len(self.tag))
                self.tag = ctx_symm.tag
            else:
                if self.cipher_one_go:
                    status = ctx_symm.cipher_one_shot(self._ctx_key, src_data)
                else:
                    status = ctx_symm.cipher_init(self._ctx_key, src_data)
            if status != apis.kStatus_SSS_Success:
                return status
            self.encrypt_data_list = list(ctx_symm.out_data)

        else:
            log.warning("Encrypt operation supported only for Symmetric and RSA keys")
            return apis.kStatus_SSS_Fail

        if encrypted_data_file is not None:
            crypt_hex_str = util.transform_int_list_to_hex_str(self.encrypt_data_list)
            crypt_der_str = binascii.unhexlify(crypt_hex_str)
            util.file_write(crypt_der_str, encrypted_data_file)
        return status

    def do_decryption(self, key_id, encrypted_data, decrypt_file):  # pylint: disable=too-many-locals
        """
        Perform decryption
        :param key_id: Key Index
        :param encrypted_data: Encrypted raw data or in file
        :param decrypt_file: Output file name to store decrypted data
        :return: Status
        """
        if os.path.isfile(encrypted_data):
            with open(encrypted_data, 'rb') as key_in:
                src_data = key_in.read()
        else:
            src_data = encrypted_data
        src_data_len = len(src_data)

        mode = apis.kMode_SSS_Decrypt
        decrypt_data_len = 1024
        decrypt_data_buf = (ctypes.c_uint8 * decrypt_data_len)(0)
        decrypt_data_len_ctype = ctypes.c_size_t(decrypt_data_len)

        status, obj_type, cypher_type = self._ctx_key.get_handle(key_id)  # pylint: disable=unused-variable
        if status != apis.kStatus_SSS_Success:
            return status

        if cypher_type in [apis.kSSS_CipherType_RSA_CRT, apis.kSSS_CipherType_RSA]:
            src_data_ctype = (ctypes.c_ubyte * src_data_len)(*src_data)
            if self.algorithm == apis.kAlgorithm_None:
                self.algorithm = apis.kAlgorithm_SSS_RSAES_PKCS1_V1_5
            ctx_asymm = Asymmetric(self._session, self._ctx_key, self.algorithm, mode)
            status, decrypt_data = ctx_asymm.decrypt(
                src_data_ctype, src_data_len, decrypt_data_buf, decrypt_data_len_ctype)

            if status != apis.kStatus_SSS_Success:
                return status
            if decrypt_data is None:
                log.error("Received decrypted data is empty")
                return status
            decrypt_data_full_list = list(decrypt_data)
            decrypt_data_list = decrypt_data_full_list[:int(decrypt_data_len_ctype.value)]

        elif cypher_type in [apis.kSSS_CipherType_HMAC, apis.kSSS_CipherType_AES, apis.kSSS_CipherType_DES]:
            src_data_hex = binascii.hexlify(src_data)
            src_data_list = util.transform_key_to_list(src_data_hex)
            ctx_symm = Symmetric(self._session)
            if self.algorithm == apis.kAlgorithm_None:
                if cypher_type == apis.kSSS_CipherType_AES:
                    ctx_symm.algorithm = apis.kAlgorithm_SSS_AES_CTR
                elif cypher_type == apis.kSSS_CipherType_DES:
                    ctx_symm.algorithm = apis.kAlgorithm_SSS_DES_ECB
                elif cypher_type == apis.kSSS_CipherType_HMAC:
                    ctx_symm.algorithm = apis.kAlgorithm_SSS_HMAC_SHA256
            else:
                ctx_symm.algorithm = self.algorithm
            ctx_symm.mode = mode
            if self.use_aead and cypher_type == apis.kSSS_CipherType_AES:
                ctx_symm.nonce = self.nonce
                ctx_symm.aad = self.aad
                if self.aead_one_go:
                    status = ctx_symm.aead_one_shot(self._ctx_key, src_data_list, self.tag, len(self.tag))
                else:
                    status = ctx_symm.aead_init(self._ctx_key, src_data_list, self.tag, len(self.tag))
            else:
                if self.cipher_one_go:
                    status = ctx_symm.cipher_one_shot(self._ctx_key, src_data_list)
                else:
                    status = ctx_symm.cipher_init(self._ctx_key, src_data_list)
            if status != apis.kStatus_SSS_Success:
                return status
            decrypt_data_list = list(ctx_symm.out_data)

        else:
            log.warning("Decrypt operation supported only for Symmetric and RSA keys")
            return apis.kStatus_SSS_Fail

        self.decrypt_data = ''.join(chr(i) for i in decrypt_data_list)

        if decrypt_file is not None:
            util.file_write(self.decrypt_data, decrypt_file)

        return status
