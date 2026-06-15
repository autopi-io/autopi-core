import datetime
import logging
import os
import time
import yaml
import signal
import re

from common_util import factory_rendering
from messaging import EventDrivenMessageProcessor, extract_error_from
from rfidreader_conn import RFIDReader

log = logging.getLogger(__name__)

context = {
    "authorized_tokens": [],
    "login_context": {},
    "authorized_token_regexes": [],
    "keep_login_context": False
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

def fatal_restart(reason , trigger_events= True, restart_delay = 1):
    try:
        log.error("Fatal RFID error, exiting for restart: %s", reason)
        if trigger_events:
            try:
                edmp.trigger_event({"reason": reason}, "system/service/{:}/failed".format(__name__.split(".")[-1]))
            except Exception:
                log.exception("Unable to trigger service failed event")
        if restart_delay:
            log.info("Restart delay: %s second(s)", restart_delay)
            time.sleep(restart_delay)
    finally:
        try:
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(2)
        except Exception:
            pass
        os._exit(1)


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
        # If we get an error in the res from the RFID reader - call fatal_restart
        # It kills the process and Rfid manager is then restarted.
        # Run in loop of 2 second intervals?
        # Trigger event whenever this failure state is hit
        fatal_restart(str(error), trigger_events=True, restart_delay=2)
        time.sleep(2)
        raise error

    # trigger event
    __salt__["minionutil.trigger_event"]("system/rfid/{}/read".format(result["value"]))


@edmp.register_hook(synchronize=False)
def try_log_rfid_out(rfid):
    if context.get("login_context", {}).get(rfid) is not None:
        __salt__["minionutil.trigger_event"]("system/rfid/{}/unauthenticated".format(rfid), data={"rfid": rfid})
        __salt__["audio.aplay"]("/opt/autopi/audio/sound/bleep.wav")
        context["login_context"][rfid] = None


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
    keep_login_context = context.get("keep_login_context", False)
    authorized_token_regex = context.get("authorized_token_regexes", [])

    if len(authorized_tokens) == 0 and not authorized_token_regex:
        log.info("No RFID tokens configured, skipping handler execution")
        __salt__["minionutil.trigger_event"]("system/rfid/{}/rejected".format(rfid))
        __salt__["audio.aplay"]("/opt/autopi/audio/sound/beep.wav")
        return

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Configured RFID tokens: {}".format(authorized_tokens))

    now = datetime.datetime.now()

    valid_token = None
    
    for token in authorized_tokens:
        if rfid != token["rfid"]:
            log.info("RFID doesn't match token provided RFID, skipping")
            continue

        valid_from = datetime.datetime.strptime(token["valid_from"], '%Y-%m-%dT%H:%M:%S') if \
            token['valid_from'] else now
        valid_for = datetime.timedelta(seconds=token["valid_for"])

        if now >= valid_from:
            if valid_for.seconds == 0:
                valid_token = token
            # is it time for this token to be valid?
            elif now <= valid_from + valid_for:
                valid_token = token
    if not valid_token:
        # Check if rfid token matches any of the authorized token regex patterns
        for pattern in authorized_token_regex:
            if re.match(pattern, rfid):
                valid_token = rfid

    # REJECT token
    if valid_token is None:
        __salt__["minionutil.trigger_event"]("system/rfid/{}/rejected".format(rfid), data={"rfid": rfid})
        __salt__["audio.aplay"]("/opt/autopi/audio/sound/beep.wav")
        return

    # AUTHENTICATE token Fallback to old behaviour if keep_login_context is not set
    if not keep_login_context:
        __salt__["minionutil.trigger_event"](
            "system/rfid/{}/authenticated".format(rfid),
            data={
                "valid_from": valid_token["valid_from"] if isinstance(valid_token, dict) else None,
                "valid_for": valid_token["valid_for"] if isinstance(valid_token, dict) else None,
                "rfid": rfid
            })

    # Login context is used to keep track of rfid tokens that have been used
    elif keep_login_context:
        login_ctx = context.setdefault("login_context", {})
        play_beep = True

        # If rfid token is already in login context, remove it if it is not the same as the current one
        for k in list(login_ctx.keys()):
            if login_ctx[k] is not None and k != rfid:
                login_ctx[k] = None
                __salt__["minionutil.trigger_event"]("system/rfid/{}/unauthenticated".format(k), data={"rfid": k})

        # If rfid token is not in login context, add it
        if context.get("login_context", {}).get(rfid) is None:
            context["login_context"][rfid] = rfid
            __salt__["minionutil.trigger_event"]("system/rfid/{}/authenticated".format(rfid), data={"rfid": rfid})
            play_beep = False

        # if rfid token is already in login context, log it as unauthenticated and remove it from login context
        else:
            __salt__["minionutil.trigger_event"]("system/rfid/{}/unauthenticated".format(rfid), data={"rfid": rfid})
            context["login_context"][rfid] = None

        # Play beep if we do not log in
        if play_beep:
            __salt__["audio.aplay"]("/opt/autopi/audio/sound/bleep.wav")



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
    authorized_token_regexes = new_settings.get("authorized_token_regexes", None) or []
    keep_login_context = new_settings.get("keep_login_context", False)

    # Apply settings
    context["authorized_tokens"] = authorized_tokens
    context["authorized_token_regexes"] = authorized_token_regexes
    context["keep_login_context"] = keep_login_context

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

        # Init the message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))

        # Init the RFID reader after message processor to ensure that we can trigger events in the except clause
        rfid_reader = RFIDReader(settings.get("rfid_device"))
        log.info(str(rfid_reader))

        # Run message processor
        edmp.run()

    except Exception as ex:
        log.exception("Failed to start RFID manager: {:}".format(ex))

        if settings.get("trigger_events", True):
            try:
                __salt__["minionutil.trigger_event"]("system/service/{:}/failed".format(__name__.split(".")[-1]), data={"reason": str(ex)})
            except:
                log.exception("Unable to trigger service failed event")

        restart_delay = settings.get("restart_delay", 1)
        if restart_delay:
            log.info("Enforcing restart delay of {:} second(s)...".format(restart_delay))
            time.sleep(restart_delay)

        raise

    finally:
        log.info("Stopping RFID manager")

        if rfid_reader:
            rfid_reader.close()
