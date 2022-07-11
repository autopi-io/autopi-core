#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import ctypes
import logging
from . import sss_api as apis
from .keystore import KeyStore
from .keyobject import KeyObject

log = logging.getLogger(__name__)

CIPHER_TYPE_DICTIONARY = {
    apis.kSSS_CipherType_NONE: "",
    apis.kSSS_CipherType_AES: "AES",
    apis.kSSS_CipherType_DES: "DES",
    apis.kSSS_CipherType_CMAC: "CMAC",
    apis.kSSS_CipherType_HMAC: "HMAC",
    apis.kSSS_CipherType_MAC: "MAC",
    apis.kSSS_CipherType_RSA: "RSA",
    apis.kSSS_CipherType_RSA_CRT: "RSA_CRT",
    apis.kSSS_CipherType_EC_NIST_P: "NIST-P",
    apis.kSSS_CipherType_EC_NIST_K: "NIST-K",
    apis.kSSS_CipherType_EC_MONTGOMERY: "EC_MONTGOMERY",
    apis.kSSS_CipherType_EC_TWISTED_ED: "EC_TWISTED_ED",
    apis.kSSS_CipherType_EC_BRAINPOOL: "EC_BRAINPOOL",
    apis.kSSS_CipherType_EC_BARRETO_NAEHRIG: "EC_BARRETO_NAEHRIG",
    apis.kSSS_CipherType_UserID: "USER-ID",
    apis.kSSS_CipherType_Certificate: "CERTIFICATE",
    apis.kSSS_CipherType_Binary: "BINARY",
    apis.kSSS_CipherType_Count: "COUNT",
    apis.kSSS_CipherType_PCR: "PCR",
    apis.kSSS_CipherType_ReservedPin: "RESERVED_PIN"
}

KEY_PART_DICTIONARY = {
    apis.kSSS_KeyPart_NONE: "",
    apis.kSSS_KeyPart_Default: "",
    apis.kSSS_KeyPart_Public: "(Public Key)",
    apis.kSSS_KeyPart_Private: "(Private Key)",
    apis.kSSS_KeyPart_Pair: "(Key Pair)",
}

CRYPTO_OBJID_DICTIONARY = {
    apis.kSE05x_CryptoObject_NA: "",
    apis.kSE05x_CryptoObject_DIGEST_SHA: "Digest SHA1",
    apis.kSE05x_CryptoObject_DIGEST_SHA224: "Digest SHA224",
    apis.kSE05x_CryptoObject_DIGEST_SHA256: "Digest SHA256",
    apis.kSE05x_CryptoObject_DIGEST_SHA384: "Digest SHA384",
    apis.kSE05x_CryptoObject_DIGEST_SHA512: "Digest SHA512",
    apis.kSE05x_CryptoObject_DES_CBC_NOPAD: "DES_CBC_NOPAD",
    apis.kSE05x_CryptoObject_DES_CBC_ISO9797_M1: "DES_CBC_ISO9797_M1",
    apis.kSE05x_CryptoObject_DES_CBC_ISO9797_M2: "DES_CBC_ISO9797_M2",
    apis.kSE05x_CryptoObject_DES_CBC_PKCS5: "DES_CBC_PKCS5",
    apis.kSE05x_CryptoObject_DES_ECB_NOPAD: "DES_ECB_NOPAD",
    apis.kSE05x_CryptoObject_DES_ECB_ISO9797_M1: "DES_ECB_ISO9797_M1",
    apis.kSE05x_CryptoObject_DES_ECB_ISO9797_M2: "DES_ECB_ISO9797_M2",
    apis.kSE05x_CryptoObject_DES_ECB_PKCS5: "DES_ECB_PKCS5",
    apis.kSE05x_CryptoObject_AES_ECB_NOPAD: "AES_ECB_NOPAD",
    apis.kSE05x_CryptoObject_AES_CBC_NOPAD: "AES_CBC_NOPAD",
    apis.kSE05x_CryptoObject_AES_CBC_ISO9797_M1: "AES_CBC_ISO9797_M1",
    apis.kSE05x_CryptoObject_AES_CBC_ISO9797_M2: "AES_CBC_ISO9797_M2",
    apis.kSE05x_CryptoObject_AES_CBC_PKCS5: "AES_CBC_PKCS5",
    apis.kSE05x_CryptoObject_AES_CTR: "AES_CTR",
    apis.kSE05x_CryptoObject_HMAC_SHA1: "HMAC_SHA1",
    apis.kSE05x_CryptoObject_HMAC_SHA256: "HMAC_SHA256",
    apis.kSE05x_CryptoObject_HMAC_SHA384: "HMAC_SHA384",
    apis.kSE05x_CryptoObject_HMAC_SHA512: "HMAC_SHA512",
    apis.kSE05x_CryptoObject_CMAC_128: "CMAC_128",
}


