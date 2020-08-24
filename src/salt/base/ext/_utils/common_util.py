import datetime
import importlib
import logging
import logging.handlers
import os
import re


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


def dict_find(dic, path, regex, default=None):
    ret = default

    p = path.split(":")
    for d in dic if isinstance(dic, list) else [dic]:
        res = dict_get(d, *p)
        if res == None:
            continue

        if re.match(regex, res):
            ret = d

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


def load_func(qname):
    mod_name, func_name = qname.rsplit(".", 1)
    mod = importlib.import_module(mod_name)
    func = getattr(mod, func_name)

    return func


def fromisoformat(date_string):
    """
    Inspired by: https://docs.python.org/3/library/datetime.html#datetime.date.fromisoformat
    """

    try:
        return datetime.datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        return datetime.datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S")


def factory_rendering(func):
    def decorator(*args, **kwargs):
        if "_factory" in kwargs:
            args, kwargs = load_func(kwargs.pop("_factory"))(*kwargs.pop("args", args), **kwargs.pop("kwargs", kwargs))

        return func(*args, **kwargs)

    return decorator


def add_rotating_file_handler_to(
    logger,
    file,
    level=logging.INFO,
    max_size=10000000,
    backup_count=3,
    format="%(asctime)s [%(levelname)s] %(message)s"):

    handler = logging.handlers.RotatingFileHandler(file, maxBytes=max_size, backupCount=backup_count)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(format))

    logger.addHandler(handler)
    logger.setLevel(level)

