import logging

import salt_more

log = logging.getLogger(__name__)


def call_error_safe(func, *args, **kwargs):
    """
    Calls a salt module function safely - if an error occurs it will be added as an error in the response.
    """

    ret = {}

    try:
        callable_function = func if callable(func) else __salt__[func]
        ret = salt_more.call_error_safe(callable_function, *args, **kwargs)

    except Exception as ex:
        log.exception(ex)
        ret["error"] = repr(ex)

    return ret
