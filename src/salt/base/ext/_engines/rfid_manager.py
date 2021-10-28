import evdev
import logging
import time
import datetime

from common_util import factory_rendering
from messaging import EventDrivenMessageProcessor, extract_error_from

log = logging.getLogger(__name__)

EVENT_KEY_MAP = {
    evdev.ecodes.KEY_0: "0",
    evdev.ecodes.KEY_1: "1",
    evdev.ecodes.KEY_2: "2",
    evdev.ecodes.KEY_3: "3",
    evdev.ecodes.KEY_4: "4",
    evdev.ecodes.KEY_5: "5",
    evdev.ecodes.KEY_6: "6",
    evdev.ecodes.KEY_7: "7",
    evdev.ecodes.KEY_8: "8",
    evdev.ecodes.KEY_9: "9",
}

rfid_tokens = [
    { "valid_from": '2021-09-25T11:30:00', "valid_for": 7200, "rfid": "0003858905" },
    { "valid_from": '2021-10-25T08:00:00', "valid_for": 3600, "rfid": "0003858905" },
    { "valid_from": '2021-10-25T11:30:00', "valid_for": 7200, "rfid": "0003858905" },
    { "valid_from": '2021-10-26T09:30:00', "valid_for": 7200, "rfid": "0011252203" },
]

context = {}

"""
- rfid_manager:
    rfid_device: /dev/autopi-rfid
    workers:
    - auto_start: true
      name: rfid_reader
      interval: 2
      loop: -1
      messages:
      - handler: reader
        trigger: rfid_read
    reactors:
    - keyword_resolve: true
      name: authenticate_rfid
      regex: ^system/rfid/read/(?P<rfid>[0-9]*)$
      actions:
      - handler: authenticate_rfid
        args:
        - $match.group('rfid')
"""


class RFIDReader():

    def __init__(self, dev_path):
        self._dev_path = dev_path
        self._dev = evdev.InputDevice(dev_path)
        self._rfids_read = []

        # grab device here
        self._dev.grab()

    def read(self, timeout=2):
        """
        Read an RFID or return within timeout.
        """

        rfid = ""
        time_left = timeout
        start = time.time()

        while time_left > 0:
            event = self._dev.read_one()

            if event == None:
                time.sleep(.1)
                continue
            else:
                # read rest of line too




        while time_left > 0:
            event = self._dev.read_one()

            if event == None:
                time.sleep(.2) # don't loop too fast
            else:
                if event.type == evdev.ecodes.EV_KEY and event.value == 1: # only care about key-down events
                    if event.code == evdev.ecodes.KEY_ENTER:
                        # we're done here, have read a full RFID
                        break
                    rfid += EVENT_KEY_MAP.get(event.code, "$")
            time_left = timeout - (time.time() - start)

        if rfid != "" and len(rfid) != 10:
            raise ValueError("Got incomplete RFID: {}".format(rfid))

        return rfid or None

    def close(self):
        """
        Close down device and cleanup.
        """

        self._dev.close()


# RFID reader
rfid_reader = None

# Message processor
edmp = EventDrivenMessageProcessor("rfid", context=context)


@edmp.register_hook(synchronize=False)
def reader_handler():
    """
    Continuously reads input from RFID reader.
    """

    rfid = rfid_reader.read(timeout=2)

    if not rfid:
        return

    ret = {}
    ret["_type"] = "read"
    ret["value"] = rfid

    return ret


@edmp.register_hook(synchronize=False)
def rfid_read_trigger(result):
    """
    Triggers events when a new RFID is read.
    """

    if not result:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Received empty result from RFID reader, skipping")
        return
    
    error = extract_error_from(result)
    if error:
        raise error
    
    # trigger event
    __salt__["minionutil.trigger_event"]("system/rfid/read/{}".format(result["value"]))


@edmp.register_hook(synchronize=False)
def authenticate_rfid_handler(rfid):
    """
    reactor settings:

    - keyword_resolve: true
      name: authenticate_rfid
      regex: ^system/rfid/read/(?P<rfid>[0-9]*)$
      actions:
      - handler: authenticate_rfid
        args:
        - $match.group('rfid')
      conditions:
      - True
    """
    log.info("FEDERLIZER: rfid: {}".format(rfid))

    ctx = context.setdefault("carstate", {})

    now = datetime.datetime.now()

    valid = False
    for token in rfid_tokens:
        if rfid != token["rfid"]:
            # rfid keys don't match
            continue

        valid_from = datetime.datetime.strptime(token["valid_from"], '%Y-%m-%dT%H:%M:%S')
        valid_for = datetime.timedelta(seconds=token["valid_for"])

        if now >= valid_from and now <= valid_from + valid_for:
            valid = True

    if not valid:
        log.info("RFID chip {} rejected".format(rfid))
        __salt__["audio.speak"]("Rejected.")
        return
    
    __salt__["audio.speak"]("Authenticated.")

    car_locked = ctx.get("locked", True) # assume car is locked, TODO - probably shouldn't assume, decern it somehow if possible

    # ensure keyfob is on
    keyfob_power_res = __salt__["keyfob.power"]()
    if not keyfob_power_res["value"]:
        __salt__["keyfob.power"](value=True)
    
    if car_locked:
        # unlock
        log.info("FEDERLIZER: Unlocking vehicle...")
        __salt__["keyfob.action"]("unlock")
        ctx["locked"] = False
    else:
        # lock
        log.info("FEDERLIZER: Locking vehicle...")
        __salt__["keyfob.action"]("lock")
        ctx["locked"] = True
    
    context["carstate"] = ctx


@factory_rendering
def start(**settings):
    global rfid_reader

    try:
        log.info("Starting RFID manager")

        if not settings.get("rfid_device", None):
            raise ValueError("rfid_device needs to be a valid path to the RFID event device")

        context["settings"] = settings

        # Init RFID reader
        rfid_reader = RFIDReader(settings.get("rfid_device"))

        # Init message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        
        # Run message processor
        edmp.run()
    
    except Exception:
        log.exception("Failed to start key fob manager")
        raise

    finally:
        log.info("Stopping RFID manager")

        if rfid_reader:
            rfid_reader.close()