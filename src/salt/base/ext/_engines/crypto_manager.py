import logging
import os
import psutil
import time
import salt.exceptions

from common_util import call_retrying
from messaging import EventDrivenMessageProcessor
from threading_more import intercept_exit_signal
from retrying import retry

log = logging.getLogger(__name__)

try:
    from se05x_conn import Se05xCryptoConnection
except Exception as err:
    log.warning("Failed to import SE05x connection class. Library (.so) files possibly not found.")

context = {
    "state": None
}

# Message processor
edmp = EventDrivenMessageProcessor("crypto", context=context, default_hooks={"handler": "query"})

# CRYPTO connection is instantiated during start
conn = None

@edmp.register_hook()
def generate_key_handler(keyid=None, confirm=False, force=False, policy_name=None):
    with conn:
        log.info("Generating key")

        existing_key = conn._public_key(keyid)
        if existing_key:
            log.info('Existing public key: {}'.format(existing_key))
            if not force:
                raise Exception('Key already exists. - must force=true')

        conn.generate_key(keyid, confirm=confirm, policy_name=policy_name)
        key_string = conn._public_key(keyid)
        log.info('New public key: {}'.format(key_string))

        if existing_key == key_string:
            raise Exception('Command returned but key DID NOT CHANGE. Maybe the keyid is a reserved range or the security policy does not allow regenerating the key?')

        return { "value": key_string }

@edmp.register_hook()
def sign_string_handler(data, keyid=None):
    with conn:
        log.info("Executing sign string on data: {}".format(data))

        signature = conn.sign_string(data, keyid)

        return { "value": signature }

@edmp.register_hook()
def query_handler(cmd, *args, **kwargs):
    """
    Queries a given command.

    Arguments:
      - cmd (str): The command to query.
    """

    ret = {
        "_type": cmd.lower(),
    }

    if not cmd.startswith('_'):
        cmd = "_{}".format(cmd)

    try:
        func = getattr(conn, cmd)
    except AttributeError:
        ret["error"] = "Unsupported command: {:s}".format(cmd)
        return ret

    with conn:
        res = func(*args, **kwargs)
        if res != None:
            if isinstance(res, dict):
                ret.update(res)
            else:
                ret["value"] = res

    return ret

@intercept_exit_signal
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting CRYPTO manager with settings: {:}".format(settings))

        # Give process higher priority
        psutil.Process(os.getpid()).nice(-1)

        # Initialize connection
        global conn

        log.warning(settings)

        if 'nxpse050_conn' in settings:
            conn = Se05xCryptoConnection(settings['nxpse050_conn'])
        else:
            raise Exception('Unknown secure element')

        # Initialize and run message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        edmp.run()

    except Exception:
        log.exception("Failed to start CRYPTO manager")
        
        raise
    finally:
        log.info("Stopping CRYPTO manager")

        if getattr(conn, "is_open", False) and conn.is_open():
            try:
                conn.close()
            except:
                log.exception("Failed to close SE connection")
