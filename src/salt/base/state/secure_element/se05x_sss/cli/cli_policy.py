#
# Copyright 2019 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import sys
import click
import sss.sss_api as apis
from sss.policy import Policy, policy_type
from .cli import policy, pass_context


@policy.command('asymkey', short_help='Create Asymmetric Key Object Policy')
@pass_context
@click.argument('policy_name', type=str, metavar='policy_name')
@click.argument('auth_obj_id', type=str, metavar='auth_obj_id')
@click.option('--sign', type=bool, default=True, help="Object policy Allow Sign. "
                                                      "Enabled by Default")
@click.option('--verify', type=bool, default=True, help="Object policy Allow Verify. "
                                                        "Enabled by Default")
@click.option('--encrypt', type=bool, default=True, help="Object policy Allow Encryption. "
                                                         "Enabled by Default")
@click.option('--decrypt', type=bool, default=True, help="Object policy Allow Decryption. "
                                                         "Enabled by Default")
@click.option('--key_derive', type=bool, default=False, help="Object policy Allow Key Derivation. "
                                                             "Disabled by Default")
@click.option('--wrap', type=bool, default=False, help="Object policy Allow Wrap. "
                                                       "Disabled by Default")
@click.option('--generate', type=bool, default=True, help="Object policy Allow Generate. "
                                                          "Enabled by Default")
@click.option('--write', type=bool, default=True, help="Object policy Allow Write. "
                                                       "Enabled by Default")
@click.option('--read', type=bool, default=True, help="Object policy Allow Read. "
                                                      "Enabled by Default")
@click.option('--import_export', type=bool, default=False,
              help="Object policy Allow Import Export. Disabled by Default")
@click.option('--key_agreement', type=bool, default=False, help="Object policy Allow Key Agreement. "
                                                                "Disabled by Default")
@click.option('--attest', type=bool, default=False, help="Object policy Allow attestation. "
                                                         "Disabled by Default")
@click.option('--forbid_derived_output', type=bool, default=False,
              help="Object policy Forbid Derived Output. Disabled by Default")
@click.option('--forbid_all', type=bool, default=False, help="Object policy forbid all. "
                                                             "Disabled by Default")
@click.option('--delete', type=bool, default=True, help="Object policy Allow Delete. "
                                                        "Enabled by Default")
@click.option('--req_sm', type=bool, default=False, help="Object policy Require Secure Messaging. "
                                                         "Disabled by Default")
@click.option('--req_pcr_val', type=bool, default=False, help="Object policy Require PCR Value. "
                                                         "Disabled by Default")
@click.option('--pcr_obj_id', type=str, default='0', help="Object policy PCR object ID in HEX format. "
                                                          "Zero by Default")
@click.option('--pcr_expected_value', type=str, default='', help="Object policy PCR Expected in Hex byte string "
                                                                 "Value. Zero by Default")
def asymkey(cli_ctx, policy_name, auth_obj_id, sign, verify, encrypt, decrypt,
            key_derive, wrap, generate, write, read, import_export, key_agreement,
            attest, forbid_derived_output, forbid_all, delete, req_sm, req_pcr_val,
            pcr_obj_id, pcr_expected_value):
    """ Create Asymmetric key object policy. \n

    policy_name = File name of the policy to be created.
    This policy name should be given as input while provisioning.\n

    auth_obj_id = Auth object id for each Object Policy. \n

    """
    if req_pcr_val:
        if pcr_obj_id == '0':
            cli_ctx.log("Error: PCR object ID required. Use '--pcr_obj_id' flag to enter PCR object ID in HEX format")
            sys.exit(1)
        if pcr_expected_value == '':
            cli_ctx.log("Error: Expected PCR Value required. Use '--pcr_expected_value' flag to enter Expected PCR Value in HEX byte string format")
            sys.exit(1)

    auth_obj_id = int(auth_obj_id, 16)
    pcr_obj_id  = int(pcr_obj_id, 16)
    policy_obj = Policy()
    policy_obj.sign                  = sign
    policy_obj.verify                = verify
    policy_obj.encrypt               = encrypt
    policy_obj.decrypt               = decrypt
    policy_obj.key_derive            = key_derive
    policy_obj.wrap                  = wrap
    policy_obj.generate              = generate
    policy_obj.write                 = write
    policy_obj.read                  = read
    policy_obj.import_export         = import_export
    policy_obj.key_agreement         = key_agreement
    policy_obj.attest                = attest
    policy_obj.forbid_derived_output = forbid_derived_output
    policy_obj.forbid_all            = forbid_all
    policy_obj.delete                = delete
    policy_obj.req_sm                = req_sm
    policy_obj.req_pcr_val           = req_pcr_val
    policy_obj.pcr_obj_id            = pcr_obj_id
    policy_obj.pcr_expected_value    = pcr_expected_value

    status = policy_obj.create_obj_policy(policy_type["Asymmetric_Key"], policy_name, auth_obj_id)
    if status == apis.kStatus_SSS_Success:
        cli_ctx.log("Object Policy created successfully")
        ret_value = 0
    else:
        cli_ctx.log("Error: Could not create object Policy")
        ret_value = 1
    sys.exit(ret_value)


