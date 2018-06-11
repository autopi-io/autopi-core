import json
import logging

import cloud_cache


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

    return cloud_cache.options()


def upload_batch():
    """
    Upload next batch of logged data to the cloud server.
    """

    base_url = __salt__["pillar.get"]("cloud_api:url")
    url = "{:s}/logbook/storage".format(base_url)
    auth_token = __salt__["pillar.get"]("cloud_api:token")

    batch = cloud_cache.upload_pending_batch(_options(), url, auth_token)

    return len(batch)


def list_cache_queues(pattern="*"):
    """
    List all cache queues or filter with specified wildcard pattern. Uses params: (pattern="*")
    """

    client = cloud_cache.client_for(_options())
    return sorted(client.keys(pattern), reverse=True)

def count_cache_queues(pattern="*"):
    """
    Counts all cache queues or filter with specified wildcard pattern. Uses params: (pattern="*")
    """

    client = cloud_cache.client_for(_options())
    return len(client.keys(pattern))


def peek_cache_queue(name, start=0, stop=-1):
    """
    Peek subset or all content of a specific cache queue. Uses params: (name, start=0, stop=-1)
    """

    client = cloud_cache.client_for(_options())
    res = client.lrange(name, start, stop)

    return [json.loads(s) for s in res]


def clear_cache_queue(name):
    """
    Clear a specific queue.
    """

    client = cloud_cache.client_for(_options())
    return bool(client.delete(name))

def retry_cache_queue(name):
    """
    Retries upload of a specific queue.
    """

    base_url = __salt__["pillar.get"]("cloud_api:url")
    url = "{:s}/logbook/storage".format(base_url)
    auth_token = __salt__["pillar.get"]("cloud_api:token")

    batch = cloud_cache.upload_pending_batch(_options(), url, auth_token, name=name)

    return len(batch)
