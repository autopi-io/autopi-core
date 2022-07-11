#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

from .keystore import KeyStore
from .keyobject import KeyObject
from . import sss_api as apis


class Erase:  # pylint: disable=too-few-public-methods
    """
    Erase key operation
    """

    def __init__(self, session_obj):
        """
        constuctor
        :param session_obj: Instance of session
        """
        self._session = session_obj
        self._ctx_ks = KeyStore(self._session)
        self._ctx_key = KeyObject(self._ctx_ks)

    def erase_key(self, key_id):
        """
        Erase key operation
        :param key_id: Key index
        :return: Status
        """
        status, object_type, cipher_type = self._ctx_key.get_handle(key_id)  # pylint: disable=unused-variable
        if status != apis.kStatus_SSS_Success:
            return status
        status = self._ctx_ks.erase_key(self._ctx_key)
        self._ctx_key.free()
        return status
