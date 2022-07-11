#
# Copyright 2019,2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import sys
import click
import func_timeout
import sss.sss_api as apis
from sss import session
from sss.genkey import Generate
from sss.const import ECC_CURVE_TYPE
from sss.policy import Policy

from .cli import generate, pass_context, session_close, \
    log_traceback, TIME_OUT, TIME_OUT_RSA

RSA_N_BITS = ["1024", "2048", "3072", "4096"]


@generate.command('ecc', short_help='Generate ECC Key')
@pass_context
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('curvetype', type=click.Choice(list(ECC_CURVE_TYPE.keys())))
@click.option('--policy_name', type=str, default='', help="File name of the policy to be applied")
def ecc(cli_ctx, keyid, curvetype, policy_name):
    """ Generate ECC Key \n

    keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

    curvetype = ECC Curve type. can be one of "NIST_P192, NIST_P224, NIST_P256,
    NIST_P384, NIST_P521, Brainpool160, Brainpool192, Brainpool224, Brainpool256,
    Brainpool320, Brainpool384, Brainpool512, Secp160k1, Secp192k1, Secp224k1, Secp256k1,
    ED_25519, MONT_DH_25519, MONT_DH_448"

    """
    try:
        keyid = int(keyid, 16)
        if policy_name != '':
            policy_obj = Policy()
            policy_params = policy_obj.get_object_policy(policy_name)
            policy = policy_obj.convert_obj_policy_to_ctype(policy_params)
        else:
            policy = None
        cli_ctx.log("Generating ECC Key Pair at KeyID = 0x%08X,  curvetype=%s" %
                    (keyid, curvetype))

        cli_ctx.session = session.Session()
        if cli_ctx.session.is_auth and \
            curvetype not in ["NIST_P256", "NIST_P384"]:
            raise Exception("ERROR! Only NIST_P256 and NIST_P384 are supported for AUTH")

        func_timeout.func_timeout(TIME_OUT, cli_ctx.session.session_open, None)

        gen_obj = Generate(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, gen_obj.gen_ecc_pair,
                                           (keyid, ECC_CURVE_TYPE[curvetype], policy))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Generated ECC Key Pair at KeyID 0x%08X " % (keyid,))
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not generate ECC Key Pair at KeyID 0x%08X " % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@generate.command('rsa', short_help='Generate RSA Key')
@pass_context
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('bits', type=click.Choice(RSA_N_BITS))
@click.option('--policy_name', type=str, default='', help="File name of the policy to be applied")
def rsa(cli_ctx, keyid, bits, policy_name):
    """ Generate RSA Key \n
    keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

    bits = Number of bits. can be one of "1024, 2048, 3072, 4096"

    """
    try:
        keyid = int(keyid, 16)
        if policy_name != '':
            policy_obj = Policy()
            policy_params = policy_obj.get_object_policy(policy_name)
            policy = policy_obj.convert_obj_policy_to_ctype(policy_params)
        else:
            policy = None
        cli_ctx.log("Generating RSA Key Pair at KeyID = 0x%08X,  bits=%s" %
                    (keyid, bits))
        cli_ctx.session = session.Session()
        if cli_ctx.session.is_auth:
            raise Exception("ERROR! RSA is not supported for AUTH")

        func_timeout.func_timeout(TIME_OUT, cli_ctx.session.session_open, None)
        gen_obj = Generate(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT_RSA, gen_obj.gen_rsa_pair,
                                           (keyid, int(bits), policy))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Generated RSA Key Pair at KeyID = 0x%08X " % (keyid,))
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not generate RSA Key Pair at KeyID 0x%08X " % (keyid,))
        ret_value = 1
    sys.exit(ret_value)


@generate.command('pub', short_help='Generate ECC Public Key to file')
@pass_context
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('curvetype', type=click.Choice(list(ECC_CURVE_TYPE.keys())))
@click.argument('filename', type=click.STRING)
@click.option('--format', default='', help="Output file format. TEXT can be \"DER\" or \"PEM\"")
@click.option('--policy_name', type=str, default='', help="File name of the policy to be applied")
def pub(cli_ctx, keyid, curvetype, filename, format, policy_name):  # pylint: disable=redefined-builtin
    """
    Generate ECC Public Key to file \n

    keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

    curvetype = ECC Curve type. can be one of "NIST_P192, NIST_P224, NIST_P256,
    NIST_P384, NIST_P521, Brainpool160, Brainpool192, Brainpool224, Brainpool256,
    Brainpool320, Brainpool384, Brainpool512, Secp160k1, Secp192k1, Secp224k1, Secp256k1,
    ED_25519, MONT_DH_25519, MONT_DH_448 \n

    filename = File name to store public key. Data can be in PEM or DER format
    based on file extension. By default filename with extension .pem in PEM format
    and others in DER format. \n
    """
    try:
        keyid = int(keyid, 16)
        if policy_name != '':
            policy_obj = Policy()
            policy_params = policy_obj.get_object_policy(policy_name)
            policy = policy_obj.convert_obj_policy_to_ctype(policy_params)
        else:
            policy = None
        cli_ctx.session = session.Session()
        if cli_ctx.session.is_auth and \
            curvetype not in ["NIST_P256", "NIST_P384"]:
            raise Exception("ERROR! Only NIST_P256 and NIST_P384 are supported for AUTH")
        func_timeout.func_timeout(TIME_OUT, cli_ctx.session.session_open, None)
        gen_obj = Generate(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, gen_obj.gen_ecc_public,
                                           (keyid, ECC_CURVE_TYPE[curvetype],
                                            filename, policy, format))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Generated ECC Public Key at KeyID = 0x%08X " % (keyid,))
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not generate ECC Public Key at KeyID 0x%08X " % (keyid,))
        ret_value = 1
    sys.exit(ret_value)
