import logging
import pickle
import os

log = logging.getLogger(__name__)

def create_dir_if_does_not_exist(dir):
    if not os.path.exists(dir):
        os.makedirs(dir)

def load_object(name, default={}, dir_path="/opt/autopi/persistence"):
    try:
        with open("{}/{}.pkl".format(dir_path, name), "rb") as f:
            return pickle.load(f)

    except Exception as err:
        log.warning("Persistent file could not be opened. Returning default. Exception: {}".format(err))

    return default

def save_object(name, value, dir_path="/opt/autopi/persistence"):
    try:
        create_dir_if_does_not_exist(dir_path)
        with open("{}/{}.pkl".format(dir_path, name), "wb+") as f:
            pickle.dump(value, f)

    except Exception as err:
        log.error("Persistent file could not be opened. Exception: {}".format(err))
        raise err