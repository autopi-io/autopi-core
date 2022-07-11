
#
# Copyright 2018,2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#


# Begin preamble

import ctypes, os, sys
from ctypes import *

_int_types = (c_int16, c_int32)
if hasattr(ctypes, 'c_int64'):
    # Some builds of ctypes apparently do not have c_int64
    # defined; it's a pretty good bet that these builds do not
    # have 64-bit pointers.
    _int_types += (c_int64,)
for t in _int_types:
    if sizeof(t) == sizeof(c_size_t):
        c_ptrdiff_t = t
del t
del _int_types

class c_void(Structure):
    # c_void_p is a buggy return type, converting to int, so
    # POINTER(None) == c_void_p is actually written as
    # POINTER(c_void), so it can be treated as a real pointer.
    _fields_ = [('dummy', c_int)]

def POINTER(obj):
    p = ctypes.POINTER(obj)

    # Convert None to a real NULL pointer to work around bugs
    # in how ctypes handles None on 64-bit platforms
    if not isinstance(p.from_param, classmethod):
        def from_param(cls, x):
            if x is None:
                return cls()
            else:
                return x
        p.from_param = classmethod(from_param)

    return p

class UserString:
    def __init__(self, seq):
        if isinstance(seq, str):
            self.data = seq
        elif isinstance(seq, UserString):
            self.data = seq.data[:]
        else:
            self.data = str(seq)
    def __str__(self): return str(self.data)
    def __repr__(self): return repr(self.data)
    def __int__(self): return int(self.data)
    def __long__(self): return int(self.data)
    def __float__(self): return float(self.data)
    def __complex__(self): return complex(self.data)
    def __hash__(self): return hash(self.data)

    def __cmp__(self, string):
        if isinstance(string, UserString):
            return cmp(self.data, string.data)
        else:
            return cmp(self.data, string)
    def __contains__(self, char):
        return char in self.data

    def __len__(self): return len(self.data)
    def __getitem__(self, index): return self.__class__(self.data[index])
    def __getslice__(self, start, end):
        start = max(start, 0); end = max(end, 0)
        return self.__class__(self.data[start:end])

    def __add__(self, other):
        if isinstance(other, UserString):
            return self.__class__(self.data + other.data)
        elif isinstance(other, str):
            return self.__class__(self.data + other)
        else:
            return self.__class__(self.data + str(other))
    def __radd__(self, other):
        if isinstance(other, str):
            return self.__class__(other + self.data)
        else:
            return self.__class__(str(other) + self.data)
    def __mul__(self, n):
        return self.__class__(self.data*n)
    __rmul__ = __mul__
    def __mod__(self, args):
        return self.__class__(self.data % args)

    # the following methods are defined in alphabetical order:
    def capitalize(self): return self.__class__(self.data.capitalize())
    def center(self, width, *args):
        return self.__class__(self.data.center(width, *args))
    def count(self, sub, start=0, end=sys.maxsize):
        return self.data.count(sub, start, end)
    def decode(self, encoding=None, errors=None): # XXX improve this?
        if encoding:
            if errors:
                return self.__class__(self.data.decode(encoding, errors))
            else:
                return self.__class__(self.data.decode(encoding))
        else:
            return self.__class__(self.data.decode())
    def encode(self, encoding=None, errors=None): # XXX improve this?
        if encoding:
            if errors:
                return self.__class__(self.data.encode(encoding, errors))
            else:
                return self.__class__(self.data.encode(encoding))
        else:
            return self.__class__(self.data.encode())
    def endswith(self, suffix, start=0, end=sys.maxsize):
        return self.data.endswith(suffix, start, end)
    def expandtabs(self, tabsize=8):
        return self.__class__(self.data.expandtabs(tabsize))
    def find(self, sub, start=0, end=sys.maxsize):
        return self.data.find(sub, start, end)
    def index(self, sub, start=0, end=sys.maxsize):
        return self.data.index(sub, start, end)
    def isalpha(self): return self.data.isalpha()
    def isalnum(self): return self.data.isalnum()
    def isdecimal(self): return self.data.isdecimal()
    def isdigit(self): return self.data.isdigit()
    def islower(self): return self.data.islower()
    def isnumeric(self): return self.data.isnumeric()
    def isspace(self): return self.data.isspace()
    def istitle(self): return self.data.istitle()
    def isupper(self): return self.data.isupper()
    def join(self, seq): return self.data.join(seq)
    def ljust(self, width, *args):
        return self.__class__(self.data.ljust(width, *args))
    def lower(self): return self.__class__(self.data.lower())
    def lstrip(self, chars=None): return self.__class__(self.data.lstrip(chars))
    def partition(self, sep):
        return self.data.partition(sep)
    def replace(self, old, new, maxsplit=-1):
        return self.__class__(self.data.replace(old, new, maxsplit))
    def rfind(self, sub, start=0, end=sys.maxsize):
        return self.data.rfind(sub, start, end)
    def rindex(self, sub, start=0, end=sys.maxsize):
        return self.data.rindex(sub, start, end)
    def rjust(self, width, *args):
        return self.__class__(self.data.rjust(width, *args))
    def rpartition(self, sep):
        return self.data.rpartition(sep)
    def rstrip(self, chars=None): return self.__class__(self.data.rstrip(chars))
    def split(self, sep=None, maxsplit=-1):
        return self.data.split(sep, maxsplit)
    def rsplit(self, sep=None, maxsplit=-1):
        return self.data.rsplit(sep, maxsplit)
    def splitlines(self, keepends=0): return self.data.splitlines(keepends)
    def startswith(self, prefix, start=0, end=sys.maxsize):
        return self.data.startswith(prefix, start, end)
    def strip(self, chars=None): return self.__class__(self.data.strip(chars))
    def swapcase(self): return self.__class__(self.data.swapcase())
    def title(self): return self.__class__(self.data.title())
    def translate(self, *args):
        return self.__class__(self.data.translate(*args))
    def upper(self): return self.__class__(self.data.upper())
    def zfill(self, width): return self.__class__(self.data.zfill(width))

class MutableString(UserString):
    """mutable string objects

    Python strings are immutable objects.  This has the advantage, that
    strings may be used as dictionary keys.  If this property isn't needed
    and you insist on changing string values in place instead, you may cheat
    and use MutableString.

    But the purpose of this class is an educational one: to prevent
    people from inventing their own mutable string class derived
    from UserString and than forget thereby to remove (override) the
    __hash__ method inherited from UserString.  This would lead to
    errors that would be very hard to track down.

    A faster and better solution is to rewrite your program using lists."""
    def __init__(self, string=""):
        self.data = string
    def __hash__(self):
        raise TypeError("unhashable type (it is mutable)")
    def __setitem__(self, index, sub):
        if index < 0:
            index += len(self.data)
        if index < 0 or index >= len(self.data): raise IndexError
        self.data = self.data[:index] + sub + self.data[index+1:]
    def __delitem__(self, index):
        if index < 0:
            index += len(self.data)
        if index < 0 or index >= len(self.data): raise IndexError
        self.data = self.data[:index] + self.data[index+1:]
    def __setslice__(self, start, end, sub):
        start = max(start, 0); end = max(end, 0)
        if isinstance(sub, UserString):
            self.data = self.data[:start]+sub.data+self.data[end:]
        elif isinstance(sub, str):
            self.data = self.data[:start]+sub+self.data[end:]
        else:
            self.data =  self.data[:start]+str(sub)+self.data[end:]
    def __delslice__(self, start, end):
        start = max(start, 0); end = max(end, 0)
        self.data = self.data[:start] + self.data[end:]
    def immutable(self):
        return UserString(self.data)
    def __iadd__(self, other):
        if isinstance(other, UserString):
            self.data += other.data
        elif isinstance(other, str):
            self.data += other
        else:
            self.data += str(other)
        return self
    def __imul__(self, n):
        self.data *= n
        return self

class String(MutableString, Union):

    _fields_ = [('raw', POINTER(c_char)),
                ('data', c_char_p)]

    def __init__(self, obj=""):
        if isinstance(obj, (str, UserString)):
            self.data = str(obj)
        else:
            self.raw = obj

    def __len__(self):
        return self.data and len(self.data) or 0

    def from_param(cls, obj):
        # Convert None or 0
        if obj is None or obj == 0:
            return cls(POINTER(c_char)())

        # Convert from String
        elif isinstance(obj, String):
            return obj

        # Convert from str
        elif isinstance(obj, str):
            return cls(obj)

        # Convert from c_char_p
        elif isinstance(obj, c_char_p):
            return obj

        # Convert from POINTER(c_char)
        elif isinstance(obj, POINTER(c_char)):
            return obj

        # Convert from raw pointer
        elif isinstance(obj, int):
            return cls(cast(obj, POINTER(c_char)))

        # Convert from object
        else:
            return String.from_param(obj._as_parameter_)
    from_param = classmethod(from_param)

def ReturnString(obj, func=None, arguments=None):
    return String.from_param(obj)

# As of ctypes 1.0, ctypes does not support custom error-checking
# functions on callbacks, nor does it support custom datatypes on
# callbacks, so we must ensure that all callbacks return
# primitive datatypes.
#
# Non-primitive return values wrapped with UNCHECKED won't be
# typechecked, and will be converted to c_void_p.
def UNCHECKED(type):
    if (hasattr(type, "_type_") and isinstance(type._type_, str)
        and type._type_ != "P"):
        return type
    else:
        return c_void_p

# ctypes doesn't have direct support for variadic functions, so we have to write
# our own wrapper class
class _variadic_function(object):
    def __init__(self,func,restype,argtypes):
        self.func=func
        self.func.restype=restype
        self.argtypes=argtypes
    def _as_parameter_(self):
        # So we can pass this variadic function as a function pointer
        return self.func
    def __call__(self,*args):
        fixed_args=[]
        i=0
        for argtype in self.argtypes:
            # Typecheck what we can
            fixed_args.append(argtype.from_param(args[i]))
            i+=1
        return self.func(*fixed_args+list(args[i:]))

# End preamble

_libs = {}
_libdirs = ['/usr/local/lib']

# Begin loader

# ----------------------------------------------------------------------------
# Copyright (c) 2008 David James
# Copyright (c) 2006-2008 Alex Holkner
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of pyglet nor the names of its
#    contributors may be used to endorse or promote products
#    derived from this software without specific prior written
#    permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# ----------------------------------------------------------------------------

import os.path, re, sys, glob
import platform
import ctypes
import logging
import ctypes.util
log = logging.getLogger(__name__)

def _environ_path(name):
    if name in os.environ:
        return os.environ[name].split(":")
    else:
        return []

class LibraryLoader(object):
    def __init__(self):
        self.other_dirs=[]

    def load_library(self,libname):
        """Given the name of a library, load it."""
        paths = self.getpaths(libname)

        for path in paths:
            if os.path.exists(path):
                log.debug("loading library from path: %s" % path)
                return self.load(path)

        raise ImportError("%s not found." % libname)

    def load(self,path):
        """Given a path to a library, load it."""
        try:
            # Darwin requires dlopen to be called with mode RTLD_GLOBAL instead
            # of the default RTLD_LOCAL.  Without this, you end up with
            # libraries not being loadable, resulting in "Symbol not found"
            # errors
            if sys.platform == 'darwin':
                return ctypes.CDLL(path, ctypes.RTLD_GLOBAL)
            else:
                return ctypes.cdll.LoadLibrary(path)
        except OSError as e:
            raise ImportError(e)

    def getpaths(self,libname):
        """Return a list of paths where the library might be found."""
        if os.path.isabs(libname):
            yield libname
        else:
            # FIXME / TODO return '.' and os.path.dirname(__file__)
            for path in self.getplatformpaths(libname):
                yield path

            path = ctypes.util.find_library(libname)
            if path: yield path

    def getplatformpaths(self, libname):
        return []

# Darwin (Mac OS X)

class DarwinLibraryLoader(LibraryLoader):
    name_formats = ["lib%s.dylib", "lib%s.so", "lib%s.bundle", "%s.dylib",
                "%s.so", "%s.bundle", "%s"]

    def getplatformpaths(self,libname):
        if os.path.pathsep in libname:
            names = [libname]
        else:
            names = [format % libname for format in self.name_formats]

        for dir in self.getdirs(libname):
            for name in names:
                yield os.path.join(dir,name)

    def getdirs(self,libname):
        '''Implements the dylib search as specified in Apple documentation:

        http://developer.apple.com/documentation/DeveloperTools/Conceptual/
            DynamicLibraries/Articles/DynamicLibraryUsageGuidelines.html

        Before commencing the standard search, the method first checks
        the bundle's ``Frameworks`` directory if the application is running
        within a bundle (OS X .app).
        '''

        dyld_fallback_library_path = _environ_path("DYLD_FALLBACK_LIBRARY_PATH")
        if not dyld_fallback_library_path:
            dyld_fallback_library_path = [os.path.expanduser('~/lib'),
                                          '/usr/local/lib', '/usr/lib']

        dirs = []

        if '/' in libname:
            dirs.extend(_environ_path("DYLD_LIBRARY_PATH"))
        else:
            dirs.extend(_environ_path("LD_LIBRARY_PATH"))
            dirs.extend(_environ_path("DYLD_LIBRARY_PATH"))

        dirs.extend(self.other_dirs)
        dirs.append(".")
        dirs.append(os.path.dirname(__file__))

        if hasattr(sys, 'frozen') and sys.frozen == 'macosx_app':
            dirs.append(os.path.join(
                os.environ['RESOURCEPATH'],
                '..',
                'Frameworks'))

        dirs.extend(dyld_fallback_library_path)

        return dirs

# Posix

class PosixLibraryLoader(LibraryLoader):
    _ld_so_cache = None

    def _create_ld_so_cache(self):
        # Recreate search path followed by ld.so.  This is going to be
        # slow to build, and incorrect (ld.so uses ld.so.cache, which may
        # not be up-to-date).  Used only as fallback for distros without
        # /sbin/ldconfig.
        #
        # We assume the DT_RPATH and DT_RUNPATH binary sections are omitted.

        directories = []
        for name in ("LD_LIBRARY_PATH",
                     "SHLIB_PATH", # HPUX
                     "LIBPATH", # OS/2, AIX
                     "LIBRARY_PATH", # BE/OS
                    ):
            if name in os.environ:
                directories.extend(os.environ[name].split(os.pathsep))
        directories.extend("/usr/local/lib")
        directories.extend(self.other_dirs)
        directories.append(".")
        directories.append(os.path.dirname(__file__))

        try: directories.extend([dir.strip() for dir in open('/etc/ld.so.conf')])
        except IOError: pass

        unix_lib_dirs_list = ['/lib', '/usr/lib', '/lib64', '/usr/lib64']
        if sys.platform.startswith('linux'):
            # Try and support multiarch work in Ubuntu
            # https://wiki.ubuntu.com/MultiarchSpec
            bitage = platform.architecture()[0]
            if bitage.startswith('32'):
                # Assume Intel/AMD x86 compat
                unix_lib_dirs_list += ['/lib/i386-linux-gnu', '/usr/lib/i386-linux-gnu']
            elif bitage.startswith('64'):
                # Assume Intel/AMD x86 compat
                unix_lib_dirs_list += ['/lib/x86_64-linux-gnu', '/usr/lib/x86_64-linux-gnu']
            else:
                # guess...
                unix_lib_dirs_list += glob.glob('/lib/*linux-gnu')
        directories.extend(unix_lib_dirs_list)

        cache = {}
        lib_re = re.compile(r'lib(.*)\.s[ol]')
        ext_re = re.compile(r'\.s[ol]$')
        for dir in directories:
            try:
                for path in glob.glob("%s/*.s[ol]*" % dir):
                    file = os.path.basename(path)

                    # Index by filename
                    if file not in cache:
                        cache[file] = path

                    # Index by library name
                    match = lib_re.match(file)
                    if match:
                        library = match.group(1)
                        if library not in cache:
                            cache[library] = path
            except OSError:
                pass

        self._ld_so_cache = cache

    def getplatformpaths(self, libname):
        if self._ld_so_cache is None:
            self._create_ld_so_cache()

        result = self._ld_so_cache.get(libname)
        if result: yield result

        path = ctypes.util.find_library(libname)
        if path: yield os.path.join("/lib",path)

# Windows

class _WindowsLibrary(object):
    def __init__(self, path):
        self.cdll = ctypes.cdll.LoadLibrary(path)
        self.windll = ctypes.windll.LoadLibrary(path)

    def __getattr__(self, name):
        try: return getattr(self.cdll,name)
        except AttributeError:
            try: return getattr(self.windll,name)
            except AttributeError:
                raise

class WindowsLibraryLoader(LibraryLoader):
    name_formats = ["%s.dll", "lib%s.dll", "%slib.dll"]

    def load_library(self, libname):
        try:
            result = LibraryLoader.load_library(self, libname)
        except ImportError:
            result = None
            if os.path.sep not in libname:
                for name in self.name_formats:
                    try:
                        result = getattr(ctypes.cdll, name % libname)
                        if result:
                            break
                    except OSError:
                        result = None
            if result is None:
                try:
                    result = getattr(ctypes.cdll, libname)
                except OSError:
                    result = None
            if result is None:
                raise ImportError("%s not found." % libname)
        return result

    def load(self, path):
        return _WindowsLibrary(path)

    def getplatformpaths(self, libname):
        if os.path.sep not in libname:
            for name in self.name_formats:
                dll_in_current_dir = os.path.abspath(name % libname)
                if os.path.exists(dll_in_current_dir):
                    yield dll_in_current_dir
                path = ctypes.util.find_library(name % libname)
                if path:
                    yield path

# Platform switching

# If your value of sys.platform does not appear in this dict, please contact
# the Ctypesgen maintainers.

loaderclass = {
    "darwin":   DarwinLibraryLoader,
    "cygwin":   WindowsLibraryLoader,
    "win32":    WindowsLibraryLoader
}

loader = loaderclass.get(sys.platform, PosixLibraryLoader)()

def add_library_search_dirs(other_dirs):
    loader.other_dirs = other_dirs

load_library = loader.load_library

del loaderclass

# End loader

add_library_search_dirs(['/usr/local/lib'])

# Begin libraries

_libs["sssapisw"] = load_library("sssapisw")

# 1 libraries
# End libraries

# No modules

U8 = c_uint8# ../../hostlib/hostLib/libCommon/infra/sm_types.h

U16 = c_uint16
U32 = c_uint32
enum_anon_6 = c_int # ../../sss/inc/fsl_sss_policy.h

KPolicy_None = 0

KPolicy_Session = (KPolicy_None + 1)

KPolicy_Sym_Key = (KPolicy_Session + 1)

KPolicy_Asym_Key = (KPolicy_Sym_Key + 1)

KPolicy_UserID = (KPolicy_Asym_Key + 1)

KPolicy_File = (KPolicy_UserID + 1)

KPolicy_Counter = (KPolicy_File + 1)

KPolicy_PCR = (KPolicy_Counter + 1)

KPolicy_Common = (KPolicy_PCR + 1)

KPolicy_Common_PCR_Value = (KPolicy_Common + 1)

KPolicy_Desfire_Changekey_Auth_Id = (KPolicy_Common_PCR_Value + 1)

KPolicy_Derive_Master_Key_Id = (KPolicy_Desfire_Changekey_Auth_Id + 1)

sss_policy_type_u = enum_anon_6
class struct_anon_7(Structure):
    pass


struct_anon_7.__slots__ = [
    'maxOperationsInSession',
    'maxDurationOfSession_sec',
    'has_MaxOperationsInSession',
    'has_MaxDurationOfSession_sec',
    'allowRefresh',
]
struct_anon_7._fields_ = [
    ('maxOperationsInSession', c_uint16),
    ('maxDurationOfSession_sec', c_uint16),
    ('has_MaxOperationsInSession', c_uint8, 1),
    ('has_MaxDurationOfSession_sec', c_uint8, 1),
    ('allowRefresh', c_uint8, 1),
]

sss_policy_session_u = struct_anon_7
class struct_anon_8(Structure):
    pass


struct_anon_8.__slots__ = [
    'can_Sign',
    'can_Verify',
    'can_Encrypt',
    'can_Decrypt',
    'can_Import_Export',
    'forbid_Derived_Output',
    'can_TLS_KDF',
    'allow_kdf_ext_rnd',
    'can_TLS_PMS_KD',
    'can_HKDF',
    'can_PBKDF',
    'can_Wrap',
    'can_Desfire_Auth',
    'can_Desfire_Dump',
    'can_Desfire_KD',
    'forbid_external_iv',
    'can_usage_hmac_pepper',
    'can_KD',
    'can_Write',
    'can_Gen',
]
struct_anon_8._fields_ = [
    ('can_Sign', c_uint8, 1),
    ('can_Verify', c_uint8, 1),
    ('can_Encrypt', c_uint8, 1),
    ('can_Decrypt', c_uint8, 1),
    ('can_Import_Export', c_uint8, 1),
    ('forbid_Derived_Output', c_uint8, 1),
    ('can_TLS_KDF', c_uint8, 1),
    ('allow_kdf_ext_rnd', c_uint8, 1),
    ('can_TLS_PMS_KD', c_uint8, 1),
    ('can_HKDF', c_uint8, 1),
    ('can_PBKDF', c_uint8, 1),
    ('can_Wrap', c_uint8, 1),
    ('can_Desfire_Auth', c_uint8, 1),
    ('can_Desfire_Dump', c_uint8, 1),
    ('can_Desfire_KD', c_uint8, 1),
    ('forbid_external_iv', c_uint8, 1),
    ('can_usage_hmac_pepper', c_uint8, 1),
    ('can_KD', c_uint8, 1),
    ('can_Write', c_uint8, 1),
    ('can_Gen', c_uint8, 1),
]

sss_policy_sym_key_u = struct_anon_8
class struct_anon_9(Structure):
    pass


struct_anon_9.__slots__ = [
    'can_Sign',
    'can_Verify',
    'can_Encrypt',
    'can_Decrypt',
    'can_Import_Export',
    'forbid_Derived_Output',
    'can_Gen',
    'can_KA',
    'can_Attest',
    'can_Read',
    'can_Write',
    'can_KD',
    'can_Wrap',
]
struct_anon_9._fields_ = [
    ('can_Sign', c_uint8, 1),
    ('can_Verify', c_uint8, 1),
    ('can_Encrypt', c_uint8, 1),
    ('can_Decrypt', c_uint8, 1),
    ('can_Import_Export', c_uint8, 1),
    ('forbid_Derived_Output', c_uint8, 1),
    ('can_Gen', c_uint8, 1),
    ('can_KA', c_uint8, 1),
    ('can_Attest', c_uint8, 1),
    ('can_Read', c_uint8, 1),
    ('can_Write', c_uint8, 1),
    ('can_KD', c_uint8, 1),
    ('can_Wrap', c_uint8, 1),
]

sss_policy_asym_key_u = struct_anon_9
class struct_anon_10(Structure):
    pass


struct_anon_10.__slots__ = [
    'can_Write',
    'can_Read',
]
struct_anon_10._fields_ = [
    ('can_Write', c_uint8, 1),
    ('can_Read', c_uint8, 1),
]

sss_policy_file_u = struct_anon_10
class struct_anon_11(Structure):
    pass


struct_anon_11.__slots__ = [
    'can_Write',
    'can_Read',
]
struct_anon_11._fields_ = [
    ('can_Write', c_uint8, 1),
    ('can_Read', c_uint8, 1),
]

sss_policy_counter_u = struct_anon_11
class struct_anon_12(Structure):
    pass


struct_anon_12.__slots__ = [
    'can_Write',
    'can_Read',
]
struct_anon_12._fields_ = [
    ('can_Write', c_uint8, 1),
    ('can_Read', c_uint8, 1),
]

sss_policy_pcr_u = struct_anon_12
class struct_anon_13(Structure):
    pass


struct_anon_13.__slots__ = [
    'can_Write',
]
struct_anon_13._fields_ = [
    ('can_Write', c_uint8, 1),
]

sss_policy_userid_u = struct_anon_13
class struct_anon_14(Structure):
    pass


struct_anon_14.__slots__ = [
    'forbid_All',
    'can_Read',
    'can_Write',
    'can_Delete',
    'req_Sm',
    'req_pcr_val',
]
struct_anon_14._fields_ = [
    ('forbid_All', c_uint8, 1),
    ('can_Read', c_uint8, 1),
    ('can_Write', c_uint8, 1),
    ('can_Delete', c_uint8, 1),
    ('req_Sm', c_uint8, 1),
    ('req_pcr_val', c_uint8, 1),
]

