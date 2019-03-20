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
      - audio_file (str): Local path of audio file to play.

    Optional arguments:
      - force (bool): Default is 'False'.
      - loops (int): Default is '0'.
      - volume (int):
    """

    return client.send_sync(_msg_pack(audio_file, force=force, loops=loops, volume=volume, _handler="play"))


def queue(audio_file):
    """
    Queues an audio file.

    Arguments:
      - audio_file (str): Local path of audio file to play.
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
      - value (int):
    """

    return client.send_sync(_msg_pack(value=value, _handler="volume"))


def speak(text, **kwargs):
    """
    Speak given text.

    Arguments:
      - text (str): Text to speak out.
    """

    return client.send_sync(_msg_pack(text, _handler="speak", **kwargs))

