import logging
import time
from bluepy import btle
import subprocess

# Define the module's virtual name
__virtualname__ = "bluetooth"

log = logging.getLogger(__name__)

def __virtual__():
    return __virtualname__

def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"](__virtualname__)

def scan(hci=0, sensitivity=-128, timeout=4, verbose=True, sort_by='rssi'):
    """
    Return list of BLE devices in the proximity.

    Optional arguments:
      - hci (int) Interface number for scan: Default is 0.
      - sensitivity (int): Default is -128 dbm.
      - timeout (int): Default is 4 seconds.
      - verbose (bool): Default is True.
      - sort_by (str): Default is 'rssi'.
    """

    btle.Debugging = verbose
    scanner = btle.Scanner(hci)

    devices_raw = []
    try:
        devices_raw = scanner.scan(timeout)
    except btle.BTLEManagementError:
        log.exception('btle.BTLEManagementError occurred. Will attempt to restart bluetooth device.')
        resp = subprocess.call("hciconfig hci0 down && hciconfig hci0 up", shell=True)
        log.exception('Result from "hciconfig hci0 down && hciconfig hci0 up": {}'.format(resp))
        time.sleep(5)
        
        # Retry
        devices_raw = scanner.scan(timeout)

    devices = []

    for device_raw in devices_raw:
        if device_raw.rssi < sensitivity:
            continue
        
        data = []
        if verbose:
            for (sdid, desc, val) in device_raw.getScanData():
                if sdid in [8, 9]:
                    data.append(desc + ': \'' + val + '\'')
                else:
                    data.append(desc + ': <' + val + '>')

        devices.append({ 
            "address": device_raw.addr,
            "address_type": device_raw.addrType,
            "connectable": device_raw.connectable,
            "rssi": device_raw.rssi,
            "data": data or None
        })

    if sort_by:
        sorted_devices = sorted(devices, key=lambda device: device.get(sort_by))
    else:
        sorted_devices = devices

    return sorted_devices