sss_policy_common_u = struct_anon_14
class struct_anon_15(Structure):
    pass


struct_anon_15.__slots__ = [
    'pcrObjId',
    'pcrExpectedValue',
]
struct_anon_15._fields_ = [
    ('pcrObjId', c_uint32),
    ('pcrExpectedValue', c_uint8 * 32),
]

sss_policy_common_pcr_value_u = struct_anon_15
class struct_anon_16(Structure):
    pass


struct_anon_16.__slots__ = [
    'desfire_authId',
]
struct_anon_16._fields_ = [
    ('desfire_authId', c_uint32),
]

sss_policy_desfire_changekey_authId_value_u = struct_anon_16
class struct_anon_17(Structure):
    pass


struct_anon_17.__slots__ = [
    'master_keyId',
]
struct_anon_17._fields_ = [
    ('master_keyId', c_uint32),
]

sss_policy_key_drv_master_keyid_value_u = struct_anon_17
class union_anon_18(Union):
    pass


union_anon_18.__slots__ = [
    'file',
    'counter',
    'pcr',
    'symmkey',
    'asymmkey',
    'pin',
    'common',
    'common_pcr_value',
    'session',
    'desfire_auth_id',
    'master_key_id',
]
union_anon_18._fields_ = [
    ('file', sss_policy_file_u),
    ('counter', sss_policy_counter_u),
    ('pcr', sss_policy_pcr_u),
    ('symmkey', sss_policy_sym_key_u),
    ('asymmkey', sss_policy_asym_key_u),
    ('pin', sss_policy_userid_u),
    ('common', sss_policy_common_u),
    ('common_pcr_value', sss_policy_common_pcr_value_u),
    ('session', sss_policy_session_u),
    ('desfire_auth_id', sss_policy_desfire_changekey_authId_value_u),
    ('master_key_id', sss_policy_key_drv_master_keyid_value_u),
]

class struct_anon_19(Structure):
    pass


struct_anon_19.__slots__ = [
    'type',
    'auth_obj_id',
    'policy',
]
struct_anon_19._fields_ = [
    ('type', sss_policy_type_u),
    ('auth_obj_id', c_uint32),
    ('policy', union_anon_18),
]

sss_policy_u = struct_anon_19
class struct_anon_20(Structure):
    pass


struct_anon_20.__slots__ = [
    'policies',
    'nPolicies',
]
struct_anon_20._fields_ = [
    ('policies', POINTER(sss_policy_u) * 10),
    ('nPolicies', c_size_t),
]

sss_policy_t = struct_anon_20
enum_anon_21 = c_int # ../../sss/inc/fsl_sss_api.h

kStatus_SSS_Success = 1515870810

kStatus_SSS_Fail = 1010565120

kStatus_SSS_InvalidArgument = 1010565121

kStatus_SSS_ResourceBusy = 1010565122

sss_status_t = enum_anon_21
enum_anon_22 = c_int 
kType_SSS_SubSystem_NONE = 0

kType_SSS_Software = ((1 << 8) | 0)

kType_SSS_mbedTLS = (kType_SSS_Software | 1)

kType_SSS_OpenSSL = (kType_SSS_Software | 2)

kType_SSS_HW = ((2 << 8) | 0)

kType_SSS_SECO = (kType_SSS_HW | 1)

kType_SSS_Isolated_HW = ((4 << 8) | 0)

kType_SSS_Sentinel = (kType_SSS_Isolated_HW | 1)

kType_SSS_Sentinel200 = (kType_SSS_Isolated_HW | 2)

kType_SSS_Sentinel300 = (kType_SSS_Isolated_HW | 3)

kType_SSS_Sentinel400 = (kType_SSS_Isolated_HW | 4)

kType_SSS_Sentinel500 = (kType_SSS_Isolated_HW | 5)

kType_SSS_SecureElement = ((8 << 8) | 0)

kType_SSS_SE_A71CH = (kType_SSS_SecureElement | 1)

kType_SSS_SE_A71CL = (kType_SSS_SecureElement | 2)

kType_SSS_SE_SE05x = (kType_SSS_SecureElement | 3)

kType_SSS_SubSystem_LAST = (kType_SSS_SE_SE05x + 1)

sss_type_t = enum_anon_22
enum_anon_23 = c_int 
kSSS_ConnectionType_Plain = 0

kSSS_ConnectionType_Password = (kSSS_ConnectionType_Plain + 1)

kSSS_ConnectionType_Encrypted = (kSSS_ConnectionType_Password + 1)

sss_connection_type_t = enum_anon_23
enum_anon_24 = c_int 
kAlgorithm_None = 0

kAlgorithm_SSS_AES_ECB = ((0 << 8) | 1)

kAlgorithm_SSS_AES_CBC = ((0 << 8) | 2)

kAlgorithm_SSS_AES_CTR = ((0 << 8) | 3)

kAlgorithm_SSS_AES_GCM = ((0 << 8) | 4)

kAlgorithm_SSS_AES_CCM = ((0 << 8) | 5)

kAlgorithm_SSS_AES_GCM_INT_IV = ((0 << 8) | 6)

kAlgorithm_SSS_AES_CTR_INT_IV = ((0 << 8) | 7)

kAlgorithm_SSS_AES_CCM_INT_IV = ((0 << 8) | 8)

kAlgorithm_SSS_CHACHA_POLY = ((1 << 8) | 1)

kAlgorithm_SSS_DES_ECB = ((2 << 8) | 1)

kAlgorithm_SSS_DES_CBC = ((2 << 8) | 2)

kAlgorithm_SSS_DES_CBC_ISO9797_M1 = ((2 << 8) | 5)

kAlgorithm_SSS_DES_CBC_ISO9797_M2 = ((2 << 8) | 6)

kAlgorithm_SSS_DES3_ECB = ((2 << 8) | 3)

kAlgorithm_SSS_DES3_CBC = ((2 << 8) | 4)

kAlgorithm_SSS_DES3_CBC_ISO9797_M1 = ((2 << 8) | 7)

kAlgorithm_SSS_DES3_CBC_ISO9797_M2 = ((2 << 8) | 8)

kAlgorithm_SSS_SHA1 = ((3 << 8) | 1)

kAlgorithm_SSS_SHA224 = ((3 << 8) | 2)

kAlgorithm_SSS_SHA256 = ((3 << 8) | 3)

kAlgorithm_SSS_SHA384 = ((3 << 8) | 4)

kAlgorithm_SSS_SHA512 = ((3 << 8) | 5)

kAlgorithm_SSS_CMAC_AES = ((4 << 8) | 1)

kAlgorithm_SSS_HMAC_SHA1 = ((4 << 8) | 2)

kAlgorithm_SSS_HMAC_SHA224 = ((4 << 8) | 3)

kAlgorithm_SSS_HMAC_SHA256 = ((4 << 8) | 4)

kAlgorithm_SSS_HMAC_SHA384 = ((4 << 8) | 5)

kAlgorithm_SSS_HMAC_SHA512 = ((4 << 8) | 6)

kAlgorithm_SSS_DES_CMAC8 = ((4 << 8) | 7)

kAlgorithm_SSS_DH = ((5 << 8) | 1)

kAlgorithm_SSS_ECDH = ((5 << 8) | 2)

kAlgorithm_SSS_DSA_SHA1 = ((6 << 8) | 1)

kAlgorithm_SSS_DSA_SHA224 = ((6 << 8) | 2)

kAlgorithm_SSS_DSA_SHA256 = ((6 << 8) | 3)

kAlgorithm_SSS_RSASSA_PKCS1_V1_5_NO_HASH = ((7 << 8) | 1)

kAlgorithm_SSS_RSASSA_PKCS1_V1_5_SHA1 = ((7 << 8) | 2)

kAlgorithm_SSS_RSASSA_PKCS1_V1_5_SHA224 = ((7 << 8) | 3)

kAlgorithm_SSS_RSASSA_PKCS1_V1_5_SHA256 = ((7 << 8) | 4)

kAlgorithm_SSS_RSASSA_PKCS1_V1_5_SHA384 = ((7 << 8) | 5)

kAlgorithm_SSS_RSASSA_PKCS1_V1_5_SHA512 = ((7 << 8) | 6)

kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA1 = ((8 << 8) | 1)

kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA224 = ((8 << 8) | 2)

kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA256 = ((8 << 8) | 3)

kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA384 = ((8 << 8) | 4)

kAlgorithm_SSS_RSASSA_PKCS1_PSS_MGF1_SHA512 = ((8 << 8) | 5)

kAlgorithm_SSS_RSAES_PKCS1_OAEP_SHA1 = ((9 << 8) | 1)

kAlgorithm_SSS_RSAES_PKCS1_OAEP_SHA224 = ((9 << 8) | 2)

kAlgorithm_SSS_RSAES_PKCS1_OAEP_SHA256 = ((9 << 8) | 3)

kAlgorithm_SSS_RSAES_PKCS1_OAEP_SHA384 = ((9 << 8) | 4)

kAlgorithm_SSS_RSAES_PKCS1_OAEP_SHA512 = ((9 << 8) | 5)

kAlgorithm_SSS_RSAES_PKCS1_V1_5 = ((10 << 8) | 1)

kAlgorithm_SSS_RSASSA_NO_PADDING = ((11 << 8) | 1)

kAlgorithm_SSS_ECDSA_SHA1 = ((12 << 8) | 1)

kAlgorithm_SSS_ECDSA_SHA224 = ((12 << 8) | 2)

kAlgorithm_SSS_ECDSA_SHA256 = ((12 << 8) | 3)

kAlgorithm_SSS_ECDSA_SHA384 = ((12 << 8) | 4)

kAlgorithm_SSS_ECDSA_SHA512 = ((12 << 8) | 5)

kAlgorithm_SSS_ECDAA = ((13 << 8) | 1)

sss_algorithm_t = enum_anon_24
enum_anon_25 = c_int 
kMode_SSS_Encrypt = 1

kMode_SSS_Decrypt = 2

kMode_SSS_Sign = 3

kMode_SSS_Verify = 4

kMode_SSS_ComputeSharedSecret = 5

kMode_SSS_Digest = 6

kMode_SSS_Mac = 7

kMode_SSS_HKDF_ExpandOnly = 9

kMode_SSS_HKDF_ExtractExpand = 10

kMode_SSS_Mac_Validate = 11

sss_mode_t = enum_anon_25
enum_anon_26 = c_int 
kAccessPermission_SSS_Read = (1 << 0)

kAccessPermission_SSS_Write = (1 << 1)

kAccessPermission_SSS_Use = (1 << 2)

kAccessPermission_SSS_Delete = (1 << 3)

kAccessPermission_SSS_ChangeAttributes = (1 << 4)

kAccessPermission_SSS_All_Permission = 31

sss_access_permission_t = enum_anon_26
enum_anon_27 = c_int 
kKeyObject_Mode_None = 0

kKeyObject_Mode_Persistent = 1

kKeyObject_Mode_Transient = 2

sss_key_object_mode_t = enum_anon_27
enum_anon_28 = c_int 
kSSS_KeyPart_NONE = 0

kSSS_KeyPart_Default = 1

kSSS_KeyPart_Public = 2

kSSS_KeyPart_Private = 3

kSSS_KeyPart_Pair = 4

sss_key_part_t = enum_anon_28
enum_anon_29 = c_int 
kSSS_CipherType_NONE = 0

kSSS_CipherType_AES = 10

kSSS_CipherType_DES = 12

kSSS_CipherType_CMAC = 20

kSSS_CipherType_HMAC = 21

kSSS_CipherType_MAC = 30

kSSS_CipherType_RSA = 31

kSSS_CipherType_RSA_CRT = 32

kSSS_CipherType_EC_NIST_P = 40

kSSS_CipherType_EC_NIST_K = 41

kSSS_CipherType_EC_MONTGOMERY = 50

kSSS_CipherType_EC_TWISTED_ED = 51

kSSS_CipherType_EC_BRAINPOOL = 52

kSSS_CipherType_EC_BARRETO_NAEHRIG = 53

kSSS_CipherType_UserID = 70

kSSS_CipherType_Certificate = 71

kSSS_CipherType_Binary = 72

kSSS_CipherType_Count = 73

kSSS_CipherType_PCR = 74

kSSS_CipherType_ReservedPin = 75

sss_cipher_type_t = enum_anon_29
class struct_anon_30(Structure):
    pass


struct_anon_30.__slots__ = [
    'X',
    'Y',
]
struct_anon_30._fields_ = [
    ('X', POINTER(c_uint8)),
    ('Y', POINTER(c_uint8)),
]

sss_ecc_point_t = struct_anon_30
class struct_anon_31(Structure):
    pass


struct_anon_31.__slots__ = [
    'p',
    'a',
    'b',
    'G',
    'n',
    'h',
]
struct_anon_31._fields_ = [
    ('p', POINTER(c_uint8)),
    ('a', POINTER(c_uint8)),
    ('b', POINTER(c_uint8)),
    ('G', POINTER(sss_ecc_point_t)),
    ('n', POINTER(c_uint8)),
    ('h', POINTER(c_uint8)),
]

sss_eccgfp_group_t = struct_anon_31
enum_anon_32 = c_int 
kSSS_SessionProp_u32_NA = 0

kSSS_SessionProp_VerMaj = (kSSS_SessionProp_u32_NA + 1)

kSSS_SessionProp_VerMin = (kSSS_SessionProp_VerMaj + 1)

kSSS_SessionProp_VerDev = (kSSS_SessionProp_VerMin + 1)

kSSS_SessionProp_UIDLen = (kSSS_SessionProp_VerDev + 1)

kSSS_SessionProp_u32_Optional_Start = 16777215

kSSS_KeyStoreProp_FreeMem_Persistant = (kSSS_SessionProp_u32_Optional_Start + 1)

kSSS_KeyStoreProp_FreeMem_Transient = (kSSS_KeyStoreProp_FreeMem_Persistant + 1)

kSSS_SessionProp_u32_Proprietary_Start = 33554431

sss_session_prop_u32_t = enum_anon_32
enum_anon_33 = c_int 
kSSS_SessionProp_au8_NA = 0

kSSS_SessionProp_szName = (kSSS_SessionProp_au8_NA + 1)

kSSS_SessionProp_UID = (kSSS_SessionProp_szName + 1)

kSSS_SessionProp_au8_Optional_Start = 16777215

kSSS_SessionProp_au8_Proprietary_Start = 33554431

sss_session_prop_au8_t = enum_anon_33
class struct_anon_34(Structure):
    pass


struct_anon_34.__slots__ = [
    'data',
]
struct_anon_34._fields_ = [
    ('data', c_uint8 * ((((0 + (1 * sizeof(POINTER(None)))) + (1 * sizeof(POINTER(None)))) + (8 * sizeof(POINTER(None)))) + 32)),
]

class struct_anon_35(Structure):
    pass


struct_anon_35.__slots__ = [
    'subsystem',
    'extension',
]
struct_anon_35._fields_ = [
    ('subsystem', sss_type_t),
    ('extension', struct_anon_34),
]

sss_session_t = struct_anon_35
class struct_anon_36(Structure):
    pass


struct_anon_36.__slots__ = [
    'data',
]
struct_anon_36._fields_ = [
    ('data', c_uint8 * (((0 + (1 * sizeof(POINTER(None)))) + (4 * sizeof(POINTER(None)))) + 32)),
]

class struct_anon_37(Structure):
    pass


struct_anon_37.__slots__ = [
    'session',
    'extension',
]
struct_anon_37._fields_ = [
    ('session', POINTER(sss_session_t)),
    ('extension', struct_anon_36),
]

sss_key_store_t = struct_anon_37
enum_anon_38 = c_int 
kSSS_KeyStoreProp_au8_Optional_Start = 16777215

sss_key_store_prop_au8_t = enum_anon_38
enum_anon_39 = c_int 
kSSS_TunnelDest_None = 0

kSSS_TunnelType_Se05x_Iot_applet = (kSSS_TunnelDest_None + 1)

sss_tunnel_dest_t = enum_anon_39
class struct_anon_40(Structure):
    pass


struct_anon_40.__slots__ = [
    'data',
]
struct_anon_40._fields_ = [
    ('data', c_uint8 * ((((0 + (1 * sizeof(POINTER(None)))) + (2 * sizeof(c_int))) + (4 * sizeof(POINTER(None)))) + 32)),
]

class struct_anon_41(Structure):
    pass


struct_anon_41.__slots__ = [
    'keyStore',
    'objectType',
    'cipherType',
    'keyId',
    'extension',
]
struct_anon_41._fields_ = [
    ('keyStore', POINTER(sss_key_store_t)),
    ('objectType', c_uint32),
    ('cipherType', c_uint32),
    ('keyId', c_uint32),
    ('extension', struct_anon_40),
]

sss_object_t = struct_anon_41
class struct_anon_42(Structure):
    pass


struct_anon_42.__slots__ = [
    'data',
]
struct_anon_42._fields_ = [
    ('data', c_uint8 * ((((((0 + (2 * sizeof(POINTER(None)))) + (2 * sizeof(c_int))) + (2 * sizeof(POINTER(None)))) + 16) + 4) + 32)),
]

class struct_anon_43(Structure):
    pass


struct_anon_43.__slots__ = [
    'session',
    'keyObject',
    'algorithm',
    'mode',
    'extension',
]
struct_anon_43._fields_ = [
    ('session', POINTER(sss_session_t)),
    ('keyObject', POINTER(sss_object_t)),
    ('algorithm', sss_algorithm_t),
    ('mode', sss_mode_t),
    ('extension', struct_anon_42),
]

sss_symmetric_t = struct_anon_43
class struct_anon_44(Structure):
    pass


struct_anon_44.__slots__ = [
    'data',
]
struct_anon_44._fields_ = [
    ('data', c_uint8 * ((((0 + (5 * sizeof(POINTER(None)))) + (6 * sizeof(c_int))) + (5 * sizeof(POINTER(None)))) + 32)),
]

class struct_anon_45(Structure):
    pass


struct_anon_45.__slots__ = [
    'session',
    'keyObject',
    'algorithm',
    'mode',
    'extension',
]
struct_anon_45._fields_ = [
    ('session', POINTER(sss_session_t)),
    ('keyObject', POINTER(sss_object_t)),
    ('algorithm', sss_algorithm_t),
    ('mode', sss_mode_t),
    ('extension', struct_anon_44),
]

sss_aead_t = struct_anon_45
class struct_anon_46(Structure):
    pass


struct_anon_46.__slots__ = [
    'data',
]
struct_anon_46._fields_ = [
    ('data', c_uint8 * ((((0 + (1 * sizeof(POINTER(None)))) + (3 * sizeof(c_int))) + (2 * sizeof(POINTER(None)))) + 32)),
]

class struct_anon_47(Structure):
    pass


struct_anon_47.__slots__ = [
    'session',
    'algorithm',
    'mode',
    'digestFullLen',
    'extension',
]
struct_anon_47._fields_ = [
    ('session', POINTER(sss_session_t)),
    ('algorithm', sss_algorithm_t),
    ('mode', sss_mode_t),
    ('digestFullLen', c_size_t),
    ('extension', struct_anon_46),
]

sss_digest_t = struct_anon_47
class struct_anon_48(Structure):
    pass


struct_anon_48.__slots__ = [
    'data',
]
struct_anon_48._fields_ = [
    ('data', c_uint8 * ((((0 + (2 * sizeof(POINTER(None)))) + (2 * sizeof(c_int))) + (2 * sizeof(POINTER(None)))) + 32)),
]

class struct_anon_49(Structure):
    pass


struct_anon_49.__slots__ = [
    'session',
    'keyObject',
    'algorithm',
    'mode',
    'extension',
]
struct_anon_49._fields_ = [
    ('session', POINTER(sss_session_t)),
    ('keyObject', POINTER(sss_object_t)),
    ('algorithm', sss_algorithm_t),
    ('mode', sss_mode_t),
    ('extension', struct_anon_48),
]

sss_mac_t = struct_anon_49
class struct_anon_50(Structure):
    pass


struct_anon_50.__slots__ = [
    'data',
]
struct_anon_50._fields_ = [
    ('data', c_uint8 * ((((0 + (2 * sizeof(POINTER(None)))) + (3 * sizeof(c_int))) + (2 * sizeof(POINTER(None)))) + 32)),
]

class struct_anon_51(Structure):
    pass


struct_anon_51.__slots__ = [
    'session',
    'keyObject',
    'algorithm',
    'mode',
    'extension',
]
struct_anon_51._fields_ = [
    ('session', POINTER(sss_session_t)),
    ('keyObject', POINTER(sss_object_t)),
    ('algorithm', sss_algorithm_t),
    ('mode', sss_mode_t),
    ('extension', struct_anon_50),
]

sss_asymmetric_t = struct_anon_51
class struct_anon_52(Structure):
    pass


struct_anon_52.__slots__ = [
    'hdr',
]
struct_anon_52._fields_ = [
    ('hdr', c_uint8 * ((((0 + 1) + 1) + 1) + 1)),
]

tlvHeader_t = struct_anon_52
class struct_anon_53(Structure):
    pass


struct_anon_53.__slots__ = [
    'data',
]
struct_anon_53._fields_ = [
    ('data', c_uint8 * ((((0 + (1 * sizeof(POINTER(None)))) + (2 * sizeof(c_int))) + (2 * sizeof(POINTER(None)))) + 32)),
]

class struct_anon_54(Structure):
    pass


struct_anon_54.__slots__ = [
    'session',
    'tunnelType',
    'extension',
]
struct_anon_54._fields_ = [
    ('session', POINTER(sss_session_t)),
    ('tunnelType', c_uint32),
    ('extension', struct_anon_53),
]

sss_tunnel_t = struct_anon_54
class struct_anon_55(Structure):
    pass


struct_anon_55.__slots__ = [
    'data',
]
struct_anon_55._fields_ = [
    ('data', c_uint8 * ((((0 + (2 * sizeof(POINTER(None)))) + (2 * sizeof(c_int))) + (2 * sizeof(POINTER(None)))) + 32)),
]

class struct_anon_56(Structure):
    pass


struct_anon_56.__slots__ = [
    'session',
    'keyObject',
    'algorithm',
    'mode',
    'extension',
]
struct_anon_56._fields_ = [
    ('session', POINTER(sss_session_t)),
    ('keyObject', POINTER(sss_object_t)),
    ('algorithm', sss_algorithm_t),
    ('mode', sss_mode_t),
    ('extension', struct_anon_55),
]

sss_derive_key_t = struct_anon_56
class struct_anon_57(Structure):
    pass


struct_anon_57.__slots__ = [
    'data',
]
struct_anon_57._fields_ = [
    ('data', c_uint8 * (((0 + (1 * sizeof(POINTER(None)))) + (2 * sizeof(POINTER(None)))) + 32)),
]

class struct_anon_58(Structure):
    pass


struct_anon_58.__slots__ = [
    'session',
    'context',
]
struct_anon_58._fields_ = [
    ('session', POINTER(sss_session_t)),
    ('context', struct_anon_57),
]

