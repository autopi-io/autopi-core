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
import random
from . import sss_api as apis
from .keystore import KeyStore
from .keyobject import KeyObject
# from .util import file_write, transform_int_list_to_hex_str

log = logging.getLogger(__name__)


class TLS:
    """
    Encrypt and Decypt operation
    """

    def __init__(self, session_obj):
        """
        constructor
        :param session_obj: Instance of session
        """
        self._ctx_ks = KeyStore(session_obj)
        self._ctx_key = KeyObject(self._ctx_ks)
        self._session = session_obj.session_ctx
        self.shared_secret = None
        self.shared_secret_len = 0
        self.client_rand_val = list()
        self.client_rand_val_len = 32
        self.server_rand_val_len = 32
        randomizer = random.SystemRandom()
        self.server_rand_val = list()
        for i in range(self.server_rand_val_len):
            self.server_rand_val.append(randomizer.randint(0x00, 0xFF))
        self.digest_mode = apis.kSE05x_DigestMode_SHA256
        self.tls_str = "master secret"
        self.req_len = 48
        self.destination_buf_len = 48
        self.destination_buf = list()
        for i in range(self.client_rand_val_len):
            self.client_rand_val.append(0)
        for i in range(self.destination_buf_len):
            self.destination_buf.append(0)


    def do_calculate_shared_secret(self, key_id, prv_key_id, psk_key_id):
        """
        Perform decryption
        :param key_id: Key Index
        :param prv_key_id: Key Index of private key
        :return: Status
        """
        if self.shared_secret is not None and isinstance(self.shared_secret, list):
            shared_secret_ctype = ctypes.byref((ctypes.c_uint8 * self.shared_secret_len)(*self.shared_secret))
        else:
            shared_secret_ctype = self.shared_secret
        status = apis.Se05x_API_TLSCalculatePreMasterSecret(ctypes.byref(self._session.s_ctx),
            prv_key_id, psk_key_id, key_id, shared_secret_ctype, self.shared_secret_len)

        if status == apis.kSE05x_SW12_NO_ERROR:
            status = apis.kStatus_SSS_Success
        else:
            status = apis.kStatus_SSS_Fail
        return status

    def do_tls_perform_prf(self, key_id):


        # if isinstance(self.client_rand_val, list):
        if self.client_rand_val is not None:
            client_rand_val_ctype = ctypes.byref((ctypes.c_uint8 * self.client_rand_val_len)(*self.client_rand_val))
        else:
            client_rand_val_ctype = self.client_rand_val

        status = apis.Se05x_API_TLSGenerateRandom(ctypes.byref(self._session.s_ctx), client_rand_val_ctype, ctypes.byref(ctypes.c_size_t(self.client_rand_val_len)))

        if status != apis.kSE05x_SW12_NO_ERROR:
            return apis.kStatus_SSS_Fail

        self.tls_str_ctypes = ctypes.create_string_buffer(len(self.tls_str))
        self.tls_str_ctypes.value = str.encode(self.tls_str)

        # if self.server_rand_val is not None and isinstance(self.server_rand_val, list):
        server_rand_val_ctype = ctypes.byref((ctypes.c_uint8 * self.server_rand_val_len)(*self.server_rand_val))
        # else:
        #     server_rand_val_ctype = self.server_rand_val

        destination_buf_ctype = (ctypes.c_uint8 * self.destination_buf_len)(*self.destination_buf)

        if self.tls_str == "master secret":
            prf_type = apis.kSE05x_TLS_PRF_CLI_HELLO
        elif self.tls_str == "key expansion":
            prf_type = apis.kSE05x_TLS_PRF_CLI_RND
        status = apis.Se05x_API_TLSPerformPRF(ctypes.byref(self._session.s_ctx),
            key_id,
            self.digest_mode,
            ctypes.byref(self.tls_str_ctypes),
            len(self.tls_str),
            server_rand_val_ctype,
            self.server_rand_val_len,
            self.req_len,
            ctypes.byref(destination_buf_ctype),
            ctypes.byref(ctypes.c_size_t(self.destination_buf_len)),
            prf_type)

        if status == apis.kSE05x_SW12_NO_ERROR:
            status = apis.kStatus_SSS_Success
        else:
            status = apis.kStatus_SSS_Fail

        return status