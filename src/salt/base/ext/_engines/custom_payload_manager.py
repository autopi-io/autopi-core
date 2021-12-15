import logging
import datetime
import os
import time
import json
from collections import OrderedDict

from common_util import factory_rendering
from messaging import EventDrivenMessageProcessor, extract_error_from

log = logging.getLogger(__name__)

context = {
    "settings": {},
    "events": []
}

edmp = EventDrivenMessageProcessor("custom_payload", context=context, default_hooks={"workflow": "extended"})

@edmp.register_hook(synchronize=False)
def generate_payload_handler():
    """
    Retrieves data from various modules and returns it.
    """

    dt = datetime.datetime.now()
    ts = int(time.mktime(dt.utctimetuple()) * 1000 + dt.microsecond / 1000)

    # Get OBD data

    # Get position
    position = __salt__["ec2x.gnss_location"]()
    latitude = position.get('lat', None)
    longitude = position.get('lon', None)
    altitude = position.get('alt', None)
    nsat = position.get('nsat', None)
    hdop = position.get('hdop', None)
    log.info('position: {}'.format(position))

    payload = OrderedDict({
        "ts": ts,

        "latitude": latitude,
        "longitude": longitude,
        "altitude": altitude,
        "nsat": nsat,
        "hdop": hdop,

        "wifi_networks": context.get("wifi_networks", []),
        "cell_details": context.get("cell_details", []),
        "events": context["events"],
    })

    # Clear events
    context["events"] = []

    ret = {}
    ret["value"] = payload

    log.info('Generated payload: {}'.format(json.dumps(ret)))

    return ret


@edmp.register_hook(synchronize=False)
def cache_events_handler(event):
    log.info('Received event: {}'.format(event))
    context["events"].append(event)

    # TODO: WIFI AND CELl INFO We might want a timestamp for when this info was retrieved, so that we can 
    # either expire the info or ignore it based on the ts.

@edmp.register_hook(synchronize=False)
def scan_wifi_handler():
    log.info('Scanning wifi networks.')
    networks = __salt__["wifi.scan"]()

    filtered_networks = [{ "name": network.get("name", None), "address": network.get("address", None), "quality": network.get('quality', None)} for network in networks]
    context["wifi_networks"] = filtered_networks

@edmp.register_hook(synchronize=False)
def retrieve_cell_info_handler():
    log.info('Reading cell tower details')
    cell_info = __salt__["qmi.cell_info"]()

    lte_info = cell_info.get('intrafrequency_lte_info', {})

    lte_obj = { 
        "plmn": lte_info.get('plmn', None),
        "global_cell_id": lte_info.get('global_cell_id', None),
    }

    index = 0
    while True:
        key = 'cell_[{}]'.format(index)
        cell_info_obj = lte_info.get(key, None)
        if not cell_info_obj:
            break

        lte_obj.update({ key: cell_info_obj })
        index += 1

    context["cell_details"] = lte_obj

# @edmp.register_hook(synchronize=False)
# def save_in_context_returner(key, networks):
#     context["wifi_networks"] = networks

@edmp.register_hook(synchronize=False)
def return_value_payload_converter(result):
    """
    Converts return payload to not be wrapped in return object.
    """
    return result.get("value", None)

@factory_rendering
def start(**settings):
    try:
        log.info("Starting custom payload manager")

        context["settings"] = settings

        # Init message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        
        # Run message processor
        edmp.run()
    
    except Exception:
        log.exception("Failed to start custom payload manager")
        raise

    finally:
        log.info("Stopping custom payload manager")


# Payload
# {
#     "ts": None,

#     # OBD maybe from loggers somehow? as different data is available from different cars
#     "engine_load": None,
#     "accelerator_pos_d": None,
#     "barometric_pressure": None,
#     "ambient_air_temp": None,
#     "rpm": None,
#     "throttle_actuator": None,
#     "intake_temp": None,
#     "fuel_level": None,
#     "speed": None,
#     "accelerator_pos_e": None,

#     # Location
#     "latitude": None, # gnss_location.lat
#     "longitude": None, # gnss_location.lon
#     "altitude": None, # gnss_location.alt

#     # Location certainty
#     "nsat": None, # gnss_location.nsat
#     "hdop": None, # gnss_location.hdop

#     # Events
#     "events": [], # insert in context["events"] using reactor

#     # Proximitry
#     "wifi_networks": [],
#     "ble_devices": [],
#     "cell_details": None,
# }