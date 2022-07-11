#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import ctypes
import logging
from .keystore import KeyStore
from .keyobject import KeyObject
from . import sss_api as apis
from .util import save_to_file

log = logging.getLogger(__name__)


class Get:  # pylint: disable=too-few-public-methods
    """
    Retrieve key operation
    """

    def __init__(self, session_obj):
        """
        Constructor
        :param session_obj: Instance of session
        """
        self._session = session_obj
        self.key = None
        self.curve_id = 0
        # key size to support long length
        self.key_size = 20000
        self.key_type = None
        self.ctx_ks = KeyStore(self._session)
        self.ctx_key = KeyObject(self.ctx_ks)
        self.cipher_type = 0

    def get_handle(self, key_id):
        status, self.key_type, self.cipher_type = self.ctx_key.get_handle(key_id)  # pylint: disable=unused-variable
        return status

    # AUTOPI
    # Method changed to return 
    def get_key(self, key_id, file_name=None, encode_format=""):
        """
        Retrieve public key or certificate
        :param key_id: Key index
        :param file_name: File name to store key or certificate
        :param encode_format: Encode format to store key
        :return: Status
        """
        status = self.get_handle(key_id)

        if status != apis.kStatus_SSS_Success:
            return status

        if self.key_type is None:
            log.error("Received object type is None")
            return apis.kStatus_SSS_Fail

        if self._session.subsystem == apis.kType_SSS_SE_SE05x:
            self.curve_id = self.ctx_key.keyobject.curve_id
        else:
            self.curve_id = 0

        data_len = int(self.key_size / 8)
        key = (ctypes.c_uint8 * data_len)(0)
        data_len_ctype = ctypes.c_size_t(data_len)
        key_size_ctype = ctypes.c_size_t(self.key_size)
        status = self.ctx_ks.get_key(self.ctx_key, key, data_len_ctype, key_size_ctype)
        key_list = list(key)
        self.key = key_list[:int(data_len_ctype.value)]
        self.key_size = data_len_ctype.value * 8

        if file_name is not None and status == apis.kStatus_SSS_Success:
            status = save_to_file(self.key, file_name, self.key_type, encode_format, self.cipher_type)
        # elif file_name is None and status == apis.kStatus_SSS_Success:
        #     return self.key
        return status


    def get_key_attest(self, key_id, attestation_key, random_data, algorithm, attst_data, file_name=None, encode_format=""):
        """
        Retrieve public key or certificate
        :param key_id: Key index
        :param file_name: File name to store key or certificate
        :param encode_format: Encode format to store key
        :return: Status
        """
        status = self.get_handle(key_id)

        if status != apis.kStatus_SSS_Success:
            return status

        if self.key_type is None:
            log.error("Received object type is None")
            return apis.kStatus_SSS_Fail

        if self._session.subsystem == apis.kType_SSS_SE_SE05x:
            self.curve_id = self.ctx_key.keyobject.curve_id
        else:
            self.curve_id = 0

        data_len = int(self.key_size / 8)
        key = (ctypes.c_uint8 * data_len)(0)
        data_len_ctype = ctypes.c_size_t(data_len)
        key_size_ctype = ctypes.c_size_t(self.key_size)

        random_c = (ctypes.c_uint8 * len(random_data))(*random_data)

        status = self.ctx_ks.get_key_attest(self.ctx_key, key, data_len_ctype, key_size_ctype, attestation_key, algorithm, random_c, len(random_data), attst_data)
        key_list = list(key)
        self.key = key_list[:int(data_len_ctype.value)]
        self.key_size = data_len_ctype.value * 8


        if file_name is not None and status == apis.kStatus_SSS_Success:
            status = save_to_file(self.key, file_name, self.key_type, encode_format, self.cipher_type)
        return status
