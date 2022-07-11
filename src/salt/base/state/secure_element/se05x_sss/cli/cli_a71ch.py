#
# Copyright 2019,2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import sys
import func_timeout
from sss.a71ch import A71CH
import sss.sss_api as apis
from .cli import a71ch, pass_context, session_open, session_close, \
    log_traceback, TIME_OUT


@a71ch.command('reset', short_help='Debug Reset A71CH')
@pass_context
def reset(cli_ctx):
    """ Resets the A71CH Secure Module to the initial state."""
    try:
        session_open(cli_ctx)
        a71ch_obj = A71CH(cli_ctx.session)
        func_timeout.func_timeout(TIME_OUT, a71ch_obj.debug_reset, None)
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


@a71ch.command('uid', short_help='Get A71CH Unique ID')
@pass_context
def uid(cli_ctx):
    """ Get uid from the A71CH Secure Module."""
    try:
        session_open(cli_ctx)
        a71ch_obj = A71CH(cli_ctx.session)
        unique_id = func_timeout.func_timeout(TIME_OUT, a71ch_obj.get_unique_id, None)
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
