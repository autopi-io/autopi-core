import datetime
import json
import logging
import os
import threading
import hashlib
from uuid import UUID
try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False
try:
    import ssl
    HAS_SSL = True
except ImportError:
    HAS_SSL = False

from salt.returners import get_returner_options


log = logging.getLogger(__name__)

client_cache_lock = threading.Lock()
client_cache = [] # List of (returner_option, client) pairs 

__virtualname__ = "mqtt"

class LockableMqttClient(mqtt.Client):
    # Allows use with "with" keyword, which controls a thread lock. 

    def __init__(self, *args, **kwargs):
        self._lock = threading.Lock()
        super(LockableMqttClient, self).__init__(*args, **kwargs)
    
    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._lock.release()
        return False    # False == propogate exceptions


def _generate_uuid_from_seed(seed):
    # Hash the ID using SHA-1 and truncate to 128 bits
    hashed_seed = hashlib.sha1(str(seed).encode()).hexdigest()[:32]
    return UUID(hashed_seed)


def __virtual__():
    if not HAS_MQTT:
        return False, "Could not import mqtt returner; " \
                      "paho mqtt client is not installed."
    if not HAS_SSL:
        return False, "Could not import mqtt returner; " \
                      "ssl is not installed."

    return __virtualname__


def _get_options(ret=None):
    """
    Get returner options, including all defaults and using the provieded returner
    options. 
    
    Note that to override a default, 'ret' structure should be {"ret_kwargs":{"<key>":"<val>"}}
    """
    if log.isEnabledFor(logging.DEBUG):
        log.debug("Getting options for: {:}".format(ret))

    # keepalive - maximum time in seconds that is allowed to pass without any 
    #   communication between the client and the broker. In other words, the 
    #   connection is considered down if there hasn't been any communication 
    #   for this many seconds, including ping probes
    defaults = {
        "client_id": "",
        "clean_session": None,
        "protocol": "MQTTv311",
        "transport": "tcp",
        "host": "localhost",
        "port": 1883,
        "keepalive": 60,
        "bind_address": "",
        "username": None,
        "password": None,
        "tls": {},
        "proxy": {},
        "ws": {},
        "topic": "",
        "qos": 0,
        "retain": False
    }

    attrs = {
        "client_id": "client_id",
        "clean_session": "clean_session",
        "protocol": "protocol",
        "transport": "transport",
        "host": "host",
        "port": "port",
        "keepalive": "keepalive",
        "bind_address": "bind_address",
        "username": "username",
        "password": "password",
        "tls": "tls",
        "proxy": "proxy",
        "ws": "ws",
        "topic": "topic",
        "qos": "qos",
        "retain": "retain"
    }

    options = get_returner_options(
        "{:}_returner".format(__virtualname__),
        ret,
        attrs,
        __salt__=__salt__,
        __opts__=__opts__,
        defaults=defaults
    )
    
    # NOTE EP: We append the process ID, so that every engine's clients would 
    #   have its own client_id (each engine runs in its own process). Otherwise, the 
    #   different clients would be constantly killing each other (if 2 clients 
    #   connect with the same client id to a broker, the first one's connection 
    #   gets killed). Then an options hash is appended so that multiple sets
    #   of options can be supported. Skip this if client_id is given explicitly.
    if not (ret and isinstance(ret, dict) and ret.get("ret_kwargs", {}).get("client_id") != None):
        override_json_str = json.dumps(ret, sort_keys=True)
        override_hash = _generate_uuid_from_seed(override_json_str)
        options["client_id"] = "{}_{}_{}".format(options["client_id"], os.getpid(), override_hash)

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Generated options: {:}".format(options))

    return options


def _get_client_for(ret):
    """
    Gets a cached client or creates a new client based on the provided option overrides
    """
    with client_cache_lock:
        # Return cached client if exsits
        kwarg_matches = filter(lambda x : x[0] == ret, client_cache)
        if kwarg_matches:
            return kwarg_matches[0][1]
        # Create, setup and cache new client if is not cached
        else:
            options = _get_options(ret)
            
            client_id = options["client_id"]
            log.info("Creating new MQTT client with id {}".format(client_id))
            instance = LockableMqttClient(
                client_id=client_id,
                clean_session=options["clean_session"],
                protocol=getattr(mqtt, options["protocol"], mqtt.MQTTv311), # Resolve MQTT constant
                transport=options["transport"]
            )
            setup_client(instance, options)
            client_cache.append(
                (ret, instance)
            )
            log.debug("Current length of client cache: {}".format(len(client_cache)))
            return instance