@policy.command('symkey', short_help='Create Symmetric Key Object Policy')
@pass_context
@click.argument('policy_name', type=str, metavar='policy_name')
@click.argument('auth_obj_id', type=str, metavar='auth_obj_id')
@click.option('--sign', type=bool, default=True, help="Object policy Allow Sign. "
                                                      "Enabled by Default")
@click.option('--verify', type=bool, default=True, help="Object policy Allow Verify. "
                                                        "Enabled by Default")
@click.option('--encrypt', type=bool, default=True, help="Object policy Allow Encryption. "
                                                         "Enabled by Default")
@click.option('--decrypt', type=bool, default=True, help="Object policy Allow Decryption. "
                                                         "Enabled by Default")
@click.option('--key_derive', type=bool, default=False, help="Object policy Allow Key Derivation. "
                                                             "Disabled by Default")
@click.option('--wrap', type=bool, default=False, help="Object policy Allow Wrap. "
                                                      "Disabled by Default")
@click.option('--generate', type=bool, default=False, help="Object policy Allow Generate. "
                                                           "Disabled by Default")
@click.option('--write', type=bool, default=True, help="Object policy Allow Write. "
                                                       "Enabled by Default")
@click.option('--read', type=bool, default=True, help="Object policy Allow Read. "
                                                      "Enabled by Default")
@click.option('--import_export', type=bool, default=False,
              help="Object policy Allow Import Export. Disabled by Default")
@click.option('--desfire_auth', type=bool, default=False,
              help="Object policy Allow to perform DESFire authentication. "
                   "Disabled by Default")
@click.option('--desfire_dump', type=bool, default=False,
              help="Object policy Allow to dump DESFire session keys. Disabled by Default")
@click.option('--forbid_derived_output', type=bool, default=False,
              help="Object policy Forbid Derived Output. Disabled by Default")
@click.option('--kdf_ext_random', type=bool, default=False,
              help="Object policy Allow key derivation ext random. Disabled by Default")
@click.option('--tls_kdf', type=bool, default=False,
              help="Object policy Allow tls kdf. Disabled by Default")
@click.option('--tls_pms_kd', type=bool, default=False,
              help="Object policy Allow tls pms kd. Disabled by Default")
@click.option('--hkdf', type=bool, default=True,
              help="Object policy Allow hkdf. Enabled by Default")
@click.option('--pbkdf', type=bool, default=False,
              help="Object policy Allow pbkdf. Disabled by Default")
@click.option('--desfire_kd', type=bool, default=False,
              help="Object policy Allow desfire kd. Disabled by Default")
@click.option('--forbid_external_iv', type=bool, default=False,
              help="Object policy forbid external IV. Disabled by Default")
@click.option('--usage_hmac_pepper', type=bool, default=False,
              help="Object policy Allow usage hmac as pepper. Disabled by Default")
@click.option('--desfire_change_key', type=bool, default=False,
              help="Object policy Allow desfire change key. Disabled by Default")
@click.option('--derived_input', type=bool, default=False,
              help="Object policy Allow derived input. Disabled by Default")
@click.option('--desfire_auth_id', type=str, default='0',
              help="32 bit desfire auth id for desfire_change_key policy")
@click.option('--source_key_id', type=str, default='0',
              help="32 bit source key id for derived_input policy")
