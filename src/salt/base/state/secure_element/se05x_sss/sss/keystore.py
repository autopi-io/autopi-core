#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import ctypes
import logging
from .util import status_to_str
from .session import Session
from . import sss_api as apis
from .keyobject import KeyObject
log = logging.getLogger(__name__)


class KeyStore:
    """
    Key Store operation
    """

    # session is instance of Session
    def __init__(self, session_obj):
        """
        Key store context initialization
        :param session_obj: Instance of Session
        """
        if not isinstance(session_obj, Session):
            log.error("%s must be instance of Session", str(session_obj))
            self.keystore = None
            return

        self.keystore = apis.sss_key_store_t()
        self.session = session_obj.session_ctx
        self._keystore_id = ctypes.c_uint32(155)

        if self.session is None:
            self.keystore = None
            return

        status = apis.sss_key_store_context_init(
            ctypes.byref(self.keystore), ctypes.byref(self.session))
        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_store_context_init %s", status_to_str(status))
            self.keystore = None
            return
        log.debug("sss_key_store_context_init %s", status_to_str(status))

        if session_obj.subsystem == apis.kType_SSS_SE_A71CH:
            self._sscp_session = apis.sss_sscp_session_t()
            status = apis.sscp_a71ch_init(
                ctypes.byref(self._sscp_session), ctypes.byref(self.keystore))
            if status != apis.kStatus_SSS_Success:
                log.error("sscp_a71ch_init %s", (status_to_str(status)))
                self.keystore = None
                return
            log.debug("sscp_a71ch_init %s", (status_to_str(status)))

        status = apis.sss_key_store_allocate(ctypes.byref(self.keystore),
                                             self._keystore_id)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_store_allocate %s", status_to_str(status))
            self.keystore = None
            return
        log.debug("sss_key_store_allocate %s", status_to_str(status))

    def set_key(self, key_object, data, data_len, key_bit_len, opt, opt_len):  # pylint: disable=too-many-arguments
        """
        Inject key or certificate
        :param key_object: Instance of key object
        :param data: Value to inject
        :param data_len: Length of the value
        :param key_bit_len: Key bit length
        :param opt: Option. Eg: Policy
        :param opt_len: Option length
        :return: Status
        """
        if not isinstance(key_object, KeyObject):
            log.error("%s must be an instance of KeyObject", str(key_object))
            return apis.kStatus_SSS_Fail

        if key_object.keyobject is None:
            log.error("set_key %s", status_to_str(apis.kStatus_SSS_Fail))
            return apis.kStatus_SSS_Fail

        status = apis.sss_key_store_set_key(
            ctypes.byref(self.keystore),
            ctypes.byref(key_object.keyobject),
            ctypes.byref(data),
            data_len, key_bit_len, opt, opt_len)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_store_set_key %s", status_to_str(status))
            return status
        log.debug("sss_key_store_set_key %s", status_to_str(status))
        return status

    def save_key_store(self):
        """
        Save key store
        :return: Status
        """
        if self.keystore is None:
            log.error("save_key_store %s", status_to_str(apis.kStatus_SSS_Fail))
            return status_to_str(apis.kStatus_SSS_Fail)
        status = apis.sss_key_store_save(ctypes.byref(self.keystore))
        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_store_save %s", status_to_str(status))
            return status_to_str(status)
        log.debug("sss_key_store_save %s", status_to_str(status))
        return status

    def open_key(self, key_object):

        if key_object is None:
            key_c_type = None
        else:
            if not isinstance(key_object, KeyObject):
                log.error("%s must be an instance of KeyObject", str(key_object))
                return apis.kStatus_SSS_Fail
            key_c_type = ctypes.byref(key_object.keyobject)
        status = apis.sss_key_store_open_key(ctypes.byref(self.keystore), key_c_type)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_store_open_key %s", status_to_str(status))
            return status

        log.debug("sss_key_store_open_key %s", status_to_str(status))
        return status

    def generate_key(self, key_object, key_len, opt):
        """
        Generate ECC or RSA key
        :param key_object: Instance of key object
        :param key_len: Key length to generate
        :param opt: Options to set. Eg: Policy
        :return: Status
        """
        if not isinstance(key_object, KeyObject):
            log.error("%s must be an instance of KeyObject", str(key_object))
            return apis.kStatus_SSS_Fail

        if key_object.keyobject is None:
            log.error("generate_key %s", status_to_str(apis.kStatus_SSS_Fail))
            return apis.kStatus_SSS_Fail

        status = apis.sss_key_store_generate_key(
            ctypes.byref(self.keystore), ctypes.byref(key_object.keyobject), key_len, opt)

        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_store_generate_key %s", status_to_str(status))
            return status
        log.debug("sss_key_store_generate_key %s", status_to_str(status))
        return status

    def get_key(self, key_object, data, data_len, key_bit_len):
        """
        Retrieve key from secure element
        :param key_object: Instance of key object
        :param data: Output data
        :param data_len: Output data length
        :param key_bit_len: Out put key bit length
        :return: Status
        """
        if not isinstance(key_object, KeyObject):
            log.error("%s must be an instance of KeyObject", str(key_object))
            return apis.kStatus_SSS_Fail

        if key_object.keyobject is None:
            log.error("get_key %s", status_to_str(apis.kStatus_SSS_Fail))
            return apis.kStatus_SSS_Fail

        status = apis.sss_key_store_get_key(
            ctypes.byref(self.keystore), ctypes.byref(key_object.keyobject), ctypes.byref(data),
            ctypes.byref(data_len), ctypes.byref(key_bit_len))

        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_store_get_key %s", status_to_str(status))
            return status
        log.debug("sss_key_store_get_key %s", status_to_str(status))
        return status

    def get_key_attest(self, key_object, data, data_len, key_bit_len, attestation_key, algorithm, random_data, random_len, attst_data):
        """
        Retrieve key from secure element
        :param key_object: Instance of key object
        :param data: Output data
        :param data_len: Output data length
        :param key_bit_len: Out put key bit length
        :return: Status
        """
        if not isinstance(key_object, KeyObject):
            log.error("%s must be an instance of KeyObject", str(key_object))
            return apis.kStatus_SSS_Fail

        if key_object.keyobject is None:
            log.error("get_key %s", status_to_str(apis.kStatus_SSS_Fail))
            return apis.kStatus_SSS_Fail

        status = apis.sss_se05x_key_store_get_key_attst(ctypes.byref(self.keystore),
            ctypes.byref(key_object.keyobject),  ctypes.byref(data),
            ctypes.byref(data_len), ctypes.byref(key_bit_len), ctypes.byref(attestation_key.keyobject),
            algorithm, random_data, random_len, ctypes.byref(attst_data))

        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_store_get_key %s", status_to_str(status))
            return status
        log.debug("sss_key_store_get_key %s", status_to_str(status))
        return status

    def erase_key(self, key_object):
        """
        Erase key from secure element
        :param key_object: Instance of key object
        :return: Status
        """
        if not isinstance(key_object, KeyObject):
            log.error("%s must be an instance of KeyObject", str(key_object))
            return apis.kStatus_SSS_Fail

        if key_object.keyobject is None:
            log.error("erase_key %s", status_to_str(apis.kStatus_SSS_Fail))
            return apis.kStatus_SSS_Fail

        status = apis.sss_key_store_erase_key(
            ctypes.byref(self.keystore), ctypes.byref(key_object.keyobject))

        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_store_erase_key %s", status_to_str(status))
            return status
        log.debug("sss_key_store_erase_key %s", status_to_str(status))
        return status

    def free(self):
        """
        Release allocated key store
        :return: None
        """
        if self.keystore:
            apis.sss_key_store_context_free(ctypes.byref(self.keystore))
            self.keystore = None
