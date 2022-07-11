#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import ctypes
import logging
from . import sss_api as apis
from .util import status_to_str
from . import keyobject
from . import session

log = logging.getLogger(__name__)


class Asymmetric:
    """
    SSS Asymmetric commands
    """

    def __init__(self, session_obj, keyobj, algorithm, mode):
        """
        Constructor performs asymmetric init
        :param session_obj: Instance of session
        :param keyobj: Instance of key object
        :param algorithm: Hash algorithm. eg: SHA 256
        :param mode: Operation mode. eg: sign, verify, encrypt, decrypt
        """

        if not isinstance(session_obj, session.Session):
            log.error("%s must be an instance of Session", str(session_obj))
            self._asymmctx = None
            return

        if not isinstance(keyobj, keyobject.KeyObject):
            log.error("%s must be an instance of KeyObject", str(keyobj))
            self._asymmctx = None
            return

        self._session = session_obj.session_ctx
        self._keyobject = keyobj.keyobject
        self._asymmctx = apis.sss_asymmetric_t()

        if self._keyobject is None:
            self._asymmctx = None
            return

        status = apis.sss_asymmetric_context_init(ctypes.byref(self._asymmctx), ctypes.byref(
            self._session), ctypes.byref(self._keyobject), algorithm, mode)
        if status != apis.kStatus_SSS_Success:
            log.error('sss_asymmetric_context_init %s', status_to_str(status))
            self._asymmctx = None
            return
        log.debug('sss_asymmetric_context_init %s', status_to_str(status))

    def sign(self, digest, digest_len, signature, signature_len):
        """
        Asymmetric Sign
        :param digest: Input digest for sign
        :param digest_len: Input digest length
        :param signature: Output signature data
        :param signature_len: Output signature length
        :return: signature data and status
        """
        if self._asymmctx is None:
            log.error('Sign %s', status_to_str(apis.kStatus_SSS_Fail))
            return None, apis.kStatus_SSS_Fail
        status = apis.sss_asymmetric_sign_digest(ctypes.byref(self._asymmctx), ctypes.byref(
            digest), digest_len, ctypes.byref(signature), ctypes.byref(signature_len))
        if status != apis.kStatus_SSS_Success:
            log.error("sss_asymmetric_sign_digest'%s", status_to_str(status))
            self._asymmctx = None
            return None, status
        log.debug("sss_asymmetric_sign_digest'%s", status_to_str(status))
        return signature, status

    def se05x_sign(self, src, src_len, signature, signature_len):
        """
        Asymmetric Sign
        :param src: Input data for sign
        :param src_len: Input data length
        :param signature: Output signature data
        :param signature_len: Output signature length
        :return: signature data and status
        """
        if self._asymmctx is None:
            log.error('Se05x Sign %s', status_to_str(apis.kStatus_SSS_Fail))
            return None, apis.kStatus_SSS_Fail
        status = apis.sss_se05x_asymmetric_sign(ctypes.byref(self._asymmctx), ctypes.byref(
            src), src_len, ctypes.byref(signature), ctypes.byref(signature_len))
        if status != apis.kStatus_SSS_Success:
            log.error("sss_se05x_asymmetric_sign'%s", status_to_str(status))
            self._asymmctx = None
            return None, status
        log.debug("sss_se05x_asymmetric_sign'%s", status_to_str(status))
        return signature, status

    def verify(self, digest, digest_len, signature, signature_len):
        """
        Asymmetric verify
        :param digest: Input digest for verify
        :param digest_len: Input digest length
        :param signature: Input signature data
        :param signature_len: Input signature length
        :return: Status
        """
        if self._asymmctx is None:
            log.error('Sign %s', status_to_str(apis.kStatus_SSS_Fail))
            return apis.kStatus_SSS_Fail

        status = apis.sss_asymmetric_verify_digest(ctypes.byref(self._asymmctx),
                                                   ctypes.byref(digest),
                                                   digest_len,
                                                   ctypes.byref(signature),
                                                   signature_len)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_asymmetric_verify_digest %s", status_to_str(status))
            self._asymmctx = None
            return status
        log.debug("sss_asymmetric_verify_digest %s", status_to_str(status))
        log.debug("Verification Success")
        return status

    def se05x_verify(self, src, src_len, signature, signature_len):
        """
        Asymmetric verify
        :param src: Input data for verify
        :param src_len: Input data length
        :param signature: Input signature data
        :param signature_len: Input signature length
        :return: Status
        """
        if self._asymmctx is None:
            log.error('Sign %s', status_to_str(apis.kStatus_SSS_Fail))
            return apis.kStatus_SSS_Fail

        status = apis.sss_se05x_asymmetric_verify(ctypes.byref(self._asymmctx),
                                                  ctypes.byref(src),
                                                  src_len,
                                                  ctypes.byref(signature),
                                                  signature_len)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_se05x_asymmetric_verify %s", status_to_str(status))
            self._asymmctx = None
            return status
        log.debug("sss_se05x_asymmetric_verify %s", status_to_str(status))
        log.debug("Verification Success")
        return status

    def encrypt(self, src_data, src_len, encrypt_data, encrypt_data_len):
        """
        Asymmetric Encrypt
        :param src_data: Input data for encryption
        :param src_len: Input data length
        :param encrypt_data: Output encrypted data
        :param encrypt_data_len: Output data length
        :return: status and Encrypted data
        """
        if self._asymmctx is None:
            log.error('encrypt %s', status_to_str(apis.kStatus_SSS_Fail))
            return apis.kStatus_SSS_Fail, None

        status = apis.sss_asymmetric_encrypt(ctypes.byref(self._asymmctx),
                                             ctypes.byref(src_data),
                                             src_len,
                                             ctypes.byref(encrypt_data),
                                             ctypes.byref(encrypt_data_len))

        if status != apis.kStatus_SSS_Success:
            log.error("sss_asymmetric_encrypt %s", status_to_str(status))
            self._asymmctx = None
            return status, None
        log.debug("sss_asymmetric_encrypt %s", status_to_str(status))
        return status, encrypt_data

    def decrypt(self, encrypt_data, encrypt_data_len, decrypt_data, decrypt_data_len):
        """
        Asymmetric Decrypt
        :param encrypt_data: Input encrypted data
        :param encrypt_data_len: Input data length
        :param decrypt_data: Output decrypted data
        :param decrypt_data_len: Output data length
        :return: status and decrypted data
        """
        if self._asymmctx is None:
            log.error('decrypt %s', status_to_str(apis.kStatus_SSS_Fail))
            return apis.kStatus_SSS_Fail, None

        status = apis.sss_asymmetric_decrypt(ctypes.byref(self._asymmctx),
                                             ctypes.byref(encrypt_data),
                                             encrypt_data_len,
                                             ctypes.byref(decrypt_data),
                                             ctypes.byref(decrypt_data_len))

        if status != apis.kStatus_SSS_Success:
            log.error("sss_asymmetric_decrypt %s", status_to_str(status))
            self._asymmctx = None
            return status, None
        log.debug("sss_asymmetric_decrypt %s", status_to_str(status))
        return status, decrypt_data
