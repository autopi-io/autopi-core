import logging

import salt.exceptions
import salt.loader


log = logging.getLogger(__name__)


class SuperiorCommandExecutionError(salt.exceptions.CommandExecutionError):

    def __init__(self, *args, **kwargs):
        self.data = kwargs.pop("data", {})
        super(salt.exceptions.CommandExecutionError, self).__init__(*args, **kwargs)


def clean_kwargs(kwargs):
    """
    Filter out funny Salt params (__pub_*).
    """

    return {k: v for k, v in kwargs.iteritems() if not k.startswith("__")}


def call_error_safe(module_func, *args, **kwargs):
    """
    """

    ret = {}

    try:
        res = module_func(*args, **kwargs)
        ret.update(res)
    except Exception as ex:
        ret["error"] = ex

    return ret


def cached_loader(__salt__, __opts__, kind, **kwargs):
    """
    """

    loaders = globals().setdefault("__cached_loaders__", {})

    ret = loaders.get(kind, None)
    if ret == None:

        # Get loader
        if kind == "modules":
            ret = salt.loader.minion_mods(__opts__, **kwargs)
        elif kind == "returners":
            ret = salt.loader.returners(__opts__, __salt__, **kwargs)
        else:
            raise ValueError("Unsupported kind '{:}' - supported kinds are: 'modules', 'returners'".format(kind))

        # Cache it
        loaders[kind] = ret

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Loaded '{:}' into cache".format(kind))

    if "context" in kwargs and kwargs["context"] != ret.pack["__context__"]:
        raise ValueError("Cached loader context mismatch")

    return ret
