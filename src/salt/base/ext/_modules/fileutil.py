import os
import requests
import logging
import salt.exceptions
import salt.utils.event
import salt.utils.jid
import subprocess
import yaml


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
    Uploads a file (by default gzipped) to a service.

    Arguments:
      - path (str): Path to the file.

    Optional arguments:
      - gzip (bool): Gzip it? Default is 'True'.
      - service (str): The service to be used (Possible: 'dropbox'). Default is None.
      - token (str): The token to use when uploading (Required when using 'dropbox' service)
    """

    # setup
    ret = {}
    _, tail = os.path.split(path)
    filename, ext = os.path.splitext(tail)
    path_to_upload = path
    gzip_path = '/tmp'

    # zip file
    if gzip:
        log.debug('Gzipping file')

        os.system('gzip --keep -f {:} --stdout > {:}'.format(path, os.path.join(gzip_path, filename + '.gz')))
        path_to_upload = os.path.join(gzip_path, filename + '.gz')
        ext = '.gz'

    # upload file
    log.info('Uploading files using {:} service'.format(service))
    if service == "dropbox":
        token = kwargs.get("token", None)
        if not token:
            raise salt.exceptions.CommandExecutionError("Dropbox token is mandatory")

        log.debug('Opening file')
        with open(path_to_upload, 'rb') as file:
            dropbox_url = 'https://content.dropboxapi.com/2/files/upload'
            dropbox_api_arg = '{{"path": "/{:}{:}", "mode": "overwrite"}}'.format(filename, ext)
            headers = {
                'Dropbox-API-Arg': dropbox_api_arg,
                'Content-Type': 'application/octet-stream',
                'Authorization': 'Bearer ' + token,
            }

            log.debug('Sending upload request')
            response = requests.post(dropbox_url, headers=headers, data=file)

        # cleanup
        if gzip:
            log.debug('Cleaning up gzip files')
            os.remove(os.path.join(gzip_path, filename + ext))

        ret = {
            "success": response.status_code >= 200 and response.status_code <= 299,
            "status_code": response.status_code,
            "text": response.text,
        }
    else:
        raise salt.exceptions.CommandExecutionError("You need to specify a service to use")
    
    return ret


def load_yaml(file, default={}):
    """
    Load a file as YAML or return default.
    """

    if not os.path.isfile(file):
        return default

    with open(file, "r") as f:
        return yaml.load(f, Loader=yaml.CLoader) or default