class ReadIDList:  # pylint: disable=too-few-public-methods
    """
    Retrieve index list
    """

    def __init__(self, session_obj):
        """
        Constructor
        :param session_obj: Instance of session
        """
        self._session = session_obj
        self._ctx_ks = KeyStore(self._session)
        self._ctx_key = KeyObject(self._ctx_ks)

    def do_read_id_list(self):  # pylint: disable=too-many-locals, too-few-public-methods
        """
        Retrieve index list from secure element and print on console
        :return: Status
        """
        output_offset = 0
        filter_data = 0xFF
        p_more = apis.kSE05x_MoreIndicator_NA
        p_more = (ctypes.c_uint8 * 1)(p_more)
        data_list_len = 1024
        data_raw = (ctypes.c_uint8 * data_list_len)(0)
        data_list_len = ctypes.c_size_t(data_list_len)
        status = apis.Se05x_API_ReadIDList(ctypes.byref(self._session.session_ctx.s_ctx),
                                           output_offset, filter_data,
                                           ctypes.byref(p_more),
                                           data_raw, ctypes.pointer(data_list_len))
        if status != apis.kSE05x_SW12_NO_ERROR:
            log.error("Se05x_API_ReadIDList failed")
            return status
        data_full_list = list(data_raw)
        data_list = data_full_list[:int(data_list_len.value)]

        key_object = apis.sss_object_t()

        status = apis.sss_key_object_init(ctypes.byref(
            key_object), ctypes.byref(self._ctx_ks.keystore))
        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_object_init failed")
            return status

        j = 0
        id_dict = {}
        for i in range(int(len(data_list) / 4)):  # pylint: disable=unused-variable
            obj_id = data_list[j] << (3 * 8) | data_list[j + 1] << (2 * 8) | \
                     data_list[j + 2] << (1 * 8) | data_list[j + 3]
            status = apis.sss_key_object_get_handle(ctypes.byref(key_object), obj_id)
            cipher_type = None
            if status != apis.kStatus_SSS_Success:
                cipher_type = "No Info available"
                object_type = ""
            else:
                cipher_type = CIPHER_TYPE_DICTIONARY[key_object.cipherType]
                object_type = KEY_PART_DICTIONARY[key_object.objectType]

            key_size = 0
            key_size = ctypes.c_size_t(key_size)
            str_id_list = "Key-Id: 0X%-10x %-17s %-15s" \
                          % (obj_id,
                             cipher_type,
                             object_type)
            if key_object.cipherType != 70:
                if key_object.cipherType in [apis.kSSS_CipherType_EC_MONTGOMERY,
                                             apis.kSSS_CipherType_EC_TWISTED_ED]:
                    key_len = 32
                else:
                    status = apis.Se05x_API_ReadSize(ctypes.byref(self._session.session_ctx.s_ctx),
                                                     obj_id,
                                                     ctypes.pointer(key_size))
                    if status != apis.kSE05x_SW12_NO_ERROR:
                        key_len = "No Info available"
                    else:
                        key_len = (int(key_size.value) * 8)

                str_id_list += "Size(Bits): %s" % key_len
            id_dict[obj_id] = str_id_list
            j += 4

        for i in sorted (id_dict.keys()):
            print(id_dict[i])
        print("")
        crypto_obj_dict = {}
        obj_list_len = 1024
        obj_list_ctype = (ctypes.c_uint8 * obj_list_len)(0)
        obj_list_len = ctypes.c_size_t(obj_list_len)
        status = apis.Se05x_API_ReadCryptoObjectList(ctypes.byref(self._session.session_ctx.s_ctx),
                                                     obj_list_ctype, ctypes.pointer(obj_list_len))
        if status != apis.kSE05x_SW12_NO_ERROR:
            log.error("Se05x_API_ReadCryptoObjectList failed")
            return status
        obj_full_list = list(obj_list_ctype)
        obj_list = obj_full_list[:int(obj_list_len.value)]

        j = 0
        for i in range(int(len(obj_list) / 4)):
            obj_id = obj_list[j + 1] | obj_list[j + 0] << 8
            crypto_obj_dict[obj_id] = "CryptoObject-Id: 0X%-10x    Type: %-15s"% (obj_id, CRYPTO_OBJID_DICTIONARY[obj_id])


        for i in sorted (crypto_obj_dict.keys()):
            print(crypto_obj_dict[i])
        return status
