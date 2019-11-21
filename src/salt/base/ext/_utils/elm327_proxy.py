import logging
import socket
import threading


log = logging.getLogger(__name__)


class ELM327Proxy(threading.Thread):
    TERMINATOR = b"\r"
    PROMPT = b"\r>"

    def __init__(self):
        super(ELM327Proxy, self).__init__()

        self.name = "elm327_proxy_{:}".format(id(self))
        #self.daemon = True
        
        self.on_command = None
        self.on_connect = None
        self.on_disconnect = None

        self._host = None
        self._port = None

        self._server = None
        self._client = None

        self._stop = False

    def start(self, host="localhost", port=35000):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Starting ELM327 proxy")

        self._host = host
        self._port = port

        self._stop = False

        return super(ELM327Proxy, self).start()

    def stop(self):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Stopping ELM327 proxy")

        # Set stop flag
        self._stop = True

        # Close and clear any client socket
        self._close(self._client)
        self._client = None

        # Close and clear any server socket
        self._close(self._server)
        self._server = None

        # Wait until terminated
        self.join()

    def run(self):
        try:
            log.info("Started ELM327 proxy")

            self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server.bind((self._host, self._port))
            self._server.listen(0)

            log.info("ELM327 proxy is listening on %s:%s", self._host, self._port)

            while not self._stop:  # Loop until stop flag is set
                log.info("Ready to accept connection from client")

                try:
                    # Wait to accept a connection - blocking call
                    # NOTE: Will be interrupted when socket is shut down
                    self._client, addr = self._server.accept()
                except socket.error as err:
                    log.info("Unable to accept client connection: %s", str(err))

                    continue

                try:
                    self._relay(self._client, addr)
                finally:

                    # Ensure client socket is closed and cleared
                    self._close(self._client)
                    self._client = None

        except:
            log.exception("Unhandled error in ELM327 proxy")

        finally:
            log.info("Stopped ELM327 proxy")

            # Ensure server socket is closed and cleared
            self._close(self._server)
            self._server = None

    def _relay(self, conn, addr):
        try:
            log.info("Connected to client %s:%s", addr[0], addr[1])

            # Trigger connect event
            if self.on_connect:
                try:
                    self.on_connect(addr)
                except:
                    log.exception("Error in 'on_connect' event handler")

            if log.isEnabledFor(logging.DEBUG):
                log.debug("Sending initial ready prompt")

            # Send initial ready prompt
            conn.send(self.PROMPT)

            while True:
                data = self._read(conn)
                if not data:

                    if log.isEnabledFor(logging.DEBUG):
                        log.debug("No data received - sending ready prompt")

                    # NOTE: Will fail after an empty read due to closed connection
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
            log.info("Disconnected connection to client %s:%s: %s", addr[0], addr[1], str(err))

        except:
            log.exception("Unhandled error in connection to client %s:%s", addr[0], addr[1])

        finally:

            # Trigger disconnect event
            if self.on_disconnect:
                try:
                    self.on_disconnect(addr)
                except:
                    log.exception("Error in 'on_disconnect' event handler")

    def _read(self, conn):
        buffer = bytearray()

        while True:

            # Wait to read - blocking call
            data = conn.recv(1024)

            # Break on no data
            if not data:
                break

            buffer.extend(data)

            # Break on CR or NL
            if buffer[-1:] in [b"\r", b"\n"]:
                break

        return buffer.decode()

    def _close(self, sock):

        # If already cleared there is no reason to continue
        if not sock:
            return

        # First ensure socket is shut down
        try:
            sock.shutdown(socket.SHUT_RDWR)  # Both read and write
        except Exception as ex:
            log.warning("Unable to shut down socket: %s", str(ex))

        # Then ensure socket is closed
        try:
            sock.close()
        except Exception as ex:
            log.warning("Unable to close socket: %s", str(ex))
