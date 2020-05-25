import datetime
import gzip
import json
import logging
import random
import re
import redis
import requests
import StringIO
import time

from requests.exceptions import RequestException
from timeit import default_timer as timer


log = logging.getLogger(__name__)


class CloudCache(object):

    DEQUEUE_BATCH_SCRIPT = "dequeue_batch"
    DEQUEUE_BATCH_LUA = """

    local ret = {}

    local cnt = tonumber(ARGV[1])

    -- Check if destination already exists
    if redis.call('EXISTS', KEYS[2]) == 1 then

        -- Retrieve all entries from destination
        for _, key in ipairs(redis.call('LRANGE', KEYS[2], 0, cnt - 1)) do

            -- Add to return table and ensure chronological/ascending order
            table.insert(ret, 1, key)

            -- Decrement count
            cnt = cnt - 1
        end
    end

    -- Check if count is still greater than zero and source exists
    if cnt > 0 and redis.call('EXISTS', KEYS[1]) == 1 then

        -- Transfer amount of entries from source to destination matching remaining count
        for i = 1, cnt do
            local val = redis.call('RPOPLPUSH', KEYS[1], KEYS[2])
            if not val then
                break
            end

            -- Also add to return table
            table.insert(ret, val)
        end

        -- Also transfer TTL
        local ttl = redis.call('TTL', KEYS[1])
        if ttl > 0 then
            redis.call('EXPIRE', KEYS[2], ttl)
        end
    end

    return ret
    """

    PENDING_QUEUE     = "pend"
    RETRY_QUEUE       = "retr_{:%Y%m%d%H%M%S%f}_#{:d}"
    FAIL_QUEUE        = "fail_{:%Y%m%d}"
    WORK_QUEUE        = "{:}.work"

    RETRY_QUEUE_REGEX  = re.compile("^(?P<type>.+)_(?P<timestamp>\d+)_#(?P<attempt>\d+)$")
    WORK_QUEUE_REGEX   = re.compile("\.work$")

    def __init__(self):
        self.upload_timer = None

    def setup(self, **options):
        self.options = options

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Creating Redis connection pool")
        self.conn_pool = redis.ConnectionPool(**options.get("redis", {k.replace("redis_", "", 1): v for k, v in options.iteritems() if k.startswith("redis_")}))

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
        start = timer()
        try:
            script = self.scripts.get(self.DEQUEUE_BATCH_SCRIPT)
            return script(keys=[source, destination], args=[count], client=self.client)
        finally:
            duration = timer() - start
            if duration > .5:
                log.warning("Dequeue batch of size {:} took {:} second(s) to complete - consider reducing batch size".format(count, duration))

    def list_queues(self, pattern="*", reverse=False):
        # We always have a limited amount of keys so it should be safe to use 'keys' instead of 'scan'
        res = self.client.keys(pattern=pattern)
        return sorted(res, reverse=reverse)

    def peek_queue(self, name, start=0, stop=-1):
        res = self.client.lrange(name, start, stop)

        return [json.loads(s) for s in res]

    def clear_queue(self, name):
        return bool(self.client.delete(name))

    def clear_everything(self, confirm=False):
        if not confirm:
            raise Exception("You are about to flush all cache queues - add parameter 'confirm=True' to continue anyway")

        return self.client.flushdb()

    def _prepare_payload_for(self, batch):
        payload = "[{:s}]".format(",".join(batch))

        if "compression" in self.options:
            if self.options["compression"]["algorithm"] == "gzip":
                start = timer()

                buffer = StringIO.StringIO()
                with gzip.GzipFile(fileobj=buffer, mode="wt", compresslevel=self.options["compression"].get("level", 1)) as gf:
                   gf.write(payload)

                compressed_payload = buffer.getvalue()
                
                log.info("Compressed payload with size {:} to {:} in {:} second(s)".format(len(payload), len(compressed_payload), timer() - start))

                payload = compressed_payload
            else:
                log.warning("Unsupported compression algorithm configured - skipping compression")

        return payload

    def _upload(self, payload, endpoint=None, splay_factor=1):
        endpoint = endpoint or self.options.get("endpoint", {})
        if not endpoint:
            log.warning("Cannot upload data to cloud because no endpoint is configured")

            return False, "No cloud endpoint configured"

        delay = random.randint(0, self.options.get("upload_splay", 10)) * splay_factor
        if self.upload_timer != None and timer() - self.upload_timer < delay:
            if splay_factor > 1:
                log.warning("Enforcing increased (by factor {:}) repeated upload delay of {:} seconds...".format(splay_factor, delay))
            else:
                log.info("Enforcing repeated upload delay of {:} seconds...".format(delay))

            # Take a little break before next upload
            time.sleep(delay)

        headers = {
            "authorization": "token {:}".format(endpoint.get("auth_token")),
            "content-type": "application/json",
        }

        # Set correct content encoding when compression is enabled
        if "compression" in self.options:
            headers["content-encoding"] = self.options["compression"]["algorithm"]

        try:
            res = requests.post(endpoint.get("url"), data=payload, headers=headers, timeout=endpoint.get("timeout", 10))
        except Exception as ex:
            return False, str(ex)
        finally:
            self.upload_timer = timer()

        # All non 2xx status codes will fail
        res.raise_for_status()

        return True, None

    def _upload_batch(self, queue):
        ret = {
            "count": 0
        }

        source_queue = re.sub(self.WORK_QUEUE_REGEX, "", queue)  # Remove suffix if already a work queue
        work_queue = self.WORK_QUEUE.format(source_queue)

        # Pop next batch into work queue
        batch = self._dequeue_batch(source_queue, work_queue, self.options.get("max_batch_size", 100))
        if not batch:
            if log.isEnabledFor(logging.DEBUG):
                log.debug("No batch found to upload from queue '{:}'".format(queue))

            return ret

        # Upload batch
        payload = self._prepare_payload_for(batch)
        ok, msg = self._upload(payload)  # Remember this call will raise exception upon server error
        if ok:
            log.info("Uploaded batch with {:} entries from queue '{:}'".format(len(batch), queue))

            ret["count"] = len(batch)

            # Batch uploaded equals work completed
            self.client.pipeline() \
                .delete(work_queue) \
                .bgsave() \
                .execute()
        else:
            log.warning("Temporarily unable to upload batch with {:} entries from queue '{:}': {:}".format(len(batch), queue, msg))

            ret["error"] = msg

        return ret

    def _upload_batch_continuing(self, queue):
        ret = {
            "count": 0
        }

        res = self._upload_batch(queue)  # Remember this call will raise exception upon server error

        ret["count"] = res["count"]
        if "error" in res:
            ret["error"] = res["error"]

        # Continue to upload if more pending batches present
        while not "error" in res and (res["count"] == self.options.get("max_batch_size", 100) or res.get("continue", False)):
            res = self._upload_batch(queue)  # Remember this call will raise exception upon server error

            ret["count"] += res["count"]
            if "error" in res:
                ret["error"] = res["error"]

        return ret

    def upload_failing(self):
        ret = {
            "total": 0,
        }

        queues = self.list_queues(pattern="fail_*")  # This will also include work queues if present
        if queues:
            log.warning("Found {:} fail queue(s)".format(len(queues)))

        try:
            for queue in queues:
                res = self._upload_batch_continuing(queue)  # Remember this call will raise exception upon server error
                ret["total"] += res["count"]

                # Stop upon first error
                if "error" in res:
                    ret.setdefault("errors", []).append(res["error"])

                    break

        except RequestException as rex:
            ret.setdefault("errors", []).append(str(rex))

            log.warning("Still unable to upload failed batch(es): {:}".format(rex))

        return ret

    def upload_pending(self):
        ret = {
            "total": 0,
        }

        try:
            res = self._upload_batch_continuing(self.PENDING_QUEUE)  # Remember this call will raise exception upon server error
            ret["total"] += res["count"]

            if "error" in res:
                ret.setdefault("errors", []).append(res["error"])

        # Only retry upon server error
        except RequestException as rex:
            ret.setdefault("errors", []).append(str(rex))

            work_queue = self.WORK_QUEUE.format(self.PENDING_QUEUE)
            if self.options.get("max_retry", 10) > 0:

                # Create retry queue for batch
                retry_queue = self.RETRY_QUEUE.format(datetime.datetime.utcnow(), 0)
                log.warning("Failed to upload pending batch - transferring to new dedicated retry queue '{:}': {:}".format(retry_queue, rex))

                self.client.pipeline() \
                    .renamenx(work_queue, retry_queue) \
                    .bgsave() \
                    .execute()

            else:
                log.warning("Failed to upload pending batch - leaving batch in queue '{:}': {:}".format(work_queue, rex))

        return ret

    def upload_retrying(self):
        ret = {
            "total": 0,
        }

        queue_limit = self.options.get("retry_queue_limit", 10)

        queues = self.list_queues(pattern="retr_*")
        if queues:
            log.warning("Found {:}/{:} retry queue(s)".format(len(queues), queue_limit))

        remaining_count = len(queues)
        for queue in queues:

            match = self.RETRY_QUEUE_REGEX.match(queue)
            if not match:
                log.error("Failed to match retry queue name '{:}'".format(queue))

                continue

            attempt = int(match.group("attempt")) + 1
            entries = self.client.lrange(queue, 0, -1)
            payload = self._prepare_payload_for(entries)

            # Retry upload
            try:
                ok, msg = self._upload(payload, splay_factor=remaining_count)  # Remember this call will raise exception upon server error
                if ok:
                    log.info("Sucessfully uploaded retry queue '{:}' with {:} entries".format(queue, len(entries)))

                    self.client.pipeline() \
                        .delete(queue) \
                        .bgsave() \
                        .execute()

                    ret["total"] += len(entries)

                    remaining_count -= 1
                else:
                    log.warning("Temporarily unable to upload retry queue(s) - skipping remaining if present: {:}".format(msg))

                    ret.setdefault("errors", []).append(msg)

                    # No reason to continue trying
                    break

            # Only retry upon server error
            except RequestException as rex:
                ret.setdefault("errors", []).append(str(rex))

                max_retry = self.options.get("max_retry", 10)
                log.warning("Failed retry attempt {:}/{:} for uploading queue '{:}': {:}".format(attempt, max_retry, queue, rex))

                # Transfer to fail queue if max retry is reached
                if attempt >= max_retry:
                    fail_queue = self.FAIL_QUEUE.format(datetime.datetime.utcnow())
                    log.warning("Max retry attempt reached for queue '{:}' - transferring to fail queue '{:}'".format(queue, fail_queue))

                    self.client.pipeline() \
                        .lpush(fail_queue, *entries) \
                        .expire(fail_queue, self.options.get("fail_ttl", 604800)) \
                        .delete(queue) \
                        .bgsave() \
                        .execute()

                else:

                    # Update attempt count in queue name
                    self.client.pipeline() \
                        .renamenx(queue, re.sub("_#\d+$", "_#{:}".format(attempt), queue)) \
                        .bgsave() \
                        .execute()

        # Signal if we have reached queue limit
        ret["is_overrun"] = remaining_count >= queue_limit

        return ret