sss_rng_context_t = struct_anon_58
for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_session_create'):
        continue
    sss_session_create = _lib.sss_session_create
    sss_session_create.argtypes = [POINTER(sss_session_t), sss_type_t, c_uint32, sss_connection_type_t, POINTER(None)]
    sss_session_create.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_session_open'):
        continue
    sss_session_open = _lib.sss_session_open
    sss_session_open.argtypes = [POINTER(sss_session_t), sss_type_t, c_uint32, sss_connection_type_t, POINTER(None)]
    sss_session_open.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_session_prop_get_u32'):
        continue
    sss_session_prop_get_u32 = _lib.sss_session_prop_get_u32
    sss_session_prop_get_u32.argtypes = [POINTER(sss_session_t), c_uint32, POINTER(c_uint32)]
    sss_session_prop_get_u32.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_session_prop_get_au8'):
        continue
    sss_session_prop_get_au8 = _lib.sss_session_prop_get_au8
    sss_session_prop_get_au8.argtypes = [POINTER(sss_session_t), c_uint32, POINTER(c_uint8), POINTER(c_size_t)]
    sss_session_prop_get_au8.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_session_close'):
        continue
    sss_session_close = _lib.sss_session_close
    sss_session_close.argtypes = [POINTER(sss_session_t)]
    sss_session_close.restype = None
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_session_delete'):
        continue
    sss_session_delete = _lib.sss_session_delete
    sss_session_delete.argtypes = [POINTER(sss_session_t)]
    sss_session_delete.restype = None
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_store_context_init'):
        continue
    sss_key_store_context_init = _lib.sss_key_store_context_init
    sss_key_store_context_init.argtypes = [POINTER(sss_key_store_t), POINTER(sss_session_t)]
    sss_key_store_context_init.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_store_allocate'):
        continue
    sss_key_store_allocate = _lib.sss_key_store_allocate
    sss_key_store_allocate.argtypes = [POINTER(sss_key_store_t), c_uint32]
    sss_key_store_allocate.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_store_save'):
        continue
    sss_key_store_save = _lib.sss_key_store_save
    sss_key_store_save.argtypes = [POINTER(sss_key_store_t)]
    sss_key_store_save.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_store_load'):
        continue
    sss_key_store_load = _lib.sss_key_store_load
    sss_key_store_load.argtypes = [POINTER(sss_key_store_t)]
    sss_key_store_load.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_store_set_key'):
        continue
    sss_key_store_set_key = _lib.sss_key_store_set_key
    sss_key_store_set_key.argtypes = [POINTER(sss_key_store_t), POINTER(sss_object_t), POINTER(c_uint8), c_size_t, c_size_t, POINTER(None), c_size_t]
    sss_key_store_set_key.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_store_generate_key'):
        continue
    sss_key_store_generate_key = _lib.sss_key_store_generate_key
    sss_key_store_generate_key.argtypes = [POINTER(sss_key_store_t), POINTER(sss_object_t), c_size_t, POINTER(None)]
    sss_key_store_generate_key.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_store_get_key'):
        continue
    sss_key_store_get_key = _lib.sss_key_store_get_key
    sss_key_store_get_key.argtypes = [POINTER(sss_key_store_t), POINTER(sss_object_t), POINTER(c_uint8), POINTER(c_size_t), POINTER(c_size_t)]
    sss_key_store_get_key.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_store_open_key'):
        continue
    sss_key_store_open_key = _lib.sss_key_store_open_key
    sss_key_store_open_key.argtypes = [POINTER(sss_key_store_t), POINTER(sss_object_t)]
    sss_key_store_open_key.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_store_freeze_key'):
        continue
    sss_key_store_freeze_key = _lib.sss_key_store_freeze_key
    sss_key_store_freeze_key.argtypes = [POINTER(sss_key_store_t), POINTER(sss_object_t)]
    sss_key_store_freeze_key.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_store_erase_key'):
        continue
    sss_key_store_erase_key = _lib.sss_key_store_erase_key
    sss_key_store_erase_key.argtypes = [POINTER(sss_key_store_t), POINTER(sss_object_t)]
    sss_key_store_erase_key.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_store_context_free'):
        continue
    sss_key_store_context_free = _lib.sss_key_store_context_free
    sss_key_store_context_free.argtypes = [POINTER(sss_key_store_t)]
    sss_key_store_context_free.restype = None
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_object_init'):
        continue
    sss_key_object_init = _lib.sss_key_object_init
    sss_key_object_init.argtypes = [POINTER(sss_object_t), POINTER(sss_key_store_t)]
    sss_key_object_init.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_object_allocate_handle'):
        continue
    sss_key_object_allocate_handle = _lib.sss_key_object_allocate_handle
    sss_key_object_allocate_handle.argtypes = [POINTER(sss_object_t), c_uint32, sss_key_part_t, sss_cipher_type_t, c_size_t, c_uint32]
    sss_key_object_allocate_handle.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_object_get_handle'):
        continue
    sss_key_object_get_handle = _lib.sss_key_object_get_handle
    sss_key_object_get_handle.argtypes = [POINTER(sss_object_t), c_uint32]
    sss_key_object_get_handle.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_object_set_user'):
        continue
    sss_key_object_set_user = _lib.sss_key_object_set_user
    sss_key_object_set_user.argtypes = [POINTER(sss_object_t), c_uint32, c_uint32]
    sss_key_object_set_user.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_object_set_purpose'):
        continue
    sss_key_object_set_purpose = _lib.sss_key_object_set_purpose
    sss_key_object_set_purpose.argtypes = [POINTER(sss_object_t), sss_mode_t, c_uint32]
    sss_key_object_set_purpose.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_object_set_access'):
        continue
    sss_key_object_set_access = _lib.sss_key_object_set_access
    sss_key_object_set_access.argtypes = [POINTER(sss_object_t), c_uint32, c_uint32]
    sss_key_object_set_access.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_object_set_eccgfp_group'):
        continue
    sss_key_object_set_eccgfp_group = _lib.sss_key_object_set_eccgfp_group
    sss_key_object_set_eccgfp_group.argtypes = [POINTER(sss_object_t), POINTER(sss_eccgfp_group_t)]
    sss_key_object_set_eccgfp_group.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_object_get_user'):
        continue
    sss_key_object_get_user = _lib.sss_key_object_get_user
    sss_key_object_get_user.argtypes = [POINTER(sss_object_t), POINTER(c_uint32)]
    sss_key_object_get_user.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_object_get_purpose'):
        continue
    sss_key_object_get_purpose = _lib.sss_key_object_get_purpose
    sss_key_object_get_purpose.argtypes = [POINTER(sss_object_t), POINTER(sss_mode_t)]
    sss_key_object_get_purpose.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_object_get_access'):
        continue
    sss_key_object_get_access = _lib.sss_key_object_get_access
    sss_key_object_get_access.argtypes = [POINTER(sss_object_t), POINTER(c_uint32)]
    sss_key_object_get_access.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_key_object_free'):
        continue
    sss_key_object_free = _lib.sss_key_object_free
    sss_key_object_free.argtypes = [POINTER(sss_object_t)]
    sss_key_object_free.restype = None
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_symmetric_context_init'):
        continue
    sss_symmetric_context_init = _lib.sss_symmetric_context_init
    sss_symmetric_context_init.argtypes = [POINTER(sss_symmetric_t), POINTER(sss_session_t), POINTER(sss_object_t), sss_algorithm_t, sss_mode_t]
    sss_symmetric_context_init.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_cipher_one_go'):
        continue
    sss_cipher_one_go = _lib.sss_cipher_one_go
    sss_cipher_one_go.argtypes = [POINTER(sss_symmetric_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_uint8), c_size_t]
    sss_cipher_one_go.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_cipher_one_go_v2'):
        continue
    sss_cipher_one_go_v2 = _lib.sss_cipher_one_go_v2
    sss_cipher_one_go_v2.argtypes = [POINTER(sss_symmetric_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t)]
    sss_cipher_one_go_v2.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_cipher_init'):
        continue
    sss_cipher_init = _lib.sss_cipher_init
    sss_cipher_init.argtypes = [POINTER(sss_symmetric_t), POINTER(c_uint8), c_size_t]
    sss_cipher_init.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_cipher_update'):
        continue
    sss_cipher_update = _lib.sss_cipher_update
    sss_cipher_update.argtypes = [POINTER(sss_symmetric_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t)]
    sss_cipher_update.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_cipher_finish'):
        continue
    sss_cipher_finish = _lib.sss_cipher_finish
    sss_cipher_finish.argtypes = [POINTER(sss_symmetric_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t)]
    sss_cipher_finish.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_cipher_crypt_ctr'):
        continue
    sss_cipher_crypt_ctr = _lib.sss_cipher_crypt_ctr
    sss_cipher_crypt_ctr.argtypes = [POINTER(sss_symmetric_t), POINTER(c_uint8), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_uint8), POINTER(c_size_t)]
    sss_cipher_crypt_ctr.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_symmetric_context_free'):
        continue
    sss_symmetric_context_free = _lib.sss_symmetric_context_free
    sss_symmetric_context_free.argtypes = [POINTER(sss_symmetric_t)]
    sss_symmetric_context_free.restype = None
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_aead_context_init'):
        continue
    sss_aead_context_init = _lib.sss_aead_context_init
    sss_aead_context_init.argtypes = [POINTER(sss_aead_t), POINTER(sss_session_t), POINTER(sss_object_t), sss_algorithm_t, sss_mode_t]
    sss_aead_context_init.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_aead_one_go'):
        continue
    sss_aead_one_go = _lib.sss_aead_one_go
    sss_aead_one_go.argtypes = [POINTER(sss_aead_t), POINTER(c_uint8), POINTER(c_uint8), c_size_t, POINTER(c_uint8), c_size_t, POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t)]
    sss_aead_one_go.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_aead_init'):
        continue
    sss_aead_init = _lib.sss_aead_init
    sss_aead_init.argtypes = [POINTER(sss_aead_t), POINTER(c_uint8), c_size_t, c_size_t, c_size_t, c_size_t]
    sss_aead_init.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_aead_update_aad'):
        continue
    sss_aead_update_aad = _lib.sss_aead_update_aad
    sss_aead_update_aad.argtypes = [POINTER(sss_aead_t), POINTER(c_uint8), c_size_t]
    sss_aead_update_aad.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_aead_update'):
        continue
    sss_aead_update = _lib.sss_aead_update
    sss_aead_update.argtypes = [POINTER(sss_aead_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t)]
    sss_aead_update.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_aead_finish'):
        continue
    sss_aead_finish = _lib.sss_aead_finish
    sss_aead_finish.argtypes = [POINTER(sss_aead_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t), POINTER(c_uint8), POINTER(c_size_t)]
    sss_aead_finish.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_aead_context_free'):
        continue
    sss_aead_context_free = _lib.sss_aead_context_free
    sss_aead_context_free.argtypes = [POINTER(sss_aead_t)]
    sss_aead_context_free.restype = None
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_digest_context_init'):
        continue
    sss_digest_context_init = _lib.sss_digest_context_init
    sss_digest_context_init.argtypes = [POINTER(sss_digest_t), POINTER(sss_session_t), sss_algorithm_t, sss_mode_t]
    sss_digest_context_init.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_digest_one_go'):
        continue
    sss_digest_one_go = _lib.sss_digest_one_go
    sss_digest_one_go.argtypes = [POINTER(sss_digest_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t)]
    sss_digest_one_go.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_digest_init'):
        continue
    sss_digest_init = _lib.sss_digest_init
    sss_digest_init.argtypes = [POINTER(sss_digest_t)]
    sss_digest_init.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_digest_update'):
        continue
    sss_digest_update = _lib.sss_digest_update
    sss_digest_update.argtypes = [POINTER(sss_digest_t), POINTER(c_uint8), c_size_t]
    sss_digest_update.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_digest_finish'):
        continue
    sss_digest_finish = _lib.sss_digest_finish
    sss_digest_finish.argtypes = [POINTER(sss_digest_t), POINTER(c_uint8), POINTER(c_size_t)]
    sss_digest_finish.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_digest_context_free'):
        continue
    sss_digest_context_free = _lib.sss_digest_context_free
    sss_digest_context_free.argtypes = [POINTER(sss_digest_t)]
    sss_digest_context_free.restype = None
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_mac_context_init'):
        continue
    sss_mac_context_init = _lib.sss_mac_context_init
    sss_mac_context_init.argtypes = [POINTER(sss_mac_t), POINTER(sss_session_t), POINTER(sss_object_t), sss_algorithm_t, sss_mode_t]
    sss_mac_context_init.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_mac_one_go'):
        continue
    sss_mac_one_go = _lib.sss_mac_one_go
    sss_mac_one_go.argtypes = [POINTER(sss_mac_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t)]
    sss_mac_one_go.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_mac_init'):
        continue
    sss_mac_init = _lib.sss_mac_init
    sss_mac_init.argtypes = [POINTER(sss_mac_t)]
    sss_mac_init.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_mac_update'):
        continue
    sss_mac_update = _lib.sss_mac_update
    sss_mac_update.argtypes = [POINTER(sss_mac_t), POINTER(c_uint8), c_size_t]
    sss_mac_update.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_mac_finish'):
        continue
    sss_mac_finish = _lib.sss_mac_finish
    sss_mac_finish.argtypes = [POINTER(sss_mac_t), POINTER(c_uint8), POINTER(c_size_t)]
    sss_mac_finish.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_mac_context_free'):
        continue
    sss_mac_context_free = _lib.sss_mac_context_free
    sss_mac_context_free.argtypes = [POINTER(sss_mac_t)]
    sss_mac_context_free.restype = None
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_asymmetric_context_init'):
        continue
    sss_asymmetric_context_init = _lib.sss_asymmetric_context_init
    sss_asymmetric_context_init.argtypes = [POINTER(sss_asymmetric_t), POINTER(sss_session_t), POINTER(sss_object_t), sss_algorithm_t, sss_mode_t]
    sss_asymmetric_context_init.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_asymmetric_encrypt'):
        continue
    sss_asymmetric_encrypt = _lib.sss_asymmetric_encrypt
    sss_asymmetric_encrypt.argtypes = [POINTER(sss_asymmetric_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t)]
    sss_asymmetric_encrypt.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_asymmetric_decrypt'):
        continue
    sss_asymmetric_decrypt = _lib.sss_asymmetric_decrypt
    sss_asymmetric_decrypt.argtypes = [POINTER(sss_asymmetric_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t)]
    sss_asymmetric_decrypt.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_asymmetric_sign_digest'):
        continue
    sss_asymmetric_sign_digest = _lib.sss_asymmetric_sign_digest
    sss_asymmetric_sign_digest.argtypes = [POINTER(sss_asymmetric_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t)]
    sss_asymmetric_sign_digest.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_asymmetric_verify_digest'):
        continue
    sss_asymmetric_verify_digest = _lib.sss_asymmetric_verify_digest
    sss_asymmetric_verify_digest.argtypes = [POINTER(sss_asymmetric_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), c_size_t]
    sss_asymmetric_verify_digest.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_asymmetric_context_free'):
        continue
    sss_asymmetric_context_free = _lib.sss_asymmetric_context_free
    sss_asymmetric_context_free.argtypes = [POINTER(sss_asymmetric_t)]
    sss_asymmetric_context_free.restype = None
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_derive_key_context_init'):
        continue
    sss_derive_key_context_init = _lib.sss_derive_key_context_init
    sss_derive_key_context_init.argtypes = [POINTER(sss_derive_key_t), POINTER(sss_session_t), POINTER(sss_object_t), sss_algorithm_t, sss_mode_t]
    sss_derive_key_context_init.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_derive_key_go'):
        continue
    sss_derive_key_go = _lib.sss_derive_key_go
    sss_derive_key_go.argtypes = [POINTER(sss_derive_key_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), c_size_t, POINTER(sss_object_t), c_uint16, POINTER(c_uint8), POINTER(c_size_t)]
    sss_derive_key_go.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_derive_key_one_go'):
        continue
    sss_derive_key_one_go = _lib.sss_derive_key_one_go
    sss_derive_key_one_go.argtypes = [POINTER(sss_derive_key_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), c_size_t, POINTER(sss_object_t), c_uint16]
    sss_derive_key_one_go.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_derive_key_sobj_one_go'):
        continue
    sss_derive_key_sobj_one_go = _lib.sss_derive_key_sobj_one_go
    sss_derive_key_sobj_one_go.argtypes = [POINTER(sss_derive_key_t), POINTER(sss_object_t), POINTER(c_uint8), c_size_t, POINTER(sss_object_t), c_uint16]
    sss_derive_key_sobj_one_go.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_derive_key_dh'):
        continue
    sss_derive_key_dh = _lib.sss_derive_key_dh
    sss_derive_key_dh.argtypes = [POINTER(sss_derive_key_t), POINTER(sss_object_t), POINTER(sss_object_t)]
    sss_derive_key_dh.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_derive_key_context_free'):
        continue
    sss_derive_key_context_free = _lib.sss_derive_key_context_free
    sss_derive_key_context_free.argtypes = [POINTER(sss_derive_key_t)]
    sss_derive_key_context_free.restype = None
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_rng_context_init'):
        continue
    sss_rng_context_init = _lib.sss_rng_context_init
    sss_rng_context_init.argtypes = [POINTER(sss_rng_context_t), POINTER(sss_session_t)]
    sss_rng_context_init.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_rng_get_random'):
        continue
    sss_rng_get_random = _lib.sss_rng_get_random
    sss_rng_get_random.argtypes = [POINTER(sss_rng_context_t), POINTER(c_uint8), c_size_t]
    sss_rng_get_random.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_rng_context_free'):
        continue
    sss_rng_context_free = _lib.sss_rng_context_free
    sss_rng_context_free.argtypes = [POINTER(sss_rng_context_t)]
    sss_rng_context_free.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_tunnel_context_init'):
        continue
    sss_tunnel_context_init = _lib.sss_tunnel_context_init
    sss_tunnel_context_init.argtypes = [POINTER(sss_tunnel_t), POINTER(sss_session_t)]
    sss_tunnel_context_init.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_tunnel'):
        continue
    sss_tunnel = _lib.sss_tunnel
    sss_tunnel.argtypes = [POINTER(sss_tunnel_t), POINTER(c_uint8), c_size_t, POINTER(sss_object_t), c_uint32, c_uint32]
    sss_tunnel.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_tunnel_context_free'):
        continue
    sss_tunnel_context_free = _lib.sss_tunnel_context_free
    sss_tunnel_context_free.argtypes = [POINTER(sss_tunnel_t)]
    sss_tunnel_context_free.restype = None
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_status_sz'):
        continue
    sss_status_sz = _lib.sss_status_sz
    sss_status_sz.argtypes = [sss_status_t]
    if sizeof(c_int) == sizeof(c_void_p):
        sss_status_sz.restype = ReturnString
    else:
        sss_status_sz.restype = String
        sss_status_sz.errcheck = ReturnString
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_cipher_type_sz'):
        continue
    sss_cipher_type_sz = _lib.sss_cipher_type_sz
    sss_cipher_type_sz.argtypes = [sss_cipher_type_t]
    if sizeof(c_int) == sizeof(c_void_p):
        sss_cipher_type_sz.restype = ReturnString
    else:
        sss_cipher_type_sz.restype = String
        sss_cipher_type_sz.errcheck = ReturnString
    break

