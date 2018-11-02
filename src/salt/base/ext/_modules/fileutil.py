import logging
import salt.exceptions
import salt.utils.event
import salt.utils.jid


log = logging.getLogger(__name__)


def remove_all(*paths):
    """
    Similar to 'file.remove' but with many at once.
    """

    ret = {}

    for path in paths:
        ret[path] = __salt__["file.remove"](path)

    return ret
