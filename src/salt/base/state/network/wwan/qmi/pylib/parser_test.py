import json

import parser


nas_get_signal_strength = """[/dev/cdc-wdm0] Successfully got signal strength
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
    Network 'lte': '-96 dBm'"""

print "-------------------------------------------------------------------------------"
print nas_get_signal_strength
print "-------------------------------------------------------------------------------"
print json.dumps(parser.parse_signal_strength(nas_get_signal_strength, include_desc=True), indent=4)


nas_get_system_info = """[/dev/cdc-wdm0] Successfully got system info:
	GSM service:
		Status: 'none'
		True Status: 'none'
		Preferred data path: 'no'
	WCDMA service:
		Status: 'none'
		True Status: 'none'
		Preferred data path: 'no'
	LTE service:
		Status: 'available'
		True Status: 'available'
		Preferred data path: 'no'
		Domain: 'cs-ps'
		Service capability: 'cs-ps'
		Roaming status: 'on'
		Forbidden: 'no'
		Cell ID: '44678925'
		MCC: '238'
		MNC: '20'
		Tracking Area Code: '14011'
		Voice support: 'yes'
		eMBMS coverage info support: 'no'
	SIM reject info: 'available'"""

print "-------------------------------------------------------------------------------"
print nas_get_system_info
print "-------------------------------------------------------------------------------"
print json.dumps(parser.parse(nas_get_system_info, skip_first=1), indent=4)


nas_get_cell_location_info = """[/dev/cdc-wdm0] Successfully got cell location info
Intrafrequency LTE Info
	UE In Idle: 'yes'
	PLMN: '23820'
	Tracking Area Code: '14011'
	Global Cell ID: '44678925'
	EUTRA Absolute RF Channel Number: '500' (E-UTRA band 1: 2100)
	Serving Cell ID: '390'
	Cell Reselection Priority: '6'
	S Non Intra Search Threshold: '20'
	Serving Cell Low Threshold: '10'
	S Intra Search Threshold: '62'
	Cell [0]:
		Physical Cell ID: '390'
		RSRQ: '-7.2' dB
		RSRP: '-89.2' dBm
		RSSI: '-62.1' dBm
		Cell Selection RX Level: '40'
	Cell [1]:
		Physical Cell ID: '34'
		RSRQ: '-18.3' dB
		RSRP: '-102.3' dBm
		RSSI: '-75.1' dBm
		Cell Selection RX Level: '27'
Interfrequency LTE Info
	UE In Idle: 'yes'
	Frequency [0]:
		EUTRA Absolute RF Channel Number: '3150' (E-UTRA band 7: 2600)
		Selection RX Level Low Threshold: '0'
		Cell Selection RX Level High Threshold: '20'
		Cell Reselection Priority: '7'
	Frequency [1]:
		EUTRA Absolute RF Channel Number: '3348' (E-UTRA band 7: 2600)
		Selection RX Level Low Threshold: '0'
		Cell Selection RX Level High Threshold: '20'
		Cell Reselection Priority: '7'
		Cell [0]:
			Physical Cell ID: '227'
			RSRQ: '-11.3' dB
			RSRP: '-114.6' dBm
			RSSI: '-94.3' dBm
			Cell Selection RX Level: '15'
		Cell [1]:
			Physical Cell ID: '228'
			RSRQ: '-14.7' dB
			RSRP: '-122.9' dBm
			RSSI: '-98.6' dBm
			Cell Selection RX Level: '7'
		Cell [2]:
			Physical Cell ID: '226'
			RSRQ: '-18.7' dB
			RSRP: '-122.6' dBm
			RSSI: '-94.3' dBm
			Cell Selection RX Level: '7'
LTE Info Neighboring GSM
	UE In Idle: 'yes'
LTE Info Neighboring WCDMA
	UE In Idle: 'yes'
	Frequency [0]:
		UTRA Absolute RF Channel Number: '10738'
		Cell Reselection Priority: '3'
		Cell Reselection High Threshold: '4'
		Cell Reselection Low Threshold: '10'
	Frequency [1]:
		UTRA Absolute RF Channel Number: '10713'
		Cell Reselection Priority: '3'
		Cell Reselection High Threshold: '4'
		Cell Reselection Low Threshold: '10'"""

print "-------------------------------------------------------------------------------"
print nas_get_cell_location_info
print "-------------------------------------------------------------------------------"
print json.dumps(parser.parse(nas_get_cell_location_info, skip_first=1), indent=4)