SST_Index_t = U8# hostlib/hostLib/inc/a71ch_api.h

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetCredentialInfo'):
        continue
    A71_GetCredentialInfo = _lib.A71_GetCredentialInfo
    A71_GetCredentialInfo.argtypes = [POINTER(U8), POINTER(U16)]
    A71_GetCredentialInfo.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetModuleInfo'):
        continue
    A71_GetModuleInfo = _lib.A71_GetModuleInfo
    A71_GetModuleInfo.argtypes = [POINTER(U16), POINTER(U8), POINTER(U8), POINTER(U8), POINTER(U8), POINTER(U8), POINTER(U16)]
    A71_GetModuleInfo.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetRandom'):
        continue
    A71_GetRandom = _lib.A71_GetRandom
    A71_GetRandom.argtypes = [POINTER(U8), U8]
    A71_GetRandom.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_CreateClientHelloRandom'):
        continue
    A71_CreateClientHelloRandom = _lib.A71_CreateClientHelloRandom
    A71_CreateClientHelloRandom.argtypes = [POINTER(U8), U8]
    A71_CreateClientHelloRandom.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetRestrictedKeyPairInfo'):
        continue
    A71_GetRestrictedKeyPairInfo = _lib.A71_GetRestrictedKeyPairInfo
    A71_GetRestrictedKeyPairInfo.argtypes = [POINTER(U8), POINTER(U16), POINTER(U8), POINTER(U16)]
    A71_GetRestrictedKeyPairInfo.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetSha256'):
        continue
    A71_GetSha256 = _lib.A71_GetSha256
    A71_GetSha256.argtypes = [POINTER(U8), U16, POINTER(U8), POINTER(U16)]
    A71_GetSha256.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_Sha256Init'):
        continue
    A71_Sha256Init = _lib.A71_Sha256Init
    A71_Sha256Init.argtypes = []
    A71_Sha256Init.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_Sha256Update'):
        continue
    A71_Sha256Update = _lib.A71_Sha256Update
    A71_Sha256Update.argtypes = [POINTER(U8), U16]
    A71_Sha256Update.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_Sha256Final'):
        continue
    A71_Sha256Final = _lib.A71_Sha256Final
    A71_Sha256Final.argtypes = [POINTER(U8), POINTER(U16)]
    A71_Sha256Final.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetUniqueID'):
        continue
    A71_GetUniqueID = _lib.A71_GetUniqueID
    A71_GetUniqueID.argtypes = [POINTER(U8), POINTER(U16)]
    A71_GetUniqueID.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetCertUid'):
        continue
    A71_GetCertUid = _lib.A71_GetCertUid
    A71_GetCertUid.argtypes = [POINTER(U8), POINTER(U16)]
    A71_GetCertUid.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetKeyPairChallenge'):
        continue
    A71_GetKeyPairChallenge = _lib.A71_GetKeyPairChallenge
    A71_GetKeyPairChallenge.argtypes = [POINTER(U8), POINTER(U16)]
    A71_GetKeyPairChallenge.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetPublicKeyChallenge'):
        continue
    A71_GetPublicKeyChallenge = _lib.A71_GetPublicKeyChallenge
    A71_GetPublicKeyChallenge.argtypes = [POINTER(U8), POINTER(U16)]
    A71_GetPublicKeyChallenge.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetUnlockChallenge'):
        continue
    A71_GetUnlockChallenge = _lib.A71_GetUnlockChallenge
    A71_GetUnlockChallenge.argtypes = [POINTER(U8), POINTER(U16)]
    A71_GetUnlockChallenge.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_InjectLock'):
        continue
    A71_InjectLock = _lib.A71_InjectLock
    A71_InjectLock.argtypes = []
    A71_InjectLock.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_LockModule'):
        continue
    A71_LockModule = _lib.A71_LockModule
    A71_LockModule.argtypes = []
    A71_LockModule.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_UnlockModule'):
        continue
    A71_UnlockModule = _lib.A71_UnlockModule
    A71_UnlockModule.argtypes = [POINTER(U8), U16]
    A71_UnlockModule.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_SetTlsLabel'):
        continue
    A71_SetTlsLabel = _lib.A71_SetTlsLabel
    A71_SetTlsLabel.argtypes = [POINTER(U8), U16]
    A71_SetTlsLabel.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_EccVerifyWithKey'):
        continue
    A71_EccVerifyWithKey = _lib.A71_EccVerifyWithKey
    A71_EccVerifyWithKey.argtypes = [POINTER(U8), U16, POINTER(U8), U16, POINTER(U8), U16, POINTER(U8)]
    A71_EccVerifyWithKey.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GenerateEccKeyPair'):
        continue
    A71_GenerateEccKeyPair = _lib.A71_GenerateEccKeyPair
    A71_GenerateEccKeyPair.argtypes = [SST_Index_t]
    A71_GenerateEccKeyPair.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GenerateEccKeyPairWithChallenge'):
        continue
    A71_GenerateEccKeyPairWithChallenge = _lib.A71_GenerateEccKeyPairWithChallenge
    A71_GenerateEccKeyPairWithChallenge.argtypes = [SST_Index_t, POINTER(U8), U16]
    A71_GenerateEccKeyPairWithChallenge.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GenerateEccKeyPairWithCode'):
        continue
    A71_GenerateEccKeyPairWithCode = _lib.A71_GenerateEccKeyPairWithCode
    A71_GenerateEccKeyPairWithCode.argtypes = [SST_Index_t, POINTER(U8), U16]
    A71_GenerateEccKeyPairWithCode.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_SetEccKeyPair'):
        continue
    A71_SetEccKeyPair = _lib.A71_SetEccKeyPair
    A71_SetEccKeyPair.argtypes = [SST_Index_t, POINTER(U8), U16, POINTER(U8), U16]
    A71_SetEccKeyPair.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetPublicKeyEccKeyPair'):
        continue
    A71_GetPublicKeyEccKeyPair = _lib.A71_GetPublicKeyEccKeyPair
    A71_GetPublicKeyEccKeyPair.argtypes = [SST_Index_t, POINTER(U8), POINTER(U16)]
    A71_GetPublicKeyEccKeyPair.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetEccKeyPairUsage'):
        continue
    A71_GetEccKeyPairUsage = _lib.A71_GetEccKeyPairUsage
    A71_GetEccKeyPairUsage.argtypes = [SST_Index_t, POINTER(U8), POINTER(U16), POINTER(U16)]
    A71_GetEccKeyPairUsage.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_EccSign'):
        continue
    A71_EccSign = _lib.A71_EccSign
    A71_EccSign.argtypes = [SST_Index_t, POINTER(U8), U16, POINTER(U8), POINTER(U16)]
    A71_EccSign.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_EccNormalizedAsnSign'):
        continue
    A71_EccNormalizedAsnSign = _lib.A71_EccNormalizedAsnSign
    A71_EccNormalizedAsnSign.argtypes = [SST_Index_t, POINTER(U8), U16, POINTER(U8), POINTER(U16)]
    A71_EccNormalizedAsnSign.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_EccRestrictedSign'):
        continue
    A71_EccRestrictedSign = _lib.A71_EccRestrictedSign
    A71_EccRestrictedSign.argtypes = [SST_Index_t, POINTER(U8), U16, POINTER(U8)]
    A71_EccRestrictedSign.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_EcdhGetSharedSecret'):
        continue
    A71_EcdhGetSharedSecret = _lib.A71_EcdhGetSharedSecret
    A71_EcdhGetSharedSecret.argtypes = [U8, POINTER(U8), U16, POINTER(U8), POINTER(U16)]
    A71_EcdhGetSharedSecret.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_FreezeEccKeyPair'):
        continue
    A71_FreezeEccKeyPair = _lib.A71_FreezeEccKeyPair
    A71_FreezeEccKeyPair.argtypes = [SST_Index_t]
    A71_FreezeEccKeyPair.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_FreezeEccKeyPairWithChallenge'):
        continue
    A71_FreezeEccKeyPairWithChallenge = _lib.A71_FreezeEccKeyPairWithChallenge
    A71_FreezeEccKeyPairWithChallenge.argtypes = [SST_Index_t, POINTER(U8), U16]
    A71_FreezeEccKeyPairWithChallenge.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_FreezeEccKeyPairWithCode'):
        continue
    A71_FreezeEccKeyPairWithCode = _lib.A71_FreezeEccKeyPairWithCode
    A71_FreezeEccKeyPairWithCode.argtypes = [SST_Index_t, POINTER(U8), U16]
    A71_FreezeEccKeyPairWithCode.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_EraseEccKeyPair'):
        continue
    A71_EraseEccKeyPair = _lib.A71_EraseEccKeyPair
    A71_EraseEccKeyPair.argtypes = [SST_Index_t]
    A71_EraseEccKeyPair.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_EraseEccKeyPairWithChallenge'):
        continue
    A71_EraseEccKeyPairWithChallenge = _lib.A71_EraseEccKeyPairWithChallenge
    A71_EraseEccKeyPairWithChallenge.argtypes = [SST_Index_t, POINTER(U8), U16]
    A71_EraseEccKeyPairWithChallenge.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_EraseEccKeyPairWithCode'):
        continue
    A71_EraseEccKeyPairWithCode = _lib.A71_EraseEccKeyPairWithCode
    A71_EraseEccKeyPairWithCode.argtypes = [SST_Index_t, POINTER(U8), U16]
    A71_EraseEccKeyPairWithCode.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_SetEccPublicKey'):
        continue
    A71_SetEccPublicKey = _lib.A71_SetEccPublicKey
    A71_SetEccPublicKey.argtypes = [SST_Index_t, POINTER(U8), U16]
    A71_SetEccPublicKey.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetEccPublicKey'):
        continue
    A71_GetEccPublicKey = _lib.A71_GetEccPublicKey
    A71_GetEccPublicKey.argtypes = [SST_Index_t, POINTER(U8), POINTER(U16)]
    A71_GetEccPublicKey.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_FreezeEccPublicKey'):
        continue
    A71_FreezeEccPublicKey = _lib.A71_FreezeEccPublicKey
    A71_FreezeEccPublicKey.argtypes = [SST_Index_t]
    A71_FreezeEccPublicKey.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_FreezeEccPublicKeyWithChallenge'):
        continue
    A71_FreezeEccPublicKeyWithChallenge = _lib.A71_FreezeEccPublicKeyWithChallenge
    A71_FreezeEccPublicKeyWithChallenge.argtypes = [SST_Index_t, POINTER(U8), U16]
    A71_FreezeEccPublicKeyWithChallenge.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_FreezeEccPublicKeyWithCode'):
        continue
    A71_FreezeEccPublicKeyWithCode = _lib.A71_FreezeEccPublicKeyWithCode
    A71_FreezeEccPublicKeyWithCode.argtypes = [SST_Index_t, POINTER(U8), U16]
    A71_FreezeEccPublicKeyWithCode.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_EraseEccPublicKey'):
        continue
    A71_EraseEccPublicKey = _lib.A71_EraseEccPublicKey
    A71_EraseEccPublicKey.argtypes = [SST_Index_t]
    A71_EraseEccPublicKey.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_EraseEccPublicKeyWithChallenge'):
        continue
    A71_EraseEccPublicKeyWithChallenge = _lib.A71_EraseEccPublicKeyWithChallenge
    A71_EraseEccPublicKeyWithChallenge.argtypes = [SST_Index_t, POINTER(U8), U16]
    A71_EraseEccPublicKeyWithChallenge.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_EraseEccPublicKeyWithCode'):
        continue
    A71_EraseEccPublicKeyWithCode = _lib.A71_EraseEccPublicKeyWithCode
    A71_EraseEccPublicKeyWithCode.argtypes = [SST_Index_t, POINTER(U8), U16]
    A71_EraseEccPublicKeyWithCode.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_EccVerify'):
        continue
    A71_EccVerify = _lib.A71_EccVerify
    A71_EccVerify.argtypes = [SST_Index_t, POINTER(U8), U16, POINTER(U8), U16, POINTER(U8)]
    A71_EccVerify.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_SetSymKey'):
        continue
    A71_SetSymKey = _lib.A71_SetSymKey
    A71_SetSymKey.argtypes = [SST_Index_t, POINTER(U8), U16]
    A71_SetSymKey.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_SetRfc3394WrappedAesKey'):
        continue
    A71_SetRfc3394WrappedAesKey = _lib.A71_SetRfc3394WrappedAesKey
    A71_SetRfc3394WrappedAesKey.argtypes = [SST_Index_t, POINTER(U8), U16]
    A71_SetRfc3394WrappedAesKey.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_FreezeSymKey'):
        continue
    A71_FreezeSymKey = _lib.A71_FreezeSymKey
    A71_FreezeSymKey.argtypes = [SST_Index_t]
    A71_FreezeSymKey.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_EraseSymKey'):
        continue
    A71_EraseSymKey = _lib.A71_EraseSymKey
    A71_EraseSymKey.argtypes = [SST_Index_t]
    A71_EraseSymKey.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetHmacSha256'):
        continue
    A71_GetHmacSha256 = _lib.A71_GetHmacSha256
    A71_GetHmacSha256.argtypes = [SST_Index_t, U8, POINTER(U8), U16, POINTER(U8), POINTER(U16)]
    A71_GetHmacSha256.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_HmacSha256Init'):
        continue
    A71_HmacSha256Init = _lib.A71_HmacSha256Init
    A71_HmacSha256Init.argtypes = [SST_Index_t, U8]
    A71_HmacSha256Init.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_HmacSha256Update'):
        continue
    A71_HmacSha256Update = _lib.A71_HmacSha256Update
    A71_HmacSha256Update.argtypes = [SST_Index_t, U8, POINTER(U8), U16]
    A71_HmacSha256Update.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_HmacSha256Final'):
        continue
    A71_HmacSha256Final = _lib.A71_HmacSha256Final
    A71_HmacSha256Final.argtypes = [SST_Index_t, U8, POINTER(U8), POINTER(U16)]
    A71_HmacSha256Final.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_HkdfExpandSymKey'):
        continue
    A71_HkdfExpandSymKey = _lib.A71_HkdfExpandSymKey
    A71_HkdfExpandSymKey.argtypes = [SST_Index_t, U8, POINTER(U8), U16, POINTER(U8), U16]
    A71_HkdfExpandSymKey.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_HkdfSymKey'):
        continue
    A71_HkdfSymKey = _lib.A71_HkdfSymKey
    A71_HkdfSymKey.argtypes = [SST_Index_t, U8, POINTER(U8), U16, POINTER(U8), U16, POINTER(U8), U16]
    A71_HkdfSymKey.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_PskDeriveMasterSecret'):
        continue
    A71_PskDeriveMasterSecret = _lib.A71_PskDeriveMasterSecret
    A71_PskDeriveMasterSecret.argtypes = [SST_Index_t, U8, POINTER(U8), U16, POINTER(U8)]
    A71_PskDeriveMasterSecret.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_SetGpData'):
        continue
    A71_SetGpData = _lib.A71_SetGpData
    A71_SetGpData.argtypes = [U16, POINTER(U8), U16]
    A71_SetGpData.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_SetGpDataWithLockCheck'):
        continue
    A71_SetGpDataWithLockCheck = _lib.A71_SetGpDataWithLockCheck
    A71_SetGpDataWithLockCheck.argtypes = [U16, POINTER(U8), U16]
    A71_SetGpDataWithLockCheck.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetGpData'):
        continue
    A71_GetGpData = _lib.A71_GetGpData
    A71_GetGpData.argtypes = [U16, POINTER(U8), U16]
    A71_GetGpData.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_FreezeGpData'):
        continue
    A71_FreezeGpData = _lib.A71_FreezeGpData
    A71_FreezeGpData.argtypes = [U16, U16]
    A71_FreezeGpData.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_IncrementCounter'):
        continue
    A71_IncrementCounter = _lib.A71_IncrementCounter
    A71_IncrementCounter.argtypes = [SST_Index_t]
    A71_IncrementCounter.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_SetCounter'):
        continue
    A71_SetCounter = _lib.A71_SetCounter
    A71_SetCounter.argtypes = [SST_Index_t, U32]
    A71_SetCounter.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_GetCounter'):
        continue
    A71_GetCounter = _lib.A71_GetCounter
    A71_GetCounter.argtypes = [SST_Index_t, POINTER(U32)]
    A71_GetCounter.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_EcdhPskDeriveMasterSecret'):
        continue
    A71_EcdhPskDeriveMasterSecret = _lib.A71_EcdhPskDeriveMasterSecret
    A71_EcdhPskDeriveMasterSecret.argtypes = [SST_Index_t, POINTER(U8), U16, SST_Index_t, U8, POINTER(U8), U16, POINTER(U8)]
    A71_EcdhPskDeriveMasterSecret.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_SetConfigKey'):
        continue
    A71_SetConfigKey = _lib.A71_SetConfigKey
    A71_SetConfigKey.argtypes = [SST_Index_t, POINTER(U8), U16]
    A71_SetConfigKey.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'A71_SetRfc3394WrappedConfigKey'):
        continue
    A71_SetRfc3394WrappedConfigKey = _lib.A71_SetRfc3394WrappedConfigKey
    A71_SetRfc3394WrappedConfigKey.argtypes = [SST_Index_t, POINTER(U8), U16]
    A71_SetRfc3394WrappedConfigKey.restype = U16
    break

HLSE_RET_CODE = U16# hostlib/hostLib/inc/HLSETypes.h

HLSE_TYPE = U32
HLSE_OBJECT_HANDLE = HLSE_TYPE
# hostlib/hostLib/inc/HLSEMisc.h
for _lib in list(_libs.values()):
    if not hasattr(_lib, 'HLSE_DisablePlainInjectionMode'):
        continue
    HLSE_DisablePlainInjectionMode = _lib.HLSE_DisablePlainInjectionMode
    HLSE_DisablePlainInjectionMode.argtypes = []
    HLSE_DisablePlainInjectionMode.restype = HLSE_RET_CODE
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'HLSE_ResetContents'):
        continue
    HLSE_ResetContents = _lib.HLSE_ResetContents
    HLSE_ResetContents.argtypes = []
    HLSE_ResetContents.restype = HLSE_RET_CODE
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'HLSE_DbgDisableDebug'):
        continue
    HLSE_DbgDisableDebug = _lib.HLSE_DbgDisableDebug
    HLSE_DbgDisableDebug.argtypes = []
    HLSE_DbgDisableDebug.restype = HLSE_RET_CODE
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'HLSE_DbgReflect'):
        continue
    HLSE_DbgReflect = _lib.HLSE_DbgReflect
    HLSE_DbgReflect.argtypes = [POINTER(U8), U16, POINTER(U8), POINTER(U16)]
    HLSE_DbgReflect.restype = HLSE_RET_CODE
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'HLSE_DbgReset'):
        continue
    HLSE_DbgReset = _lib.HLSE_DbgReset
    HLSE_DbgReset.argtypes = []
    HLSE_DbgReset.restype = HLSE_RET_CODE
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'HLSE_NormalizeECCSignature'):
        continue
    HLSE_NormalizeECCSignature = _lib.HLSE_NormalizeECCSignature
    HLSE_NormalizeECCSignature.argtypes = [POINTER(U8), U16, POINTER(U8), POINTER(U16)]
    HLSE_NormalizeECCSignature.restype = HLSE_RET_CODE
    break

enum_anon_80 = c_int # ../../hostlib/hostLib/libCommon/infra/sm_api.h

kType_SE_Conn_Type_NONE = 0

kType_SE_Conn_Type_SCII2C = (0 + 2)

kType_SE_Conn_Type_VCOM = (0 + 3)

kType_SE_Conn_Type_JRCP_V1 = (0 + 4)

kType_SE_Conn_Type_JRCP_V2 = (0 + 5)

kType_SE_Conn_Type_T1oI2C = (0 + 6)

kType_SE_Conn_Type_NFC = (0 + 7)

kType_SE_Conn_Type_Channel = (0 + 8)

kType_SE_Conn_Type_PCSC = (0 + 9)

kType_SE_Conn_Type_LAST = (kType_SE_Conn_Type_PCSC + 1)

kType_SE_Conn_Type_SIZE = 32767

SSS_Conn_Type_t = enum_anon_80
class struct_anon_81(Structure):
    pass


struct_anon_81.__slots__ = [
    'connType',
    'param1',
    'param2',
    'hostLibVersion',
    'appletVersion',
    'sbVersion',
    'select',
]
struct_anon_81._fields_ = [
    ('connType', U16),
    ('param1', U16),
    ('param2', U16),
    ('hostLibVersion', U16),
    ('appletVersion', U32),
    ('sbVersion', U16),
    ('select', U8),
]

SmCommState_t = struct_anon_81
for _lib in list(_libs.values()):
    if not hasattr(_lib, 'SM_Close'):
        continue
    SM_Close = _lib.SM_Close
    SM_Close.argtypes = [POINTER(None), U8]
    SM_Close.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'SM_Connect'):
        continue
    SM_Connect = _lib.SM_Connect
    SM_Connect.argtypes = [POINTER(None), POINTER(SmCommState_t), POINTER(U8), POINTER(U16)]
    SM_Connect.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'SM_ConnectWithAID'):
        continue
    SM_ConnectWithAID = _lib.SM_ConnectWithAID
    SM_ConnectWithAID.argtypes = [POINTER(SmCommState_t), POINTER(U8), U16, POINTER(U8), POINTER(U16)]
    SM_ConnectWithAID.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'SM_RjctConnect'):
        continue
    SM_RjctConnect = _lib.SM_RjctConnect
    SM_RjctConnect.argtypes = [POINTER(POINTER(None)), String, POINTER(SmCommState_t), POINTER(U8), POINTER(U16)]
    SM_RjctConnect.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'SM_RjctConnectWithAID'):
        continue
    SM_RjctConnectWithAID = _lib.SM_RjctConnectWithAID
    SM_RjctConnectWithAID.argtypes = [String, POINTER(SmCommState_t), POINTER(U8), U16, POINTER(U8), POINTER(U16)]
    SM_RjctConnectWithAID.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'SM_I2CConnect'):
        continue
    SM_I2CConnect = _lib.SM_I2CConnect
    SM_I2CConnect.argtypes = [POINTER(POINTER(None)), POINTER(SmCommState_t), POINTER(U8), POINTER(U16), String]
    SM_I2CConnect.restype = U16
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'SM_SendAPDU'):
        continue
    SM_SendAPDU = _lib.SM_SendAPDU
    SM_SendAPDU.argtypes = [POINTER(U8), U16, POINTER(U8), POINTER(U16)]
    SM_SendAPDU.restype = U16
    break

sscp_status_t = c_uint32# ../../sss/inc/fsl_sscp.h

class struct__sscp_context(Structure):
    pass


sscp_context_t = struct__sscp_context
class struct__sscp_operation(Structure):
    pass


sscp_operation_t = struct__sscp_operation
fn_sscp_invoke_command_t = CFUNCTYPE(UNCHECKED(sscp_status_t), POINTER(sscp_context_t), c_uint32, POINTER(sscp_operation_t), POINTER(c_uint32))
class struct_anon_82(Structure):
    pass


struct_anon_82.__slots__ = [
    'data',
]
struct_anon_82._fields_ = [
    ('data', c_uint8 * sizeof(POINTER(None))),
]

struct__sscp_context.__slots__ = [
    'invoke',
    'context',
]
struct__sscp_context._fields_ = [
    ('invoke', fn_sscp_invoke_command_t),
    ('context', struct_anon_82),
]

class struct__sscp_memref(Structure):
    pass


struct__sscp_memref.__slots__ = [
    'buffer',
    'size',
]
struct__sscp_memref._fields_ = [
    ('buffer', POINTER(None)),
    ('size', c_size_t),
]

sscp_memref_t = struct__sscp_memref
class struct__sscp_value(Structure):
    pass


struct__sscp_value.__slots__ = [
    'a',
    'b',
]
struct__sscp_value._fields_ = [
    ('a', c_uint32),
    ('b', c_uint32),
]

sscp_value_t = struct__sscp_value
class struct__sscp_aggregate_operation(Structure):
    pass


struct__sscp_aggregate_operation.__slots__ = [
    'op',
]
struct__sscp_aggregate_operation._fields_ = [
    ('op', POINTER(sscp_operation_t)),
]

sscp_aggregate_operation_t = struct__sscp_aggregate_operation
class struct__sscp_context_operation(Structure):
    pass


struct__sscp_context_operation.__slots__ = [
    'ptr',
    'type',
]
struct__sscp_context_operation._fields_ = [
    ('ptr', POINTER(None)),
    ('type', c_uint32),
]

sscp_context_reference_t = struct__sscp_context_operation
class union__sscp_parameter(Union):
    pass


union__sscp_parameter.__slots__ = [
    'value',
    'memref',
    'aggregate',
    'context',
]
union__sscp_parameter._fields_ = [
    ('value', sscp_value_t),
    ('memref', sscp_memref_t),
    ('aggregate', sscp_aggregate_operation_t),
    ('context', sscp_context_reference_t),
]

sscp_parameter_t = union__sscp_parameter
struct__sscp_operation.__slots__ = [
    'paramTypes',
    'params',
]
struct__sscp_operation._fields_ = [
    ('paramTypes', c_uint32),
    ('params', sscp_parameter_t * 7),
]

fn_sscp_close_t = CFUNCTYPE(UNCHECKED(None), )# ../../sss/inc/fsl_sss_sscp.h

class struct__sss_sscp_session(Structure):
    pass


struct__sss_sscp_session.__slots__ = [
    'subsystem',
    'sscp_context',
    'mem_sscp_ctx',
    'sessionId',
    'fp_closeConnection',
]
struct__sss_sscp_session._fields_ = [
    ('subsystem', sss_type_t),
    ('sscp_context', POINTER(sscp_context_t)),
    ('mem_sscp_ctx', sscp_context_t),
    ('sessionId', c_uint32),
    ('fp_closeConnection', fn_sscp_close_t),
]

sss_sscp_session_t = struct__sss_sscp_session
# ../../sss/inc/fsl_sss_keyid_map.h
class struct_anon_89(Structure):
    pass


struct_anon_89.__slots__ = [
    'extKeyId',
    'keyPart',
    'accessPermission',
    'cipherType',
    'keyIntIndex',
]
struct_anon_89._fields_ = [
    ('extKeyId', c_uint32),
    ('keyPart', c_uint8),
    ('accessPermission', c_uint8),
    ('cipherType', c_uint8),
    ('keyIntIndex', c_uint8),
]

keyIdAndTypeIndexLookup_t = struct_anon_89
class struct__keyStoreTable_t(Structure):
    pass


struct__keyStoreTable_t.__slots__ = [
    'magic',
    'version',
    'maxEntries',
    'entries',
]
struct__keyStoreTable_t._fields_ = [
    ('magic', c_uint32),
    ('version', c_uint16),
    ('maxEntries', c_uint16),
    ('entries', POINTER(keyIdAndTypeIndexLookup_t)),
]

keyStoreTable_t = struct__keyStoreTable_t
# ../../sss/inc/fsl_sscp_a71ch.h
class struct__sss_a71ch_key_store(Structure):
    pass


struct__sss_a71ch_key_store.__slots__ = [
    'session',
    'keystore_shadow',
    'shadow_handle',
]
struct__sss_a71ch_key_store._fields_ = [
    ('session', POINTER(sss_sscp_session_t)),
    ('keystore_shadow', POINTER(keyStoreTable_t)),
    ('shadow_handle', HLSE_OBJECT_HANDLE),
]

sss_a71ch_key_store_t = struct__sss_a71ch_key_store
class struct__sscp_a71ch_context(Structure):
    pass


struct__sscp_a71ch_context.__slots__ = [
    'invoke',
    'keyStore',
]
struct__sscp_a71ch_context._fields_ = [
    ('invoke', fn_sscp_invoke_command_t),
    ('keyStore', POINTER(sss_a71ch_key_store_t)),
]

sscp_a71ch_context_t = struct__sscp_a71ch_context
for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sscp_a71ch_init'):
        continue
    sscp_a71ch_init = _lib.sscp_a71ch_init
    sscp_a71ch_init.argtypes = [POINTER(sscp_a71ch_context_t), POINTER(sss_a71ch_key_store_t)]
    sscp_a71ch_init.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sscp_a71ch_free'):
        continue
    sscp_a71ch_free = _lib.sscp_a71ch_free
    sscp_a71ch_free.argtypes = [POINTER(sscp_a71ch_context_t)]
    sscp_a71ch_free.restype = None
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sscp_a71ch_invoke_command'):
        continue
    sscp_a71ch_invoke_command = _lib.sscp_a71ch_invoke_command
    sscp_a71ch_invoke_command.argtypes = [POINTER(sscp_context_t), c_uint32, POINTER(sscp_operation_t), POINTER(c_uint32)]
    sscp_a71ch_invoke_command.restype = sscp_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sscp_a71ch_openSession'):
        continue
    sscp_a71ch_openSession = _lib.sscp_a71ch_openSession
    sscp_a71ch_openSession.argtypes = [POINTER(None), POINTER(sss_sscp_session_t)]
    sscp_a71ch_openSession.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sscp_a71chkey_store_context_free'):
        continue
    sscp_a71chkey_store_context_free = _lib.sscp_a71chkey_store_context_free
    sscp_a71chkey_store_context_free.argtypes = [POINTER(sss_a71ch_key_store_t)]
    sscp_a71chkey_store_context_free.restype = None
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sscp_a71ch_closeSession'):
        continue
    sscp_a71ch_closeSession = _lib.sscp_a71ch_closeSession
    sscp_a71ch_closeSession.argtypes = [POINTER(sss_sscp_session_t)]
    sscp_a71ch_closeSession.restype = None
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sscp_a71ch_closeConnect'):
        continue
    sscp_a71ch_closeConnect = _lib.sscp_a71ch_closeConnect
    sscp_a71ch_closeConnect.argtypes = []
    sscp_a71ch_closeConnect.restype = None
    break

enum_anon_90 = c_int # hostlib/hostLib/inc/nxScp03_Types.h

kSSS_AuthType_None = 0

kSSS_AuthType_SCP03 = 1

kSSS_AuthType_ID = 2

kSSS_AuthType_AESKey = 3

kSSS_AuthType_ECKey = 4

kSSS_AuthType_INT_ECKey_Counter = 20

kSSS_SIZE = 2147483647

SE_AuthType_t = enum_anon_90
class struct_anon_91(Structure):
    pass


struct_anon_91.__slots__ = [
    'Enc',
    'Mac',
    'Rmac',
    'MCV',
    'cCounter',
    'SecurityLevel',
    'authType',
]
struct_anon_91._fields_ = [
    ('Enc', sss_object_t),
    ('Mac', sss_object_t),
    ('Rmac', sss_object_t),
    ('MCV', c_uint8 * 16),
    ('cCounter', c_uint8 * 16),
    ('SecurityLevel', c_uint8),
    ('authType', SE_AuthType_t),
]

