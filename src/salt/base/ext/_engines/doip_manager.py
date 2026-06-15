import binascii
import logging
import socket
import time
import types

from messaging import EventDrivenMessageProcessor

log = logging.getLogger(__name__)

try:
    from udsoncan.client import Client
    from udsoncan.connections import SocketConnection
except:
    log.warning("Unable to import 'udsoncan'")

BOARD_VERSION_1_3 = "1.3"
BOARD_VERSION_1_4 = "1.4"
BOARD_VERSION_1_6 = "1.6"

context = {}

# Message processor
edmp = EventDrivenMessageProcessor("doip", context=context, default_hooks={"workflow": "extended"})

# UDS client connection
class TCPSocketConnection(SocketConnection):

    def __init__(self, host=None, port=None, timeout=0.1, **kwargs):
        self.host = host
        self.port = port
        self.timeout = timeout

        super(TCPSocketConnection, self).__init__(None, **kwargs)

    def open(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)  # For recv
        self.sock.connect((self.host, self.port))

        super(TCPSocketConnection, self).open()

    def close(self):
        super(TCPSocketConnection, self).close()

        self.sock.close()

        log.info("Connection closed")

conn = TCPSocketConnection()
client = Client(conn)


@edmp.register_hook(synchronize=False)
def context_handler(key=None):
    """
    Gets current context.
    """

    if key:
        return context.get(key, None)

    return context


@edmp.register_hook()
def interface_handler(*cmds, **kwargs):
    """
    Manages the DoIP interface.
    """

    ret = {}

    board_version = context.get("settings", {}).get("board_version", "1.3")
    if not board_version in [BOARD_VERSION_1_3, BOARD_VERSION_1_4, BOARD_VERSION_1_6]:
        raise ValueError("The configured board version '{}' is not supported".format(board_version))

    ret["board_version"] = board_version

    for cmd in cmds:
        if cmd == "help":
            ret["commands"] = ["activate", "deactivate", "connect", "disconnect", "reconnect"]

            return ret
        elif cmd == "activate":

            # Ensure correct pin setup
            pin_setup = kwargs.get("pin_setup", context.get("settings", {}).get("default_pin_setup", "main"))
            if pin_setup == "main":
                if board_version == BOARD_VERSION_1_3:
                    __salt__["spm.query"]("ext_pins", low="ext_misc2", high="ext_misc1")
                elif board_version == BOARD_VERSION_1_4:
                    __salt__["spm.query"]("ext_pins", high="ext_misc2")
                elif board_version == BOARD_VERSION_1_6:
                    __salt__["spm.query"]("ext_pins", low="ext_misc2")
            elif pin_setup == "alt":
                if board_version == BOARD_VERSION_1_3:
                    __salt__["spm.query"]("ext_pins", low="ext_misc1", high="ext_misc2")
                elif board_version == BOARD_VERSION_1_4:
                    __salt__["spm.query"]("ext_pins", low="ext_misc2")
                elif board_version == BOARD_VERSION_1_6:
                    __salt__["spm.query"]("ext_pins", high="ext_misc2")
            else:
                raise ValueError("Unsupported value of 'pin_setup': {}".format(pin_setup))

            # Enable the pin switch only for v1.4 and v1.6
            if board_version == BOARD_VERSION_1_4:
                __salt__["spm.query"]("ext_pins", low="ext_misc1")  # NOTE: Low is enabled on v1.4
            elif board_version == BOARD_VERSION_1_6:
                __salt__["spm.query"]("ext_pins", high="ext_misc1")  # NOTE: High is enabled on v1.6

            __salt__["spm.query"]("usr_pins", high="doip_act")
        elif cmd == "deactivate":
            __salt__["spm.query"]("usr_pins", low="doip_act")

            # Disable pins
            if board_version == BOARD_VERSION_1_4:
                __salt__["spm.query"]("ext_pins", high="ext_misc1,ext_misc2")  # NOTE: High is disabled
            else:  # Coincidentally the same for for v1.3 and v1.6
                __salt__["spm.query"]("ext_pins", low="ext_misc1,ext_misc2")
        elif cmd == "connect":
            client.open()
        elif cmd == "disconnect":
            client.close()
        elif cmd == "reconnect":
            client.close()
            client.open()
        else:
            raise ValueError("Unsupported command '{:}'".format(cmd))

    res = __salt__["spm.query"]("usr_pins")
    ret["state"] = "activated" if res["output"]["doip_act"] else "deactivated"

    res = __salt__["spm.query"]("ext_pins")

    if board_version == BOARD_VERSION_1_3:
        if res["output"]["ext_misc1"]:
            ret["pin_setup"] = "main" 
        elif res["output"]["ext_misc2"]:
            ret["pin_setup"] = "alt"
        else:
            ret["pin_setup"] = "none"
    elif board_version == BOARD_VERSION_1_4:
        ret["pin_switch"] = "off" if res["output"]["ext_misc1"] else "on"
        ret["pin_setup"] = "main" if res["output"]["ext_misc2"] else "alt"
    elif board_version == BOARD_VERSION_1_6:
        ret["pin_switch"] = "on" if res["output"]["ext_misc1"] else "off"
        ret["pin_setup"] = "alt" if res["output"]["ext_misc2"] else "main"

    ret["connection"] = {
        "state": "opened" if conn.is_open() else "closed",
        "host": conn.host,
        "port": conn.port
    }

    return ret


