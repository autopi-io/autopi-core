import logging


log = logging.getLogger(__name__)


def dict_find(dic, *args, **kwargs):
    ret = dic

    for arg in args:
        if not arg in ret:
            return kwargs.get("default", None)

        ret = ret[arg]

    return ret


def dict_filter(items, key_func=None):
    ret = {}

    for key, val in items.iteritems():
        if key_func == None or key_func(key):
            if isinstance(val, dict):
                ret[key] = dict_filter(val, key_func=key_func)
            else:
                ret[key] = val

    return ret
