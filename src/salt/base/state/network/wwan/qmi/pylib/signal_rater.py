
ratings = {
    0:   "none",
    1:   "poor",
    2:   "fair",
    3:   "good",
    4:   "excellent",
}

rating_descs = {
    "rssi": "Received Signal Strength Indicator (3G, CDMA/UMTS/EV-DO)",
    "ecio": "Energy to Interference Ratio (3G, CDMA/UMTS/EV-DO)",
    "rsrp": "Reference Signal Received Power (4G LTE)",
    "rsrq": "Reference Signal Received Quality (4G LTE)",
    "sinr": "Signal to Interference-plus-Noise Ratio (4G LTE)",
}


def rate(kind, value, unit):
    if kind in rating_funcs:
        return rating_funcs[kind](value, unit)
        
    return None


def rssi_strength_rating(value, unit):
    """
    RSSI - Received Signal Strength Indicator (3G, CDMA/UMTS/EV-DO)
    """

    if unit != "dBm":
        raise ValueError("Unsupported unit '{:}'".format(unit))

    rating = 0
    if value > -65:
        rating = 4
    elif -65 >= value > -75:
        rating = 3
    elif -75 >= value > -85:
        rating = 2
    elif value <= -85:
        rating = 1

    return rating


def ecio_quality_rating(value, unit):
    """
    ECIO (Ec/Io) - Energy to Interference Ratio (3G, CDMA/UMTS/EV-DO)
    """

    if unit != "dBm":
        raise ValueError("Unsupported unit '{:}'".format(unit))

    rating = 0
    if value > -2:
        rating = 4
    elif -2 >= value > -5:
        rating = 3
    elif -5 >= value > -10:
        rating = 2
    elif value <= -10:
        rating = 1

    return rating


def rsrp_strength_rating(value, unit):
    """
    Reference Signal Received Power (4G LTE)
    """

    if unit != "dBm":
        raise ValueError("Unsupported unit '{:}'".format(unit))

    rating = 0
    if value > -80:
        rating = 4
    elif -80 >= value > -90:
        rating = 3
    elif -90 >= value > -101:
        rating = 2
    elif value <= -101:
        rating = 1

    return rating


def rsrq_quality_rating(value, unit):
    """
    RSRQ - Reference Signal Received Quality (4G LTE)
    """

    if unit != "dB":
        raise ValueError("Unsupported unit '{:}'".format(unit))

    rating = 0
    if value > -6:
        rating = 4
    elif -6 >= value > -9:
        rating = 3
    elif -9 >= value > -16:
        rating = 2
    elif value <= -16:
        rating = 1

    return rating


def sinr_throughput_rating(value, unit):
    """
    SINR - Signal to Interference-plus-Noise Ratio (4G LTE)
    """

    if unit != "dB":
        raise ValueError("Unsupported unit '{:}'".format(unit))

    rating = 0
    if value >= 10:
        rating = 4
    elif 10 > value >= 6:
        rating = 3
    elif 6 > value >= 0:
        rating = 2
    elif value < 0:
        rating = 1

    return rating


rating_funcs = {
    "rssi": rssi_strength_rating,
    "ecio": ecio_quality_rating,
    "rsrp": rsrp_strength_rating,
    "rsrq": rsrq_quality_rating,
    "sinr": sinr_throughput_rating,
}
