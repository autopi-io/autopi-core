#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

from . import sss_api as apis
from . import authkey


STATUS2STR = {
    apis.kStatus_SSS_Success: "SUCCESS",
    apis.kStatus_SSS_Fail: "FAILED",
    apis.kStatus_SSS_InvalidArgument: "Invalid Argument",
    apis.kStatus_SSS_ResourceBusy: "Resource Busy",
}

SUBSYSTEM_TYPE = {
    'mbedtls': apis.kType_SSS_mbedTLS,
    'a71ch': apis.kType_SSS_SE_A71CH,
    'se05x': apis.kType_SSS_SE_SE05x,
    'se050': apis.kType_SSS_SE_SE05x,
    'openssl': apis.kType_SSS_OpenSSL,
    'auth': apis.kType_SSS_SE_SE05x,
}

CONNECTION_TYPE = {
    'none': apis.kType_SE_Conn_Type_NONE,
    'sci2c': apis.kType_SE_Conn_Type_SCII2C,
    'vcom': apis.kType_SE_Conn_Type_VCOM,
    't1oi2c': apis.kType_SE_Conn_Type_T1oI2C,
    'jrcpv1': apis.kType_SE_Conn_Type_JRCP_V1,
    'jrcpv2': apis.kType_SE_Conn_Type_JRCP_V2,
    'pcsc': apis.kType_SE_Conn_Type_PCSC,
    # 'last': apis.kType_SE_Conn_Type_LAST,
}

ECC_CURVE_TYPE = {
    'NIST_P192': apis.kSE05x_ECCurve_NIST_P192,
    'NIST_P224': apis.kSE05x_ECCurve_NIST_P224,
    'NIST_P256': apis.kSE05x_ECCurve_NIST_P256,
    'NIST_P384': apis.kSE05x_ECCurve_NIST_P384,
    'NIST_P521': apis.kSE05x_ECCurve_NIST_P521,
    'Brainpool160': apis.kSE05x_ECCurve_Brainpool160,
    'Brainpool192': apis.kSE05x_ECCurve_Brainpool192,
    'Brainpool224': apis.kSE05x_ECCurve_Brainpool224,
    'Brainpool256': apis.kSE05x_ECCurve_Brainpool256,
    'Brainpool320': apis.kSE05x_ECCurve_Brainpool320,
    'Brainpool384': apis.kSE05x_ECCurve_Brainpool384,
    'Brainpool512': apis.kSE05x_ECCurve_Brainpool512,
    'Secp160k1': apis.kSE05x_ECCurve_Secp160k1,
    'Secp192k1': apis.kSE05x_ECCurve_Secp192k1,
    'Secp224k1': apis.kSE05x_ECCurve_Secp224k1,
    'Secp256k1': apis.kSE05x_ECCurve_Secp256k1,
    'ED_25519': apis.kSE05x_ECCurve_RESERVED_ID_ECC_ED_25519,
    'MONT_DH_25519': apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_25519,
    'MONT_DH_448': apis.kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_448,
    'BN_P256': apis.kSE05x_ECCurve_Total_Weierstrass_Curves

}

HASH = {
    'SHA1': apis.kAlgorithm_SSS_SHA1,
    'SHA224': apis.kAlgorithm_SSS_SHA224,
    'SHA256': apis.kAlgorithm_SSS_SHA256,
    'SHA384': apis.kAlgorithm_SSS_SHA384,
    'SHA512': apis.kAlgorithm_SSS_SHA512,
    'RSASSA_PKCS1_V1_5_SHA1': apis.kAlgorithm_SSS_RSASSA_PKCS1_V1_5_SHA1,
    'RSASSA_PKCS1_V1_5_SHA224': apis.kAlgorithm_SSS_RSASSA_PKCS1_V1_5_SHA224,
    'RSASSA_PKCS1_V1_5_SHA256': apis.kAlgorithm_SSS_RSASSA_PKCS1_V1_5_SHA256,
    'RSASSA_PKCS1_V1_5_SHA384': apis.kAlgorithm_SSS_RSASSA_PKCS1_V1_5_SHA384,
    'RSASSA_PKCS1_V1_5_SHA512': apis.kAlgorithm_SSS_RSASSA_PKCS1_V1_5_SHA512,
    'RSASSA_PKCS1_PSS_MGF1_SHA1': apis.kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA1,
    'RSASSA_PKCS1_PSS_MGF1_SHA224': apis.kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA224,
    'RSASSA_PKCS1_PSS_MGF1_SHA256': apis.kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA256,
    'RSASSA_PKCS1_PSS_MGF1_SHA384': apis.kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA384,
    'RSASSA_PKCS1_PSS_MGF1_SHA512': apis.kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA512,
}


AUTH_TYPE_MAP = {
    "None": [apis.kSE05x_AuthType_None, 0, False],
    "PlatformSCP": [apis.kSE05x_AuthType_SCP03, 0, False],
    "UserID": [apis.kSE05x_AuthType_UserID, authkey.SE050_AUTHID_USER_ID, False],
    "ECKey": [apis.kSE05x_AuthType_ECKey, authkey.SE050_AUTHID_ECKEY, False],
    "AESKey": [apis.kSE05x_AuthType_AESKey, authkey.SE050_AUTHID_AESKEY, False],
    "UserID_PlatformSCP": [apis.kSE05x_AuthType_UserID, authkey.SE050_AUTHID_USER_ID, True],
    "ECKey_PlatformSCP": [apis.kSE05x_AuthType_ECKey, authkey.SE050_AUTHID_ECKEY, True],
    "AESKey_PlatformSCP": [apis.kSE05x_AuthType_AESKey, authkey.SE050_AUTHID_AESKEY, True],
}


CRYPT_ALGO = {
    'oaep': apis.kAlgorithm_SSS_RSAES_PKCS1_OAEP_SHA1,
    'rsaes': apis.kAlgorithm_SSS_RSAES_PKCS1_V1_5,
    'AES_CTR': apis.kAlgorithm_SSS_AES_CTR,
    'DES_ECB': apis.kAlgorithm_SSS_DES_ECB,
    'HMAC_SHA256': apis.kAlgorithm_SSS_HMAC_SHA256,
}


class SSSException(Exception):
    """
    SSS Exception
    """
    pass  # pylint: disable=unnecessary-pass


class SSSUsageError(SSSException):
    """
    SSS Usage exception
    """
    pass  # pylint: disable=unnecessary-pass
