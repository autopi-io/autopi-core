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
from .util import status_to_str
from .util import save_to_file

log = logging.getLogger(__name__)


class DeriveKey:  # pylint: disable=too-many-instance-attributes
    """
    Key derivation operation
    """

    def __init__(self, session_obj, host_session_obj=None):
        """
        Constuctor
        :param session_obj: Instance of session
        :param host_session_obj: Instance of host session
        """
        self._session = session_obj.session_ctx
        self.derive = apis.sss_derive_key_t()
        self.algorithm = apis.kAlgorithm_SSS_ECDH
        self.mode = apis.kMode_SSS_ComputeSharedSecret
        self._ctx_ks = KeyStore(session_obj)
        self._ctx_key = KeyObject(self._ctx_ks)
        self._derived_key = None
        self._derived_key_size = 304 * 8
        self.object_type = apis.kSSS_KeyPart_Default
        self.cipher_type = apis.kSSS_CipherType_HMAC
        self._host_ctx_key = None
        self._host_ctx_key_id = 0
        if host_session_obj is not None:
            self._host_session = host_session_obj.session_ctx
            self._host_ctx_ks = KeyStore(host_session_obj)
            self._host_ctx_key = KeyObject(self._host_ctx_ks)

    def _symmetric_context_init(self, key_id):
        """
        asymmetric context initialization
        :param key_id: Key index
        :param prv_key_obj: key object of private key
        :return: Status
        """
        data_len = 80

        status, self.object_type, self.cipher_type = self._ctx_key.get_handle(key_id)

        if status != apis.kStatus_SSS_Success:
            return status
        status = apis.sss_derive_key_context_init(ctypes.byref(self.derive),
                                                  ctypes.byref(self._session),
                                                  ctypes.byref(self._ctx_key.keyobject),
                                                  self.algorithm, self.mode)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_derive_key_context_init %s", status_to_str(status))
        return status

    def symmetric_derive_ka(self, key_id, pub_key_obj, output_key_obj):
        """
        Asymmetric derive key agreement
        :param key_id: Key index of private key
        :param prv_key_obj: Public key object
        :param pub_key_obj: Output key object
        :return: Status
        """
        self.algorithm = apis.kAlgorithm_SSS_ECDH

        status = self._symmetric_context_init(key_id)
        if status != apis.kStatus_SSS_Success:
            return status

        status = apis.sss_derive_key_dh(ctypes.byref(self.derive),
                                        ctypes.byref(pub_key_obj.keyobject),
                                        ctypes.byref(output_key_obj.keyobject))
        if status != apis.kStatus_SSS_Success:
            log.error("sss_derive_key_dh %s", status_to_str(status))

        return status

    def symmetric_derive_kd(self, key_id, salt, info, req_key_len, derive_key_id = None, salt_id=None):  # pylint: disable=too-many-arguments

        """
        Symmetric derive key derivation
        :param key_id: Key index
        :param prv_key_obj: Key object of private key
        :param salt: Salt data
        :param info: Info data
        :param req_key_len: Request key length
        :param derive_key_file: File name to store derived key
        :return: Status
        """

        status = self._symmetric_context_init(key_id)
        if status != apis.kStatus_SSS_Success:
            return status


        info_len = len(info)
        info_ctype = (ctypes.c_uint8 * info_len)(*info)
        hostObject = None

        if self._host_ctx_key is not None:
            if derive_key_id is not None:
                status = self._host_ctx_key.allocate_handle(derive_key_id, self.object_type,
                                                        self.cipher_type, req_key_len,
                                                        apis.kKeyObject_Mode_Persistent)
                if status != apis.kStatus_SSS_Success:
                    return status
                hostObject = ctypes.byref(self._host_ctx_key.keyobject)

        if salt is not None:
            salt_len = len(salt)
            salt_ctype = (ctypes.c_uint8 * salt_len)(*salt)

            status = apis.sss_derive_key_one_go(ctypes.byref(self.derive), salt_ctype, salt_len,
                                                info_ctype, info_len,
                                                hostObject,
                                                req_key_len)
        else:

            status, object_type, cipher_type = self._ctx_key.get_handle(salt_id)

            if status != apis.kStatus_SSS_Success:
                return status
            status = apis.sss_derive_key_sobj_one_go(ctypes.byref(self.derive), ctypes.byref(self._ctx_key.keyobject),
                                                info_ctype, info_len,
                                                hostObject,
                                                req_key_len)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_derive_key_dh %s", status_to_str(status))
            return status

        # Get derived key now
        if self._host_ctx_key is None:
            return apis.kStatus_SSS_Success

        data_len = int(self._derived_key_size / 8)
        key = (ctypes.c_uint8 * data_len)(0)
        data_len_ctype = ctypes.c_size_t(data_len)
        key_size_ctype = ctypes.c_size_t(self._derived_key_size)
        status = self._host_ctx_ks.get_key(self._host_ctx_key, key, data_len_ctype, key_size_ctype)
        if status == apis.kStatus_SSS_Fail:
            log.warning("Failed to retrieve derived key")
            self._derived_key = None
            self._derived_key_size = 0
            # Return success in case object was derived in SE05x
            return apis.kStatus_SSS_Success
        key_list = list(key)
        self._derived_key = key_list[:int(data_len_ctype.value)]
        self._derived_key_size = data_len_ctype.value * 8

        return status

    def symmetric_derive_pbkdf(self, key_id, iterations, req_key_len, salt = None, salt_id = None, derived_obj_id = None):
        """
        Symmetric derive key (PBKDF)
        :param key_id: Key ID of HMAC key to use to perform PBKDF
        :param iterations: No. of iterations to use while performing PBKDF
        :param req_key_len: Length of output requested
        :param salt: Salt to use for PBKDF (Optional - Not required if salt_id passed)
        :param salt_id: Key ID to use for salt (Optional - Not required if salt is passed)
        :param derived_obj_id: Key ID to store derived output (Optional - Derived output will be returned if not passed)
        """
        """
        Supported algorithms:
        kSE05x_MACAlgo_HMAC_SHA1
        kSE05x_MACAlgo_HMAC_SHA256
        kSE05x_MACAlgo_HMAC_SHA384
        kSE05x_MACAlgo_HMAC_SHA512
        """
        salt_c = None
        salt_len_c = 0
        salt_id_c = 0
        derived_session_key_len = ctypes.c_size_t(req_key_len)
        derived_key = (ctypes.c_uint8 * req_key_len)(0)
        derived_key_ptr = ctypes.byref(derived_key)
        derived_key_id = 0

        if salt is None and salt_id is None:
            log.error("One of salt and salt_id must be passed")
            return apis.kStatus_SSS_Fail

        if salt is not None and salt_id is not None:
            log.error("Either salt or salt_id must be passed")
            return apis.kStatus_SSS_Fail

        if derived_obj_id is None:
            pass
        elif not isinstance(derived_obj_id, int):
            log.error("derived_obj_id must be a valid integer")
            return apis.kStatus_SSS_Fail
        else:
            derived_key = None
            derived_key_ptr = None
            derived_session_key_len = ctypes.c_size_t(0)
            derived_key_id = derived_obj_id

        if salt is not None:
            salt_c = ctypes.byref((ctypes.c_uint8 * len(salt))(*salt))
            salt_len_c = len(salt)
        else:
            salt_id_c = salt_id

        sm_status = apis.Se05x_API_PBKDF2_extended(
            ctypes.byref(self._session.s_ctx),
            key_id,
            salt_c,
            salt_len_c,
            salt_id_c,
            iterations,
            self.algorithm,
            req_key_len,
            derived_key_id,
            derived_key_ptr,
            ctypes.byref(derived_session_key_len)
        )

        if sm_status != apis.kSE05x_SW12_NO_ERROR:
            return apis.kStatus_SSS_Fail

        if derived_key is not None:
            derived_session_key_list = list(derived_key)
            self._derived_key = derived_session_key_list[:int(derived_session_key_len.value)]
            self._derived_key_size = int(derived_session_key_len.value)

        return apis.kStatus_SSS_Success

    def get_derived_key(self, file_name=None, encode_format=""):
        return self._derived_key
