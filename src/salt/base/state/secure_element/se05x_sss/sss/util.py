#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
# Modified by AutoPi 2022

"""License text"""

import binascii
import hashlib
import base64
import os
import logging
import ctypes
from . import sss_api as apis
from . import const

if True:  # pylint: disable=using-constant-test
    from sss import patch_cryptography
    patch_cryptography.patch()
    from cryptography.hazmat.primitives.asymmetric import ec, rsa
    from cryptography.hazmat.backends import openssl, default_backend
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import PublicFormat, PrivateFormat, \
        load_der_public_key
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption
    from cryptography.hazmat.primitives.serialization import load_pem_private_key, \
        load_pem_public_key, load_der_private_key, load_der_public_key
    from cryptography.x509.base import load_pem_x509_certificate, \
        load_der_x509_certificate
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives import asymmetric


log = logging.getLogger(__name__)

CRYPTO_ECC_CURVE_MAP = {
    # Mapping Crytography curve type with Plug&Trust Middleware curve type
    ec.SECP192R1: [apis.kSE05x_ECCurve_NIST_P192, 192],
    ec.SECP224R1: [apis.kSE05x_ECCurve_NIST_P224, 224],
    ec.SECP256R1: [apis.kSE05x_ECCurve_NIST_P256, 256],
    ec.SECP384R1: [apis.kSE05x_ECCurve_NIST_P384, 384],
    ec.SECP521R1: [apis.kSE05x_ECCurve_NIST_P521, 521],
}

# pylint: disable=no-member
if hasattr(ec, "BrainpoolP160R1"):
    CRYPTO_ECC_CURVE_MAP[ec.BrainpoolP160R1] = [apis.kSE05x_ECCurve_Brainpool160, 160]
if hasattr(ec, "BrainpoolP192R1"):
    CRYPTO_ECC_CURVE_MAP[ec.BrainpoolP192R1] = [apis.kSE05x_ECCurve_Brainpool192, 192]
if hasattr(ec, "BrainpoolP224R1"):
    CRYPTO_ECC_CURVE_MAP[ec.BrainpoolP224R1] = [apis.kSE05x_ECCurve_Brainpool224, 224]
if hasattr(ec, "BrainpoolP256R1"):
    CRYPTO_ECC_CURVE_MAP[ec.BrainpoolP256R1] = [apis.kSE05x_ECCurve_Brainpool256, 256]
if hasattr(ec, "BrainpoolP320R1"):
    CRYPTO_ECC_CURVE_MAP[ec.BrainpoolP320R1] = [apis.kSE05x_ECCurve_Brainpool320, 320]
if hasattr(ec, "BrainpoolP384R1"):
    CRYPTO_ECC_CURVE_MAP[ec.BrainpoolP384R1] = [apis.kSE05x_ECCurve_Brainpool384, 384]
if hasattr(ec, "BrainpoolP512R1"):
    CRYPTO_ECC_CURVE_MAP[ec.BrainpoolP512R1] = [apis.kSE05x_ECCurve_Brainpool512, 512]
if hasattr(ec, "SECP160K1"):
    CRYPTO_ECC_CURVE_MAP[ec.SECP160K1] = [apis.kSE05x_ECCurve_Secp160k1, 160]
if hasattr(ec, "SECP192K1"):
    CRYPTO_ECC_CURVE_MAP[ec.SECP192K1] = [apis.kSE05x_ECCurve_Secp192k1, 192]
if hasattr(ec, "SECP224K1"):
    CRYPTO_ECC_CURVE_MAP[ec.SECP224K1] = [apis.kSE05x_ECCurve_Secp224k1, 224]
if hasattr(ec, "SECP256K1"):
    CRYPTO_ECC_CURVE_MAP[ec.SECP256K1] = [apis.kSE05x_ECCurve_Secp256k1, 256]

# pylint: enable=no-member

HASH_MAP = {
    # Mapping Hash alogorithm of Middleware with Cryptography
    # Don't put parenthesis on hashlib.shaXX (eg - hashlib.sha256()) as it will initialize
    # a global sha256 object. Parenthesis should be put wherever we want to
    # initialize the SHA object.
    # eg - hash_value = HASH_MAP[hash_algo][1]()
    apis.kAlgorithm_SSS_SHA1: [hashes.SHA1(), hashlib.sha1],
    apis.kAlgorithm_SSS_SHA224: [hashes.SHA224(), hashlib.sha224],
    apis.kAlgorithm_SSS_SHA256: [hashes.SHA256(), hashlib.sha256],
    apis.kAlgorithm_SSS_SHA384: [hashes.SHA384(), hashlib.sha384],
    apis.kAlgorithm_SSS_SHA512: [hashes.SHA512(), hashlib.sha512],
    apis.kAlgorithm_SSS_RSASSA_PKCS1_V1_5_SHA1: [hashes.SHA1(), hashlib.sha1],
    apis.kAlgorithm_SSS_RSASSA_PKCS1_V1_5_SHA224: [hashes.SHA224(), hashlib.sha224],
    apis.kAlgorithm_SSS_RSASSA_PKCS1_V1_5_SHA256: [hashes.SHA256(), hashlib.sha256],
    apis.kAlgorithm_SSS_RSASSA_PKCS1_V1_5_SHA384: [hashes.SHA384(), hashlib.sha384],
    apis.kAlgorithm_SSS_RSASSA_PKCS1_V1_5_SHA512: [hashes.SHA512(), hashlib.sha512],
    apis.kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA1: [hashes.SHA1(), hashlib.sha1],
    apis.kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA224: [hashes.SHA224(), hashlib.sha224],
    apis.kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA256: [hashes.SHA256(), hashlib.sha256],
    apis.kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA384: [hashes.SHA384(), hashlib.sha384],
    apis.kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA512: [hashes.SHA512(), hashlib.sha512],
}


def get_session_pkl_path():
    """
    Get session pkl file path
    :return: Session pkl file path
    """
    work_space = os.getenv("WORKSPACE")
    if work_space:
        return "%s/~.ssscli_session.pkl" % (work_space,)
    home = os.path.expanduser("~")
    return "%s/~.ssscli_session.pkl" % (home,)


def get_host_session_pkl_path():
    """
    Get Host session pkl file path
    :return: Host session pkl file path
    """
    work_space = os.getenv("WORKSPACE")
    if work_space:
        return "%s/~.ssscli_host_session.pkl" % (work_space,)
    home = os.path.expanduser("~")
    return "%s/~.ssscli_host_session.pkl" % (home,)