@click.option('--forbid_all', type=bool, default=False, help="Object policy forbid all. "
                                                             "Disabled by Default")
@click.option('--delete', type=bool, default=True, help="Object policy Allow Delete. "
                                                        "Enabled by Default")
@click.option('--req_sm', type=bool, default=False, help="Object policy Require Secure Messaging. "
                                                         "Disabled by Default")
@click.option('--req_pcr_val', type=bool, default=False, help="Object policy Require PCR Value. "
                                                         "Disabled by Default")
@click.option('--pcr_obj_id', type=str, default='0', help="Object policy PCR object ID in HEX format. "
                                                          "Zero by Default")
@click.option('--pcr_expected_value', type=str, default='', help="Object policy PCR Expected in Hex byte string "
                                                                 "Value. Zero by Default")
def symkey(cli_ctx, policy_name, auth_obj_id, sign, verify, encrypt, decrypt, key_derive,
           wrap, generate, write, read, import_export, desfire_auth, desfire_dump,
           forbid_derived_output, kdf_ext_random,
           tls_kdf, tls_pms_kd, hkdf, pbkdf, desfire_kd, forbid_external_iv,
           usage_hmac_pepper, desfire_change_key, derived_input, desfire_auth_id, source_key_id,
           forbid_all, delete, req_sm, req_pcr_val, pcr_obj_id, pcr_expected_value):
    """ Create Symmetric key object policy. \n

    policy_name = File name of the policy to be created.
    This policy name should be given as input while provisioning.\n

    auth_obj_id = Auth object id for each Object Policy. \n

    """
    if desfire_change_key and desfire_auth_id == '0':
        cli_ctx.log("Error: 32 bit desfire auth id required for desfire_change_key policy. Use '--desfire_auth_id' flag to enter desfire auth id")
        sys.exit(1)

    if derived_input and source_key_id == '0':
        cli_ctx.log("Error: 32 bit source key id required for derived_input policy. Use '--source_key_id' flag to enter source key id")
        sys.exit(1)

    if req_pcr_val:
        if pcr_obj_id == '0':
            cli_ctx.log("Error: PCR object ID required. Use '--pcr_obj_id' flag to enter PCR object ID in HEX format")
            sys.exit(1)
        if pcr_expected_value == '':
            cli_ctx.log("Error: Expected PCR Value required. Use '--pcr_expected_value' flag to enter Expected PCR Value in HEX byte string format")
            sys.exit(1)

    auth_obj_id = int(auth_obj_id, 16)
    pcr_obj_id  = int(pcr_obj_id, 16)
    desfire_auth_id = int(desfire_auth_id, 16)
    source_key_id = int(source_key_id, 16)
    policy_obj = Policy()
    policy_obj.sign                  = sign
    policy_obj.verify                = verify
    policy_obj.encrypt               = encrypt
    policy_obj.decrypt               = decrypt
    policy_obj.key_derive            = key_derive
    policy_obj.wrap                  = wrap
    policy_obj.generate              = generate
    policy_obj.write                 = write
    policy_obj.read                  = read
    policy_obj.import_export         = import_export
    policy_obj.desfire_auth          = desfire_auth
    policy_obj.desfire_dump          = desfire_dump
    policy_obj.forbid_derived_output = forbid_derived_output
    policy_obj.kdf_ext_random        = kdf_ext_random
    policy_obj.tls_kdf               = tls_kdf
    policy_obj.tls_pms_kd            = tls_pms_kd
    policy_obj.hkdf                  = hkdf
    policy_obj.pbkdf                 = pbkdf
    policy_obj.desfire_kd            = desfire_kd
    policy_obj.forbid_external_iv    = forbid_external_iv
    policy_obj.usage_hmac_pepper     = usage_hmac_pepper
    policy_obj.desfire_change_key    = desfire_change_key
    policy_obj.derived_input         = derived_input
    policy_obj.desfire_auth_id       = desfire_auth_id
    policy_obj.source_key_id         = source_key_id
    policy_obj.forbid_all            = forbid_all
    policy_obj.delete                = delete
    policy_obj.req_sm                = req_sm
    policy_obj.req_pcr_val           = req_pcr_val
    policy_obj.pcr_obj_id            = pcr_obj_id
    policy_obj.pcr_expected_value    = pcr_expected_value

    status = policy_obj.create_obj_policy(policy_type["Symmetric_Key"], policy_name, auth_obj_id)
    if status == apis.kStatus_SSS_Success:
        cli_ctx.log("Object Policy created successfully")
        ret_value = 0
    else:
        cli_ctx.log("Error: Could not create object Policy")
        ret_value = 1
    sys.exit(ret_value)


