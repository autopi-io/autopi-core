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


class Se05x:
    """
    Se05x specific operation
    """

    def __init__(self, session_obj):
        """
        Constructor
        :param session_obj: Instance of session
        """
        self._session = session_obj
        self.rng_data = 0

    def debug_reset(self):
        """
        Se05x Debug reset
        :return: None
        """
        if self._session.subsystem == apis.kType_SSS_SE_SE05x:
            apis.Se05x_API_DeleteAll_Iterative(ctypes.byref(self._session.session_ctx.s_ctx))
        else:
            log.warning("Unsupported subsystem='%s'", (self._session.subsystem,))

    def get_unique_id(self):
        """
        Retrieve 18 byte unique id
        :return: Unique id
        """
        unique_id_len = ctypes.c_uint16(18)
        unique_id = (ctypes.c_uint8 * unique_id_len.value)(0)

        if self._session.subsystem == apis.kType_SSS_SE_SE05x:
            apis.sss_session_prop_get_au8(ctypes.byref(self._session.session_ctx),
                                          apis.kSSS_SessionProp_UID,
                                          ctypes.byref(unique_id),
                                          ctypes.byref(unique_id_len))
        log.info(hex_uid(unique_id))
        return hex_uid(unique_id)

    def get_cert_unique_id(self):
        """
        Retrieve cert unique id
        :return: Cert unique id
        """
        unique_id_len = ctypes.c_uint16(10)
        unique_id = (ctypes.c_uint8 * unique_id_len.value)(0)

        if self._session.subsystem == apis.kType_SSS_SE_SE05x:
            apis.sss_session_prop_get_au8(ctypes.byref(self._session.session_ctx),
                                          apis.kSSS_SE05x_SessionProp_CertUID,
                                          ctypes.byref(unique_id),
                                          ctypes.byref(unique_id_len))
        log.info(hex_uid(unique_id))
        return hex_uid(unique_id)

    def get_applet_version(self):
        """
        Retrieve applet version
        :return: applet version
        """
        applet_ver_len = ctypes.c_size_t(7)
        applet_ver = (ctypes.c_uint8 * applet_ver_len.value)(0)

        status = apis.Se05x_API_GetVersion(ctypes.byref(self._session.session_ctx.s_ctx),
                                           ctypes.byref(applet_ver),
                                           ctypes.byref(applet_ver_len))

        if status != apis.kSE05x_SW12_NO_ERROR:
            log.error("Se05x_API_GetVersion failed")
            return 0

        app_ver_str = hex_uid(applet_ver)[:4]
        hex_appletver = int(app_ver_str, 16)
        print('Applet_Version: %s'%app_ver_str)
        return hex_appletver

    def get_random_number(self):
        """
        Retrieve 10 bytes random number
        :return: random number
        """
        self._rng_ctx = apis.sss_rng_context_t()
        rng_data_len = ctypes.c_size_t(10)
        rngdata = (ctypes.c_uint8 * rng_data_len .value)(0)
        status = apis.sss_rng_context_init(ctypes.byref(self._rng_ctx),
                                           ctypes.byref(self._session.session_ctx)
                                           )

        if status != apis.kStatus_SSS_Success:
            log.error('sss_rng_context_init failed')
            self._rng_ctx = None
            return

        status = apis.sss_rng_get_random(ctypes.byref(self._rng_ctx),
                                         ctypes.byref(rngdata),
                                         rng_data_len
                                         )

        if status != apis.kStatus_SSS_Success:
            log.error('sss_rng_get_random failed')
            self._rng_ctx = None
            return

        status = apis.sss_rng_context_free(ctypes.byref(self._rng_ctx))

        log.info(hex_uid(rngdata))
        self.rng_data = hex_uid(rngdata)
        return hex_uid(rngdata)