def status_to_str(status):
    """
    Parse sss status to string format
    :param status: SSS status
    :return: Status as string
    """
    if status in const.STATUS2STR:
        return const.STATUS2STR[status]
    return 'Unknown Status "%s")' % (repr(status),)


def is_hex(key):
    """
    Check if the key is in he format or not
    :param key: Input key
    :return: True if key in hex format, else False
    """
    try:
        int(key, 16)
        return True
    except ValueError:
        return False


def key_der_to_list(key_data):
    """
    Read AES key from der format
    :param key_data: Input Key data
    :return: key as list
    """
    key_list = list()
    for i in key_data:
        key_list.append(ord(chr(i)))
    return key_list


def transform_key_to_list(key):
    """
    Convert key to list. Takes each 2 digit value and put it in list.
    :param key: Input key
    :return: Key as integer list format
    """
    key_int_list = list()
    for i in range(0, len(key), 2):
        key_int_list.append(int(key[i:i + 2], 16))
    return key_int_list


def transform_int_list_to_hex_str(key_list):
    """
    Convert key from integer list to hex string.
    :param key_list: Input key as integer list
    :return: Key as hex string format
    """
    key_hex_str = ""
    for key_item in key_list:
        hex_str_item = format(key_item, 'x')
        if len(hex_str_item) == 1:
            hex_str_item = "0" + hex_str_item
        key_hex_str += hex_str_item
    return key_hex_str


def to_cert_dat(key):
    """
    Convert input raw key to list
    :param key: Input raw key
    :return: Key as list format
    """
    cert_data = list()
    for i in key:
        cert_data.append(ord(i))
    return cert_data


def file_write(key, filename):
    """
    Store key into file
    :param key: Input key
    :param filename: File name to store key
    :return: None
    """
    with open(filename, 'wb') as f:
        if isinstance(key, str):
            f.write(str.encode(key))
        else:
            f.write(key)


def write_pkcs12_refkey(refkey_file, password, refpem_key, cert):  # pylint: disable=too-many-locals
    """
    Write PKCS12 key to file
    :param refkey_file: File name to store reference key
    :param password: Password for encryption of ref key
    :param refpem_key: Input reference pem key
    :param cert: Input certificate
    :return: Status
    """
    password_ctypes = ctypes.create_string_buffer(1024)
    password_ctypes.value = str.encode(password)
    refpem_key_ctypes = ctypes.create_string_buffer(4096)
    refpem_key_ctypes.value = str.encode(refpem_key)

    encode_format = ""
    if not os.path.isfile(cert):

        if encode_format in ["", "PEM"]:
            cert_data = load_pem_x509_certificate(cert, default_backend())
    else:
        with open(cert, 'rb') as key_in:
            cert_data_file = key_in.read()

        if encode_format in ["", "PEM"]:
            if cert.endswith('.pem') or cert.endswith('.cer'):
                cert_data = load_pem_x509_certificate(cert_data_file, default_backend())
            else:
                cert_data = load_der_x509_certificate(cert_data_file, default_backend())

    key_der = cert_data.public_bytes(Encoding.DER)

    # key_hex = binascii.hexlify(key_der)
    #     cert_data = to_cert_dat(cert)
    #     cert_len = len(cert_data)
    # else:
    #     cert_data, cert_len, key_bit_len, curve = from_file_dat(cert,  # pylint: disable=unused-variable
    #                                                             apis.kSSS_KeyPart_Default,
    #                                                             '')

    cert_ctypes = ctypes.create_string_buffer(len(key_der))
    cert_ctypes.value = key_der
    # cert_ctypes = (ctypes.c_uint8 * cert_len)(*cert_data)

    if refkey_file.endswith('.pfx') or refkey_file.endswith('.p12'):
        # write to pkcs12 format
        refkey_file_ctypes = ctypes.create_string_buffer(1024)
        refkey_file_ctypes.value = str.encode(refkey_file)
        status = apis.sss_util_openssl_write_pkcs12(apis.String(refkey_file_ctypes),
                                                    apis.String(password_ctypes),
                                                    apis.String(refpem_key_ctypes),
                                                    len(refpem_key),
                                                    apis.String(cert_ctypes),
                                                    len(key_der))
    else:
        # write to pkcs12 format
        p12_refkey_file = refkey_file[:-4] + ".p12"
        p12_refkey_file_ctypes = ctypes.create_string_buffer(1024)
        p12_refkey_file_ctypes.value = str.encode(p12_refkey_file)
        status = apis.sss_util_openssl_write_pkcs12(apis.String(p12_refkey_file_ctypes),
                                                    apis.String(password_ctypes),
                                                    apis.String(refpem_key_ctypes),
                                                    len(refpem_key),
                                                    apis.String(cert_ctypes),
                                                    len(key_der))
        if status != apis.kStatus_SSS_Success:
            log.error("pkcs12 refkey creation failed")
            return status

        pem_refkey = (ctypes.c_uint8 * 10400)(0)
        certificate = (ctypes.c_uint8 * 10400)(0)

        # extract ref pem key from pkcs12 file
        status = apis.sss_util_openssl_read_pkcs12(apis.String(p12_refkey_file_ctypes),
                                                   apis.String(password_ctypes),
                                                   pem_refkey,
                                                   certificate)

        if status != apis.kStatus_SSS_Success:
            log.error("pkcs12 refkey pem extraction failed")
            return status

        pem_refkey_list = list(pem_refkey)
        # Remove zero padding
        while pem_refkey_list[-1] == 0:
            pem_refkey_list = pem_refkey_list[:-1]

        pem = transform_int_list_to_hex_str(pem_refkey_list)
        extracted_ref_key = binascii.unhexlify(pem)

        # convert to DER
        if refkey_file.endswith('.der'):
            pemkey = load_pem_private_key(extracted_ref_key, None, default_backend())
            extracted_ref_key = pemkey.private_bytes(serialization.Encoding.DER,
                                                     serialization.PrivateFormat.TraditionalOpenSSL,
                                                     serialization.NoEncryption())
        # save pkcs12 extracted refkey
        with open(refkey_file, 'wb') as f:
            f.write(extracted_ref_key)

    return status


