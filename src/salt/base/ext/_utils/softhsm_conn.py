import logging
import binascii
import base64
import subprocess
import re
from cryptography.hazmat.primitives.serialization import load_der_public_key, PublicFormat, Encoding
from cryptography.hazmat.backends import default_backend
from Cryptodome.Hash import keccak

import asn1
import ecdsa

TIME_OUT = 15  # Time out in seconds

log = logging.getLogger(__name__)
DEBUG = log.isEnabledFor(logging.DEBUG)

class SoftHSMCryptoConnection():

    def __init__(self, settings):
        self.settings = settings

    def _serial_number(self):
        return "No serialnumer for softHSM"

    def sign_string(self, data, keyid=None, hashalgo="KECCAK256", encoding="PEM"):
        command = ['edge-identity', '--lib', '/usr/lib/softhsm/libsofthsm2.so', 'sign', '--token', 'dimo', '--label', 'dimo', '--message', data, '--pin', '1234']
        
        result = subprocess.Popen(command, stdout=None, stderr=subprocess.PIPE)
        std, err = result.communicate(input=None)

        eth_start_index = err.strip().find('0x')
        if eth_start_index > -1:
            return err.strip()[eth_start_index:]
        else:
            raise Exception('Unable to find eth signature in response: {}'.format(err.strip()))

    def generate_key(self, keyid=None, confirm=False, key_type="ecc", ecc_curve="Secp256k1", policy_name=None):
        if not confirm == True:
            raise Exception("This action will generate a new key on the secure element. This could overwrite an existing key. Add 'confirm=true' to continue the operation")
        
        keys = self._keys()
        if keys:
            return "No keys already exists!"

        return 'huh?'

        command = ['edge-identity', '--lib', '/usr/lib/softhsm/libsofthsm2.so', 'generateKeyPair', '--algorithm', 'S256', '--keytype', 'EC', '--keysize', '256', '--label', 'dimo', '--token', 'dimo', '--pin', '1234']
        result = subprocess.Popen(command, stdout=None, stderr=subprocess.PIPE)
        std, err = result.communicate(input=None)

        return err.strip()

    def _keys(self):
        command = ['edge-identity', '--lib', '/usr/lib/softhsm/libsofthsm2.so', 'list', '--token', 'dimo', '--pin', '1234']
        result = subprocess.Popen(command, stdout=None, stderr=subprocess.PIPE)
        std, err = result.communicate(input=None)

        val = err.strip()
        return val

    def _public_key(self, keyid=None):
        """
        Retrieve a previously generated ECC key, will use default keyid if not specified.
        """
        return "No public key from softhsm"

    def _ethereum_address(self, keyid=None):
        """
        Retrieve a previously generated ECC key, will use default keyid if not specified.
        """
        command = ['edge-identity', '--lib', '/usr/lib/softhsm/libsofthsm2.so', 'getEthereumAddress', '--token', 'dimo', '--label', 'dimo', '--keyid', , '--pin', '1234']
        result = subprocess.Popen(command, stdout=None, stderr=subprocess.PIPE)
        std, err = result.communicate(input=None)

        val = err.strip()

        eth_start_index = val.find('0x')
        if eth_start_index > -1:
            return err.strip()[eth_start_index:]
        else:
            raise Exception('Unable to find eth address in response: {}'.format(err.strip()))

        # regex = r'0x.*'
        # res_regex = re.compile("\+CMEE: (?P<mode>[0-2])")
        # match = res_regex.search(err.strip())
        # if match:
        #     return match[0]
        # else:
        #     raise Exception('Unable to find eth address in response: {}'.format(err.strip()))

    def _device(self):
        return 'SoftHSM'

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return 0
