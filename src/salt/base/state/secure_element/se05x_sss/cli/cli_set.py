#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import sys
import click
import func_timeout
from sss.setkey import Set
from sss.policy import Policy
import sss.sss_api as apis
from .cli import set, pass_context, session_open, session_close, log_traceback, TIME_OUT  # pylint: disable=redefined-builtin


@set.group()
@pass_context
def ecc(cli_ctx):
    """Set ECC Keys"""
    cli_ctx.vlog("Set ECC Keys")


@set.group()
@pass_context
def rsa(cli_ctx):
    """Set RSA Keys"""
    cli_ctx.vlog("Set RSA Keys")


@set.command('hmac', short_help='Set HMAC Keys')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('key', type=str, metavar='key')
@pass_context
def hmac(cli_ctx, keyid, key):
    """ Set HMAC Keys \n

        keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

        key = Can be in file or raw key in DER or HEX format\n
    """
    try:
        keyid = int(keyid, 16)
        cli_ctx.log("Injecting HMAC Key at KeyID = 0x%08X" % keyid)
        session_open(cli_ctx)
        set_object = Set(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, set_object.do_set_hmac_key, (keyid, key, None))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Injected HMAC Key at KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Inject HMAC Key at KeyID 0x%08X " % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@set.command('aes', short_help='Set AES Keys')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('key', type=str, metavar='key')
@click.option('--policy_name', type=str, default='', help="File name of the policy to be applied")
@pass_context
def aes(cli_ctx, keyid, key, policy_name):
    """ Set AES Keys \n

        keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

        key = Can be in file or raw key in DER or HEX format\n
    """
    try:
        keyid = int(keyid, 16)
        if policy_name != '':
            policy_obj = Policy()
            policy_params = policy_obj.get_object_policy(policy_name)
            policy = policy_obj.convert_obj_policy_to_ctype(policy_params)
        else:
            policy = None
        cli_ctx.log("Injecting AES Key at KeyID = 0x%08X" % keyid)
        session_open(cli_ctx)
        set_object = Set(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, set_object.do_set_aes_key,
                                           (keyid, key, policy))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Injected AES Key at KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Inject AES Key at KeyID 0x%08X " % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@set.command('cert', short_help='Set Certificate')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('key', type=str, metavar='key')
@click.option('--format', default='',
              help="Input certificate format. TEXT can be \"DER\" or \"PEM\"")
@click.option('--policy_name', type=str, default='', help="File name of the policy to be applied")
@pass_context
def cert(cli_ctx, keyid, key, format, policy_name):  # pylint: disable=redefined-builtin
    """ Set Certificate \n

        keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

        key = Can be raw certificate (DER format) or in file.
        For file, by default filename with extension .pem and .cer considered
        as PEM format and others as DER format.\n
    """
    try:
        keyid = int(keyid, 16)
        if policy_name != '':
            policy_obj = Policy()
            policy_params = policy_obj.get_object_policy(policy_name)
            policy = policy_obj.convert_obj_policy_to_ctype(policy_params)
        else:
            policy = None
        cli_ctx.log("Injecting Certificate at KeyID = 0x%08X" % keyid)
        session_open(cli_ctx)
        set_object = Set(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, set_object.do_set_cert,
                                           (keyid, key, policy, format))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Injected Certificate at KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Inject Certificate at KeyID 0x%08X "
                    % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@set.command('bin', short_help='Set Binary')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('data', type=str, metavar='data')
@click.option('--policy_name', type=str, default='', help="File name of the policy to be applied")
@pass_context
def bin(cli_ctx, keyid, data, policy_name):  # pylint: disable=redefined-builtin
    """ Set Certificate \n

        keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

        data = Can be raw binary or in file \n
    """
    try:
        keyid = int(keyid, 16)
        if policy_name != '':
            policy_obj = Policy()
            policy_params = policy_obj.get_object_policy(policy_name)
            policy = policy_obj.convert_obj_policy_to_ctype(policy_params)
        else:
            policy = None
        cli_ctx.log("Injecting Binary at KeyID = 0x%08X" % keyid)
        session_open(cli_ctx)
        set_object = Set(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, set_object.do_set_bin,
                                           (keyid, data, policy))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Injected Binary at KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Inject Binary at KeyID 0x%08X "
                    % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@ecc.command('pub', short_help='Set ECC Public Keys')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('key', type=str, metavar='key')
@click.option('--format', default='',
              help="Input key format. TEXT can be \"DER\" or \"PEM\"")
