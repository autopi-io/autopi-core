import logging
import os


log = logging.getLogger(__name__)


def dict_get(dic, *args, **kwargs):
    if not isinstance(dic, dict):
        return kwargs.get("default", None)

    ret = dic

    for arg in args:
        if not arg in ret:
            return kwargs.get("default", None)

        ret = ret[arg]

    return ret


def dict_find(dic, path, value, default=None)
    ret = default

    p = path.split(":")
    for d in dic if isinstance(dic, list) else [dic]:
        res = dict_get(d, *p)

        if res != None and res == value:
            ret = res

            break

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


def dict_key_by_value(dic, val):
    kv = { k: v for k, v in dic.items() if v == val }
    if not kv:
        raise ValueError("Value {:} is not available - valid options are: {:}".format(val, ", ".join(str(v) for v in dic.values())))

    return next(iter(kv))


def abs_file_path(name, fallback_folder, ext=None):
        ret = name if os.path.isabs(name) else os.path.join(fallback_folder, name)
        if ext and not ret.endswith(".{:}".format(ext)):
            ret += ".{:}".format(ext)

        return ret
