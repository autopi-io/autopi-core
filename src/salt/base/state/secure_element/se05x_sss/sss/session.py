#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import ctypes
import os
import pickle
import logging
from . import sss_api as apis
from . import util
from . import const
from . import prepare_host_session
from .util import status_to_str

log = logging.getLogger(__name__)


class Session:  # pylint: disable=too-many-instance-attributes
    """
    Session open and close operation
    """

    def __init__(self, from_pickle=True, host_session=False):
        """
        Constructor
        :param from_pickle: take session parameters from pickle file or not
        :param host_session: whether session is host session or not
        """
        if from_pickle:
            # Check for host session pkl file, To support parallel session with se050 session
            if host_session:
                pkl = util.get_host_session_pkl_path()
            else:
                pkl = util.get_session_pkl_path()
            if os.path.isfile(pkl):
                with open(pkl, 'rb') as pkl_session:
                    session_params = pickle.load(pkl_session)
                try:
                    pkl_v_major = session_params["pkl_v_major"]
                except KeyError:
                    pkl_v_major = 0
                if 1 == pkl_v_major:  # pylint: disable=misplaced-comparison-constant
                    pass
                else:
                    raise const.SSSUsageError("Session data is in old format. "
                                              "Please close and open session again.")

                self.subsystem = session_params['subsystem']
                self._connection_method = session_params['connection_method']
                self._port_name = session_params['port_name']
                self._auth_type = session_params['auth_type']
                self._scpkey = session_params['scpkey']
                self._tunnel = session_params['tunnel']
                self.is_auth = session_params['is_auth']

            else:
                log.error("No open session, try connecting first")
                log.error("Run 'ssscli connect --help' for more information.")
                raise Exception("No open session, try connecting first")
        else:
            self.subsystem = None
            self._connection_method = None
            self._port_name = None
            self._auth_type = None
            self._scpkey = None
            self._tunnel = None
            self.is_auth = None

        self.session_ctx = None
        self.session_policy = None
        self._tunnel_session_ctx = None
        self._connect_ctx = apis.SE_Connect_Ctx_t()
        self.prepare_host_obj = prepare_host_session.PrepareHostSession()

    def session_open(self):
        """
        Session open
        :return: status
        """
        port_name = ctypes.create_string_buffer(1024)
        port_name.value = self._port_name.encode('utf-8')
        self._connect_ctx.portName = apis.String(port_name)
        self._connect_ctx.connType = self._connection_method
        if hasattr(self, "_scpkey"):
            self.prepare_host_obj.scpkey = self._scpkey

        if self._tunnel:
            # open host session
            status = self.prepare_host_obj.setup_counter_part_session()
            if status != apis.kStatus_SSS_Success:
                raise Exception("Could not open host session. Status = %s" % (status,))

            # prepare host for tunnel session
            self._connect_ctx.auth.authType = apis.kSE05x_AuthType_SCP03
            self.prepare_host_obj.prepare_host(self._connect_ctx)

            # apply session policy
            if self.session_policy is not None:
                self._connect_ctx.session_policy = ctypes.pointer(self.session_policy)

            # open tunnel session
            self._tunnel_session_ctx = self._session_open_internal(self._connect_ctx)

            # prepare host for auth session
            sss_connect_ctx = self._connect_ctx
            sss_connect_ctx.auth.authType = self._auth_type
            self.prepare_host_obj.prepare_host(sss_connect_ctx)
            sss_connect_ctx.auth.ctx.scp03.pStatic_ctx = self._connect_ctx.auth.ctx.scp03.pStatic_ctx
            sss_connect_ctx.auth.ctx.scp03.pDyn_ctx = self._connect_ctx.auth.ctx.scp03.pDyn_ctx

            # Initialize tunnel context
            tunnel_ctx = apis.sss_tunnel_t()
            status = apis.sss_tunnel_context_init(ctypes.byref(tunnel_ctx),
                                                  ctypes.byref(self._tunnel_session_ctx))
            if status != apis.kStatus_SSS_Success:
                raise Exception("sss_tunnel_context_init failed. status: %s" % status_to_str(status))

            sss_connect_ctx.connType = apis.kType_SE_Conn_Type_Channel
            sss_connect_ctx.tunnelCtx = ctypes.pointer(tunnel_ctx)

            # Open auth session
            self.session_ctx = self._session_open_internal(sss_connect_ctx)
            self.session_ctx.s_ctx.conn_ctx = self._tunnel_session_ctx.s_ctx.conn_ctx

        else:
            if self.subsystem == apis.kType_SSS_SE_SE05x:
                self._connect_ctx.auth.authType = self._auth_type

                if self._auth_type in [apis.kSE05x_AuthType_UserID,
                                       apis.kSE05x_AuthType_AESKey,
                                       apis.kSE05x_AuthType_ECKey,
                                       apis.kSE05x_AuthType_SCP03]:
                    # open host session and prepare host
                    status = self.prepare_host_obj.setup_counter_part_session()
                    if status != apis.kStatus_SSS_Success:
                        raise Exception("Could not open host session. Status = %s" % (status,))
                    self.prepare_host_obj.prepare_host(self._connect_ctx)

                # apply session policy
                if self.session_policy is not None:
                    self._connect_ctx.session_policy = ctypes.pointer(self.session_policy)

            # open session
            self.session_ctx = self._session_open_internal(self._connect_ctx)

        return apis.kStatus_SSS_Success

    def _session_open_internal(self, connect_ctx):  # pylint: disable=too-many-branches
        """
        Opens session based on connect context parameter
        :param connect_ctx: Connection parameters to open session
        :return: session context
        """
        session_ctx = apis.sss_session_t()
        session_data = None

        if self.subsystem in [apis.kType_SSS_SE_A71CH, apis.kType_SSS_SE_A71CL]:
            session_data = ctypes.byref(connect_ctx)

        elif self.subsystem == apis.kType_SSS_SE_SE05x:
            session_ctx = apis.sss_se05x_session_t()
            session_data = ctypes.byref(connect_ctx)

        elif self.subsystem in [apis.kType_SSS_mbedTLS, apis.kType_SSS_OpenSSL]:
            session_data = connect_ctx.portName

        status = apis.sss_session_open(
            ctypes.byref(session_ctx), self.subsystem, self.prepare_host_obj.auth_id,
            self.prepare_host_obj.connection_type, session_data)

        if status != apis.kStatus_SSS_Success:
            subsystem_str = list(const.SUBSYSTEM_TYPE.keys())[
                list(const.SUBSYSTEM_TYPE.values()).index(self.subsystem)]
            connection_type_str = list(const.CONNECTION_TYPE.keys())[
                list(const.CONNECTION_TYPE.values()).index(self._connection_method)]
            log.warning("#     Connection parameters:")
            log.warning("#     subsystem       : %s", subsystem_str)
            log.warning("#     connection_type : %s", connection_type_str)
            log.warning("#     connection_data : %s", self._port_name)
            raise Exception("sss_session_open failed. status: %s" % status_to_str(status))

        log.debug("sss_session_open %s", status_to_str(status))
        return session_ctx

    def session_close(self):
        """
        Session close
        :return: None
        """
        if self.session_ctx:
            log.debug("Closing port")
            apis.sss_session_close(ctypes.byref(self.session_ctx))
            self.session_ctx = None

        if self.prepare_host_obj.host_keystore:
            self.prepare_host_obj.host_keystore.free()
            self.prepare_host_obj.host_keystore = None

    def refresh_session(self):
        """
        Refresh session
        :return: Status
        """
        status = apis.kStatus_SSS_Fail
        if self.session_policy is not None:
            status = apis.sss_se05x_refresh_session(ctypes.byref(self.session_ctx),
                                                    ctypes.byref(self.session_policy))
        return status