@click.option('--policy_name', type=str, default='', help="File name of the policy to be applied")
@pass_context
def pub(cli_ctx, keyid, key, format, policy_name):  # pylint: disable=redefined-builtin
    """ Set ECC Public Keys \n

        keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

        key = Can be raw key (DER format) or in file.
        For file, by default filename with extension .pem considered as PEM format
        and others as DER format.\n
    """
    try:
        keyid = int(keyid, 16)
        if policy_name != '':
            policy_obj = Policy()
            policy_params = policy_obj.get_object_policy(policy_name)
            policy = policy_obj.convert_obj_policy_to_ctype(policy_params)
        else:
            policy = None
        cli_ctx.log("Injecting ECC Public Key at KeyID = 0x%08X" % (keyid,))
        session_open(cli_ctx)
        set_object = Set(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, set_object.do_set_ecc_pub_key,
                                           (keyid, key, policy, format))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Injected ECC Public Key at KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Inject ECC Public Key at KeyID 0x%08X "
                    % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@ecc.command('pair', short_help='Set ECC Key pair')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('key', type=str, metavar='key')
@click.option('--format', default='',
              help="Input key format. TEXT can be \"DER\" or \"PEM\"")
@click.option('--policy_name', type=str, default='', help="File name of the policy to be applied")
@pass_context
def pair(cli_ctx, keyid, key, format, policy_name):  # pylint: disable=redefined-builtin
    """ Set ECC Key pair \n

        keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

        key = Can be raw key (DER format) or in file.
        For file, by default filename with extension .pem considered as PEM format
        and others as DER format.\n
    """
    try:
        keyid = int(keyid, 16)
        if policy_name != '':
            policy_obj = Policy()
            policy_params = policy_obj.get_object_policy(policy_name)
            policy = policy_obj.convert_obj_policy_to_ctype(policy_params)
        else:
            policy = None
        cli_ctx.log("Injecting ECC Key Pair at KeyID = 0x%08X" % (keyid,))
        session_open(cli_ctx)
        set_object = Set(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, set_object.do_set_ecc_key_pair,
                                           (keyid, key, policy, format))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Injected ECC Key Pair at KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Inject ECC Pair at KeyID 0x%08X "
                    % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@rsa.command('pub', short_help='Set RSA Public Keys')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('key', type=str, metavar='key')
@click.option('--format', default='',
              help="Input key format. TEXT can be \"DER\" or \"PEM\"")
@click.option('--policy_name', type=str, default='', help="File name of the policy to be applied")
@pass_context
def pub(cli_ctx, keyid, key, format, policy_name):  # pylint: disable=function-redefined, redefined-builtin
    """ Set RSA Public Keys \n

        keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

        key = Can be raw key (DER format) or in file.
        For file, by default filename with extension .pem considered as PEM format
        and others as DER format.\n
    """
    try:
        keyid = int(keyid, 16)
        if policy_name != '':
            policy_obj = Policy()
            policy_params = policy_obj.get_object_policy(policy_name)
            policy = policy_obj.convert_obj_policy_to_ctype(policy_params)
        else:
            policy = None
        cli_ctx.log("Injecting RSA Public Key at KeyID = 0x%08X" % keyid)
        session_open(cli_ctx)
        set_object = Set(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, set_object.do_set_rsa_pub_key,
                                           (keyid, key, policy, format))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Injected RSA Public Key at KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Inject RSA Public Key at KeyID 0x%08X "
                    % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@rsa.command('pair', short_help='Set RSA Key Pair')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('key', type=str, metavar='key')
@click.option('--format', default='',
              help="Input key format. TEXT can be \"DER\" or \"PEM\"")
@click.option('--policy_name', type=str, default='', help="File name of the policy to be applied")
@pass_context
def pair(cli_ctx, keyid, key, format, policy_name):  # pylint: disable=function-redefined, redefined-builtin
    """ Set RSA Key Pair \n

        keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

        key = Can be raw key (DER format) or in file.
        For file, by default filename with extension .pem considered as PEM format
        and others as DER format.\n
    """
    try:
        keyid = int(keyid, 16)
        if policy_name != '':
            policy_obj = Policy()
            policy_params = policy_obj.get_object_policy(policy_name)
            policy = policy_obj.convert_obj_policy_to_ctype(policy_params)
        else:
            policy = None
        cli_ctx.log("Injecting RSA Key Pair at KeyID = 0x%08X" % keyid)
        session_open(cli_ctx)
        set_object = Set(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, set_object.do_set_rsa_key_pair,
                                           (keyid, key, policy, format))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Injected RSA Key Pair at KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Inject RSA Pair at KeyID 0x%08X "
                    % (keyid,))
        ret_value = 1
    sys.exit(ret_value)
