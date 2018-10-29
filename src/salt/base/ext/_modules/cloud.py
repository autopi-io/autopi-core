import json
import logging

from cloud_cache import CloudCache


log = logging.getLogger(__name__)


def _options():
    return cloud_cache.load_options(__salt__)


def help():
    '''
    This command.
    '''
    return __salt__["sys.doc"]("cloud.*")


def cache_options():
    """
    Show current cache configuration.
    """

    # Prepare default values
    options = {
        "redis": {
            "host": "localhost",
            "port": 6379,
            "db": 0,
        },
        "url": "{:s}/logbook/storage".format(__salt__["pillar.get"]("cloud_api:url")),
        "auth_token": __salt__["pillar.get"]("cloud_api:token"),
        "batch_size": 100,
        "max_retry": 10,
        "fail_ttl": 3600,  # One hour
        "upload_splay": 10,  # 10 secs
    }

    # Overwrite defaults with options specified in config file
    options.update(__salt__["config.get"]("cloud_cache"))

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Loaded options from config file: {:}".format(options))

    return options


def upload_cache(include_failed=False):
    """
    Upload logged data to the cloud server.
    """

    return CloudCache(**cache_options()).upload_everything(include_failed=include_failed)


def upload_batch():
    """
    DEPRECATED: Use 'upload_cache()' instead.

    Upload next batch of logged data to the cloud server.
    """

    return upload_cache().get("pending", 0)


def list_cache_queues(pattern="*"):
    """
    List all cache queues or filter with specified wildcard pattern.

    Args:
        pattern (str): Wildcard pattern used filter.
    """

    return CloudCache(**cache_options()).list_queues(pattern=pattern)


def count_cache_queues(pattern="*"):
    """
    Counts all cache queues or filter with specified wildcard pattern.

    Args:
        pattern (str): Wildcard pattern used filter.
    """

    return len(list_cache_queues(pattern=pattern))


def peek_cache_queue(name, start=0, stop=-1):
    """
    Peek subset or all content of a specific cache queue.

    Args:
        name (str): Name of existing queue.
        start (int): Start index.
        stop (int): Stop index.
    """

    return CloudCache(**cache_options()).peek_queue(name, start=start, stop=stop)


def clear_cache_queue(name):
    """
    Clear a specific queue.

    Args:
        name (str): Name of existing queue.
    """

    return CloudCache(**cache_options()).clear_queue(name)
