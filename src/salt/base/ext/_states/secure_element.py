import logging
import salt_more
import time
import os
import subprocess

log = logging.getLogger(__name__)

def provisioned(name):
    """
    Ensure that secure element is provisioned / has a Secp256k1 private key in the specific keyid.
    """

    ret = {
        "name": name,
        "result": None,
        "changes": {},
        "comment": ""
    }

    device = __salt__["crypto.query"]("device").get("value")

    log.info("Provisioning Secure Element as {}".format(device))

    if device == "NXPS05X":
        # Can we just use the generate_key function? It will fail if key already exists...

        # # Check if secure element has required key, use query public key.
        # If no public key available, try to do the regenerate key method.
        try:
            public_key = __salt__["crypto.query"]("public_key")
            public_key_value = public_key.get('value', None)
            if public_key_value:
                if not public_key_value.startswith("-----BEGIN PUBLIC KEY-----"):
                    ret["result"] = True
                    ret["comment"] = "Key already exists"
                    return ret
                
            # Todo catch specific exception that key does not exist, not all exceptions!
            # no connection or something should not make it try to regenerate key!
        except Exception:
            pass

        try:
            generated_public_key = __salt__["crypto.generate_key"](confirm=True, force=False, policy_name="NoMod")
        except Exception as ex:
            if "Key already exists" in str(ex):
                ret["result"] = True
                ret["comment"] = "Key already exists"
                return ret
            else:
                ret["result"] = False
                ret["comment"] = "Generate key threw exception: {}".format(str(ex))
                return ret

        generated_public_key_value = generated_public_key.get('value', "")
        if generated_public_key_value.startswith("-----BEGIN PUBLIC KEY-----"):
            ret["result"] = True
            ret["comment"] = "New key generated"
            ret["changes"]["new"] = generated_public_key_value
            return ret
        
        ret["result"] = False
        ret["comment"] = "Returned key does not start with '-----BEGIN PUBLIC KEY-----'"
        return ret

    elif device == "SoftHSM":
        
        # Generate the token
        try:
            token_exists = __salt__["crypto.query"]("token_exists").get("value")
            if not token_exists:
                log.info("Generating a SoftHSM token")
                __salt__["crypto.query"]("generate_token")

        except Exception as ex:
            ret["result"] = False
            ret["comment"] = "SoftHSM token generation threw exception: {}".format(str(ex))

        # Generate the keys
        try:
            key_valid = __salt__["crypto.key_exists"]().get("value")
            if key_valid:
                ret["result"] = True
                ret["comment"] = "Key already exists"
                return ret

            log.info("Genearting a new key")
            
            __salt__["crypto.generate_key"](confirm=True, force=False, policy_name="NoMod")

            ret["result"] = True
            ret["comment"] = "New key generated"
            return ret

        except Exception as ex:
            ret["result"] = False
            ret["comment"] = "SoftHSM key generation threw exception: {}".format(str(ex))
            return ret
    else:
        raise Exception("Unknown secure element device: {}".format(device))