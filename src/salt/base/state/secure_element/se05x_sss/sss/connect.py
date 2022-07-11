#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import os
import logging
import pickle
from . import util
from . import sss_api as apis
log = logging.getLogger(__name__)


def do_open_session(subsystem, connection_method, port_name, host_session=False,
                    auth_type=apis.kSE05x_AuthType_None, scpkey='', tunnel = False,
                    is_auth = False):
    """
    Stores session open parameter in pkl file format
    :param subsystem: SE050, A71CH, A71CL, MBEDTLS, OPENSSL
    :param connection_method: vcom, t1oi2c, sci2c, jrcpv1, jrcpv2, pcsc
    :param port_name: connection data. eg: COM6, 192.168.1.1:8050, None
    :param host_session: session is host session or not
    :param auth_type: authentication type for session open. eg: None, userid, aeskey,
    eckey, platformscp
    :param scpkey: scpkey file path for PlatforSCP session
    :return: None
    """
    session_params = {
        'pkl_v_major': 1,
        'pkl_v_minor': 0,
        'subsystem': subsystem,
        'connection_method': connection_method,
        'port_name': port_name,
        'auth_type': auth_type,
        'scpkey': scpkey,
        'tunnel': tunnel,
        'is_auth': is_auth}

    # Keep Host session parameters separate to support parallel session with se050
    if host_session:
        if not os.path.isfile(util.get_host_session_pkl_path()):
            with open(util.get_host_session_pkl_path(), 'wb+') as pkl_session:
                pickle.dump(session_params, pkl_session)
        else:
            log.warning('Session already open, close current session first')
    else:
        if not os.path.isfile(util.get_session_pkl_path()):
            with open(util.get_session_pkl_path(), 'wb+') as pkl_session:
                pickle.dump(session_params, pkl_session)
        else:
            log.warning('Session already open, close current session first')


def do_close_session():
    """
    Erase session open parameters
    :return: None
    """
    pkl = util.get_session_pkl_path()
    host_pkl = util.get_host_session_pkl_path()
    if os.path.isfile(host_pkl):
        os.remove(host_pkl)
    if os.path.isfile(pkl):
        os.remove(pkl)
    else:
        log.warning('No open session. Nothing to do')
