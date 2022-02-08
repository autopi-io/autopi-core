import yaml
import logging

from pygeodesy.sphericalNvector import LatLon
from math import radians, cos, sin, sqrt, atan2

log = logging.getLogger(__name__)


def get_distance_between_points(point1, point2):
    """
    Returns the geographical distance in km between 2 coordinates formatted as ("lat": lat, "lon": lon)
    """
    # Thanks, https://stackoverflow.com/a/19412565

    R = 6373.0

    lat1 = radians(point1["lat"])
    lon1 = radians(point1["lon"])
    lat2 = radians(point2["lat"])
    lon2 = radians(point2["lon"])

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance = R * c

    return distance


def is_in_circle(location, circle_center, circle_radius):
    """
    Returns true if location is within radius in km of the circle center
    """
    dist = get_distance_between_points(location, circle_center)
    return dist <= circle_radius


def is_in_polygon(location, polygon_corners):
    """
    Returns true if location is within the specified polygon
    """
    location_latlon = LatLon(location["lat"], location["lon"])  # TODO EP: LatLon is instantiated each time - can this be cached? If so, this function is kind of redundant.
    return location_latlon.isenclosedBy(polygon_corners)


def read_geofence_file(file_path):
    """
    Reads the specified yaml file containing geofences, adds fields necessary for state tracking
    """

    log.info("Reading geofences file {}".format(file_path))
    
    ret_arr = []

    # Try to read and parse the geofence file
    try:
        file = open(file_path, "r")
        fence_file_dict = yaml.load(file)
        file.close()  # TODO EP: A little nicer to use Python's 'with' statement

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Creating fences from: {}".format(fence_file_dict))

        # Verify and add state, last_readiang, repeat_count fields used by tracking manager
        for fence in fence_file_dict:
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Read fence {} ({})".format(fence["id"], fence["name"]))

            if fence["shape"] == "SHAPE_POLYGON" or fence["shape"] == "SHAPE_CIRCLE":    
                fence["state"] = None
                fence["last_reading"] = None
                fence["repeat_count"] = 0

                if fence["shape"] == "SHAPE_POLYGON":
                    fence["coordinates"] = [LatLon(corner["lat"], corner["lon"]) for corner in fence["coordinates"]]

                ret_arr.append(fence)

            else:
                log.warn("Invalid geofence shape of '{}' for fence '{}'".format(fence["shape"], fence["name"]))

    except Exception as err:
        log.warn("Failed while reading geofences file: {}".format(err))
        raise err

    return ret_arr