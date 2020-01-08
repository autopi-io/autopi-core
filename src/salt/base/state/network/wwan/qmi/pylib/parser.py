import re
import signal_rater


def parse(string):
    ret = {}

    prev = None
    for line in string.split("\n"):

        kv = line.split(":")
        if len(kv) != 2:
            continue

        key = kv[0].lower().replace(" ", "_")
        val = kv[1].strip().strip("'")
        if not val:
            ret[key] = {}
            prev = ret[key]
        elif key.startswith("\t"):
            key = key.lstrip()
            prev[key] = val
        else:
            ret[key] = val

    return ret


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
            ret[key]["rating"] = {
                "value": rating,
                "text": signal_rater.ratings.get(rating, "unknown"),
            }

    return ret
