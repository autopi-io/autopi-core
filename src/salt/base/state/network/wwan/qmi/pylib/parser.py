import collections
import re
import signal_rater


def parse(string, skip_first=0):
    ret = collections.OrderedDict()

    # Keep an index with parents by level
    parents = {}
    for lvl in range(0, skip_first + 1):
        parents[lvl] = ret

    lines = iter(string.split("\n")[skip_first:])
    line = next(lines, None)
    while line != None:
        kv = line.split(":", 1)

        # Prepare next line
        line = next(lines, None)

        # Parse current line
        level = kv[0].count("\t")
        key = kv[0].lower().replace(" ", "_").lstrip()
        if not key:
            continue

        val = kv[1].strip().replace("'", "") if len(kv) > 1 else None
        if not val:
            val = collections.OrderedDict()
        else:

            # Kind of hack fix: Check if next line is a child of current
            if line and level < line.count("\t"):

                # Override value with dictionary
                val = collections.OrderedDict()
            else:
                val = int(val) if val.isdigit() else val

        # Add value to parent
        parents[level][key] = val

        # Update parents by level index
        parents[level + 1] = val

    return ret


signal_strength_regex = re.compile(r"(?P<key>\w+)(?: \(\w+\))?:(?:\s+Network '(?P<net>\w+)':)? '(?P<val>-?[0-9]*\.?[0-9]*) (?P<unit>\w+)'", re.MULTILINE)


def parse_signal_strength(string, skip_unrated=False, include_desc=False):
    ret = collections.OrderedDict()
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

        if include_desc and key in signal_rater.rating_descs:
            ret[key]["desc"] = signal_rater.rating_descs[key]

    return ret
