import can
import logging

from can_conn import CANConn, decode_msg_from, encode_msg_to
from messaging import EventDrivenMessageProcessor
from six import string_types


log = logging.getLogger(__name__)

context = {}

# Message processor
edmp = EventDrivenMessageProcessor("can", context=context, default_hooks={"workflow": "extended"})

conn = None


@edmp.register_hook()
def connection_handler(autodetect=None, **kwargs):
    """
    """

    if autodetect != None:
        if autodetect == True:
            conn.autodetect()
        elif isinstance(autodetect, string_types):
            conn.autodetect(*autodetect.split(","))
        elif isinstance(autodetect, list):
            conn.autodetect(*autodetect)
        elif isinstance(autodetect, dict):
            for key, val in autodetect.iteritems():
                if conn.autodetect(key, **val):
                    break

    ret = {
        "is_open": conn.is_open(),
        "bus": dict(conn.bus_metadata, state=conn.bus_state()),
        "interface": dict(conn.settings, state=conn.interface_state())
    }

    return ret


@edmp.register_hook()
def filter_handler():
    """
    """

    ret = {
        "values": []
    }

    # TODO HN: Support add, remove etc.
    
    for filter in conn.list_filters():
        filter["id"] = "{:x}".format(filter["id"])
        filter["mask"] = "{:x}".format(filter["mask"])

        ret["values"].append(filter)

    return ret


@edmp.register_hook()
def send_handler(*messages, **kwargs):
    """
    Sends one or more CAN frames on the CAN bus.
    """

    ret = {}

    conn.send(*[decode_msg_from(m) for m in messages], **kwargs)

    return ret


@edmp.register_hook()
def query_handler(*messages, **kwargs):
    """
    """

    ret = {}

    output = kwargs.pop("output", "str")

    for reply in conn.query(*[decode_msg_from(m) for m in messages], **kwargs):
        ret.setdefault("values", []).append(encode_msg_to(output, reply))

    return ret


@edmp.register_hook()
def monitor_handler(**kwargs):
    """
    """

    ret = {}

    output = kwargs.pop("output", "str")

    for msg in conn.monitor(**kwargs):
        ret.setdefault("values", []).append(encode_msg_to(output, msg))

    return ret


@edmp.register_hook()
def dump_handler(file, **kwargs):
    """
    """

    ret = {}

    ret["count"] = conn.dump(file, **kwargs)

    return ret


@edmp.register_hook()
def play_handler(*files, **kwargs):
    """
    """

    ret = {}

    total, sent = conn.play(*files, **kwargs)
    ret["total"] = total
    ret["sent"] = sent

    return ret


@edmp.register_hook()
def obd_query_handler(name, mode=None, pid=None, bytes=0, frames=None, strict=False, decoder=None, unit=None, **kwargs):
    """
    """

    ret = {
        "_type": name.lower()
    }

    import obd
    from obd.protocols import CANProtocol

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Querying: %s", name)

    if pid != None:
        mode = "{:02X}".format(int(str(mode), 16)) if mode != None else "01"
        pid = "{:02X}".format(int(str(pid), 16))

        cmd = obd.OBDCommand(name, None, "{:}{:}".format(mode, pid), bytes, getattr(obd.decoders, decoder or "raw_string"))
    elif obd.commands.has_name(name.upper()):
        cmd = obd.commands[name.upper()]
    else:
        cmd = obd.OBDCommand(name, None, name, bytes, getattr(obd.decoders, decoder or "raw_string"))
    cmd.frames = frames
    cmd.strict = strict

    msgs = conn.obd_query(cmd.mode, cmd.pid, **kwargs)
    lines = [encode_msg_to("str", msg, separator="") for msg in msgs]

    protocol = CANProtocol([])
    if getattr(next(iter(msgs), None), "is_extended_id", False):
        protocol.HEADER_BITS = 29
    else:
        protocol.HEADER_BITS = 11

    obd_msgs = protocol(lines)
    if not obd_msgs:
        raise Exception("No OBD messages could be parsed from lines {:}".format(lines))

    res = cmd(obd_msgs, filtering=False)
    if log.isEnabledFor(logging.DEBUG):
        log.debug("Got query result: %s", res)

    # Unpack command result
    if not res.is_null():
        if isinstance(res.value, obd.UnitsAndScaling.Unit.Quantity):
            ret["value"] = res.value.m
            ret["unit"] = unit or str(res.value.u)
        else:
            ret["value"] = res.value
            if unit != None:
                ret["unit"] = unit

    return ret

#@intercept_exit_signal
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting CAN manager with settings: {:}".format(settings))

        # TODO HN: Get from settings
        global conn
        conn = CANConn(__salt__)
        conn.setup(channel="can0", bitrate=500000)

        # Initialize and run message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        edmp.run()

    except Exception:
        log.exception("Failed to start CAN manager")

        raise
    finally:
        log.info("Stopping CAN manager")