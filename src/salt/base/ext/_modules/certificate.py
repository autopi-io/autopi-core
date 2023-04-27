import requests
import json
import logging
import sys
import uuid
import salt.exceptions
from sha3 import keccak_256
from cryptography.hazmat.primitives import serialization

if ((3, 0) <= sys.version_info <= (3, 9)):
    from urllib.parse import urljoin
elif ((2, 0) <= sys.version_info <= (2, 9)):
    from urlparse import urljoin

import requests.packages.urllib3 as urllib3

log = logging.getLogger(__name__)

def get_oauth_token(oauth_url, eth_address):
    state = None

    assert eth_address
    assert oauth_url

    form_urlencoded_headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    # Init/generate challenge
    nonce = None

    init_params = {
        "domain": "http://127.0.0.1:10000",
        "client_id": "step-ca",
        "response_type": "code",
        "scope": "openid email",
        "address": eth_address
    }
    with requests.post(urljoin(oauth_url, "auth/web3/generate_challenge"), params=init_params) as r:
        r.raise_for_status()
        state = r.json()['state']
        nonce = r.json()['challenge']

    # 3. Hash and sign challenge
    challenge = "\x19Ethereum Signed Message:\n{}{}".format(len(nonce), nonce)
    hashed = keccak_256(challenge).hexdigest()
    signed_challenge = __salt__["crypto.sign_string"](hashed)['value']
    log.info('signed: {}'.format(signed_challenge))

    # 4. submit challenge
    access_token = None

    challenge_submit_params = {
        "client_id": "step-ca",
        "domain": "http://127.0.0.1:10000",
        "grant_type": "authorization_code",
        "state": state,
        "signature": signed_challenge,
        "client_secret": "step-ca-secret"
    }
    challenge_submit_params_payload = '&'.join(["{}={}".format(k,v) for k,v in challenge_submit_params.items()])

    with requests.post(urljoin(oauth_url, "auth/web3/submit_challenge"), headers=form_urlencoded_headers, data=challenge_submit_params_payload) as r:
        r.raise_for_status()
        access_token = r.json()["access_token"]

    return access_token


def sign_web3_certificate(oauth_url, ca_url, ca_fingerprint, certificate_path, key_path="/etc/salt/pki/minion/minion.pem", confirm=False):
    from ca_utils import CSR, StepClient

    if not confirm:
        raise salt.exceptions.CommandExecutionError(
            "This command will create and sign a new client certificate - add parameter 'confirm=true' to continue anyway")

    eth_address = __salt__["crypto.query"]("ethereum_address").get('value', None)
    log.info('eth_address: {}'.format(eth_address))

    token = get_oauth_token(oauth_url, eth_address)

    # Generate CSR, cn = unitid with dashes
    csr = CSR(str(eth_address), key_path)

    # Sign certificate
    step_ca = StepClient(ca_url, ca_fingerprint)
    certificate = step_ca.sign(csr, token)

    certificate_pem = certificate.public_bytes(serialization.Encoding.PEM)
    
    # Save certificate
    with open(certificate_path, 'w') as cert_file:
        cert_file.write(certificate_pem)

    # Notify with event
    tag = "system/certificate/signed"
    __salt__["minionutil.trigger_event"](tag, data={
        "path": certificate_path,
        "address": eth_address,
        "ca_fingerprint": ca_fingerprint,
        "ca_url": ca_url,
    })

    return {
        "certificate": certificate_pem
    }

def expire_trigger(result):
    # check if certificate will expire, if yes, trigger event so we know it's happening.
    # then we catch that and execute the certificate sign function.
    if not result:
        tag = "system/certificate/missing"
        __salt__["minionutil.trigger_event"](tag)
    else:
        # if cert is empty: "Problem executing 'x509.will_expire': PEM does not contain a single entry of type CERTIFICATE:"
        if isinstance(result, salt.exceptions.CommandExecutionError):
            tag = "system/certificate/invalid"
            __salt__["minionutil.trigger_event"](tag, data={
                "issue": str(result)
            })
            return
        
        will_expire = result.get('will_expire', None)
        if will_expire: # will_expire is true
            tag = "system/certificate/expiring"
            __salt__["minionutil.trigger_event"](tag, data={
                "path": result.get('path'),
                "within_days": result.get('check_days')
            })
        elif will_expire == False: # will_expire is false
            # This is for debug and visibility.
            tag = "system/certificate/valid"
            __salt__["minionutil.trigger_event"](tag, data={
                "path": result.get('path'),
                "within_days": result.get('check_days')
            })
        else: # will_expire is None which means that the certificate could be invalid.
            tag = "system/certificate/invalid"
            __salt__["minionutil.trigger_event"](tag, data={
                "path": result.get('path'),
                "within_days": result.get('check_days')
            })