import logging
import os
import psutil
import time
import salt.exceptions

from common_util import call_retrying
from messaging import EventDrivenMessageProcessor
from threading_more import intercept_exit_signal
from retrying import retry
from se05x_conn import Se05xCryptoConnection

log = logging.getLogger(__name__)

context = {
    "state": None
}

# Message processor
edmp = EventDrivenMessageProcessor("crypto", context=context, default_hooks={"handler": "query"})

# CRYPTO connection is instantiated during start
conn = None

@edmp.register_hook()
def generate_key_handler(confirm=False, keyid=None):
    with conn:
        log.info("Generating key")

        conn.generate_key(confirm=confirm)
        key_string = conn._public_key()

        return { "value": key_string }

@edmp.register_hook()
def sign_string_handler(data, keyid=None):
    log.info("Executing sign string on data: {}".format(data))

    with conn:
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
