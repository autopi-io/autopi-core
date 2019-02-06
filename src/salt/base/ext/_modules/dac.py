import time

from mcp4725_conn import MCP4725Conn


def test():
    conn = MCP4725Conn()
    with conn.setup({"port": 1, "address": 96}):
        for idx in range(0, 5):

            conn.voltage(0)
            time.sleep(1)

            conn.voltage(2048)  # 2048 = half of 4096
            time.sleep(1)

            conn.voltage(4096, True)
            time.sleep(1)

    return {
        "success": True
    }