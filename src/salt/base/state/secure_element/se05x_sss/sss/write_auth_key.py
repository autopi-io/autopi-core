#
# Copyright 2019,2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import ctypes
import logging
from . import sss_api as apis
log = logging.getLogger(__name__)


class WriteAuthKey:
    """
    Write Authentication key
    """

    def __init__(self, session_obj):
        """
        Constructor
        :param session_obj: Instance of session
        """
        self._session = session_obj
        self.max_attempts = apis.SE05x_MaxAttemps_UNLIMITED

    @classmethod
    def _create_policy_buffer(cls, policy_in=None):
        """
        Transform policy to buffer
        :param policy_in: Input policy to put in buffer
        :return: Policy
        """
        policy = apis.Se05xPolicy_t()
        if policy_in is not None:
            policy_length_int = 200
            policy_buf = (ctypes.c_uint8 * policy_length_int)(0)
            policy_length = ctypes.c_size_t(policy_length_int)
            apis.sss_se05x_create_object_policy_buffer(policy_in,
                                                       ctypes.byref(policy_buf),
                                                       ctypes.byref(policy_length))
            policy.value = policy_buf
            policy.value_len = policy_length
        else:
            policy.value = None
            policy.value_len = 0
        return ctypes.pointer(policy)

    def do_write_ec_key(self, key_id, curve_id, prv_key, pub_key, policy_in=None):  # pylint: disable=too-many-arguments
        """
        Inject ECC authentication key
        :param key_id: Key index
        :param curve_id: Curve id
        :param prv_key: ECC private key
        :param pub_key: ECC public key
        :param policy_in: Policy to be applied
        :return: Status
        """
        policy = self._create_policy_buffer(policy_in)
        prv_key_len = len(prv_key)
        pb_key_len = len(pub_key)
        prv_key = (ctypes.c_uint8 * prv_key_len)(*prv_key)
        pub_key = (ctypes.c_uint8 * pb_key_len)(*pub_key)
        status = apis.Se05x_API_WriteECKey(ctypes.byref(self._session.session_ctx.s_ctx),
                                           policy,
                                           self.max_attempts,
                                           key_id,
                                           curve_id,
                                           prv_key,
                                           prv_key_len,
                                           pub_key,
                                           pb_key_len,
                                           apis.kSE05x_AttestationType_AUTH |
                                           apis.kSE05x_TransientType_Persistent,
                                           apis.kSE05x_KeyPart_Pair)
        if status != apis.kSE05x_SW12_NO_ERROR:
            status = apis.kStatus_SSS_Fail
        else:
            status = apis.kStatus_SSS_Success
        return status

    def do_write_sym_key(self, key_id, sym_key, policy_in=None,
                         sym_key_type=apis.kSE05x_SymmKeyType_AES):
        """
        Inject symmetric key
        :param key_id: Key index
        :param sym_key: Symmetric key
        :param policy_in: Policy to be applied
        :param sym_key_type: Symmetric key type
        :return: Status
        """
        policy = self._create_policy_buffer(policy_in)
        sym_key_len = len(sym_key)
        sym_key_ctype = (ctypes.c_uint8 * sym_key_len)(*sym_key)
        status = apis.Se05x_API_WriteSymmKey(ctypes.byref(self._session.session_ctx.s_ctx),
                                             policy,
                                             self.max_attempts,
                                             key_id,
                                             apis.SE05x_KeyID_KEK_NONE,
                                             sym_key_ctype,
                                             sym_key_len,
                                             apis.kSE05x_AttestationType_AUTH |
                                             apis.kSE05x_TransientType_Persistent,
                                             sym_key_type)
        if status != apis.kSE05x_SW12_NO_ERROR:
            status = apis.kStatus_SSS_Fail
        else:
            status = apis.kStatus_SSS_Success
        return status
