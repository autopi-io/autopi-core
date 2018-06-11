import json

import parser


s = """
[/dev/cdc-wdm0] Successfully got signal strength
Current:
    Network 'lte': '-64 dBm'
RSSI:
    Network 'lte': '-64 dBm'
ECIO:
    Network 'lte': '-2.5 dBm'
IO: '-106 dBm'
SINR (8): '9.0 dB'
RSRQ:
    Network 'lte': '-9 dB'
SNR:
    Network 'lte': '19.2 dB'
RSRP:
    Network 'lte': '-96 dBm'
"""
r = parser.parse_signal_strength(s)
print json.dumps(r, indent=4)
