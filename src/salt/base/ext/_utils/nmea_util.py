import datetime
import pynmea2


def parse_as_dict(sentence, check=True, verbose=False):
    ret = {}

    if verbose:
        ret["sentence"] = sentence

    obj = pynmea2.parse(sentence, check=True)
    ret["data_type"] = obj.__class__.__name__

    for f in obj.fields:
        desc = f[0]
        attr = f[1]
        val = getattr(obj, attr)

        if not val and not verbose:
            continue

        # Workaround because msgpack will not serialize datetime.date, datetime.time and decimal.Decimal
        if isinstance(val, datetime.date):
            val = str(val)
        elif isinstance(val, datetime.time):
            val = str(val)
        elif isinstance(val, decimal.Decimal):
            val = float(val)
        # TODO: Temp fix to get correct types because pynmea2 does not handle it
        elif attr.startswith("num_") or attr.endswith("_num") or "_num_" in attr:
            val = int(val)
        elif attr.startswith("snr_") or attr.startswith("azimuth_"):
            val = float(val)

        ret[attr] = val if not verbose else {
            "description": desc,
            "value": val
        }

    return ret