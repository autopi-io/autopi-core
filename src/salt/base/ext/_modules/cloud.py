import logging

from messaging import EventDrivenMessageClient, msg_pack as _msg_pack


log = logging.getLogger(__name__)

client = EventDrivenMessageClient("cloud")


def __init__(opts):
    client.init(opts)


def help():
    """
    Shows this help information.
    """
    
    return __salt__["sys.doc"]("cloud.*")


def cache(cmd, *args, **kwargs):
    """
    Queries/calls a given cache function.
    """

    kwargs["_handler"] = "cache"

    return client.send_sync(_msg_pack(cmd, *args, **kwargs))


def upload(**kwargs):
    """
    Upload cached data to cloud.
    """

    return client.send_sync(_msg_pack(_handler="upload", **kwargs))


# TODO: Delete when scheduled job '_cloud_upload' is removed from pillar in backend.
def upload_batch():
    """
    DEPRECATED: This will no longer upload anything.

    Upload next batch of logged data to the cloud server.
    """

    return 0


def status(**kwargs):
    """
    Get current status.
    """

    return client.send_sync(_msg_pack(_handler="status", **kwargs))


def manage(*args, **kwargs):
    """
    Examples:
      - 'spm.manage handler'        Lists all available handlers.
      - 'spm.manage worker list *'  Lists all existing worker threads.
    """

    return client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs))
