from .parser import *



#Mode preference: gsm, umts, lte
#Service preference: wcdma

def network_summary():
    ret = {
        "operator": "",
        "services": {
            "available": [],
            "selected": ""
        }
    }

#
# Network Access Service
#

def network_operator_name():
    pass

    #qmicli --device-open-$MODE --device $DEVICE --nas-get-operator-name

def network_system_info():
    pass

    # --nas-get-system-info

def network_services():
    pass

    res = system_info()
    #GSM service:\nStatus: 'available'
    #WCDMA service:\nStatus: 'available'
    #LTE service:\nStatus: 'available'

def network_serving_system():
    pass

    # Get selected network
    #--nas-get-serving-system
    # Selected network: '3gpp'

def network_signal(rated_only=False):
    """
    Current signal strength values.
    """

    out = _run("nas-get-signal-strength")
    ret = parse_signal_strength(out, skip_unrated=rated_only)

    return ret


#
# Wireless Data Service
#

def connection_status():
    pass
    #--wds-get-packet-service-status

def connection_stats():
    pass
    #--wds-get-packet-statistics