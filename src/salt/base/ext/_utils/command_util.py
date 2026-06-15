import logging 
import re

from os.path import exists, isdir, isfile
from six import string_types
from sys import version_info

log = logging.getLogger(__name__)

TRUE_VALS = (True, "True", "true", 1, "1")
FALSE_VALS = (False, "False", "false", 0, "0")

# We need to enforce sanization on some values, mostly concerning with hex
#   values (We want to be able to use the xHEX format in engines.conf).
FLAG_FORCE_SANITIZATION = 1

if version_info[0] >= 3:
    unicode = str

def int_to_str(i, to_hex):
    if to_hex:
        return hex(i)
    else:
        return i

def is_valid_hex(input_str):
    pattern = r"^[0-9A-Fa-f]+$"
    return bool(re.match(pattern, input_str))

def _sanitize(val, name, normalizer, validators):
    norm_val, is_hex = normalizer(val, name)
    for validator in validators:
        validator(norm_val, name, is_hex=is_hex)
    return norm_val

def sanitize(val, name, normalizer, validators=[], default=None):
    """
    Sanitizes a value based on given normalizer and validators. Allows for a
    default which is passed if val is None. 
    """
    if val == None:
        return default
    return _sanitize(val, name, normalizer, validators)

def sanitize_dict_val(kwargs, name, default, normalizer, validators=[]):
    """
    Sanitizes a named value in a dictionary
    """
    val = kwargs.get(name)
    kwargs[name] = sanitize(val, name, normalizer, validators, default)

def sanitize_kwargs(enabled, kwargs, sanitizers):
    """
    Sanitizes a whole dictionary based on given sanitizers. Each sanitizer is
    a list/tuple of format (name (str), default (any), normalizer (Normalizer), 
    validators (list/tuple of Validator), flags (list/tuple of FLAG_XXX))
    """
    for sanitizer in sanitizers:
        name, default, normalizer, validators, flags = sanitizer
        val = kwargs.get(name)
        if val == None:
            kwargs[name] = default
            continue

        if enabled or FLAG_FORCE_SANITIZATION in flags:
            kwargs[name] =_sanitize(val, name, normalizer, validators)

