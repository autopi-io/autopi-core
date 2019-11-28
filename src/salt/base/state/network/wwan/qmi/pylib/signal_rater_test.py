from .signal_rater import rate


# High rating mean good signal quality

# RSSI

assert rate("rssi",   0.0, "dBm") == 4
assert rate("rssi", -64.9, "dBm") == 4

assert rate("rssi", -65.0, "dBm") == 3
assert rate("rssi", -74.9, "dBm") == 3

assert rate("rssi", -75.0, "dBm") == 2
assert rate("rssi", -84.9, "dBm") == 2

assert rate("rssi", -85.0, "dBm") == 1
assert rate("rssi", -99.9, "dBm") == 1


# ECIO

assert rate("ecio",   0.0, "dBm") == 4
assert rate("ecio",  -1.9, "dBm") == 4

assert rate("ecio",  -2.0, "dBm") == 3
assert rate("ecio",  -4.9, "dBm") == 3

assert rate("ecio",  -5.0, "dBm") == 2
assert rate("ecio",  -9.9, "dBm") == 2

assert rate("ecio", -10.0, "dBm") == 1
assert rate("ecio", -99.9, "dBm") == 1


# RSRP

assert rate("rsrp",    0.0, "dBm") == 4
assert rate("rsrp",  -79.9, "dBm") == 4

assert rate("rsrp",  -80.0, "dBm") == 3
assert rate("rsrp",  -89.9, "dBm") == 3

assert rate("rsrp",  -90.0, "dBm") == 2
assert rate("rsrp", -100.9, "dBm") == 2

assert rate("rsrp", -101.0, "dBm") == 1
assert rate("rsrp", -999.9, "dBm") == 1


# RSRQ
assert rate("rsrq",   0.0, "dB") == 4
assert rate("rsrq",  -5.9, "dB") == 4

assert rate("rsrq",  -6.0, "dB") == 3
assert rate("rsrq",  -8.9, "dB") == 3

assert rate("rsrq",  -9.0, "dB") == 2
assert rate("rsrq", -15.9, "dB") == 2

assert rate("rsrq", -16.0, "dB") == 1
assert rate("rsrq", -99.0, "dB") == 1


# SINR
assert rate("sinr", 99.9, "dB") == 4
assert rate("sinr", 10.0, "dB") == 4

assert rate("sinr",  9.9, "dB") == 3
assert rate("sinr",  6.0, "dB") == 3

assert rate("sinr",  5.9, "dB") == 2
assert rate("sinr",  0.0, "dB") == 2

assert rate("sinr", -0.1, "dB") == 1
assert rate("sinr", -9.9, "dB") == 1