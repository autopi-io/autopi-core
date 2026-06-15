import os
import logging
from binascii import unhexlify
from datetime import datetime
import json

HOME_DIR = "/opt/autopi/can"

log = logging.getLogger(__name__)
DEBUG = log.isEnabledFor(logging.DEBUG)

DEFAULT_MASK = 0xFFFFFFFF
MASK_ALL_11BIT = 0x7FF
MASK_ALL_29BIT = 0x1FFFFFFF

# Loaded CAN databases indexed by procotol ID
can_db_cache = {}

class CanDB(object):

    def __init__(self, cantools_db):
        self._cantools_db = cantools_db
        self._filters = None
    
    def get_length_seperated_frame_ids(self):
        can_msgs = self._cantools_db.messages
        
        frame_ids_11bit = [msg.frame_id for msg in can_msgs if not msg.is_extended_frame]
        frame_ids_29bit = [msg.frame_id for msg in can_msgs if msg.is_extended_frame]
                
        return frame_ids_11bit, frame_ids_29bit

    def get_filters(self):
        if self._filters == None:
            ret = []
            
            mask = self._cantools_db._frame_id_mask
            
            frame_ids_11bit, frame_ids_29bit = self.get_length_seperated_frame_ids()
            
            frame_ids_11bit = set([frame_id & mask for frame_id in frame_ids_11bit])
            frame_ids_29bit = set([frame_id & mask for frame_id in frame_ids_29bit])
            
            # The default mask that cantools uses is not compatible with the
            #   can_conn filtering
            if mask == DEFAULT_MASK:
                mask_11bit = MASK_ALL_11BIT
                mask_29bit = MASK_ALL_29BIT
            else:
                mask_11bit = mask
                mask_29bit = mask
            
            # Create filter per masked frame id
            for frame_id in frame_ids_11bit:
                ret.append(dict(
                        id=frame_id, 
                        is_ext_id=False, 
                        mask=mask_11bit))
            for frame_id in frame_ids_29bit:
                ret.append(dict(
                        id=frame_id, 
                        is_ext_id=True, 
                        mask=mask_29bit))

            if not ret:
                log.warning("No filters to sync found in CAN DB")

            self._filters = ret
        return self._filters

    def decode(self, msg_dict, flatten=False):
        return decode_can_frame_for(self._cantools_db, msg_dict, flatten)


def can_db_from_file(dbc_path, conf={}, cache=False):
    """
    Helper function to find cached CAN database instance or load it from file.
    
    Accepts either absolute path or relative to /opt/autopi/can/db/
    """
    ret = None
    
    if not os.path.isabs(dbc_path):
        dbc_path = os.path.join(HOME_DIR, "db", dbc_path)
    
    # Ensure that a dbc file can have multiple cached DBs, based on config
    if cache:
        conf_hash = hash(json.dumps(conf, sort_keys=True))
        ret = can_db_cache.get(dbc_path, {}).get(conf_hash)
    
    if not ret:
        import cantools

        # Check for override (prefixed with underscore)
        if not os.path.isfile(dbc_path):
            raise Exception('Specified file "{}" does not exist'.format(dbc_path))

        # Load file
        log.info("Loading CAN database from file '{:}' with configuration: {:}".format(dbc_path, conf))
        can_db = cantools.db.load_file(dbc_path, **conf)
        ret = CanDB(can_db)

        # Put into cache
        if cache:
            file_cache = can_db_cache.setdefault(dbc_path, {})
            file_cache[conf_hash] = ret

    return ret


def can_db_for(protocol_id, conf):
    """
    Helper function to find cached CAN database instance or load it from file.
    The CAN database file (.dbc) is found on the local file system by the following path expression:

        /opt/autopi/obd/can/db/protocol_<protocol_id>.dbc
    """

    ret = can_db_cache.get(protocol_id, None)
    if not ret:
        import cantools

        # Check for override (prefixed with underscore)
        path = os.path.join(HOME_DIR, "db", "_protocol_{:}.dbc".format(protocol_id))
        if os.path.isfile(path):
            log.warning("Using overridden CAN database file '{:}'".format(path))
        else:
            path = os.path.join(HOME_DIR, "db", "protocol_{:}.dbc".format(protocol_id))

        # Load file
        ret = cantools.db.load_file(path, **conf)
        log.info("Loaded CAN database from file '{:}' with configuration: {:}".format(path, conf))

        # Put into cache
        can_db_cache[protocol_id] = ret

    return ret

def get_isotime_timestamp_from_msg(msg_dict):
    # Prefer an isotime timestamp from the dictionary
    timestamp = msg_dict.get("_stamp", None)
    if timestamp != None:
        return timestamp
    
    # Otherwise use ts (unix time)
    timestamp = msg_dict.get("ts", None)
    if timestamp != None:
        return datetime.fromtimestamp(timestamp).isoformat()
        
    # Otherwise make a new one
    return datetime.utcnow().isoformat()
    

def decode_can_frame_for(can_db, msg_dict, flatten=False):
    """
    Helper function to decode a raw CAN frame result.
    Note that one single CAN frame can output multiple results.
    """

    ret = []
    
    msg_id = msg_dict["id"]
    data = msg_dict["data"]
    
    # Find message by decimal value of header
    try:
        msg = can_db.get_message_by_frame_id(msg_id)
    except KeyError:  # Unknown message
        if DEBUG:
            log.debug("No CAN message found by ID {:}".format(msg_id))

        return ret

    # Decode data using found message
    try:
        message_dict = msg.decode(unhexlify(data), True, True)
        
        iso_timestamp = get_isotime_timestamp_from_msg(msg_dict)

        if flatten:
            ret = message_dict
        else:
            for key, val in message_dict.items():
                ret.append({
                    "_stamp": iso_timestamp,
                    "value": val,
                    "_type": key.lower()
                    # TODO HN: Also add unit if specified in signal
                })
            
    except Exception as ex:
        log.exception(ex)
        raise

    log.info(ret)

    return ret