class normalizers:

    @staticmethod
    def uinteger(i, name):
        """
        Normalize to an integer, interpreting hex values as unsigned. Will 
        raise if given a negative int.
        """
        norm_val = None
        is_hex = False
        if isinstance(i, int) or isinstance(i, long):  # NOTE: Also allow long
            # Don't allow negative integers
            if i < 0:
                pass
            else:
                norm_val = i
        elif isinstance(i, string_types):
            if i.startswith('x'):
                #   If the conversion fails beacuase of non-hex characters, we 
                # want to show the error message at the bottom of the function
                try:
                    norm_val = int(i[1:], 16)
                    is_hex = True
                except ValueError:
                    pass
            else:
                try:
                    norm_val = int(i, 10)
                    is_hex = False
                except ValueError:
                    pass

        if norm_val == None:
            raise ValueError("{} must either be a positive integer or str of format 'x<HEX|hex>' (e.g. 61123 or 'xEEC3'). Got '{}' of type {}".format(name, i, type(i).__name__))

        return norm_val, is_hex
    
    @staticmethod
    def hex_str(i, name):
        """
        Normalize to a uppercase hex string of any string length without a
        0x prefix.
        
        All values are interpreted as hex, including integers. In other words,
        there is no way to pass in an integer value: int 10 is seen as hex 10.
        """
        norm_val = None
        is_hex = True
        
        # Get initial string form
        if isinstance(i, string_types):
            if i.startswith('x'):
                hex_candidate = i[1:]
            else:
                hex_candidate = i
                
            if is_valid_hex(hex_candidate):
                norm_val = hex_candidate
        elif isinstance(i, int):
            norm_val = str(i)

        if norm_val != None:
            norm_val = norm_val.upper()

        # Raise if can't be normalized
        if norm_val == None:
            raise ValueError("{} must be a hex string of format 'x<HEX|hex>' or '<HEX|hex>'  (e.g. 'xEE', 'c2', '01'). Got '{}' of type {}".format(name, i, type(i).__name__))
        
        return norm_val, is_hex

    @staticmethod
    def string_unicode(i, name):
        """
        Normalize to unicode string of any length. Accepts any string-convertible type.
        """
        is_hex = False
        norm_val = i

        if type(i) != unicode:
            norm_val = unicode(i)

        return norm_val, is_hex
    
    @staticmethod
    def floating(i, name):
        """
        Normalize to float. Accepts string, int, float.
        """
        is_hex = False
        norm_val = None
        
        if isinstance(i, float):
            norm_val = i
        elif isinstance(i, int):
            norm_val = float(i)
        elif isinstance(i, string_types):
            try:
                norm_val = float(i)
            except:
                pass
        
        if norm_val == None:
            raise ValueError("{} must be a float or a type/value convertable to float. (e.g. 1, 3.1, '3.3'). Got '{}' of type {}".format(name, i, type(i).__name__))

        return norm_val, is_hex
    
    @staticmethod
    def boolean(i, name):
        """
        Normalize to bool. Accepts any value in command_util.TRUE_VALS and command_util.FALSE_VALS.
        """
        is_hex = False
        norm_val = None
        
        if isinstance(i, bool):
            norm_val = i
        else:
            if i in TRUE_VALS:
                norm_val = True
            elif i in FALSE_VALS:
                norm_val = False
        
        if norm_val == None:
            raise ValueError("{} must be a true/false value. Got '{}' of type {}".format(name, i, type(i).__name__))
        
        return norm_val, is_hex
    
    @staticmethod
    def list_or_tuple(i, name):
        """
        Normalize to a 'list' or 'tuple'. Accepts comma (,) delimited string, tuple, list, or a single value.
        """
        is_hex = False
        norm_val = None
        
        delimiter = ","
        
        if isinstance(i, list) or isinstance(i, tuple):
            norm_val = i
        elif isinstance(i, string_types):
            norm_val = i.split(delimiter)
        else:
            norm_val = [i]
        
        if norm_val == None:
            raise ValueError("{} must must be a list of type list/tuple or of values delimited by '{}'. Got '{}' of type {}".format(name, delimiter, i, type(i).__name__))
        
        return norm_val, is_hex
    
    @staticmethod
    def collection(i, name):
        """
        Normalize to a 'list'. Accepts comma (,) delimited string, tuple, list, set or a single value.
        """
        is_hex = False
        norm_val = None
        
        delimiter = ","
        
        if isinstance(i, (list, set, tuple)):
            norm_val = i
        elif isinstance(i, string_types):
            norm_val = i.split(delimiter)
        else:
            norm_val = [i]
        
        if norm_val == None:
            raise ValueError("{} must must be a collection of type list/set/tuple or of values delimited by '{}'. Got '{}' of type {}".format(name, delimiter, i, type(i).__name__))
        
        return norm_val, is_hex

    @staticmethod
    def tuple_key_value_pair(i, name):
        """
        Normalize to a key value pair 'tuple'. Accepts colon (:) delimited string, tuple, list, or a single value.
        """
        is_hex = False
        norm_val = None
        
        delimiter = ":"
        
        if isinstance(i, list) or isinstance(i, tuple):
            norm_val = i
        elif isinstance(i, string_types):
            norm_val = i.split(delimiter)
        else:
            norm_val = [i]
        
        if norm_val == None or len(norm_val) > 2:
            raise ValueError("{} must must be a key value pair of type list/tuple or of values delimited by '{}'. Got '{}' of type {}".format(name, delimiter, i, type(i).__name__))

        return tuple(norm_val), is_hex

    @staticmethod
    def can_message_any_type(i, name):
        is_hex = False
        ret = i

        if isinstance(i, dict):
            ret = {}

            FIELD_NORMALIZERS = {
                "id": normalizers.uinteger,
                "is_ext_id": normalizers.boolean,
                "is_fd": normalizers.boolean,
                "data": normalizers.hex_str
            }

            for key, val in i.iteritems():
                if not key in FIELD_NORMALIZERS.keys():
                    raise ValueError("{} dictionary contains unsupported key '{}'. Got '{}' of type {}".format(name, key, i, type(i).__name__))

                ret[key], _ = FIELD_NORMALIZERS[key](i[key], key)

        elif isinstance(i, string_types):
            if not "#" in i:
                raise ValueError("{} string must contain at least one '#' character. Got '{}' of type {}".format(name, i, type(i).__name__))
        elif isinstance(i, object):
            if not i.__class__.__module__ == "can.message" or not i.__class__.__name__ == "Message":
                raise ValueError("{} must be an object of class 'can.message.Message'. Got '{}' of type {}".format(name, i, type(i).__name__))
        else:
            raise ValueError("{} must be a dictionary, string or instance of class 'can.message.Message'. Got '{}' of type {}".format(name, i, type(i).__name__))

        return ret, is_hex

    @staticmethod
    def can_filter_dict(i, name):
        is_hex = False
        ret = {}

        if not isinstance(i, dict):
            raise ValueError("{} must be a dictionary. Got '{}' of type {}".format(name, i, type(i).__name__))

        for key in ["id", "mask"]:
            if not key in i:
                raise ValueError("{} dictionary contains unsupported key '{}'. Got '{}' of type {}".format(name, key, i, type(i).__name__))

            ret[key], _ = normalizers.uinteger(i[key], key)

        if not "is_ext_id" in i:
            raise ValueError("{} dictionary is missing key 'is_ext_id'. Got '{}' of type {}".format(name, i, type(i).__name__))

        ret["is_ext_id"], _ = normalizers.boolean(i["is_ext_id"], "is_ext_id")

        return ret, is_hex

    @staticmethod
    def hex_mapping_dict(i, name):
        is_hex = False
        ret = {}

        if not isinstance(i, dict):
            raise ValueError("{} must be a dictionary. Got '{}' of type {}".format(name, i, type(i).__name__))

        for key, val in i.iteritems():
            norm_key, _ = normalizers.uinteger(key, key)
            norm_val, _ = normalizers.uinteger(val, val)

            ret[norm_key] = norm_val

        return ret, is_hex

    class complex:
        """
        Normalizers which allow passing additional arguments. 
        """
        @staticmethod
        def byte_array(allow_half_bytes=False):
            """
            Normalize to a 'bytearray' type object. Accepts only xHEX format.
            
            Params:
            - allow_half_bytes (bool): if true, x1 will not throw an error and will prepent a zero and be interpreted as x01, x111 => x0111, etc
            """
            def _byte_array(i, name, allow_half_bytes=allow_half_bytes):
                def fail():
                    raise ValueError("{} must be a str of format 'x<HEX|hex>' (e.g. 'xEEC3'). Got '{}' of type {}".format(name, i, type(i).__name__))
                
                norm_val = None
                is_hex = False
                if not (isinstance(i, string_types) and i.startswith('x')):
                    fail()
                    
                hex_candidate = i[1:]
                if not is_valid_hex(hex_candidate):
                    fail()
                
                if len(hex_candidate) % 2 != 0:
                    if allow_half_bytes:
                        hex_candidate = "0" + hex_candidate
                    else:
                        raise ValueError("{} must be of full byte length (e.g. 'xEEC3'. Not allowed: 'xE', 'xEEC'). Got '{}' of type {}".format(name, i, type(i).__name__))
    
                norm_val = bytearray.fromhex(hex_candidate)

                return norm_val, is_hex
            
            return _byte_array
            
    class nested:
        """
        Normalizers which allow nesting other normalizers. For example, first 
        normalize to a list, then each list's item to an int.
        """

        @staticmethod
        def list_or_tuple(secondary_normalizer):
            def _list_or_tuple(i, name, secondary_normalizer=secondary_normalizer):
                norm_val = []
                is_hex = False

                norm_list, _ = normalizers.list_or_tuple(i, name)
                
                for idx, item in enumerate(norm_list):
                    item_name = "{} index {}".format(name, idx)
                    norm_item, is_hex = secondary_normalizer(item, item_name)
                    norm_val.append(norm_item)
                
                return norm_val, is_hex
            return _list_or_tuple

        @staticmethod
        def collection(secondary_normalizer):
            def _collection(i, name, secondary_normalizer=secondary_normalizer):
                norm_val = []
                is_hex = False

                norm_list, _ = normalizers.collection(i, name)
                
                for idx, item in enumerate(norm_list):
                    item_name = "{} index {}".format(name, idx)
                    norm_item, is_hex = secondary_normalizer(item, item_name)
                    norm_val.append(norm_item)
                
                return norm_val, is_hex
            return _collection

        @staticmethod
        def tuple_key_value_pair(secondary_normalizer):
            def _tuple_key_value_pair(i, name, secondary_normalizer=secondary_normalizer):
                norm_val = []
                is_hex = False

                norm_list, _ = normalizers.tuple_key_value_pair(i, name)
                
                for idx, item in enumerate(norm_list):
                    item_name = "{} index {}".format(name, idx)
                    norm_item, is_hex = secondary_normalizer(item, item_name)
                    norm_val.append(norm_item)
                
                return tuple(norm_val), is_hex
            return _tuple_key_value_pair


