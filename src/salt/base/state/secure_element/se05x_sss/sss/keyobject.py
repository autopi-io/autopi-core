#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import ctypes
import logging
from .util import status_to_str
from . import sss_api as apis
log = logging.getLogger(__name__)


class KeyObject:
    """
    Key object operation
    """

    def __init__(self, keystore_obj):
        """
        Constructor
        :param keystore_obj: Instance of key store
        """
        from . import keystore  # pylint: disable=import-outside-toplevel
        if not isinstance(keystore_obj, keystore.KeyStore):
            log.error("%s must be an instance of KeyStore", str(keystore))
            self.keyobject = None
            return

        self._keystore = keystore_obj.keystore

        if keystore_obj.session.subsystem == apis.kType_SSS_SE_SE05x:
            self.keyobject = apis.sss_se05x_object_t()
        else:
            self.keyobject = apis.sss_object_t()

        if self._keystore is None:
            self.keyobject = None
            return

        status = apis.sss_key_object_init(ctypes.byref(
            self.keyobject), ctypes.byref(self._keystore))
        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_object_init %s", status_to_str(status))
            self.keyobject = None
            return
        log.debug("sss_key_object_init %s", status_to_str(status))

    def allocate_handle(self, key_id, key_part, cypher_type, key_len, object_type):  # pylint: disable=too-many-arguments
        """
        Allocate handle to inject or generate key or certificate
        :param key_id: Key index to set or generate key
        :param key_part: Key type
        :param cypher_type: Cipher type
        :param key_len: Key length
        :param object_type: Key object mode. Eg: Transient, Persistent
        :return: Status
        """
        if self.keyobject is None:
            log.error("allocate_handle %s", status_to_str(apis.kStatus_SSS_Fail))
            return apis.kStatus_SSS_Fail

        status = apis.sss_key_object_allocate_handle(
            ctypes.byref(self.keyobject), key_id, key_part,
            cypher_type, ctypes.c_size_t(key_len), object_type)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_object_allocate_handle %s", status_to_str(status))
            self.keyobject = None
            raise Exception("sss_key_object_allocate_handle %s" % status_to_str(status))
        log.debug("sss_key_object_allocate_handle %s", status_to_str(status))
        return status

    def get_handle(self, key_id):
        """
        Get handle of the key
        :param key_id: Key index to retrieve handle
        :return: Status, Object type and Cipher type
        """
        if self.keyobject is None:
            log.error("get_handle %s", status_to_str(apis.kStatus_SSS_Fail))
            return apis.kStatus_SSS_Fail, None, None
        status = apis.sss_key_object_get_handle(
            ctypes.byref(self.keyobject), key_id)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_object_get_handle %s", status_to_str(status))
            self.keyobject = None
            return status, None, None
        log.debug("sss_key_object_get_handle %s", status_to_str(status))
        return status, self.keyobject.objectType, self.keyobject.cipherType

    def free(self):
        """
        Release allocated key object
        :return: None
        """
        if self.keyobject is None:
            log.error("Free %s", status_to_str(apis.kStatus_SSS_Fail))
            return
        apis.sss_key_object_free(ctypes.byref(self.keyobject))
