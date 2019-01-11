import logging
import salt.exceptions

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack


log = logging.getLogger(__name__)

client = EventDrivenMessageClient("audio")


def __init__(opts):
    client.init(opts)


def help():
    """
    This command.
    """

    return __salt__["sys.doc"]("audio")


def play(audio_file, force=False, loops=0, volume=None):
    """
    Plays a specific audio file. 

    Args:
        audio_file (str): 
        force (bool): 
        loops (int): 
        volume (int): 
    """

    return client.send_sync(_msg_pack(audio_file, force=force, loops=loops, volume=volume, _handler="play"))


def queue(audio_file):
    """
    Queues an audio file.

    Args:
        audio_file (str): 
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

    Args: 
        value (int): 
    """

    return client.send_sync(_msg_pack(value=value, _handler="volume"))


def speak(text, **kwargs):
    """
    Speak given text.

    Args:
        text (str): 
    """

    return client.send_sync(_msg_pack(text, _handler="speak", **kwargs))