@edmp.register_hook()
def uds_handler(cmd, *args, **kwargs):
    """
    Queries using the UDS client. The UDS client works synchronously and can handle a single request/response at a time.
    """

    ret = {
        "_type": cmd.lower(),
    }

    def get_func(name):
        try:
            return getattr(client, name)
        except AttributeError:
            raise ValueError("Unsupported command: {:s}".format(name))

    if cmd == "help":
        if args:
            for arg in args:
                ret[arg] = get_func(arg).__doc__ or "N/A"
        else:
            ret["commands"] = [f for f in dir(client) if not f.startswith("_") and type(getattr(client, f)) == types.MethodType]

        return ret

    res = get_func(cmd)(*args, **kwargs)
    if res != None:

        def to_dict(val):
            if hasattr(val, "__dict__"):
                ret = {}

                for k, v in val.__dict__.iteritems():

                    # Skip hidden attributes and callables
                    if k.startswith("_") or callable(v):
                        continue

                    ret[k] = to_dict(v)

                return ret

            elif isinstance(val, (bytes, bytearray)):
                return binascii.hexlify(val)

            return val

        ret.update(to_dict(res))

    return ret


def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting the DoIP manager with settings: {:}".format(settings))

        # Store settings in the context
        context["settings"] = settings

        # Configure the TCP socket connection
        conn.host = settings.get("host", "127.0.0.1")
        conn.port = settings.get("port", 13400)
        conn.timeout = settings.get("timeout", 0.1)

        # Initialize and run the message processor
        edmp.init(__salt__, __opts__,
            namespace=settings.get("namespace", None),
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        edmp.run()

    except Exception as ex:
        log.exception("Failed to start the DoIP manager")

        if settings.get("trigger_events", True):
            try:
                edmp.trigger_event({
                    "reason": str(ex),
                }, "system/service/{:}/failed".format(__name__.split(".")[-1]))
            except:
                log.exception("Unable to trigger service failed event")

        restart_delay = settings.get("restart_delay", 1)
        if restart_delay:
            log.info("Enforcing restart delay of {:} second(s)...".format(restart_delay))
            time.sleep(restart_delay)

        raise

    finally:
        log.info("Stopping the DoIP manager")

        # Close client connection
        try:
            client.close()
        except:
            log.exception("Failed to close the UDS client connection")
