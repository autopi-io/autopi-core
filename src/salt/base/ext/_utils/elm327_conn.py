import logging
import obd

from obd.interfaces import STN11XX
from retrying import retry
from serial_conn import SerialConn


log = logging.getLogger(__name__)


class ELM327Conn(SerialConn):

    def __init__(self):
        self._device = None
        self._baudrate = None

        self._obd = None

    def init(self, settings):
        log.info("Initializing ELM327 connection using settings: %s", settings)

        if not "device" in settings:
            raise ValueError("Setting 'device' must be specified")
        self._device = settings["device"]

        if not "baudrate" in settings:
            raise ValueError("Setting 'baudrate' must be specified")
        if not settings["baudrate"] in STN11XX.TRY_BAUDRATES:
            raise ValueError("Setting 'baudrate' has unsupported value")
        self._baudrate = settings["baudrate"]

    @retry(stop_max_attempt_number=3, wait_fixed=1000)
    def open(self):
        log.info("Opening ELM327 connection")

        try :
            self._obd = obd.OBD(portstr=self._device, baudrate=self._baudrate, interface_cls=STN11XX)

            return self
        except Exception:
            log.exception("Failed to open ELM327 connection")

            raise

    def is_open(self):
        return self._obd != None \
            and self._obd.status() != obd.OBDStatus.NOT_CONNECTED

    def close(self):
        self._obd.close()

    def info(self):
        return {
            "status": self._obd.status(),
            "serial": self._obd.connection_info(),
            "protocol": self._obd.protocol_info()
        }

    def protocol_info(self):
        return self._obd.protocol_info()

    def supported_protocols(self):
        return {k: v.NAME for k, v in self._obd.supported_protocols().iteritems()}

    def change_protocol(self, id, **kwargs):
        self.ensure_open()
        
        return self._obd.change_protocol(id, **kwargs)

    def query(self, cmd, **kwargs):
        self.ensure_open()

        return self._obd.query(cmd, **kwargs)

    def supported_commands(self):
        self.ensure_open()

        return {c.name: c.desc for c in self._obd.supported_commands}

    def send(self, msg, **kwargs):
        self.ensure_open()

        # Parse out header if found
        hash_pos = msg.find("#")
        if hash_pos > 0:
            kwargs["header"] = msg[:hash_pos]
            msg = msg[hash_pos + 1:]

        return self._obd.send(msg, **kwargs)

    def execute(self, cmd, **kwargs):
        self.ensure_open()

        return self._obd.execute(cmd, **kwargs)

    def reset(self, **kwargs):
        self.ensure_open()

        self._obd.reset(**kwargs) 

    def change_baudrate(self, value):
        if not value in STN11XX.TRY_BAUDRATES:
            raise ValueError("Invalid baudrate - supported values are: {:}".format(
                ", ".join([str(b) for b in STN11XX.TRY_BAUDRATES])
            ))

        self.ensure_open()

        return self._obd.interface.set_baudrate(value)

    def monitor_all(self, **kwargs):
        self.ensure_open()

        # Format messages
        return [l.replace(" ", "#", 1).replace(" ", "") for l in self._obd.interface.monitor_all(**kwargs)]
