import datetime
import json
import logging
try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False

from salt.returners import get_returner_options


log = logging.getLogger(__name__)


__virtualname__ = "mqtt"


def __virtual__():
    if not HAS_MQTT:
        return False, "Could not import mqtt returner; " \
                      "paho mqtt client is not installed."

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
        "tls": "tls",
        "proxy": "proxy",
        "ws": "ws"
    }

    options = get_returner_options(
        __name__,
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
            protocol=getattr(mqtt, options["protocol"], mqtt.MQTTv311),
            transport=options["transport"])

        # Setup TLS if defined
        if options["tls"]:
            client.tls_set(**options["tls"])

        # Setup proxy if defined
        if options["proxy"]:
            client.proxy_set(**options["proxy"])

        # Setup WebSocket if defined
        if options["ws"]:
            client.ws_set(**options["ws"])

        client.connect(options["host"],
            port=options["port"],
            keepalive=options["keepalive"],
            bind_address=options["bind_address"])

        __context__[__name__] = client
    else:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Re-using client instance found in context")

        # TODO HN:
        #if not client.is_connected():
        #    log.warn("Existing client instance is no longer connected - attempting to reconnect")

        #    client.reconnect()

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
    res = client.publish("/".join(namespace), json.dumps(payload, separators=(",", ":")))

    # TODO HN:
    #if res.is_published():
    #    client.disconnect()

