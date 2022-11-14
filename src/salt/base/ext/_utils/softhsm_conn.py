import logging
import binascii
import base64
from random import randrange
import subprocess
import re
from cryptography.hazmat.primitives.serialization import load_der_public_key, PublicFormat, Encoding
from cryptography.hazmat.backends import default_backend
from Cryptodome.Hash import keccak

import pexpect
import asn1
import ecdsa

TIME_OUT = 15  # Time out in seconds

log = logging.getLogger(__name__)
DEBUG = log.isEnabledFor(logging.DEBUG)

DEFAULT_TOKEN_LABEL = "autopipi"
DEFAULT_PIN = "1234"
LIBRARY_PATH = '/usr/lib/softhsm/libsofthsm2.so'

class SoftHSMCryptoConnection():

    def __init__(self, settings):
        self.settings = settings
        self.default_key_label = str(settings["keyid"])

    def _serial_number(self):
        return "No serialnumer for softHSM"

    def get_key_count(self, keys):
        return len(re.findall(r"\[Object [0-9]*\]", keys))

    def keys_by_label(self, label):
        command = ['edge-identity', 'list', 
            '--lib', LIBRARY_PATH, 
            '--token', DEFAULT_TOKEN_LABEL, 
            '--label', label, 
            '--pin', DEFAULT_PIN]
        self.print_command(command)

        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        std, err = result.communicate(input=None)

        if (err):
            log.info("[WARNING] Has error: {}".format(err.strip()))

        return std.strip()

    def print_command(self, cmd):
        cmd_string = ""
        for word in cmd:
            cmd_string = "{} {}".format(cmd_string, word)

        log.info(cmd_string)

    def sign_string(self, data, keyid=None, hashalgo="KECCAK256", encoding="PEM"):
        label = self.default_key_label if keyid == None else str(keyid)

        command = ['edge-identity', 'sign', 
            '--lib', LIBRARY_PATH, 
            '--token', DEFAULT_TOKEN_LABEL, 
            '--label', label, 
            '--message', data, 
            '--pin', DEFAULT_PIN]
        
        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        std, err = result.communicate(input=None)
        val = err.strip()

        sig = re.findall(r"Signature (?P<signature>0x[0-9a-fA-F]*)[*]*$", val)

        log.info("Val: {}".format(val))
        log.info("Sig: {}".format(sig))

        if len(sig) == 1:
            return sig[0]
        else:
            raise Exception('Unable to find eth signature in response. \nStdout: {} \nStderr: {}'.format(std.strip(), err.strip()))

    def generate_key(self, keyid=None, confirm=False, key_type="ecc", ecc_curve="Secp256k1", policy_name=None):

        if not confirm:
            raise Exception("This action will generate a new key on the secure element. This could overwrite an existing key. Add 'confirm=true' to continue the operation")

        if key_type != "ecc":
            raise Exception("Unknown key_type. Allowed: ['ecc']")

        label = str(keyid) if keyid else self.default_key_label
        log.info("Generating key with label {}".format(label))

        keys_string = self.keys_by_label(label)

        if self.get_key_count(keys_string) > 0:
            raise Exception("Key with token/label combination has too many matches (key already exists)")

        command = ['edge-identity', 'generateKeyPair', 
            '--lib', LIBRARY_PATH, 
            '--algorithm', 'S256', 
            '--keytype', 'EC', 
            '--keysize', '256', 
            '--label', label, 
            '--token', DEFAULT_TOKEN_LABEL, 
            '--pin', DEFAULT_PIN]
        self.print_command(command)

        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        std, err = result.communicate(input=None)

        return std.strip()


    def _keys(self):
        command = ['edge-identity', 'list', 
            '--lib', LIBRARY_PATH, 
            '--token', DEFAULT_TOKEN_LABEL, 
            '--pin', DEFAULT_PIN]
        self.print_command(command)

        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        std, err = result.communicate(input=None)

        log.info("Std: {}".format(std))

        if (err):
            log.warning("Has error: {}".format(err.strip()))

        val = std.strip()

        return val

    def key_exists(self, keyid=None):
        label = str(keyid) if keyid else self.default_key_label 

        log.info("Label: {}".format(label))
        key_count = self.get_key_count(self.keys_by_label(label))

        log.info("Key Count: {}".format(key_count))
        return key_count > 0

    def _ethereum_address(self, keyid=None):
        """
        Retrieve a previously generated ECC key, will use default keyid if not specified.
        """
        label = self.default_key_label if keyid == None else str(keyid)

        command = ['edge-identity', 'getEthereumAddress',
            '--lib', LIBRARY_PATH,  
            '--token', DEFAULT_TOKEN_LABEL, 
            '--label', label, 
            '--pin', DEFAULT_PIN]
        self.print_command(command)

        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        std, err = result.communicate(input=None)

        # Issue with the getEthereumAddress command. Outputs to stderr
        val = err.strip()
        
        matches = re.findall(r"0x[0-9A-Fa-f]{40}", val)
        if len(matches) == 1:
            return matches[0]
        else:
            raise Exception('Unable to find eth address in response: {}'.format(val))

    def _public_key(self, keyid=None):
        """
        Retrieve a previously generated ECC key, will use default keyid if not specified.
        """
        raise AttributeError("SoftHSM does not support retrieving public keys")

        ## There is the EC point, though I don't see the point in handling the formatting since all we need is the ETH address.
         
        # label = self.default_key_label if keyid == None else str(keyid)
        # keys_str = self.keys_by_label(label)

        # ec_points = re.findall(r"CKA_EC_POINT: (?P<point>[0-9a-fA-F]*) \(hex\)", keys_str)
        # if len(ec_points) == 1:
        #     return ec_points[0]
        # elif len(ec_points) > 1:
        #     raise Exception("Retrieved more than 1 public key. Got {}".format(len(ec_points)))
        # else:
        #     return None

    def get_slots(self):
        command = ["softhsm2-util", "--show-slots"]
        self.print_command(command)

        proc = subprocess.Popen(command, stdout=subprocess.PIPE)
        out, err = proc.communicate(input=None)
        val = out.strip()

        slots = re.split(r"(Slot [0-9]+\n)", val)[1:]
        slots = zip(slots[::2], slots[1::2])

        slot_dict_list = []

        for slot in slots:
            
            slot_dict = {
                "id": slot[0].strip().split(" ")[1]
            }

            for line in slot[1].splitlines():

                if "Label" in line:
                    words = re.sub(" +", " ", line).strip().split(" ")
                    slot_dict["label"] = words[-1] if len(words) > 1 else None

                if "Initialized" in line:
                    words = re.sub(" +", " ", line).strip().split(" ")
                    slot_dict["init"] = bool(len(words) > 1 and words[-1] == "yes")

            slot_dict_list.append(slot_dict)

        return slot_dict_list

    def _token_exists(self, label=None):
        label = label if label else DEFAULT_TOKEN_LABEL

        slots = self.get_slots()

        for slot in slots:
            if slot["label"] == label:
                return True
        
        return False


    def _generate_token(self, label=None):

        label = label if label else DEFAULT_TOKEN_LABEL

        log.info("Generating new token with label {}".format(label))

        child = pexpect.spawn("softhsm2-util --init-token --free --label {} --pin {}".format(label, DEFAULT_PIN), timeout=5)

        child.expect(".*enter SO PIN: .*")
        child.sendline(DEFAULT_PIN)
        child.expect(".*reenter SO PIN: .*")
        child.sendline(DEFAULT_PIN)
        child.wait()

        log.info("Token generated")

        # TODO EP: Proper return
        return True


    def _device(self):
        return 'SoftHSM'

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return 0

