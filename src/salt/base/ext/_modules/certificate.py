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

    json_headers = {
        'Content-Type': 'application/json'
    }

    # 1. Initiate oauth flow, get state
    init_params = {
        "action": "subscribe",
        "redirect_uri": "http://127.0.0.1:10000",
        "client_id": "step-ca",
        "response_type": "code",
        "scope": "openid email",
        "state": "S256"
    }
    with requests.post(urljoin(oauth_url, "auth/web3/init"), params=init_params) as r:
        r.raise_for_status()
        state = r.json()['state']

    assert state
    
    # 2. Get challenge
    nonce = None
    challenge_payload = {
        "address": eth_address,
        "state": str(state),
    }
    with requests.post(urljoin(oauth_url, "auth/web3/challenge"), headers=json_headers, json=challenge_payload) as r:
        r.raise_for_status()
        nonce = r.json()["nonce"]

    # 3. Hash and sign challenge
    challenge = "\x19Ethereum Signed Message:\n{}{}".format(len(nonce), nonce)
    hashed = keccak_256(challenge).hexdigest()
    signed_challenge = __salt__["crypto.sign_string"](hashed)['value']
    log.info('signed: {}'.format(signed_challenge))

    # 4. submit challenge
    verify_payload = {
        "signed": signed_challenge,
        "state": state
    }
    with requests.post(urljoin(oauth_url, "auth/web3/verify_direct"), headers=json_headers, json=verify_payload) as r:
        r.raise_for_status()
        code = r.json()["code"]
        log.info('Verified signature, received code: {}'.format(code))

    # 5. Exchange token for jwt
    access_token = None
    token_exchange_params = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": "step-ca",
        "client_secret": "step-ca-secret",
        "redirect_uri": init_params["redirect_uri"]
    }
    token_exchange_payload = '&'.join(["{}={}".format(k,v) for k,v in token_exchange_params.items()])
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    with requests.post(urljoin(oauth_url, "token"), headers=headers, data=token_exchange_payload) as r:
        log.info("Response: {}".format(r.text))
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
    
    # example {'path': '/opt/autopi/client.crt', 'check_days': 30, 'cn': '3b03b28b-b662-4fad-68e6-7e74f9ce658c', 'will_expire': False}

    # Scenario invalid certificate: will not include a will_expire field
    # X Scenario no certificate: will return empty response

    if not result:
        tag = "system/certificate/missing"
        __salt__["minionutil.trigger_event"](tag)
    else:
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