def write_refkey_to_file(refkey_file, password, key_pem, key_der, cert, encode_format):  # pylint: disable=too-many-arguments
    """
    Write reference key into file
    :param refkey_file: File name to store reference key
    :param password: Password for encryption of pkcs12 reference key
    :param key_pem: Reference key in PEM format
    :param key_der: Reference key in DER format
    :param cert: Input certificate
    :param encode_format: File format to store key
    :return: Status
    """
    if refkey_file.endswith('.pfx') or refkey_file.endswith('.p12') or encode_format == "PKCS12":
        status = write_pkcs12_refkey(refkey_file, password, bytes.decode(key_pem), cert)
    else:

        try:
            f = open(refkey_file, 'wb')  # pylint: disable=consider-using-with
        except IOError as exc:
            log.error(exc)
            return apis.kStatus_SSS_Fail

        # Consider file extension for default
        if encode_format == "":
            if refkey_file.endswith('.pem'):
                f.write(key_pem)
            else:
                f.write(key_der)
        elif encode_format == "PEM":
            f.write(key_pem)
        elif encode_format == "DER":
            f.write(key_der)
        else:
            log.error("Unknown file format")
            f.close()
            return apis.kStatus_SSS_Fail
        f.close()
        status = apis.kStatus_SSS_Success

    return status


