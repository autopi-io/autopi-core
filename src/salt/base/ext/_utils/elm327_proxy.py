import errno
import logging
import socket
import thread
import threading

from retrying import retry


log = logging.getLogger(__name__)


class ELM327Proxy(threading.Thread):
    TERMINATOR = b"\r"
    PROMPT = b"\r>"

    def __init__(self):
        super(ELM327Proxy, self).__init__()

        self.name = "elm327_proxy_{:}".format(id(self))
        self.daemon = True

        self.on_command = None
        self.on_connect = None
        self.on_disconnect = None

        self._sock = None
        self._host = None
        self._port = None

    def start(self, host="localhost", port=35000):
        self._host = host
        self._port = port

        return super(ELM327Proxy, self).start()

    @retry(wait_fixed=5000)
    def run(self):
        try:
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Starting ELM327 proxy")

            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.bind((self._host, self._port))
            self._sock.listen(1)  # Only allow one connection

            log.info("ELM327 proxy listening on %s:%s", self.host, self.port)

            while True:

                # Wait to accept a connection - blocking call
                conn, addr = self.sock.accept()
                log.info("Accepted new connection from ELM327 client %s:%s", addr[0], addr[1])

                # Spawn new dedicated client thread
                thread.start_new_thread(self._client_thread, (conn, addr))
        except:
            log.exception("Unhandled error in ELM327 proxy")

            raise
        finally:
            log.info("Stopping ELM327 proxy")

            self._sock.close()

    def _client_thread(self, conn, addr):
        try:
            log.info("Connected to ELM327 client %s:%s", addr[0], addr[1])

            if self.on_connect:
                try:
                    self.on_connect(conn, addr)
                except:
                    log.exception("Error in 'on_connect' event handler")

            # Send initial ready prompt
            conn.send(self.PROMPT)

            while True:
                for cmd in self._read(conn).rstrip().split(self.TERMINATOR):
                    res = self.TERMINATOR.join(self.on_command(cmd)) + self.PROMPT

                    if log.isEnabledFor(logging.DEBUG):
                        log.debug("TX: %s", repr(res))

                    conn.send(res)
        except socket.error as err:
            if err.errno == errno.EPIPE:
                log.info("Broken pipe in ELM327 client connection %s:%s", addr[0], addr[1])
            else:
                log.exception("Socket error in ELM327 client connection %s:%s", addr[0], addr[1])
        except:
            log.exception("Unhandled error in ELM327 client connection %s:%s", addr[0], addr[1])

        finally:
            log.info("Closing connection to ELM327 client %s:%s", addr[0], addr[1])

            if self.on_disconnect:
                try:
                    self.on_disconnect(conn, addr)
                except:
                    log.exception("Error in 'on_disconnect' event handler")

            conn.close()

    def _read(self, conn):
        buffer = bytearray()

        while True:
            data = conn.recv(1024)
            if not data:
                log.warning("No data received")

                break

            buffer.extend(data)

            if buffer[-1:] in [b"\r", b"\n"]:
                break

        if log.isEnabledFor(logging.DEBUG):
            log.debug("RX: %s", repr(buffer.decode()))

        return buffer.decode()
