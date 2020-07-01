import logging
import salt.exceptions
import salt.utils.event
import salt.utils.jid
import subprocess


log = logging.getLogger(__name__)


def remove_all(*paths):
    """
    Similar to 'file.remove' but with many at once.
    """

    ret = {}

    for path in paths:
        ret[path] = __salt__["file.remove"](path)

    return ret


def line_count(file):
    """
    Returns count of new line characters in a file.
    """

    ret = {}

    proc = subprocess.Popen(["wc", "-l", file],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    out = proc.stdout.read()
    err = proc.stderr.read()
    if err:
      raise Exception(err)

    ret["value"] = int(out.spit(" ")[0])

    return ret
    

def upload(path, gzip=True, service=None, **kwargs):
    """
    TODO: Add documentation
    """

    ret = {}

    if service == "dropbox":
        token = kwargs.get("token", None)
        if not token:
            raise salt.exceptions.CommandExecutionError("Dropbox token is mandatory")


    # TODO: Implement
    
    return ret