NXSCP03_DynCtx_t = struct_anon_91
class struct_anon_92(Structure):
    pass


struct_anon_92.__slots__ = [
    'keyVerNo',
    'Enc',
    'Mac',
    'Dek',
]
struct_anon_92._fields_ = [
    ('keyVerNo', c_uint8),
    ('Enc', sss_object_t),
    ('Mac', sss_object_t),
    ('Dek', sss_object_t),
]

NXSCP03_StaticCtx_t = struct_anon_92
class struct_anon_93(Structure):
    pass


struct_anon_93.__slots__ = [
    'pStatic_ctx',
    'pDyn_ctx',
]
struct_anon_93._fields_ = [
    ('pStatic_ctx', POINTER(NXSCP03_StaticCtx_t)),
    ('pDyn_ctx', POINTER(NXSCP03_DynCtx_t)),
]

NXSCP03_AuthCtx_t = struct_anon_93
class struct_anon_94(Structure):
    pass


struct_anon_94.__slots__ = [
    'HostEcdsaObj',
    'HostEcKeypair',
    'SeEcPubKey',
    'masterSec',
]
struct_anon_94._fields_ = [
    ('HostEcdsaObj', sss_object_t),
    ('HostEcKeypair', sss_object_t),
    ('SeEcPubKey', sss_object_t),
    ('masterSec', sss_object_t),
]

NXECKey03_StaticCtx_t = struct_anon_94
class struct_anon_95(Structure):
    pass


struct_anon_95.__slots__ = [
    'pStatic_ctx',
    'pDyn_ctx',
]
struct_anon_95._fields_ = [
    ('pStatic_ctx', POINTER(NXECKey03_StaticCtx_t)),
    ('pDyn_ctx', POINTER(NXSCP03_DynCtx_t)),
]

SE05x_AuthCtx_ECKey_t = struct_anon_95
class struct_anon_96(Structure):
    pass


struct_anon_96.__slots__ = [
    'pObj',
]
struct_anon_96._fields_ = [
    ('pObj', POINTER(sss_object_t)),
]

SE05x_AuthCtx_ID_t = struct_anon_96
class struct_anon_97(Structure):
    pass


struct_anon_97.__slots__ = [
    'pKeyEnc',
    'pKeyMac',
    'pKeyDek',
]
struct_anon_97._fields_ = [
    ('pKeyEnc', sss_object_t),
    ('pKeyMac', sss_object_t),
    ('pKeyDek', sss_object_t),
]

SM_SECURE_SCP03_KEYOBJ = struct_anon_97
class struct_anon_98(Structure):
    pass


struct_anon_98.__slots__ = [
    'data',
]
struct_anon_98._fields_ = [
    ('data', c_uint8 * ((0 + (3 * sizeof(POINTER(None)))) + 8)),
]

class union_anon_99(Union):
    pass


union_anon_99.__slots__ = [
    'scp03',
    'eckey',
    'idobj',
    'a71chAuthKeys',
    'extension',
]
union_anon_99._fields_ = [
    ('scp03', NXSCP03_AuthCtx_t),
    ('eckey', SE05x_AuthCtx_ECKey_t),
    ('idobj', SE05x_AuthCtx_ID_t),
    ('a71chAuthKeys', SM_SECURE_SCP03_KEYOBJ),
    ('extension', struct_anon_98),
]

class struct__SE_AuthCtx(Structure):
    pass


struct__SE_AuthCtx.__slots__ = [
    'authType',
    'ctx',
]
struct__SE_AuthCtx._fields_ = [
    ('authType', SE_AuthType_t),
    ('ctx', union_anon_99),
]

SE_AuthCtx_t = struct__SE_AuthCtx
class struct_anon_100(Structure):
    pass


struct_anon_100.__slots__ = [
    'sizeOfStucture',
    'auth',
    'session_policy',
    'tunnelCtx',
    'connType',
    'portName',
    'i2cAddress',
    'refresh_session',
    'skip_select_applet',
]
struct_anon_100._fields_ = [
    ('sizeOfStucture', c_uint16),
    ('auth', SE_AuthCtx_t),
    ('session_policy', POINTER(sss_policy_session_u)),
    ('tunnelCtx', POINTER(sss_tunnel_t)),
    ('connType', SSS_Conn_Type_t),
    ('portName', String),
    ('i2cAddress', U32),
    ('refresh_session', c_uint8, 1),
    ('skip_select_applet', c_uint8, 1),
]

SE_Connect_Ctx_t = struct_anon_100
class struct_anon_101(Structure):
    pass


struct_anon_101.__slots__ = [
    'data',
]
struct_anon_101._fields_ = [
    ('data', c_uint8 * ((0 + (4 * sizeof(POINTER(None)))) + 8)),
]

class struct_anon_102(Structure):
    pass


struct_anon_102.__slots__ = [
    'sizeOfStucture',
    'auth',
    'session_policy',
    'extension',
]
struct_anon_102._fields_ = [
    ('sizeOfStucture', c_uint16),
    ('auth', SE_AuthCtx_t),
    ('session_policy', POINTER(sss_policy_session_u)),
    ('extension', struct_anon_101),
]

sss_connect_ctx_t = struct_anon_102
enum_Se05x_SYMM_CIPHER_MODES = c_int # hostlib/hostLib/inc/se05x_const.h

Se05x_SYMM_MODE_NONE = 0

Se05x_SYMM_CBC = 1

Se05x_SYMM_EBC = 2

Se05x_SYMM_CTR = 8

enum_Se05x_AES_PADDING = c_int 
Se05x_AES_PADDING_NONE = 0

Se05x_AES_PAD_NOPAD = 1

Se05x_AES_PAD_ISO9797_M1 = 2

Se05x_AES_PAD_ISO9797_M2 = 3

enum_Se05x_SHA_TYPE = c_int 
Se05x_SHA_1 = 0

Se05x_SHA_256 = 4

Se05x_SHA_384 = 5

Se05x_SHA_512 = 6

enum_Se05x_MAC_TYPE = c_int 
Se05x_CMAC = 10

enum_Se05x_MAC_Sign_verify = c_int 
Se05x_MAC_Sign = 0

Se05x_MAC_Verify = 1

enum_Se05x_I2CM_RESULT_TYPE = c_int 
Se05x_I2CM_RESULT_SUCCESS = 165

Se05x_I2CM_RESULT_FAILURE = 150

enum_anon_103 = c_int # hostlib/hostLib/inc/se05x_enums.h

kSE05x_AppletResID_NA = 0

kSE05x_AppletResID_TRANSPORT = 2147418624

kSE05x_AppletResID_KP_ECKEY_USER = 2147418625

kSE05x_AppletResID_KP_ECKEY_IMPORT = 2147418626

kSE05x_AppletResID_FEATURE = 2147418628

kSE05x_AppletResID_FACTORY_RESET = 2147418629

kSE05x_AppletResID_UNIQUE_ID = 2147418630

kSE05x_AppletResID_PLATFORM_SCP = 2147418631

kSE05x_AppletResID_I2CM_ACCESS = 2147418632

kSE05x_AppletResID_RESTRICT = 2147418634

SE05x_AppletResID_t = enum_anon_103
enum_anon_104 = c_int 
kSE05x_SW12_NA = 0

kSE05x_SW12_NO_ERROR = 36864

kSE05x_SW12_CONDITIONS_NOT_SATISFIED = 27013

kSE05x_SW12_SECURITY_STATUS = 27010

kSE05x_SW12_WRONG_DATA = 27264

kSE05x_SW12_DATA_INVALID = 27012

kSE05x_SW12_COMMAND_NOT_ALLOWED = 27014

SE05x_SW12_t = enum_anon_104
enum_anon_105 = c_int 
kSE05x_INS_NA = 0

kSE05x_INS_MASK_INS_CHAR = 224

kSE05x_INS_MASK_INSTRUCTION = 31

kSE05x_INS_TRANSIENT = 128

kSE05x_INS_AUTH_OBJECT = 64

kSE05x_INS_ATTEST = 32

kSE05x_INS_WRITE = 1

kSE05x_INS_READ = 2

kSE05x_INS_CRYPTO = 3

kSE05x_INS_MGMT = 4

kSE05x_INS_PROCESS = 5

SE05x_INS_t = enum_anon_105
enum_anon_106 = c_int 
kSE05x_P1_NA = 0

kSE05x_P1_UNUSED = 128

kSE05x_P1_MASK_KEY_TYPE = 96

kSE05x_P1_MASK_CRED_TYPE = 31

kSE05x_P1_KEY_PAIR = 96

kSE05x_P1_PRIVATE = 64

kSE05x_P1_PUBLIC = 32

kSE05x_P1_DEFAULT = 0

kSE05x_P1_EC = 1

kSE05x_P1_RSA = 2

kSE05x_P1_AES = 3

kSE05x_P1_DES = 4

kSE05x_P1_HMAC = 5

kSE05x_P1_BINARY = 6

kSE05x_P1_UserID = 7

kSE05x_P1_COUNTER = 8

kSE05x_P1_PCR = 9

kSE05x_P1_CURVE = 11

kSE05x_P1_SIGNATURE = 12

kSE05x_P1_MAC = 13

kSE05x_P1_CIPHER = 14

kSE05x_P1_TLS = 15

kSE05x_P1_CRYPTO_OBJ = 16

kSE05x_P1_AEAD = 17

kSE05x_P1_AEAD_SP800_38D = 18

SE05x_P1_t = enum_anon_106
enum_anon_107 = c_int 
kSE05x_P2_DEFAULT = 0

kSE05x_P2_GENERATE = 3

kSE05x_P2_CREATE = 4

kSE05x_P2_SIZE = 7

kSE05x_P2_SIGN = 9

kSE05x_P2_VERIFY = 10

kSE05x_P2_INIT = 11

kSE05x_P2_UPDATE = 12

kSE05x_P2_FINAL = 13

kSE05x_P2_ONESHOT = 14

kSE05x_P2_DH = 15

kSE05x_P2_DIVERSIFY = 16

kSE05x_P2_AUTH_FIRST_PART2 = 18

kSE05x_P2_AUTH_NONFIRST_PART2 = 19

kSE05x_P2_DUMP_KEY = 20

kSE05x_P2_CHANGE_KEY_PART1 = 21

kSE05x_P2_CHANGE_KEY_PART2 = 22

kSE05x_P2_KILL_AUTH = 23

kSE05x_P2_IMPORT = 24

kSE05x_P2_EXPORT = 25

kSE05x_P2_SESSION_CREATE = 27

kSE05x_P2_SESSION_CLOSE = 28

kSE05x_P2_SESSION_REFRESH = 30

kSE05x_P2_SESSION_POLICY = 31

kSE05x_P2_VERSION = 32

kSE05x_P2_VERSION_EXT = 33

kSE05x_P2_MEMORY = 34

kSE05x_P2_LIST = 37

kSE05x_P2_TYPE = 38

kSE05x_P2_EXIST = 39

kSE05x_P2_DELETE_OBJECT = 40

kSE05x_P2_DELETE_ALL = 42

kSE05x_P2_SESSION_UserID = 44

kSE05x_P2_HKDF = 45

kSE05x_P2_PBKDF = 46

kSE05x_P2_HKDF_EXPAND_ONLY = 47

kSE05x_P2_I2CM = 48

kSE05x_P2_I2CM_ATTESTED = 49

kSE05x_P2_MAC = 50

kSE05x_P2_UNLOCK_CHALLENGE = 51

kSE05x_P2_CURVE_LIST = 52

kSE05x_P2_SIGN_ECDAA = 53

kSE05x_P2_ID = 54

kSE05x_P2_ENCRYPT_ONESHOT = 55

kSE05x_P2_DECRYPT_ONESHOT = 56

kSE05x_P2_ATTEST = 58

kSE05x_P2_ATTRIBUTES = 59

kSE05x_P2_CPLC = 60

kSE05x_P2_TIME = 61

kSE05x_P2_TRANSPORT = 62

kSE05x_P2_VARIANT = 63

kSE05x_P2_PARAM = 64

kSE05x_P2_DELETE_CURVE = 65

kSE05x_P2_ENCRYPT = 66

kSE05x_P2_DECRYPT = 67

kSE05x_P2_VALIDATE = 68

kSE05x_P2_GENERATE_ONESHOT = 69

kSE05x_P2_VALIDATE_ONESHOT = 70

kSE05x_P2_CRYPTO_LIST = 71

kSE05x_P2_RANDOM = 73

kSE05x_P2_TLS_PMS = 74

kSE05x_P2_TLS_PRF_CLI_HELLO = 75

kSE05x_P2_TLS_PRF_SRV_HELLO = 76

kSE05x_P2_TLS_PRF_CLI_RND = 77

kSE05x_P2_TLS_PRF_SRV_RND = 78

kSE05x_P2_TLS_PRF_BOTH = 90

kSE05x_P2_RAW = 79

kSE05x_P2_IMPORT_EXT = 81

kSE05x_P2_SCP = 82

kSE05x_P2_AUTH_FIRST_PART1 = 83

kSE05x_P2_AUTH_NONFIRST_PART1 = 84

kSE05x_P2_CM_COMMAND = 85

kSE05x_P2_MODE_OF_OPERATION = 86

kSE05x_P2_RESTRICT = 87

kSE05x_P2_SANITY = 88

kSE05x_P2_DH_REVERSE = 89

kSE05x_P2_READ_STATE = 91

kSE05x_P2_ECPM = 98

SE05x_P2_t = enum_anon_107
enum_anon_108 = c_int 
kSE05x_MemoryType_NA = 0

kSE05x_MemoryType_PERSISTENT = 1

kSE05x_MemoryType_TRANSIENT_RESET = 2

kSE05x_MemoryType_TRANSIENT_DESELECT = 3

SE05x_MemoryType_t = enum_anon_108
enum_anon_109 = c_int 
kSE05x_Origin_NA = 0

kSE05x_Origin_EXTERNAL = 1

kSE05x_Origin_INTERNAL = 2

kSE05x_Origin_PROVISIONED = 3

SE05x_Origin_t = enum_anon_109
enum_anon_110 = c_int 
kSE05x_TAG_NA = 0

kSE05x_TAG_SESSION_ID = 16

kSE05x_TAG_POLICY = 17

kSE05x_TAG_MAX_ATTEMPTS = 18

kSE05x_TAG_IMPORT_AUTH_DATA = 19

kSE05x_TAG_IMPORT_AUTH_KEY_ID = 20

kSE05x_TAG_POLICY_CHECK = 21

kSE05x_TAG_1 = 65

kSE05x_TAG_2 = 66

kSE05x_TAG_3 = 67

kSE05x_TAG_4 = 68

kSE05x_TAG_5 = 69

kSE05x_TAG_6 = 70

kSE05x_TAG_7 = 71

kSE05x_TAG_8 = 72

kSE05x_TAG_9 = 73

kSE05x_TAG_10 = 74

kSE05x_TAG_11 = 75

kSE05x_TAG_TIMESTAMP = 79

kSE05x_TAG_SIGNATURE = 82

kSE05x_GP_TAG_CONTRL_REF_PARM = 166

kSE05x_GP_TAG_AID = 79

kSE05x_GP_TAG_KEY_TYPE = 128

kSE05x_GP_TAG_KEY_LEN = 129

kSE05x_GP_TAG_GET_DATA = 131

kSE05x_GP_TAG_DR_SE = 133

kSE05x_GP_TAG_RECEIPT = 134

kSE05x_GP_TAG_SCP_PARMS = 144

SE05x_TAG_t = enum_anon_110
enum_anon_111 = c_int 
kSE05x_ECSignatureAlgo_NA = 0

kSE05x_ECSignatureAlgo_PLAIN = 9

kSE05x_ECSignatureAlgo_SHA = 17

kSE05x_ECSignatureAlgo_SHA_224 = 37

kSE05x_ECSignatureAlgo_SHA_256 = 33

kSE05x_ECSignatureAlgo_SHA_384 = 34

kSE05x_ECSignatureAlgo_SHA_512 = 38

SE05x_ECSignatureAlgo_t = enum_anon_111
enum_anon_112 = c_int 
kSE05x_EDSignatureAlgo_NA = 0

kSE05x_EDSignatureAlgo_ED25519PURE_SHA_512 = 163

SE05x_EDSignatureAlgo_t = enum_anon_112
enum_anon_113 = c_int 
kSE05x_ECDAASignatureAlgo_NA = 0

kSE05x_ECDAASignatureAlgo_ECDAA = 244

SE05x_ECDAASignatureAlgo_t = enum_anon_113
enum_anon_114 = c_int 
kSE05x_ECDHAlgo_NA = 0

kSE05x_ECDHAlgo_EC_SVDP_DH = 1

kSE05x_ECDHAlgo_EC_SVDP_DH_PLAIN = 3

SE05x_ECDHAlgo_t = enum_anon_114
enum_anon_115 = c_int
kSE05x_RSASignatureAlgo_NA = 0

kSE05x_RSASignatureAlgo_SHA1_PKCS1_PSS = 21

kSE05x_RSASignatureAlgo_SHA224_PKCS1_PSS = 43

kSE05x_RSASignatureAlgo_SHA256_PKCS1_PSS = 44

kSE05x_RSASignatureAlgo_SHA384_PKCS1_PSS = 45

kSE05x_RSASignatureAlgo_SHA512_PKCS1_PSS = 46

kSE05x_RSASignatureAlgo_SHA1_PKCS1 = 10

kSE05x_RSASignatureAlgo_SHA_224_PKCS1 = 39

kSE05x_RSASignatureAlgo_SHA_256_PKCS1 = 40

kSE05x_RSASignatureAlgo_SHA_384_PKCS1 = 41

kSE05x_RSASignatureAlgo_SHA_512_PKCS1 = 42

SE05x_RSASignatureAlgo_t = enum_anon_115
enum_anon_116 = c_int
kSE05x_RSAEncryptionAlgo_NA = 0

kSE05x_RSAEncryptionAlgo_NO_PAD = 12

kSE05x_RSAEncryptionAlgo_PKCS1 = 10

kSE05x_RSAEncryptionAlgo_PKCS1_OAEP = 15

SE05x_RSAEncryptionAlgo_t = enum_anon_116
enum_anon_117 = c_int
kSE05x_RSABitLength_NA = 0

kSE05x_RSABitLength_512 = 512

kSE05x_RSABitLength_1024 = 1024

kSE05x_RSABitLength_1152 = 1152

kSE05x_RSABitLength_2048 = 2048

kSE05x_RSABitLength_3072 = 3072

kSE05x_RSABitLength_4096 = 4096

SE05x_RSABitLength_t = enum_anon_117
enum_anon_118 = c_int
kSE05x_RSAKeyComponent_NA = 255

kSE05x_RSAKeyComponent_MOD = 0

kSE05x_RSAKeyComponent_PUB_EXP = 1

kSE05x_RSAKeyComponent_PRIV_EXP = 2

kSE05x_RSAKeyComponent_P = 3

kSE05x_RSAKeyComponent_Q = 4

kSE05x_RSAKeyComponent_DP = 5

kSE05x_RSAKeyComponent_DQ = 6

kSE05x_RSAKeyComponent_INVQ = 7

SE05x_RSAKeyComponent_t = enum_anon_118
enum_anon_119 = c_int
kSE05x_DigestMode_NA = 0

kSE05x_DigestMode_NO_HASH = 0

kSE05x_DigestMode_SHA = 1

kSE05x_DigestMode_SHA224 = 7

kSE05x_DigestMode_SHA256 = 4

kSE05x_DigestMode_SHA384 = 5

kSE05x_DigestMode_SHA512 = 6

SE05x_DigestMode_t = enum_anon_119
enum_anon_120 = c_int
kSE05x_MACAlgo_NA = 0

kSE05x_MACAlgo_HMAC_SHA1 = 24

kSE05x_MACAlgo_HMAC_SHA256 = 25

kSE05x_MACAlgo_HMAC_SHA384 = 26

kSE05x_MACAlgo_HMAC_SHA512 = 27

kSE05x_MACAlgo_CMAC_128 = 49

kSE05x_MACAlgo_DES_CMAC8 = 122

SE05x_MACAlgo_t = enum_anon_120
enum_anon_121 = c_int
kSE05x_AeadAlgo_NA = 0

kSE05x_AeadGCMAlgo = 176

kSE05x_AeadGCM_IVAlgo = 243

kSE05x_AeadCCMAlgo = 244

SE05x_AeadAlgo_t = enum_anon_121
enum_anon_122 = c_int
kSE05x_HkdfMode_NA = 0

kSE05x_HkdfMode_ExtractExpand = 1

kSE05x_HkdfMode_ExpandOnly = 2

SE05x_HkdfMode_t = enum_anon_122
enum_anon_123 = c_int
kSE05x_ECCurve_NA = 0

kSE05x_ECCurve_NIST_P192 = 1

kSE05x_ECCurve_NIST_P224 = 2

kSE05x_ECCurve_NIST_P256 = 3

kSE05x_ECCurve_NIST_P384 = 4

kSE05x_ECCurve_NIST_P521 = 5

kSE05x_ECCurve_Brainpool160 = 6

kSE05x_ECCurve_Brainpool192 = 7

kSE05x_ECCurve_Brainpool224 = 8

kSE05x_ECCurve_Brainpool256 = 9

kSE05x_ECCurve_Brainpool320 = 10

kSE05x_ECCurve_Brainpool384 = 11

kSE05x_ECCurve_Brainpool512 = 12

kSE05x_ECCurve_Secp160k1 = 13

kSE05x_ECCurve_Secp192k1 = 14

kSE05x_ECCurve_Secp224k1 = 15

kSE05x_ECCurve_Secp256k1 = 16

kSE05x_ECCurve_TPM_ECC_BN_P256 = 17

kSE05x_ECCurve_ECC_ED_25519 = 64

kSE05x_ECCurve_ECC_MONT_DH_25519 = 65

kSE05x_ECCurve_ECC_MONT_DH_448 = 67

SE05x_ECCurve_t = enum_anon_123
enum_anon_124 = c_int
kSE05x_ECCurveParam_NA = 0

kSE05x_ECCurveParam_PARAM_A = 1

kSE05x_ECCurveParam_PARAM_B = 2

kSE05x_ECCurveParam_PARAM_G = 4

kSE05x_ECCurveParam_PARAM_N = 8

kSE05x_ECCurveParam_PARAM_PRIME = 16

SE05x_ECCurveParam_t = enum_anon_124
enum_anon_125 = c_int
kSE05x_CipherMode_NA = 0

kSE05x_CipherMode_DES_CBC_NOPAD = 1

kSE05x_CipherMode_DES_CBC_ISO9797_M1 = 2

kSE05x_CipherMode_DES_CBC_ISO9797_M2 = 3

kSE05x_CipherMode_DES_CBC_PKCS5 = 4

kSE05x_CipherMode_DES_ECB_NOPAD = 5

kSE05x_CipherMode_DES_ECB_ISO9797_M1 = 6

kSE05x_CipherMode_DES_ECB_ISO9797_M2 = 7

kSE05x_CipherMode_DES_ECB_PKCS5 = 8

kSE05x_CipherMode_AES_ECB_NOPAD = 14

kSE05x_CipherMode_AES_CBC_NOPAD = 13

kSE05x_CipherMode_AES_CBC_ISO9797_M1 = 22

kSE05x_CipherMode_AES_CBC_ISO9797_M2 = 23

kSE05x_CipherMode_AES_CBC_PKCS5 = 24

kSE05x_CipherMode_AES_GCM = 176

kSE05x_CipherMode_AES_CTR = 240

kSE05x_CipherMode_AES_CTR_INT_IV = 241

kSE05x_CipherMode_AES_GCM_INT_IV = 243

kSE05x_CipherMode_AES_CCM = 244

kSE05x_CipherMode_AES_CCM_INT_IV = 245

SE05x_CipherMode_t = enum_anon_125
enum_anon_126 = c_int
kSE05x_AppletConfig_NA = 0

kSE05x_AppletConfig_ECDAA = 1

kSE05x_AppletConfig_ECDSA_ECDH_ECDHE = 2

kSE05x_AppletConfig_EDDSA = 4

kSE05x_AppletConfig_DH_MONT = 8

kSE05x_AppletConfig_HMAC = 16

kSE05x_AppletConfig_RSA_PLAIN = 32

kSE05x_AppletConfig_RSA_CRT = 64

kSE05x_AppletConfig_AES = 128

kSE05x_AppletConfig_DES = 256

kSE05x_AppletConfig_PBKDF = 512

kSE05x_AppletConfig_TLS = 1024

