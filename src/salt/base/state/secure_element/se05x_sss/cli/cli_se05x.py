#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import sys
import func_timeout
from sss.read_id_list import ReadIDList
from sss.se05x import Se05x
import sss.sss_api as apis
from .cli import se05x, pass_context, session_open, session_close, \
    log_traceback, TIME_OUT


@se05x.command('reset', short_help='Reset SE05X')
@pass_context
def reset(cli_ctx):
    """
    Resets the SE05X Secure Module to the initial state.

    This command uses ``Se05x_API_DeleteAll_Iterative`` API of the SE05X
    MW to iterately delete objects provisioned inside the SE.  Because of this,
    some objects are purposefully skipped from deletion.

    It does not use the low level SE05X API ``Se05x_API_DeleteAll``

    For more information, see documentation/implementation of the
    ``Se05x_API_DeleteAll_Iterative`` API.

    """
    try:
        session_open(cli_ctx)
        se05x_obj = Se05x(cli_ctx.session)
        func_timeout.func_timeout(TIME_OUT, se05x_obj.debug_reset, None)
        status = apis.kStatus_SSS_Success
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        ret_value = 0
    else:
        ret_value = 1
    sys.exit(ret_value)


@se05x.command('uid', short_help='Get SE05X Unique ID (18 bytes)')
@pass_context
def uid(cli_ctx):
    """ Get 18 bytes Unique ID from the SE05X Secure Module."""
    try:
        session_open(cli_ctx)
        se05x_obj = Se05x(cli_ctx.session)
        unique_id = func_timeout.func_timeout(TIME_OUT, se05x_obj.get_unique_id, None)
        cli_ctx.log("Unique ID: %s" % (unique_id,))
        status = apis.kStatus_SSS_Success
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        ret_value = 0
    else:
        ret_value = 1
    sys.exit(ret_value)


@se05x.command('certuid', short_help='Get SE05X Cert Unique ID (10 bytes)')
@pass_context
def certuid(cli_ctx):
    """ Get 10 bytes Cert Unique ID from the SE05X Secure Module.
    The cert uid is a subset of the Secure Module Unique Identifier"""
    try:
        session_open(cli_ctx)
        se05x_obj = Se05x(cli_ctx.session)
        cert_uid = func_timeout.func_timeout(TIME_OUT, se05x_obj.get_cert_unique_id, None)
        cli_ctx.log("Cert UID: %s" % (cert_uid,))
        status = apis.kStatus_SSS_Success
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        ret_value = 0
    else:
        ret_value = 1
    sys.exit(ret_value)


@se05x.command('readidlist', short_help='Read contents of SE050')
@pass_context
def readidlist(cli_ctx):
    """ Read contents of SE050"""
    try:
        session_open(cli_ctx)
        read_id_list_obj = ReadIDList(cli_ctx.session)
        func_timeout.func_timeout(TIME_OUT, read_id_list_obj.do_read_id_list, None)
        status = apis.kStatus_SSS_Success
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        ret_value = 0
    else:
        ret_value = 1
    sys.exit(ret_value)

@se05x.command('getrng', short_help='Get SE05X random number (10 bytes)')
@pass_context
def uid(cli_ctx):
    """ Get 10 bytes random number from the SE05X Secure Module."""
    try:
        session_open(cli_ctx)
        se05x_obj = Se05x(cli_ctx.session)
        rngdata = func_timeout.func_timeout(TIME_OUT, se05x_obj.get_random_number, None)
        cli_ctx.log("Random number: %s" % (rngdata,))
        status = apis.kStatus_SSS_Success
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        ret_value = 0
    else:
        ret_value = 1
    sys.exit(ret_value)
