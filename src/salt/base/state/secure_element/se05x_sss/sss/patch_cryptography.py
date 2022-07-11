#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography import utils, hazmat
if hasattr(hazmat, "_oid"):
    from cryptography.hazmat._oid import ObjectIdentifier  # pylint: disable=protected-access

# pylint: disable=missing-class-docstring,too-few-public-methods


@utils.register_interface(ec.EllipticCurve)
class SECP224K1:
    name = "secp224k1"
    key_size = 224


@utils.register_interface(ec.EllipticCurve)
class SECP192K1:
    name = "secp192k1"
    key_size = 192


@utils.register_interface(ec.EllipticCurve)
class SECP160K1:
    name = "secp160k1"
    key_size = 160


@utils.register_interface(ec.EllipticCurve)
class BrainpoolP160R1:
    name = "brainpoolP160r1"
    key_size = 160


@utils.register_interface(ec.EllipticCurve)
class BrainpoolP192R1:
    name = "brainpoolP192r1"
    key_size = 192


@utils.register_interface(ec.EllipticCurve)
class BrainpoolP224R1:
    name = "brainpoolP224r1"
    key_size = 224


@utils.register_interface(ec.EllipticCurve)
class BrainpoolP256R1:
    name = "brainpoolP256r1"
    key_size = 256


@utils.register_interface(ec.EllipticCurve)
class BrainpoolP320R1:
    name = "brainpoolP320r1"
    key_size = 320


@utils.register_interface(ec.EllipticCurve)
class BrainpoolP384R1:
    name = "brainpoolP384r1"
    key_size = 384


@utils.register_interface(ec.EllipticCurve)
class BrainpoolP512R1:
    name = "brainpoolP512r1"
    key_size = 512

# pylint: enable=missing-class-docstring,too-few-public-methods


def patch():
    """
    Apply patch to python cryptography module to support all ecc curves
    :return: None
    """
    if not hasattr(ec, 'PatchedKoblitshBrainpool'):
        setattr(ec, 'SECP160K1', SECP160K1)
        setattr(ec, 'SECP192K1', SECP192K1)
        setattr(ec, 'SECP224K1', SECP224K1)
        setattr(ec, 'BrainpoolP160R1', BrainpoolP160R1)
        setattr(ec, 'BrainpoolP192R1', BrainpoolP192R1)
        setattr(ec, 'BrainpoolP224R1', BrainpoolP224R1)
        setattr(ec, 'BrainpoolP256R1', BrainpoolP256R1)
        setattr(ec, 'BrainpoolP320R1', BrainpoolP320R1)
        setattr(ec, 'BrainpoolP384R1', BrainpoolP384R1)
        setattr(ec, 'BrainpoolP512R1', BrainpoolP512R1)

        # pylint: disable=no-member, protected-access
        ec._CURVE_TYPES["secp160k1"] = ec.SECP160K1
        ec._CURVE_TYPES["secp192k1"] = ec.SECP192K1
        ec._CURVE_TYPES["secp224k1"] = ec.SECP224K1

        ec._CURVE_TYPES["brainpoolP160r1"] = ec.BrainpoolP160R1
        ec._CURVE_TYPES["brainpoolP192r1"] = ec.BrainpoolP192R1
        ec._CURVE_TYPES["brainpoolP224r1"] = ec.BrainpoolP224R1
        ec._CURVE_TYPES["brainpoolP256r1"] = ec.BrainpoolP256R1
        ec._CURVE_TYPES["brainpoolP320r1"] = ec.BrainpoolP320R1
        ec._CURVE_TYPES["brainpoolP384r1"] = ec.BrainpoolP384R1
        ec._CURVE_TYPES["brainpoolP512r1"] = ec.BrainpoolP512R1

        if 'ObjectIdentifier' in globals():
            setattr(ec.EllipticCurveOID, 'SECP160K1', ObjectIdentifier("1.3.132.0.9"))
            setattr(ec.EllipticCurveOID, 'SECP192K1', ObjectIdentifier("1.3.132.0.31"))
            setattr(ec.EllipticCurveOID, 'SECP224K1', ObjectIdentifier("1.3.132.0.32"))
            setattr(ec.EllipticCurveOID, 'BRAINPOOLP160R1',
                    ObjectIdentifier("1.3.36.3.3.2.8.1.1.1"))
            setattr(ec.EllipticCurveOID, 'BRAINPOOLP192R1',
                    ObjectIdentifier("1.3.36.3.3.2.8.1.1.3"))
            setattr(ec.EllipticCurveOID, 'BRAINPOOLP224R1',
                    ObjectIdentifier("1.3.36.3.3.2.8.1.1.5"))
            setattr(ec.EllipticCurveOID, 'BRAINPOOLP256R1',
                    ObjectIdentifier("1.3.36.3.3.2.8.1.1.7"))
            setattr(ec.EllipticCurveOID, 'BRAINPOOLP320R1',
                    ObjectIdentifier("1.3.36.3.3.2.8.1.1.9"))
            setattr(ec.EllipticCurveOID, 'BRAINPOOLP384R1',
                    ObjectIdentifier("1.3.36.3.3.2.8.1.1.11"))
            setattr(ec.EllipticCurveOID, 'BRAINPOOLP512R1',
                    ObjectIdentifier("1.3.36.3.3.2.8.1.1.13"))

        if hasattr(ec, '_OID_TO_CURVE'):
            ec._OID_TO_CURVE[ec.EllipticCurveOID.SECP160K1] = ec.SECP160K1
            ec._OID_TO_CURVE[ec.EllipticCurveOID.SECP192K1] = ec.SECP192K1
            ec._OID_TO_CURVE[ec.EllipticCurveOID.SECP224K1] = ec.SECP224K1
            ec._OID_TO_CURVE[ec.EllipticCurveOID.BRAINPOOLP160R1] = ec.BrainpoolP160R1
            ec._OID_TO_CURVE[ec.EllipticCurveOID.BRAINPOOLP192R1] = ec.BrainpoolP192R1
            ec._OID_TO_CURVE[ec.EllipticCurveOID.BRAINPOOLP224R1] = ec.BrainpoolP224R1
            ec._OID_TO_CURVE[ec.EllipticCurveOID.BRAINPOOLP256R1] = ec.BrainpoolP256R1
            ec._OID_TO_CURVE[ec.EllipticCurveOID.BRAINPOOLP320R1] = ec.BrainpoolP320R1
            ec._OID_TO_CURVE[ec.EllipticCurveOID.BRAINPOOLP384R1] = ec.BrainpoolP384R1
            ec._OID_TO_CURVE[ec.EllipticCurveOID.BRAINPOOLP512R1] = ec.BrainpoolP512R1
        # pylint: enable=no-member, protected-access

        setattr(ec, 'PatchedKoblitshBrainpool', True)
