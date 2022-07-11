#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import ctypes
import logging
from . import sss_api as apis
from .util import hex_uid

log = logging.getLogger(__name__)


class A71CH:
    """
    A71CH Specifc commands
    """

    def __init__(self, session_obj):
        """
        Constructor
        :param session_obj: Instance of session
        """
        self._session = session_obj

    def debug_reset(self):
        """
        A71CH Debug Reset
        :return: None
        """
        if self._session.subsystem == apis.kType_SSS_SE_A71CH:
            apis.HLSE_DbgReset()
        else:
            log.warning("Unsupported subsystem='%s'", (self._session.subsystem,))

    def get_unique_id(self):
        """
        Retrieve A71CH unique id in hex format
        :return:  unique id
        """
        unique_id_len = ctypes.c_uint16(10)
        unique_id = (ctypes.c_uint8 * unique_id_len.value)(0)

        if self._session.subsystem == apis.kType_SSS_SE_A71CH:
            apis.A71_GetCertUid(ctypes.byref(unique_id), ctypes.byref(unique_id_len))
        log.info(hex_uid(unique_id))
        return hex_uid(unique_id)