if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

    AUTOPI_KEY_ID = "3dc5861"
    RAINDOM_KEY_ID = randrange(1, 0xFFFFFFFF)

    settings = {
        "keyid": "auf"
    }
    conn = SoftHSMCryptoConnection(settings)
    
    # conn._create_token("auf")
    exists = conn._token_exists("auf")
    log.info(exists)

    exists = conn._token_exists("autopi")
    log.info(exists)

    exists = conn._token_exists("BingyBongo")
    log.info(exists)
    
    # keys = conn._keys()

    # log.info("Geting public key")
    # p_key = conn._public_key()
    # print(p_key)

    # log.info("Generating key with id {}".format(settings["keyid"]))
    # conn.generate_key(confirm=True)

    # log.info("Retrieving ethereum address")
    # eth_addr = conn._ethereum_address(keyid=keyid)
    # log.info("Eth addr: {}".format(eth_addr))

    # sig_data = "Red Apples"
    # log.info("Signing string {}".format(sig_data))
    # signature = conn.sign_string(sig_data, keyid=keyid)
    # log.info("Signature: {}".format(signature))

    # sig_data = "Red Apples"
    # log.info("Signing string {}".format(sig_data))
    # signature = conn.sign_string(sig_data, keyid=settings["keyid"])
    # log.info("Signature: {}".format(signature))

    # log.info("-- Generating key")
    # conn.generate_key(settings["keyid"], confirm=True)

    # log.info("-- Getting keys by label")
    # log.info(conn.keys_by_label(settings["keyid"]))

    # log.info("-- Checking if key exists")
    # log.info(conn.key_exists(settings["keyid"]))

    # log.info(conn._public_key("default"))
