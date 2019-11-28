import logging
import socket
import _thread
import random


DATA = {
    # ELM327
    "ATZ":      "OBDSIM",       # Reset
    "ATRV":     "{:d}.{:d}V".format(random.randint(11,13), random.randint(0,9)),        # Voltage

    # OBD
    "010C":     "00 00 00 00",  # RPM
    "010D":     "00 00 00",     # Speed
}


log = logging.getLogger(__name__)


def client_thread(conn, addr):
    
    # TODO: Is this actually done by STN?
    # Send initial ready command
    #conn.send(">\r")

    while True:
        rx = conn.recv(1024)
        if not rx:
            break

        log.info("RX %s", repr(rx))

        cmd = rx.strip().upper()
        res = DATA.get(cmd, "ERROR: No simulator data found for command '{:s}'".format(cmd))        

        tx = "{:s}\r{:s}\r>\r".format(cmd, res)
        conn.send(tx)
        log.info("TX %s", repr(tx))

    conn.close()
    log.info("Disconnected connection to %s:%s", addr[0], addr[1])


def start(host, port):
    log.info("Starting OBD simulator")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        sock.listen(5)
        log.info("Listening on %s:%s", host, port)

        while True:
            # Wait to accept a connection - blocking call
            conn, addr = sock.accept()
            log.info("Accepted connection from %s:%s", addr[0], addr[1])
              
            # Spawn new dedicated client thread
            _thread.start_new_thread(client_thread, (conn, addr))
    finally:
        log.info("Stopping OBD simulator")
        sock.close()