#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import logging
from . import sss_api as apis
from .keystore import KeyStore
from .keyobject import KeyObject
from .getkey import Get
from .util import get_ecc_cypher_type

log = logging.getLogger(__name__)


class Generate:
    """
    Generate key pair/public key of ecc/rsa
    """

    def __init__(self, session_obj):
        """
        Constructor
        :param session_obj: Instance of session
        """
        self._session = session_obj
        self._ctx_ks = KeyStore(self._session)
        self._ctx_key = KeyObject(self._ctx_ks)
        self.key_obj_mode = apis.kKeyObject_Mode_Persistent

    def gen_ecc_public(self, key_id, curve_type, file_name, policy, encode_format=""):  # pylint: disable=too-many-arguments
        """
        Generate ecc public key
        :param key_id: Key index
        :param curve_type: ECC curve type
        :param file_name: File name to store public key
        :param policy: Policy to be applied
        :param encode_format: File format to store public key
        :return: Status
        """
        if file_name[-4:] != '.pem' and file_name[-4:] != '.der':
            log.error("Unsupported file type. File type should be in pem or der format")
            return apis.kStatus_SSS_Fail

        status = self.gen_ecc_pair(key_id, curve_type, policy)
        if status != apis.kStatus_SSS_Success:
            return status

        get = Get(self._session)
        status = get.get_key(key_id, file_name, encode_format)
        return status

    def gen_ecc_pair(self, key_id, curve_type, policy):
        """
        Generate ecc key pair
        :param key_id: Key index
        :param curve_type: ECC curve type
        :param policy: Policy to be applied
        :return: Status
        """
        cypher_type, key_size = get_ecc_cypher_type(curve_type)
        key_type = apis.kSSS_KeyPart_Pair
        if key_size == 0:
            log.error("curve type not supported")
            return apis.kStatus_SSS_Fail
        status = self._gen_key_pair(key_id, key_size, key_type, cypher_type, policy)
        return status

    def gen_rsa_public(self, key_id, key_size, file_name, policy):
        """
        Generate rsa public key
        :param key_id: Key index
        :param key_size: Key size to generate
        :param file_name: File name to store public key
        :param policy: Policy to be applied
        :return: Status
        """
        if file_name[-4:] != '.pem' and file_name[-4:] != '.der':
            log.error("Unsupported file type. File type should be in pem or der format")
            return apis.kStatus_SSS_Fail

        status = self.gen_rsa_pair(key_id, key_size, policy)
        if status != apis.kStatus_SSS_Success:
            return status

        get = Get(self._session)
        status = get.get_key(key_id, file_name)
        return status

    def gen_rsa_pair(self, key_id, key_size, policy):
        """
        Generate rsa key pair
        :param key_id: Key index
        :param key_size: RSA key size to generate
        :param policy: Policy to be applied
        :return: Status
        """
        key_type = apis.kSSS_KeyPart_Pair
        cypher_type = apis.kSSS_CipherType_RSA_CRT
        status = self._gen_key_pair(key_id, key_size, key_type, cypher_type, policy)
        return status

    def _gen_key_pair(self, key_id, key_size, key_type, cypher_type, policy):  # pylint: disable=too-many-arguments
        """
        Generate key pair
        :param key_id: Key index
        :param key_size: Key size
        :param key_type: Key type
        :param cypher_type: Cypher type
        :param policy: Policy to be applied
        :return: Status
        """

        # Key length calculation based on key bit length
        # if modulus of key_bit_len is non zero, then allocate extra byte
        if (key_size % 8) != 0:
            key_len = (key_size / 8) + 1
        else:
            key_len = key_size / 8

        status = self._ctx_key.allocate_handle(key_id, key_type, cypher_type, int(key_len),
                                               self.key_obj_mode)
        if status != apis.kStatus_SSS_Success:
            return status

        status = self._ctx_ks.generate_key(self._ctx_key, key_size, policy)
        if status != apis.kStatus_SSS_Success:
            return status

        status = self._ctx_ks.save_key_store()
        return status
