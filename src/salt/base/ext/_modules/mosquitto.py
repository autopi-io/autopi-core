import logging
import os

from messaging import extract_error_from


log = logging.getLogger(__name__)


LAST_ERROR_FILE = "/opt/autopi/.last_mosquitto_error"


def error_event_trigger(result):
    """
    Triggers 'system/mosquitto/error' events.
    """

    # Check for error result
    error = extract_error_from(result)
    if error:
        log.error("Error event trigger got an error result: {:}".format(result))

        return

    # Prepare old and new values
    old_value = ""
    new_value = "\n".join(result["values"]) if "values" in result else result.get("value", "unknown")

    # Load old value from file
    if os.path.exists(LAST_ERROR_FILE):
        with open(LAST_ERROR_FILE, "r") as file:
            old_value = file.read()

    # Trigger error event if changed
    if old_value != new_value:
        __salt__["minionutil.trigger_event"]("system/mosquitto/error", data={"message": new_value})

        with open("/opt/autopi/.last_mosquitto_error", "w") as file:
            file.write(new_value)
