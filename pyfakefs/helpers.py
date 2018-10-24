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
import sys
from copy import copy
from stat import S_IFLNK

import os

IS_PY2 = sys.version_info[0] < 3


try:
    text_type = unicode  # Python 2
except NameError:
    text_type = str      # Python 3


def is_int_type(val):
    """Return True if `val` is of integer type."""
    try:               # Python 2
        return isinstance(val, (int, long))
    except NameError:  # Python 3
        return isinstance(val, int)


def is_byte_string(val):
    """Return True if `val` is a bytes-like object, False for a unicode
    string."""
    if not IS_PY2:
        return not hasattr(val, 'encode')
    return isinstance(val, (memoryview, str))


def is_unicode_string(val):
    """Return True if `val` is a unicode string, False for a bytes-like
    object."""
    try:               # Python 2
        return isinstance(val, unicode)
    except NameError:  # Python 3
        return hasattr(val, 'encode')


def make_string_path(dir_name):
    if sys.version_info >= (3, 6):
        dir_name = os.fspath(dir_name)
    return dir_name


class FakeStatResult(object):
    """Mimics os.stat_result for use as return type of `stat()` and similar.
    This is needed as `os.stat_result` has no possibility to set
    nanosecond times directly.
    """
    try:
        long_type = long  # Python 2
    except NameError:
        long_type = int   # Python 3
    _stat_float_times = sys.version_info >= (2, 5)

    def __init__(self, is_windows, initial_time=None):
        self._use_float = None
        self.st_mode = None
        self.st_ino = None
        self.st_dev = None
        self.st_nlink = 0
        self.st_uid = None
        self.st_gid = None
        self._st_size = None
        self.is_windows = is_windows
        if initial_time is not None:
            self._st_atime_ns = self.long_type(initial_time * 1e9)
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
        if sys.version_info < (3, 3):
            self._st_atime_ns = self.long_type(stat_result.st_atime * 1e9)
            self._st_mtime_ns = self.long_type(stat_result.st_mtime * 1e9)
            self._st_ctime_ns = self.long_type(stat_result.st_ctime * 1e9)
        else:
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

    @property
    def st_atime(self):
        """Return the access time in seconds."""
        atime = self._st_atime_ns / 1e9
        return atime if self.use_float else int(atime)

    @property
    def st_mtime(self):
        """Return the modification time in seconds."""
        mtime = self._st_mtime_ns / 1e9
        return mtime if self.use_float else int(mtime)

    @st_ctime.setter
    def st_ctime(self, val):
        """Set the creation time in seconds."""
        self._st_ctime_ns = self.long_type(val * 1e9)

    @st_atime.setter
    def st_atime(self, val):
        """Set the access time in seconds."""
        self._st_atime_ns = self.long_type(val * 1e9)

    @st_mtime.setter
    def st_mtime(self, val):
        """Set the modification time in seconds."""
        self._st_mtime_ns = self.long_type(val * 1e9)

    @property
    def st_size(self):
        if self.st_mode & S_IFLNK == S_IFLNK and self.is_windows:
            return 0
        return self._st_size

    @st_size.setter
    def st_size(self, val):
        self._st_size = val

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

    if sys.version_info >= (3, 3):
        @property
        def st_atime_ns(self):
            """Return the access time in nanoseconds."""
            return self._st_atime_ns

        @property
        def st_mtime_ns(self):
            """Return the modification time in nanoseconds."""
            return self._st_mtime_ns

        @property
        def st_ctime_ns(self):
            """Return the creation time in nanoseconds."""
            return self._st_ctime_ns

        @st_atime_ns.setter
        def st_atime_ns(self, val):
            """Set the access time in nanoseconds."""
            self._st_atime_ns = val

        @st_mtime_ns.setter
        def st_mtime_ns(self, val):
            """Set the modification time of the fake file in nanoseconds."""
            self._st_mtime_ns = val

        @st_ctime_ns.setter
        def st_ctime_ns(self, val):
            """Set the creation time of the fake file in nanoseconds."""
            self._st_ctime_ns = val