def setup_client(client, options):
    """
    Sets up a newly created MQTT client based on provided options
    """
    setattr(client, "metadata", {})

    # Store options in metadata
    client.metadata["options"] = options

    if options["username"]:
        client.username_pw_set(options["username"], password=options["password"])

    # Setup TLS if defined
    if options["tls"]:

        tls_kwargs = {}
        for key, val in options["tls"].iteritems():

            # Resolve SSL constants
            if key in ["cert_reqs", "tls_version"]:
                tls_kwargs[key] = getattr(ssl, val)
            else:
                tls_kwargs[key] = val

        client.tls_set(**tls_kwargs)

    # Setup proxy if defined
    if options["proxy"]:
        client.proxy_set(**options["proxy"])

    # Setup WebSocket if defined
    if options["ws"]:
        client.ws_set(**options["ws"])

    # Register callback on connect
    def on_connect(client, userdata, flags, rc):
        if rc == mqtt.MQTT_ERR_SUCCESS:
            log.info("Client successfully connected to broker")
        else:
            log.error("Client unable to connect to broker: {:}".format(mqtt.error_string(rc)))

    client.on_connect = on_connect

    # Register callback on disconnect
    def on_disconnect(client, userdata, rc):
        log.warn("Client disconnected from broker: {:}".format(mqtt.error_string(rc)))

    client.on_disconnect = on_disconnect

    # Connect to the broker
    client.connect(options["host"],
        port=options["port"],
        keepalive=options["keepalive"],
        bind_address=options["bind_address"])

    # Run a client loop to make sure 'is_connected' will return True
    rc = client.loop_start()
    if rc != mqtt.MQTT_ERR_SUCCESS:
        log.error("Client loop call after initial connect failed: {:}".format(mqtt.error_string(rc)))


def returner(ret):
    """
    Return a result to MQTT.

    Example: salt '*' test.ping --return mqtt --return_kwargs '{"host": "127.0.0.1", "port": 1883}'
    """

    returner_job(ret)


def returner_job(job):
    """
    Return a Salt job result to MQTT.
    """

    if not job or not job.get("jid", None):
        log.warn("Skipping invalid job result: {:}".format(job))

        return

    ret = job.get("return", job.get("ret", None))

    if not ret or not job.get("success", True):  # Default is success if not specified
        log.warn("Skipping unsuccessful job result with JID {:}: {:}".format(job["jid"], job))

        return

    namespace = job["fun"].split(".")
    if isinstance(ret, dict) and "_type" in ret:

        # Only use module name when type is available
        returner_data(ret, namespace[0], **job)
    else:
        returner_data(ret, *namespace, **job)


def returner_data(data, *args, **kwargs):
    """
    Return any arbitrary data structure to MQTT.
    """
    res = None

    if not data:
        log.debug("Skipping empty data result")

        return

    # Blocking lock on context enter
    with _get_client_for(kwargs) as client:
        options = client.metadata["options"]
        
        # Use the topic passed by options
        if options["topic"]:
            namespace = [options["topic"]] + list(args)[1:]

        # Use the topic passed from the workflow
        elif isinstance(data, list):
            namespace = data[1:]
            data = data[0]

        # Otherwise, go for the one that has been passed by the hook itself
        else:
            namespace = list(args)

        if isinstance(data, dict):
            payload = data

            # Append type to namespace if present and not already added
            if "_type" in data and not options["topic"] and not data["_type"] in namespace:
                namespace.append(data["_type"])

            if not "_stamp" in data:
                data["_stamp"] = datetime.datetime.utcnow().isoformat()

        elif isinstance(data, (list, set, tuple)):
            payload = {
                "_stamp": datetime.datetime.utcnow().isoformat(),
                "values": data
            }
        else:
            payload = {
                "_stamp": datetime.datetime.utcnow().isoformat(),
                "value": data
            }

        # Publish message
        topic = "/".join(namespace)
        res = client.publish(topic, json.dumps(payload, separators=(",", ":")), qos=options["qos"], retain=options["retain"])

    if res.rc != mqtt.MQTT_ERR_SUCCESS:
        log.warn("Publish of message with topic '{:}' failed: {:}".format(topic, mqtt.error_string(res.rc)))
