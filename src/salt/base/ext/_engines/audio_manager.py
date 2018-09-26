import gpio_pin
import importlib
import logging
import RPi.GPIO as gpio
import salt.exceptions

from messaging import EventDrivenMessageProcessor
from retrying import retry


log = logging.getLogger(__name__)

# Message processor
edmp = EventDrivenMessageProcessor("audio", default_hooks={"handler": "play"})

context = {
    "mixer": {
        "settings": None,
        "initialized": False
    }
}


@retry(stop_max_attempt_number=5, wait_fixed=1000)
def _ensure_mixer():
    ctx = context["mixer"]

    if ctx.get("initialized", False):
        return

    try:
        log.debug("Initially powering off amplifier chip")

        gpio.setwarnings(False)
        gpio.setmode(gpio.BOARD)
        
        gpio.setup(gpio_pin.AMP_ON, gpio.OUT)
        gpio.output(gpio_pin.AMP_ON, gpio.LOW)
        log.debug("GPIO pin #%d is set low", gpio_pin.AMP_ON)

        settings = ctx["settings"]

        globals()["pygame"] = importlib.import_module("pygame")

        log.info("Initializing mixer using settings: {:}".format(settings))

        pygame.mixer.init(frequency=settings["frequency"],
                          size=settings["bit_size"],
                          channels=settings["channels"],
                          buffer=settings["buffer_size"])

        log.debug("Successfully initialized mixer")

        ctx["initialized"] = True

    except Exception:
        log.exception("Failed to initialize mixer")
        raise


@edmp.register_hook()
def play_handler(audio_file, force=False, loops=0, volume=None):
    _ensure_mixer()

    if pygame.mixer.music.get_busy():
        if not force:
            return {
                "success": False,
                "error": "Already busy playing audio"
            }

        log.info("Forcibly fading out ongoing playback")
        pygame.mixer.music.fadeout(100)

    if volume != None:
        log.debug("Setting volume to: %d%%", volume*100)
        pygame.mixer.music.set_volume(volume)

    log.debug("Loading audio file: %s", audio_file)
    pygame.mixer.music.load(audio_file)

    # Power on amplifier
    gpio.output(gpio_pin.AMP_ON, gpio.HIGH)

    log.info("Playback of audio file: %s", audio_file)
    pygame.mixer.music.play(loops=loops)

    # TODO: Power off when stopped playing - use: set_endevent()
    # Power off amplifier
    #gpio.output(gpio_pin.AMP_ON, gpio.LOW)
    
    return {
        "playing": True
    }


@edmp.register_hook()
def queue_handler(audio_file):
    _ensure_mixer()

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
    _ensure_mixer()

    busy = pygame.mixer.music.get_busy()
    if busy:
        log.info("Stopping playback of all audio")
        pygame.mixer.music.stop()
    
    return {
        "was_playing": bool(busy)
    }


@edmp.register_hook()
def volume_handler(value=None):
    _ensure_mixer()

    if value != None:
        log.info("Setting volume to: %d%%", value*100)
        pygame.mixer.music.set_volume(value)
    
    return {
        "value": pygame.mixer.music.get_volume()
    }


@edmp.register_hook()
def speak_handler(text):

    res = __salt__["cmd.run_all"]("espeak '{:}'".format(text))
    #if res["retcode"] != 0:
    #    raise salt.exceptions.CommandExecutionError(res["stderr"])

    return res


def start(mixer, **kwargs):
    try:
        log.debug("Starting audio manager")

        context["mixer"]["settings"] = mixer

        # Initialize and run message processor
        edmp.init(__opts__)
        edmp.run()

    except Exception:
        log.exception("Failed to start audio manager")
        raise
    finally:
        log.info("Stopping audio manager")

