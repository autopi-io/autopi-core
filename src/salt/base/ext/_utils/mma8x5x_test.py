import mma8x5x_conn as mma8x5x


def signed_int_alt(word, bits=10):
    from ctypes import c_short
    return c_short(word << (16-bit)).value >> (16-bit)


def g(word, bits=10, g_range=2):
    res = mma8x5x.calc_g(word, bits=bits, g_range=g_range, decimals=4)
    print "{:d}g, {:d}bit; {:010b} = {:f}g".format(g_range, bits, word, res)
    return res


#
# 10bit
#

# +-2g
assert g(0b0111111111) == 1.9961
assert g(0b0111111110) == 1.9922
assert g(0b0000000001) == 0.0039
assert g(0b0000000000) == 0.0
assert g(0b1111111111) == -0.0039
assert g(0b1000000001) == -1.9961
assert g(0b1000000000) == -2.0

# +-4g
assert g(0b0111111111, g_range=4) == 3.9922
assert g(0b0111111110, g_range=4) == 3.9844
assert g(0b0000000001, g_range=4) == 0.0078
assert g(0b0000000000, g_range=4) == 0.0
assert g(0b1111111111, g_range=4) == -0.0078
assert g(0b1000000001, g_range=4) == -3.9922
assert g(0b1000000000, g_range=4) == -4.0

# +-8g
assert g(0b0111111111, g_range=8) == 7.9844
assert g(0b0111111110, g_range=8) == 7.9688
assert g(0b0000000001, g_range=8) == 0.0156
assert g(0b0000000000, g_range=8) == 0.0
assert g(0b1111111111, g_range=8) == -0.0156
assert g(0b1000000001, g_range=8) == -7.9844
assert g(0b1000000000, g_range=8) == -8.0


#
# 8bit
#

# +-2g
assert g(0b01111111, bits=8) == 1.9844
assert g(0b01111110, bits=8) == 1.9688
assert g(0b00000001, bits=8) == 0.0156
assert g(0b00000000, bits=8) == 0.0
assert g(0b11111111, bits=8) == -0.0156
assert g(0b10000001, bits=8) == -1.9844
assert g(0b10000000, bits=8) == -2.0

# +-4g
assert g(0b01111111, bits=8, g_range=4) == 3.9688
assert g(0b01111110, bits=8, g_range=4) == 3.9375
assert g(0b00000001, bits=8, g_range=4) == 0.0313
assert g(0b00000000, bits=8, g_range=4) == 0.0
assert g(0b11111111, bits=8, g_range=4) == -0.0313
assert g(0b10000001, bits=8, g_range=4) == -3.9688
assert g(0b10000000, bits=8, g_range=4) == -4.0

# +-8g
assert g(0b01111111, bits=8, g_range=8) == 7.9375
assert g(0b01111110, bits=8, g_range=8) == 7.8750
assert g(0b00000001, bits=8, g_range=8) == 0.0625
assert g(0b00000000, bits=8, g_range=8) == 0.0
assert g(0b11111111, bits=8, g_range=8) == -0.0625
assert g(0b10000001, bits=8, g_range=8) == -7.9375
assert g(0b10000000, bits=8, g_range=8) == -8.0
