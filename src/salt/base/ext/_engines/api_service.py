import logging
import shlex
import uuid

from flask import Flask, jsonify, request, send_from_directory, send_file, abort
from werkzeug.exceptions import HTTPException
from flask_cors import CORS
from flask_api import FlaskAPI
from functools import wraps
from threading_more import intercept_exit_signal

log = logging.getLogger(__name__)

app = FlaskAPI(__name__)

# Allows OPTIONS requests everywhere.
cors = CORS(app, send_wildcard=True)

# Default Flask settings
flask_settings = {
    "host": "0.0.0.0",
    "port": 9000,
    "threaded": True,
    # Do not use debug settings here, as this will spawn new processes of the salt-minion
}


@app.errorhandler(Exception)
def handle_error(e):
    log.error('exception occurred: {:}'.format(e))
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    return jsonify(error=str(e)), code


from werkzeug.exceptions import default_exceptions
for ex in default_exceptions:
    app.register_error_handler(ex, handle_error)


minion_id = None

def _minion_id():
    global minion_id
    if minion_id:
        return minion_id
    else:
        minion_id = uuid.UUID(__salt__["config.get"]("id"))
        return minion_id


def _caller():
    log.info('Creating Salt caller instance...')

    import salt.client
    import salt.config

    opts = salt.config.minion_config('/etc/salt/minion')
    opts['file_client'] = 'local'
    opts['file_roots']['base'].append('/var/cache/salt/minion/files/base')

    return salt.client.Caller(mopts=opts)


@app.route("/")
def index():
    return {"unit_id": _minion_id()}


@app.route("/auth/login/", methods=["POST"])
def auth_login():
    devices = [{"unit_id": _minion_id(), "display": "Local device"}]
    auth_response = {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImxvY2FsIHVzZXIiLCJ1c2VyX2lkIjoxLCJlbWFpbCI6IiIsImV4cCI6NDEwMjQ0NDgwMH0.X4nF8J2JMOXX0JIfs_KUbf7TjzU-5sfN1VImSmRnoW8",
        "user": {
            "pk": 0,
            "username": "local user",
            "has_devices": True,
            "is_local": True,
            "devices": devices,
            "timezone": 'UTC'
        }
    }
    return auth_response


@app.route("/dongle/devices/")
def devices():
    devices = [{"unit_id": _minion_id(), "display": "Local device"}]
    return devices


@app.route("/download_log/")
def download_log():
    file_name = request.args.get('file')
    return send_from_directory('/var/log/', file_name, as_attachment=True)


@app.route('/dongle/<uuid:unit_id>/execute/', methods=['POST'])
def terminal_execute(unit_id, data=None):
    minion_id = _minion_id()

    if not minion_id == unit_id:
        log.warning('unit_id does not match the id configured on this device')
        return 'unit_id does not match the id configured on this device', 401

    data = data or request.get_json(force=True)
    if isinstance(data, list):
        import salt.utils.args  # Lazy load because it is a little slow
        args = salt.utils.args.parse_input(data)

        cmd = args.pop(0)
        cmd_args = []
        cmd_kwargs = {}
        for arg in args:
            if isinstance(arg, dict) and arg.get("__kwarg__", False):
                arg.pop("__kwarg__")
                cmd_kwargs = arg
            else:
                cmd_args.append(arg)
    else:
        cmd = data['command']
        cmd_args = data['arg']
        cmd_kwargs = dict(data['kwarg'])

    if cmd.startswith('state.'):
        log.info("Executing command via caller: {:}".format(data))
        res = _caller().cmd(cmd, *cmd_args, **cmd_kwargs)
    elif cmd.startswith('minionutil.update_release'):
        log.info("Executing command via minion process: {:}".format(data))
        res = __salt__['minionutil.run_job'](cmd, *cmd_args, **cmd_kwargs)
    else:
        log.info("Executing command directly in local process: {:}".format(data))
        res = __salt__[cmd](*cmd_args, **cmd_kwargs)

    return jsonify(res)


@app.route('/dongle/<uuid:unit_id>/execute_raw/', methods=['POST'])
def terminal_execute_raw(unit_id):
    data = request.get_json(force=True)
    return terminal_execute(unit_id, data=shlex.split(data["command"], posix=False))


@app.route('/dongle/<uuid:unit_id>/settings/apn/', methods=['GET', 'PUT'])
def apn_settings(unit_id):
    minion_id = _minion_id()

    if not minion_id == unit_id:
        log.warning('unit_id does not match the id configured on this device')
        return 'unit_id does not match the id configured on this device', 401

    grain_name = 'qmi'
    allowed_keys = ["pin", "user", "pass", "apn", "mtu"]

    if request.method == 'GET':
        obj = __salt__['grains.get'](grain_name, default={})

        return jsonify(obj)
    elif request.method == 'PUT':
        obj = request.get_json(force=True)
        validated_settings = {
            "apn": obj.get("apn", ""),
            "pass": obj.get("pass", ""),
            "user": obj.get("user", ""),
            "pin": obj.get("pin", ""),
            "mtu": obj.get("mtu", None)
        }

        if not all(key in allowed_keys for key in obj.keys()):
            invalid_keys = list(set(obj.keys()) - set(allowed_keys))
            return ('Invalid keys found. %s' % invalid_keys), 400

        __salt__["grains.set"](grain_name, validated_settings, force=True)
        __salt__["saltutil.refresh_grains"](refresh_pillar=False)

        grains = __salt__["grains.get"](grain_name, default={})
        return grains


@intercept_exit_signal
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting API service with settings: {:}".format(settings))

        global flask_settings
        flask_settings.update(settings["flask"])

        _minion_id()

        app.run(**flask_settings)

    except Exception:
        log.exception("Failed to start API service")

        raise
    finally:
        log.info("Stopping API service")
