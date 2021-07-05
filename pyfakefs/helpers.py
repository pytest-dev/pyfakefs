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
import os
import platform
import stat
import sys
import time
from copy import copy
from stat import S_IFLNK
from typing import Union, Optional, Any, AnyStr, overload, cast

IS_PYPY = platform.python_implementation() == 'PyPy'
IS_WIN = sys.platform == 'win32'
IN_DOCKER = os.path.exists('/.dockerenv')

AnyPath = Union[AnyStr, os.PathLike]


def is_int_type(val: Any) -> bool:
    """Return True if `val` is of integer type."""
    return isinstance(val, int)


def is_byte_string(val: Any) -> bool:
    """Return True if `val` is a bytes-like object, False for a unicode
    string."""
    return not hasattr(val, 'encode')


def is_unicode_string(val: Any) -> bool:
    """Return True if `val` is a unicode string, False for a bytes-like
    object."""
    return hasattr(val, 'encode')


@overload
def make_string_path(dir_name: AnyStr) -> AnyStr: ...


@overload
def make_string_path(dir_name: os.PathLike) -> str: ...


def make_string_path(dir_name: AnyPath) -> AnyStr:
    return cast(AnyStr, os.fspath(dir_name))


def to_string(path: Union[AnyStr, Union[str, bytes]]) -> str:
    """Return the string representation of a byte string using the preferred
     encoding, or the string itself if path is a str."""
    if isinstance(path, bytes):
        return path.decode(locale.getpreferredencoding(False))
    return path


def to_bytes(path: Union[AnyStr, Union[str, bytes]]) -> bytes:
    """Return the bytes representation of a string using the preferred
     encoding, or the byte string itself if path is a byte string."""
    if isinstance(path, str):
        return bytes(path, locale.getpreferredencoding(False))
    return path


def join_strings(s1: AnyStr, s2: AnyStr) -> AnyStr:
    """This is a bit of a hack to satisfy mypy - may be refactored."""
    return s1 + s2


def real_encoding(encoding: Optional[str]) -> Optional[str]:
    """Since Python 3.10, the new function ``io.text_encoding`` returns
    "locale" as the encoding if None is defined. This will be handled
    as no encoding in pyfakefs."""
    if sys.version_info >= (3, 10):
        return encoding if encoding != "locale" else None
    return encoding


def now():
    return time.time()


@overload
def matching_string(matched: bytes, string: AnyStr) -> bytes: ...


@overload
def matching_string(matched: str, string: AnyStr) -> str: ...


@overload
def matching_string(matched: AnyStr, string: None) -> None: ...