def generate_openssl_ecc_refkey(key_pub_raw, keyid_int,  # pylint: disable=too-many-locals, too-many-branches, too-many-arguments, too-many-statements
                                refkey_file, key_type,
                                ecc_curve, encode_format="",
                                password="nxp", cert=""):
    """
    Generate ecc reference key using openssl
    :param key_pub_raw: Retrieved public key
    :param keyid_int: Key index
    :param refkey_file: File name to store reference key
    :param key_type: Key type for magic number
    :param ecc_curve: ECC curve type
    :param encode_format: Encode format to store file
    :param password: Password for encryption of pkcs12 reference key
    :param cert: Input certificate
    :return: Status
    """
    # Dictionary used for ECC ref key creation
    # Maps MW curve type enum with cryptography curve type, public key header length,
    # Private key length and Private key length calculator index
    crypto_refpem_dict = {
        apis.kSE05x_ECCurve_NIST_P192: [ec.SECP192R1, 23, 6],
        apis.kSE05x_ECCurve_NIST_P224: [ec.SECP224R1, 20, 6],
        apis.kSE05x_ECCurve_NIST_P256: [ec.SECP256R1, 23, 6],
        apis.kSE05x_ECCurve_NIST_P384: [ec.SECP384R1, 20, 7],
        apis.kSE05x_ECCurve_NIST_P521: [ec.SECP521R1, 21, 7],
    }
    # pylint: disable=no-member
    if hasattr(ec, "BrainpoolP160R1"):
        crypto_refpem_dict[apis.kSE05x_ECCurve_Brainpool160] = [ec.BrainpoolP160R1, 24, 6]
    if hasattr(ec, "BrainpoolP192R1"):
        crypto_refpem_dict[apis.kSE05x_ECCurve_Brainpool192] = [ec.BrainpoolP192R1, 24, 6]
    if hasattr(ec, "BrainpoolP224R1"):
        crypto_refpem_dict[apis.kSE05x_ECCurve_Brainpool224] = [ec.BrainpoolP224R1, 24, 6]
    if hasattr(ec, "BrainpoolP256R1"):
        crypto_refpem_dict[apis.kSE05x_ECCurve_Brainpool256] = [ec.BrainpoolP256R1, 24, 6]
    if hasattr(ec, "BrainpoolP320R1"):
        crypto_refpem_dict[apis.kSE05x_ECCurve_Brainpool320] = [ec.BrainpoolP320R1, 24, 7]
    if hasattr(ec, "BrainpoolP384R1"):
        crypto_refpem_dict[apis.kSE05x_ECCurve_Brainpool384] = [ec.BrainpoolP384R1, 24, 7]
    if hasattr(ec, "BrainpoolP512R1"):
        crypto_refpem_dict[apis.kSE05x_ECCurve_Brainpool512] = [ec.BrainpoolP512R1, 25, 7]
    if hasattr(ec, "SECP160K1"):
        crypto_refpem_dict[apis.kSE05x_ECCurve_Secp160k1] = [ec.SECP160K1, 20, 6]
    if hasattr(ec, "SECP192K1"):
        crypto_refpem_dict[apis.kSE05x_ECCurve_Secp192k1] = [ec.SECP192K1, 20, 6]
    if hasattr(ec, "SECP224K1"):
        crypto_refpem_dict[apis.kSE05x_ECCurve_Secp224k1] = [ec.SECP224K1, 20, 6]
    if hasattr(ec, "SECP256K1"):
        crypto_refpem_dict[apis.kSE05x_ECCurve_Secp256k1] = [ec.SECP256K1, 20, 6]

    if hasattr(asymmetric, "x25519"):
        crypto_refpem_dict[apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_25519] = [asymmetric.x25519, 12, 15]
    else:
        log.warning("Python Cryptography module does not support MONT_DH_25519 curve.!! "
                    "Consider upgrading via \'pip3 install cryptography --upgrade\' command.")

    if hasattr(asymmetric, "ed25519"):
        crypto_refpem_dict[apis.kSE05x_ECCurve_RESERVED_ID_ECC_ED_25519] = [asymmetric.ed25519, 12, 15]
    if hasattr(asymmetric, "x448"):
        crypto_refpem_dict[apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_448] = [asymmetric.x448, 12, 15]
    # pylint: enable=no-member

    # To support EAR_CH, setting NIST_P256 as default
    if ecc_curve == 0:
        ecc_curve = apis.kSE05x_ECCurve_NIST_P256

    curve_info = crypto_refpem_dict[ecc_curve]
    curve_type = curve_info[0]
    pub_key_header_length = curve_info[1]
    index_to_cal_length = curve_info[2]

    openssl_format_list = ['10', '00', '00', '00', '00', '00', '00', '00', '00', '00',
                           '00', '00', '00', '00', '00', '00', '00', '00', ]
    magic_data_list = ['a5', 'a6', 'b5', 'b6', 'a5', 'a6', 'b5', 'b6', key_type, '00']

    # Convert key id from int to hex list format
    keyid_str = format("%08x" % keyid_int)
    keyid_list = list()
    for j in range(0, len(keyid_str), 2):
        keyid_list.append(keyid_str[j:j + 2])

    # Convert public key from raw key to hex list format and trim header
    key_pub_list = list(key_pub_raw)
    key_pub_hex_list = []
    for key_pub_item in key_pub_list:
        key_pub_item = format(key_pub_item, 'x')
        if len(key_pub_item) == 1:
            key_pub_item = "0" + key_pub_item
        key_pub_hex_list.append(key_pub_item)
    key_pub_no_header_list = key_pub_hex_list[pub_key_header_length:]

    # Generate private key using openssl and convert it to hex list format
    if ecc_curve == apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_25519:
        key_openssl = asymmetric.x25519.X25519PrivateKey.generate()
        key_openssl_prv_bytes = key_openssl.private_bytes(
            Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    elif ecc_curve == apis.kSE05x_ECCurve_RESERVED_ID_ECC_ED_25519:
        key_openssl = asymmetric.ed25519.Ed25519PrivateKey.generate()
        key_openssl_prv_bytes = key_openssl.private_bytes(
            Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    elif ecc_curve == apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_448:
        key_openssl = asymmetric.x448.X448PrivateKey.generate()
        key_openssl_prv_bytes = key_openssl.private_bytes(
            Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    else:
        key_openssl = ec.generate_private_key(curve_type, default_backend())
        key_openssl_prv_bytes = key_openssl.private_bytes(
            Encoding.DER, PrivateFormat.TraditionalOpenSSL, NoEncryption())
    key_openssl_hex = binascii.hexlify(key_openssl_prv_bytes)
    key_openssl_list = list()
    for i in range(0, len(key_openssl_hex), 2):
        key_openssl_list.append(key_openssl_hex[i:i + 2])

    if ecc_curve not in [apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_25519,
                         apis.kSE05x_ECCurve_RESERVED_ID_ECC_ED_25519,
                         apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_448]:
        # Remove public key from generated ecc key
        private_key_length = len(key_openssl_list) - len(key_pub_no_header_list)
        key_openssl_prv_list = key_openssl_list[:private_key_length]
    else:
        key_openssl_prv_list = key_openssl_list

    key_openssl_prv_length = int(key_openssl_prv_list[index_to_cal_length], 16)
    openssl_format_length = key_openssl_prv_length - (len(openssl_format_list) +
                                                      len(keyid_list) + len(magic_data_list))
    if openssl_format_length >= 0:
        # Append zeros to openssl format to match length
        for i in range(openssl_format_length):
            openssl_format_list.append('00')
    else:
        for i in range((len(openssl_format_list) + len(keyid_list) +
                        len(magic_data_list)) - key_openssl_prv_length):
            openssl_format_list = openssl_format_list[:-1]
    index_to_cal_length += 1

    openssl_format_list.extend(keyid_list)
    openssl_format_list.extend(magic_data_list)
    # Update openssl generated private key with magic data
    for i in range(len(openssl_format_list)):  # pylint: disable=consider-using-enumerate
        key_openssl_prv_list[i + index_to_cal_length] = openssl_format_list[i]

    if ecc_curve not in [apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_25519,
                         apis.kSE05x_ECCurve_RESERVED_ID_ECC_ED_25519,
                         apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_448]:
        # Add public key
        key_openssl_prv_list.extend(key_pub_no_header_list)

    # Convert key from list to string
    key_der_hex = ""
    for key_openssl_prv_item in key_openssl_prv_list:
        if isinstance(key_openssl_prv_item, bytes):
            key_der_hex += bytes.decode(key_openssl_prv_item)
        else:
            key_der_hex += key_openssl_prv_item

    key_der = binascii.unhexlify(key_der_hex)
    key_pem_obj = openssl.backend.load_der_private_key(key_der, None)
    if ecc_curve in [apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_25519,
                     apis.kSE05x_ECCurve_RESERVED_ID_ECC_ED_25519,
                     apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_448]:
        key_pem = key_pem_obj.private_bytes(Encoding.PEM, PrivateFormat.PKCS8,
                                            NoEncryption())
    else:
        key_pem = key_pem_obj.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL,
                                            NoEncryption())
    status = write_refkey_to_file(refkey_file, password,
                                  key_pem, key_der, cert, encode_format)

    return status


def get_length(key_list):
    """
    Get length in the TLV
    :param key_list: Key to parse
    :return: Length in the TLV
    """
    # Find tag value
    if 2 == int(key_list[0], 16):  # pylint: disable=misplaced-comparison-constant
        # check MSB is zero, if yes then this byte indicates length
        # else this byte indicates number of bytes for length calculation
        if int(key_list[1], 16) & 0x80 == 0x00:
            length = int(key_list[1], 16)
            length += 2
        else:
            length_bytes = int(key_list[1], 16) & 0x7f  # Mask MSB
            length_header = 2 + length_bytes
            length = int(key_list[2], 16)
            for i in range(1, length_bytes):
                length = length * 0x100
                length = length | int(key_list[2 + i], 16)
            length += length_header
        return length
    return 0


def replace_bytes(list_dest, len_dest, dest_index, list_src, len_src):
    """
    Replace key values
    :param list_dest: Output list
    :param len_dest: Output length
    :param dest_index: Index to replace bytes
    :param list_src: Input list
    :param len_src: Input length
    :return: Output list
    """
    index = 0
    # if destination list length is bigger then copy source list and remove extra bytes
    if len_dest > len_src:
        for index in range(len_src):
            list_dest[dest_index + index] = list_src[index]
        del list_dest[dest_index + index + 1: dest_index + index + (len_dest - len_src) + 1]

    else:
        for index in range(len_dest):
            list_dest[dest_index + index] = list_src[index]
        for i in range(index + 1, len_src):
            list_dest.insert(dest_index + index + i, list_src[index + i])

    return list_dest


def generate_openssl_rsa_refkey(key_pub_raw,  # pylint: disable=too-many-locals, too-many-branches, too-many-arguments, too-many-statements
                                keyid_int, refkey_file,
                                key_size, encode_format="", password="nxp",
                                cert=""):
    """
    Generate rsa reference key using openssl
    :param key_pub_raw: Retrieved public key
    :param keyid_int: Key index
    :param refkey_file: File name to store reference key
    :param key_size: RSA key size
    :param encode_format: Encode format to store file
    :param password: Password for encryption of pkcs12 reference key
    :param cert: Input certificate
    :return: Status
    """
    # generate rsa key pair
    key_openssl = rsa.generate_private_key(public_exponent=65537, key_size=key_size,
                                           backend=default_backend())
    key_prv_bytes = key_openssl.private_bytes(encoding=Encoding.DER,
                                              format=serialization.PrivateFormat.TraditionalOpenSSL,
                                              encryption_algorithm=serialization.NoEncryption())
    key_openssl_hex = binascii.hexlify(key_prv_bytes)

    key_openssl_list = list()
    for k in range(0, len(key_openssl_hex), 2):
        key_openssl_list.append(key_openssl_hex[k:k + 2])

    # convert the retrieved public key to hex format
    key_pub_list = list(key_pub_raw)

    # trim the header of public key
    if key_size == 1024:
        key_pub_no_header_list = key_pub_list[25:]
    elif key_size in [2048, 3072, 4096]:
        key_pub_no_header_list = key_pub_list[28:]
    else:
        log.error("key size: %s is not supported. Should be one of 1024, 2048, 3072, 4096",
                  (str(key_size),))
        return apis.kStatus_SSS_Fail

    key_pub_str_list = list()
    for key_pub_no_header_item in key_pub_no_header_list:
        key_pub_no_header_item = format(key_pub_no_header_item, 'x')
        if len(key_pub_no_header_item) == 1:
            key_pub_no_header_item = "0" + key_pub_no_header_item
        key_pub_str_list.append(key_pub_no_header_item)

    openssl_index = 7

    # Public Key section
    retrieved_pub_len = get_length(key_pub_str_list)
    openssl_pub_len = get_length(key_openssl_list[openssl_index:])
    key_openssl_list = replace_bytes(key_openssl_list, openssl_pub_len, openssl_index,
                                     key_pub_str_list, retrieved_pub_len)
    openssl_index += retrieved_pub_len

    # publicExponent section
    openssl_index += get_length(key_openssl_list[openssl_index:])

    # Private key Exponent section
    openssl_index += get_length(key_openssl_list[openssl_index:])

    # prime1 section
    magic_prime1_data = ['02', '01', '01']
    openssl_prime1_len = get_length(key_openssl_list[openssl_index:])
    key_openssl_list = replace_bytes(key_openssl_list, openssl_prime1_len, openssl_index,
                                     magic_prime1_data, len(magic_prime1_data))
    openssl_index += len(magic_prime1_data)

    # convert keyID to hex format and add TLV
    keyid_str = format("%08x" % keyid_int)
    key_id_list = ['02']
    if len(keyid_str) < 31:
        key_id_len = int(len(keyid_str) / 2)
        key_id_len_hex = format("%x" % key_id_len)
        if len(key_id_len_hex) == 1:
            key_id_len_hex = "0" + key_id_len_hex
        key_id_list.append(key_id_len_hex)
    for i in range(0, len(keyid_str), 2):
        key_id_list.append(keyid_str[i:i + 2])

    # prime 2 section
    openssl_prime2_len = get_length(key_openssl_list[openssl_index:])
    key_openssl_list = replace_bytes(key_openssl_list, openssl_prime2_len,
                                     openssl_index, key_id_list, len(key_id_list))
    openssl_index += len(key_id_list)

    # exponent1 section
    openssl_index += get_length(key_openssl_list[openssl_index:])

    # exponent2 section
    openssl_index += get_length(key_openssl_list[openssl_index:])

    # coefficient section
    magic_mod_p = ['02', '04', 'a5', 'a6', 'b5', 'b6']
    openssl_coefficient_len = get_length(key_openssl_list[openssl_index:])
    key_openssl_list = replace_bytes(key_openssl_list, openssl_coefficient_len,
                                     openssl_index, magic_mod_p,
                                     len(magic_mod_p))

    # Recalculate total length of the key
    key_openssl_len = len(key_openssl_list) - 4
    key_openssl_len_str = format("%04x" % key_openssl_len)
    total_len_list = []
    for i in range(0, len(key_openssl_len_str), 2):
        total_len_list.append(key_openssl_len_str[i:i + 2])

    key_openssl_list[2] = total_len_list[0]
    key_openssl_list[3] = total_len_list[1]

    # convert key to der or pem format
    key_der_hex = ""
    for key_openssl_item in key_openssl_list:
        if isinstance(key_openssl_item, bytes):
            key_der_hex += bytes.decode(key_openssl_item)
        else:
            key_der_hex += key_openssl_item

    key_der = binascii.unhexlify(key_der_hex)

    key_pem = b'-----BEGIN RSA PRIVATE KEY-----\n' + base64.b64encode(key_der) + \
              b'\n-----END RSA PRIVATE KEY-----\n'

    status = write_refkey_to_file(refkey_file, password,
                                  key_pem, key_der, cert, encode_format)
    return status


def ecc_ex_curve_add_pub_key(prv_key_in):
    """
    Make key pair for ECC extra curves
    :param prv_key_in: Private key
    :return: Full key pair
    """
    # Generate public key from private
    pub_key = prv_key_in.public_key()
    pub_bytes = pub_key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    prv_key_der = prv_key_in.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())

    # Convert keys to hex format
    prv_key_data_hex = binascii.hexlify(prv_key_der)
    pub_key_data_hex = binascii.hexlify(pub_bytes)
    # Private key header
    prv_key_header = prv_key_data_hex[:32]

    # Private key data
    prv_key_data = prv_key_data_hex[32:]

    # Convert header to list for manipulation
    prv_header_list = transform_key_to_list(prv_key_header)

    # Create public key header for key pair
    header = b'81' + str.encode(format((len(pub_bytes) - 12 + 1), 'x')) + b'00'

    pub_key_data = pub_key_data_hex[24:]

    # Update key pair length
    key_pair = prv_key_data + header + pub_key_data

    # Update Key pair header
    prv_header_list[1] = int(14 + (len(key_pair)/2))  # Update new length
    prv_header_list[4] = 0x01  # 0x01 Indicates key pair
    prv_header_list[13] = int(2 + (len(prv_key_data)/2))  # Update new length

    header_str = transform_int_list_to_hex_str(prv_header_list)

    return binascii.unhexlify(str.encode(header_str) + key_pair)


def from_file_dat(filename, key_part, encode_format=""):  # pylint: disable=too-many-branches, too-many-statements
    """
    Parse key from file to list format
    :param filename: Input file name
    :param key_part: Key type
    :param encode_format: Encode format. Eg: DER, PEM
    :return: Key as integer list, key length, key bit length and curve type
    """
    key_bit_len = 0
    curve_type = None
    with open(filename, 'rb') as key_in:
        key_data = key_in.read()

    if key_part == apis.kSSS_KeyPart_Public:
        # Consider file extension for default
        if encode_format == "":
            if filename.endswith('.pem'):
                key_pub = load_pem_public_key(key_data, backend=default_backend())
            else:
                key_pub = load_der_public_key(key_data, backend=default_backend())
        elif encode_format == "PEM":
            key_pub = load_pem_public_key(key_data, backend=default_backend())
        elif encode_format == "DER":
            key_pub = load_der_public_key(key_data, backend=default_backend())
        else:
            log.error("Unknown key file format")
            return None, 0, 0, None
        key_der = key_pub.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        if hasattr(key_pub, 'curve'):
            curve_type = CRYPTO_ECC_CURVE_MAP[type(key_pub.curve)][0]
        else:
            if hasattr(openssl, 'ed25519'):
                if key_pub.__class__ is openssl.ed25519._Ed25519PublicKey:  # pylint: disable=protected-access
                    curve_type = apis.kSE05x_ECCurve_RESERVED_ID_ECC_ED_25519
                    key_bit_len = 256
            if hasattr(openssl, 'x25519'):
                if key_pub.__class__ is openssl.x25519._X25519PublicKey:  # pylint: disable=protected-access
                    curve_type = apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_25519
                    key_bit_len = 256
            if hasattr(openssl, 'x448'):
                if key_pub.__class__ is openssl.x448._X448PublicKey:  # pylint: disable=protected-access
                    curve_type = apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_448
                    key_bit_len = 448

        if hasattr(key_pub, 'key_size'):
            key_bit_len = key_pub.key_size
        elif hasattr(key_pub, 'curve'):
            key_bit_len = CRYPTO_ECC_CURVE_MAP[type(key_pub.curve)][1]

    elif key_part == apis.kSSS_KeyPart_Pair:
        # Consider file extension for default
        if encode_format == "":
            if filename.endswith('.pem'):
                key_prv = load_pem_private_key(key_data, None, default_backend())
            else:
                key_prv = load_der_private_key(key_data, None, default_backend())
        elif encode_format == "PEM":
            key_prv = load_pem_private_key(key_data, None, default_backend())
        elif encode_format == "DER":
            key_prv = load_der_private_key(key_data, None, default_backend())
        else:
            log.error("Unknown key file format")
            return None, 0, 0, None
        key_der = key_prv.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
        if hasattr(key_prv, 'curve'):
            curve_type = CRYPTO_ECC_CURVE_MAP[type(key_prv.curve)][0]
        else:
            if hasattr(openssl, 'ed25519'):
                if key_prv.__class__ is openssl.ed25519._Ed25519PrivateKey:  # pylint: disable=protected-access
                    curve_type = apis.kSE05x_ECCurve_RESERVED_ID_ECC_ED_25519
                    key_bit_len = 256
                    key_der = ecc_ex_curve_add_pub_key(key_prv)
            if hasattr(openssl, 'x25519'):
                if key_prv.__class__ is openssl.x25519._X25519PrivateKey:  # pylint: disable=protected-access
                    curve_type = apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_25519
                    key_bit_len = 256
                    key_der = ecc_ex_curve_add_pub_key(key_prv)
            if hasattr(openssl, 'x448'):
                if key_prv.__class__ is openssl.x448._X448PrivateKey:  # pylint: disable=protected-access
                    curve_type = apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_448
                    key_bit_len = 448
                    key_der = ecc_ex_curve_add_pub_key(key_prv)

        if hasattr(key_prv, 'key_size'):
            key_bit_len = key_prv.key_size
        elif hasattr(key_prv, 'curve'):
            key_bit_len = CRYPTO_ECC_CURVE_MAP[type(key_prv.curve)][1]

    elif key_part == apis.kSSS_KeyPart_Default:
        # Consider file extension for default
        if encode_format == "":
            if filename.endswith('.pem') or filename.endswith('.cer'):
                cert = load_pem_x509_certificate(key_data, default_backend())
            else:
                cert = load_der_x509_certificate(key_data, default_backend())
        elif encode_format == "PEM":
            cert = load_pem_x509_certificate(key_data, default_backend())
        elif encode_format == "DER":
            cert = load_der_x509_certificate(key_data, default_backend())
        else:
            log.error("Unknown key file format")
            return None, 0, 0, None
        key_der = cert.public_bytes(Encoding.DER)
    else:
        log.error("Un support key type")
        return None, 0, 0, None

    # Convert key to int list format
    key_hex = binascii.hexlify(key_der)
    key_int_list = transform_key_to_list(key_hex)
    key_len = len(key_int_list)

    return key_int_list, key_len, key_bit_len, curve_type


def hex_uid(uid_raw):
    """
    Convert key to Hex string
    :param uid_raw: Input UID
    :return: Hex string
    """
    uid_list = list(uid_raw)
    uid_hex_str = ""
    for uid_item in uid_list:
        uid_hex = format(uid_item, 'x')
        if len(uid_hex) == 1:
            uid_hex = "0" + uid_hex
        uid_hex_str += uid_hex
    return uid_hex_str


def save_to_file(key, filename, key_part, encode_format="", cypher_type = 0):
    """
    Store key in file
    :param key: Input key
    :param filename: File name to store key
    :param key_part: Key type
    :param encode_format: Encode format to store key. Eg: DER, PEM
    :param cypher_type: cipher type to save to file.
    :return: status
    """
    key_pem = None
    key_der = ""
    key_hex_str = ""
    for i in range(len(key)):  # pylint: disable=consider-using-enumerate
        key[i] = format(key[i], 'x')
        if len(key[i]) == 1:
            key[i] = "0" + key[i]
        key_hex_str += key[i]
    key_der_str = binascii.unhexlify(key_hex_str)

    if key_part == apis.kSSS_KeyPart_Default:
        if cypher_type == apis.kSSS_CipherType_Binary and encode_format == "HEX":
            key_pem = key_der_str
            key_der = key_der_str
        else:
            certificate = load_der_x509_certificate(key_der_str, default_backend())
            key_pem = certificate.public_bytes(Encoding.PEM)
            key_der = certificate.public_bytes(Encoding.DER)

    elif key_part in [apis.kSSS_KeyPart_Pair, apis.kSSS_KeyPart_Public]:
        if cypher_type == apis.kSSS_CipherType_EC_TWISTED_ED:
            if not hasattr(asymmetric, 'ed25519'):
                log.warning("Python Cryptography module does not support ed25519 curve.!! "
                            "Consider upgrading via \'pip3 install cryptography --upgrade\' command.")
                return apis.kStatus_SSS_Fail
            # Remove header
            key_der_str_no_header = key_der_str[12:]
            key_crypto = asymmetric.ed25519.Ed25519PublicKey.from_public_bytes(key_der_str_no_header)
            key_pem = key_crypto.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
            key_der = key_crypto.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        elif cypher_type == apis.kSSS_CipherType_EC_MONTGOMERY:
            if not hasattr(asymmetric, 'x25519') or not hasattr(asymmetric, 'x448'):
                log.warning("Python Cryptography module does not support montgomery curve.!! "
                            "Consider upgrading via \'pip3 install cryptography --upgrade\' command.")
                return apis.kStatus_SSS_Fail
            # Remove header
            key_der_str_no_header = key_der_str[12:]
            if len(key_der_str_no_header) == 56:  # Mont_DH_448 key size is 56 bytes
                key_crypto = asymmetric.x448.X448PublicKey.from_public_bytes(key_der_str_no_header)
            else:
                key_crypto = asymmetric.x25519.X25519PublicKey.from_public_bytes(key_der_str_no_header)
            key_pem = key_crypto.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
            key_der = key_crypto.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        else:
            key_crypto = load_der_public_key(key_der_str, default_backend())
            key_pem = key_crypto.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
            key_der = key_crypto.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)

    elif key_part == apis.kSSS_KeyPart_NONE:
        key_pem = base64.b64encode(key_der_str)
        key_der = key_der_str

    if isinstance(key_der, str):
        key_der = str.encode(key_der)

    try:
        f = open(filename, 'wb')  # pylint: disable=consider-using-with
    except IOError as exc:
        log.error(exc)
        return apis.kStatus_SSS_Fail

    # Consider file extension for default
    if encode_format == "":
        if filename.endswith('.pem') or filename.endswith('.cer'):
            log.debug("writing to file in pem format")
            f.write(key_pem)
        else:
            log.debug("writing to file in der format")
            f.write(key_der)
    elif encode_format == "PEM":
        log.debug("writing to file in pem format")
        f.write(key_pem)
    elif encode_format == "DER":
        log.debug("writing to file in der format")
        f.write(key_der)
    elif encode_format == "HEX" and cypher_type == apis.kSSS_CipherType_Binary:
        log.debug("writing to file in hex format")
        f.write(key_der)
    else:
        log.error("Unknown file format")
        f.close()
        return apis.kStatus_SSS_Fail
    f.close()
    return apis.kStatus_SSS_Success