class validators:
    @staticmethod
    def max(val):
        """
        Ensure val <= max
        """
        def _max(val, name, is_hex=False, max_val=val):
            if val > max_val:
                raise Exception("{} must be {} or less. Got {}".format(name, int_to_str(max_val, is_hex), int_to_str(val, is_hex)))
        return _max
    
    @staticmethod
    def min(val):
        """
        Ensure val >= min
        """
        def _min(val, name=None, is_hex=False, min_val=val):
            if val < min_val:
                raise Exception("{} must be {} or more. Got {}".format(name, int_to_str(min_val, is_hex), int_to_str(val, is_hex)))
        return _min
    
    @staticmethod
    def max_len(val):
        """
        Ensure len(val) <= max_len
        """
        def _max_len(val, name=None, is_hex=None, max_val=val):
            if len(val) > max_val:
                raise Exception("Length of {} must be {} characters/bytes or less. Got {}".format(name, max_val, val))
        return _max_len

    @staticmethod
    def ensure_string(contains=None, allow_blank=True):
        """
        Ensure item is string
        """
        def _ensure_string(val, name=None, is_hex=None, contains=contains, blank=allow_blank):
            if not isinstance(val, str) or (contains and not contains in val) or (not blank and val == ""):
                contain_str = ", contain: '{}',".format(contains) if contains else ""
                raise ValueError("Parameter '{}' with value ('{}') must be a string{} and allows blank: {}. Got {}".format(name, val, contain_str, blank, type(val)))
        return _ensure_string

    @staticmethod
    def ensure_number(signed=True):
        """
        Ensure item is a number (integer or float)
        """
        def _ensure_number(val, name=None, is_hex=None, signed=signed):
            if not type(val) in [int, float] or (signed or val < 0):
                raise ValueError("Item {} must be a number, {}".format(val, "signed" if signed else "unsigned"))
        return _ensure_number

    @staticmethod
    def ensure_path(restrict_to_dir=False, restrict_to_file=False, allow_none=False):
        """
        Ensure path exists
        """
        def _ensure_path(path, name=None, is_hex=None, restrict_to_dir=restrict_to_dir, restrict_to_file=restrict_to_file, allow_none=allow_none):
            if allow_none and path == None:
                return
            if restrict_to_dir:
                if not isdir(path):
                    raise ValueError("{} must be a valid directory.".format(path))
            elif restrict_to_file:
                if not isfile(path):
                    raise ValueError("{} must be a valid file.".format(path))
            else:
                if not exists(path):
                    raise ValueError("{} must be a valid path.".format(path))
        return _ensure_path
    
    @staticmethod
    def choice(choices):
        """
        Ensure value is one of choices. (type sensitive)
        """
        def _choice(val, name=None, is_hex=None, choices=choices):
            if val not in choices:
                choices_str = '|'.join(['{}'.format(c) for c in choices])
                raise Exception("{} must of one of: {}. Got: {}".format(name, choices_str, val))
        return _choice
    
    @staticmethod
    def per_item(validator, allow_none=False):
        """
        Nested. Apply given validator to every item in value list.
        """
        def _per_item(items, name=None, is_hex=None, validator=validator):
            if items:
                for idx, item in enumerate(items):
                    item_name = "{} index {}".format(name, idx)
                    validator(item, item_name)
            elif not allow_none:
                raise ValueError("List '{}' must not be empty or None".format(name))
        return _per_item

    @staticmethod
    def ensure_dict(dict_validator, restrict=False):
        """
        Nested. uses dictionary to validate dictionary by using key to apply validator.
        """
        def _per_entry(items, name=None, is_hex=None, validator=dict_validator, restrict=restrict):
            for key, _validator in validator.items():
                if key in items:
                    _validator(items[key], key)
                elif restrict:
                    raise ValueError("Dictionary key {} is missing from one of the items".format(key))
        return _per_entry
