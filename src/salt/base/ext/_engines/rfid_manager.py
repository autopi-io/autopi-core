import logging
import datetime
import yaml
import os

from common_util import factory_rendering
from messaging import EventDrivenMessageProcessor, extract_error_from
from rfidreader_conn import RFIDReader

log = logging.getLogger(__name__)

context = {
    "authorized_tokens": []
}

rfid_reader = None
edmp = EventDrivenMessageProcessor("rfid", context=context, default_hooks={ "workflow": "extended" })


@edmp.register_hook(synchronize=False)
def reader_handler():
    """
    Reads input from the RFID reader.
    """

    rfid = rfid_reader.read(timeout=2)

    # no RFID chip was close to reader, skip
    if rfid == None:
        return

    # partial RFID received, this should be an error
    if len(rfid) != 10:
        raise Warning("Received an RFID that is not 10 characters long: {}".format(rfid))

    ret = {}
    ret["_type"] = "read"
    ret["value"] = rfid

    return ret


@edmp.register_hook(synchronize=False)
def rfid_read_trigger(result):
    """
    Triggers 'system/rfid/<rfid>/read' events when RFID chips are read.

    NOTE: Use in conjunction with reader_handler.
    """

    if not result:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Received empty result from RFID reader, skipping")
        return
    
    error = extract_error_from(result)
    if error:
        raise error
    
    # trigger event
    __salt__["minionutil.trigger_event"]("system/rfid/{}/read".format(result["value"]))


@edmp.register_hook(synchronize=False)
def authenticate_rfid_handler(rfid):
    """
    If there are any authorized_tokens saved in context, this handler will attempt to authenticate
    an RFID against those tokens. Triggers 'system/rfid/<rfid>/rejected' and
    'system/rfid/<rfid>/authenticated' events.

    If the tokens get updated in /opt/autopi/rfid/settings.yaml the manager needs to know about
    the changes - use 'load_settings_handler' to reload the settings.
    """

    authorized_tokens = context.get("authorized_tokens", [])

    if len(authorized_tokens) == 0:
        log.info("No RFID tokens configured, skipping handler execution")
        __salt__["minionutil.trigger_event"]("system/rfid/{}/rejected".format(rfid))
        __salt__["audio.play"]("/opt/autopi/audio/sound/beep.wav")
        return

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Configured RFID tokens: {}".format(authorized_tokens))

    now = datetime.datetime.now()

    valid_token = None
    for token in authorized_tokens:
        if rfid != token["rfid"]:
            log.info("RFID donesn't match token provided RFID, skipping")
            continue

        valid_from = datetime.datetime.strptime(token["valid_from"], '%Y-%m-%dT%H:%M:%S')
        valid_for = datetime.timedelta(seconds=token["valid_for"])

        # is it time for this token to be valid?
        if now >= valid_from and now <= valid_from + valid_for:
            valid_token = token

    # REJECT token
    if valid_token == None:
        __salt__["minionutil.trigger_event"]("system/rfid/{}/rejected".format(rfid))
        __salt__["audio.play"]("/opt/autopi/audio/sound/beep.wav")
        return

    # AUTHENTICATE token
    __salt__["minionutil.trigger_event"](
        "system/rfid/{}/authenticated".format(rfid),
        data={
            "valid_from": valid_token["valid_from"],
            "valid_for": valid_token["valid_for"],
        })


@edmp.register_hook(synchronize=False)
def load_settings_handler():
    """
    Read the settings file stored in /opt/autopi/rfid/settings.yaml and load it.
    """
    # TODO: NV we might want to make a check on the file before we read - make sure all
    # the settings are set in the proper format, etc.

    ret = {}
    ret["settings_updated"] = False

    if not os.path.isfile("/opt/autopi/rfid/settings.yaml"): # file or path doesn't exist
        return ret

    with open("/opt/autopi/rfid/settings.yaml", "r") as settings_file:
        new_settings = yaml.load(settings_file)

    # Need this to be with default None because auth_tokens can look like this:
    # authorized_tokens: null
    # `null` will override a default value of an empty array
    authorized_tokens = new_settings.get("authorized_tokens", None) or []

    # Apply settings
    context["authorized_tokens"] = authorized_tokens

    ret["settings_updated"] = True
    ret["value"] = {
        "authorized_tokens": authorized_tokens
    }

    return ret


@factory_rendering
def start(**settings):
    global rfid_reader

    try:
        log.info("Starting RFID manager")

        if not settings.get("rfid_device", None):
            raise ValueError("rfid_device needs to be a valid path to the RFID event device")

        context["settings"] = settings

        # Init RFID settings
        res = load_settings_handler()
        if not res.get("settings_updated", False):
            log.warning("RFID specific settings couldn't be loaded.")

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
        log.exception("Failed to start RFID manager")
        raise

    finally:
        log.info("Stopping RFID manager")

        if rfid_reader:
            rfid_reader.close()