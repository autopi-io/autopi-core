

def dict_find(dic, *args, default=None):
    ret = dic

    for arg in args:
        if not arg in ret:
            return default

        ret = ret[arg]

    return ret


def dict_filter(items, key_func=None):
    ret = {}

    for key, val in items.iteritems():
        if key_func == None or key_func(key):
            if isinstance(val, dict):
                ret[key] = _filter_dict(val, key_func=key_func)
            else:
                ret[key] = val

    return ret