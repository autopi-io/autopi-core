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
        self.daemon = False

        self.on_command = None
        self.on_connect = None
        self.on_disconnect = None

        self.multiple_clients = False

        self._sock = None
        self._host = None
        self._port = None

    def start(self, host="localhost", port=35000):
        self._host = host
        self._port = port

        return super(ELM327Proxy, self).start()

    @retry(wait_fixed=10000)
    def run(self):
        try:
            if log.isEnabledFor(logging.DEBUG):
                log.debug("Starting ELM327 proxy")

            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.bind((self._host, self._port))
            self._sock.listen(0)

            while True:
                log.info("ELM327 proxy is ready and listening on %s:%s", self._host, self._port)

                # Wait to accept a connection - blocking call
                conn, addr = self._sock.accept()
                log.info("Accepted new connection from ELM327 client %s:%s", addr[0], addr[1])

                if self.multiple_clients:

                    # Spawn new dedicated client thread
                    thread.start_new_thread(self._client_thread, (conn, addr))

                else:

                    # Run in current thread
                    self._client_thread(conn, addr)

        except:
            log.exception("Unhandled error in ELM327 proxy")

            raise
        finally:
            log.info("Stopping ELM327 proxy")

            self._sock.shutdown(socket.SHUT_RDWR)
            self._sock.close()

    def _client_thread(self, conn, addr):
        try:
            log.info("Connected to ELM327 client %s:%s", addr[0], addr[1])

            if self.on_connect:
                try:
                    self.on_connect(conn, addr)
                except:
                    log.exception("Error in 'on_connect' event handler")

            #if log.isEnabledFor(logging.DEBUG):
            log.info("Sending initial ready prompt")

            # Send initial ready prompt
            conn.send(self.PROMPT)

            while True:
                data = self._read(conn)
                if not data:

                    #if log.isEnabledFor(logging.DEBUG):
                    log.info("No data received - sending ready prompt")

                    # Send ready prompt again
                    conn.send(self.PROMPT)

                    continue

                if log.isEnabledFor(logging.DEBUG):
                    log.debug("RX: %s", repr(data))

                for cmd in data.rstrip().split(self.TERMINATOR):
                    res = self.TERMINATOR.join(self.on_command(cmd)) + self.PROMPT

                    if log.isEnabledFor(logging.DEBUG):
                        log.debug("TX: %s", repr(res))

                    conn.send(res)
        except socket.error as err:
            log.info("Disconnected ELM327 client connection %s:%s due to socket error: %s", addr[0], addr[1], str(err))

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
                break

            buffer.extend(data)

            # Break on CR or NL
            if buffer[-1:] in [b"\r", b"\n"]:
                break

        return buffer.decode()
