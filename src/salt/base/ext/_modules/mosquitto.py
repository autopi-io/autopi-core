import logging

from messaging import extract_error_from


log = logging.getLogger(__name__)


def error_event_trigger(result):
    """
    Triggers 'system/mosquitto/error' events.
    """

    # Check for error result
    error = extract_error_from(result)
    if error:
        log.error("Error event trigger got an error result: {:}".format(result))

        return

    # Trigger error event
    __salt__["minionutil.trigger_event"]("system/mosquitto/error", data={"message": "\n".join(result["values"]) if "values" in result else result.get("value", "unknown")})
