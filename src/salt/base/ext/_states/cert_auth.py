import logging
import salt_more
import time
import os

log = logging.getLogger(__name__)

def client_certificate_signed(name, ca_url, ca_fingerprint, token, force):
    """
    Ensure that client certificate is created from private minion key and signed from root CA server.
    """

    ret = {
        "name": name,
        "result": None,
        "changes": {},
        "comment": ""
    }

    cert_exists = os.path.exists(name)
    res = __salt__["x509.expired"](name)
    expired = res['expired']

    # Check if cert exists, if already exists, only create again if force=true
    # We could do extra checks here to verify certificate matches private key and is not expired etc.
    if (cert_exists and not expired) and not force:
        ret["result"] = True
        ret["comment"] = "Cert already exists, use force=true to overwrite"
        return ret

    res = salt_more.call_error_safe(__salt__["minionutil.sign_certificate"], ca_url, ca_fingerprint, name, token, True)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to generate and sign certificate: {:}".format(res["error"])
        return ret

    ret["result"] = True
    ret["comment"] = "Sucessfully generated and signed certificate"
    ret["changes"] = res["certificate"]

    return ret