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
    if generated_public_key_value:
        ret["result"] = True
        ret["comment"] = "New key generated"
        ret["changes"]["new"] = generated_public_key_value
        return ret

    ret["result"] = False
    ret["comment"] = "Returned key was empty"
    return ret