# AutoPi 2022
def encode_to_pem(key, key_part, encode_format="", cypher_type=0):
    """
    Store key in file
    :param key: Input key
    :param key_part: Key type
    :param encode_format: Encode format to store key. Eg: DER, PEM
    :param cypher_type: cipher type to save to file.
    :return: status
    """
    key_pem = None
    key_hex_str = ""
    for i in range(len(key)):  # pylint: disable=consider-using-enumerate
        key[i] = format(key[i], 'x')
        if len(key[i]) == 1:
            key[i] = "0" + key[i]
        key_hex_str += key[i]
    key_der_str = binascii.unhexlify(key_hex_str)

    if key_part == apis.kSSS_KeyPart_Default:
        if cypher_type == apis.kSSS_CipherType_Binary and encode_format == "HEX":
            key_pem = key_der_str
        else:
            certificate = load_der_x509_certificate(key_der_str, default_backend())
            key_pem = certificate.public_bytes(Encoding.PEM)

    elif key_part in [apis.kSSS_KeyPart_Pair, apis.kSSS_KeyPart_Public]:
        if cypher_type == apis.kSSS_CipherType_EC_TWISTED_ED:
            if not hasattr(asymmetric, 'ed25519'):
                log.warning("Python Cryptography module does not support ed25519 curve.!! "
                            "Consider upgrading via \'pip3 install cryptography --upgrade\' command.")
                return apis.kStatus_SSS_Fail
            # Remove header
            key_der_str_no_header = key_der_str[12:]
            key_crypto = asymmetric.ed25519.Ed25519PublicKey.from_public_bytes(key_der_str_no_header)
            key_pem = key_crypto.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        elif cypher_type == apis.kSSS_CipherType_EC_MONTGOMERY:
            if not hasattr(asymmetric, 'x25519') or not hasattr(asymmetric, 'x448'):
                log.warning("Python Cryptography module does not support montgomery curve.!! "
                            "Consider upgrading via \'pip3 install cryptography --upgrade\' command.")
                return apis.kStatus_SSS_Fail
            # Remove header
            key_der_str_no_header = key_der_str[12:]
            if len(key_der_str_no_header) == 56:  # Mont_DH_448 key size is 56 bytes
                key_crypto = asymmetric.x448.X448PublicKey.from_public_bytes(key_der_str_no_header)
            else:
                key_crypto = asymmetric.x25519.X25519PublicKey.from_public_bytes(key_der_str_no_header)
            key_pem = key_crypto.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        else:
            key_crypto = load_der_public_key(key_der_str, default_backend())
            key_pem = key_crypto.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

    elif key_part == apis.kSSS_KeyPart_NONE:
        key_pem = base64.b64encode(key_der_str)

    return key_pem



