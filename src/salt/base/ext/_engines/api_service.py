import logging
import uuid
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException
from flask_cors import CORS
from flask_api import FlaskAPI
from functools import wraps

log = logging.getLogger(__name__)

#app = Flask(__name__)
app = FlaskAPI(__name__)

# Allows OPTIONS requests everywhere.
cors = CORS(app)

# Default settings
settings = {
    "host": "0.0.0.0",
    "port": 9000,
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


def get_minion_id():
    global minion_id
    if minion_id:
        return minion_id
    else:
        minion_id = uuid.UUID(__salt__["config.get"]("id"))
        return minion_id


caller = None

def get_caller():
    global caller
    if not caller:
        import salt.client
        import salt.config
        __opts__ = salt.config.minion_config('/etc/salt/minion')
        __opts__['file_client'] = 'local'
        __opts__['file_roots']['base'].append('/var/cache/salt/minion/files/base')

        caller = salt.client.Caller(mopts=__opts__)

    return caller


def salt(command, *args, **kwargs):
    log.info('SALT CMD: cmd: {:}, args: {:}, kwargs: {:}'.format(
        command, args, kwargs))
    return __salt__['minionutil.run_job'](command, *args, **kwargs)


@app.route("/")
def index():
    return {"unit_id": get_minion_id()}


@app.route("/auth/login/", methods=["POST"])
def auth_login():
    devices = [{"unit_id": get_minion_id(), "display": "Local device"}]
    auth_response = {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImxvY2FsIHVzZXIiLCJ1c2VyX2lkIjoxLCJlbWFpbCI6IiIsImV4cCI6NDEwMjQ0NDgwMH0.X4nF8J2JMOXX0JIfs_KUbf7TjzU-5sfN1VImSmRnoW8",
        "user": {
            "pk": 0,
            "username": "local user",
            "has_devices": True,
            "is_local": True,
            "devices": devices
        }
    }
    return auth_response


@app.route("/dongle/devices/")
def devices():
    devices = [{"unit_id": get_minion_id(), "display": "Local device"}]
    return devices


@app.route('/dongle/<uuid:unit_id>/execute/', methods=['POST'])
def terminal_execute(unit_id):
    minion_id = get_minion_id()

    if not minion_id == unit_id:
        log.warning('unit_id does not match the id configured on this device')
        return 'unit_id does not match the id configured on this device', 401

    cmd_object = request.get_json(force=True)

    command = cmd_object['command']
    args = cmd_object['arg']
    kwargs = dict(cmd_object['kwarg'])

    if command.startswith('state.'):
        log.info('executing command via caller')
        try:
            response = get_caller().cmd(command, *args, **kwargs)
        except:
            log.exception('Failed while executing command via caller')
            # reset caller to get new instance for next command, just in case
            global caller
            caller = None

            raise
    else:
        log.info('executing command via minionutil.run_job')
        response = salt(command, *args, **kwargs)

    return jsonify(response)


@app.route('/dongle/<uuid:unit_id>/settings/apn/', methods=['GET', 'PUT'])
def apn_settings(unit_id):
    minion_id = get_minion_id()

    if not minion_id == unit_id:
        log.warning('unit_id does not match the id configured on this device')
        return 'unit_id does not match the id configured on this device', 401

    grain_name = 'qmi'
    allowed_keys = ["pin", "user", "pass", "apn"]

    if request.method == 'GET':
        obj = __salt__['grains.get'](grain_name, default={})

        return jsonify(obj)
    elif request.method == 'PUT':
        obj = request.get_json(force=True)
        validated_settings = {"apn": obj.get("apn", ""), "pass": obj.get(
            "pass", ""), "user": obj.get("user", ""), "pin": obj.get("pin", "")}

        if not all(key in allowed_keys for key in obj.keys()):
            invalid_keys = list(set(obj.keys()) - set(allowed_keys))
            return ('Invalid keys found. %s' % invalid_keys), 400

        __salt__["grains.set"](grain_name, validated_settings, force=True)
        __salt__["saltutil.refresh_grains"](refresh_pillar=False)

        grains = __salt__["grains.get"](grain_name, default={})
        return grains


def start(flask):
    try:
        log.debug("Starting API service")

        global settings
        settings.update(flask)

        get_minion_id()

        app.run(**settings)

    except Exception:
        log.exception("Failed to start API service")
        raise
    finally:
        log.info("Stopping API service")
