#
# Copyright 2019,2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import os
import sys
import traceback
import logging
import click
import func_timeout

if '-v' in sys.argv or '--verbose' in sys.argv:
    logging.basicConfig(level=logging.DEBUG)

try:
    from sss.erasekey import Erase
    from sss.connect import do_open_session, do_close_session
    from sss.sign import Sign
    from sss.verify import Verify
    from sss.crypt import Crypt
    from sss import const
    from sss import session
    from sss import sss_api as apis
    from sss import plugandtrust_ver
    from sss.const import AUTH_TYPE_MAP, CRYPT_ALGO
except ImportError:
    print("Error: Library sssapisw not found !! Build sssapisw first !!")
    sys.exit(1)

TIME_OUT = 60  # Time out in seconds
TIME_OUT_RSA = 180  # Longer timeout for RSA key
VERSION = plugandtrust_ver.PLUGANDTRUST_VER_STR


class Context:
    """
    Logs a message to stdout
    """
    def __init__(self):
        self.verbose = False
        self.logger = logging.getLogger(__name__)

    @classmethod
    def log(cls, msg, *args):
        """Logs a message to stdout."""
        if args:
            msg %= args
        print(msg)  # pylint: disable=superfluous-parens

    def vlog(self, msg, *args):
        """Logs a message to stdout only if verbose is enabled."""
        if self.verbose:
            self.log(msg, *args)

    def error(self, msg):
        """Logs error messages"""
        self.logger.error(msg)


pass_context = click.make_pass_decorator(Context, ensure=True)  # pylint: disable=invalid-name


def log_traceback(cli_ctx, ex):
    """ Logs the call hierarchy. Called in case of error
    """
    cli_ctx.error(ex)
    output_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "..", "output")

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    error_file = output_dir + os.sep + "error_log.txt"

    with open(error_file, 'a+') as err_write:
        err_write.write("\n\n")
        traceback.print_exc(None, err_write)
        err_write.close()


def session_open(cli_ctx):
    """ Session open
    """
    cli_ctx.session = session.Session()
    func_timeout.func_timeout(TIME_OUT, cli_ctx.session.session_open, None)


def session_close(cli_ctx):
    """
    Session close
    :param cli_ctx: Holds cli parameters
    :return: status
    """
    try:
        func_timeout.func_timeout(TIME_OUT, cli_ctx.session.session_close, None)
        status = apis.kStatus_SSS_Success
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    return status


@click.group()
@click.option('--verbose', '-v', is_flag=True,
              help='Enables verbose mode.')
@click.version_option(version=VERSION)
@click.pass_context
def cli(cli_ctx, verbose):
    """Command line interface for SE050"""
    # Top level Group
    cli_ctx.verbose = verbose


@cli.group()
@pass_context
def generate(cli_ctx):
    """ Generate ECC/RSA Key pair """
    cli_ctx.vlog("Generate ECC/RSA Key pair")


@cli.group()
@pass_context
def set(cli_ctx):  # pylint: disable=redefined-builtin
    """ Set ECC/RSA/AES Keys or certificates """
    cli_ctx.vlog("Set ECC/RSA/AES Keys or certificates")


@cli.command('erase', short_help='Erase ECC/RSA/AES Keys or Certificate (contents)')
@click.argument('keyid', type=str, metavar='keyid')
@pass_context
def erase(cli_ctx, keyid):
    """ Erase ECC/RSA/AES Keys or Certificate (contents) \n

        keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n
    """
    try:
        keyid = int(keyid, 16)
        cli_ctx.log("Erasing Key entry from KeyID = 0x%08x" % keyid)
        session_open(cli_ctx)
        erase_obj = Erase(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, erase_obj.erase_key, (keyid, ))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Erased Key entry from KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Erase Key Entry from KeyID 0x%08X " % keyid)
        ret_value = 1
    sys.exit(ret_value)


@cli.group()
@pass_context
def get(cli_ctx):
    """ Get ECC/RSA/AES Keys or certificates """
    cli_ctx.vlog("Get ECC/RSA/AES Keys or certificates")


@cli.group()
@pass_context
def cloud(cli_ctx):
    """ (Not Implemented) Cloud Specific utilities.

    This helps to handle GCP/AWS/Watson specific settings."""
    cli_ctx.vlog("Cloud Specific utilities")


@cli.command()
@click.argument('subsystem', type=click.Choice(list(const.SUBSYSTEM_TYPE.keys())),
                metavar='subsystem')
@click.argument('method', type=click.Choice(list(const.CONNECTION_TYPE.keys())), metavar='method')
@click.argument('port_name', type=str, metavar='port_name')
@click.option('--auth_type', default='None', type=click.Choice(list(AUTH_TYPE_MAP.keys())),
              help="Authentication type. Default is \"None\". Can be one of \"None, UserID, "
                   "ECKey, AESKey, PlatformSCP, UserID_PlatformSCP, ECKey_PlatformSCP, "
                   "AESKey_PlatformSCP\"")
