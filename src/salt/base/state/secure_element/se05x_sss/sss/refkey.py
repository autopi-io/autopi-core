#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import logging
from .util import generate_openssl_ecc_refkey, generate_openssl_rsa_refkey
from .getkey import Get
from . import sss_api as apis

log = logging.getLogger(__name__)


class RefPem:
    """
    Create reference key
    """

    def __init__(self, session_obj):
        """
        Constructor
        :param session_obj: Instance of session
        """
        self._session = session_obj
        self._get_object = Get(session_obj)

    def do_ecc_refpem_pair(self, key_id, file_name, encode_format="", password="nxp", cert= ""):
        """
        Create ECC reference key pair
        :param key_id: Key index of the private key
        :param file_name: File name to store reference key
        :param encode_format: Encode format to store key. Eg: DER, PEM
        :param password: Password to encrypt pkcs12 reference key
        :return: Status
        """
        status = self._get_object.get_key(key_id)

        if status == apis.kStatus_SSS_Success:
            if self._get_object.key_type == apis.kSSS_KeyPart_Pair:
                key_part = '10'
                status = generate_openssl_ecc_refkey(self._get_object.key, key_id,
                                                     file_name, key_part,
                                                     self._get_object.curve_id,
                                                     encode_format, password,
                                                     cert)
            else:
                log.error("Reference Key creation is not supported for this key type: %s",
                          (self._get_object.key_type,))
                status = apis.kStatus_SSS_Fail
        return status

    def do_ecc_refpem_pub(self, key_id, file_name, encod_format="", password="nxp", cert= ""):
        """
        Create ECC reference public key
        :param key_id: Key index
        :param file_name: File name to store reference key
        :param encod_format: Encode format to store key. Eg: DER, PEM
        :param password: Password to encrypt pkcs12 reference key
        :return: Status
        """
        status = self._get_object.get_key(key_id)
        if status == apis.kStatus_SSS_Success:
            if self._get_object.key_type in [apis.kSSS_KeyPart_Pair, apis.kSSS_KeyPart_Public]:
                key_part = '20'
                status = generate_openssl_ecc_refkey(self._get_object.key, key_id, file_name,
                                                     key_part, self._get_object.curve_id,
                                                     encod_format, password,
                                                     cert)
            else:
                log.error("Reference Key creation is not supported for this key type: %s",
                          (self._get_object.key_type,))
                status = apis.kStatus_SSS_Fail
        return status

    def do_rsa_refpem_pair(self, key_id, file_name, encode_format="", password="nxp", cert= ""):
        """
        Create RSA reference key pair
        :param key_id: Key index
        :param file_name: File name to store reference key
        :param encode_format: Encode format to store key. Eg: DER, PEM
        :param password: Password to encrypt pkcs12 reference key
        :return: Status
        """
        status = self._get_object.get_key(key_id)
        if status == apis.kStatus_SSS_Success:
            if self._get_object.key_type in [apis.kSSS_KeyPart_Pair, apis.kSSS_KeyPart_Public]:
                key_size = 0
                if self._get_object.key_size == 4400:
                    key_size = 4096
                elif self._get_object.key_size == 3376:
                    key_size = 3072
                elif self._get_object.key_size == 2352:
                    key_size = 2048
                elif self._get_object.key_size == 1296:
                    key_size = 1024
                status = generate_openssl_rsa_refkey(self._get_object.key, key_id, file_name,
                                                     key_size, encode_format, password,
                                                     cert)
            else:
                log.error("Reference Key creation is not supported for this key type: %s",
                          (self._get_object.key_type,))
                status = apis.kStatus_SSS_Fail
        return status