@policy.command('userid', short_help='Create User ID Object Policy')
@pass_context
@click.argument('policy_name', type=str, metavar='policy_name')
@click.argument('auth_obj_id', type=str, metavar='auth_obj_id')
@click.option('--write', type=bool, default=True, help="Object policy Allow Write. "
                                                       "Enabled by Default")
@click.option('--forbid_all', type=bool, default=False, help="Object policy forbid all. "
                                                             "Disabled by Default")
@click.option('--delete', type=bool, default=True, help="Object policy Allow Delete. "
                                                        "Enabled by Default")
@click.option('--req_sm', type=bool, default=False, help="Object policy Require Secure Messaging. "
                                                         "Disabled by Default")
@click.option('--req_pcr_val', type=bool, default=False, help="Object policy Require PCR Value. "
                                                         "Disabled by Default")
@click.option('--pcr_obj_id', type=str, default='0', help="Object policy PCR object ID in HEX format. "
                                                          "Zero by Default")
@click.option('--pcr_expected_value', type=str, default='', help="Object policy PCR Expected in Hex byte string "
                                                                 "Value. Zero by Default")
def userid(cli_ctx, policy_name, auth_obj_id, write, forbid_all, delete, req_sm,
    req_pcr_val, pcr_obj_id, pcr_expected_value):
    """ Create user id object policy. \n

    policy_name = File name of the policy to be created.
    This policy name should be given as input while provisioning.\n

    auth_obj_id = Auth object id for each Object Policy. \n

    """
    if req_pcr_val:
        if pcr_obj_id == '0':
            cli_ctx.log("Error: PCR object ID required. Use '--pcr_obj_id' flag to enter PCR object ID in HEX format")
            sys.exit(1)
        if pcr_expected_value == '':
            cli_ctx.log("Error: Expected PCR Value required. Use '--pcr_expected_value' flag to enter Expected PCR Value in HEX byte string format")
            sys.exit(1)
    auth_obj_id = int(auth_obj_id, 16)
    pcr_obj_id  = int(pcr_obj_id, 16)
    policy_obj = Policy()
    policy_obj.write              = write
    policy_obj.forbid_all         = forbid_all
    policy_obj.delete             = delete
    policy_obj.req_sm             = req_sm
    policy_obj.req_pcr_val        = req_pcr_val
    policy_obj.pcr_obj_id         = pcr_obj_id
    policy_obj.pcr_expected_value = pcr_expected_value
    status = policy_obj.create_obj_policy(policy_type["user_id"], policy_name, auth_obj_id)
    if status == apis.kStatus_SSS_Success:
        cli_ctx.log("Object Policy created successfully")
        ret_value = 0
    else:
        cli_ctx.log("Error: Could not create object Policy")
        ret_value = 1
    sys.exit(ret_value)


@policy.command('file', short_help='Create Binary file Object Policy')
@pass_context
@click.argument('policy_name', type=str, metavar='policy_name')
@click.argument('auth_obj_id', type=str, metavar='auth_obj_id')
@click.option('--write', type=bool, default=True, help="Object policy Allow Write. "
                                                       "Enabled by Default")
@click.option('--read', type=bool, default=True, help="Object policy Allow Read. "
                                                      "Enabled by Default")
@click.option('--forbid_all', type=bool, default=False, help="Object policy forbid all. "
                                                             "Disabled by Default")
@click.option('--delete', type=bool, default=True, help="Object policy Allow Delete. "
                                                        "Enabled by Default")
@click.option('--req_sm', type=bool, default=False, help="Object policy Require Secure Messaging. "
                                                         "Disabled by Default")
@click.option('--req_pcr_val', type=bool, default=False, help="Object policy Require PCR Value. "
                                                         "Disabled by Default")
