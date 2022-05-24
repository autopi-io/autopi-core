import unittest

import salt.base.ext._utils.se05x_conn as se_conn

# Note: __init__.py's might need to be added for this to work

class TestGenerateKey(unittest.TestCase):
    def test_get_serial_expectedOk(self):
        con = se_conn.CryptoConnection()
        ret_serial = None
        with con:
            ret_serial = con.get_serial()

        self.assertIsNotNone(ret_serial);

if __name__ == '__main__':
    unittest.main()