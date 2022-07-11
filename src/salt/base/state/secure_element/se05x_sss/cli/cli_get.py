#
# Copyright 2019,2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import sys
import click
import func_timeout
from sss.getkey import Get
import sss.sss_api as apis
from .cli import get, pass_context, session_open, session_close, \
    log_traceback, TIME_OUT


@get.group()
@pass_context
def ecc(cli_ctx):
    """ Get ECC Keys"""
    cli_ctx.vlog("Get RSA Keys")


@get.group()
@pass_context
def rsa(cli_ctx):
    """ Get RSA Keys """
    cli_ctx.vlog("Get ECC Keys")


@get.command('aes', short_help='Get AES Keys')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('filename', type=click.STRING, metavar='filename')
@click.option('--format', default='', help="Output file format. TEXT can be \"DER\" or \"PEM\"")
@pass_context
def aes(cli_ctx, keyid, filename, format):  # pylint: disable=redefined-builtin
    """ Get AES Keys \n

        keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

        filename = File name to store key. Data can be in PEM or DER format
        based on file extension. By default filename with extension .pem in PEM format
        and others in DER format.
    """
    keyid = int(keyid, 16)
    try:
        session_open(cli_ctx)
        cli_ctx.log("Getting Symmetric Key from KeyID = 0x%08X" % keyid)
        get_object = Get(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, get_object.get_key, (keyid, filename, format))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Retrieved AES Key from KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not retrieve AES Key from KeyID 0x%08X " % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@get.command('cert', short_help='Get Certificate')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('filename', type=click.STRING, metavar='filename')
@click.option('--format', default='', help="Output file format. TEXT can be \"DER\" or \"PEM\"")
@pass_context
def cert(cli_ctx, keyid, filename, format):  # pylint: disable=redefined-builtin
    """ Get Certificate \n

        keyid = 32bit Key ID. Should be in hex format. Example: 401286E6 \n

        filename = File name to store certificate. Data can be in PEM or DER format
        based on file extension. By default filename with extension .pem and .cer in PEM format
        and others in DER format.
    """
    try:
        keyid = int(keyid, 16)
        cli_ctx.log("Getting Certificate from KeyID = 0x%08X" % keyid)
        session_open(cli_ctx)
        get_object = Get(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, get_object.get_key, (keyid, filename, format))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Retrieved Certificate from KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not retrieve Certificate from KeyID 0x%08X " % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@get.command('bin', short_help='Get Binary')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('filename', type=click.STRING, metavar='filename')
@pass_context
def bin(cli_ctx, keyid, filename):  # pylint: disable=redefined-builtin
    """ Get Binary \n

        keyid = 32bit Key ID. Should be in hex format. Example: 401286E6 \n

        filename = File name to store binary data.
    """
    try:
        keyid = int(keyid, 16)
        cli_ctx.log("Getting Binary data from KeyID = 0x%08X" % keyid)
        session_open(cli_ctx)
        get_object = Get(cli_ctx.session)
        data_format = "HEX"
        status = func_timeout.func_timeout(TIME_OUT, get_object.get_key,
                                           (keyid, filename, data_format))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Retrieved Binary from KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not retrieve Binary from KeyID 0x%08X " % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@ecc.command('pub', short_help='Get ECC Pub')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('filename', type=click.STRING, metavar='filename')
@click.option('--format', default='', help="Output file format. TEXT can be \"DER\" or \"PEM\"")
@pass_context
def pub(cli_ctx, keyid, filename, format):  # pylint: disable=function-redefined, redefined-builtin
    """Get ECC Pub \n

       keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

       filename = File name to store key. Data can be in PEM or DER format
       based on file extension. By default filename with extension .pem in PEM format
       and others in DER format.
    """
    try:
        keyid = int(keyid, 16)
        cli_ctx.log("Getting ECC Public Key from KeyID = 0x%08X" % keyid)
        session_open(cli_ctx)
        get_object = Get(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, get_object.get_key, (keyid, filename, format))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Retrieved ECC Public Key from KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not retrieve ECC Public Key from KeyID 0x%08X " % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@ecc.command('pair', short_help='Get ECC pair')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('filename', type=click.STRING, metavar='filename')
@click.option('--format', default='', help="Output file format. TEXT can be \"DER\" or \"PEM\"")
@pass_context
def pair(cli_ctx, keyid, filename, format):  # pylint: disable=function-redefined, redefined-builtin
    """Get ECC Pair \n

       keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

       filename = File name to store key. Data can be in PEM or DER format
       based on file extension. By default filename with extension .pem in PEM format
       and others in DER format.
    """
    try:
        keyid = int(keyid, 16)
        cli_ctx.log("Getting ECC Public Key from KeyID = 0x%08X" % keyid)
        session_open(cli_ctx)
        get_object = Get(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, get_object.get_key, (keyid, filename, format))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Retrieved ECC Public Key from KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not retrieve ECC Public Key from KeyID 0x%08X " % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@rsa.command('pub', short_help='Get RSA Pub')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('filename', type=click.STRING, metavar='filename')
@click.option('--format', default='', help="Output file format. TEXT can be \"DER\" or \"PEM\"")
@pass_context
def pub(cli_ctx, keyid, filename, format):  # pylint: disable=function-redefined, redefined-builtin
    """Get RSA Pub \n

       keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

       filename = File name to store key. Data can be in PEM or DER format
       based on file extension. By default filename with extension .pem in PEM format
       and others in DER format.
    """
    try:
        keyid = int(keyid, 16)
        cli_ctx.log("Getting RSA Public Key from KeyID = 0x%08X" % keyid)
        session_open(cli_ctx)
        get_object = Get(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, get_object.get_key, (keyid, filename, format))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Retrieved RSA Public Key from KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not retrieve RSA Public Key from KeyID 0x%08X " % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@rsa.command('pair', short_help='Get RSA Pair')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('filename', type=click.STRING, metavar='filename')
@click.option('--format', default='', help="Output file format. TEXT can be \"DER\" or \"PEM\"")
@pass_context
def pair(cli_ctx, keyid, filename, format):  # pylint: disable=function-redefined, redefined-builtin
    """Get RSA Pair \n

       keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

       filename = File name to store key. Data can be in PEM or DER format
       based on file extension. By default filename with extension .pem in PEM format
       and others in DER format.
    """
    try:
        keyid = int(keyid, 16)
        cli_ctx.log("Getting RSA Public Key from KeyID = 0x%08X" % keyid)
        session_open(cli_ctx)
        get_object = Get(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, get_object.get_key, (keyid, filename, format))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Retrieved RSA Public Key from KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not retrieve RSA Public Key from KeyID 0x%08X " % (keyid,))
        ret_value = 1
    sys.exit(ret_value)
