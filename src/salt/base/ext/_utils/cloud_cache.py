import datetime
import json
import logging
import random
import re
import redis
import requests
import time

from timeit import default_timer as timer


log = logging.getLogger(__name__)


class CloudCache(object):

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
    RETRY_QUEUE   = "retr_{:s}_#{:d}"
    FAIL_QUEUE    = "fail_{:s}_#{:d}"

    TIMESTAMP_FORMAT = "{:%Y%m%d%H%M%S%f}"

    ERROR_QUEUE_REGEX = re.compile("^(?P<type>.+)_(?P<timestamp>\d+)_#(?P<attempt>\d+)$")

    def __init__(self, **options):
        self.options = options

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Creating Redis connection pool")
        self.conn_pool = redis.ConnectionPool(**options.get("redis", {}))

        self.client = redis.StrictRedis(connection_pool=self.conn_pool)

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Loading Redis LUA scripts")
        self.scripts = {
            self.DEQUEUE_PENDING_BATCH_SCRIPT: self.client.register_script(self.DEQUEUE_PENDING_BATCH_LUA)
        }

        self.upload_timer = None

    def _dequeue_pending_batch(self, source, destination, count):
        script = self.scripts.get(self.DEQUEUE_PENDING_BATCH_SCRIPT)
        return script(keys=[source, destination], args=[count], client=self.client)

    def _upload(self, entries):

        delay = random.randint(0, self.options.get("upload_splay", 10))
        if self.upload_timer != None and timer() - self.upload_timer < delay:

            # Take a little break before next upload
            time.sleep(delay)

        payload = "[{:s}]".format(", ".join(entries))
        headers = {
            "authorization": "token {:}".format(self.options.get("auth_token")),
            "content-type": "application/json",
        }

        try:
            res = requests.post(self.options.get("url"), data=payload, headers=headers)
        except:

            # TODO: Suppress this log
            log.exception("Unable to upload data to cloud")

            return False
        finally:
            self.upload_timer = timer()

        # All non 2xx status codes will fail
        res.raise_for_status()

        return True

    def enqueue(self, data):
        self.client.lpush(self.PENDING_QUEUE, json.dumps(data, separators=(",", ":")))

    def list_queues(self, pattern="*"):
        cur, res = self.client.scan(match=pattern)
        return sorted(res, reverse=True)

    def peek_queue(self, name, start=0, stop=-1):
        res = self.client.lrange(name, start, stop)

        return [json.loads(s) for s in res]

    def clear_queue(self, name):
        return bool(self.client.delete(name))

    def upload_queue(self, name):
        if name == self.PENDING_QUEUE:
            raise Exception("Not allowed to upload pending queue directly - use 'upload_pending_batch' method instead")

        ret = {
            "success": False,
            "count": 0
        }

        entries = self.client.lrange(name, 0, -1)
        ret["count"] = len(entries)

        if self._upload(entries):

            # Delete queue when sucessfully uploaded
            self.client.delete(name)

            ret["success"] = True

        return ret

    def upload_pending_batch(self):
        ret = {
            "success": True,
            "count": 0
        }

        # Pop next batch into work queue, if not work queue already has data
        batch = self._dequeue_pending_batch(self.PENDING_QUEUE, self.WORK_QUEUE, self.options.get("batch_size"))
        if not batch:
            if log.isEnabledFor(logging.DEBUG):
                log.debug("No pending batch found to upload")

            return ret

        ret["count"] = len(batch)

        # Upload batch
        if self._upload(batch):
            log.info("Uploaded pending batch of size %d", len(batch))

            # Batch uploaded equals work completed
            self.client.delete(self.WORK_QUEUE)
        else:
            log.warning("Temporarily unable to upload pending batch")

            ret["success"] = False

        return ret

    def upload_retry_queues(self):
        ret = {}

        for queue in self.list_queues(pattern="retr_*"):

            match = self.ERROR_QUEUE_REGEX.match(queue)
            if not match:
                log.error("Failed to match retry queue name '{:}'".format(queue))

                continue

            attempt = int(match.group("attempt")) + 1
            timestamp = match.group("timestamp")

            # Retry upload
            try:
                res = self.upload_queue(queue)
                if res["success"]:
                    log.info("Sucessfully uploaded retry queue '{:}'".format(queue))
                    ret[queue] = res["count"]
                else:
                    log.warning("Temporarily unable to upload retry queue(s)")

                    # No reason to continue trying
                    break

            except:
                max_retry = self.options.get("max_retry", 10)
                log.exception("Failed retry attempt {:}/{:} for uploading queue '{:}'".format(attempt, max_retry, queue))

                # Check if max retry is reached
                if attempt >= max_retry:
                    fail_queue = self.FAIL_QUEUE.format(timestamp, 0)

                    log.warning("Max retry attempt reached for queue '{:}' - transferring to fail queue '{:}'".format(queue, fail_queue))

                    self.client.renamenx(queue, fail_queue)
                else:

                    # Update attempt count in queue name
                    self.client.renamenx(queue, self.RETRY_QUEUE.format(timestamp, attempt))

        return ret

    def upload_fail_queues(self):
        ret = {}

        for queue in self.list_queues(pattern="fail_*"):

            match = self.ERROR_QUEUE_REGEX.match(queue)
            if not match:
                log.error("Failed to match fail queue name '{:}'".format(queue))

                continue

            attempt = int(match.group("attempt")) + 1
            timestamp = match.group("timestamp")

            try:
                res = self.upload_queue(queue)
                if res["success"]:
                    log.info("Sucessfully uploaded fail queue '{:}'".format(queue))
                    ret[queue] = res["count"]
                else:
                    log.warning("Temporarily unable to upload fail queue(s)")

                    # No reason to continue trying
                    break

            except:
                log.info("Still unable to upload fail queue '{:}'".format(queue))

                 # Update attempt count in queue name
                self.client.renamenx(queue, self.FAIL_QUEUE.format(timestamp, attempt))

        return ret

    def upload_everything(self, include_failed=False):
        ret = {}

        try:
            if include_failed:
                res = self.upload_fail_queues()
                if res:
                    ret["failed"] = sum(res.values())

            res = self.upload_retry_queues()
            if res:
                ret["retried"] = sum(res.values())
        finally:
            try:
                res = self.upload_pending_batch()
                ret["pending"] = res["count"] if res["success"] else 0

                # Continue to upload if batch limit is reached
                while res["success"] and res["count"] == self.options.get("batch_size"):
                    res = self.upload_pending_batch()
                    ret["pending"] += res["count"] if res["success"] else 0

            except:
                retry_queue = self.RETRY_QUEUE.format(self.TIMESTAMP_FORMAT.format(datetime.datetime.utcnow()), 0)
                log.exception("Failed to upload pending batch - transferring to retry queue '{:}'".format(retry_queue))
                self.client.renamenx(self.WORK_QUEUE, retry_queue)

                raise

        return ret
