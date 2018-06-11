import re


number_regex = re.compile("^'(?P<value>-?[0-9]\d*(?:\.\d+)?) (?P<unit>[a-zA-Z]+)'$")


def number_parser(str):
    match = number_regex.match(str)
    if not match:
        raise Exception("Unable to parse as number: {:s}".format(repr(str)))
    return match.groupdict()


def lines_parser(str):
    if isinstance(str, list):
        return str

    return str.split("\n")


def into_dict_parser(str, root={}, lines_parser=lines_parser, separator=":", value_parser=None):
    prev = None

    for line in lines_parser(str):
        kv = line.split(separator)
        key = kv[0].lower().replace(" ", "_")
        val = kv[1].strip()

        if not val:
            root[key] = {}
            prev = root[key]
        elif key.startswith("\t"):
            key = key.lstrip()
            prev[key] = value_parser(val) if value_parser else val
        else:
            root[key] = value_parser(val) if value_parser else val

    return root