def hash_convert(filename, encode_format="", hash_algo=apis.kAlgorithm_SSS_SHA256):
    """
    Convert hash data from file using algorithm
    :param filename: Input file
    :param encode_format: File format. Eg: DER, PEM
    :param hash_algo: Hash algorithm
    :return: Key as integer list and length
    """
    with open(filename, 'rb') as raw_data:
        data = raw_data.read()
    hash_value = hashes.Hash(HASH_MAP[hash_algo][0], default_backend())
    if not is_hex(data):
        # Consider file extension for default
        if encode_format == "":
            if filename.endswith('.pem') or filename.endswith('.cer'):
                cert = load_pem_x509_certificate(data, default_backend())
            else:
                cert = load_der_x509_certificate(data, default_backend())
        elif encode_format == "PEM":
            cert = load_pem_x509_certificate(data, default_backend())
        elif encode_format == "DER":
            cert = load_der_x509_certificate(data, default_backend())
        else:
            log.error("Unknown file format")
            return None, 0

        cert_der = cert.public_bytes(Encoding.DER)
        cert_hex = binascii.hexlify(cert_der)
    else:
        cert_hex = data
    hash_value.update(cert_hex)
    final_hash = hash_value.finalize()
    cert_hash_hex = binascii.hexlify(final_hash)
    key_int_list = transform_key_to_list(cert_hash_hex)
    hash_len = hash_value.algorithm.digest_size
    return key_int_list, hash_len


