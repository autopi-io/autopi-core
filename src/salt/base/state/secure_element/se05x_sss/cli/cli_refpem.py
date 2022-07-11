#
# Copyright 2019,2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import sys
import click
import func_timeout
from sss.refkey import RefPem
import sss.sss_api as apis
from .cli import refpem, pass_context, session_open, session_close, \
    log_traceback, TIME_OUT, TIME_OUT_RSA


@refpem.group()
@pass_context
def ecc(cli_ctx):
    """Refpem ECC Keys"""
    cli_ctx.vlog("Refpem ECC Keys")


@refpem.group()
@pass_context
def rsa(cli_ctx):
    """Refpem RSA Keys"""
    cli_ctx.vlog("Refpem RSA Keys")


@ecc.command('pair', short_help='Create reference PEM file for ECC Pair')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('filename', type=str, metavar='filename')
@click.option('--format', default='',
              help="Output file format. TEXT can be \"DER\" or \"PEM\" or \"PKCS12\"")
@click.option('--password', default="", type=str, help="Password used for PKCS12 format.")
@click.option('--cert', default="", type=str, help="Certificate for PKCS12 format.")
@pass_context
def pair(cli_ctx, keyid, filename, format, password, cert):  # pylint: disable=function-redefined, redefined-builtin
    """Create reference PEM file for ECC Pair \n

       keyid = 32bit Key ID. Should be in hex format. Example: 0x20E8A001 \n

       filename = File name to store key. Can be in PEM or DER or PKCS12 format
       based on file extension. By default filename with extension .pem in PEM format,
       .pfx or .p12 in PKCS12 format and others in DER format.
       """
    session_status = apis.kStatus_SSS_Fail
    try:
        keyid = int(keyid, 16)
        if (filename.endswith('.pfx') or filename.endswith('.p12') or format == "PKCS12"):
            if password == "":
                raise Exception("Password Required for PKCS12 format. "
                                "Use '--password' flag to enter password")
            if cert == "":
                raise Exception("Certificate Required for PKCS12 format. "
                                "Use '--cert' flag for certificate input")
        try:
            session_open(cli_ctx)
            refpem_obj = RefPem(cli_ctx.session)
            status = func_timeout.func_timeout(TIME_OUT, refpem_obj.do_ecc_refpem_pair,
                                               (keyid, filename, format, password, cert))
        except func_timeout.FunctionTimedOut as timeout_exc:
            log_traceback(cli_ctx, timeout_exc.getMsg())
            status = apis.kStatus_SSS_Fail
        except Exception as exc:  # pylint: disable=broad-except
            log_traceback(cli_ctx, exc)
            status = apis.kStatus_SSS_Fail
        session_status = session_close(cli_ctx)

    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Created reference key for ECC Pair from KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Create reference key for ECC Pair from KeyID 0x%08X "
                    % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@ecc.command('pub', short_help='Create reference PEM file for ECC Pub')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('filename', type=str, metavar='filename')
@click.option('--format', default='',
              help="Output file format. TEXT can be \"DER\" or \"PEM\" or \"PKCS12\"")
@click.option('--password', default="", type=str, help="Password used for PKCS12 format.")
@click.option('--cert', default="", type=str, help="Certificate for PKCS12 format.")
@pass_context
def pub(cli_ctx, keyid, filename, format, password, cert):  # pylint: disable=redefined-builtin
    """Create reference PEM file for ECC Pub \n

       keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

       filename = File name to store key. Data Can be in PEM or DER format or PKCS12 format
       based on file extension. By default filename with extension .pem in PEM format,
       .pfx or .p12 in PKCS12 format and others in DER format.

    """
    session_status = apis.kStatus_SSS_Fail
    try:
        keyid = int(keyid, 16)
        if (filename.endswith('.pfx') or filename.endswith('.p12') or format == "PKCS12"):
            if password == "":
                raise Exception("Password Required for PKCS12 format. "
                                "Use '--password' flag to enter password")
            if cert == "":
                raise Exception("Certificate Required for PKCS12 format. "
                                "Use '--cert' flag for certificate input")
        try:
            session_open(cli_ctx)
            refpem_obj = RefPem(cli_ctx.session)
            status = func_timeout.func_timeout(TIME_OUT, refpem_obj.do_ecc_refpem_pub,
                                               (keyid, filename, format, password, cert))
        except func_timeout.FunctionTimedOut as timeout_exc:
            log_traceback(cli_ctx, timeout_exc.getMsg())
            status = apis.kStatus_SSS_Fail
        except Exception as exc:  # pylint: disable=broad-except
            log_traceback(cli_ctx, exc)
            status = apis.kStatus_SSS_Fail
        session_status = session_close(cli_ctx)
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Created reference key for ECC Public Key from KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Create reference key for ECC Public Key from KeyID 0x%08X "
                    % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@rsa.command('pair', short_help='Create reference PEM file for RSA Pair')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('filename', type=str, metavar='filename')
@click.option('--format', default='',
              help="Output file format. TEXT can be \"DER\" or \"PEM\" or \"PKCS12\"")
@click.option('--password', default="", type=str, help="Password used for PKCS12 format.")
@click.option('--cert', default="", type=str, help="Certificate for PKCS12 format.")
@pass_context
def pair(cli_ctx, keyid, filename, format, password, cert):  # pylint: disable=function-redefined, redefined-builtin
    """Create reference PEM file for RSA Pair \n

       keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

       filename = File name to store key. Data Can be in PEM or DER format or PKCS12 format
       based on file extension. By default filename with extension .pem in PEM format,
       .pfx or .p12 in PKCS12 format and others in DER format.
    """
    session_status = apis.kStatus_SSS_Fail
    try:
        keyid = int(keyid, 16)
        if (filename.endswith('.pfx') or filename.endswith('.p12') or format == "PKCS12"):
            if password == "":
                raise Exception("Password Required for PKCS12 format. "
                                "Use '--password' flag to enter password")
            if cert == "":
                raise Exception("Certificate Required for PKCS12 format. "
                                "Use '--cert' flag for certificate input")
        try:
            session_open(cli_ctx)
            refpem_obj = RefPem(cli_ctx.session)
            status = func_timeout.func_timeout(TIME_OUT_RSA, refpem_obj.do_rsa_refpem_pair,
                                               (keyid, filename, format, password, cert))
        except func_timeout.FunctionTimedOut as timeout_exc:
            log_traceback(cli_ctx, timeout_exc.getMsg())
            status = apis.kStatus_SSS_Fail
        except Exception as exc:  # pylint: disable=broad-except
            log_traceback(cli_ctx, exc)
            status = apis.kStatus_SSS_Fail
        session_status = session_close(cli_ctx)

    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Created reference key for RSA Pair from KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Create reference key for RSA Pair from KeyID 0x%08X "
                    % (keyid,))
        ret_value = 1
    sys.exit(ret_value)
