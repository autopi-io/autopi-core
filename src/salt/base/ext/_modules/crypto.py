import binascii
import logging
import salt.exceptions

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack
from retrying import retry


__virtualname__ = "crypto"

log = logging.getLogger(__name__)

client = EventDrivenMessageClient("crypto", default_timeout=15)

def __virtual__():
    return __virtualname__

def __init__(opts):
    client.init(opts)

def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"](__virtualname__)

def query(cmd, *args, **kwargs):
    """
    Queries a given SPM command.

    Arguments:
      - cmd (str): The SPM command to query.
    """
    return client.send_sync(_msg_pack(cmd, *args, **kwargs))

def sign_string(*args, **kwargs):
    """
    Signs a given string using the Secure Element 

    Arguments:
      - data (str): String to be signed
      - keyid (str/int): key's id 
    """
    return client.send_sync(_msg_pack(*args, _handler="sign_string", **kwargs))

def generate_key(*args, **kwargs):
    """
    Generates a new key in the Secure Element

    Arguments:
      - keyid (str/int): key's id
    """
    return client.send_sync(_msg_pack(*args, _handler="generate_key", **kwargs))

def key_exists(*args, **kwargs):
    return client.send_sync(_msg_pack(*args, _handler="key_exists", **kwargs))