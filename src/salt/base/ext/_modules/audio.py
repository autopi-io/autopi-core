import logging
import salt.exceptions

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack


log = logging.getLogger(__name__)

client = EventDrivenMessageClient("audio")


def __init__(opts):
    client.init(opts)


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"]("audio")


def play(audio_file, force=False, loops=0, volume=None):
    """
    Plays a specific audio file. 

    Arguments:
      - audio_file (str): Local path of the audio file to play.

    Optional arguments:
      - force (bool): Force even though another playback is in progress? Default is 'False'.
      - loops (int): How many repetitions of playback? Default is '0'.
      - volume (int): Set volumen of the playback.
    """

    return client.send_sync(_msg_pack(audio_file, force=force, loops=loops, volume=volume, _handler="play"))


def queue(audio_file):
    """
    Queues an audio file.

    Arguments:
      - audio_file (str): Local path of the audio file to play.
    """

    return client.send_sync(_msg_pack(audio_file, _handler="queue"))


def stop():
    """
    Stops playback of the current audio.
    """

    return client.send_sync(_msg_pack(_handler="stop"))


def volume(value=None):
    """
    Set volumen of the playback.

    Optional arguments:
      - value (int): The volume to set.
    """

    return client.send_sync(_msg_pack(value=value, _handler="volume"))


def espeak(text, **kwargs):
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

    return client.send_sync(_msg_pack(text, _handler="espeak", **kwargs))


def speak(*args, **kwargs):
    """
    Alias for 'audio.espeak'.
    """

    return espeak(*args, **kwargs)


def aplay(audio_file, **kwargs):
    """
    Play a given audio file using the 'aplay' command.

    Arguments:
        - audio_file (str): Local path of the audio file to play.

    Optional arguments:
      - duration (int): Interrupt playback after amount of seconds.
    """

    return client.send_sync(_msg_pack(audio_file, _handler="aplay", **kwargs))


def manage(*args, **kwargs):
    """
    Runtime management of the underlying service instance.

    Supported commands:
      - 'hook list|call <name> [argument]... [<key>=<value>]...'
      - 'worker list|show|start|pause|resume|kill <name>'
      - 'reactor list|show <name>'
      - 'run <key>=<value>...'

    Examples:
      - 'audio.manage hook list'
      - 'audio.manage hook call query_handler play'
      - 'audio.manage worker list *'
      - 'audio.manage worker show *'
      - 'audio.manage worker start *'
      - 'audio.manage worker pause *'
      - 'audio.manage worker resume *'
      - 'audio.manage worker kill *'
      - 'audio.manage reactor list'
      - 'audio.manage reactor show *'
      - 'audio.manage run handler="play" args="[\"sound.wav\"]"'
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))