@click.option('--pcr_obj_id', type=str, default='0', help="Object policy PCR object ID in HEX format. "
                                                          "Zero by Default")
@click.option('--pcr_expected_value', type=str, default='', help="Object policy PCR Expected in Hex byte string "
                                                                 "Value. Zero by Default")
def file(cli_ctx, policy_name, auth_obj_id, write, read, forbid_all, delete, req_sm, req_pcr_val, pcr_obj_id, pcr_expected_value):
    """ Create Binary file object policy. \n

    policy_name = File name of the policy to be created.
    This policy name should be given as input while provisioning.\n

    auth_obj_id = Auth object id for each Object Policy. \n

    """
    if req_pcr_val:
        if pcr_obj_id == '0':
            cli_ctx.log("Error: PCR object ID required. Use '--pcr_obj_id' flag to enter PCR object ID in HEX format")
            sys.exit(1)
        if pcr_expected_value == '':
            cli_ctx.log("Error: Expected PCR Value required. Use '--pcr_expected_value' flag to enter Expected PCR Value in HEX byte string format")
            sys.exit(1)
    auth_obj_id = int(auth_obj_id, 16)
    pcr_obj_id  = int(pcr_obj_id, 16)
    policy_obj = Policy()
    policy_obj.write              = write
    policy_obj.read               = read
    policy_obj.forbid_all         = forbid_all
    policy_obj.delete             = delete
    policy_obj.req_sm             = req_sm
    policy_obj.req_pcr_val        = req_pcr_val
    policy_obj.pcr_obj_id         = pcr_obj_id
    policy_obj.pcr_expected_value = pcr_expected_value
    status = policy_obj.create_obj_policy(policy_type["file"], policy_name, auth_obj_id)
    if status == apis.kStatus_SSS_Success:
        cli_ctx.log("Object Policy created successfully")
        ret_value = 0
    else:
        cli_ctx.log("Error: Could not create object Policy")
        ret_value = 1
    sys.exit(ret_value)


@policy.command('counter', short_help='Create Counter Object Policy')
@pass_context
@click.argument('policy_name', type=str, metavar='policy_name')
@click.argument('auth_obj_id', type=str, metavar='auth_obj_id')
@click.option('--write', type=bool, default=True, help="Object policy Allow Write. "
                                                       "Enabled by Default")
@click.option('--read', type=bool, default=True, help="Object policy Allow Read. "
                                                      "Enabled by Default")
@click.option('--forbid_all', type=bool, default=False, help="Object policy forbid all. "
                                                             "Disabled by Default")
@click.option('--delete', type=bool, default=True, help="Object policy Allow Delete. "
                                                        "Enabled by Default")
@click.option('--req_sm', type=bool, default=False, help="Object policy Require Secure Messaging. "
                                                         "Disabled by Default")
@click.option('--req_pcr_val', type=bool, default=False, help="Object policy Require PCR Value. "
                                                         "Disabled by Default")
@click.option('--pcr_obj_id', type=str, default='0', help="Object policy PCR object ID in HEX format. "
                                                          "Zero by Default")
@click.option('--pcr_expected_value', type=str, default='', help="Object policy PCR Expected in Hex byte string "
                                                                 "Value. Zero by Default")
def counter(cli_ctx, policy_name, auth_obj_id, write, read, forbid_all, delete, req_sm, req_pcr_val, pcr_obj_id, pcr_expected_value):
    """ Create Counter object policy. \n

    policy_name = File name of the policy to be created.
    This policy name should be given as input while provisioning.\n

    auth_obj_id = Auth object id for each Object Policy. \n

    """
    if req_pcr_val:
        if pcr_obj_id == '0':
            cli_ctx.log("Error: PCR object ID required. Use '--pcr_obj_id' flag to enter PCR object ID in HEX format")
            sys.exit(1)
        if pcr_expected_value == '':
            cli_ctx.log("Error: Expected PCR Value required. Use '--pcr_expected_value' flag to enter Expected PCR Value in HEX byte string format")
            sys.exit(1)
    auth_obj_id = int(auth_obj_id, 16)
    pcr_obj_id  = int(pcr_obj_id, 16)
    policy_obj = Policy()
    policy_obj.write              = write
    policy_obj.read               = read
    policy_obj.forbid_all         = forbid_all
    policy_obj.delete             = delete
    policy_obj.req_sm             = req_sm
    policy_obj.req_pcr_val        = req_pcr_val
    policy_obj.pcr_obj_id         = pcr_obj_id
    policy_obj.pcr_expected_value = pcr_expected_value
    status = policy_obj.create_obj_policy(policy_type["counter"], policy_name, auth_obj_id)
    if status == apis.kStatus_SSS_Success:
        cli_ctx.log("Object Policy created successfully")
        ret_value = 0
    else:
        cli_ctx.log("Error: Could not create object Policy")
        ret_value = 1
    sys.exit(ret_value)