def load_certificate(filename, encode_format=""):
    """
    Convert Load certificate from file
    :param filename: Input file
    :param encode_format: File format. Eg: DER, PEM
    :return: Key as integer list and length
    """
    with open(filename, 'rb') as raw_data:
        data = raw_data.read()

    # Consider file extension for default
    if encode_format == "":
        if filename.endswith('.pem') or filename.endswith('.cer'):
            cert = load_pem_x509_certificate(data, default_backend())
        else:
            cert = load_der_x509_certificate(data, default_backend())
    elif encode_format == "PEM":
        cert = load_pem_x509_certificate(data, default_backend())
    elif encode_format == "DER":
        cert = load_der_x509_certificate(data, default_backend())
    else:
        log.error("Unknown file format")
        return None, 0
    cert_der = cert.public_bytes(Encoding.DER)
    cert_hex = binascii.hexlify(cert_der)
    key_int_list = transform_key_to_list(cert_hex)
    return key_int_list, len(key_int_list)


def hash_convert_raw(data, hash_algo=apis.kAlgorithm_SSS_SHA256):
    """
    Convert raw hash data using algorithm
    :param data: Input data
    :param hash_algo: Hash algorithm
    :return: Key in list format and length
    """
    hash_value = HASH_MAP[hash_algo][1]()
    if isinstance(data, str):
        hash_value.update(str.encode(data))
    else:
        hash_value.update(data)
    key_hex = hash_value.hexdigest()
    key_int_list = transform_key_to_list(key_hex)
    hash_len = int(hash_value.digest_size)
    return key_int_list, hash_len


