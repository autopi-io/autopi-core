import logging

log = logging.getLogger(__name__)

class TranslatableMessage(object):
    def __init__(self, data):
        if type(data) != bytearray:
            raise TypeError("Type of data must be bytearray")
        
        self.data = data

def bytes_to_int(bs):
    """ converts a big-endian byte array into a single integer """
    v = 0
    p = 0
    for b in reversed(bs):
        v += b * (2**p)
        p += 8
    return v

def bytes_to_hex(bs):
    h = ""
    for b in bs:
        bh = hex(b)[2:]
        h += ("0" * (2 - len(bh))) + bh
    return h

def twos_comp(val, num_bits):
    """compute the 2's compliment of int value val"""
    if( (val&(1<<(num_bits-1))) != 0 ):
        val = val - (1<<num_bits)
    return val

def calc_formula(expression, message_data, default=None):

    if not message_data:
        log.warn("No data found to calculate formula: {:}".format(expression))

        return default

    if type(message_data) == bytearray:
        message_data = [TranslatableMessage(message_data)]

    try:
        return eval(expression, {}, {
            # Helper functions
            "bytes_to_int": bytes_to_int,
            "bytes_to_hex": bytes_to_hex,
            "twos_comp": twos_comp,
            # Message data
            "message": message_data[0],
            "messages": message_data
        })
    except Exception as ex:
        log.exception("Failed to calculate formula")

        raise Exception("Failed to calculate formula: {:}".format(ex))