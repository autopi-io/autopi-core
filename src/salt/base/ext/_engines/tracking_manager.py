import datetime
import logging
import pynmea2
import salt.loader
import yaml

from pygeodesy.sphericalNvector import LatLon
from math import radians, cos, sin, sqrt, atan2
from messaging import EventDrivenMessageProcessor, extract_error_from
from salt_more import SuperiorCommandExecutionError
from serial_conn import SerialConn
from threading_more import intercept_exit_signal


log = logging.getLogger(__name__)

context = {
    "position": {
        "state": None,  # Available states: unknown|standstill|moving
        "error": None,
        "last_recorded": None,
        "last_reported": None,
    },
    "geofence": {
        "error": None,
        "repeat_count_to_trigger_change": 3,
        "fences": []
    }
}

# Message processor
edmp = EventDrivenMessageProcessor("tracking", context=context, default_hooks={"workflow": "extended"})

# Serial connection
conn = SerialConn()

# Geofence object array
geofence_objects = []

@edmp.register_hook(synchronize=False)
def status_handler():
    """
    Gets current status.
    """

    ret = {
        "connection": {
            "open": conn.is_open()
        },
        "position": context["position"]
    }

    return ret


@edmp.register_hook()
def nmea0183_readout_handler():
    """
    Reads all available NMEA0183 sentences through serial connection.
    """

    ret = {}

    # Read lines from serial connection
    lines = conn.read_lines()
    if not lines:
        log.warn("No NMEA0183 sentences available")

        return ret

    # Parse NMEA sentences
    for line in lines:
        try:
            obj = pynmea2.parse(line, check=True)

            # Put into dict indexed by type
            name = obj.__class__.__name__.lower()
            if name in ret:
                if isinstance(ret[name], list):
                    ret[name].append(obj)
                else:
                    ret[name] = [ret[name], obj]
            else:
                ret[name] = obj

        except Exception:
            log.exception("Failed to parse NMEA0183 sentence: {:}".format(line))

    return ret


@edmp.register_hook()
def nmea0183_readout_to_position_converter(result):
    """
    Converts NMEA0183 sentences result into position type.
    """

    ret = {
        "_type": "pos",
        "_stamp": datetime.datetime.utcnow().isoformat(),
    }

    # Add general fix information
    if not "gga" in result:
        log.warn("No GGA sentence found in result")
    elif result["gga"].gps_qual > 0:
        ret["utc"] = result["gga"].timestamp.isoformat()
        ret["loc"] = {
            "lat": result["gga"].latitude,
            "lon": result["gga"].longitude,
        }
        ret["alt"] = float(result["gga"].altitude)
        ret["nsat"] = int(result["gga"].num_sats)

    # Add vector track data
    if "vtg" in result:
        ret["sog"] = result["vtg"].spd_over_grnd_kmph
        ret["cog"] = 0 #result["vtg"].  # TODO

    return ret


@edmp.register_hook()
def gnss_query_handler(cmd, *args, **kwargs):
    """
    Reads GNSS data and settings synchronously from EC2X module.
    """

    try:
        return __salt__["ec2x.gnss_{:s}".format(cmd)](*args, **kwargs)
    except SuperiorCommandExecutionError as scee:
        if scee.data.get("type", None) == "CME" and \
            scee.data.get("reason", None) in ["516", "Not fixed now"]:

            raise Warning("no_fix")
        else:
            raise


@edmp.register_hook()
def gnss_location_to_position_converter(result):
    """
    Converts a GNSS location result into position type.
    """

    ret = {
        "_type": "pos",
        "_stamp": result["_stamp"],
        "utc": result["time_utc"],
        "loc": {
            "lat": result["lat"],
            "lon": result["lon"]
        },
        "alt": result["alt"],
        "sog": result["sog_km"],
        "cog": result["cog"],
        "nsat": result["nsat"],
    }

    return ret


@edmp.register_hook(synchronize=False)
def position_event_trigger(result):
    """
    Listens for position results and triggers position unknown/standstill/moving events.
    """

    # Check for error result
    error = extract_error_from(result)
    if log.isEnabledFor(logging.DEBUG) and error:
        log.debug("Position event trigger is unable to determine GNSS location: {:}".format(error))

    ctx = context["position"]

    old_state = ctx["state"]
    new_state = None

    old_error = ctx["error"]
    new_error = None

    # Determine new state
    if error:
        new_state = "unknown"
        new_error = str(error)
    elif result.get("sog", 0) > 0:
        new_state = "moving"
    else:
        new_state = "standstill"

    # Check if state has chaged since last known state
    if old_state != new_state or old_error != new_error:
        ctx["state"] = new_state
        ctx["error"] = new_error

        # Trigger event
        edmp.trigger_event(
            {"reason": ctx["error"]} if ctx["error"] else {},
            "vehicle/position/{:s}".format(ctx["state"]))


@edmp.register_hook(synchronize=False)
def significant_position_filter(result):
    """
    Filter that only returns significant non duplicated positions.
    """

    ctx = context["position"]

    old_pos = ctx["last_reported"]
    new_pos = result

    # Update context with newly recorded position
    ctx["last_recorded"] = new_pos

    # Check whether or not position has changed since last reported
    if old_pos != None:

        # If moving check if direction/speed vector has changed
        if new_pos.get("sog", 0) > 0 and old_pos.get("sog", 0) == new_pos.get("sog", 0) and old_pos.get("cog", 0) == new_pos.get("cog", 0):
            return
        # Or when standing still check if location has changed
        # TODO: Compare with allowed deviation using: pip install geopy
        elif old_pos["loc"]["lat"] == new_pos["loc"]["lat"] and old_pos["loc"]["lon"] == new_pos["loc"]["lon"]:
            return

    # Update context with last reported position
    ctx["last_reported"] = new_pos

    return new_pos

