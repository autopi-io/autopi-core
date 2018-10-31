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

    DEQUEUE_BATCH_SCRIPT = "dequeue_batch"
    DEQUEUE_BATCH_LUA = """
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

    PENDING_QUEUE       = "pend"
    PENDING_WORK_QUEUE  = "pend.work"
    RETRY_QUEUE         = "retr_{:%Y%m%d%H%M%S%f}_#{:d}"
    FAIL_QUEUE          = "fail_{:%Y%m%d}"
    FAIL_WORK_QUEUE     = "fail.work"

    RETRY_QUEUE_REGEX = re.compile("^(?P<type>.+)_(?P<timestamp>\d+)_#(?P<attempt>\d+)$")

    def __init__(self):
        self.upload_timer = None

    def setup(self, **options):
        self.options = options

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Creating Redis connection pool")
        self.conn_pool = redis.ConnectionPool(**options.get("redis", {}))

        self.client = redis.StrictRedis(connection_pool=self.conn_pool)

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Loading Redis LUA scripts")
        self.scripts = {
            self.DEQUEUE_BATCH_SCRIPT: self.client.register_script(self.DEQUEUE_BATCH_LUA)
        }

        return self

    def enqueue(self, data):
        self.client.lpush(self.PENDING_QUEUE, json.dumps(data, separators=(",", ":")))

    def _dequeue_batch(self, source, destination, count):
        script = self.scripts.get(self.DEQUEUE_BATCH_SCRIPT)
        return script(keys=[source, destination], args=[count], client=self.client)

    def list_queues(self, pattern="*"):
        # We always have a limited amount of keys so it should be fine to use 'keys' instead of 'scan'
        res = self.client.keys(pattern=pattern)
        return sorted(res, reverse=True)

    def peek_queue(self, name, start=0, stop=-1):
        res = self.client.lrange(name, start, stop)

        return [json.loads(s) for s in res]

    def clear_queue(self, name):
        return bool(self.client.delete(name))

    def _upload(self, entries, endpoint=None):
        endpoint = endpoint or self.options.get("endpoint", {})
        if not endpoint:
            log.warning("Cannot upload data to cloud because no endpoint is configured")

            return False, "No cloud endpoint configured"

        delay = random.randint(0, self.options.get("upload_splay", 10))
        if self.upload_timer != None and timer() - self.upload_timer < delay:

            # Take a little break before next upload
            time.sleep(delay)

        payload = "[{:s}]".format(", ".join(entries))
        headers = {
            "authorization": "token {:}".format(endpoint.get("auth_token")),
            "content-type": "application/json",
        }

        try:
            res = requests.post(endpoint.get("url"), data=payload, headers=headers)
        except Exception as ex:
            return False, str(ex)
        finally:
            self.upload_timer = timer()

        # All non 2xx status codes will fail
        res.raise_for_status()

        return True, None

    def _upload_batch(self, source_queue, work_queue):
        ret = {
            "count": 0
        }

        # Pop next batch into work queue, if not work queue already has data
        batch = self._dequeue_batch(source_queue, work_queue, self.options.get("batch_size", 100))
        if not batch:
            if log.isEnabledFor(logging.DEBUG):
                log.debug("No batch found to upload")

            return ret

        # Upload batch
        ok, msg = self._upload(batch)
        if ok:
            log.info("Uploaded batch with {:} entries".format(len(batch)))

            ret["count"] = len(batch)

            # Batch uploaded equals work completed
            self.client.delete(work_queue)
        else:
            log.warning("Temporarily unable to upload batch")

            ret["error"] = msg

        return ret

    def upload_failing(self):
        ret = {
            "total": 0,
        }

        for queue in self.list_queues(pattern="fail_*"):
            res = self._upload_batch(queue, self.FAIL_WORK_QUEUE)
            if "error" in res:
                ret["error"] = res["error"]
            else:
                ret["total"] += res["count"]

            # Continue to upload if more failed batches present
            while not "error" in res and res["count"] == self.options.get("batch_size", 100):
                res = self._upload_batch(queue, self.FAIL_WORK_QUEUE)
                if "error" in res:
                    ret["error"] = res["error"]
                else:
                    ret["total"] += res["count"]

        return ret

    def upload_pending(self):
        ret = {
            "total": 0,
        }

        try:
            res = self._upload_batch(self.PENDING_QUEUE, self.PENDING_WORK_QUEUE)
            if "error" in res:
                ret["error"] = res["error"]
            else:
                ret["total"] += res["count"]

            # Continue to upload if more pending batches present
            while not "error" in res and res["count"] == self.options.get("batch_size", 100):
                res = self.upload_pending_batch()
                if "error" in res:
                    ret["error"] = res["error"]
                else:
                    ret["total"] += res["count"]

        except:

            # Create retry queue for batch
            retry_queue = self.RETRY_QUEUE.format(datetime.datetime.utcnow(), 0)
            log.exception("Failed to upload pending batch - transferring to dedicated retry queue '{:}'".format(retry_queue))

            self.client.renamenx(self.PENDING_WORK_QUEUE, retry_queue)

            raise

        return ret

    def upload_retrying(self):
        ret = {
            "total": 0,
        }

        queues = self.list_queues(pattern="retr_*")

        # Needed in 'upload_everything' so we add it here
        ret["queue_count"] = len(queues)

        for queue in queues:

            match = self.RETRY_QUEUE_REGEX.match(queue)
            if not match:
                log.error("Failed to match retry queue name '{:}'".format(queue))

                continue

            attempt = int(match.group("attempt")) + 1
            entries = self.client.lrange(queue, 0, -1)

            # Retry upload
            try:
                ok, msg = self._upload(entries)
                if ok:
                    log.info("Sucessfully uploaded retry queue '{:}'".format(queue))
                    ret["total"] += len(entries)
                else:
                    log.warning("Temporarily unable to upload retry queue(s) - skipping remaining if present")

                    ret["error"] = msg

                    # No reason to continue trying
                    break

            except:
                max_retry = self.options.get("max_retry", 10)
                log.warning("Failed retry attempt {:}/{:} for uploading queue '{:}'".format(attempt, max_retry, queue))

                # Transfer to fail queue if max retry is reached
                if attempt >= max_retry:
                    fail_queue = self.FAIL_QUEUE.format(datetime.datetime.utcnow())
                    log.warning("Max retry attempt reached for queue '{:}' - transferring to fail queue '{:}'".format(queue, fail_queue))

                    self.client.pipeline() \
                        .lpush(fail_queue, *entries) \
                        .expire(fail_queue, self.options.get("fail_ttl", 604800)) \
                        .delete(queue) \
                        .execute()

                else:

                    # Update attempt count in queue name
                    self.client.renamenx(queue, re.sub("_#\d+$", "_#{:}".format(attempt), queue))

        return ret

    def upload_everything(self, include_failed=False):
        ret = {}

        if include_failed:
            try:
                res = self.upload_failing()
                if res["total"] > 0:
                    log.info("Successfully uploaded {:} failed entries".format(res["total"]))

                ret["failed"] = res
            except:
                log.warning("Still unable to upload failed batch(es)")

        try:
            res = self.upload_retrying()
            if res["total"] > 0:
                log.info("Successfully uploaded {:} retried entries".format(res["total"]))

            ret["retried"] = res

            # Check if we have reached retry queue limit
            if res["queue_count"] >= self.options.get("retry_queue_limit", 20):
                log.warning("Skipping upload of pending batch(es) as retry queue limit is reached")

                return ret
        except:
            log.exception("Failed to upload retrying due to an unexpected exception")

        ret["pending"] = self.upload_pending()

        return ret
