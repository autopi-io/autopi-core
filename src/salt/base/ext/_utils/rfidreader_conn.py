import time
import threading
import queue
import logging
import os

log = logging.getLogger(__name__)

try:
    import evdev
    HAS_EVDEV = True
except ImportError:
    log.warning("Unable to import 'evdev'")
    HAS_EVDEV = False

EVENT_KEY_MAP = {
    evdev.ecodes.KEY_0: "0",
    evdev.ecodes.KEY_1: "1",
    evdev.ecodes.KEY_2: "2",
    evdev.ecodes.KEY_3: "3",
    evdev.ecodes.KEY_4: "4",
    evdev.ecodes.KEY_5: "5",
    evdev.ecodes.KEY_6: "6",
    evdev.ecodes.KEY_7: "7",
    evdev.ecodes.KEY_8: "8",
    evdev.ecodes.KEY_9: "9",
}

class RFIDReader():
    _SENTINEL = object()
    def __init__(self, dev_path):
        self._dev_path = dev_path
        self._dev = evdev.InputDevice(dev_path)
        self._rfids_read = []

        # grab device here (the input will only be shown inside the Core system, nothing will be
        # written on screen: https://python-evdev.readthedocs.io/en/latest/apidoc.html#evdev.device.InputDevice.grab)
        self._dev.grab()
        self._buffer = queue.Queue()
        self._stop_event = threading.Event()
        self._reader_thread = threading.Thread(target=self.read_prod)
        self._reader_thread.daemon = True
        self._reader_thread.start()
        self._fatal_exc = None

    def translate_event_to_char(self, event):
        """
        Returns the character string or "$" if nothing was matched.
        """

        return EVENT_KEY_MAP.get(event.code, "$")

    def is_key_down_event(self, event):
        """
        Returns a boolean if the event passed is a key down event.
        """
        return event.type == evdev.ecodes.EV_KEY and event.value == 1

    def read(self, timeout=2):
        """
        Blocking call that returns next RFID tag from buffer, or None after timeout.
        """
        if self._fatal_exc:
            log.exception("Fatal exception occurred in read_prod - restart of manager required")
            return self._fatal_exc
        try:
            return self._buffer.get(timeout=timeout)
        except queue.Empty:
            return None


    def read_prod(self):
        """Continuously read input and push complete RFID tags into buffer"""
        rfid = ""
        try:
            while not self._stop_event.is_set():
                try:
                    os.stat(self._dev_path)
                    for event in self._dev.read_loop():
                        if self._stop_event.is_set():
                            break
                        if self.is_key_down_event(event):
                            if event.code == evdev.ecodes.KEY_ENTER:
                                if rfid:
                                    self._buffer.put(rfid)
                                    rfid = ""
                            else:
                                rfid += self.translate_event_to_char(event)
                except Exception as e: 
                    self._buffer.put(self._SENTINEL)
                    self._fatal_exc = e
        except Exception as e:
            self._fatal_exc = e
            self._buffer.put(self._SENTINEL)

    def close(self):
        """
        Close down device and cleanup.
        """
        self._stop_event.set()
        self._reader_thread.join()
        self._dev.close()