class FileBufferIO(object):
    """Stream class that handles both Python2 and Python3 string and
    byte contents for files. The standard io.StringIO cannot be used
    for strings due to the slightly different handling of newline mode.
    Uses an io.BytesIO stream for the raw data and adds handling of encoding
    and newlines.
    """
    def __init__(self, contents=None, linesep='\n', binary=False,
                 newline=None, encoding=None, errors='strict'):
        self._newline = newline
        self._encoding = encoding
        self.errors = errors
        self._linesep = linesep
        self.binary = binary
        self._bytestream = io.BytesIO()
        if contents is not None:
            self.putvalue(contents)
            self._bytestream.seek(0)

    def encoding(self):
        return self._encoding or locale.getpreferredencoding(False)

    def encoded_string(self, contents):
        if is_byte_string(contents):
            return contents
        return contents.encode(self.encoding(), self.errors)

    def decoded_string(self, contents):
        if IS_PY2 and not self._encoding:
            return contents
        return contents.decode(self.encoding(), self.errors)

    def convert_newlines_for_writing(self, s):
        if self.binary:
            return s
        if self._newline in (None, '-'):
            return s.replace('\n', self._linesep)
        if self._newline in ('', '\n'):
            return s
        return s.replace('\n', self._newline)

    def convert_newlines_after_reading(self, s):
        if self._newline is None:
            return s.replace('\r\n', '\n').replace('\r', '\n')
        if self._newline == '-':
            return s.replace(self._linesep, '\n')
        return s

    def read(self, size=-1):
        contents = self._bytestream.read(size)
        if self.binary:
            return contents
        return self.convert_newlines_after_reading(
            self.decoded_string(contents))

    def readline(self, size=-1):
        seek_pos = self._bytestream.tell()
        byte_contents = self._bytestream.read(size)
        if self.binary:
            read_contents = byte_contents
            LF = b'\n'
        else:
            read_contents = self.convert_newlines_after_reading(
                self.decoded_string(byte_contents))
            LF = '\n'
        end_pos = 0

        if self._newline is None:
            end_pos = self._linelen_for_universal_newlines(byte_contents)
            if end_pos > 0:
                length = read_contents.find(LF) + 1
        elif self._newline == '':
            end_pos = self._linelen_for_universal_newlines(byte_contents)
            if end_pos > 0:
                if byte_contents[end_pos - 1] == ord(b'\r'):
                    newline = '\r'
                elif end_pos > 1 and byte_contents[end_pos - 2] == ord(b'\r'):
                    newline = '\r\n'
                else:
                    newline = '\n'
                length = read_contents.find(newline) + len(newline)
        else:
            newline = '\n' if self._newline == '-' else self._newline
            length = read_contents.find(newline)
            if length >= 0:
                nl_len = len(newline)
                end_pos = byte_contents.find(newline.encode()) + nl_len
                length += nl_len

        if end_pos == 0:
            length = len(read_contents)
            end_pos = len(byte_contents)

        self._bytestream.seek(seek_pos + end_pos)
        return (byte_contents[:end_pos] if self.binary
                else read_contents[:length])

    def _linelen_for_universal_newlines(self, byte_contents):
        if self.binary:
            return byte_contents.find(b'\n') + 1
        pos_lf = byte_contents.find(b'\n')
        pos_cr = byte_contents.find(b'\r')
        if pos_lf == -1 and pos_cr == -1:
            return 0
        if pos_lf != -1 and (pos_lf < pos_cr or pos_cr == -1):
            end_pos = pos_lf
        else:
            end_pos = pos_cr
        if end_pos == pos_cr and end_pos + 1 == pos_lf:
            end_pos = pos_lf
        return end_pos + 1

    def readlines(self, size=-1):
        remaining_size = size
        lines = []
        while True:
            line = self.readline(remaining_size)
            if not line:
                return lines
            lines.append(line)
            if size > 0:
                remaining_size -= len(line)
                if remaining_size <= 0:
                    return lines

    def putvalue(self, s):
        self._bytestream.write(self.encoded_string(s))

    def write(self, s):
        if not IS_PY2 and self.binary != is_byte_string(s):
            raise TypeError('Incorrect type for writing')
        contents = self.convert_newlines_for_writing(s)
        length = len(contents)
        self.putvalue(contents)
        return length

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def __iter__(self):
        return self

    def __next__(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line

    # Python 2 version
    def next(self):
        return self.__next__()

    def __getattr__(self, name):
        return getattr(self._bytestream, name)


class NullFileBufferIO(FileBufferIO):
    """Special stream for null device. Does nothing on writing."""
    def putvalue(self, s):
        pass
