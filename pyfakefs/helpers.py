# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Helper classes use for fake file system implementation."""
import io
import locale
import platform
import stat
import sys
import time
from copy import copy
from stat import S_IFLNK

import os

IS_PYPY = platform.python_implementation() == 'PyPy'
IS_WIN = sys.platform == 'win32'
IN_DOCKER = os.path.exists('/.dockerenv')


def is_int_type(val):
    """Return True if `val` is of integer type."""
    return isinstance(val, int)


def is_byte_string(val):
    """Return True if `val` is a bytes-like object, False for a unicode
    string."""
    return not hasattr(val, 'encode')


def is_unicode_string(val):
    """Return True if `val` is a unicode string, False for a bytes-like
    object."""
    return hasattr(val, 'encode')


def make_string_path(dir_name):
    if sys.version_info >= (3, 6):
        dir_name = os.fspath(dir_name)
    return dir_name


def to_string(path):
    """Return the string representation of a byte string using the preferred
     encoding, or the string itself if path is a str."""
    if isinstance(path, bytes):
        return path.decode(locale.getpreferredencoding(False))
    return path


def real_encoding(encoding):
    """Since Python 3.10, the new function ``io.text_encoding`` returns
    "locale" as the encoding if None is defined. This will be handled
    as no encoding in pyfakefs."""
    if sys.version_info >= (3, 10):
        return encoding if encoding != "locale" else None
    return encoding


def now():
    return time.time()


def matching_string(matched, string):
    """Return the string as byte or unicode depending
    on the type of matched, assuming string is an ASCII string.
    """
    if string is None:
        return string
    if isinstance(matched, bytes) and isinstance(string, str):
        return string.encode(locale.getpreferredencoding(False))
    return string


