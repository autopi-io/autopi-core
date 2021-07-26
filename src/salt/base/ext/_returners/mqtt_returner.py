import datetime
import json
import logging
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


__virtualname__ = "mqtt"


def __virtual__():
    if not HAS_MQTT:
        return False, "Could not import mqtt returner; " \
                      "paho mqtt client is not installed."
    if not HAS_SSL:
        return False, "Could not import mqtt returner; " \
                      "ssl is not installed."

    return __virtualname__


def _get_options(ret=None):
    if log.isEnabledFor(logging.DEBUG):
        log.debug("Getting options for: {:}".format(ret))

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
        "ws": {}
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
        "ws": "ws"
    }

    options = get_returner_options(
        "{:}_returner".format(__virtualname__),
        ret,
        attrs,
        __salt__=__salt__,
        __opts__=__opts__,
        defaults=defaults
    )

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Generated options: {:}".format(options))

    return options


def _get_client_for(ret):

    # Get client instance from context if present
    client = __context__.get(__name__, None)

    # Create new instance if no existing found
    if client == None:
        options = _get_options(ret)
        log.info("Creating client instance with options: {:}".format(options))

        client = mqtt.Client(
            client_id=options["client_id"],
            clean_session=options["clean_session"],
            protocol=getattr(mqtt, options["protocol"], mqtt.MQTTv311),  # Resolve MQTT constant
            transport=options["transport"])

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
            
            # Call disconnect to make sure 'is_connected' will return False
            rc = client.disconnect()
            log.info("Client disconnect result: {:}".format(mqtt.error_string(rc)))

        client.on_disconnect = on_disconnect

        # Connect to the broker
        client.connect(options["host"],
            port=options["port"],
            keepalive=options["keepalive"],
            bind_address=options["bind_address"])

        # Run a client loop to make sure 'is_connected' will return True
        rc = client.loop()
        if rc != mqtt.MQTT_ERR_SUCCESS:
            log.error("Client loop call after initial connect failed: {:}".format(mqtt.error_string(rc)))

        __context__[__name__] = client
    else:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Re-using client instance found in context")

    # Check connection
    if not client.is_connected():
        log.warn("Client is no longer connected - attempting to reconnect")

        # Attempt to reconnect
        rc = client.reconnect()
        log.info("Client reconnect result: {:}".format(mqtt.error_string(rc)))

        # Run a client loop to make sure 'is_connected' will return True
        rc = client.loop()
        if rc != mqtt.MQTT_ERR_SUCCESS:
            log.error("Client loop call after reconnect failed: {:}".format(mqtt.error_string(rc)))

    return client


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

    if not data:
        log.debug("Skipping empty data result")

        return

    namespace = list(args)
    if isinstance(data, dict):
        payload = data

        # Append type to namespace if present and not already added
        if "_type" in data and not data["_type"] in namespace:
            namespace.append(data["_type"])
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

    client = _get_client_for(kwargs)

    # Publish message
    topic = "/".join(namespace)
    res = client.publish(topic, json.dumps(payload, separators=(",", ":")))
    if res.rc != mqtt.MQTT_ERR_SUCCESS:
        log.warn("Publish of message with topic '{:}' failed: {:}".format(topic, mqtt.error_string(res.rc)))
