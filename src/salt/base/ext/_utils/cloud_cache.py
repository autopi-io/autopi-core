import datetime
import json
import logging
import redis
import requests


DEQUEUE_PENDING_BATCH_SCRIPT = "dequeue_pending_batch"
DEQUEUE_PENDING_BATCH_LUA = """
local ret = {}
if redis.call('EXISTS', KEYS[2]) == 1 then
    ret = redis.call('LRANGE', KEYS[2], 0, -1)
elseif redis.call('EXISTS', KEYS[1]) == 1 then
    for i = 1, ARGV[1] do
        local val = redis.call('RPOPLPUSH', KEYS[1], KEYS[2])
        if not val then
            break
        end
        table.insert(ret, val)
    end
end
return ret
"""

PENDING_QUEUE = "pend"
WORK_QUEUE    = "work"
RETRY_QUEUE   = "retr_{0:%Y%m%d%H%M%S%f}"
FAIL_QUEUE    = "fail_{0:%Y%m%d%H%M%S%f}"


log = logging.getLogger(__name__)


# Redis connection pool
_conn_pool = None

# Redis LUA scripts loaded
_scripts = None


def _dequeue_pending_batch(client, source, destination, count):
    script = _scripts.get(DEQUEUE_PENDING_BATCH_SCRIPT)
    return script(keys=[source, destination], args=[count], client=client)


def load_options(__salt__):
    options = {
        "redis": {
            "host": "localhost",
            "port": 6379,
            "db": 0,
        },
        "batch_size": 1,
        "retry_count": 3,
        "fail_ttl": 3600,  # One hour
    }

    # Overwrite defaults with options specified in config file
    options.update(__salt__["config.get"]("cloud_cache"))

    log.debug("Loaded options from config file")
    return options


def conn_pool_for(options):
    global _conn_pool
    if _conn_pool is None:
        log.debug("Creating Redis connection pool")
        _conn_pool = redis.ConnectionPool(**options.get("redis"))

    return _conn_pool


def client_for(options):
    client = redis.StrictRedis(connection_pool=conn_pool_for(options))

    global _scripts
    if _scripts is None:
        log.debug("Loading Redis LUA scripts")

        _scripts = {
            DEQUEUE_PENDING_BATCH_SCRIPT: client.register_script(DEQUEUE_PENDING_BATCH_LUA)
        }

    return client


def enqueue(options, data):
    # TODO: Use a Set to determine duplicate/unchanged values in order to skip them 
    client_for(options).lpush(PENDING_QUEUE, json.dumps(data, separators=(",", ":")))


def upload_pending_batch(options, url, auth_token, name=None):
    client = client_for(options)

    # Pop next batch into work queue, if not work queue already has data
    if name is None:
        batch = _dequeue_pending_batch(client, PENDING_QUEUE, WORK_QUEUE, options.get("batch_size"))
    else:
        batch = _dequeue_pending_batch(client, name, WORK_QUEUE, options.get("batch_size"))
        log.info("Uploading batch name %s", name)

    if not batch:
        log.debug("No pending batch found to upload")

        return batch

    # Upload batch of data to cloud
    try:
        log.info("Uploading batch of size %d", len(batch))

        payload = "[{:s}]".format(", ".join(batch))
        headers = {
            "authorization": "token {:}".format(auth_token),
            "content-type": "application/json",
        }

        res = requests.post(url, data=payload, headers=headers)
        res = res.raise_for_status()

        # Batch uploaded equals work completed
        client.delete(WORK_QUEUE)
        if name != None:
            client.delete(name)
        else:
            retry_failed_batches(options, url, auth_token, count=5)

    except Exception:
        log.exception("Failed to upload batch")

        # Move batch data into dedicated error queue
        if client.renamenx(WORK_QUEUE, FAIL_QUEUE.format(datetime.datetime.utcnow())):
            # TODO: Set EXPIRE seconds to 7 days using pipeline

            pass # TODO: Handle fail

        raise

    return batch

def retry_failed_batches(options, url, auth_token, count=0):
    client = client_for(options)

    # find failed queues
    failkeys = sorted(client.keys("fail*"), reverse=True)

    if len(failkeys) < count:
        count = len(failkeys)

    for i in range(0,count):
        upload_pending_batch(options, url, auth_token, name=failkeys[i])

