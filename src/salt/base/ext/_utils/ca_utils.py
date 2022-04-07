import requests
import json
import tempfile
import logging
import sys
import binascii

if ((3, 0) <= sys.version_info <= (3, 9)):
    from urllib.parse import urljoin
elif ((2, 0) <= sys.version_info <= (2, 9)):
    from urlparse import urljoin

import atexit
from os import unlink
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import uuid
from datetime import datetime, timedelta
import pytz

import requests.packages.urllib3 as urllib3

log = logging.getLogger(__name__)

class StepClient(object):
    def __init__(self, ca_url, ca_fingerprint):
        self.url = ca_url
        self.fingerprint = ca_fingerprint
        self.root_pem = self.root()
        self.cert_bundle_fn = self._save_tempfile(self.root_pem)

    # Verifies the root fingerprint and returns the root PEM
    # from the server.
    def root(self):
        # Disable TLS verification warnings for this request.
        urllib3.warnings.simplefilter("ignore")

        with requests.get(urljoin(self.url, 'root/{}'.format(self.fingerprint)), verify=False) as r:
            root_pem = r.json()['ca']
            self._compare_fingerprints(root_pem, self.fingerprint)

        # Re-enable TLS verification warnings
        urllib3.warnings.simplefilter("default")
        return root_pem

    # sign() accepts a CSR PEM, and a JWT string.
    # It returns a cryptography.x509.Certificate object.
    # https://cryptography.io/en/latest/x509/reference/#x-509-certificate-object
    def sign(self, csr, raw_token):
        payload = json.dumps({'csr': csr.csr_pem, 'ott': raw_token})
        r = requests.post(urljoin(self.url, '1.0/sign'),
						   verify=self.cert_bundle_fn,
						   data=payload)
        r.raise_for_status()
        return x509.load_pem_x509_certificate(str(r.json()['crt']), backend=default_backend())

    def health(self):
        with requests.get(urljoin(self.url, 'health'), verify=self.cert_bundle_fn) as r:
            print(r.json())

    def _save_tempfile(self, contents):
        f = tempfile.NamedTemporaryFile(mode='w', delete=False)
        f.write(contents)
        f.close()
        atexit.register(self._tempfile_unlinker(f.name))
        return f.name

    def _tempfile_unlinker(self, fn):
        def cleanup():
            unlink(fn)
        return cleanup

    def _compare_fingerprints(self, pem, fingerprint):
        pem_bytes = bytes(str(pem).encode("utf-8"))
        cert = x509.load_pem_x509_certificate(pem_bytes, backend=default_backend())
        if cert.fingerprint(hashes.SHA256()) != binascii.a2b_hex(fingerprint):
            raise Exception("WARNING: fingerprints do not match")
        else:
            log.info('Cert verified OK. Yay!')

class CSR(object):
    def __init__(self, cn, private_key_path, dns_sans = []):
        self.key = self._load_private_key(private_key_path)
        self.cn = unicode(cn)
        self.dns_sans = dns_sans
        self.csr_pem_bytes = self._generate_csr()
        self.csr_pem = self.csr_pem_bytes.decode('UTF-8')

    def _load_private_key(self, path):
        with open(path, "r+") as private_key_file:
            private_key_str = private_key_file.read()
            private_key_bytes = bytes(str(private_key_str).encode("utf-8"))

        # private_key = crypto_serialization.load_pem_private_key(private_key_str, password=None, backend=crypto_default_backend())
        return serialization.load_pem_private_key(private_key_bytes, password=None, backend=default_backend())

    # Returns CSR PEM bytes
    def _generate_csr(self):
        return x509.CertificateSigningRequestBuilder(
            ).subject_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, self.cn)])
            ).add_extension(
                x509.ExtendedKeyUsage([
                    x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                    x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH
                ]),
                critical=False
            ).sign(self.key, hashes.SHA256(), backend=default_backend()
            ).public_bytes(serialization.Encoding.PEM)

    # Returns an encrypted PEM of the private key
    def key_pem(self, passphrase):
        return self.key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.BestAvailableEncryption(bytes(passphrase, 'UTF-8')),
        )