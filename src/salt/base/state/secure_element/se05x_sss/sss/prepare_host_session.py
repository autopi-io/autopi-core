# Copyright 2020 NXP
#
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import ctypes
import logging
import os
from inspect import currentframe
from . import authkey
from . import sss_api as apis
from . import util
from .util import status_to_str

log = logging.getLogger(__name__)


class PrepareHostSession:  # pylint: disable=too-many-instance-attributes
    """
    Session open and close operation
    """

    def __init__(self):
        self.auth_id = 0
        self.connection_type = apis.kSSS_ConnectionType_Plain
        self._enc_key = None
        self._mac_key = None
        self._dek_key = None
        self._tunnel_session_ctx = None
        self._connect_ctx = apis.SE_Connect_Ctx_t()
        self.session = None
        self.subsystem = None
        self.host_keystore = None
        self.scpkey = None

    def open_host_session(self, subsystem):
        """
        Open Host session
        :param subsystem: Host session subsystem. Eg: Mbedtls, Openssl
        :return: status
        """
        from . import session  # pylint: disable=import-outside-toplevel
        session_obj = session.Session(from_pickle=False)
        if not session_obj.session_ctx:
            session_obj.session_ctx = apis.sss_session_t()
        status = apis.sss_session_open(
            ctypes.byref(session_obj.session_ctx), subsystem, 0,
            apis.kSSS_ConnectionType_Plain, None)
        if status == apis.kStatus_SSS_Success:
            self.subsystem = subsystem
            self.session = session_obj
        return status

    def setup_counter_part_session(self):
        """
        Open Host Crypto Session. Either MbedTLS or Openssl depending on sssapisw library.
        :return: Status
        """
        from . import keystore  # pylint: disable=import-outside-toplevel
        status = self.open_host_session(apis.kType_SSS_mbedTLS)
        if status != apis.kStatus_SSS_Success:
            # Retry with OpenSSL
            status = self.open_host_session(apis.kType_SSS_OpenSSL)
        if status != apis.kStatus_SSS_Success:
            log.error("Failed to openHost Session")
            return status

        self.host_keystore = keystore.KeyStore(self.session)
        return status

    def prepare_host(self, connect_ctx):
        """
        Host Session open
        :param connect_ctx: Connection context for host session
        :return: None
        """

        if connect_ctx.auth.authType in [apis.kSE05x_AuthType_UserID,
                                         apis.kSE05x_AuthType_AESKey,
                                         apis.kSE05x_AuthType_ECKey,
                                         apis.kSE05x_AuthType_SCP03]:

            if connect_ctx.auth.authType == apis.kSE05x_AuthType_SCP03:
                self.connection_type = apis.kSSS_ConnectionType_Encrypted
                self._read_scpkey()
                self._se05x_prepare_host_platformscp(connect_ctx)

            elif connect_ctx.auth.authType == apis.kSE05x_AuthType_UserID:
                self.auth_id = authkey.SE050_AUTHID_USER_ID
                self.connection_type = apis.kSSS_ConnectionType_Password
                obj = apis.sss_object_t()
                self._host_crypto_alloc_setkeys(currentframe().f_lineno, obj,
                                                apis.kSSS_CipherType_UserID,
                                                authkey.SE050_AUTHID_USER_ID_VALUE)
                connect_ctx.auth.ctx.idobj.pObj = ctypes.pointer(obj)

            elif connect_ctx.auth.authType == apis.kSE05x_AuthType_AESKey:
                self.auth_id = authkey.SE050_AUTHID_AESKEY
                self.connection_type = apis.kSSS_ConnectionType_Encrypted
                self._se05x_prepare_host_applet_scp03_keys(connect_ctx)

            elif connect_ctx.auth.authType == apis.kSE05x_AuthType_ECKey:
                self.auth_id = authkey.SE050_AUTHID_ECKEY
                self.connection_type = apis.kSSS_ConnectionType_Encrypted
                self._se05x_prepare_host_eckey(connect_ctx)

    def _se05x_prepare_host_applet_scp03_keys(self, connect_ctx):
        """
        Set keys using host for Applet SCP03 session
        :return:
        """

        static_ctx = apis.NXSCP03_StaticCtx_t()
        dynamic_ctx = apis.NXSCP03_DynCtx_t()

        self._host_crypto_alloc_setkeys(currentframe().f_lineno, static_ctx.Enc,
                                        apis.kSSS_CipherType_AES,
                                        authkey.SE050_AUTHID_AESKEY_VALUE)

        self._host_crypto_alloc_setkeys(currentframe().f_lineno, static_ctx.Mac,
                                        apis.kSSS_CipherType_AES,
                                        authkey.SE050_AUTHID_AESKEY_VALUE)

        self._host_crypto_alloc_setkeys(currentframe().f_lineno, static_ctx.Dek,
                                        apis.kSSS_CipherType_AES,
                                        authkey.SE050_AUTHID_AESKEY_VALUE)

        self._alloc_applet_scp03_key_to_se05x_authctx(currentframe().f_lineno,
                                                      dynamic_ctx.Enc)

        self._alloc_applet_scp03_key_to_se05x_authctx(currentframe().f_lineno,
                                                      dynamic_ctx.Mac)

        self._alloc_applet_scp03_key_to_se05x_authctx(currentframe().f_lineno,
                                                      dynamic_ctx.Rmac)

        connect_ctx.auth.ctx.scp03.pStatic_ctx = ctypes.pointer(static_ctx)
        connect_ctx.auth.ctx.scp03.pDyn_ctx = ctypes.pointer(dynamic_ctx)

    def _alloc_applet_scp03_key_to_se05x_authctx(self, key_id, key_obj):
        """
        Perform key object init and key object allocate handle using host session.
        :param key_id: Key index
        :param key_obj: key object
        :return: Status
        """

        status = apis.sss_key_object_init(ctypes.byref(
            key_obj), ctypes.byref(self.host_keystore.keystore))

        if status != apis.kStatus_SSS_Success:
            raise Exception("Prepare Host sss_key_object_init %s" % status_to_str(status))

        status = apis.sss_key_object_allocate_handle(
            ctypes.byref(key_obj), key_id, apis.kSSS_KeyPart_Default,
            apis.kSSS_CipherType_AES, 16, apis.kKeyObject_Mode_Persistent)
        if status != apis.kStatus_SSS_Success:
            raise Exception("Prepare Host sss_key_object_allocate_handle %s" %
                            status_to_str(status))

    def _se05x_prepare_host_platformscp(self, connect_ctx):
        """
        Prepare host for Platform SCP session
        :return: Status
        """
        static_ctx = apis.NXSCP03_StaticCtx_t()
        dynamic_ctx = apis.NXSCP03_DynCtx_t()

        # This key version is constant for platform scp
        static_ctx.keyVerNo = authkey.SE05X_KEY_VERSION_NO

        self._host_crypto_alloc_setkeys(currentframe().f_lineno,
                                        static_ctx.Enc,
                                        apis.kSSS_CipherType_AES, self._enc_key)
        self._host_crypto_alloc_setkeys(currentframe().f_lineno,
                                        static_ctx.Mac,
                                        apis.kSSS_CipherType_AES, self._mac_key)
        self._host_crypto_alloc_setkeys(currentframe().f_lineno,
                                        static_ctx.Dek,
                                        apis.kSSS_CipherType_AES, self._dek_key)
        self._alloc_applet_scp03_key_to_se05x_authctx(currentframe().f_lineno,
                                                      dynamic_ctx.Enc)

        self._alloc_applet_scp03_key_to_se05x_authctx(currentframe().f_lineno,
                                                      dynamic_ctx.Mac)

        self._alloc_applet_scp03_key_to_se05x_authctx(currentframe().f_lineno,
                                                      dynamic_ctx.Rmac)

        connect_ctx.auth.ctx.scp03.pStatic_ctx = ctypes.pointer(static_ctx)
        connect_ctx.auth.ctx.scp03.pDyn_ctx = ctypes.pointer(dynamic_ctx)

    def _se05x_prepare_host_eckey(self, connect_ctx):
        """
        Set keys using host for Fast SCP session
        :return: Status
        """

        static_ctx = apis.NXECKey03_StaticCtx_t()
        dynamic_ctx = apis.NXSCP03_DynCtx_t()

        # Init allocate Host ECDSA Key pair
        status = self._alloc_eckey_key_to_se05x_authctx(static_ctx.HostEcdsaObj,
                                                        currentframe().f_lineno,
                                                        apis.kSSS_KeyPart_Pair)
        if status != apis.kStatus_SSS_Success:
            log.error("_alloc_eckey_key_to_se05x_authctx %s", status_to_str(status))
            return status

        # Set Host ECDSA Key pair
        status = apis.sss_key_store_set_key(
            ctypes.byref(self.host_keystore.keystore),
            ctypes.byref(static_ctx.HostEcdsaObj),
            ctypes.byref((ctypes.c_ubyte * len(authkey.SSS_AUTH_SE05X_KEY_HOST_ECDSA_KEY))
                         (*authkey.SSS_AUTH_SE05X_KEY_HOST_ECDSA_KEY)),
            len(authkey.SSS_AUTH_SE05X_KEY_HOST_ECDSA_KEY),
            len(authkey.SSS_AUTH_SE05X_KEY_HOST_ECDSA_KEY) * 8, 0, 0)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_store_set_key %s", status_to_str(status))
            return status

        # Init allocate Host ECKA Key pair
        status = self._alloc_eckey_key_to_se05x_authctx(static_ctx.HostEcKeypair,
                                                        currentframe().f_lineno,
                                                        apis.kSSS_KeyPart_Pair)
        if status != apis.kStatus_SSS_Success:
            log.error("_alloc_eckey_key_to_se05x_authctx %s", status_to_str(status))
            return status

        # Generate Host EC Key pair
        status = apis.sss_key_store_generate_key(
            ctypes.byref(self.host_keystore.keystore),
            ctypes.byref(static_ctx.HostEcKeypair), 256, None)

        if status != apis.kStatus_SSS_Success:
            log.error("_alloc_eckey_key_to_se05x_authctx %s", status_to_str(status))
            return status

        # Init allocate SE ECKA Public Key
        status = self._alloc_eckey_key_to_se05x_authctx(static_ctx.SeEcPubKey,
                                                        currentframe().f_lineno,
                                                        apis.kSSS_KeyPart_Public)
        if status != apis.kStatus_SSS_Success:
            log.error("_alloc_eckey_key_to_se05x_authctx %s", status_to_str(status))
            return status

        # Init Allocate Master Secret
        self._alloc_applet_scp03_key_to_se05x_authctx(currentframe().f_lineno,
                                                      static_ctx.masterSec)

        # Init Allocate ENC Session Key
        self._alloc_applet_scp03_key_to_se05x_authctx(currentframe().f_lineno,
                                                      dynamic_ctx.Enc)

        # Init Allocate MAC Session Key
        self._alloc_applet_scp03_key_to_se05x_authctx(currentframe().f_lineno,
                                                      dynamic_ctx.Mac)

        # Init Allocate DEK Session Key
        self._alloc_applet_scp03_key_to_se05x_authctx(currentframe().f_lineno,
                                                      dynamic_ctx.Rmac)

        connect_ctx.auth.ctx.eckey.pStatic_ctx = ctypes.pointer(static_ctx)
        connect_ctx.auth.ctx.eckey.pDyn_ctx = ctypes.pointer(dynamic_ctx)
        return status

    def _alloc_eckey_key_to_se05x_authctx(self, key_obj, key_id, key_type):
        """
        Key object initialization and allocate handle for fast SCP session
        :param key_obj: Key Object
        :param key_id: Key index
        :param key_type: key type
        :return: Status
        """

        status = apis.sss_key_object_init(ctypes.byref(
            key_obj), ctypes.byref(self.host_keystore.keystore))

        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_object_init %s", status_to_str(status))
            return status

        status = apis.sss_key_object_allocate_handle(ctypes.byref(key_obj), key_id, key_type,
                                                     apis.kSSS_CipherType_EC_NIST_P, 256,
                                                     apis.kKeyObject_Mode_Persistent)
        if status != apis.kStatus_SSS_Success:
            log.error("sss_key_object_allocate_handle %s", status_to_str(status))

        return status

    def _host_crypto_alloc_setkeys(self, key_id, key_obj, cypher_type, key_value):
        """
        Key object initialization, allocate handle and Set key using host
        :param key_id: Key Index
        :param key_obj: Key object
        :param cypher_type: Cypher type
        :param key_value: Key value
        :return: None
        """

        status = apis.sss_key_object_init(ctypes.byref(
            key_obj), ctypes.byref(self.host_keystore.keystore))

        if status != apis.kStatus_SSS_Success:
            raise Exception("Prepare Host sss_key_object_init %s" % status_to_str(status))

        status = apis.sss_key_object_allocate_handle(
            ctypes.byref(key_obj), key_id, apis.kSSS_KeyPart_Default,
            cypher_type, len(key_value), apis.kKeyObject_Mode_Persistent)
        if status != apis.kStatus_SSS_Success:
            raise Exception("sss_key_object_allocate_handle %s" % status_to_str(status))

        status = apis.sss_key_store_set_key(
            ctypes.byref(self.host_keystore.keystore),
            ctypes.byref(key_obj),
            ctypes.byref((ctypes.c_ubyte * len(key_value))(*key_value)),
            len(key_value), len(key_value) * 8, 0, 0)
        if status != apis.kStatus_SSS_Success:
            raise Exception("sss_key_store_set_key %s" % status_to_str(status))

    def _read_scpkey(self):
        """
        Read SCP keys for platform scp session
        :return: None
        """
        enc_key_str = ""
        mac_key_str = ""
        dek_key_str = ""

        if os.path.isfile(self.scpkey):
            with open(self.scpkey, 'r') as scp_file:
                scp_data = scp_file.readlines()
            for line in scp_data:
                line = line.split("#", 2)[0]
                line = line.replace(" ", "")
                line = line.replace("\n", "")
                if "ENC" in line:
                    enc_key_str =  line.replace("ENC", "")
                elif "MAC" in line:
                    mac_key_str =  line.replace("MAC", "")
                elif "DEK" in line:
                    dek_key_str =  line.replace("DEK", "")
            self._enc_key = util.transform_key_to_list(enc_key_str)
            self._mac_key = util.transform_key_to_list(mac_key_str)
            self._dek_key = util.transform_key_to_list(dek_key_str)
        else:
            raise Exception("Invalid scp key file. !!")