class Geofence:    
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.repeat_count = 0
        self.last_recorded = None
        self.state = None

    def is_inside(self, coords):
        pass

    def reset_count(self):
        self.repeat_count = 0

    def increment_count(self):
        self.repeat_count += 1

    def set_state(self, new_state):
        self.state = new_state

    def set_last_recorded(self, reading):
        self.last_recorded = reading

class GeofencePolygon(Geofence):
    # corner_coords: [(lat, lon, seq)]
    def __init__(self, id, name, corner_coords):
        Geofence.__init__(self, id, name)
        
        def sortKey(point):
            return point["seq"] 
        corner_coords.sort(key=sortKey)

        self.corner_coords = [LatLon(corner["lat"], corner["lon"]) for corner in corner_coords]
        
    def is_inside(self, coords):
        locCoord = LatLon(*coords)
        return locCoord.isenclosedBy(self.corner_coords)

class GeofenceCircle(Geofence):
    def __init__(self, id, name, center_coords, radius):
        Geofence.__init__(self, id, name)
        self.center_coords = (center_coords["lat"], center_coords["lon"])
        self.radius = radius

    @staticmethod
    def get_distance(point1, point2):
        R = 6373.0

        lat1 = radians(point1[0])
        lon1 = radians(point1[1])
        lat2 = radians(point2[0])
        lon2 = radians(point2[1])

        dlon = lon2 - lon1
        dlat = lat2 - lat1

        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        distance = R * c

        return distance

    @staticmethod
    def is_in_circle(vehiclePosition, circleCenter, cirlceRadius):
        dist = GeofenceCircle.get_distance((vehiclePosition[0], vehiclePosition[1]), (circleCenter[0], circleCenter[1]))
        return dist <= cirlceRadius

    def is_inside(self, coords):
        dist = GeofenceCircle.get_distance(coords, self.center_coords)
        return dist <= self.radius

def update_geofence_context(fence_objects):
    fence_dict = []
    for fence in fence_objects:
        fence_dict.append({
            "id": fence.id,
            "name": fence.name,
            "state": fence.state
        })
    context["geofence"]["fences"] = fence_dict

def init_geofence_objects():

    log.info("Initializing geofence objects")
    
    try:
        file = open("/etc/salt/minion.d/geofences.yaml", "r")
        fences_dict = yaml.load(file)
        file.close()

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Creating fences from: {}".format(fences_dict))
       
        # Create objects for all geofences and store in global array
        for fence in fences_dict:
            if fence["shape"] == "SHAPE_POLYGON":
                geofence_objects.append(
                    GeofencePolygon(
                        id=fence["id"],
                        name=fence["name"],
                        corner_coords=fence["polygon_corners"]
                ))

            elif fence["shape"] == "SHAPE_CIRCLE":
                geofence_objects.append(
                    GeofenceCircle(
                        id=fence["id"],
                        name=fence["name"],
                        center_coords=fence["circle_center"],
                        radius=fence["circle_radius"]
                ))

            else:
                log.warn("Invalid geofence shape of '{}' for fence '{}'".format(fence["shape"], fence["name"]))
    
    except Exception as err:
        log.warn("Failed while initializing geofence objects: {}".format(err))
        return

    update_geofence_context(geofence_objects)
            

@edmp.register_hook(synchronize=False)
def geofence_event_trigger(result):
    """
    Listens for position results and triggers geofence inside/outside events
    """

    if log.isEnabledFor(logging.DEBUG):
        log.debug("Checking all geofences")

    if isinstance(result, Exception):
        log.warn("No data from GPS, can not determine geofence status. Exception: {}".format(result))
        return

    updated = False
    ctx = context["geofence"]
    current_location_coords = (result["loc"]["lat"], result["loc"]["lon"])

    # Check if the device is within a geofence
    for fence in geofence_objects:

        if log.isEnabledFor(logging.DEBUG):
            log.debug("Checking geofence {} ({})".format(fence.id, fence.name))

        new_state = "outside"

        # Check if vehicle is inside the geofence
        if fence.is_inside(current_location_coords):
            new_state = "inside"

        # Update repeat counter
        if fence.last_recorded == new_state:
            fence.increment_count()
        else:
            fence.reset_count()

        # Check if fence's state needs to be updated and event triggered 
        if fence.repeat_count >= ctx["repeat_count_to_trigger_change"] and fence.state != new_state:
            fence.set_state(new_state)
            updated = True

            edmp.trigger_event(
                {"reason": ctx["error"], "fence": fence.id} if ctx["error"] else {"fence": fence.id},
                "vehicle/geofence/{:s}".format(fence.state))

        # prepare fence for next check
        fence.set_last_recorded(new_state)

    # if change happended, update the context
    if updated:
        update_geofence_context(geofence_objects)    

@intercept_exit_signal
def start(**settings):
    try:
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting tracking manager with settings: {:}".format(settings))

        # Initialize serial connection
        conn.init(settings["serial_conn"])

        # Initialize geofence objects
        init_geofence_objects()

        # Initialize and run message processor
        edmp.init(__salt__, __opts__,
            hooks=settings.get("hooks", []),
            workers=settings.get("workers", []),
            reactors=settings.get("reactors", []))
        edmp.run()

    except Exception:
        log.exception("Failed to start tracking manager")
        
        raise

    finally:
        log.info("Stopping tracking manager")

        if conn.is_open():
            try:
                conn.close()
            except:
                log.exception("Failed to close serial connection")
