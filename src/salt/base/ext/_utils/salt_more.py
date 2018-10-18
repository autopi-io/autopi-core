import salt.exceptions


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