kSE05x_AppletConfig_MIFARE = 2048

kSE05x_AppletConfig_RFU1 = 4096

kSE05x_AppletConfig_I2CM = 8192

kSE05x_AppletConfig_RFU2 = 16384

SE05x_AppletConfig_t = enum_anon_126
enum_anon_127 = c_int
kSE05x_LockIndicator_NA = 0

kSE05x_LockIndicator_TRANSIENT_LOCK = 1

kSE05x_LockIndicator_PERSISTENT_LOCK = 2

SE05x_LockIndicator_t = enum_anon_127
enum_anon_128 = c_int
kSE05x_RestrictMode_NA = 0

kSE05x_RestrictMode_RESTRICT_NEW = 1

kSE05x_RestrictMode_RESTRICT_ALL = 2

SE05x_RestrictMode_t = enum_anon_128
enum_anon_129 = c_int
kSE05x_LockState_NA = 0

kSE05x_LockState_LOCKED = 1

SE05x_LockState_t = enum_anon_129
enum_anon_130 = c_int
kSE05x_CryptoContext_NA = 0

kSE05x_CryptoContext_DIGEST = 1

kSE05x_CryptoContext_CIPHER = 2

kSE05x_CryptoContext_SIGNATURE = 3

kSE05x_CryptoContext_AEAD = 4

SE05x_CryptoContext_t = enum_anon_130
enum_anon_131 = c_int
kSE05x_Result_NA = 0

kSE05x_Result_SUCCESS = 1

kSE05x_Result_FAILURE = 2

SE05x_Result_t = enum_anon_131
enum_anon_132 = c_int
kSE05x_TransientIndicator_NA = 0

kSE05x_TransientIndicator_PERSISTENT = 1

kSE05x_TransientIndicator_TRANSIENT = 2

SE05x_TransientIndicator_t = enum_anon_132
enum_anon_133 = c_int
kSE05x_SetIndicator_NA = 0

kSE05x_SetIndicator_NOT_SET = 1

kSE05x_SetIndicator_SET = 2

SE05x_SetIndicator_t = enum_anon_133
enum_anon_134 = c_int
kSE05x_MoreIndicator_NA = 0

kSE05x_MoreIndicator_NO_MORE = 1

kSE05x_MoreIndicator_MORE = 2

SE05x_MoreIndicator_t = enum_anon_134
enum_anon_135 = c_int
kSE05x_HealthCheckMode_NA = 0

kSE05x_HealthCheckMode_FIPS = 63750

kSE05x_HealthCheckMode_CODE_SIGNATURE = 65025

kSE05x_HealthCheckMode_DYNAMIC_FLASH_INTEGRITY = 64770

kSE05x_HealthCheckMode_SHIELDING = 64260

kSE05x_HealthCheckMode_SENSOR = 64005

kSE05x_HealthCheckMode_SFR_CHECK = 64515

SE05x_HealthCheckMode_t = enum_anon_135
enum_anon_136 = c_int
kSE05x_PlatformSCPRequest_NA = 0

kSE05x_PlatformSCPRequest_REQUIRED = 1

kSE05x_PlatformSCPRequest_NOT_REQUIRED = 2

SE05x_PlatformSCPRequest_t = enum_anon_136
enum_anon_137 = c_int
kSE05x_CryptoObject_NA = 0

kSE05x_CryptoObject_DIGEST_SHA = (kSE05x_CryptoObject_NA + 1)

kSE05x_CryptoObject_DIGEST_SHA224 = (kSE05x_CryptoObject_DIGEST_SHA + 1)

kSE05x_CryptoObject_DIGEST_SHA256 = (kSE05x_CryptoObject_DIGEST_SHA224 + 1)

kSE05x_CryptoObject_DIGEST_SHA384 = (kSE05x_CryptoObject_DIGEST_SHA256 + 1)

kSE05x_CryptoObject_DIGEST_SHA512 = (kSE05x_CryptoObject_DIGEST_SHA384 + 1)

kSE05x_CryptoObject_DES_CBC_NOPAD = (kSE05x_CryptoObject_DIGEST_SHA512 + 1)

kSE05x_CryptoObject_DES_CBC_ISO9797_M1 = (kSE05x_CryptoObject_DES_CBC_NOPAD + 1)

kSE05x_CryptoObject_DES_CBC_ISO9797_M2 = (kSE05x_CryptoObject_DES_CBC_ISO9797_M1 + 1)

kSE05x_CryptoObject_DES_CBC_PKCS5 = (kSE05x_CryptoObject_DES_CBC_ISO9797_M2 + 1)

kSE05x_CryptoObject_DES_ECB_NOPAD = (kSE05x_CryptoObject_DES_CBC_PKCS5 + 1)

kSE05x_CryptoObject_DES_ECB_ISO9797_M1 = (kSE05x_CryptoObject_DES_ECB_NOPAD + 1)

kSE05x_CryptoObject_DES_ECB_ISO9797_M2 = (kSE05x_CryptoObject_DES_ECB_ISO9797_M1 + 1)

kSE05x_CryptoObject_DES_ECB_PKCS5 = (kSE05x_CryptoObject_DES_ECB_ISO9797_M2 + 1)

kSE05x_CryptoObject_AES_ECB_NOPAD = (kSE05x_CryptoObject_DES_ECB_PKCS5 + 1)

kSE05x_CryptoObject_AES_CBC_NOPAD = (kSE05x_CryptoObject_AES_ECB_NOPAD + 1)

kSE05x_CryptoObject_AES_CBC_ISO9797_M1 = (kSE05x_CryptoObject_AES_CBC_NOPAD + 1)

kSE05x_CryptoObject_AES_CBC_ISO9797_M2 = (kSE05x_CryptoObject_AES_CBC_ISO9797_M1 + 1)

kSE05x_CryptoObject_AES_CBC_PKCS5 = (kSE05x_CryptoObject_AES_CBC_ISO9797_M2 + 1)

kSE05x_CryptoObject_AES_CTR = (kSE05x_CryptoObject_AES_CBC_PKCS5 + 1)

kSE05x_CryptoObject_AES_CTR_INT_IV = (kSE05x_CryptoObject_AES_CTR + 1)

kSE05x_CryptoObject_HMAC_SHA1 = (kSE05x_CryptoObject_AES_CTR_INT_IV + 1)

kSE05x_CryptoObject_HMAC_SHA256 = (kSE05x_CryptoObject_HMAC_SHA1 + 1)

kSE05x_CryptoObject_HMAC_SHA384 = (kSE05x_CryptoObject_HMAC_SHA256 + 1)

kSE05x_CryptoObject_HMAC_SHA512 = (kSE05x_CryptoObject_HMAC_SHA384 + 1)

kSE05x_CryptoObject_CMAC_128 = (kSE05x_CryptoObject_HMAC_SHA512 + 1)

kSE05x_CryptoObject_AES_GCM = (kSE05x_CryptoObject_CMAC_128 + 1)

kSE05x_CryptoObject_AES_GCM_INT_IV = (kSE05x_CryptoObject_AES_GCM + 1)

kSE05x_CryptoObject_AES_CCM = (kSE05x_CryptoObject_AES_GCM_INT_IV + 1)

kSE05x_CryptoObject_AES_CCM_INT_IV = (kSE05x_CryptoObject_AES_CCM + 1)

SE05x_CryptoObject_t = enum_anon_137
enum_anon_138 = c_int
kSE05x_SecObjTyp_NA = 0

kSE05x_SecObjTyp_EC_KEY_PAIR = 1

kSE05x_SecObjTyp_EC_PRIV_KEY = 2

kSE05x_SecObjTyp_EC_PUB_KEY = 3

kSE05x_SecObjTyp_RSA_KEY_PAIR = 4

kSE05x_SecObjTyp_RSA_KEY_PAIR_CRT = 5

kSE05x_SecObjTyp_RSA_PRIV_KEY = 6

kSE05x_SecObjTyp_RSA_PRIV_KEY_CRT = 7

kSE05x_SecObjTyp_RSA_PUB_KEY = 8

kSE05x_SecObjTyp_AES_KEY = 9

kSE05x_SecObjTyp_DES_KEY = 10

kSE05x_SecObjTyp_BINARY_FILE = 11

kSE05x_SecObjTyp_UserID = 12

kSE05x_SecObjTyp_COUNTER = 13

kSE05x_SecObjTyp_PCR = 15

kSE05x_SecObjTyp_CURVE = 16

kSE05x_SecObjTyp_HMAC_KEY = 17

kSE05x_SecObjTyp_EC_KEY_PAIR_NIST_P192 = 33

kSE05x_SecObjTyp_EC_PRIV_KEY_NIST_P192 = 34

kSE05x_SecObjTyp_EC_PUB_KEY_NIST_P192 = 35

kSE05x_SecObjTyp_EC_KEY_PAIR_NIST_P224 = 37

kSE05x_SecObjTyp_EC_PRIV_KEY_NIST_P224 = 38

kSE05x_SecObjTyp_EC_PUB_KEY_NIST_P224 = 39

kSE05x_SecObjTyp_EC_KEY_PAIR_NIST_P256 = 41

kSE05x_SecObjTyp_EC_PRIV_KEY_NIST_P256 = 42

kSE05x_SecObjTyp_EC_PUB_KEY_NIST_P256 = 43

kSE05x_SecObjTyp_EC_KEY_PAIR_NIST_P384 = 45

kSE05x_SecObjTyp_EC_PRIV_KEY_NIST_P384 = 46

kSE05x_SecObjTyp_EC_PUB_KEY_NIST_P384 = 47

kSE05x_SecObjTyp_EC_KEY_PAIR_NIST_P521 = 49

kSE05x_SecObjTyp_EC_PRIV_KEY_NIST_P521 = 50

kSE05x_SecObjTyp_EC_PUB_KEY_NIST_P521 = 51

kSE05x_SecObjTyp_EC_KEY_PAIR_Brainpool160 = 53

kSE05x_SecObjTyp_EC_PRIV_KEY_Brainpool160 = 54

kSE05x_SecObjTyp_EC_PUB_KEY_Brainpool160 = 55

kSE05x_SecObjTyp_EC_KEY_PAIR_Brainpool192 = 57

kSE05x_SecObjTyp_EC_PRIV_KEY_Brainpool192 = 58

kSE05x_SecObjTyp_EC_PUB_KEY_Brainpool192 = 59

kSE05x_SecObjTyp_EC_KEY_PAIR_Brainpool224 = 61

kSE05x_SecObjTyp_EC_PRIV_KEY_Brainpool224 = 62

kSE05x_SecObjTyp_EC_PUB_KEY_Brainpool224 = 63

kSE05x_SecObjTyp_EC_KEY_PAIR_Brainpool256 = 65

kSE05x_SecObjTyp_EC_PRIV_KEY_Brainpool256 = 66

kSE05x_SecObjTyp_EC_PUB_KEY_Brainpool256 = 67

kSE05x_SecObjTyp_EC_KEY_PAIR_Brainpool320 = 69

kSE05x_SecObjTyp_EC_PRIV_KEY_Brainpool320 = 70

kSE05x_SecObjTyp_EC_PUB_KEY_Brainpool320 = 71

kSE05x_SecObjTyp_EC_KEY_PAIR_Brainpool384 = 73

kSE05x_SecObjTyp_EC_PRIV_KEY_Brainpool384 = 74

kSE05x_SecObjTyp_EC_PUB_KEY_Brainpool384 = 75

kSE05x_SecObjTyp_EC_KEY_PAIR_Brainpool512 = 77

kSE05x_SecObjTyp_EC_PRIV_KEY_Brainpool512 = 78

kSE05x_SecObjTyp_EC_PUB_KEY_Brainpool512 = 79

kSE05x_SecObjTyp_EC_KEY_PAIR_Secp160k1 = 81

kSE05x_SecObjTyp_EC_PRIV_KEY_Secp160k1 = 82

kSE05x_SecObjTyp_EC_PUB_KEY_Secp160k1 = 83

kSE05x_SecObjTyp_EC_KEY_PAIR_Secp192k1 = 85

kSE05x_SecObjTyp_EC_PRIV_KEY_Secp192k1 = 86

kSE05x_SecObjTyp_EC_PUB_KEY_Secp192k1 = 87

kSE05x_SecObjTyp_EC_KEY_PAIR_Secp224k1 = 89

kSE05x_SecObjTyp_EC_PRIV_KEY_Secp224k1 = 90

kSE05x_SecObjTyp_EC_PUB_KEY_Secp224k1 = 91

kSE05x_SecObjTyp_EC_KEY_PAIR_Secp256k1 = 93

kSE05x_SecObjTyp_EC_PRIV_KEY_Secp256k1 = 94

kSE05x_SecObjTyp_EC_PUB_KEY_Secp256k1 = 95

kSE05x_SecObjTyp_EC_KEY_PAIR_BN_P256 = 97

kSE05x_SecObjTyp_EC_PRIV_KEY_BN_P256 = 98

kSE05x_SecObjTyp_EC_PUB_KEY_BN_P256 = 99

kSE05x_SecObjTyp_EC_KEY_PAIR_ED25519 = 101

kSE05x_SecObjTyp_EC_PRIV_KEY_ED25519 = 102

kSE05x_SecObjTyp_EC_PUB_KEY_ED25519 = 103

kSE05x_SecObjTyp_EC_KEY_PAIR_MONT_DH_25519 = 105

kSE05x_SecObjTyp_EC_PRIV_KEY_MONT_DH_25519 = 106

kSE05x_SecObjTyp_EC_PUB_KEY_MONT_DH_25519 = 107

kSE05x_SecObjTyp_EC_KEY_PAIR_MONT_DH_448 = 113

kSE05x_SecObjTyp_EC_PRIV_KEY_MONT_DH_448 = 114

kSE05x_SecObjTyp_EC_PUB_KEY_MONT_DH_448 = 115

SE05x_SecObjTyp_t = enum_anon_138
SE05x_SecureObjectType_t = SE05x_SecObjTyp_t
enum_anon_139 = c_int
kSE05x_RSASignAlgo_NA = 0

kSE05x_RSASignAlgo_SHA1_PKCS1_PSS = 21

kSE05x_RSASignAlgo_SHA224_PKCS1_PSS = 43

kSE05x_RSASignAlgo_SHA256_PKCS1_PSS = 44

kSE05x_RSASignAlgo_SHA384_PKCS1_PSS = 45

kSE05x_RSASignAlgo_SHA512_PKCS1_PSS = 46

kSE05x_RSASignAlgo_SHA_224_PKCS1 = 39

kSE05x_RSASignAlgo_SHA_256_PKCS1 = 40

kSE05x_RSASignAlgo_SHA_384_PKCS1 = 41

kSE05x_RSASignAlgo_SHA_512_PKCS1 = 42

SE05x_RSASignAlgo_t = enum_anon_139
enum_anon_140 = c_int
kSE05x_RSAPubKeyComp_NA = 0

kSE05x_RSAPubKeyComp_MOD = kSE05x_RSAKeyComponent_MOD

kSE05x_RSAPubKeyComp_PUB_EXP = kSE05x_RSAKeyComponent_PUB_EXP

SE05x_RSAPubKeyComp_t = enum_anon_140
class union_anon_141(Union):
    pass


union_anon_141.__slots__ = [
    'digest',
    'cipher',
    'mac',
    'aead',
    'union_8bit',
]
union_anon_141._fields_ = [
    ('digest', SE05x_DigestMode_t),
    ('cipher', SE05x_CipherMode_t),
    ('mac', SE05x_MACAlgo_t),
    ('aead', SE05x_AeadAlgo_t),
    ('union_8bit', c_uint8),
]

SE05x_CryptoModeSubType_t = union_anon_141
enum_anon_142 = c_int
kSE05x_TAG_I2CM_Config = 1

kSE05x_TAG_I2CM_Write = 3

kSE05x_TAG_I2CM_Read = 4

SE05x_I2CM_TAG_t = enum_anon_142
enum_anon_143 = c_int
kSE05x_TransientType_Persistent = 0

kSE05x_TransientType_Transient = kSE05x_INS_TRANSIENT

SE05x_TransientType_t = enum_anon_143
enum_anon_144 = c_int
kSE05x_KeyPart_NA = kSE05x_P1_DEFAULT

kSE05x_KeyPart_Pair = kSE05x_P1_KEY_PAIR

kSE05x_KeyPart_Private = kSE05x_P1_PRIVATE

kSE05x_KeyPart_Public = kSE05x_P1_PUBLIC

SE05x_KeyPart_t = enum_anon_144
enum_anon_145 = c_int
kSE05x_Cipher_Oper_NA = 0

kSE05x_Cipher_Oper_Encrypt = kSE05x_P2_ENCRYPT

kSE05x_Cipher_Oper_Decrypt = kSE05x_P2_DECRYPT

SE05x_Cipher_Oper_t = enum_anon_145
enum_anon_146 = c_int
kSE05x_Cipher_Oper_OneShot_NA = 0

kSE05x_Cipher_Oper_OneShot_Encrypt = kSE05x_P2_ENCRYPT_ONESHOT

kSE05x_Cipher_Oper_OneShot_Decrypt = kSE05x_P2_DECRYPT_ONESHOT

SE05x_Cipher_Oper_OneShot_t = enum_anon_146
enum_anon_147 = c_int
kSE05x_Mac_Oper_NA = 0

kSE05x_Mac_Oper_Generate = kSE05x_P2_GENERATE

kSE05x_Mac_Oper_Validate = kSE05x_P2_VALIDATE

SE05x_Mac_Oper_t = enum_anon_147
enum_anon_148 = c_int
kSE05x_AttestationType_None = 0

kSE05x_AttestationType_AUTH = kSE05x_INS_AUTH_OBJECT

SE05x_AttestationType_t = enum_anon_148
enum_anon_149 = c_int
kSE05x_SymmKeyType_NA = 0

kSE05x_SymmKeyType_AES = kSE05x_P1_AES

kSE05x_SymmKeyType_DES = kSE05x_P1_DES

kSE05x_SymmKeyType_HMAC = kSE05x_P1_HMAC

kSE05x_SymmKeyType_CMAC = kSE05x_P1_AES

SE05x_SymmKeyType_t = enum_anon_149
SE05x_Variant_t = SE05x_AppletConfig_t
enum_anon_150 = c_int
kSE05x_TLS_PRF_NA = 0

kSE05x_TLS_PRF_CLI_HELLO = kSE05x_P2_TLS_PRF_CLI_HELLO

kSE05x_TLS_PRF_SRV_HELLO = kSE05x_P2_TLS_PRF_SRV_HELLO

kSE05x_TLS_PRF_CLI_RND = kSE05x_P2_TLS_PRF_CLI_RND

kSE05x_TLS_PRF_SRV_RND = kSE05x_P2_TLS_PRF_SRV_RND

kSE05x_TLS_PRF_BOTH = kSE05x_P2_TLS_PRF_BOTH

SE05x_TLSPerformPRFType_t = enum_anon_150
enum_anon_151 = c_int
kSE05x_AttestationAlgo_NA = 0

kSE05x_AttestationAlgo_EC_PLAIN = kSE05x_ECSignatureAlgo_PLAIN

kSE05x_AttestationAlgo_EC_SHA = kSE05x_ECSignatureAlgo_SHA

kSE05x_AttestationAlgo_EC_SHA_224 = kSE05x_ECSignatureAlgo_SHA_224

kSE05x_AttestationAlgo_EC_SHA_256 = kSE05x_ECSignatureAlgo_SHA_256

kSE05x_AttestationAlgo_EC_SHA_384 = kSE05x_ECSignatureAlgo_SHA_384

kSE05x_AttestationAlgo_EC_SHA_512 = kSE05x_ECSignatureAlgo_SHA_512

kSE05x_AttestationAlgo_ED25519PURE_SHA_512 = kSE05x_EDSignatureAlgo_ED25519PURE_SHA_512

kSE05x_AttestationAlgo_ECDAA = kSE05x_ECDAASignatureAlgo_ECDAA

kSE05x_AttestationAlgo_RSA_SHA1_PKCS1_PSS = kSE05x_RSASignatureAlgo_SHA1_PKCS1_PSS

kSE05x_AttestationAlgo_RSA_SHA224_PKCS1_PSS = kSE05x_RSASignatureAlgo_SHA224_PKCS1_PSS

kSE05x_AttestationAlgo_RSA_SHA256_PKCS1_PSS = kSE05x_RSASignatureAlgo_SHA256_PKCS1_PSS

kSE05x_AttestationAlgo_RSA_SHA384_PKCS1_PSS = kSE05x_RSASignatureAlgo_SHA384_PKCS1_PSS

kSE05x_AttestationAlgo_RSA_SHA512_PKCS1_PSS = kSE05x_RSASignatureAlgo_SHA512_PKCS1_PSS

kSE05x_AttestationAlgo_RSA_SHA_224_PKCS1 = kSE05x_RSASignatureAlgo_SHA_224_PKCS1

kSE05x_AttestationAlgo_RSA_SHA_256_PKCS1 = kSE05x_RSASignatureAlgo_SHA_256_PKCS1

kSE05x_AttestationAlgo_RSA_SHA_384_PKCS1 = kSE05x_RSASignatureAlgo_SHA_384_PKCS1

kSE05x_AttestationAlgo_RSA_SHA_512_PKCS1 = kSE05x_RSASignatureAlgo_SHA_512_PKCS1

SE05x_AttestationAlgo_t = enum_anon_151
enum_anon_152 = c_int
kSE05x_RSAKeyFormat_CRT = kSE05x_P2_DEFAULT

kSE05x_RSAKeyFormat_RAW = kSE05x_P2_RAW

SE05x_RSAKeyFormat_t = enum_anon_152
enum_anon_153 = c_int
kSE05x_ECPMAlgo_PACE_GM = 5

kSE05x_ECPMAlgo_SVDP_DH_PLAIN_XY = 6

SE05x_ECPMAlgo_t = enum_anon_153
SE05x_MacOperation_t = SE05x_MACAlgo_t
SE05x_KeyID_t = c_uint32
SE05x_MaxAttemps_t = c_uint16
enum_anon_154 = c_int # ../../hostlib/hostLib/inc/se05x_tlv.h

smStatus_t = enum_anon_154
class struct_Se05xSession(Structure):
    pass


# sss/inc/fsl_sss_se05x_types.h
class struct__sss_se05x_tunnel_context(Structure):
    pass


struct_Se05xSession.__slots__ = [
    'value',
    'hasSession',
    'authType',
    'auth_id',
    'fp_TXn',
    'fp_Transform',
    'fp_DeCrypt',
    'fp_RawTXn',
    'pChannelCtx',
    'fp_Transmit',
    'pdynScp03Ctx',
    'conn_ctx',
]
struct_Se05xSession._fields_ = [
    ('value', c_uint8 * 8),
    ('hasSession', c_uint8, 1),
    ('authType', SE_AuthType_t),
    ('auth_id', c_uint32),
    ('fp_TXn', CFUNCTYPE(UNCHECKED(smStatus_t), POINTER(struct_Se05xSession), POINTER(tlvHeader_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t), c_uint8)),
    ('fp_Transform', CFUNCTYPE(UNCHECKED(smStatus_t), POINTER(struct_Se05xSession), POINTER(tlvHeader_t), POINTER(c_uint8), c_size_t, POINTER(tlvHeader_t), POINTER(c_uint8), POINTER(c_size_t), c_uint8)),
    ('fp_DeCrypt', CFUNCTYPE(UNCHECKED(smStatus_t), POINTER(struct_Se05xSession), c_size_t, POINTER(c_uint8), POINTER(c_size_t), c_uint8)),
    ('fp_RawTXn', CFUNCTYPE(UNCHECKED(smStatus_t), POINTER(None), POINTER(struct__sss_se05x_tunnel_context), SE_AuthType_t, POINTER(tlvHeader_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t), c_uint8)),
    ('pChannelCtx', POINTER(struct__sss_se05x_tunnel_context)),
    ('fp_Transmit', CFUNCTYPE(UNCHECKED(smStatus_t), SE_AuthType_t, POINTER(tlvHeader_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t), c_uint8)),
    ('pdynScp03Ctx', POINTER(NXSCP03_DynCtx_t)),
    ('conn_ctx', POINTER(None)),
]

Se05xSession_t = struct_Se05xSession# ../../hostlib/hostLib/inc/se05x_tlv.h

class struct_anon_157(Structure):
    pass


