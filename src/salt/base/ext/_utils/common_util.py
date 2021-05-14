import datetime
import errno
import importlib
import json
import logging
import logging.handlers
import os
import re

from timeit import default_timer as timer


log = logging.getLogger(__name__)


def makedirs(path, exist_ok=False):
    try:
        os.makedirs(path)
    except OSError as e:
        if exist_ok and e.errno == errno.EEXIST:
            pass
        else:
            raise


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


def ensure_primitive(val):
    if isinstance(val, (int, float, bool, str)):
        return val
    elif isinstance(val, dict):
        return {ensure_primitive(k): ensure_primitive(v) for k, v in val.iteritems()}
    elif isinstance(val, (list, set, tuple)):
        return [ensure_primitive(v) for v in val]
    else:
        return str(val)

    return ret


def last_iter(it):

    # Ensure it's an iterator and get the first field
    it = iter(it)
    prev = next(it)
    for item in it:

        # Lag by one item so I know I'm not at the end
        yield 0, prev
        prev = item
        
    # Last item
    yield 1, prev


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


def jsonl_dumps(objs, separators=(",", ":"), **kwargs):
    ret = ""

    encoder = json.JSONEncoder(separators=separators, **kwargs)
    for obj in objs:
        ret += encoder.encode(obj) + "\n"

    return ret


def jsonl_dump(objs, fp, **kwargs):
    fp.write(jsonl_dumps(objs, **kwargs))


class RotatingTextFile(object):

    def __init__(self, open_func):
        self.max_size = 0
        self.expiration_time = 0

        self._open_func = open_func
        self._file = None
        self._size = 0

    def __str__(self):
        return "<{:}.{:} file={:} at {:}>".format(
            self.__class__.__module__,
            self.__class__.__name__,
            self._file,
            hex(id(self))
        )

    @property
    def name(self):
        if self._file:
            return self._file.name

        return None

    @property
    def closed(self):
        if self._file != None:
            return self._file.closed

        # Not considered closed when file has not yet been opened
        return False

    @property
    def size(self):
        return self._size

    def close(self):
        if self._file != None:
            self._file.close()

    def rotate(self):

        # First close any existing file
        self.close()

        # Open new file
        self._file = self._open_func(self)

        # Get initial size
        self._size = os.path.getsize(self._file.name)

    def write(self, line):

        if self._file == None:
            self.rotate()
        elif self.max_size and self.max_size <= self._size:
            log.info("Rotating {:} due to max size reached ({:}/{:})".format(self._file, self._size, self.max_size))

            self.rotate()
        elif self.expiration_time and self.expiration_time <= timer():
            log.info("Rotating {:} due to expiration time reached ({:}/{:})".format(self._file, timer(), self.expiration_time))

            self.rotate()

        # Perform write
        ret = self._file.write(line)

        self._size += len(line)

        return ret
