import logging

from messaging import EventDrivenMessageProcessor
from mma8x5x_conn import MMA8X5XConn


log = logging.getLogger(__name__)

# Message processor
edmp = EventDrivenMessageProcessor("acc",
    default_hooks={"handler": "query"})

# MMA8X5X I2C connection
conn = MMA8X5XConn()


@edmp.register_hook()
def query_handler(cmd, *args, **kwargs):
    """
    Query/call an accelerometer function.
    """

    ret = {
        "_type": cmd.lower(),
    }

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


def start(mma8x5x_conn, **kwargs):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting accelerometer manager")

        # Configure connection
        conn.setup(mma8x5x_conn)

        # Initialize and run message processor
        edmp.init(__opts__)
        edmp.run()

    except Exception:
        log.exception("Failed to start accelerometer manager")

        raise
    finally:
        log.info("Stopping accelerometer manager")
