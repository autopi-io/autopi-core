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


class PCR:  # pylint: disable=too-few-public-methods
    """
    PCR Operation
    """

    def __init__(self, session_obj):
        """
        Constructor
        :param session_obj: Instance of session
        """
        self._session = session_obj
        self._ctx_ks = KeyStore(self._session)
        self._ctx_key = KeyObject(self._ctx_ks)
        self.key_type = apis.kSSS_KeyPart_Default
        self.cypher_type = apis.kSSS_CipherType_PCR

    def do_write_pcr(self, key_id, pcr_value_init, pcr_value_update, policy=None):
        """
        Write PCR
        :param key_id: Key index
        :param pcr_value_init: PCR initial value
        :param pcr_value_update: PCR Updated value
        :param policy: Policy to be applied
        :return: Status
        """

        if pcr_value_init is not None:
            pcr_int_data_len = len(pcr_value_init)
        else:
            pcr_value_init = []
            pcr_int_data_len = 0
        pcr_value_init_ctype = (ctypes.c_uint8 * pcr_int_data_len)(*pcr_value_init)

        if pcr_value_update is not None:
            pcr_update_data_len = len(pcr_value_update)
        else:
            pcr_update_data_len = 0
            pcr_value_update = []
        pcr_value_update_ctype = (ctypes.c_uint8 * pcr_update_data_len)(*pcr_value_update)
        pcr_update_data_len_ctype = ctypes.c_size_t(pcr_update_data_len)

        if pcr_int_data_len != 0:
            status = self._ctx_key.allocate_handle(key_id, self.key_type,
                                                   self.cypher_type, pcr_int_data_len,
                                                   apis.kKeyObject_Mode_None)
            if status != apis.kStatus_SSS_Success:
                return status

        status = apis.Se05x_API_WritePCR_WithType(ctypes.byref(self._session.session_ctx.s_ctx),
                                         apis.kSE05x_INS_NA,
                                         policy, key_id,
                                         ctypes.byref(pcr_value_init_ctype),
                                         pcr_int_data_len,
                                         ctypes.byref(pcr_value_update_ctype),
                                         pcr_update_data_len_ctype)
        if status == apis.kSE05x_SW12_NO_ERROR:
            status = apis.kStatus_SSS_Success
        else:
            status = apis.kStatus_SSS_Fail

        return status