def parse_signature(signature_file, encode_format=""):
    """
    Parse signature from file
    :param signature_file: Input file
    :param encode_format: Stored encode format
    :return: Signature in list format and length
    """
    with open(signature_file, 'rb') as infile:
        sig = infile.read()
    if not is_hex(sig):
        if (signature_file[-4:] == '.pem' and encode_format == "") or encode_format == "PEM":
            sig_der = base64.b64decode(sig)
        else:
            sig_der = sig
        sig_hex = binascii.hexlify(sig_der)
    else:
        sig_hex = sig
    sig_int_list = transform_key_to_list(sig_hex)
    sig_len = len(sig_int_list)
    return sig_int_list, sig_len


def get_ecc_cypher_type(curve_type):
    """
    Return Cypher Type and Key length based on EC curve type
    :param curve_type: ECC Curve type
    :return: Cypher type and key length
    """
    ecc_curve_cypher_type_map = {
        # Mapping curve type with Cypher Type and Key length
        apis.kSE05x_ECCurve_NIST_P192: [apis.kSSS_CipherType_EC_NIST_P, 192],
        apis.kSE05x_ECCurve_NIST_P224: [apis.kSSS_CipherType_EC_NIST_P, 224],
        apis.kSE05x_ECCurve_NIST_P256: [apis.kSSS_CipherType_EC_NIST_P, 256],
        apis.kSE05x_ECCurve_NIST_P384: [apis.kSSS_CipherType_EC_NIST_P, 384],
        apis.kSE05x_ECCurve_NIST_P521: [apis.kSSS_CipherType_EC_NIST_P, 521],
        apis.kSE05x_ECCurve_Brainpool160: [apis.kSSS_CipherType_EC_BRAINPOOL, 160],
        apis.kSE05x_ECCurve_Brainpool192: [apis.kSSS_CipherType_EC_BRAINPOOL, 192],
        apis.kSE05x_ECCurve_Brainpool224: [apis.kSSS_CipherType_EC_BRAINPOOL, 224],
        apis.kSE05x_ECCurve_Brainpool256: [apis.kSSS_CipherType_EC_BRAINPOOL, 256],
        apis.kSE05x_ECCurve_Brainpool320: [apis.kSSS_CipherType_EC_BRAINPOOL, 320],
        apis.kSE05x_ECCurve_Brainpool384: [apis.kSSS_CipherType_EC_BRAINPOOL, 384],
        apis.kSE05x_ECCurve_Brainpool512: [apis.kSSS_CipherType_EC_BRAINPOOL, 512],
        apis.kSE05x_ECCurve_Secp160k1: [apis.kSSS_CipherType_EC_NIST_K, 160],
        apis.kSE05x_ECCurve_Secp192k1: [apis.kSSS_CipherType_EC_NIST_K, 192],
        apis.kSE05x_ECCurve_Secp224k1: [apis.kSSS_CipherType_EC_NIST_K, 224],
        apis.kSE05x_ECCurve_Secp256k1: [apis.kSSS_CipherType_EC_NIST_K, 256],
        apis.kSE05x_ECCurve_RESERVED_ID_ECC_ED_25519: [apis.kSSS_CipherType_EC_TWISTED_ED, 256],
        apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_25519: [apis.kSSS_CipherType_EC_MONTGOMERY, 256],
        apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_448: [apis.kSSS_CipherType_EC_MONTGOMERY, 448],
    }

    cypher_type = ecc_curve_cypher_type_map[curve_type][0]
    key_len = ecc_curve_cypher_type_map[curve_type][1]
    return cypher_type, key_len


def ecc_curve_type_from_key(key, key_part):
    """
    Returns curve type and key bit length for ecc key
    :param key: Input key
    :param key_part: Key type
    :return: Curve type and key bit length
    """
    key = binascii.unhexlify(key)
    curve_type = apis.kSE05x_ECCurve_NA
    key_bit_len = 0

    if key_part == apis.kSSS_KeyPart_Public:
        pub_key = load_der_public_key(key, default_backend())
        if hasattr(pub_key, 'curve'):
            curve_type = CRYPTO_ECC_CURVE_MAP[type(pub_key.curve)][0]
        if hasattr(pub_key, 'key_size'):
            key_bit_len = pub_key.key_size
        elif hasattr(pub_key, 'curve'):
            key_bit_len = CRYPTO_ECC_CURVE_MAP[type(pub_key.curve)][1]

    elif key_part == apis.kSSS_KeyPart_Pair:
        priv_key = load_der_private_key(key, None, default_backend())
        if hasattr(priv_key, 'curve'):
            curve_type = CRYPTO_ECC_CURVE_MAP[type(priv_key.curve)][0]
        if hasattr(priv_key, 'key_size'):
            key_bit_len = priv_key.key_size
        elif hasattr(priv_key, 'curve'):
            key_bit_len = CRYPTO_ECC_CURVE_MAP[type(priv_key.curve)][1]

    return curve_type, key_bit_len
