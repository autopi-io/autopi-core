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

        # existing_key = conn._public_key(keyid)
        key_exists = conn.key_exists(keyid)

        if key_exists:
            if not force:
                raise Exception('Key already exists. - must force=true')

        conn.generate_key(keyid, confirm=confirm, policy_name=policy_name)

        key_exists = conn.key_exists(keyid=keyid)

        return { "value": key_exists }

@edmp.register_hook()
def sign_string_handler(data, keyid=None):
    with conn:
        log.info("Executing sign string on data: {}".format(data))

        signature = conn.sign_string(data=data, keyid=keyid, expected_address=context.get("ethereum_address", None))

        return { "value": signature }

@edmp.register_hook()
def key_exists_handler(keyid=None):
    with conn:
        log.info("Checking if key {} exists".format(str(keyid) if keyid else "default"))

        key_exists = conn.key_exists(keyid)

        return { "value": key_exists }

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
            log.debug("Starting crypto manager with settings: {:}".format(settings))

        # Give process higher priority
        psutil.Process(os.getpid()).nice(-1)

        # Initialize connection
        global conn

        log.info("Importing crypto connection")
        if 'atecc108A_conn' in settings:
            from atecc108a_conn import ATECC108AConn
            conn = ATECC108AConn(settings['atecc108A_conn'])
        elif 'nxpse05x_conn' in settings:
            try:
                from se05x_conn import Se05xCryptoConnection
                conn = Se05xCryptoConnection(settings['nxpse05x_conn'])
                context["ethereum_address"] = conn._ethereum_address()
            except Exception as err:
                log.error(err)
                raise Exception('Error importing or creating SE05x connection class')
        elif 'softhsm_conn' in settings:
            try:
                from softhsm_conn import SoftHSMCryptoConnection
                conn = SoftHSMCryptoConnection(settings['softhsm_conn'])
            except Exception as err:
                log.error(err)
                raise Exception('Error importing or creating SoftHSMCryptoConnection')
        else:
            raise Exception('Unknown secure element')

        # Test image code -  will fall back to the secure element that is supported.
        # try:
        #     from atecc108a_conn import ATECC108AConn
        #     conn = ATECC108AConn({ "port": 1 })
        #     conn.ensure_open()
        #     assert conn.is_open
        #     log.info('USING ATECC108A SECURE ELEMENT')
        # except Exception as ex:
        #     log.exception("Exception occurred while connecting to ATECC108A secure element. Will try using new secure element instead.")

        #     from se05x_conn import Se05xCryptoConnection
        #     conn = Se05xCryptoConnection({ "keyid": "3dc586a1" })
        #     log.info('USING *NEW* NXPS050 SECURE ELEMENT')

        # Initialize and run message processor
        log.info("Initializing crypto manager")
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))

        log.info("Starting crypto manager")
        edmp.run()

    except Exception as ex:
        log.exception("Failed to start crypto manager")

        if settings.get("trigger_events", True):
            edmp.trigger_event({
                "reason": str(ex),
            }, "system/service/{:}/failed".format(__name__.split(".")[-1]))
        
        raise

    finally:
        log.info("Stopping crypto manager")

        if getattr(conn, "is_open", False) and conn.is_open():
            try:
                conn.close()
            except:
                log.exception("Failed to close SE connection")