@click.option('--scpkey', default='', type=str,
              help="File path of the platformscp keys for platformscp session")
@pass_context
def connect(cli_ctx, subsystem, method, port_name, auth_type, scpkey):
    """ Open Session.\n

    subsystem = Security subsystem is selected to be used. Can be one of "se05x, auth, a71ch,
    mbedtls, openssl"\n

    method = Connection method to the system. Can be one of "none, sci2c, vcom, t1oi2c, jrcpv1,
    jrcpv2, pcsc"\n

    port_name = Subsystem specific connection parameters. Example: COM6, 127.0.0.1:8050.
    Use "None" where not applicable. e.g. SCI2C/T1oI2C. Default i2c port (i2c-1) will be used
    for port name = "None".
    """
    if subsystem == "se050":
        cli_ctx.log("Warning: subsystem 'se050' has been depreciated. Use 'se05x' instead")
    if auth_type in ["PlatformSCP", "UserID_PlatformSCP", "ECKey_PlatformSCP",
                     "AESKey_PlatformSCP"]:
        if scpkey == '':
            cli_ctx.log("scpkey file is required for PlatformSCP session. "
                        "Use option '--scpkey' to enter scp key file path.")
            return
        if not os.path.isfile(scpkey):
            cli_ctx.log("Invalid scpkey file ! "
                        "Use option '--scpkey' to enter scp key file path.")
            return

    cli_ctx.vlog("Open Session")
    is_auth = bool(subsystem == "auth")
    do_open_session(const.SUBSYSTEM_TYPE[subsystem],
                    const.CONNECTION_TYPE[method],
                    port_name, False, AUTH_TYPE_MAP[auth_type][0], scpkey,
                    AUTH_TYPE_MAP[auth_type][2],
                    is_auth)


@cli.command()
@pass_context
def disconnect(cli_ctx):
    """ Close session. """
    cli_ctx.vlog("Close session")
    do_close_session()


@cli.group()
@pass_context
def se05x(cli_ctx):
    """ SE05X specific commands """
    cli_ctx.vlog("SE05X specific commands")


@cli.group()
@pass_context
def a71ch(cli_ctx):
    """ A71CH specific commands """
    cli_ctx.vlog("A71CH specific commands")


@cli.command('sign', short_help='Sign Operation')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('input_file', type=str, metavar='input_file')
@click.argument('signature_file', type=str, metavar='signature_file')
@click.option('--informat', default='',
              help="Input format. TEXT can be \"DER\" or \"PEM\".")
@click.option('--outformat', default='',
              help="Output file format. TEXT can be \"DER\" or \"PEM\"")
# pylint: disable=too-many-arguments
@click.option('--hashalgo', default='',
              help='Hash algorithm. TEXT can be one of \"SHA1, SHA224, SHA256, SHA384, '
                   'SHA512, \nRSASSA_PKCS1_V1_5_SHA1, RSASSA_PKCS1_V1_5_SHA224, \n'
                   'RSASSA_PKCS1_V1_5_SHA256, \nRSASSA_PKCS1_V1_5_SHA384, \n'
                   'RSASSA_PKCS1_V1_5_SHA512, \nRSASSA_PKCS1_PSS_MGF1_SHA1, \n'
                   'RSASSA_PKCS1_PSS_MGF1_SHA224, RSASSA_PKCS1_PSS_MGF1_SHA256, '
                   'RSASSA_PKCS1_PSS_MGF1_SHA384, RSASSA_PKCS1_PSS_MGF1_SHA512\"')
# pylint: enable=too-many-arguments
@pass_context
def sign(cli_ctx, keyid, input_file, signature_file, informat, outformat, hashalgo):
    """ Sign Operation \n
        keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

        input_file = Input file to sign.
        By default filename with extension .pem and .cer considered as PEM format,
        others as DER/BINARY format.\n

        signature_file = File name to store signature data.
        By default filename with extension .pem in PEM format and others in DER format.
        """
    try:
        keyid = int(keyid, 16)
        session_open(cli_ctx)
        sign_obj = Sign(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, sign_obj.do_signature,
                                           (keyid, input_file, signature_file,
                                            informat, outformat, hashalgo))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Signed from KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Sign from KeyID 0x%08X " % keyid)
        ret_value = 1
    sys.exit(ret_value)


@cli.command('verify', short_help='verify Operation')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('input_file', type=str, metavar='input_file')
@click.argument('signature_file', type=str, metavar='signature_file')
@click.option('--format', default='',
              help="input_file and signature file format. TEXT can be \"DER\" or \"PEM\"")