@policy.command('pcr', short_help='Create PCR Object Policy')
@pass_context
@click.argument('policy_name', type=str, metavar='policy_name')
@click.argument('auth_obj_id', type=str, metavar='auth_obj_id')
@click.option('--write', type=bool, default=True, help="Object policy Allow Write. "
                                                       "Enabled by Default")
@click.option('--read', type=bool, default=True, help="Object policy Allow Read. "
                                                      "Enabled by Default")
@click.option('--forbid_all', type=bool, default=False, help="Object policy forbid all. "
                                                             "Disabled by Default")
@click.option('--delete', type=bool, default=True, help="Object policy Allow Delete. "
                                                        "Enabled by Default")
@click.option('--req_sm', type=bool, default=False, help="Object policy Require Secure Messaging. "
                                                         "Disabled by Default")
@click.option('--req_pcr_val', type=bool, default=False, help="Object policy Require PCR Value. "
                                                         "Disabled by Default")
@click.option('--pcr_obj_id', type=str, default='0', help="Object policy PCR object ID in HEX format. "
                                                          "Zero by Default")
@click.option('--pcr_expected_value', type=str, default='', help="Object policy PCR Expected in Hex byte string "
                                                                 "Value. Zero by Default")
def pcr(cli_ctx, policy_name, auth_obj_id, write, read, forbid_all, delete, req_sm, req_pcr_val,
    pcr_obj_id, pcr_expected_value):
    """ Create PCR object policy. \n

    policy_name = File name of the policy to be created.
    This policy name should be given as input while provisioning.\n

    auth_obj_id = Auth object id for each Object Policy. \n

    """
    if req_pcr_val:
        if pcr_obj_id == '0':
            cli_ctx.log("Error: PCR object ID required. Use '--pcr_obj_id' flag to enter PCR object ID in HEX format")
            sys.exit(1)
        if pcr_expected_value == '':
            cli_ctx.log("Error: Expected PCR Value required. Use '--pcr_expected_value' flag to enter Expected PCR Value in HEX byte string format")
            sys.exit(1)
    auth_obj_id = int(auth_obj_id, 16)
    pcr_obj_id  = int(pcr_obj_id, 16)
    policy_obj = Policy()
    policy_obj.write              = write
    policy_obj.read               = read
    policy_obj.forbid_all         = forbid_all
    policy_obj.delete             = delete
    policy_obj.req_sm             = req_sm
    policy_obj.req_pcr_val        = req_pcr_val
    policy_obj.pcr_obj_id         = pcr_obj_id
    policy_obj.pcr_expected_value = pcr_expected_value
    status = policy_obj.create_obj_policy(policy_type["counter"], policy_name, auth_obj_id)
    if status == apis.kStatus_SSS_Success:
        cli_ctx.log("Object Policy created successfully")
        ret_value = 0
    else:
        cli_ctx.log("Error: Could not create object Policy")
        ret_value = 1
    sys.exit(ret_value)


@policy.command('dump', short_help='Display Created Object Policy')
@pass_context
@click.argument('policy_name', type=str, metavar='policy_name')
def dump(cli_ctx, policy_name):
    """ Display Created object policy. \n

    policy_name = File name of the policy to be displayed.\n

    """
    policy_obj = Policy()
    pol_obj_params = policy_obj.get_object_policy(policy_name)
    if pol_obj_params is not None:
        policy_obj.display_policy(pol_obj_params)
        policy_obj.display_policy_in_hex(pol_obj_params)
        ret_value = 0
    else:
        cli_ctx.log("Policy file not found. Try creating policy first")
        ret_value = 1
    sys.exit(ret_value)
