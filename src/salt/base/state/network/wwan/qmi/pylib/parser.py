import re

from . import signal_rater


signal_strength_regex = re.compile(r"(?P<key>\w+)(?: \(\w+\))?:(?:\s+Network '(?P<net>\w+)':)? '(?P<val>-?[0-9]*\.?[0-9]*) (?P<unit>\w+)'", re.MULTILINE)


def parse_signal_strength(string, skip_unrated=False):
    ret = {}
    for match in signal_strength_regex.finditer(string):
        groups = match.groupdict()

        key = groups["key"].lower()
        val = float(groups["val"])

        rating = signal_rater.rate(key, val, groups["unit"])
        if skip_unrated and rating == None:
            continue

        ret[key] = {
            "value": val,
            "unit": groups["unit"],
            "network": groups["net"],
        }

        if rating != None:
            ret[key]["rating"] = rating

    return ret
