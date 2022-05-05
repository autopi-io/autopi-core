import logging
import salt_more
import time
import os


log = logging.getLogger(__name__)


def client_certificate_signed(name, ca_url, ca_fingerprint, token, force, key_path="/etc/salt/pki/minion/minion.pem"):
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
    expired = False
    if cert_exists:
        try:
            res = __salt__["x509.expired"](name)
            expired = res.get('expired', False)
        except Exception:
            log.exception('x509.expired failed somehow. Continuing expecting cert to not be expired.')

    # Check if cert exists, if already exists, only create again if force=true
    # We could do extra checks here to verify certificate matches private key and is not expired etc.
    if (cert_exists and not expired) and not force:
        ret["result"] = True
        ret["comment"] = "Certificate already exists, use force=true to overwrite"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Certificate will be generated and signed"
        return ret

    res = salt_more.call_error_safe(__salt__["minionutil.sign_certificate"], ca_url, ca_fingerprint, name, token, key_path=key_path, confirm=True)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to generate and sign certificate: {:}".format(res["error"])
        return ret

    ret["result"] = True
    ret["comment"] = "Sucessfully generated and signed certificate"
    ret["changes"] = res["certificate"]

    return ret