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
from .util import status_to_str
from .keystore import KeyStore
from .keyobject import KeyObject


log = logging.getLogger(__name__)


class Symmetric:
    """
    SSS Symmetric commands
    """

    def __init__(self, session_obj):
        """
        Constructor performs asymmetric init
        :param session_obj: Instance of session
        :param keyobj: Instance of key object
        :param algorithm: Hash algorithm. eg: SHA 256
        :param mode: Operation mode. eg: sign, verify, encrypt, decrypt
        """
        self._session   = session_obj
        self._ctx_ks = KeyStore(self._session)
        self._ctx_key = KeyObject(self._ctx_ks)
        self._symmctx   = apis.sss_symmetric_t()
        self.algorithm  =  apis.kAlgorithm_SSS_HMAC_SHA512
        self.mode       = apis.kMode_SSS_Mac
        self.mac_ctx    = apis.sss_mac_t()
        self.out_data = None
        self.out_data_size = 0
        self.block_size = 55

        #AEAD
        self.nonce_len = 0
        self.aad_len = 0
        self.tag_len = 0
        self.aead_ctx = apis.sss_aead_t()
        self.iv = None
        self.iv_len = 0
        self.tag = None
        self.aad = None
        self.nonce = None


    def mac_multi_step(self, key_obj, src_data, src_data_len, dest_data=None, dest_data_len=None):

        status = apis.sss_mac_context_init(ctypes.byref(self.mac_ctx), ctypes.byref(self._session.session_ctx),
            ctypes.byref(key_obj.keyobject), self.algorithm, self.mode)

        if status != apis.kStatus_SSS_Success:
            log.error("sss_mac_context_init %s", status_to_str(apis.kStatus_SSS_Fail))
            return status

        status = apis.sss_mac_init(ctypes.byref(self.mac_ctx))
        if status != apis.kStatus_SSS_Success:
            log.error("sss_mac_init %s", status_to_str(apis.kStatus_SSS_Fail))
            return status

        status = apis.sss_mac_update(ctypes.byref(self.mac_ctx), ctypes.byref(src_data), src_data_len)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_mac_update %s", status_to_str(apis.kStatus_SSS_Fail))
            return status

        if dest_data is None:
            dest_data_len = 1000
            dest_ctype = (ctypes.c_uint8 * dest_data_len)(0)
            dest_len_ctype = ctypes.c_size_t(dest_data_len)
            dest_ctype_byref = ctypes.byref(dest_ctype)
            status = apis.sss_mac_finish(ctypes.byref(self.mac_ctx), ctypes.byref(dest_ctype), ctypes.byref(dest_len_ctype))
            if status != apis.kStatus_SSS_Success:
                log.error("sss_mac_finish %s", status_to_str(apis.kStatus_SSS_Fail))
                return status

            self.out_data = dest_ctype
            self.out_data_size = dest_len_ctype

        else:
            status = apis.sss_mac_finish(ctypes.byref(self.mac_ctx), dest_data, ctypes.byref(dest_data_len))
            if status != apis.kStatus_SSS_Success:
                log.error("sss_mac_finish %s", status_to_str(apis.kStatus_SSS_Fail))
                return status

        return status

    def mac_one_go(self, key_obj, src_data, src_data_len):
        status = apis.sss_mac_context_init(ctypes.byref(self.mac_ctx), ctypes.byref(self._session.session_ctx),
            ctypes.byref(key_obj.keyobject), self.algorithm, self.mode)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_mac_context_init %s", status_to_str(apis.kStatus_SSS_Fail))
            return status

        out_data_len = 1000
        out_ctype = (ctypes.c_uint8 * out_data_len)(0)
        out_len_ctype = ctypes.c_size_t(out_data_len)

        status = apis.sss_mac_one_go(ctypes.byref(self.mac_ctx), src_data,
         src_data_len, ctypes.byref(out_ctype), ctypes.byref(out_len_ctype))
        if status != apis.kStatus_SSS_Success:
            log.error("sss_mac_one_go %s", status_to_str(apis.kStatus_SSS_Fail))
            return status
        self.out_data = out_ctype
        self.out_data_size = out_len_ctype
        return status

    def mac_validate_one_go(self, key_obj, src_data, src_data_len, dest_data, dest_data_len):
        status = apis.sss_mac_context_init(ctypes.byref(self.mac_ctx), ctypes.byref(self._session.session_ctx),
            ctypes.byref(key_obj.keyobject), self.algorithm, self.mode)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_mac_context_init %s", status_to_str(apis.kStatus_SSS_Fail))
            return status

        status = apis.sss_se05x_mac_validate_one_go(ctypes.byref(self.mac_ctx), src_data,
        src_data_len, dest_data, dest_data_len)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_se05x_mac_validate_one_go %s", status_to_str(apis.kStatus_SSS_Fail))

        return status

    def cipher_init(self, key_obj, src_data):
        status = apis.sss_symmetric_context_init(ctypes.byref(self._symmctx), ctypes.byref(self._session.session_ctx),
            ctypes.byref(key_obj.keyobject), self.algorithm, self.mode);
        if status != apis.kStatus_SSS_Success:
            log.error("sss_symmetric_context_init %s", status_to_str(apis.kStatus_SSS_Fail))
            return status

        if self.iv is not None:
            self.iv_len = len(self.iv)
            iv_ctype = ctypes.byref((ctypes.c_ubyte * self.iv_len)(*self.iv))
        else:
            iv_ctype = None

        status = apis.sss_cipher_init(ctypes.byref(self._symmctx), iv_ctype, self.iv_len)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_cipher_init %s", status_to_str(apis.kStatus_SSS_Fail))
            return status

        dest_data_list = list()
        for i in range(len(src_data)):
            if i + self.block_size > len(src_data):
                temp_data_len = len(src_data) - i
            else:
                temp_data_len = self.block_size
            temp_out_buf_en = temp_data_len + 16

            src_data_list = src_data[i:temp_data_len+i]
            src_data_ctype = (ctypes.c_ubyte * temp_data_len)(*src_data_list)


            dest_ctype = (ctypes.c_ubyte * temp_out_buf_en)(0)
            temp_buf_len_ctype = ctypes.c_size_t(temp_out_buf_en)

            status = apis.sss_cipher_update(ctypes.byref(self._symmctx), src_data_ctype,
                temp_data_len, ctypes.byref(dest_ctype), ctypes.byref(temp_buf_len_ctype))

            if status != apis.kStatus_SSS_Success:
                log.error("sss_cipher_update %s", status_to_str(apis.kStatus_SSS_Fail))
                return status
            temp_out_buf_en = temp_buf_len_ctype.value
            dest_data_list += list(dest_ctype)[:temp_buf_len_ctype.value]
            if i + self.block_size > len(src_data):
                break
            i = i + self.block_size

        temp_out_buf_en = self.block_size + 16;
        dest_ctype = (ctypes.c_ubyte * temp_out_buf_en)(0)
        temp_buf_len_ctype = ctypes.c_size_t(temp_out_buf_en)

        status = apis.sss_cipher_finish(ctypes.byref(self._symmctx), None, 0,
            ctypes.byref(dest_ctype), ctypes.byref(temp_buf_len_ctype))
        if status != apis.kStatus_SSS_Success:
            log.error("sss_cipher_finish %s", status_to_str(apis.kStatus_SSS_Fail))
            return status

        dest_data_list += list(dest_ctype)[:temp_buf_len_ctype.value]

        self.out_data = (ctypes.c_ubyte * len(dest_data_list))(*dest_data_list)
        self.out_data_size = len(dest_data_list)

        return status

    def cipher_one_shot(self, key_obj, src_data):

        status = apis.sss_symmetric_context_init(ctypes.byref(self._symmctx), ctypes.byref(self._session.session_ctx),
            ctypes.byref(key_obj.keyobject), self.algorithm, self.mode);
        if status != apis.kStatus_SSS_Success:
            log.error("sss_symmetric_context_init %s", status_to_str(apis.kStatus_SSS_Fail))
            return status

        if self.iv is not None:
            self.iv_len = len(self.iv)
            iv_ctype = ctypes.byref((ctypes.c_ubyte * self.iv_len)(*self.iv))
        else:
            iv_ctype = None

        src_data_ctype = (ctypes.c_ubyte * len(src_data))(*src_data)
        dest_data_ctype = (ctypes.c_ubyte * len(src_data))(0)
        dest_data_len = len(src_data)
        status = apis.sss_cipher_one_go(ctypes.byref(self._symmctx), iv_ctype, self.iv_len,
            ctypes.byref(src_data_ctype), ctypes.byref(dest_data_ctype), dest_data_len)

        if status != apis.kStatus_SSS_Success:
            log.error("sss_cipher_one_go %s", status_to_str(apis.kStatus_SSS_Fail))
            return status

        self.out_data = dest_data_ctype
        self.out_data_size = dest_data_len
        return status

    def aead_init(self, key_obj, src_data, tag, tag_len):

        if self.nonce is not None:
            self.nonce_len = len(self.nonce)
            nonce_ctype = ctypes.byref((ctypes.c_ubyte * self.nonce_len)(*self.nonce))
        else:
            nonce_ctype = None
            self.nonce_len = 0

        if self.aad is not None:
            self.aad_len = len(self.aad)
            aad_ctype = ctypes.byref((ctypes.c_ubyte * self.aad_len)(*self.aad))
        else:
            aad_ctype = None
            self.aad_len = 0

        if tag is not None:
            tag_ctype = (ctypes.c_ubyte * tag_len)(*tag)
        elif tag_len != 0:
            tag_ctype = (ctypes.c_ubyte * tag_len)(0)
        else:
            log.error("tag or tag_len required")
            return apis.kStatus_SSS_Fail

        tag_len_ctype = ctypes.c_size_t(tag_len)

        status = apis.sss_aead_context_init(ctypes.byref(self.aead_ctx), ctypes.byref(self._session.session_ctx),
            ctypes.byref(key_obj.keyobject), self.algorithm, self.mode)

        if status != apis.kStatus_SSS_Success:
            log.error("sss_aead_context_init %s", status_to_str(apis.kStatus_SSS_Fail))
            return status

        src_data_ctype = (ctypes.c_ubyte * len(src_data))(*src_data)
        dest_data_ctype = (ctypes.c_ubyte * len(src_data))(0)
        dest_data_len = len(src_data)

        status = apis.sss_aead_init(ctypes.byref(self.aead_ctx), nonce_ctype,
            self.nonce_len, tag_len, self.aad_len, len(src_data))
        if status != apis.kStatus_SSS_Success:
            log.error("sss_aead_init %s", status_to_str(apis.kStatus_SSS_Fail))
            return status

        status = apis.sss_aead_update_aad(ctypes.byref(self.aead_ctx), aad_ctype, self.aad_len)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_aead_init %s", status_to_str(apis.kStatus_SSS_Fail))
            return status

        dest_data_list = list()
        for i in range(len(src_data)):
            if i + self.block_size > len(src_data):
                temp_data_len = len(src_data) - i
            else:
                temp_data_len = self.block_size
            temp_out_buf_en = temp_data_len + 16

            src_data_list = src_data[i:temp_data_len+i]
            src_data_ctype = (ctypes.c_ubyte * temp_data_len)(*src_data_list)


            dest_ctype = (ctypes.c_ubyte * temp_out_buf_en)(0)
            temp_buf_len_ctype = ctypes.c_size_t(temp_out_buf_en)

            status = apis.sss_aead_update(ctypes.byref(self.aead_ctx), ctypes.byref(src_data_ctype),
                temp_data_len, ctypes.byref(dest_ctype), ctypes.byref(temp_buf_len_ctype))
            if status != apis.kStatus_SSS_Success:
                log.error("sss_aead_update %s", status_to_str(apis.kStatus_SSS_Fail))
                return status

            temp_out_buf_en = temp_buf_len_ctype.value
            dest_data_list += list(dest_ctype)[:temp_buf_len_ctype.value]
            if i + self.block_size > len(src_data):
                break
            i = i + self.block_size

        temp_out_buf_en = self.block_size + 16;
        dest_ctype = (ctypes.c_ubyte * temp_out_buf_en)(0)
        temp_buf_len_ctype = ctypes.c_size_t(temp_out_buf_en)

        status = apis.sss_aead_finish(ctypes.byref(self.aead_ctx), None, 0,
            ctypes.byref(dest_ctype), ctypes.byref(temp_buf_len_ctype),
            ctypes.byref(tag_ctype), ctypes.byref(tag_len_ctype))
        if status != apis.kStatus_SSS_Success:
            log.error("sss_aead_finish %s", status_to_str(apis.kStatus_SSS_Fail))

        dest_data_list += list(dest_ctype)[:temp_buf_len_ctype.value]

        self.out_data = (ctypes.c_ubyte * len(dest_data_list))(*dest_data_list)
        self.out_data_size = len(dest_data_list)
        self.tag = list(tag_ctype)[:tag_len_ctype.value]
        return status

    def aead_one_shot(self, key_obj, src_data, tag, tag_len):

        if self.nonce is not None:
            self.nonce_len = len(self.nonce)
            nonce_ctype = ctypes.byref((ctypes.c_ubyte * self.nonce_len)(*self.nonce))
        else:
            nonce_ctype = None
            self.nonce_len = 0

        if self.aad is not None:
            self.aad_len = len(self.aad)
            aad_ctype = ctypes.byref((ctypes.c_ubyte * self.aad_len)(*self.aad))
        else:
            aad_ctype = None
            self.aad_len = 0

        if tag is not None:
            tag_ctype = (ctypes.c_ubyte * tag_len)(*tag)
        elif tag_len != 0:
            tag_ctype = (ctypes.c_ubyte * tag_len)(0)
        else:
            log.error("tag or tag_len required")
            return apis.kStatus_SSS_Fail

        tag_len_ctype = ctypes.c_size_t(tag_len)

        status = apis.sss_aead_context_init(ctypes.byref(self.aead_ctx), ctypes.byref(self._session.session_ctx),
            ctypes.byref(key_obj.keyobject), self.algorithm, self.mode)

        if status != apis.kStatus_SSS_Success:
            log.error("sss_aead_context_init %s", status_to_str(apis.kStatus_SSS_Fail))
            return status

        src_data_ctype = (ctypes.c_ubyte * len(src_data))(*src_data)
        dest_data_ctype = (ctypes.c_ubyte * len(src_data))(0)
        dest_data_len = len(src_data)

        status = apis.sss_aead_one_go(ctypes.byref(self.aead_ctx), ctypes.byref(src_data_ctype), ctypes.byref(dest_data_ctype),
            dest_data_len, nonce_ctype, self.nonce_len, aad_ctype, self.aad_len, ctypes.byref(tag_ctype), ctypes.byref(tag_len_ctype))

        if status != apis.kStatus_SSS_Success:
            log.error("sss_aead_one_go %s", status_to_str(apis.kStatus_SSS_Fail))
            return status
        self.out_data = dest_data_ctype
        self.out_data_size = dest_data_len
        self.tag = list(tag_ctype)[:tag_len_ctype.value]

        return status