# pylint: disable=too-many-arguments
@click.option('--hashalgo', default='',
              help='Hash algorithm. TEXT can be one of \"SHA1, SHA224, SHA256, SHA384, '
                   'SHA512, \nRSASSA_PKCS1_V1_5_SHA1, RSASSA_PKCS1_V1_5_SHA224, \n'
                   'RSASSA_PKCS1_V1_5_SHA256, \nRSASSA_PKCS1_V1_5_SHA384, \n'
                   'RSASSA_PKCS1_V1_5_SHA512, \nRSASSA_PKCS1_PSS_MGF1_SHA1, \n'
                   'RSASSA_PKCS1_PSS_MGF1_SHA224, RSASSA_PKCS1_PSS_MGF1_SHA256, '
                   'RSASSA_PKCS1_PSS_MGF1_SHA384, RSASSA_PKCS1_PSS_MGF1_SHA512\"')
# pylint: enable=too-many-arguments
@pass_context
def verify(cli_ctx, keyid, input_file, signature_file, format, hashalgo):  # pylint: disable=redefined-builtin
    """ verify operation \n
        keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

        input_file = Input file to verify.
        By default filename with extension .pem and .cer considered as PEM format,
        others as DER/BINARY format.\n

        filename = signature_file data file for verification.
        By default filename with extension .pem in PEM format and others in DER format.
    """
    try:
        keyid = int(keyid, 16)
        session_open(cli_ctx)
        verify_obj = Verify(cli_ctx.session)
        status = func_timeout.func_timeout(TIME_OUT, verify_obj.do_verification,
                                           (keyid, input_file, signature_file, format, hashalgo))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Verified from KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Verify from KeyID 0x%08X " % keyid)
        ret_value = 1
    sys.exit(ret_value)


@cli.command('encrypt', short_help='Encrypt Operation')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('input_data', type=str, metavar='input_data')
@click.argument('filename', type=str, metavar='filename')
@click.option('--algo', default='',
              help='Algorithm. TEXT can be one of \"oaep\", \"rsaes\"')
@pass_context
def encrypt(cli_ctx, keyid, input_data, filename, algo):
    """ Sign Operation \n
        keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

        input_data = Input data to Encrypt. can be raw string or in file.\n

        filename = Output file name to store encrypted data.
        Encrypted data will be stored in DER format.\n
        """
    try:
        keyid = int(keyid, 16)
        session_open(cli_ctx)
        crypt_obj = Crypt(cli_ctx.session)
        if algo != '':
            crypt_obj.algorithm = CRYPT_ALGO[algo]
        status = func_timeout.func_timeout(TIME_OUT, crypt_obj.do_encryption,
                                           (keyid, input_data, filename))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Encrypted from KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Encrypt from KeyID = 0x%08X " % keyid)
        ret_value = 1
    sys.exit(ret_value)


@cli.command('decrypt', short_help='Decrypt Operation')
@click.argument('keyid', type=str, metavar='keyid')
@click.argument('encrypted_data', type=str, metavar='encrypted_data')
@click.argument('filename', type=str, metavar='filename')
@click.option('--algo', default='',
              help='Algorithm. TEXT can be one of \"oaep\", \"rsaes\"')
@pass_context
def decrypt(cli_ctx, keyid, encrypted_data, filename, algo):
    """ Sign Operation \n
        keyid = 32bit Key ID. Should be in hex format. Example: 20E8A001 \n

        encrypted_data = Encrypted data to Decrypt. can be raw data or in file.
        Input data should be in DER format.\n

        filename = Output file name to store Decrypted data.
        """
    try:
        keyid = int(keyid, 16)
        session_open(cli_ctx)
        crypt_obj = Crypt(cli_ctx.session)
        if algo != '':
            crypt_obj.algorithm = CRYPT_ALGO[algo]
        status = func_timeout.func_timeout(TIME_OUT, crypt_obj.do_decryption,
                                           (keyid, encrypted_data, filename))
    except func_timeout.FunctionTimedOut as timeout_exc:
        log_traceback(cli_ctx, timeout_exc.getMsg())
        status = apis.kStatus_SSS_Fail
    except Exception as exc:  # pylint: disable=broad-except
        log_traceback(cli_ctx, exc)
        status = apis.kStatus_SSS_Fail
    session_status = session_close(cli_ctx)
    if status == apis.kStatus_SSS_Success and session_status == apis.kStatus_SSS_Success:
        cli_ctx.log("Decrypted from KeyID = 0x%08X" % keyid)
        ret_value = 0
    else:
        cli_ctx.log("ERROR! Could not Decrypt from KeyID = 0x%08X " % keyid)
        ret_value = 1
    sys.exit(ret_value)


@cli.group()
@pass_context
def refpem(cli_ctx):
    """ Create Reference PEM/DER files (For OpenSSL Engine)."""
    cli_ctx.vlog("Create Reference PEM/DER files (For OpenSSL Engine)")


@cli.group()
@pass_context
def policy(cli_ctx):
    """ Create/Dump Object Policy"""
    cli_ctx.vlog("Create/Dump Object Policy")
