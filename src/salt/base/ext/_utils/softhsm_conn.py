import logging
from random import randrange
import subprocess
import re

import pexpect

TIME_OUT = 15  # Time out in seconds

log = logging.getLogger(__name__)
DEBUG = log.isEnabledFor(logging.DEBUG)

class SoftHSMCryptoConnection():

    def __init__(self, settings):
        self.settings = settings
        self.default_key_label = str(settings.get("keyid", "default"))
        self.default_token_label = str(settings.get("tokenid", "autopi"))
        self.default_pin = str(settings.get("pin", "1234"))
        self.library_path = str(settings.get("libpath", '/usr/lib/softhsm/libsofthsm2.so'))
        
        # Ensure provisioned.
        token_exists = self._token_exists()
        if not token_exists:
            log.info("Generating a SoftHSM token")
            self._generate_token()

        key_exists = self.key_exists()
        if not key_exists:
            log.info("Generating a SoftHSM key")
            self.generate_key(confirm=True)


    def _serial_number(self):
        return "No serialnumber for softHSM"

    def get_key_count(self, keys):
        return len(re.findall(r"\[Object [0-9]*\]", keys))

    def get_command_string(self, cmd):
        cmd_string = ""
        for word in cmd:
            cmd_string = "{} {}".format(cmd_string, word)

        return cmd_string

    def log_raw_output(self, cmd, stdout, stderr):
        if DEBUG:
            log.debug("cmd: {}\nstdout: {}\nstderr: {}".format(self.get_command_string(cmd), stdout, stderr))

    def keys_by_label(self, label):
        command = ['edge-identity', 'list', 
            '--lib', self.library_path, 
            '--token', self.default_token_label, 
            '--label', label, 
            '--pin', self.default_pin]

        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        std, err = result.communicate(input=None)
        self.log_raw_output(command, std, err)

        return std.strip()

    def sign_string(self, data, keyid=None, hashalgo="KECCAK256", encoding="RS_HEX", expected_address=None):
        label = self.default_key_label if keyid == None else str(keyid)

        if encoding != "RS_HEX":
            raise Exception("Unsupported encoding")

        if hashalgo != "KECCAK256":
            raise Exception("Unsupported hashalgo")

        log.info(data)
        log.info(type(data))
        if type(data) == str:
            if data[:2] != "0x":
                data = "0x{}".format(data)
        else:
            data = hex(data)

        command = ['edge-identity', 'sign', 
            '--lib', self.library_path, 
            '--token', self.default_token_label, 
            '--label', label, 
            '--hash', data, 
            '--pin', self.default_pin]
        
        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        std, err = result.communicate(input=None)
        self.log_raw_output(command, std, err)

        val = err.strip()

        sig = re.findall(r"Signature (?P<signature>0x[0-9a-fA-F]*)[*]*$", val)

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
            '--lib', self.library_path, 
            '--algorithm', 'S256', 
            '--keytype', 'EC', 
            '--keysize', '256', 
            '--label', label, 
            '--token', self.default_token_label, 
            '--pin', self.default_pin]

        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        std, err = result.communicate(input=None)
        self.log_raw_output(command, std, err)

        return std.strip()


    def _keys(self):
        command = ['edge-identity', 'list', 
            '--lib', self.library_path, 
            '--token', self.default_token_label, 
            '--pin', self.default_pin]

        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        std, err = result.communicate(input=None)
        self.log_raw_output(command, std, err)

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
            '--lib', self.library_path,  
            '--token', self.default_token_label, 
            '--label', label, 
            '--pin', self.default_pin]

        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        std, err = result.communicate(input=None)
        self.log_raw_output(command, std, err)

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

    def get_slots(self):
        """
        Get dictionary of all key slots
        """
        command = ["softhsm2-util", "--show-slots"]

        proc = subprocess.Popen(command, stdout=subprocess.PIPE)
        std, err = proc.communicate(input=None)
        self.log_raw_output(command, std, err)

        val = std.strip()

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
        label = str(label) if label else self.default_token_label

        slots = self.get_slots()

        for slot in slots:
            if slot["label"] == label:
                return True
        
        return False

    def _generate_token(self, label=None):

        label = str(label) if label else self.default_token_label

        log.info("Generating new token with label {}".format(label))

        child = pexpect.spawn("softhsm2-util --init-token --free --label {} --pin {}".format(label, self.default_pin), timeout=5)

        child.expect(".*enter SO PIN: .*")
        child.sendline(self.default_pin)
        child.expect(".*reenter SO PIN: .*")
        child.sendline(self.default_pin)
        child.wait()

        log.info("Token generation steps done")

        return True

    def _device(self):
        return 'SoftHSM'

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return 0

if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

    RANDOM_KEY_ID = randrange(1, 0xFFFFFFFF)
    RANDOM_TOKEN_ID = randrange(1, 0xFFFFFFFF)

    settings = {
        "keyid": RANDOM_KEY_ID
    }
    conn = SoftHSMCryptoConnection(settings)

    token_exists = conn._token_exists()
    if not token_exists:
        conn._generate_token()

    token_exists = conn._token_exists()
    assert(token_exists)

    key_exists = conn.key_exists()
    assert(not key_exists)

    conn.generate_key(confirm=True)

    key_exists = conn.key_exists()
    assert(key_exists)

    eth_addr = conn._ethereum_address()
    assert(eth_addr.startswith("0x"))

    signature = conn.sign_string("Test String", encoding="RS_HEX")
    assert(signature.startswith("0x"))