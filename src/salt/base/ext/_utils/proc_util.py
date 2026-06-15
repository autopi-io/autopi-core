import logging
import psutil

from subprocess import check_output


log = logging.getLogger(__name__)


HAS_SETPROCTITLE = True
try:
    import setproctitle
except:
    HAS_SETPROCTITLE = False
    log.exception("Failed to import 'setproctitle'")
    

def pid_by_name(name):
    try:
        return int(check_output(["pidof", name]).strip())
    except subprocess.CalledProcessError as err:
        log.info("Unable to find PID by name '{}': {}".format(name, err))
        return None


def enforce_single_process_with_name(name, prefix="", suffix="@salt_engine"):
    full_name = "{}{}{}".format(prefix, name, suffix)

    if not HAS_SETPROCTITLE:
        log.warning("Unable to enforce single process with name '{}' because dependency 'setproctitle' is missing".format(full_name))

        return False

    for proc in psutil.process_iter():
        if proc.name() == full_name:
            log.warning("Killing existing process with name '{}': {}".format(full_name, proc))
            proc.kill()

    setproctitle.setproctitle(full_name)

    return True


def find_children(pid, func, recursive=False):
    parent = psutil.Process(pid)
    for child in parent.children(recursive=recursive):
        if func(child):
            return child

    return None


def kill_recursively(pid):
    ret = True

    parent = psutil.Process(pid)
    for child in parent.children(recursive=True):
        try:
            child.kill()
        except:
            log.exception("Unable to kill the child process of parent with PID {}: {}".format(pid, child))
            ret = False

    try:
        parent.kill()
    except:
        log.exception("Unable to kill the parent process with PID {}: {}".format(pid, parent))
        ret = False

    return ret