class FakeStatResult:
    """Mimics os.stat_result for use as return type of `stat()` and similar.
    This is needed as `os.stat_result` has no possibility to set
    nanosecond times directly.
    """
    _stat_float_times = True

    def __init__(self, is_windows, user_id, group_id, initial_time=None):
        self._use_float = None
        self.st_mode = None
        self.st_ino = None
        self.st_dev = None
        self.st_nlink = 0
        self.st_uid = user_id
        self.st_gid = group_id
        self._st_size = None
        self.is_windows = is_windows
        if initial_time is not None:
            self._st_atime_ns = int(initial_time * 1e9)
        else:
            self._st_atime_ns = None
        self._st_mtime_ns = self._st_atime_ns
        self._st_ctime_ns = self._st_atime_ns

    @property
    def use_float(self):
        if self._use_float is None:
            return self.stat_float_times()
        return self._use_float

    @use_float.setter
    def use_float(self, val):
        self._use_float = val

    def __eq__(self, other):
        return (
                isinstance(other, FakeStatResult) and
                self._st_atime_ns == other._st_atime_ns and
                self._st_ctime_ns == other._st_ctime_ns and
                self._st_mtime_ns == other._st_mtime_ns and
                self.st_size == other.st_size and
                self.st_gid == other.st_gid and
                self.st_uid == other.st_uid and
                self.st_nlink == other.st_nlink and
                self.st_dev == other.st_dev and
                self.st_ino == other.st_ino and
                self.st_mode == other.st_mode
        )

    def __ne__(self, other):
        return not self == other

    def copy(self):
        """Return a copy where the float usage is hard-coded to mimic the
        behavior of the real os.stat_result.
        """
        stat_result = copy(self)
        stat_result.use_float = self.use_float
        return stat_result

    def set_from_stat_result(self, stat_result):
        """Set values from a real os.stat_result.
        Note: values that are controlled by the fake filesystem are not set.
        This includes st_ino, st_dev and st_nlink.
        """
        self.st_mode = stat_result.st_mode
        self.st_uid = stat_result.st_uid
        self.st_gid = stat_result.st_gid
        self._st_size = stat_result.st_size
        self._st_atime_ns = stat_result.st_atime_ns
        self._st_mtime_ns = stat_result.st_mtime_ns
        self._st_ctime_ns = stat_result.st_ctime_ns

    @classmethod
    def stat_float_times(cls, newvalue=None):
        """Determine whether a file's time stamps are reported as floats
        or ints.

        Calling without arguments returns the current value.
        The value is shared by all instances of FakeOsModule.

        Args:
            newvalue: If `True`, mtime, ctime, atime are reported as floats.
                Otherwise, they are returned as ints (rounding down).
        """
        if newvalue is not None:
            cls._stat_float_times = bool(newvalue)
        return cls._stat_float_times

    @property
    def st_ctime(self):
        """Return the creation time in seconds."""
        ctime = self._st_ctime_ns / 1e9
        return ctime if self.use_float else int(ctime)

    @st_ctime.setter
    def st_ctime(self, val):
        """Set the creation time in seconds."""
        self._st_ctime_ns = int(val * 1e9)

    @property
    def st_atime(self):
        """Return the access time in seconds."""
        atime = self._st_atime_ns / 1e9
        return atime if self.use_float else int(atime)

    @st_atime.setter
    def st_atime(self, val):
        """Set the access time in seconds."""
        self._st_atime_ns = int(val * 1e9)

    @property
    def st_mtime(self):
        """Return the modification time in seconds."""
        mtime = self._st_mtime_ns / 1e9
        return mtime if self.use_float else int(mtime)

    @st_mtime.setter
    def st_mtime(self, val):
        """Set the modification time in seconds."""
        self._st_mtime_ns = int(val * 1e9)

    @property
    def st_size(self):
        if self.st_mode & S_IFLNK == S_IFLNK and self.is_windows:
            return 0
        return self._st_size

    @st_size.setter
    def st_size(self, val):
        self._st_size = val

    @property
    def st_file_attributes(self):
        if not self.is_windows:
            raise AttributeError("module 'os.stat_result' "
                                 "has no attribute 'st_file_attributes'")
        mode = 0
        st_mode = self.st_mode
        if st_mode & stat.S_IFDIR:
            mode |= stat.FILE_ATTRIBUTE_DIRECTORY
        if st_mode & stat.S_IFREG:
            mode |= stat.FILE_ATTRIBUTE_NORMAL
        if st_mode & (stat.S_IFCHR | stat.S_IFBLK):
            mode |= stat.FILE_ATTRIBUTE_DEVICE
        if st_mode & stat.S_IFLNK:
            mode |= stat.FILE_ATTRIBUTE_REPARSE_POINT
        return mode

    @property
    def st_reparse_tag(self):
        if not self.is_windows or sys.version_info < (3, 8):
            raise AttributeError("module 'os.stat_result' "
                                 "has no attribute 'st_reparse_tag'")
        if self.st_mode & stat.S_IFLNK:
            return stat.IO_REPARSE_TAG_SYMLINK
        return 0

    def __getitem__(self, item):
        """Implement item access to mimic `os.stat_result` behavior."""
        import stat

        if item == stat.ST_MODE:
            return self.st_mode
        if item == stat.ST_INO:
            return self.st_ino
        if item == stat.ST_DEV:
            return self.st_dev
        if item == stat.ST_NLINK:
            return self.st_nlink
        if item == stat.ST_UID:
            return self.st_uid
        if item == stat.ST_GID:
            return self.st_gid
        if item == stat.ST_SIZE:
            return self.st_size
        if item == stat.ST_ATIME:
            # item access always returns int for backward compatibility
            return int(self.st_atime)
        if item == stat.ST_MTIME:
            return int(self.st_mtime)
        if item == stat.ST_CTIME:
            return int(self.st_ctime)
        raise ValueError('Invalid item')

    @property
    def st_atime_ns(self):
        """Return the access time in nanoseconds."""
        return self._st_atime_ns

    @st_atime_ns.setter
    def st_atime_ns(self, val):
        """Set the access time in nanoseconds."""
        self._st_atime_ns = val

    @property
    def st_mtime_ns(self):
        """Return the modification time in nanoseconds."""
        return self._st_mtime_ns

    @st_mtime_ns.setter
    def st_mtime_ns(self, val):
        """Set the modification time of the fake file in nanoseconds."""
        self._st_mtime_ns = val

    @property
    def st_ctime_ns(self):
        """Return the creation time in nanoseconds."""
        return self._st_ctime_ns

    @st_ctime_ns.setter
    def st_ctime_ns(self, val):
        """Set the creation time of the fake file in nanoseconds."""
        self._st_ctime_ns = val


class BinaryBufferIO(io.BytesIO):
    """Stream class that handles byte contents for files."""

    def putvalue(self, value):
        self.write(value)


class TextBufferIO(io.TextIOWrapper):
    """Stream class that handles Python string contents for files.
    """

    def __init__(self, contents=None, newline=None, encoding=None,
                 errors='strict'):
        self._bytestream = io.BytesIO(contents)
        super().__init__(self._bytestream, encoding, errors, newline)

    def getvalue(self):
        return self._bytestream.getvalue()

    def putvalue(self, value):
        self._bytestream.write(value)