struct_anon_157.__slots__ = [
    'value',
    'value_len',
]
struct_anon_157._fields_ = [
    ('value', POINTER(c_uint8)),
    ('value_len', c_size_t),
]

Se05xPolicy_t = struct_anon_157
class struct_anon_158(Structure):
    pass


struct_anon_158.__slots__ = [
    'ts',
]
struct_anon_158._fields_ = [
    ('ts', c_uint8 * 12),
]

SE05x_TimeStamp_t = struct_anon_158
pSe05xSession_t = POINTER(Se05xSession_t)
pSe05xPolicy_t = POINTER(Se05xPolicy_t)
# sss/inc/fsl_sss_se05x_types.h
class struct__sss_se05x_session(Structure):
    pass


struct__sss_se05x_tunnel_context.__slots__ = [
    'se05x_session',
    'tunnelDest',
]
struct__sss_se05x_tunnel_context._fields_ = [
    ('se05x_session', POINTER(struct__sss_se05x_session)),
    ('tunnelDest', sss_tunnel_dest_t),
]

sss_se05x_tunnel_context_t = struct__sss_se05x_tunnel_context
struct__sss_se05x_session.__slots__ = [
    'subsystem',
    's_ctx',
    'ptun_ctx',
]
struct__sss_se05x_session._fields_ = [
    ('subsystem', sss_type_t),
    ('s_ctx', Se05xSession_t),
    ('ptun_ctx', POINTER(sss_se05x_tunnel_context_t)),
]

sss_se05x_session_t = struct__sss_se05x_session
class struct__sss_se05x_object(Structure):
    pass


class struct_anon_161(Structure):
    pass


struct_anon_161.__slots__ = [
    'session',
    'kekKey',
]
struct_anon_161._fields_ = [
    ('session', POINTER(sss_se05x_session_t)),
    ('kekKey', POINTER(struct__sss_se05x_object)),
]

sss_se05x_key_store_t = struct_anon_161
struct__sss_se05x_object.__slots__ = [
    'keyStore',
    'objectType',
    'cipherType',
    'keyId',
    'curve_id',
    'isPersistant',
]
struct__sss_se05x_object._fields_ = [
    ('keyStore', POINTER(sss_se05x_key_store_t)),
    ('objectType', c_uint32),
    ('cipherType', c_uint32),
    ('keyId', c_uint32),
    ('curve_id', SE05x_ECCurve_t),
    ('isPersistant', c_uint8, 1),
]

sss_se05x_object_t = struct__sss_se05x_object
class struct_anon_162(Structure):
    pass


struct_anon_162.__slots__ = [
    'session',
    'keyObject',
    'algorithm',
    'mode',
]
struct_anon_162._fields_ = [
    ('session', POINTER(sss_se05x_session_t)),
    ('keyObject', POINTER(sss_se05x_object_t)),
    ('algorithm', sss_algorithm_t),
    ('mode', sss_mode_t),
]

sss_se05x_derive_key_t = struct_anon_162
class struct_anon_163(Structure):
    pass


struct_anon_163.__slots__ = [
    'session',
    'keyObject',
    'algorithm',
    'mode',
]
struct_anon_163._fields_ = [
    ('session', POINTER(sss_se05x_session_t)),
    ('keyObject', POINTER(sss_se05x_object_t)),
    ('algorithm', sss_algorithm_t),
    ('mode', sss_mode_t),
]

sss_se05x_asymmetric_t = struct_anon_163
class struct_anon_164(Structure):
    pass


struct_anon_164.__slots__ = [
    'session',
    'keyObject',
    'algorithm',
    'mode',
    'cryptoObjectId',
    'cache_data',
    'cache_data_len',
]
struct_anon_164._fields_ = [
    ('session', POINTER(sss_se05x_session_t)),
    ('keyObject', POINTER(sss_se05x_object_t)),
    ('algorithm', sss_algorithm_t),
    ('mode', sss_mode_t),
    ('cryptoObjectId', SE05x_CryptoObject_t),
    ('cache_data', c_uint8 * 16),
    ('cache_data_len', c_size_t),
]

sss_se05x_symmetric_t = struct_anon_164
class struct_anon_165(Structure):
    pass


struct_anon_165.__slots__ = [
    'session',
    'keyObject',
    'algorithm',
    'mode',
    'cryptoObjectId',
]
struct_anon_165._fields_ = [
    ('session', POINTER(sss_se05x_session_t)),
    ('keyObject', POINTER(sss_se05x_object_t)),
    ('algorithm', sss_algorithm_t),
    ('mode', sss_mode_t),
    ('cryptoObjectId', SE05x_CryptoObject_t),
]

sss_se05x_mac_t = struct_anon_165
class struct_anon_166(Structure):
    pass


struct_anon_166.__slots__ = [
    'session',
    'keyObject',
    'algorithm',
    'mode',
    'cryptoObjectId',
    'cache_data',
    'cache_data_len',
]
struct_anon_166._fields_ = [
    ('session', POINTER(sss_se05x_session_t)),
    ('keyObject', POINTER(sss_se05x_object_t)),
    ('algorithm', sss_algorithm_t),
    ('mode', sss_mode_t),
    ('cryptoObjectId', SE05x_CryptoObject_t),
    ('cache_data', c_uint8 * 16),
    ('cache_data_len', c_size_t),
]

sss_se05x_aead_t = struct_anon_166
class struct_anon_167(Structure):
    pass


struct_anon_167.__slots__ = [
    'session',
    'algorithm',
    'mode',
    'digestFullLen',
    'cryptoObjectId',
]
struct_anon_167._fields_ = [
    ('session', POINTER(sss_se05x_session_t)),
    ('algorithm', sss_algorithm_t),
    ('mode', sss_mode_t),
    ('digestFullLen', c_size_t),
    ('cryptoObjectId', SE05x_CryptoObject_t),
]

sss_se05x_digest_t = struct_anon_167
class struct_anon_168(Structure):
    pass


struct_anon_168.__slots__ = [
    'session',
]
struct_anon_168._fields_ = [
    ('session', POINTER(sss_se05x_session_t)),
]

sss_se05x_rng_context_t = struct_anon_168
enum_anon_169 = c_int
kSSS_SE05x_SessionProp_CertUID = (kSSS_SessionProp_au8_Proprietary_Start + 1)

sss_s05x_sesion_prop_au8_t = enum_anon_169
enum_anon_170 = c_int
kSSS_SE05x_SessionProp_CertUIDLen = (kSSS_SessionProp_u32_Optional_Start + 1)

sss_s05x_sesion_prop_u32_t = enum_anon_170
class struct_anon_171(Structure):
    pass


struct_anon_171.__slots__ = [
    'AppletConfig_ECDAA',
    'AppletConfig_ECDSA_ECDH_ECDHE',
    'AppletConfig_EDDSA',
    'AppletConfig_DH_MONT',
    'AppletConfig_HMAC',
    'AppletConfig_RSA_PLAIN',
    'AppletConfig_RSA_CRT',
    'AppletConfig_AES',
    'AppletConfig_DES',
    'AppletConfig_PBKDF',
    'AppletConfig_TLS',
    'AppletConfig_MIFARE',
    'AppletConfig_RFU1',
    'AppletConfig_I2CM',
    'AppletConfig_RFU21',
]
struct_anon_171._fields_ = [
    ('AppletConfig_ECDAA', c_uint8, 1),
    ('AppletConfig_ECDSA_ECDH_ECDHE', c_uint8, 1),
    ('AppletConfig_EDDSA', c_uint8, 1),
    ('AppletConfig_DH_MONT', c_uint8, 1),
    ('AppletConfig_HMAC', c_uint8, 1),
    ('AppletConfig_RSA_PLAIN', c_uint8, 1),
    ('AppletConfig_RSA_CRT', c_uint8, 1),
    ('AppletConfig_AES', c_uint8, 1),
    ('AppletConfig_DES', c_uint8, 1),
    ('AppletConfig_PBKDF', c_uint8, 1),
    ('AppletConfig_TLS', c_uint8, 1),
    ('AppletConfig_MIFARE', c_uint8, 1),
    ('AppletConfig_RFU1', c_uint8, 1),
    ('AppletConfig_I2CM', c_uint8, 1),
    ('AppletConfig_RFU21', c_uint8, 1),
]

SE05x_Applet_Feature_t = struct_anon_171
class struct_anon_172(Structure):
    pass


struct_anon_172.__slots__ = [
    'EXTCFG_FORBID_ECDH',
    'EXTCFG_FORBID_ECDAA',
    'EXTCFG_FORBID_RSA_LT_2K',
    'EXTCFG_FORBID_RSA_SHA1',
    'EXTCFG_FORBID_AES_GCM',
    'EXTCFG_FORBID_AES_GCM_EXT_IV',
    'EXTCFG_FORBID_HKDF_EXTRACT',
]
struct_anon_172._fields_ = [
    ('EXTCFG_FORBID_ECDH', c_uint8, 1),
    ('EXTCFG_FORBID_ECDAA', c_uint8, 1),
    ('EXTCFG_FORBID_RSA_LT_2K', c_uint8, 1),
    ('EXTCFG_FORBID_RSA_SHA1', c_uint8, 1),
    ('EXTCFG_FORBID_AES_GCM', c_uint8, 1),
    ('EXTCFG_FORBID_AES_GCM_EXT_IV', c_uint8, 1),
    ('EXTCFG_FORBID_HKDF_EXTRACT', c_uint8, 1),
]

SE05x_Applet_Feature_Disable_t = struct_anon_172
class struct_anon_173(Structure):
    pass


struct_anon_173.__slots__ = [
    'timeStamp',
    'timeStampLen',
    'chipId',
    'chipIdLen',
    'attribute',
    'attributeLen',
    'cmd',
    'cmdLen',
    'objSize',
    'objSizeLen',
    'signature',
    'signatureLen',
]
struct_anon_173._fields_ = [
    ('timeStamp', SE05x_TimeStamp_t),
    ('timeStampLen', c_size_t),
    ('chipId', c_uint8 * 18),
    ('chipIdLen', c_size_t),
    ('attribute', c_uint8 * (256 + 15)),
    ('attributeLen', c_size_t),
    ('cmd', c_uint8 * 100),
    ('cmdLen', c_size_t),
    ('objSize', c_uint8 * 2),
    ('objSizeLen', c_size_t),
    ('signature', c_uint8 * 512),
    ('signatureLen', c_size_t),
]

sss_se05x_attst_comp_data_t = struct_anon_173
class struct_anon_174(Structure):
    pass


struct_anon_174.__slots__ = [
    'data',
    'valid_number',
]
struct_anon_174._fields_ = [
    ('data', sss_se05x_attst_comp_data_t * 2),
    ('valid_number', c_uint8),
]

sss_se05x_attst_data_t = struct_anon_174
enum_anon_175 = c_int
kSE05x_I2CM_None = 0

kSE05x_I2CM_Configure = (kSE05x_I2CM_None + 1)

kSE05x_I2CM_Write = 3

kSE05x_I2CM_Read = (kSE05x_I2CM_Write + 1)

kSE05x_I2CM_StructuralIssue = 255

SE05x_I2CM_TLV_type_t = enum_anon_175
enum_anon_176 = c_int
kSE05x_I2CM_Success = 90

kSE05x_I2CM_I2C_Nack_Fail = 1

kSE05x_I2CM_I2C_Write_Error = 2

kSE05x_I2CM_I2C_Read_Error = 3

kSE05x_I2CM_I2C_Time_Out_Error = 5

kSE05x_I2CM_Invalid_Tag = 17

kSE05x_I2CM_Invalid_Length = 18

kSE05x_I2CM_Invalid_Length_Encode = 19

kSE05x_I2CM_I2C_Config = 33

SE05x_I2CM_status_t = enum_anon_176
enum_anon_177 = c_int
kSE05x_Security_None = 0

kSE05x_Sign_Request = (kSE05x_Security_None + 1)

kSE05x_Sign_Enc_Request = (kSE05x_Sign_Request + 1)

SE05x_I2CM_securityReq_t = enum_anon_177
enum_anon_178 = c_int
kSE05x_I2CM_Baud_Rate_100Khz = 0

kSE05x_I2CM_Baud_Rate_400Khz = (kSE05x_I2CM_Baud_Rate_100Khz + 1)

SE05x_I2CM_Baud_Rate_t = enum_anon_178
class struct_anon_179(Structure):
    pass


struct_anon_179.__slots__ = [
    'I2C_addr',
    'I2C_baudRate',
    'status',
]
struct_anon_179._fields_ = [
    ('I2C_addr', c_uint8),
    ('I2C_baudRate', SE05x_I2CM_Baud_Rate_t),
    ('status', SE05x_I2CM_status_t),
]

SE05x_I2CM_configData_t = struct_anon_179
class struct_anon_180(Structure):
    pass


struct_anon_180.__slots__ = [
    'operation',
    'keyObject',
]
struct_anon_180._fields_ = [
    ('operation', SE05x_I2CM_securityReq_t),
    ('keyObject', c_uint32),
]

SE05x_I2CM_securityData_t = struct_anon_180
class struct_anon_181(Structure):
    pass


struct_anon_181.__slots__ = [
    'writeLength',
    'wrStatus',
    'writebuf',
]
struct_anon_181._fields_ = [
    ('writeLength', c_uint8),
    ('wrStatus', SE05x_I2CM_status_t),
    ('writebuf', POINTER(c_uint8)),
]

SE05x_I2CM_writeData_t = struct_anon_181
class struct_anon_182(Structure):
    pass


struct_anon_182.__slots__ = [
    'readLength',
    'rdStatus',
    'rdBuf',
]
struct_anon_182._fields_ = [
    ('readLength', c_uint16),
    ('rdStatus', SE05x_I2CM_status_t),
    ('rdBuf', POINTER(c_uint8)),
]

SE05x_I2CM_readData_t = struct_anon_182
class struct_anon_183(Structure):
    pass


struct_anon_183.__slots__ = [
    'issueStatus',
]
struct_anon_183._fields_ = [
    ('issueStatus', SE05x_I2CM_status_t),
]

SE05x_I2CM_structuralIssue_t = struct_anon_183
class union_anon_184(Union):
    pass


union_anon_184.__slots__ = [
    'cfg',
    'sec',
    'w',
    'rd',
    'issue',
]
union_anon_184._fields_ = [
    ('cfg', SE05x_I2CM_configData_t),
    ('sec', SE05x_I2CM_securityData_t),
    ('w', SE05x_I2CM_writeData_t),
    ('rd', SE05x_I2CM_readData_t),
    ('issue', SE05x_I2CM_structuralIssue_t),
]

SE05x_I2CM_INS_type_t = union_anon_184
class struct__SE05x_I2CM_cmd(Structure):
    pass


struct__SE05x_I2CM_cmd.__slots__ = [
    'type',
    'cmd',
]
struct__SE05x_I2CM_cmd._fields_ = [
    ('type', SE05x_I2CM_TLV_type_t),
    ('cmd', SE05x_I2CM_INS_type_t),
]

SE05x_I2CM_cmd_t = struct__SE05x_I2CM_cmd
for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_se05x_mac_validate_one_go'):
        continue
    sss_se05x_mac_validate_one_go = _lib.sss_se05x_mac_validate_one_go
    sss_se05x_mac_validate_one_go.argtypes = [POINTER(sss_se05x_mac_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), c_size_t]
    sss_se05x_mac_validate_one_go.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_se05x_asymmetric_sign'):
        continue
    sss_se05x_asymmetric_sign = _lib.sss_se05x_asymmetric_sign
    sss_se05x_asymmetric_sign.argtypes = [POINTER(sss_se05x_asymmetric_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t)]
    sss_se05x_asymmetric_sign.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_se05x_asymmetric_verify'):
        continue
    sss_se05x_asymmetric_verify = _lib.sss_se05x_asymmetric_verify
    sss_se05x_asymmetric_verify.argtypes = [POINTER(sss_se05x_asymmetric_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), c_size_t]
    sss_se05x_asymmetric_verify.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_se05x_key_store_get_key_attst'):
        continue
    sss_se05x_key_store_get_key_attst = _lib.sss_se05x_key_store_get_key_attst
    sss_se05x_key_store_get_key_attst.argtypes = [POINTER(sss_se05x_key_store_t), POINTER(sss_se05x_object_t), POINTER(c_uint8), POINTER(c_size_t), POINTER(c_size_t), POINTER(sss_se05x_object_t), sss_algorithm_t, POINTER(c_uint8), c_size_t, POINTER(sss_se05x_attst_data_t)]
    sss_se05x_key_store_get_key_attst.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'se05x_sssKeyTypeLenToCurveId'):
        continue
    se05x_sssKeyTypeLenToCurveId = _lib.se05x_sssKeyTypeLenToCurveId
    se05x_sssKeyTypeLenToCurveId.argtypes = [sss_cipher_type_t, c_size_t]
    se05x_sssKeyTypeLenToCurveId.restype = c_uint32
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_i2c_master_txn'):
        continue
    Se05x_i2c_master_txn = _lib.Se05x_i2c_master_txn
    Se05x_i2c_master_txn.argtypes = [POINTER(sss_session_t), POINTER(SE05x_I2CM_cmd_t), c_uint8]
    Se05x_i2c_master_txn.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_i2c_master_attst_txn'):
        continue
    Se05x_i2c_master_attst_txn = _lib.Se05x_i2c_master_attst_txn
    Se05x_i2c_master_attst_txn.argtypes = [POINTER(sss_session_t), POINTER(sss_object_t), POINTER(SE05x_I2CM_cmd_t), POINTER(c_uint8), c_size_t, SE05x_AttestationAlgo_t, POINTER(sss_se05x_attst_comp_data_t), POINTER(c_uint8), POINTER(c_size_t), c_uint8]
    Se05x_i2c_master_attst_txn.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'se05x_GetAppletVersion'):
        continue
    se05x_GetAppletVersion = _lib.se05x_GetAppletVersion
    se05x_GetAppletVersion.argtypes = []
    se05x_GetAppletVersion.restype = c_uint32
    break

# pycli/scripts/fsl_sss_python_export.h
for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_DeleteAll_Iterative'):
        continue
    Se05x_API_DeleteAll_Iterative = _lib.Se05x_API_DeleteAll_Iterative
    Se05x_API_DeleteAll_Iterative.argtypes = [pSe05xSession_t]
    Se05x_API_DeleteAll_Iterative.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_WritePCR_WithType'):
        continue
    Se05x_API_WritePCR_WithType = _lib.Se05x_API_WritePCR_WithType
    Se05x_API_WritePCR_WithType.argtypes = [pSe05xSession_t, SE05x_INS_t, pSe05xPolicy_t, c_uint32, POINTER(c_uint8), c_size_t, POINTER(c_uint8), c_size_t]
    Se05x_API_WritePCR_WithType.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_ReadIDList'):
        continue
    Se05x_API_ReadIDList = _lib.Se05x_API_ReadIDList
    Se05x_API_ReadIDList.argtypes = [pSe05xSession_t, c_uint16, c_uint8, POINTER(c_uint8), POINTER(c_uint8), POINTER(c_size_t)]
    Se05x_API_ReadIDList.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_ReadSize'):
        continue
    Se05x_API_ReadSize = _lib.Se05x_API_ReadSize
    Se05x_API_ReadSize.argtypes = [pSe05xSession_t, c_uint32, POINTER(c_uint16)]
    Se05x_API_ReadSize.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_ReadCryptoObjectList'):
        continue
    Se05x_API_ReadCryptoObjectList = _lib.Se05x_API_ReadCryptoObjectList
    Se05x_API_ReadCryptoObjectList.argtypes = [pSe05xSession_t, POINTER(c_uint8), POINTER(c_size_t)]
    Se05x_API_ReadCryptoObjectList.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_util_openssl_write_pkcs12'):
        continue
    sss_util_openssl_write_pkcs12 = _lib.sss_util_openssl_write_pkcs12
    sss_util_openssl_write_pkcs12.argtypes = [String, String, String, c_long, String, c_long]
    sss_util_openssl_write_pkcs12.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_util_openssl_read_pkcs12'):
        continue
    sss_util_openssl_read_pkcs12 = _lib.sss_util_openssl_read_pkcs12
    sss_util_openssl_read_pkcs12.argtypes = [String, String, POINTER(c_uint8), POINTER(c_uint8)]
    sss_util_openssl_read_pkcs12.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_WriteSymmKey'):
        continue
    Se05x_API_WriteSymmKey = _lib.Se05x_API_WriteSymmKey
    Se05x_API_WriteSymmKey.argtypes = [pSe05xSession_t, pSe05xPolicy_t, SE05x_MaxAttemps_t, c_uint32, SE05x_KeyID_t, POINTER(c_uint8), c_size_t, SE05x_INS_t, SE05x_SymmKeyType_t]
    Se05x_API_WriteSymmKey.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_WriteECKey'):
        continue
    Se05x_API_WriteECKey = _lib.Se05x_API_WriteECKey
    Se05x_API_WriteECKey.argtypes = [pSe05xSession_t, pSe05xPolicy_t, SE05x_MaxAttemps_t, c_uint32, SE05x_ECCurve_t, POINTER(c_uint8), c_size_t, POINTER(c_uint8), c_size_t, SE05x_INS_t, SE05x_KeyPart_t]
    Se05x_API_WriteECKey.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_se05x_create_object_policy_buffer'):
        continue
    sss_se05x_create_object_policy_buffer = _lib.sss_se05x_create_object_policy_buffer
    sss_se05x_create_object_policy_buffer.argtypes = [POINTER(sss_policy_t), POINTER(c_uint8), POINTER(c_size_t)]
    sss_se05x_create_object_policy_buffer.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_se05x_refresh_session'):
        continue
    sss_se05x_refresh_session = _lib.sss_se05x_refresh_session
    sss_se05x_refresh_session.argtypes = [POINTER(sss_se05x_session_t), POINTER(None)]
    sss_se05x_refresh_session.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_se05x_asymmetric_sign'):
        continue
    sss_se05x_asymmetric_sign = _lib.sss_se05x_asymmetric_sign
    sss_se05x_asymmetric_sign.argtypes = [POINTER(sss_se05x_asymmetric_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), POINTER(c_size_t)]
    sss_se05x_asymmetric_sign.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_se05x_asymmetric_verify'):
        continue
    sss_se05x_asymmetric_verify = _lib.sss_se05x_asymmetric_verify
    sss_se05x_asymmetric_verify.argtypes = [POINTER(sss_se05x_asymmetric_t), POINTER(c_uint8), c_size_t, POINTER(c_uint8), c_size_t]
    sss_se05x_asymmetric_verify.restype = sss_status_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_GetVersion'):
        continue
    Se05x_API_GetVersion = _lib.Se05x_API_GetVersion
    Se05x_API_GetVersion.argtypes = [pSe05xSession_t, POINTER(c_uint8), POINTER(c_size_t)]
    Se05x_API_GetVersion.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_TLSCalculatePreMasterSecret'):
        continue
    Se05x_API_TLSCalculatePreMasterSecret = _lib.Se05x_API_TLSCalculatePreMasterSecret
    Se05x_API_TLSCalculatePreMasterSecret.argtypes = [pSe05xSession_t, c_uint32, c_uint32, c_uint32, POINTER(c_uint8), c_size_t]
    Se05x_API_TLSCalculatePreMasterSecret.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_TLSGenerateRandom'):
        continue
    Se05x_API_TLSGenerateRandom = _lib.Se05x_API_TLSGenerateRandom
    Se05x_API_TLSGenerateRandom.argtypes = [pSe05xSession_t, POINTER(c_uint8), POINTER(c_size_t)]
    Se05x_API_TLSGenerateRandom.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_TLSPerformPRF'):
        continue
    Se05x_API_TLSPerformPRF = _lib.Se05x_API_TLSPerformPRF
    Se05x_API_TLSPerformPRF.argtypes = [pSe05xSession_t, c_uint32, c_uint8, POINTER(c_uint8), c_size_t, POINTER(c_uint8), c_size_t, c_uint16, POINTER(c_uint8), POINTER(c_size_t), SE05x_TLSPerformPRFType_t]
    Se05x_API_TLSPerformPRF.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_WriteUserID'):
        continue
    Se05x_API_WriteUserID = _lib.Se05x_API_WriteUserID
    Se05x_API_WriteUserID.argtypes = [pSe05xSession_t, pSe05xPolicy_t, SE05x_MaxAttemps_t, c_uint32, POINTER(c_uint8), c_size_t, SE05x_AttestationType_t]
    Se05x_API_WriteUserID.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_CreateCounter'):
        continue
    Se05x_API_CreateCounter = _lib.Se05x_API_CreateCounter
    Se05x_API_CreateCounter.argtypes = [pSe05xSession_t, pSe05xPolicy_t, c_uint32, c_uint16]
    Se05x_API_CreateCounter.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_SetCounterValue'):
        continue
    Se05x_API_SetCounterValue = _lib.Se05x_API_SetCounterValue
    Se05x_API_SetCounterValue.argtypes = [pSe05xSession_t, c_uint32, c_uint16, c_uint64]
    Se05x_API_SetCounterValue.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_IncCounter'):
        continue
    Se05x_API_IncCounter = _lib.Se05x_API_IncCounter
    Se05x_API_IncCounter.argtypes = [pSe05xSession_t, c_uint32]
    Se05x_API_IncCounter.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_ExportObject'):
        continue
    Se05x_API_ExportObject = _lib.Se05x_API_ExportObject
    Se05x_API_ExportObject.argtypes = [pSe05xSession_t, c_uint32, SE05x_RSAKeyComponent_t, POINTER(c_uint8), POINTER(c_size_t)]
    Se05x_API_ExportObject.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_ImportObject'):
        continue
    Se05x_API_ImportObject = _lib.Se05x_API_ImportObject
    Se05x_API_ImportObject.argtypes = [pSe05xSession_t, c_uint32, SE05x_RSAKeyComponent_t, POINTER(c_uint8), c_size_t]
    Se05x_API_ImportObject.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'Se05x_API_PBKDF2_extended'):
        continue
    Se05x_API_PBKDF2_extended = _lib.Se05x_API_PBKDF2_extended
    Se05x_API_PBKDF2_extended.argtypes = [pSe05xSession_t, c_uint32, POINTER(c_uint8), c_size_t, c_uint32, c_uint16, SE05x_MACAlgo_t, c_uint16, c_uint32, POINTER(c_uint8), POINTER(c_size_t)]
    Se05x_API_PBKDF2_extended.restype = smStatus_t
    break

