import evdev
import time

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

    def __init__(self, dev_path):
        self._dev_path = dev_path
        self._dev = evdev.InputDevice(dev_path)
        self._rfids_read = []

        # grab device here (the input will only be shown inside the Core system, nothing will be
        # written on screen: https://python-evdev.readthedocs.io/en/latest/apidoc.html#evdev.device.InputDevice.grab)
        self._dev.grab()

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
        Read an RFID or return within timeout (2 seconds default).

        NOTE NV: This can probably be improved to use a thread class instead of using time.sleep - time.sleep can possibly hang
        NOTE NV: It can also probably be improved to hold different RFIDs even if they aren't read - act like a buffer?
        """

        rfid = ""
        time_left = timeout
        start = time.time()

        event = self._dev.read_one()

        while time_left > 0 or event: # as long as we have time, but continue working if new events come in

            if event == None:
                time.sleep(.1)

            elif self.is_key_down_event(event):
                # if it's enter, break the loop
                if event.code == evdev.ecodes.KEY_ENTER:
                    break

                # otherwise, keep building the RFID
                rfid += self.translate_event_to_char(event)

            # get new event, recalc time_left
            time_left = timeout - (time.time() - start)
            event = self._dev.read_one()

        return rfid or None

    def close(self):
        """
        Close down device and cleanup.
        """

        self._dev.close()