def matching_string(  # type: ignore[misc]
        matched: AnyStr, string: Optional[AnyStr]) -> Optional[AnyStr]:
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
    _stat_float_times: bool = True

    def __init__(self, is_windows: bool, user_id: int, group_id: int,
                 initial_time: Optional[float] = None):
        self._use_float: Optional[bool] = None
        self.st_mode: int = 0
        self.st_ino: Optional[int] = None
        self.st_dev: int = 0
        self.st_nlink: int = 0
        self.st_uid: int = user_id
        self.st_gid: int = group_id
        self._st_size: int = 0
        self.is_windows: bool = is_windows
        self._st_atime_ns: int = int((initial_time or 0) * 1e9)
        self._st_mtime_ns: int = self._st_atime_ns
        self._st_ctime_ns: int = self._st_atime_ns

    @property
    def use_float(self) -> bool:
        if self._use_float is None:
            return self.stat_float_times()
        return self._use_float

    @use_float.setter
    def use_float(self, val: bool) -> None:
        self._use_float = val

    def __eq__(self, other: Any) -> bool:
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

    def __ne__(self, other: Any) -> bool:
        return not self == other

    def copy(self) -> "FakeStatResult":
        """Return a copy where the float usage is hard-coded to mimic the
        behavior of the real os.stat_result.
        """
        stat_result = copy(self)
        stat_result.use_float = self.use_float
        return stat_result

    def set_from_stat_result(self, stat_result: os.stat_result) -> None:
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
    def stat_float_times(cls, newvalue: Optional[bool] = None) -> bool:
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
    def st_ctime(self) -> Union[int, float]:
        """Return the creation time in seconds."""
        ctime = self._st_ctime_ns / 1e9
        return ctime if self.use_float else int(ctime)

    @st_ctime.setter
    def st_ctime(self, val: Union[int, float]) -> None:
        """Set the creation time in seconds."""
        self._st_ctime_ns = int(val * 1e9)

    @property
    def st_atime(self) -> Union[int, float]:
        """Return the access time in seconds."""
        atime = self._st_atime_ns / 1e9
        return atime if self.use_float else int(atime)

    @st_atime.setter
    def st_atime(self, val: Union[int, float]) -> None:
        """Set the access time in seconds."""
        self._st_atime_ns = int(val * 1e9)

    @property
    def st_mtime(self) -> Union[int, float]:
        """Return the modification time in seconds."""
        mtime = self._st_mtime_ns / 1e9
        return mtime if self.use_float else int(mtime)

    @st_mtime.setter
    def st_mtime(self, val: Union[int, float]) -> None:
        """Set the modification time in seconds."""
        self._st_mtime_ns = int(val * 1e9)

    @property
    def st_size(self) -> int:
        if self.st_mode & S_IFLNK == S_IFLNK and self.is_windows:
            return 0
        return self._st_size

    @st_size.setter
    def st_size(self, val: int) -> None:
        self._st_size = val

    @property
    def st_file_attributes(self) -> int:
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
    def st_reparse_tag(self) -> int:
        if not self.is_windows or sys.version_info < (3, 8):
            raise AttributeError("module 'os.stat_result' "
                                 "has no attribute 'st_reparse_tag'")
        if self.st_mode & stat.S_IFLNK:
            return stat.IO_REPARSE_TAG_SYMLINK  # type: ignore[attr-defined]
        return 0

    def __getitem__(self, item: int) -> Optional[int]:
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
    def st_atime_ns(self) -> int:
        """Return the access time in nanoseconds."""
        return self._st_atime_ns

    @st_atime_ns.setter
    def st_atime_ns(self, val: int) -> None:
        """Set the access time in nanoseconds."""
        self._st_atime_ns = val

    @property
    def st_mtime_ns(self) -> int:
        """Return the modification time in nanoseconds."""
        return self._st_mtime_ns

    @st_mtime_ns.setter
    def st_mtime_ns(self, val: int) -> None:
        """Set the modification time of the fake file in nanoseconds."""
        self._st_mtime_ns = val

    @property
    def st_ctime_ns(self) -> int:
        """Return the creation time in nanoseconds."""
        return self._st_ctime_ns

    @st_ctime_ns.setter
    def st_ctime_ns(self, val: int) -> None:
        """Set the creation time of the fake file in nanoseconds."""
        self._st_ctime_ns = val


class BinaryBufferIO(io.BytesIO):
    """Stream class that handles byte contents for files."""

    def __init__(self, contents: Optional[bytes]):
        super().__init__(contents or b'')

    def putvalue(self, value: bytes) -> None:
        self.write(value)


class TextBufferIO(io.TextIOWrapper):
    """Stream class that handles Python string contents for files.
    """

    def __init__(self, contents: Optional[bytes] = None,
                 newline: Optional[str] = None,
                 encoding: Optional[str] = None,
                 errors: str = 'strict'):
        self._bytestream = io.BytesIO(contents or b'')
        super().__init__(self._bytestream, encoding, errors, newline)

    def getvalue(self) -> bytes:
        return self._bytestream.getvalue()

    def putvalue(self, value: bytes) -> None:
        self._bytestream.write(value)