for _lib in list(_libs.values()):
    if not hasattr(_lib, 'sss_derive_key_sobj_one_go'):
        continue
    sss_derive_key_sobj_one_go = _lib.sss_derive_key_sobj_one_go
    sss_derive_key_sobj_one_go.argtypes = [POINTER(sss_derive_key_t), POINTER(sss_object_t), POINTER(c_uint8), c_size_t, POINTER(sss_object_t), c_uint16]
    sss_derive_key_sobj_one_go.restype = sss_status_t
    break

# ../../sss/inc/fsl_sss_api.h
try:
    SSS_API_VERSION = 1
except:
    pass

try:
    SSS_AES_BLOCK_SIZE = 16
except:
    pass

try:
    SSS_DES_BLOCK_SIZE = 8
except:
    pass

try:
    SSS_DES_KEY_SIZE = 8
except:
    pass

try:
    SSS_DES_IV_SIZE = 8
except:
    pass

def SSS_ENUM(GROUP, 
INDEX):    return (GROUP | INDEX)

try:
    SSS_ALGORITHM_START_AES = 0
except:
    pass

try:
    SSS_ALGORITHM_START_CHACHA = 1
except:
    pass

try:
    SSS_ALGORITHM_START_DES = 2
except:
    pass

try:
    SSS_ALGORITHM_START_SHA = 3
except:
    pass

try:
    SSS_ALGORITHM_START_MAC = 4
except:
    pass

try:
    SSS_ALGORITHM_START_DH = 5
except:
    pass

try:
    SSS_ALGORITHM_START_DSA = 6
except:
    pass

try:
    SSS_ALGORITHM_START_RSASSA_PKCS1_V1_5 = 7
except:
    pass

try:
    SSS_ALGORITHM_START_RSASSA_PKCS1_PSS_MGF1 = 8
except:
    pass

try:
    SSS_ALGORITHM_START_RSAES_PKCS1_OAEP = 9
except:
    pass

try:
    SSS_ALGORITHM_START_RSAES_PKCS1_V1_5 = 10
except:
    pass

try:
    SSS_ALGORITHM_START_RSASSA_NO_PADDING = 11
except:
    pass

try:
    SSS_ALGORITHM_START_ECDSA = 12
except:
    pass

try:
    SSS_ALGORITHM_START_ECDAA = 13
except:
    pass

try:
    kAlgorithm_SSS_RSASSA_PKCS1_OEAP_SHA1 = kAlgorithm_SSS_RSAES_PKCS1_OAEP_SHA1
except:
    pass

try:
    kAlgorithm_SSS_RSASSA_PKCS1_OEAP_SHA224 = kAlgorithm_SSS_RSAES_PKCS1_OAEP_SHA224
except:
    pass

try:
    kAlgorithm_SSS_RSASSA_PKCS1_OEAP_SHA256 = kAlgorithm_SSS_RSAES_PKCS1_OAEP_SHA256
except:
    pass

try:
    kAlgorithm_SSS_RSASSA_PKCS1_OEAP_SHA384 = kAlgorithm_SSS_RSAES_PKCS1_OAEP_SHA384
except:
    pass

try:
    kAlgorithm_SSS_RSASSA_PKCS1_OEAP_SHA512 = kAlgorithm_SSS_RSAES_PKCS1_OAEP_SHA512
except:
    pass

try:
    kAlgorithm_SSS_RSAES_PKCS1_V1_5_SHA1 = kAlgorithm_SSS_RSAES_PKCS1_V1_5
except:
    pass

try:
    kAlgorithm_SSS_RSAES_PKCS1_V1_5_SHA224 = kAlgorithm_SSS_RSAES_PKCS1_V1_5
except:
    pass

try:
    kAlgorithm_SSS_RSAES_PKCS1_V1_5_SHA256 = kAlgorithm_SSS_RSAES_PKCS1_V1_5
except:
    pass

try:
    kAlgorithm_SSS_RSAES_PKCS1_V1_5_SHA384 = kAlgorithm_SSS_RSAES_PKCS1_V1_5
except:
    pass

try:
    kAlgorithm_SSS_RSAES_PKCS1_V1_5_SHA512 = kAlgorithm_SSS_RSAES_PKCS1_V1_5
except:
    pass

# hostlib/hostLib/inc/a71ch_api.h
try:
    A71CH_INJECT_LOCK_STATE_LOCKED = 1
except:
    pass

try:
    A71CH_INJECT_LOCK_STATE_UNLOCKED = 2
except:
    pass

try:
    A71CH_TRANSPORT_LOCK_STATE_LOCKED = 1
except:
    pass

try:
    A71CH_TRANSPORT_LOCK_STATE_UNLOCKED = 2
except:
    pass

try:
    A71CH_TRANSPORT_LOCK_STATE_ALLOW_LOCK = 3
except:
    pass

try:
    A71CH_NO_RESTRICTED_KP = 15
except:
    pass

try:
    A71CH_KEY_PAIR_0 = 0
except:
    pass

try:
    A71CH_KEY_PAIR_1 = 1
except:
    pass

try:
    A71CH_KEY_PAIR_2 = 2
except:
    pass

try:
    A71CH_KEY_PAIR_3 = 3
except:
    pass

try:
    A71CH_PUBLIC_KEY_0 = 0
except:
    pass

try:
    A71CH_PUBLIC_KEY_1 = 1
except:
    pass

try:
    A71CH_PUBLIC_KEY_2 = 2
except:
    pass

try:
    A71CH_SYM_KEY_0 = 0
except:
    pass

try:
    A71CH_SYM_KEY_1 = 1
except:
    pass

try:
    A71CH_SYM_KEY_2 = 2
except:
    pass

try:
    A71CH_SYM_KEY_3 = 3
except:
    pass

try:
    A71CH_SYM_KEY_4 = 4
except:
    pass

try:
    A71CH_SYM_KEY_5 = 5
except:
    pass

try:
    A71CH_SYM_KEY_6 = 6
except:
    pass

try:
    A71CH_SYM_KEY_7 = 7
except:
    pass

try:
    A71CH_COUNTER_0 = 0
except:
    pass

try:
    A71CH_COUNTER_1 = 1
except:
    pass

try:
    A71CH_CFG_KEY_IDX_MODULE_LOCK = 0
except:
    pass

try:
    A71CH_CFG_KEY_IDX_PRIVATE_KEYS = 1
except:
    pass

try:
    A71CH_CFG_KEY_IDX_PUBLIC_KEYS = 2
except:
    pass

try:
    A71CH_SYM_KEY_COMBINED_MAX = 4
except:
    pass

try:
    A71CH_MAP_SIZE_MAX = 203
except:
    pass

try:
    A71CH_MAX_CMD_PAYLOAD_SIZE = 255
except:
    pass

try:
    A71CH_SCP03_MAX_PAYLOAD_SIZE = 239
except:
    pass

try:
    A71CH_GP_STORAGE_SIZE_A = 1024
except:
    pass

try:
    A71CH_GP_STORAGE_SIZE_B = 4096
except:
    pass

try:
    A71CH_GP_STORAGE_GRANULARITY = 32
except:
    pass

try:
    A71CH_GP_STORAGE_MAX_DATA_CHUNK = A71CH_SCP03_MAX_PAYLOAD_SIZE
except:
    pass

try:
    DERIVE_KEYDATA_FROM_SHARED_SECRET_MAX_INFO = 192
except:
    pass

try:
    DERIVE_KEYDATA_FROM_SHARED_SECRET_MAX_DERIVED_DATA = 255
except:
    pass

try:
    A71CH_HKDF_MAX_SALT = 32
except:
    pass

try:
    A71CH_HMAC_SHA256_MAX_DATA_CHUNK = A71CH_SCP03_MAX_PAYLOAD_SIZE
except:
    pass

try:
    A71CH_SHA256_MAX_DATA_CHUNK = A71CH_SCP03_MAX_PAYLOAD_SIZE
except:
    pass

try:
    A71CH_TLS_MAX_LABEL = 24
except:
    pass

try:
    A71CH_MODULE_UNLOCK_CHALLENGE_LEN = 16
except:
    pass

try:
    A71CH_MODULE_UNIQUE_ID_LEN = 18
except:
    pass

try:
    A71CH_MODULE_CERT_UID_LEN = 10
except:
    pass

try:
    A71CH_WRAPPED_KEY_LEN = 24
except:
    pass

try:
    A71CH_PUB_KEY_LEN = 65
except:
    pass

try:
    AX_SHA256_LEN = 32
except:
    pass

try:
    AX_TLS_PSK_MASTER_SECRET_LEN = 48
except:
    pass

try:
    AX_TLS_PSK_HELLO_RANDOM_LEN = 32
except:
    pass

try:
    SESSION_ID_LEN = 4
except:
    pass

try:
    MONOTONIC_COUNTER_BYTE_COUNT = 4
except:
    pass

try:
    A71CH_SCP_MANDATORY = 1
except:
    pass

try:
    A71CH_SCP_NOT_SET_UP = 2
except:
    pass

try:
    A71CH_SCP_KEYS_SET = 3
except:
    pass

try:
    A71CH_SCP_CHANNEL_STATE_UNKNOWN = 15
except:
    pass

try:
    A71CH_UID_IC_TYPE_OFFSET = 2
except:
    pass

try:
    A71CH_UID_IC_FABRICATION_DATA_OFFSET = 8
except:
    pass

try:
    A71CH_UID_IC_SERIAL_NR_OFFSET = 10
except:
    pass

try:
    A71CH_UID_IC_BATCH_ID_OFFSET = 13
except:
    pass

try:
    MAX_CHUNK_LENGTH_LINK = 256
except:
    pass

# ../../hostlib/hostLib/inc/PlugAndTrust_HostLib_Ver.h
try:
    PLUGANDTRUST_HOSTLIB_VER_MAJOR = 3
except:
    pass

try:
    PLUGANDTRUST_HOSTLIB_VER_MINOR = 3
except:
    pass

# ../../hostlib/hostLib/libCommon/infra/sm_api.h
try:
    AX_HOST_LIB_MAJOR = PLUGANDTRUST_HOSTLIB_VER_MAJOR
except:
    pass

try:
    AX_HOST_LIB_MINOR = PLUGANDTRUST_HOSTLIB_VER_MINOR
except:
    pass

try:
    SE_CONNECT_TYPE_START = 0
except:
    pass

try:
    SELECT_APPLET = 0
except:
    pass

try:
    SELECT_NONE = 1
except:
    pass

try:
    SELECT_SSD = 2
except:
    pass

# hostlib/hostLib/inc/nxScp03_Types.h
try:
    kSSS_AuthType_INT_FastSCP_Counter = kSSS_AuthType_INT_ECKey_Counter
except:
    pass

try:
    kSSS_AuthType_FastSCP_Counter = kSSS_AuthType_INT_ECKey_Counter
except:
    pass

try:
    kSSS_AuthType_FastSCP = kSSS_AuthType_ECKey
except:
    pass

try:
    kSSS_AuthType_AppletSCP03 = kSSS_AuthType_AESKey
except:
    pass

SE05x_AuthCtx_t = SE_AuthCtx_t
try:
    kSE05x_AuthType_None = kSSS_AuthType_None
except:
    pass

try:
    kSE05x_AuthType_SCP03 = kSSS_AuthType_SCP03
except:
    pass

try:
    kSE05x_AuthType_UserID = kSSS_AuthType_ID
except:
    pass

try:
    kSE05x_AuthType_AESKey = kSSS_AuthType_AESKey
except:
    pass

try:
    kSE05x_AuthType_ECKey = kSSS_AuthType_ECKey
except:
    pass

SE05x_AuthType_t = SE_AuthType_t
# hostlib/hostLib/inc/se05x_const.h
try:
    SE05X_SESSIONID_LEN = 8
except:
    pass

try:
    SE05X_MAX_BUF_SIZE_CMD = 1024
except:
    pass

try:
    SE05X_MAX_BUF_SIZE_RSP = 1024
except:
    pass

try:
    SE050_MODULE_UNIQUE_ID_LEN = 18
except:
    pass

try:
    SE05X_I2CM_MAX_BUF_SIZE_CMD = 271
except:
    pass

try:
    SE05X_I2CM_MAX_BUF_SIZE_RSP = 271
except:
    pass

try:
    SE05X_I2CM_MAX_TIMESTAMP_SIZE = 12
except:
    pass

try:
    SE05X_I2CM_MAX_FRESHNESS_SIZE = 16
except:
    pass

try:
    SE05X_I2CM_MAX_CHIP_ID_SIZE = 18
except:
    pass

try:
    SE05X_MINIMUM_KEY_DERIVATION_OUTPUT_LEN = 16
except:
    pass

try:
    SE05X_MAX_ATTST_DATA = 2
except:
    pass

try:
    START_SE05X_ID_CURVE_START = 0
except:
    pass

try:
    CIPHER_BLOCK_SIZE = 16
except:
    pass

try:
    DES_BLOCK_SIZE = 8
except:
    pass

try:
    CIPHER_UPDATE_MAX_DATA = 448
except:
    pass

try:
    AEAD_UPDATE_MAX_DATA = 800
except:
    pass

try:
    AEAD_BLOCK_SIZE = 16
except:
    pass

try:
    BINARY_WRITE_MAX_LEN = 500
except:
    pass

try:
    MAX_OBJ_PCR_VALUE_SIZE = 32
except:
    pass

try:
    MAX_POLICY_BUFFER_SIZE = 256
except:
    pass

try:
    MAX_OBJ_POLICY_SIZE = 55
except:
    pass

try:
    MAX_OBJ_POLICY_TYPES = 6
except:
    pass

try:
    DEFAULT_OBJECT_POLICY_SIZE = 8
except:
    pass

try:
    OBJ_POLICY_HEADER_OFFSET = 5
except:
    pass

try:
    OBJ_POLICY_LENGTH_OFFSET = 0
except:
    pass

try:
    OBJ_POLICY_AUTHID_OFFSET = 1
except:
    pass

try:
    OBJ_POLICY_EXT_OFFSET = 9
except:
    pass

try:
    OBJ_POLICY_PCR_DATA_SIZE = (4 + MAX_OBJ_PCR_VALUE_SIZE)
except:
    pass

try:
    OBJ_POLICY_AUTH_DATA_SIZE = 2
except:
    pass

try:
    OBJ_POLICY_OBJ_ID_SIZE = 4
except:
    pass

try:
    SESSION_POLICY_LENGTH_OFFSET = 0
except:
    pass

try:
    SESSION_POLICY_AR_HEADER_OFFSET = 1
except:
    pass

try:
    DEFAULT_SESSION_POLICY_SIZE = 3
except:
    pass

try:
    POLICY_OBJ_FORBID_ALL = 536870912
except:
    pass

try:
    POLICY_OBJ_ALLOW_SIGN = 268435456
except:
    pass

try:
    POLICY_OBJ_ALLOW_VERIFY = 134217728
except:
    pass

try:
    POLICY_OBJ_ALLOW_KA = 67108864
except:
    pass

try:
    POLICY_OBJ_ALLOW_ENC = 33554432
except:
    pass

try:
    POLICY_OBJ_ALLOW_DEC = 16777216
except:
    pass

try:
    POLICY_OBJ_ALLOW_WRAP = 4194304
except:
    pass

try:
    POLICY_OBJ_ALLOW_READ = 2097152
except:
    pass

try:
    POLICY_OBJ_ALLOW_WRITE = 1048576
except:
    pass

try:
    POLICY_OBJ_ALLOW_GEN = 524288
except:
    pass

try:
    POLICY_OBJ_ALLOW_DELETE = 262144
except:
    pass

try:
    POLICY_OBJ_REQUIRE_SM = 131072
except:
    pass

try:
    POLICY_OBJ_REQUIRE_PCR_VALUE = 65536
except:
    pass

try:
    POLICY_OBJ_ALLOW_ATTESTATION = 32768
except:
    pass

try:
    POLICY_OBJ_ALLOW_DESFIRE_AUTHENTICATION = 16384
except:
    pass

try:
    POLICY_OBJ_ALLOW_DESFIRE_DUMP_SESSION_KEYS = 8192
except:
    pass

try:
    POLICY_OBJ_ALLOW_IMPORT_EXPORT = 4096
except:
    pass

try:
    POLICY_OBJ_FORBID_DERIVED_OUTPUT = 2048
except:
    pass

try:
    POLICY_OBJ_ALLOW_KDF_EXT_RANDOM = 1024
except:
    pass

try:
    POLICY_OBJ_ALLOW_TLS_KDF = 2147483648
except:
    pass

try:
    POLICY_OBJ_ALLOW_TLS_PMS = 1073741824
except:
    pass

try:
    POLICY_OBJ_ALLOW_HKDF = 8388608
except:
    pass

try:
    POLICY_OBJ_ALLOW_DESFIRE_CHANGEKEY = 512
except:
    pass

try:
    POLICY_OBJ_ALLOW_DERIVED_INPUT = 256
except:
    pass

try:
    POLICY_OBJ_ALLOW_PBKDF = 128
except:
    pass

try:
    POLICY_OBJ_ALLOW_DESFIRE_KDF = 64
except:
    pass

try:
    POLICY_OBJ_FORBID_EXTERNAL_IV = 32
except:
    pass

try:
    POLICY_OBJ_ALLOW_USAGE_AS_HMAC_PEPPER = 16
except:
    pass

try:
    POLICY_SESSION_MAX_APDU = 32768
except:
    pass

try:
    POLICY_SESSION_MAX_TIME = 16384
except:
    pass

try:
    POLICY_SESSION_ALLOW_REFRESH = 8192
except:
    pass

# hostlib/hostLib/inc/se05x_enums.h
try:
    kSE05x_TAG_GP_CONTRL_REF_PARM = kSE05x_GP_TAG_CONTRL_REF_PARM
except:
    pass

try:
    kSE05x_ECCurve_RESERVED_ID_ECC_ED_25519 = kSE05x_ECCurve_ECC_ED_25519
except:
    pass

try:
    kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_25519 = kSE05x_ECCurve_ECC_MONT_DH_25519
except:
    pass

try:
    kSE05x_ECCurve_RESERVED_ID_ECC_MONT_DH_448 = kSE05x_ECCurve_ECC_MONT_DH_448
except:
    pass

try:
    kSE05x_ECCurve_Total_Weierstrass_Curves = kSE05x_ECCurve_TPM_ECC_BN_P256
except:
    pass

SE05x_CryptoObjectID_t = SE05x_CryptoObject_t
try:
    SE050_MAX_NUMBER_OF_SESSIONS = 2
except:
    pass

try:
    SE050_OBJECT_IDENTIFIER_SIZE = 4
except:
    pass

try:
    SE050_MAX_I2CM_COMMAND_LENGTH = 255
except:
    pass

try:
    SE050_MAX_APDU_PAYLOAD_LENGTH = 892
except:
    pass

try:
    SE050_INS_MASK_INS_CHAR = 224
except:
    pass

try:
    SE050_INS_MASK_INSTRUCTION = 31
except:
    pass

try:
    SE05x_KeyID_KEK_NONE = 0
except:
    pass

try:
    SE05x_KeyID_MFDF_NONE = 0
except:
    pass

try:
    SE05x_MaxAttemps_UNLIMITED = 0
except:
    pass

try:
    SE05x_MaxAttemps_NA = 0
except:
    pass

try:
    kSE05x_INS_READ_With_Attestation = (kSE05x_INS_READ | kSE05x_INS_ATTEST)
except:
    pass

try:
    kSE05x_INS_I2CM_Attestation = (kSE05x_INS_CRYPTO | kSE05x_INS_ATTEST)
except:
    pass

# sss/inc/fsl_sss_se05x_types.h
def SSS_SUBSYSTEM_TYPE_IS_SE05X(subsystem):    return (subsystem == kType_SSS_SE_SE05x)

def SSS_SESSION_TYPE_IS_SE05X(session):    return (session and (SSS_SUBSYSTEM_TYPE_IS_SE05X ((session.contents.subsystem))))

def SSS_KEY_STORE_TYPE_IS_SE05X(keyStore):    return (keyStore and (SSS_SESSION_TYPE_IS_SE05X ((keyStore.contents.session))))

def SSS_OBJECT_TYPE_IS_SE05X(pObject):    return (pObject and (SSS_KEY_STORE_TYPE_IS_SE05X ((pObject.contents.keyStore))))

def SSS_ASYMMETRIC_TYPE_IS_SE05X(context):    return (context and (SSS_SESSION_TYPE_IS_SE05X ((context.contents.session))))

def SSS_DERIVE_KEY_TYPE_IS_SE05X(context):    return (context and (SSS_SESSION_TYPE_IS_SE05X ((context.contents.session))))

def SSS_SYMMETRIC_TYPE_IS_SE05X(context):    return (context and (SSS_SESSION_TYPE_IS_SE05X ((context.contents.session))))

def SSS_MAC_TYPE_IS_SE05X(context):    return (context and (SSS_SESSION_TYPE_IS_SE05X ((context.contents.session))))

def SSS_RNG_CONTEXT_TYPE_IS_SE05X(context):    return (context and (SSS_SESSION_TYPE_IS_SE05X ((context.contents.session))))

def SSS_DIGEST_TYPE_IS_SE05X(context):    return (context and (SSS_SESSION_TYPE_IS_SE05X ((context.contents.session))))

def SSS_AEAD_TYPE_IS_SE05X(context):    return (context and (SSS_SESSION_TYPE_IS_SE05X ((context.contents.session))))

def SSS_TUNNEL_CONTEXT_TYPE_IS_SE05X(context):    return (context and (SSS_SESSION_TYPE_IS_SE05X ((context.contents.session))))

def SSS_TUNNEL_TYPE_IS_SE05X(context):    return (context and (SSS_SESSION_TYPE_IS_SE05X ((context.contents.session))))

SE05x_Connect_Ctx_t = SE_Connect_Ctx_t
se05x_auth_context_t = SE_Connect_Ctx_t
_sss_a71ch_key_store = struct__sss_a71ch_key_store# ../../sss/inc/fsl_sscp_a71ch.h

_sscp_a71ch_context = struct__sscp_a71ch_context
_SE_AuthCtx = struct__SE_AuthCtx# hostlib/hostLib/inc/nxScp03_Types.h

_sss_se05x_tunnel_context = struct__sss_se05x_tunnel_context# sss/inc/fsl_sss_se05x_types.h

_sss_se05x_session = struct__sss_se05x_session
_sss_se05x_object = struct__sss_se05x_object
_SE05x_I2CM_cmd = struct__SE05x_I2CM_cmd
# No inserted files

