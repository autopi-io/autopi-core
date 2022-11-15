import gpio_pin
import importlib
import logging
import RPi.GPIO as gpio
import salt.exceptions

from messaging import EventDrivenMessageProcessor
from retrying import retry
from threading_more import intercept_exit_signal


log = logging.getLogger(__name__)

DEBUG = log.isEnabledFor(logging.DEBUG)

context = {
    "mixer": {
        "settings": None,
        "initialized": False
    },
    "amplifier": {
        "enabled": False
    }
}

# Message processor
edmp = EventDrivenMessageProcessor("audio", context=context, default_hooks={"handler": "play"})


@retry(stop_max_attempt_number=5, wait_fixed=1000)
def _ensure_mixer():
    ctx = context["mixer"]

    if ctx.get("initialized", False):
        return

    try:
        settings = ctx["settings"]

        globals()["pygame"] = importlib.import_module("pygame")

        log.info("Initializing mixer using settings: {:}".format(settings))
        pygame.mixer.init(frequency=settings["frequency"],
                          size=settings["bit_size"],
                          channels=settings["channels"],
                          buffer=settings["buffer_size"])

        if DEBUG:
            log.debug("Successfully initialized mixer")
        
        ctx["initialized"] = True

    except Exception:
        log.exception("Failed to initialize mixer")
        raise


@retry(stop_max_attempt_number=3, wait_fixed=1000)
def _ensure_amplifier():
    ctx = context["amplifier"]

    if ctx.get("enabled", False):
        return

    try:
        log.info("Turning on amplifier")

        if __opts__.get("spm.version", 1.0) >= 4.0:
            res = __salt__["spm.query"]("sys_pins", high="sw_amp")
            assert res["output"]["sw_amp"] == True, "Amplifier was not switched on in the SPM"
        else:
            gpio.setwarnings(False)
            gpio.setmode(gpio.BOARD)
            gpio.setup(gpio_pin.AMP_ON, gpio.OUT, initial=gpio.HIGH)

            if DEBUG:
                log.debug("Powered on amplifier by setting GPIO pin #%d high", gpio_pin.AMP_ON)

        ctx["enabled"] = True

    except Exception:
        log.exception("Failed to enable amplifier")
        raise


@edmp.register_hook()
def play_handler(audio_file, force=False, loops=0, volume=None):
    """
    Plays a specific audio file. 

    Arguments:
      - audio_file (str): Local path of the audio file to play.

    Optional arguments:
      - force (bool): Force even though another playback is in progress? Default is 'False'.
      - loops (int): How many repetitions of playback? Default is '0'.
      - volume (int): Set volumen of the playback.
    """

    _ensure_mixer()
    _ensure_amplifier()

    if pygame.mixer.music.get_busy():
        if not force:
            return {
                "success": False,
                "error": "Already busy playing audio"
            }

        log.info("Forcibly fading out ongoing playback")
        pygame.mixer.music.fadeout(100)

    if volume != None:
        if DEBUG:
            log.debug("Setting volume to: %d%%", volume*100)
        pygame.mixer.music.set_volume(volume)

    if DEBUG:
        log.debug("Loading audio file: %s", audio_file)
    pygame.mixer.music.load(audio_file)

    log.info("Playback of audio file: %s", audio_file)
    pygame.mixer.music.play(loops=loops)

    return {
        "playing": True
    }


@edmp.register_hook()
def queue_handler(audio_file):
    """
    Queues an audio file.

    Arguments:
      - audio_file (str): Local path of the audio file to play.
    """

    _ensure_mixer()
    _ensure_amplifier()

    #if not pygame.mixer.music.get_busy():
    #    return _play_handler(audio_file)

    log.info("Queuing audio file: %s", audio_file)
    # TODO: Apparently not working?
    pygame.mixer.music.queue(audio_file)

    return {
        "queued": True
    }


@edmp.register_hook()
def stop_handler():
    """
    Stops playback of the current audio.
    """

    _ensure_mixer()
    _ensure_amplifier()

    busy = pygame.mixer.music.get_busy()
    if busy:
        log.info("Stopping playback of all audio")
        pygame.mixer.music.stop()

    return {
        "was_playing": bool(busy)
    }


@edmp.register_hook()
def volume_handler(value=None):
    """
    Set volumen of the playback.

    Optional arguments:
      - value (int): The volume to set.
    """

    _ensure_mixer()
    _ensure_amplifier()

    if value != None:
        log.info("Setting volume to: %d%%", value*100)
        pygame.mixer.music.set_volume(value)

    return {
        "value": pygame.mixer.music.get_volume()
    }


@edmp.register_hook()
def espeak_handler(text, volume=100, language="en-gb", pitch=50, speed=175, word_gap=10, timeout=10):
    """
    Speak a given text using the 'espeak' command.

    NOTE: Unfortunately 'espeak' command is not always reliable - sometimes it fails for uncertain reasons.

    Arguments:
      - text (str): Text to speak out.

    Optional arguments:
      - volume (int): Set volumen of the playback. Default value is '100'.
      - language (str): The language to speak in. Default value is 'en-gb'.
      - pitch (int): The pitch of the voice. Default value is '50'.
      - speed (int): Rate of speech. Default value is '175'.
      - word_gap (int): Time gap between words spoken. Default value is '10'.
      - timeout (int): Timeout in seconds of the command to finish. Default value is '10'.
    """

    _ensure_amplifier()

    ret = {}

    res = __salt__["cmd.run_all"]("espeak -a {:d} -v {:s} -p {:d} -s {:d} -g {:d} -X '{:s}'".format(volume, language, pitch, speed, word_gap, text),
        timeout=timeout)  # Timeout added because espeak sometimes hangs
    if res["retcode"] != 0:
        raise salt.exceptions.CommandExecutionError(res["stderr"])

    ret["result"] = res["stdout"]

    return ret


@edmp.register_hook()
def aplay_handler(audio_file, duration=0, **kwargs):
    """
    Play a given audio file using the 'aplay' command.

    Arguments:
        - audio_file (str): Local path of the audio file to play.

    Optional arguments:
      - duration (int): Interrupt playback after amount of seconds.
    """

    _ensure_amplifier()

    ret = {}

    res = __salt__["cmd.run_all"]("aplay -d {:d} '{:s}'".format(duration, audio_file), **kwargs)
    if res["retcode"] != 0:
        raise salt.exceptions.CommandExecutionError(res["stderr"])

    ret["result"] = res["stdout"]

    return ret


@intercept_exit_signal
def start(**settings):
    try:
        if DEBUG:
            log.debug("Starting audio manager with settings: {:}".format(settings))

        context["mixer"]["settings"] = settings["mixer"]

        if __opts__.get("spm.version", 1.0) < 4.0:

            # Ensure that amplifier is enabled immediately for backwards compatibility
            _ensure_amplifier()

        # Initialize and run message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        edmp.run()

    except Exception:
        log.exception("Failed to start audio manager")

        raise
    finally:
        log.info("Stopping audio manager")

