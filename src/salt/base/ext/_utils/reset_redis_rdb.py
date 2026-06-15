import logging
import os
import shutil
import subprocess

log = logging.getLogger(__name__)

RDB_PATH = "/var/lib/redis/dump.rdb"
RDB_BACKUP_PATH = "/var/lib/redis/dump.rdb.bak"


def run_cmd_rc(cmd):
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    stdout, stderr = proc.communicate()
    return proc.returncode, stdout, stderr


def check_redis_and_reset():
    rc, _, _ = run_cmd_rc(["systemctl", "is-active", "--quiet", "redis"])
    if rc == 0:
        return

    if not os.path.exists(RDB_PATH):
        log.error("RDB file does not exist: %s", RDB_PATH)
        return

    rc, stdout, stderr = run_cmd_rc(["redis-check-rdb", RDB_PATH])

    if rc == 0:
        log.warning("Redis is down, RDB file is valid. Not moving backup.")
        return

    log.error("RDB validation failed: %s", stderr or stdout)

    try:
        shutil.move(RDB_PATH, RDB_BACKUP_PATH)
    except Exception as exc:
        log.error("Could not move RDB file to backup: %s", exc)
        return

    rc, stdout, stderr = run_cmd_rc(["systemctl", "restart", "redis"])
    if rc != 0:
        log.error("Failed to restart redis: %s", stderr or stdout)
        return

    log.info("Redis RDB moved to backup and redis restarted successfully.")