class NextCloudCache(CloudCache):
    """
    To improve performance at large batch sizes, '.work' queues have been phased out.
    """

    def __init__(self):
        CloudCache.__init__(self)
        self.upload_cache = {}

    def _dequeue_batch(self, *args, **kwargs):
        raise Exception("Not supported")

    def _upload_batch(self, queue):
        ret = {
            "count": 0
        }

        # First check for cached batch
        batch_reversed, payload = self.upload_cache.pop(queue, (None, None))
        if batch_reversed:
            log.info("Found cached batch with {:} entries for queue '{:}'".format(len(batch_reversed), queue))

            # Signal that upload of next batch should continue on success (needed because max batch size might not be met)
            ret["continue"] = True

        # Otherwise pull new batch from queue
        else:
            batch_reversed = self.client.lrange(queue, -self.options.get("max_batch_size", 100), -1)
            if not batch_reversed:
                if log.isEnabledFor(logging.DEBUG):
                    log.debug("No batch found to upload from queue '{:}'".format(queue))

                return ret

            payload = self._prepare_payload_for(reversed(batch_reversed))

        # Try upload batch payload
        try:
            ok, msg = self._upload(payload)  # Remember this call will raise exception upon server error
            if ok:
                log.info("Uploaded batch with {:} entries from queue '{:}'".format(len(batch_reversed), queue))

                ret["count"] = len(batch_reversed)

                # Remove batch entries from queue and persist immediately
                self.client.pipeline() \
                    .ltrim(queue, 0, -(len(batch_reversed) + 1)) \
                    .bgsave() \
                    .execute()

            else:
                log.warning("Temporarily unable to upload batch with {:} entries from queue '{:}': {:}".format(len(batch_reversed), queue, msg))

                # Put batch into upload cache
                self.upload_cache[queue] = (batch_reversed, payload)

                ret["error"] = msg

        # Only pending queue support retry upon server error
        except RequestException as rex:

            if queue == self.PENDING_QUEUE and self.options.get("max_retry", 10) > 0:

                # Create retry queue for batch
                retry_queue = self.RETRY_QUEUE.format(datetime.datetime.utcnow(), 0)
                log.warning("Failed to upload pending batch - transferring to new dedicated retry queue '{:}': {:}".format(retry_queue, rex))

                self.client.pipeline() \
                    .lpush(retry_queue, *batch_reversed) \
                    .ltrim(queue, 0, -(len(batch_reversed) + 1)) \
                    .bgsave() \
                    .execute()

            else:
                log.warning("Failed to upload batch - leaving batch in queue '{:}': {:}".format(queue, rex))

            raise

        return ret

    def upload_pending(self):
        ret = {
            "total": 0,
        }

        try:
            res = self._upload_batch_continuing(self.PENDING_QUEUE)  # Remember this call will raise exception upon server error
            ret["total"] += res["count"]

            if "error" in res:
                ret.setdefault("errors", []).append(res["error"])

        except RequestException as rex:
            ret.setdefault("errors", []).append(str(rex))

            # Retry queue logic is moved to '_upload_batch' method

        return ret