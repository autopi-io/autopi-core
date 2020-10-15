import binascii
import logging

from retrying import retry
from serial import *

log = logging.getLogger(__name__)


class SerialConn(object):

    class Decorators(object):

        @staticmethod
        def ensure_open(func):

            def decorator(self, *args, **kwargs):

                # Ensure connection is open
                self.ensure_open()

                try:
                    return func(self, *args, **kwargs)
                except SerialException as se:

                    if self._settings.get("close_on_error", True):
                        log.warning("Closing serial connection due to error: {:}".format(se))

                        try:
                            self.close()
                        except:
                            log.exception("Failed to close serial connection after error occurred: {:}".format(se))

                    raise

            # Add reference to the original undecorated function
            decorator.undecorated = func

            return decorator

    def __init__(self):
        pass

    def init(self, settings):
        if "device" in settings:
            log.info("Using device '%s'", settings["device"])

            self._serial = Serial(
                baudrate=settings["baudrate"],
                timeout=settings["timeout"],
                bytesize=EIGHTBITS,
                parity=PARITY_NONE,
                stopbits=STOPBITS_ONE,
            )
            self._serial.port = settings["device"]
        elif "url" in settings:
            log.info("Using URL '%s'", settings["url"])

            self._serial = serial_for_url(settings["url"], do_not_open=True)
            self._serial.timeout = settings["timeout"]
        else:
            raise ValueError("Either 'device' or 'url' must be specified in settings")

        self._settings = settings

    @property
    def settings(self):
        return self._settings

    @retry(stop_max_attempt_number=3, wait_fixed=1000)
    def open(self):
        log.info("Opening serial connection")

        try :
            self._serial.open()

            return self
        except Exception:
            log.exception("Failed to open serial connection")

            raise

    def is_open(self):
        return self._serial.is_open

    def ensure_open(self):
        if not self.is_open():
            self.open()

    def close(self):
        self._serial.close()

    def __enter__(self):
        return self.open()

    def __exit__(self, type, value, traceback):
        self.close()

    @Decorators.ensure_open
    def write(self, *args, **kwargs):
        return self._serial.write(*args, **kwargs)

    @Decorators.ensure_open
    def write_line(self, data, line_terminator="\r"):
        log.debug("TX: %s", repr(data))

        if line_terminator:
            data += line_terminator

        self._serial.write(data)

    @Decorators.ensure_open
    def read(self, *args, **kwargs):
        return self._serial.read(*args, **kwargs)

    @Decorators.ensure_open
    def read_line(self, timeout=None):
        try:

            # Use temporary timeout if specified
            if timeout != None:
                timeout_orig = self._serial.timeout
                self._serial.timeout = timeout

            line = self._serial.readline()
        finally:

            # Restore original timeout
            if timeout != None:
                self._serial.timeout = timeout_orig

        log.debug("RX: %s", repr(line))

        return line

    def read_lines(self):

        # Read first line using initial timeout
        line = self.read_line()
        if not line:
            return

        lines = []
        lines.append(line)

        # Read following lines without any timeout
        while True:
            line = self.read_line(timeout=0)

            # Stop reading when no more data
            if not line:
                break

            lines.append(line)

        return lines

    @Decorators.ensure_open
    def read_until(self, ready_word, error_regex,
            line_separator="\n",
            dedicated_ready_line=True,
            ignore_empty_lines=True,
            echo_on=True,
            expect_multi_lines=False,
            return_command=False):

        ret = {}

        lines = []
        chars = []
        while True:
            char = self._serial.read()
            if not char:
                log.error("Read timeout after waiting %f second(s)", self._serial.timeout)
                # TODO: Mark timeout occured and next read might be false?

                ret["error"] = "Timeout"
                break

            if char == line_separator:
                line = "".join(chars).rstrip()
                chars = []

                log.debug("RX: %s", repr(line))

                # Break if entire line matches ready word
                if dedicated_ready_line and line == ready_word:
                   break

                match = error_regex.match(line)
                if match:
                    groups = match.groupdict()
                    if groups:
                        ret["error"] = groups
                    else:
                        ret["error"] = line
                    break

                if not ignore_empty_lines or line:
                    lines.append(line)
            else:
                chars.append(char)

            # Break if current chars matches ready word
            if not dedicated_ready_line and chars == list(ready_word):
                break

        if echo_on and lines:
            if return_command:
                ret["command"] = lines[0]
            lines = lines[1:]

        if lines:
            ret["data"] = lines[0] if len(lines) == 1 and not expect_multi_lines else lines

        return ret
