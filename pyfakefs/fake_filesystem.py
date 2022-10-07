# Copyright 2009 Google Inc. All Rights Reserved.
#
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

"""A fake filesystem implementation for unit testing.

:Includes:
  * :py:class:`FakeFile`: Provides the appearance of a real file.
  * :py:class:`FakeDirectory`: Provides the appearance of a real directory.
  * :py:class:`FakeFilesystem`: Provides the appearance of a real directory
    hierarchy.
  * :py:class:`FakeOsModule`: Uses :py:class:`FakeFilesystem` to provide a
    fake :py:mod:`os` module replacement.
  * :py:class:`FakeIoModule`: Uses :py:class:`FakeFilesystem` to provide a
    fake ``io`` module replacement.
  * :py:class:`FakePathModule`:  Faked ``os.path`` module replacement.
  * :py:class:`FakeFileOpen`:  Faked ``file()`` and ``open()`` function
    replacements.

:Usage:

>>> from pyfakefs import fake_filesystem
>>> filesystem = fake_filesystem.FakeFilesystem()
>>> os_module = fake_filesystem.FakeOsModule(filesystem)
>>> pathname = '/a/new/dir/new-file'

Create a new file object, creating parent directory objects as needed:

>>> os_module.path.exists(pathname)
False
>>> new_file = filesystem.create_file(pathname)

File objects can't be overwritten:

>>> os_module.path.exists(pathname)
True
>>> try:
...   filesystem.create_file(pathname)
... except OSError as e:
...   assert e.errno == errno.EEXIST, 'unexpected errno: %d' % e.errno
...   assert e.strerror == 'File exists in the fake filesystem'

Remove a file object:

>>> filesystem.remove_object(pathname)
>>> os_module.path.exists(pathname)
False

Create a new file object at the previous path:

>>> beatles_file = filesystem.create_file(pathname,
...     contents='Dear Prudence\\nWon\\'t you come out to play?\\n')
>>> os_module.path.exists(pathname)
True

Use the FakeFileOpen class to read fake file objects:

>>> file_module = fake_filesystem.FakeFileOpen(filesystem)
>>> for line in file_module(pathname):
...     print(line.rstrip())
...
Dear Prudence
Won't you come out to play?

File objects cannot be treated like directory objects:

>>> try:
...   os_module.listdir(pathname)
... except OSError as e:
...   assert e.errno == errno.ENOTDIR, 'unexpected errno: %d' % e.errno
...   assert e.strerror == 'Not a directory in the fake filesystem'

The FakeOsModule can list fake directory objects:

>>> os_module.listdir(os_module.path.dirname(pathname))
['new-file']

The FakeOsModule also supports stat operations:

>>> import stat
>>> stat.S_ISREG(os_module.stat(pathname).st_mode)
True
>>> stat.S_ISDIR(os_module.stat(os_module.path.dirname(pathname)).st_mode)
True
"""
import errno
import functools
import heapq
import inspect
import io
import locale
import os
import random
import sys
import traceback
import uuid
from collections import namedtuple, OrderedDict
from contextlib import contextmanager
from doctest import TestResults
from enum import Enum
from stat import (
    S_IFREG, S_IFDIR, S_ISLNK, S_IFMT, S_ISDIR, S_IFLNK, S_ISREG, S_IFSOCK
)
from types import ModuleType, TracebackType
from typing import (
    List, Optional, Callable, Union, Any, Dict, Tuple, cast, AnyStr, overload,
    NoReturn, ClassVar, IO, Iterator, TextIO, Type
)
from pyfakefs.extra_packages import use_scandir
from pyfakefs.fake_scandir import scandir, walk, ScanDirIter
from pyfakefs.helpers import (
    FakeStatResult, BinaryBufferIO, TextBufferIO,
    is_int_type, is_byte_string, is_unicode_string, make_string_path,
    IS_PYPY, to_string, matching_string, real_encoding, now, AnyPath, to_bytes
)
from pyfakefs import __version__  # noqa: F401 for upwards compatibility

PERM_READ = 0o400  # Read permission bit.
PERM_WRITE = 0o200  # Write permission bit.
PERM_EXE = 0o100  # Execute permission bit.
PERM_DEF = 0o777  # Default permission bits.
PERM_DEF_FILE = 0o666  # Default permission bits (regular file)
PERM_ALL = 0o7777  # All permission bits.

_OpenModes = namedtuple(
    '_OpenModes',
    'must_exist can_read can_write truncate append must_not_exist'
)

_OPEN_MODE_MAP = {
    # mode name:(file must exist, can read, can write,
    #            truncate, append, must not exist)
    'r': (True, True, False, False, False, False),
    'w': (False, False, True, True, False, False),
    'a': (False, False, True, False, True, False),
    'r+': (True, True, True, False, False, False),
    'w+': (False, True, True, True, False, False),
    'a+': (False, True, True, False, True, False),
    'x': (False, False, True, False, False, True),
    'x+': (False, True, True, False, False, True)
}

AnyFileWrapper = Union[
    "FakeFileWrapper", "FakeDirWrapper",
    "StandardStreamWrapper", "FakePipeWrapper"
]

AnyString = Union[str, bytes]

AnyFile = Union["FakeFile", "FakeDirectory"]

if sys.platform.startswith('linux'):
    # on newer Linux system, the default maximum recursion depth is 40
    # we ignore older systems here
    _MAX_LINK_DEPTH = 40
else:
    # on MacOS and Windows, the maximum recursion depth is 32
    _MAX_LINK_DEPTH = 32

NR_STD_STREAMS = 3
if sys.platform == 'win32':
    USER_ID = 1
    GROUP_ID = 1
else:
    USER_ID = os.getuid()
    GROUP_ID = os.getgid()


class OSType(Enum):
    """Defines the real or simulated OS of the underlying file system."""
    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"


class PatchMode(Enum):
    """Defines if patching shall be on, off, or in automatic mode.
    Currently only used for `patch_open_code` option.
    """
    OFF = 1
    AUTO = 2
    ON = 3


def set_uid(uid: int) -> None:
    """Set the global user id. This is used as st_uid for new files
    and to differentiate between a normal user and the root user (uid 0).
    For the root user, some permission restrictions are ignored.

    Args:
        uid: (int) the user ID of the user calling the file system functions.
    """
    global USER_ID
    USER_ID = uid


def set_gid(gid: int) -> None:
    """Set the global group id. This is only used to set st_gid for new files,
    no permission checks are performed.

    Args:
        gid: (int) the group ID of the user calling the file system functions.
    """
    global GROUP_ID
    GROUP_ID = gid


def reset_ids() -> None:
    """Set the global user ID and group ID back to default values."""
    if sys.platform == 'win32':
        set_uid(1)
        set_gid(1)
    else:
        set_uid(os.getuid())
        set_gid(os.getgid())


def is_root() -> bool:
    """Return True if the current user is the root user."""
    return USER_ID == 0


class FakeLargeFileIoException(Exception):
    """Exception thrown on unsupported operations for fake large files.
    Fake large files have a size with no real content.
    """

    def __init__(self, file_path: str) -> None:
        super(FakeLargeFileIoException, self).__init__(
            'Read and write operations not supported for '
            'fake large file: %s' % file_path)


def _copy_module(old: ModuleType) -> ModuleType:
    """Recompiles and creates new module object."""
    saved = sys.modules.pop(old.__name__, None)
    new = __import__(old.__name__)
    if saved is not None:
        sys.modules[old.__name__] = saved
    return new


class FakeFile:
    """Provides the appearance of a real file.

    Attributes currently faked out:
      * `st_mode`: user-specified, otherwise S_IFREG
      * `st_ctime`: the time.time() timestamp of the file change time (updated
        each time a file's attributes is modified).
      * `st_atime`: the time.time() timestamp when the file was last accessed.
      * `st_mtime`: the time.time() timestamp when the file was last modified.
      * `st_size`: the size of the file
      * `st_nlink`: the number of hard links to the file
      * `st_ino`: the inode number - a unique number identifying the file
      * `st_dev`: a unique number identifying the (fake) file system device
        the file belongs to
      * `st_uid`: always set to USER_ID, which can be changed globally using
            `set_uid`
      * `st_gid`: always set to GROUP_ID, which can be changed globally using
            `set_gid`

    .. note:: The resolution for `st_ctime`, `st_mtime` and `st_atime` in the
        real file system depends on the used file system (for example it is
        only 1s for HFS+ and older Linux file systems, but much higher for
        ext4 and NTFS). This is currently ignored by pyfakefs, which uses
        the resolution of `time.time()`.

        Under Windows, `st_atime` is not updated for performance reasons by
        default. pyfakefs never updates `st_atime` under Windows, assuming
        the default setting.
    """
    stat_types = (
        'st_mode', 'st_ino', 'st_dev', 'st_nlink', 'st_uid', 'st_gid',
        'st_size', 'st_atime', 'st_mtime', 'st_ctime',
        'st_atime_ns', 'st_mtime_ns', 'st_ctime_ns'
    )

    def __init__(self, name: AnyStr,
                 st_mode: int = S_IFREG | PERM_DEF_FILE,
                 contents: Optional[AnyStr] = None,
                 filesystem: Optional["FakeFilesystem"] = None,
                 encoding: Optional[str] = None,
                 errors: Optional[str] = None,
                 side_effect: Optional[Callable[["FakeFile"], None]] = None):
        """
        Args:
            name: Name of the file/directory, without parent path information
            st_mode: The stat.S_IF* constant representing the file type (i.e.
                stat.S_IFREG, stat.S_IFDIR), and the file permissions.
                If no file type is set (e.g. permission flags only), a
                regular file type is assumed.
            contents: The contents of the filesystem object; should be a string
                or byte object for regular files, and a dict of other
                FakeFile or FakeDirectory objects wih the file names as
                keys for FakeDirectory objects
            filesystem: The fake filesystem where the file is created.
            encoding: If contents is a unicode string, the encoding used
                for serialization.
            errors: The error mode used for encoding/decoding errors.
            side_effect: function handle that is executed when file is written,
                must accept the file object as an argument.
        """
        # to be backwards compatible regarding argument order, we raise on None
        if filesystem is None:
            raise ValueError('filesystem shall not be None')
        self.filesystem: FakeFilesystem = filesystem
        self._side_effect: Optional[Callable] = side_effect
        self.name: AnyStr = name  # type: ignore[assignment]
        self.stat_result = FakeStatResult(
            filesystem.is_windows_fs, USER_ID, GROUP_ID, now())
        if st_mode >> 12 == 0:
            st_mode |= S_IFREG
        self.stat_result.st_mode = st_mode
        self.st_size: int = 0
        self.encoding: Optional[str] = real_encoding(encoding)
        self.errors: str = errors or 'strict'
        self._byte_contents: Optional[bytes] = self._encode_contents(contents)
        self.stat_result.st_size = (
            len(self._byte_contents) if self._byte_contents is not None else 0)
        self.epoch: int = 0
        self.parent_dir: Optional[FakeDirectory] = None
        # Linux specific: extended file system attributes
        self.xattr: Dict = {}
        self.opened_as: AnyString = ''

    @property
    def byte_contents(self) -> Optional[bytes]:
        """Return the contents as raw byte array."""
        return self._byte_contents

    @property
    def contents(self) -> Optional[str]:
        """Return the contents as string with the original encoding."""
        if isinstance(self.byte_contents, bytes):
            return self.byte_contents.decode(
                self.encoding or locale.getpreferredencoding(False),
                errors=self.errors)
        return None

    @property
    def st_ctime(self) -> float:
        """Return the creation time of the fake file."""
        return self.stat_result.st_ctime

    @st_ctime.setter
    def st_ctime(self, val: float) -> None:
        """Set the creation time of the fake file."""
        self.stat_result.st_ctime = val

    @property
    def st_atime(self) -> float:
        """Return the access time of the fake file."""
        return self.stat_result.st_atime

    @st_atime.setter
    def st_atime(self, val: float) -> None:
        """Set the access time of the fake file."""
        self.stat_result.st_atime = val

    @property
    def st_mtime(self) -> float:
        """Return the modification time of the fake file."""
        return self.stat_result.st_mtime

    @st_mtime.setter
    def st_mtime(self, val: float) -> None:
        """Set the modification time of the fake file."""
        self.stat_result.st_mtime = val

    def set_large_file_size(self, st_size: int) -> None:
        """Sets the self.st_size attribute and replaces self.content with None.

        Provided specifically to simulate very large files without regards
        to their content (which wouldn't fit in memory).
        Note that read/write operations with such a file raise
            :py:class:`FakeLargeFileIoException`.

        Args:
          st_size: (int) The desired file size

        Raises:
          OSError: if the st_size is not a non-negative integer,
                   or if st_size exceeds the available file system space
        """
        self._check_positive_int(st_size)
        if self.st_size:
            self.size = 0
        if self.filesystem:
            self.filesystem.change_disk_usage(st_size, self.name, self.st_dev)
        self.st_size = st_size
        self._byte_contents = None

    def _check_positive_int(self, size: int) -> None:
        # the size should be an positive integer value
        if not is_int_type(size) or size < 0:
            self.filesystem.raise_os_error(errno.ENOSPC, self.name)

    def is_large_file(self) -> bool:
        """Return `True` if this file was initialized with size
         but no contents.
        """
        return self._byte_contents is None

    def _encode_contents(
            self, contents: Union[str, bytes, None]) -> Optional[bytes]:
        if is_unicode_string(contents):
            contents = bytes(
                cast(str, contents),
                self.encoding or locale.getpreferredencoding(False),
                self.errors)
        return cast(bytes, contents)

    def set_initial_contents(self, contents: AnyStr) -> bool:
        """Sets the file contents and size.
           Called internally after initial file creation.

        Args:
            contents: string, new content of file.

        Returns:
            True if the contents have been changed.

        Raises:
              OSError: if the st_size is not a non-negative integer,
                   or if st_size exceeds the available file system space
        """
        byte_contents = self._encode_contents(contents)
        changed = self._byte_contents != byte_contents
        st_size = len(byte_contents) if byte_contents else 0

        current_size = self.st_size or 0
        self.filesystem.change_disk_usage(
            st_size - current_size, self.name, self.st_dev)
        self._byte_contents = byte_contents
        self.st_size = st_size
        self.epoch += 1
        return changed

    def set_contents(self, contents: AnyStr,
                     encoding: Optional[str] = None) -> bool:
        """Sets the file contents and size and increases the modification time.
        Also executes the side_effects if available.

        Args:
          contents: (str, bytes) new content of file.
          encoding: (str) the encoding to be used for writing the contents
                    if they are a unicode string.
                    If not given, the locale preferred encoding is used.

        Returns:
            True if the contents have been changed.

        Raises:
          OSError: if `st_size` is not a non-negative integer,
                   or if it exceeds the available file system space.
        """
        self.encoding = real_encoding(encoding)
        changed = self.set_initial_contents(contents)
        if self._side_effect is not None:
            self._side_effect(self)
        return changed

    @property
    def size(self) -> int:
        """Return the size in bytes of the file contents.
        """
        return self.st_size

    @size.setter
    def size(self, st_size: int) -> None:
        """Resizes file content, padding with nulls if new size exceeds the
        old size.

        Args:
          st_size: The desired size for the file.

        Raises:
          OSError: if the st_size arg is not a non-negative integer
                   or if st_size exceeds the available file system space
        """

        self._check_positive_int(st_size)
        current_size = self.st_size or 0
        self.filesystem.change_disk_usage(
            st_size - current_size, self.name, self.st_dev)
        if self._byte_contents:
            if st_size < current_size:
                self._byte_contents = self._byte_contents[:st_size]
            else:
                self._byte_contents += b'\0' * (st_size - current_size)
        self.st_size = st_size
        self.epoch += 1

    @property
    def path(self) -> AnyStr:
        """Return the full path of the current object."""
        names: List[AnyStr] = []
        obj: Optional[FakeFile] = self
        while obj:
            names.insert(
                0, matching_string(self.name, obj.name))  # type: ignore
            obj = obj.parent_dir
        sep = self.filesystem.get_path_separator(names[0])
        if names[0] == sep:
            names.pop(0)
            dir_path = sep.join(names)
            drive = self.filesystem.splitdrive(dir_path)[0]
            # if a Windows path already starts with a drive or UNC path,
            # no extra separator is needed
            if not drive:
                dir_path = sep + dir_path
        else:
            dir_path = sep.join(names)
        return self.filesystem.absnormpath(dir_path)

    def __getattr__(self, item: str) -> Any:
        """Forward some properties to stat_result."""
        if item in self.stat_types:
            return getattr(self.stat_result, item)
        return super().__getattribute__(item)

    def __setattr__(self, key: str, value: Any) -> None:
        """Forward some properties to stat_result."""
        if key in self.stat_types:
            return setattr(self.stat_result, key, value)
        return super().__setattr__(key, value)

    def __str__(self) -> str:
        return '%r(%o)' % (self.name, self.st_mode)


class FakeNullFile(FakeFile):
    def __init__(self, filesystem: "FakeFilesystem") -> None:
        devnull = 'nul' if filesystem.is_windows_fs else '/dev/null'
        super(FakeNullFile, self).__init__(
            devnull, filesystem=filesystem, contents='')

    @property
    def byte_contents(self) -> bytes:
        return b''

    def set_initial_contents(self, contents: AnyStr) -> bool:
        return False


class FakeFileFromRealFile(FakeFile):
    """Represents a fake file copied from the real file system.

    The contents of the file are read on demand only.
    """

    def __init__(self, file_path: str, filesystem: "FakeFilesystem",
                 side_effect: Optional[Callable] = None) -> None:
        """
        Args:
            file_path: Path to the existing file.
            filesystem: The fake filesystem where the file is created.

        Raises:
            OSError: if the file does not exist in the real file system.
            OSError: if the file already exists in the fake file system.
        """
        super().__init__(
            name=os.path.basename(file_path), filesystem=filesystem,
            side_effect=side_effect)
        self.contents_read = False

    @property
    def byte_contents(self) -> Optional[bytes]:
        if not self.contents_read:
            self.contents_read = True
            with io.open(self.file_path, 'rb') as f:
                self._byte_contents = f.read()
        # On MacOS and BSD, the above io.open() updates atime on the real file
        self.st_atime = os.stat(self.file_path).st_atime
        return self._byte_contents

    def set_contents(self, contents, encoding=None):
        self.contents_read = True
        super(FakeFileFromRealFile, self).set_contents(contents, encoding)

    def is_large_file(self):
        """The contents are never faked."""
        return False


class FakeDirectory(FakeFile):
    """Provides the appearance of a real directory."""

    def __init__(self, name: str, perm_bits: int = PERM_DEF,
                 filesystem: Optional["FakeFilesystem"] = None):
        """
        Args:
            name:  name of the file/directory, without parent path information
            perm_bits: permission bits. defaults to 0o777.
            filesystem: if set, the fake filesystem where the directory
                is created
        """
        FakeFile.__init__(
            self, name, S_IFDIR | perm_bits, '', filesystem=filesystem)
        # directories have the link count of contained entries,
        # including '.' and '..'
        self.st_nlink += 1
        self._entries: Dict[str, AnyFile] = {}

    def set_contents(self, contents: AnyStr,
                     encoding: Optional[str] = None) -> bool:
        raise self.filesystem.raise_os_error(errno.EISDIR, self.path)

    @property
    def entries(self) -> Dict[str, FakeFile]:
        """Return the list of contained directory entries."""
        return self._entries

    @property
    def ordered_dirs(self) -> List[str]:
        """Return the list of contained directory entry names ordered by
        creation order.
        """
        return [item[0] for item in sorted(
            self._entries.items(), key=lambda entry: entry[1].st_ino)]

    def add_entry(self, path_object: FakeFile) -> None:
        """Adds a child FakeFile to this directory.

        Args:
            path_object: FakeFile instance to add as a child of this directory.

        Raises:
            OSError: if the directory has no write permission (Posix only)
            OSError: if the file or directory to be added already exists
        """
        if (not is_root() and not self.st_mode & PERM_WRITE and
                not self.filesystem.is_windows_fs):
            raise OSError(errno.EACCES, 'Permission Denied', self.path)

        path_object_name: str = to_string(path_object.name)
        if path_object_name in self.entries:
            self.filesystem.raise_os_error(errno.EEXIST, self.path)

        self._entries[path_object_name] = path_object
        path_object.parent_dir = self
        if path_object.st_ino is None:
            self.filesystem.last_ino += 1
            path_object.st_ino = self.filesystem.last_ino
        self.st_nlink += 1
        path_object.st_nlink += 1
        path_object.st_dev = self.st_dev
        if path_object.st_nlink == 1:
            self.filesystem.change_disk_usage(
                path_object.size, path_object.name, self.st_dev)

    def get_entry(self, pathname_name: str) -> AnyFile:
        """Retrieves the specified child file or directory entry.

        Args:
            pathname_name: The basename of the child object to retrieve.

        Returns:
            The fake file or directory object.

        Raises:
            KeyError: if no child exists by the specified name.
        """
        pathname_name = self._normalized_entryname(pathname_name)
        return self.entries[to_string(pathname_name)]

    def _normalized_entryname(self, pathname_name: str) -> str:
        if not self.filesystem.is_case_sensitive:
            matching_names = [name for name in self.entries
                              if name.lower() == pathname_name.lower()]
            if matching_names:
                pathname_name = matching_names[0]
        return pathname_name

    def remove_entry(self, pathname_name: str, recursive: bool = True) -> None:
        """Removes the specified child file or directory.

        Args:
            pathname_name: Basename of the child object to remove.
            recursive: If True (default), the entries in contained directories
                are deleted first. Used to propagate removal errors
                (e.g. permission problems) from contained entries.

        Raises:
            KeyError: if no child exists by the specified name.
            OSError: if user lacks permission to delete the file,
                or (Windows only) the file is open.
        """
        pathname_name = self._normalized_entryname(pathname_name)
        entry = self.get_entry(pathname_name)
        if self.filesystem.is_windows_fs:
            if entry.st_mode & PERM_WRITE == 0:
                self.filesystem.raise_os_error(errno.EACCES, pathname_name)
            if self.filesystem.has_open_file(entry):
                self.filesystem.raise_os_error(errno.EACCES, pathname_name)
        else:
            if (not is_root() and (self.st_mode & (PERM_WRITE | PERM_EXE) !=
                                   PERM_WRITE | PERM_EXE)):
                self.filesystem.raise_os_error(errno.EACCES, pathname_name)

        if recursive and isinstance(entry, FakeDirectory):
            while entry.entries:
                entry.remove_entry(list(entry.entries)[0])
        elif entry.st_nlink == 1:
            self.filesystem.change_disk_usage(
                -entry.size, pathname_name, entry.st_dev)

        self.st_nlink -= 1
        entry.st_nlink -= 1
        assert entry.st_nlink >= 0

        del self.entries[to_string(pathname_name)]

    @property
    def size(self) -> int:
        """Return the total size of all files contained in this directory tree.
        """
        return sum([item[1].size for item in self.entries.items()])

    @size.setter
    def size(self, st_size: int) -> None:
        """Setting the size is an error for a directory."""
        raise self.filesystem.raise_os_error(errno.EISDIR, self.path)

    def has_parent_object(self, dir_object: "FakeDirectory") -> bool:
        """Return `True` if dir_object is a direct or indirect parent
        directory, or if both are the same object."""
        obj: Optional[FakeDirectory] = self
        while obj:
            if obj == dir_object:
                return True
            obj = obj.parent_dir
        return False

    def __str__(self) -> str:
        description = super(FakeDirectory, self).__str__() + ':\n'
        for item in self.entries:
            item_desc = self.entries[item].__str__()
            for line in item_desc.split('\n'):
                if line:
                    description = description + '  ' + line + '\n'
        return description


class FakeDirectoryFromRealDirectory(FakeDirectory):
    """Represents a fake directory copied from the real file system.

    The contents of the directory are read on demand only.
    """

    def __init__(self, source_path: AnyPath, filesystem: "FakeFilesystem",
                 read_only: bool, target_path: Optional[AnyPath] = None):
        """
        Args:
            source_path: Full directory path.
            filesystem: The fake filesystem where the directory is created.
            read_only: If set, all files under the directory are treated
                as read-only, e.g. a write access raises an exception;
                otherwise, writing to the files changes the fake files
                only as usually.
            target_path: If given, the target path of the directory,
                otherwise the target is the same as `source_path`.

        Raises:
            OSError: if the directory does not exist in the real file system
        """
        target_path = target_path or source_path
        real_stat = os.stat(source_path)
        super(FakeDirectoryFromRealDirectory, self).__init__(
            name=to_string(os.path.split(target_path)[1]),
            perm_bits=real_stat.st_mode,
            filesystem=filesystem)

        self.st_ctime = real_stat.st_ctime
        self.st_atime = real_stat.st_atime
        self.st_mtime = real_stat.st_mtime
        self.st_gid = real_stat.st_gid
        self.st_uid = real_stat.st_uid
        self.source_path = source_path  # type: ignore
        self.read_only = read_only
        self.contents_read = False

    @property
    def entries(self) -> Dict[str, FakeFile]:
        """Return the list of contained directory entries, loading them
        if not already loaded."""
        if not self.contents_read:
            self.contents_read = True
            base = self.path
            for entry in os.listdir(self.source_path):
                source_path = os.path.join(self.source_path, entry)
                target_path = os.path.join(base, entry)  # type: ignore
                if os.path.islink(source_path):
                    self.filesystem.add_real_symlink(source_path, target_path)
                elif os.path.isdir(source_path):
                    self.filesystem.add_real_directory(
                        source_path, self.read_only, target_path=target_path)
                else:
                    self.filesystem.add_real_file(
                        source_path, self.read_only, target_path=target_path)
        return self._entries

    @property
    def size(self) -> int:
        # we cannot get the size until the contents are loaded
        if not self.contents_read:
            return 0
        return super(FakeDirectoryFromRealDirectory, self).size

    @size.setter
    def size(self, st_size: int) -> None:
        raise self.filesystem.raise_os_error(errno.EISDIR, self.path)


class FakeFilesystem:
    """Provides the appearance of a real directory tree for unit testing.

    Attributes:
        path_separator: The path separator, corresponds to `os.path.sep`.
        alternative_path_separator: Corresponds to `os.path.altsep`.
        is_windows_fs: `True` in a real or faked Windows file system.
        is_macos: `True` under MacOS, or if we are faking it.
        is_case_sensitive: `True` if a case-sensitive file system is assumed.
        root: The root :py:class:`FakeDirectory` entry of the file system.
        umask: The umask used for newly created files, see `os.umask`.
        patcher: Holds the Patcher object if created from it. Allows access
            to the patcher object if using the pytest fs fixture.
        patch_open_code: Defines how `io.open_code` will be patched;
            patching can be on, off, or in automatic mode.
        shuffle_listdir_results: If `True`, `os.listdir` will not sort the
            results to match the real file system behavior.
    """

    def __init__(self, path_separator: str = os.path.sep,
                 total_size: int = None,
                 patcher: Any = None) -> None:
        """
        Args:
            path_separator:  optional substitute for os.path.sep
            total_size: if not None, the total size in bytes of the
                root filesystem.

        Example usage to use the same path separator under all systems:

        >>> filesystem = FakeFilesystem(path_separator='/')

        """
        self.path_separator: str = path_separator
        self.alternative_path_separator: Optional[str] = os.path.altsep
        self.patcher = patcher
        if path_separator != os.sep:
            self.alternative_path_separator = None

        # is_windows_fs can be used to test the behavior of pyfakefs under
        # Windows fs on non-Windows systems and vice verse;
        # is it used to support drive letters, UNC paths and some other
        # Windows-specific features
        self._is_windows_fs = sys.platform == 'win32'

        # can be used to test some MacOS-specific behavior under other systems
        self._is_macos = sys.platform == 'darwin'

        # is_case_sensitive can be used to test pyfakefs for case-sensitive
        # file systems on non-case-sensitive systems and vice verse
        self.is_case_sensitive: bool = (
            not (self.is_windows_fs or self._is_macos)
        )

        self.root = FakeDirectory(self.path_separator, filesystem=self)
        self._cwd = ''

        # We can't query the current value without changing it:
        self.umask = os.umask(0o22)
        os.umask(self.umask)

        # A list of open file objects. Their position in the list is their
        # file descriptor number
        self.open_files: List[Optional[List[AnyFileWrapper]]] = []
        # A heap containing all free positions in self.open_files list
        self._free_fd_heap: List[int] = []
        # last used numbers for inodes (st_ino) and devices (st_dev)
        self.last_ino: int = 0
        self.last_dev: int = 0
        self.mount_points: Dict[AnyString, Dict] = OrderedDict()
        self._add_root_mount_point(total_size)
        self._add_standard_streams()
        self.dev_null = FakeNullFile(self)
        # set from outside if needed
        self.patch_open_code = PatchMode.OFF
        self.shuffle_listdir_results = False

    @property
    def is_linux(self) -> bool:
        return not self.is_windows_fs and not self.is_macos

    @property
    def is_windows_fs(self) -> bool:
        return self._is_windows_fs

    @is_windows_fs.setter
    def is_windows_fs(self, value: bool) -> None:
        if self._is_windows_fs != value:
            self._is_windows_fs = value
            self.reset()
            FakePathModule.reset(self)

    @property
    def is_macos(self) -> bool:
        return self._is_macos

    @is_macos.setter
    def is_macos(self, value: bool) -> None:
        if self._is_macos != value:
            self._is_macos = value
            self.reset()
            FakePathModule.reset(self)

    @property
    def cwd(self) -> str:
        """Return the current working directory of the fake filesystem."""
        return self._cwd

    @cwd.setter
    def cwd(self, value: str) -> None:
        """Set the current working directory of the fake filesystem.
        Make sure a new drive or share is auto-mounted under Windows.
        """
        self._cwd = value
        self._auto_mount_drive_if_needed(value)

    @property
    def root_dir(self) -> FakeDirectory:
        """Return the root directory, which represents "/" under POSIX,
        and the current drive under Windows."""
        if self.is_windows_fs:
            return self._mount_point_dir_for_cwd()
        return self.root

    @property
    def root_dir_name(self) -> str:
        """Return the root directory name, which is "/" under POSIX,
        and the root path of the current drive under Windows."""
        root_dir = to_string(self.root_dir.name)
        if not root_dir.endswith(self.path_separator):
            return root_dir + self.path_separator
        return root_dir

    @property
    def os(self) -> OSType:
        """Return the real or simulated type of operating system."""
        return (OSType.WINDOWS if self.is_windows_fs else
                OSType.MACOS if self.is_macos else OSType.LINUX)

    @os.setter
    def os(self, value: OSType) -> None:
        """Set the simulated type of operating system underlying the fake
        file system."""
        self._is_windows_fs = value == OSType.WINDOWS
        self._is_macos = value == OSType.MACOS
        self.is_case_sensitive = value == OSType.LINUX
        self.path_separator = '\\' if value == OSType.WINDOWS else '/'
        self.alternative_path_separator = ('/' if value == OSType.WINDOWS
                                           else None)
        self.reset()
        FakePathModule.reset(self)

    def reset(self, total_size: Optional[int] = None):
        """Remove all file system contents and reset the root."""
        self.root = FakeDirectory(self.path_separator, filesystem=self)

        self.open_files = []
        self._free_fd_heap = []
        self.last_ino = 0
        self.last_dev = 0
        self.mount_points = OrderedDict()
        self._add_root_mount_point(total_size)
        self._add_standard_streams()
        from pyfakefs import fake_pathlib
        fake_pathlib.init_module(self)

    def _add_root_mount_point(self, total_size):
        mount_point = 'C:' if self.is_windows_fs else self.path_separator
        self._cwd = mount_point
        if not self.cwd.endswith(self.path_separator):
            self._cwd += self.path_separator
        self.add_mount_point(mount_point, total_size)

    def pause(self) -> None:
        """Pause the patching of the file system modules until `resume` is
        called. After that call, all file system calls are executed in the
        real file system.
        Calling pause() twice is silently ignored.
        Only allowed if the file system object was created by a
        Patcher object. This is also the case for the pytest `fs` fixture.

        Raises:
            RuntimeError: if the file system was not created by a Patcher.
        """
        if self.patcher is None:
            raise RuntimeError('pause() can only be called from a fake file '
                               'system object created by a Patcher object')
        self.patcher.pause()

    def resume(self) -> None:
        """Resume the patching of the file system modules if `pause` has
        been called before. After that call, all file system calls are
        executed in the fake file system.
        Does nothing if patching is not paused.
        Raises:
            RuntimeError: if the file system has not been created by `Patcher`.
        """
        if self.patcher is None:
            raise RuntimeError('resume() can only be called from a fake file '
                               'system object created by a Patcher object')
        self.patcher.resume()

    def clear_cache(self) -> None:
        """Clear the cache of non-patched modules."""
        if self.patcher:
            self.patcher.clear_cache()

    def line_separator(self) -> str:
        return '\r\n' if self.is_windows_fs else '\n'

    def raise_os_error(self, err_no: int,
                       filename: Optional[AnyString] = None,
                       winerror: Optional[int] = None) -> NoReturn:
        """Raises OSError.
        The error message is constructed from the given error code and shall
        start with the error string issued in the real system.
        Note: this is not true under Windows if winerror is given - in this
        case a localized message specific to winerror will be shown in the
        real file system.

        Args:
            err_no: A numeric error code from the C variable errno.
            filename: The name of the affected file, if any.
            winerror: Windows only - the specific Windows error code.
        """
        message = os.strerror(err_no) + ' in the fake filesystem'
        if (winerror is not None and sys.platform == 'win32' and
                self.is_windows_fs):
            raise OSError(err_no, message, filename, winerror)
        raise OSError(err_no, message, filename)

    def get_path_separator(self, path: AnyStr) -> AnyStr:
        """Return the path separator as the same type as path"""
        return matching_string(path, self.path_separator)

    def _alternative_path_separator(
            self, path: AnyStr) -> Optional[AnyStr]:
        """Return the alternative path separator as the same type as path"""
        return matching_string(path, self.alternative_path_separator)

    def starts_with_sep(self, path: AnyStr) -> bool:
        """Return True if path starts with a path separator."""
        sep = self.get_path_separator(path)
        altsep = self._alternative_path_separator(path)
        return (path.startswith(sep) or altsep is not None and
                path.startswith(altsep))

    def add_mount_point(self, path: AnyStr,
                        total_size: Optional[int] = None,
                        can_exist: bool = False) -> Dict:
        """Add a new mount point for a filesystem device.
        The mount point gets a new unique device number.

        Args:
            path: The root path for the new mount path.

            total_size: The new total size of the added filesystem device
                in bytes. Defaults to infinite size.

            can_exist: If True, no error is raised if the mount point
                already exists

        Returns:
            The newly created mount point dict.

        Raises:
            OSError: if trying to mount an existing mount point again,
                and `can_exist` is False.
        """
        path = self.normpath(self.normcase(path))
        for mount_point in self.mount_points:
            if (self.is_case_sensitive and
                    path == matching_string(path, mount_point) or
                    not self.is_case_sensitive and
                    path.lower() == matching_string(
                        path, mount_point.lower())):
                if can_exist:
                    return self.mount_points[mount_point]
                self.raise_os_error(errno.EEXIST, path)

        self.last_dev += 1
        self.mount_points[path] = {
            'idev': self.last_dev, 'total_size': total_size, 'used_size': 0
        }
        if path == matching_string(path, self.root.name):
            # special handling for root path: has been created before
            root_dir = self.root
            self.last_ino += 1
            root_dir.st_ino = self.last_ino
        else:
            root_dir = self._create_mount_point_dir(path)
        root_dir.st_dev = self.last_dev
        return self.mount_points[path]

    def _create_mount_point_dir(
            self, directory_path: AnyPath) -> FakeDirectory:
        """A version of `create_dir` for the mount point directory creation,
        which avoids circular calls and unneeded checks.
         """
        dir_path = self.make_string_path(directory_path)
        path_components = self._path_components(dir_path)
        current_dir = self.root

        new_dirs = []
        for component in [to_string(p) for p in path_components]:
            directory = self._directory_content(
                current_dir, to_string(component))[1]
            if not directory:
                new_dir = FakeDirectory(component, filesystem=self)
                new_dirs.append(new_dir)
                current_dir.add_entry(new_dir)
                current_dir = new_dir
            else:
                current_dir = cast(FakeDirectory, directory)

        for new_dir in new_dirs:
            new_dir.st_mode = S_IFDIR | PERM_DEF

        return current_dir

    def _auto_mount_drive_if_needed(self, path: AnyStr) -> Optional[Dict]:
        """Windows only: if `path` is located on an unmounted drive or UNC
        mount point, the drive/mount point is added to the mount points."""
        if self.is_windows_fs:
            drive = self.splitdrive(path)[0]
            if drive:
                return self.add_mount_point(path=drive, can_exist=True)
        return None

    def _mount_point_for_path(self, path: AnyStr) -> Dict:
        path = self.absnormpath(self._original_path(path))
        for mount_path in self.mount_points:
            if path == matching_string(path, mount_path):
                return self.mount_points[mount_path]
        mount_path = matching_string(path, '')
        drive = self.splitdrive(path)[0]
        for root_path in self.mount_points:
            root_path = matching_string(path, root_path)
            if drive and not root_path.startswith(drive):
                continue
            if path.startswith(root_path) and len(root_path) > len(mount_path):
                mount_path = root_path
        if mount_path:
            return self.mount_points[to_string(mount_path)]
        mount_point = self._auto_mount_drive_if_needed(path)
        assert mount_point
        return mount_point

    def _mount_point_dir_for_cwd(self) -> FakeDirectory:
        """Return the fake directory object of the mount point where the
        current working directory points to."""
        def object_from_path(file_path):
            path_components = self._path_components(file_path)
            target = self.root
            for component in path_components:
                target = target.get_entry(component)
            return target

        path = to_string(self.cwd)
        for mount_path in self.mount_points:
            if path == to_string(mount_path):
                return object_from_path(mount_path)
        mount_path = ''
        drive = to_string(self.splitdrive(path)[0])
        for root_path in self.mount_points:
            str_root_path = to_string(root_path)
            if drive and not str_root_path.startswith(drive):
                continue
            if (path.startswith(str_root_path) and
                    len(str_root_path) > len(mount_path)):
                mount_path = root_path
        return object_from_path(mount_path)

    def _mount_point_for_device(self, idev: int) -> Optional[Dict]:
        for mount_point in self.mount_points.values():
            if mount_point['idev'] == idev:
                return mount_point
        return None

    def get_disk_usage(
            self, path: AnyStr = None) -> Tuple[int, int, int]:
        """Return the total, used and free disk space in bytes as named tuple,
        or placeholder values simulating unlimited space if not set.

        .. note:: This matches the return value of shutil.disk_usage().

        Args:
            path: The disk space is returned for the file system device where
                `path` resides.
                Defaults to the root path (e.g. '/' on Unix systems).
        """
        DiskUsage = namedtuple('DiskUsage', 'total, used, free')
        if path is None:
            mount_point = next(iter(self.mount_points.values()))
        else:
            file_path = make_string_path(path)
            mount_point = self._mount_point_for_path(file_path)
        if mount_point and mount_point['total_size'] is not None:
            return DiskUsage(mount_point['total_size'],
                             mount_point['used_size'],
                             mount_point['total_size'] -
                             mount_point['used_size'])
        return DiskUsage(
            1024 * 1024 * 1024 * 1024, 0, 1024 * 1024 * 1024 * 1024)

    def set_disk_usage(
            self, total_size: int, path: Optional[AnyStr] = None) -> None:
        """Changes the total size of the file system, preserving the
        used space.
        Example usage: set the size of an auto-mounted Windows drive.

        Args:
            total_size: The new total size of the filesystem in bytes.

            path: The disk space is changed for the file system device where
                `path` resides.
                Defaults to the root path (e.g. '/' on Unix systems).

        Raises:
            OSError: if the new space is smaller than the used size.
        """
        file_path: AnyStr = (path if path is not None  # type: ignore
                             else self.root_dir_name)
        mount_point = self._mount_point_for_path(file_path)
        if (mount_point['total_size'] is not None and
                mount_point['used_size'] > total_size):
            self.raise_os_error(errno.ENOSPC, path)
        mount_point['total_size'] = total_size

    def change_disk_usage(self, usage_change: int,
                          file_path: AnyStr, st_dev: int) -> None:
        """Change the used disk space by the given amount.

        Args:
            usage_change: Number of bytes added to the used space.
                If negative, the used space will be decreased.

            file_path: The path of the object needing the disk space.

            st_dev: The device ID for the respective file system.

        Raises:
            OSError: if usage_change exceeds the free file system space
        """
        mount_point = self._mount_point_for_device(st_dev)
        if mount_point:
            total_size = mount_point['total_size']
            if total_size is not None:
                if total_size - mount_point['used_size'] < usage_change:
                    self.raise_os_error(errno.ENOSPC, file_path)
            mount_point['used_size'] += usage_change

    def stat(self, entry_path: AnyStr,
             follow_symlinks: bool = True):
        """Return the os.stat-like tuple for the FakeFile object of entry_path.

        Args:
            entry_path:  Path to filesystem object to retrieve.
            follow_symlinks: If False and entry_path points to a symlink,
                the link itself is inspected instead of the linked object.

        Returns:
            The FakeStatResult object corresponding to entry_path.

        Raises:
            OSError: if the filesystem object doesn't exist.
        """
        # stat should return the tuple representing return value of os.stat
        try:
            file_object = self.resolve(
                entry_path, follow_symlinks,
                allow_fd=True, check_read_perm=False)
        except TypeError:
            file_object = self.resolve(entry_path)
        if not is_root():
            # make sure stat raises if a parent dir is not readable
            parent_dir = file_object.parent_dir
            if parent_dir:
                self.get_object(parent_dir.path)  # type: ignore[arg-type]

        self.raise_for_filepath_ending_with_separator(
            entry_path, file_object, follow_symlinks)

        return file_object.stat_result.copy()

    def raise_for_filepath_ending_with_separator(
            self, entry_path: AnyStr,
            file_object: FakeFile,
            follow_symlinks: bool = True,
            macos_handling: bool = False) -> None:
        if self.ends_with_path_separator(entry_path):
            if S_ISLNK(file_object.st_mode):
                try:
                    link_object = self.resolve(entry_path)
                except OSError as exc:
                    if self.is_macos and exc.errno != errno.ENOENT:
                        return
                    if self.is_windows_fs:
                        self.raise_os_error(errno.EINVAL, entry_path)
                    raise
                if not follow_symlinks or self.is_windows_fs or self.is_macos:
                    file_object = link_object
            if self.is_windows_fs:
                is_error = S_ISREG(file_object.st_mode)
            elif self.is_macos and macos_handling:
                is_error = not S_ISLNK(file_object.st_mode)
            else:
                is_error = not S_ISDIR(file_object.st_mode)
            if is_error:
                error_nr = (errno.EINVAL if self.is_windows_fs
                            else errno.ENOTDIR)
                self.raise_os_error(error_nr, entry_path)

    def chmod(self, path: AnyStr, mode: int,
              follow_symlinks: bool = True) -> None:
        """Change the permissions of a file as encoded in integer mode.

        Args:
            path: (str) Path to the file.
            mode: (int) Permissions.
            follow_symlinks: If `False` and `path` points to a symlink,
                the link itself is affected instead of the linked object.
        """
        file_object = self.resolve(path, follow_symlinks, allow_fd=True,
                                   check_owner=True)
        if self.is_windows_fs:
            if mode & PERM_WRITE:
                file_object.st_mode = file_object.st_mode | 0o222
            else:
                file_object.st_mode = file_object.st_mode & 0o777555
        else:
            file_object.st_mode = ((file_object.st_mode & ~PERM_ALL) |
                                   (mode & PERM_ALL))
        file_object.st_ctime = now()

    def utime(self, path: AnyStr,
              times: Optional[Tuple[Union[int, float], Union[int, float]]] =
              None, *, ns: Optional[Tuple[int, int]] = None,
              follow_symlinks: bool = True) -> None:
        """Change the access and modified times of a file.

        Args:
            path: (str) Path to the file.
            times: 2-tuple of int or float numbers, of the form (atime, mtime)
                which is used to set the access and modified times in seconds.
                If None, both times are set to the current time.
            ns: 2-tuple of int numbers, of the form (atime, mtime)  which is
                used to set the access and modified times in nanoseconds.
                If `None`, both times are set to the current time.
            follow_symlinks: If `False` and entry_path points to a symlink,
                the link itself is queried instead of the linked object.

            Raises:
                TypeError: If anything other than the expected types is
                    specified in the passed `times` or `ns` tuple,
                    or if the tuple length is not equal to 2.
                ValueError: If both times and ns are specified.
        """
        self._handle_utime_arg_errors(ns, times)

        file_object = self.resolve(path, follow_symlinks, allow_fd=True)
        if times is not None:
            for file_time in times:
                if not isinstance(file_time, (int, float)):
                    raise TypeError('atime and mtime must be numbers')

            file_object.st_atime = times[0]
            file_object.st_mtime = times[1]
        elif ns is not None:
            for file_time in ns:
                if not isinstance(file_time, int):
                    raise TypeError('atime and mtime must be ints')

            file_object.st_atime_ns = ns[0]
            file_object.st_mtime_ns = ns[1]
        else:
            current_time = now()
            file_object.st_atime = current_time
            file_object.st_mtime = current_time

    @staticmethod
    def _handle_utime_arg_errors(
            ns: Optional[Tuple[int, int]],
            times: Optional[Tuple[Union[int, float], Union[int, float]]]):
        if times is not None and ns is not None:
            raise ValueError(
                "utime: you may specify either 'times' or 'ns' but not both")
        if times is not None and len(times) != 2:
            raise TypeError(
                "utime: 'times' must be either a tuple of two ints or None")
        if ns is not None and len(ns) != 2:
            raise TypeError("utime: 'ns' must be a tuple of two ints")

    def _add_open_file(
            self,
            file_obj: AnyFileWrapper) -> int:
        """Add file_obj to the list of open files on the filesystem.
        Used internally to manage open files.

        The position in the open_files array is the file descriptor number.

        Args:
            file_obj: File object to be added to open files list.

        Returns:
            File descriptor number for the file object.
        """
        if self._free_fd_heap:
            open_fd = heapq.heappop(self._free_fd_heap)
            self.open_files[open_fd] = [file_obj]
            return open_fd

        self.open_files.append([file_obj])
        return len(self.open_files) - 1

    def _close_open_file(self, file_des: int) -> None:
        """Remove file object with given descriptor from the list
        of open files.

        Sets the entry in open_files to None.

        Args:
            file_des: Descriptor of file object to be removed from
            open files list.
        """
        self.open_files[file_des] = None
        heapq.heappush(self._free_fd_heap, file_des)

    def get_open_file(self, file_des: int) -> AnyFileWrapper:
        """Return an open file.

        Args:
            file_des: File descriptor of the open file.

        Raises:
            OSError: an invalid file descriptor.
            TypeError: filedes is not an integer.

        Returns:
            Open file object.
        """
        if not is_int_type(file_des):
            raise TypeError('an integer is required')
        valid = file_des < len(self.open_files)
        if valid:
            file_list = self.open_files[file_des]
            if file_list is not None:
                return file_list[0]
        self.raise_os_error(errno.EBADF, str(file_des))

    def has_open_file(self, file_object: FakeFile) -> bool:
        """Return True if the given file object is in the list of open files.

        Args:
            file_object: The FakeFile object to be checked.

        Returns:
            `True` if the file is open.
        """
        return (file_object in [wrappers[0].get_object()
                                for wrappers in self.open_files if wrappers])

    def _normalize_path_sep(self, path: AnyStr) -> AnyStr:
        alt_sep = self._alternative_path_separator(path)
        if alt_sep is not None:
            return path.replace(alt_sep, self.get_path_separator(path))
        return path

    def normcase(self, path: AnyStr) -> AnyStr:
        """Replace all appearances of alternative path separator
        with path separator.

        Do nothing if no alternative separator is set.

        Args:
            path: The path to be normalized.

        Returns:
            The normalized path that will be used internally.
        """
        file_path = make_string_path(path)
        return self._normalize_path_sep(file_path)

    def normpath(self, path: AnyStr) -> AnyStr:
        """Mimic os.path.normpath using the specified path_separator.

        Mimics os.path.normpath using the path_separator that was specified
        for this FakeFilesystem. Normalizes the path, but unlike the method
        absnormpath, does not make it absolute.  Eliminates dot components
        (. and ..) and combines repeated path separators (//).  Initial ..
        components are left in place for relative paths.
        If the result is an empty path, '.' is returned instead.

        This also replaces alternative path separator with path separator.
        That is, it behaves like the real os.path.normpath on Windows if
        initialized with '\\' as path separator and  '/' as alternative
        separator.

        Args:
            path:  (str) The path to normalize.

        Returns:
            (str) A copy of path with empty components and dot components
            removed.
        """
        path_str = self.normcase(path)
        drive, path_str = self.splitdrive(path_str)
        sep = self.get_path_separator(path_str)
        is_absolute_path = path_str.startswith(sep)
        path_components: List[AnyStr] = path_str.split(sep)
        collapsed_path_components: List[AnyStr] = []
        dot = matching_string(path_str, '.')
        dotdot = matching_string(path_str, '..')
        for component in path_components:
            if (not component) or (component == dot):
                continue
            if component == dotdot:
                if collapsed_path_components and (
                        collapsed_path_components[-1] != dotdot):
                    # Remove an up-reference: directory/..
                    collapsed_path_components.pop()
                    continue
                elif is_absolute_path:
                    # Ignore leading .. components if starting from the
                    # root directory.
                    continue
            collapsed_path_components.append(component)
        collapsed_path = sep.join(collapsed_path_components)
        if is_absolute_path:
            collapsed_path = sep + collapsed_path
        return drive + collapsed_path or dot

    def _original_path(self, path: AnyStr) -> AnyStr:
        """Return a normalized case version of the given path for
        case-insensitive file systems. For case-sensitive file systems,
        return path unchanged.

        Args:
            path: the file path to be transformed

        Returns:
            A version of path matching the case of existing path elements.
        """

        def components_to_path():
            if len(path_components) > len(normalized_components):
                normalized_components.extend(
                    to_string(p) for p in path_components[len(
                        normalized_components):])
            sep = self.path_separator
            normalized_path = sep.join(normalized_components)
            if (self.starts_with_sep(path)
                    and not self.starts_with_sep(normalized_path)):
                normalized_path = sep + normalized_path
            if (len(normalized_path) == 2 and
                    self.starts_with_drive_letter(normalized_path)):
                normalized_path += sep
            return normalized_path

        if self.is_case_sensitive or not path:
            return path
        path = self.replace_windows_root(path)
        path_components = self._path_components(path)
        normalized_components = []
        current_dir = self.root
        for component in path_components:
            if not isinstance(current_dir, FakeDirectory):
                return components_to_path()
            dir_name, directory = self._directory_content(
                current_dir, to_string(component))
            if directory is None or (
                    isinstance(directory, FakeDirectory) and
                    directory._byte_contents is None and
                    directory.st_size == 0):
                return components_to_path()
            current_dir = cast(FakeDirectory, directory)
            normalized_components.append(dir_name)
        return components_to_path()

    def absnormpath(self, path: AnyStr) -> AnyStr:
        """Absolutize and minimalize the given path.

        Forces all relative paths to be absolute, and normalizes the path to
        eliminate dot and empty components.

        Args:
            path:  Path to normalize.

        Returns:
            The normalized path relative to the current working directory,
            or the root directory if path is empty.
        """
        path = self.normcase(path)
        cwd = matching_string(path, self.cwd)
        if not path:
            path = self.get_path_separator(path)
        if path == matching_string(path, '.'):
            path = cwd
        elif not self._starts_with_root_path(path):
            # Prefix relative paths with cwd, if cwd is not root.
            root_name = matching_string(path, self.root.name)
            empty = matching_string(path, '')
            path = self.get_path_separator(path).join(
                (cwd != root_name and cwd or empty, path))
        else:
            path = self.replace_windows_root(path)
        return self.normpath(path)

    def splitpath(self, path: AnyStr) -> Tuple[AnyStr, AnyStr]:
        """Mimic os.path.split using the specified path_separator.

        Mimics os.path.split using the path_separator that was specified
        for this FakeFilesystem.

        Args:
            path:  (str) The path to split.

        Returns:
            (str) A duple (pathname, basename) for which pathname does not
            end with a slash, and basename does not contain a slash.
        """
        path = make_string_path(path)
        sep = self.get_path_separator(path)
        alt_sep = self._alternative_path_separator(path)
        seps = sep if alt_sep is None else sep + alt_sep
        drive, path = self.splitdrive(path)
        i = len(path)
        while i and path[i-1] not in seps:
            i -= 1
        head, tail = path[:i], path[i:]  # now tail has no slashes
        # remove trailing slashes from head, unless it's all slashes
        head = head.rstrip(seps) or head
        return drive + head, tail

    def splitdrive(self, path: AnyStr) -> Tuple[AnyStr, AnyStr]:
        """Splits the path into the drive part and the rest of the path.

        Taken from Windows specific implementation in Python 3.5
        and slightly adapted.

        Args:
            path: the full path to be splitpath.

        Returns:
            A tuple of the drive part and the rest of the path, or of
            an empty string and the full path if drive letters are
            not supported or no drive is present.
        """
        path_str = make_string_path(path)
        if self.is_windows_fs:
            if len(path_str) >= 2:
                norm_str = self.normcase(path_str)
                sep = self.get_path_separator(path_str)
                # UNC path_str handling
                if (norm_str[0:2] == sep * 2) and (
                        norm_str[2:3] != sep):
                    # UNC path_str handling - splits off the mount point
                    # instead of the drive
                    sep_index = norm_str.find(sep, 2)
                    if sep_index == -1:
                        return path_str[:0], path_str
                    sep_index2 = norm_str.find(sep, sep_index + 1)
                    if sep_index2 == sep_index + 1:
                        return path_str[:0], path_str
                    if sep_index2 == -1:
                        sep_index2 = len(path_str)
                    return path_str[:sep_index2], path_str[sep_index2:]
                if path_str[1:2] == matching_string(path_str, ':'):
                    return path_str[:2], path_str[2:]
        return path_str[:0], path_str

    def _join_paths_with_drive_support(
            self, *all_paths: AnyStr) -> AnyStr:
        """Taken from Python 3.5 os.path.join() code in ntpath.py
        and slightly adapted"""
        base_path = all_paths[0]
        paths_to_add = all_paths[1:]
        sep = self.get_path_separator(base_path)
        seps = [sep, self._alternative_path_separator(base_path)]
        result_drive, result_path = self.splitdrive(base_path)
        for path in paths_to_add:
            drive_part, path_part = self.splitdrive(path)
            if path_part and path_part[:1] in seps:
                # Second path is absolute
                if drive_part or not result_drive:
                    result_drive = drive_part
                result_path = path_part
                continue
            elif drive_part and drive_part != result_drive:
                if (self.is_case_sensitive or
                        drive_part.lower() != result_drive.lower()):
                    # Different drives => ignore the first path entirely
                    result_drive = drive_part
                    result_path = path_part
                    continue
                # Same drive in different case
                result_drive = drive_part
            # Second path is relative to the first
            if result_path and result_path[-1:] not in seps:
                result_path = result_path + sep
            result_path = result_path + path_part
        # add separator between UNC and non-absolute path
        colon = matching_string(base_path, ':')
        if (result_path and result_path[:1] not in seps and
                result_drive and result_drive[-1:] != colon):
            return result_drive + sep + result_path
        return result_drive + result_path

    def joinpaths(self, *paths: AnyStr) -> AnyStr:
        """Mimic os.path.join using the specified path_separator.

        Args:
            *paths:  (str) Zero or more paths to join.

        Returns:
            (str) The paths joined by the path separator, starting with
            the last absolute path in paths.
        """
        file_paths = [os.fspath(path) for path in paths]
        if len(file_paths) == 1:
            return paths[0]
        if self.is_windows_fs:
            return self._join_paths_with_drive_support(*file_paths)
        joined_path_segments = []
        sep = self.get_path_separator(file_paths[0])
        for path_segment in file_paths:
            if self._starts_with_root_path(path_segment):
                # An absolute path
                joined_path_segments = [path_segment]
            else:
                if (joined_path_segments and
                        not joined_path_segments[-1].endswith(sep)):
                    joined_path_segments.append(sep)
                if path_segment:
                    joined_path_segments.append(path_segment)
        return matching_string(file_paths[0], '').join(joined_path_segments)

    @overload
    def _path_components(self, path: str) -> List[str]: ...

    @overload
    def _path_components(self, path: bytes) -> List[bytes]: ...

    def _path_components(self, path: AnyStr) -> List[AnyStr]:
        """Breaks the path into a list of component names.

        Does not include the root directory as a component, as all paths
        are considered relative to the root directory for the FakeFilesystem.
        Callers should basically follow this pattern:

        .. code:: python

            file_path = self.absnormpath(file_path)
            path_components = self._path_components(file_path)
            current_dir = self.root
            for component in path_components:
                if component not in current_dir.entries:
                    raise OSError
                _do_stuff_with_component(current_dir, component)
                current_dir = current_dir.get_entry(component)

        Args:
            path:  Path to tokenize.

        Returns:
            The list of names split from path.
        """
        if not path or path == self.get_path_separator(path):
            return []
        drive, path = self.splitdrive(path)
        path_components = path.split(self.get_path_separator(path))
        assert drive or path_components
        if not path_components[0]:
            if len(path_components) > 1 and not path_components[1]:
                path_components = []
            else:
                # This is an absolute path.
                path_components = path_components[1:]
        if drive:
            path_components.insert(0, drive)
        return path_components

    def starts_with_drive_letter(self, file_path: AnyStr) -> bool:
        """Return True if file_path starts with a drive letter.

        Args:
            file_path: the full path to be examined.

        Returns:
            `True` if drive letter support is enabled in the filesystem and
            the path starts with a drive letter.
        """
        colon = matching_string(file_path, ':')
        if (len(file_path) >= 2 and
                file_path[0:1].isalpha and file_path[1:2] == colon):
            if self.is_windows_fs:
                return True
            if os.name == 'nt':
                # special case if we are emulating Posix under Windows
                # check if the path exists because it has been mapped in
                # this is not foolproof, but handles most cases
                try:
                    self.get_object_from_normpath(file_path)
                    return True
                except OSError:
                    return False
        return False

    def _starts_with_root_path(self, file_path: AnyStr) -> bool:
        root_name = matching_string(file_path, self.root.name)
        file_path = self._normalize_path_sep(file_path)
        return (file_path.startswith(root_name) or
                not self.is_case_sensitive and file_path.lower().startswith(
                    root_name.lower()) or
                self.starts_with_drive_letter(file_path))

    def replace_windows_root(self, path: AnyStr) -> AnyStr:
        """In windows, if a path starts with a single separator,
        it points to the root dir of the current mount point, usually a
        drive - replace it with that mount point path to get the real path.
        """
        if path and self.is_windows_fs and self.root_dir:
            sep = self.get_path_separator(path)
            # ignore UNC paths
            if path[0:1] == sep and (len(path) == 1 or path[1:2] != sep):
                # check if we already have a mount point for that path
                for root_path in self.mount_points:
                    root_path = matching_string(path, root_path)
                    if path.startswith(root_path):
                        return path
                # must be a pointer to the current drive - replace it
                mount_point = matching_string(path, self.root_dir_name)
                path = mount_point + path[1:]
        return path

    def _is_root_path(self, file_path: AnyStr) -> bool:
        root_name = matching_string(file_path, self.root.name)
        return file_path == root_name or self.is_mount_point(file_path)

    def is_mount_point(self, file_path: AnyStr) -> bool:
        """Return `True` if `file_path` points to a mount point."""
        for mount_point in self.mount_points:
            mount_point = matching_string(file_path, mount_point)
            if (file_path == mount_point or not self.is_case_sensitive and
                    file_path.lower() == mount_point.lower()):
                return True
            if (self.is_windows_fs and len(file_path) == 3 and
                    len(mount_point) == 2 and
                    self.starts_with_drive_letter(file_path) and
                    file_path[:2].lower() == mount_point.lower()):
                return True
        return False

    def ends_with_path_separator(self, path: Union[int, AnyPath]) -> bool:
        """Return True if ``file_path`` ends with a valid path separator."""
        if isinstance(path, int):
            return False
        file_path = make_string_path(path)
        if not file_path:
            return False
        sep = self.get_path_separator(file_path)
        altsep = self._alternative_path_separator(file_path)
        return (file_path not in (sep, altsep) and
                (file_path.endswith(sep) or
                 altsep is not None and file_path.endswith(altsep)))

    def is_filepath_ending_with_separator(self, path: AnyStr) -> bool:
        if not self.ends_with_path_separator(path):
            return False
        return self.isfile(self._path_without_trailing_separators(path))

    def _directory_content(self, directory: FakeDirectory,
                           component: str) -> Tuple[Optional[str],
                                                    Optional[AnyFile]]:
        if not isinstance(directory, FakeDirectory):
            return None, None
        if component in directory.entries:
            return component, directory.entries[component]
        if not self.is_case_sensitive:
            matching_content = [(subdir, directory.entries[subdir]) for
                                subdir in directory.entries
                                if subdir.lower() == component.lower()]
            if matching_content:
                return matching_content[0]

        return None, None

    def exists(self, file_path: AnyPath, check_link: bool = False) -> bool:
        """Return true if a path points to an existing file system object.

        Args:
            file_path:  The path to examine.
            check_link: If True, links are not followed

        Returns:
            (bool) True if the corresponding object exists.

        Raises:
            TypeError: if file_path is None.
        """
        if check_link and self.islink(file_path):
            return True
        path = to_string(make_string_path(file_path))
        if path is None:
            raise TypeError
        if not path:
            return False
        if path == self.dev_null.name:
            return not self.is_windows_fs or sys.version_info >= (3, 8)
        try:
            if self.is_filepath_ending_with_separator(path):
                return False
            path = self.resolve_path(path)
        except OSError:
            return False
        if self._is_root_path(path):
            return True

        path_components: List[str] = self._path_components(path)
        current_dir = self.root
        for component in path_components:
            directory = self._directory_content(
                current_dir, to_string(component))[1]
            if directory is None:
                return False
            current_dir = cast(FakeDirectory, directory)
        return True

    def resolve_path(self,
                     file_path: AnyStr, allow_fd: bool = False) -> AnyStr:
        """Follow a path, resolving symlinks.

        ResolvePath traverses the filesystem along the specified file path,
        resolving file names and symbolic links until all elements of the path
        are exhausted, or we reach a file which does not exist.
        If all the elements are not consumed, they just get appended to the
        path resolved so far.
        This gives us the path which is as resolved as it can be, even if the
        file does not exist.

        This behavior mimics Unix semantics, and is best shown by example.
        Given a file system that looks like this:

              /a/b/
              /a/b/c -> /a/b2          c is a symlink to /a/b2
              /a/b2/x
              /a/c   -> ../d
              /a/x   -> y

         Then:
              /a/b/x      =>  /a/b/x
              /a/c        =>  /a/d
              /a/x        =>  /a/y
              /a/b/c/d/e  =>  /a/b2/d/e

        Args:
            file_path: The path to examine.
            allow_fd: If `True`, `file_path` may be open file descriptor.

        Returns:
            The resolved_path (str or byte).

        Raises:
            TypeError: if `file_path` is `None`.
            OSError: if `file_path` is '' or a part of the path doesn't exist.
        """

        if allow_fd and isinstance(file_path, int):
            return self.get_open_file(file_path).get_object().path
        path = make_string_path(file_path)
        if path is None:
            # file.open(None) raises TypeError, so mimic that.
            raise TypeError('Expected file system path string, received None')
        if not path or not self._valid_relative_path(path):
            # file.open('') raises OSError, so mimic that, and validate that
            # all parts of a relative path exist.
            self.raise_os_error(errno.ENOENT, path)
        path = self.absnormpath(self._original_path(path))
        path = self.replace_windows_root(path)
        if self._is_root_path(path):
            return path
        if path == matching_string(path, self.dev_null.name):
            return path
        path_components = self._path_components(path)
        resolved_components = self._resolve_components(path_components)
        path = self._components_to_path(resolved_components)
        # after resolving links, we have to check again for Windows root
        return self.replace_windows_root(path)

    def _components_to_path(self, component_folders):
        sep = (self.get_path_separator(component_folders[0])
               if component_folders else self.path_separator)
        path = sep.join(component_folders)
        if not self._starts_with_root_path(path):
            path = sep + path
        return path

    def _resolve_components(self, components: List[AnyStr]) -> List[str]:
        current_dir = self.root
        link_depth = 0
        path_components = [to_string(comp) for comp in components]
        resolved_components: List[str] = []
        while path_components:
            component = path_components.pop(0)
            resolved_components.append(component)
            directory = self._directory_content(current_dir, component)[1]
            if directory is None:
                # The component of the path at this point does not actually
                # exist in the folder.  We can't resolve the path any more.
                # It is legal to link to a file that does not yet exist, so
                # rather than raise an error, we just append the remaining
                # components to what return path we have built so far and
                # return that.
                resolved_components.extend(path_components)
                break
            # Resolve any possible symlinks in the current path component.
            elif S_ISLNK(directory.st_mode):
                # This link_depth check is not really meant to be an accurate
                # check. It is just a quick hack to prevent us from looping
                # forever on cycles.
                if link_depth > _MAX_LINK_DEPTH:
                    self.raise_os_error(errno.ELOOP,
                                        self._components_to_path(
                                            resolved_components))
                link_path = self._follow_link(resolved_components, directory)

                # Following the link might result in the complete replacement
                # of the current_dir, so we evaluate the entire resulting path.
                target_components = self._path_components(link_path)
                path_components = target_components + path_components
                resolved_components = []
                current_dir = self.root
                link_depth += 1
            else:
                current_dir = cast(FakeDirectory, directory)
        return resolved_components

    def _valid_relative_path(self, file_path: AnyStr) -> bool:
        if self.is_windows_fs:
            return True
        slash_dotdot = matching_string(
            file_path, self.path_separator + '..')
        while file_path and slash_dotdot in file_path:
            file_path = file_path[:file_path.rfind(slash_dotdot)]
            if not self.exists(self.absnormpath(file_path)):
                return False
        return True

    def _follow_link(self, link_path_components: List[str],
                     link: AnyFile) -> str:
        """Follow a link w.r.t. a path resolved so far.

        The component is either a real file, which is a no-op, or a
        symlink. In the case of a symlink, we have to modify the path
        as built up so far
          /a/b => ../c  should yield /a/../c (which will normalize to /a/c)
          /a/b => x     should yield /a/x
          /a/b => /x/y/z should yield /x/y/z
        The modified path may land us in a new spot which is itself a
        link, so we may repeat the process.

        Args:
            link_path_components: The resolved path built up to the link
                so far.
            link: The link object itself.

        Returns:
            (string) The updated path resolved after following the link.

        Raises:
            OSError: if there are too many levels of symbolic link
        """
        link_path = link.contents
        if link_path is not None:
            # ignore UNC prefix for local files
            if self.is_windows_fs and link_path.startswith('\\\\?\\'):
                link_path = link_path[4:]
            sep = self.get_path_separator(link_path)
            # For links to absolute paths, we want to throw out everything
            # in the path built so far and replace with the link. For relative
            # links, we have to append the link to what we have so far,
            if not self._starts_with_root_path(link_path):
                # Relative path. Append remainder of path to what we have
                # processed so far, excluding the name of the link itself.
                # /a/b => ../c  should yield /a/../c
                # (which will normalize to /c)
                # /a/b => d should yield a/d
                components = link_path_components[:-1]
                components.append(link_path)
                link_path = sep.join(components)
            # Don't call self.NormalizePath(), as we don't want to prepend
            # self.cwd.
            return self.normpath(link_path)
        raise ValueError("Invalid link")

    def get_object_from_normpath(self,
                                 file_path: AnyPath,
                                 check_read_perm: bool = True,
                                 check_owner: bool = False) -> AnyFile:
        """Search for the specified filesystem object within the fake
        filesystem.

        Args:
            file_path: Specifies target FakeFile object to retrieve, with a
                path that has already been normalized/resolved.
            check_read_perm: If True, raises OSError if a parent directory
                does not have read permission
            check_owner: If True, and check_read_perm is also True,
                only checks read permission if the current user id is
                different from the file object user id

        Returns:
            The FakeFile object corresponding to file_path.

        Raises:
            OSError: if the object is not found.
        """
        path = make_string_path(file_path)
        if path == matching_string(path, self.root.name):
            return self.root
        if path == matching_string(path, self.dev_null.name):
            return self.dev_null

        path = self._original_path(path)
        path_components = self._path_components(path)
        target = self.root
        try:
            for component in path_components:
                if S_ISLNK(target.st_mode):
                    if target.contents:
                        target = cast(FakeDirectory,
                                      self.resolve(target.contents))
                if not S_ISDIR(target.st_mode):
                    if not self.is_windows_fs:
                        self.raise_os_error(errno.ENOTDIR, path)
                    self.raise_os_error(errno.ENOENT, path)
                target = target.get_entry(component)  # type: ignore
                if (not is_root() and check_read_perm and target and
                        not self._can_read(target, check_owner)):
                    self.raise_os_error(errno.EACCES, target.path)
        except KeyError:
            self.raise_os_error(errno.ENOENT, path)
        return target

    @staticmethod
    def _can_read(target, owner_can_read):
        if target.st_uid == USER_ID:
            if owner_can_read or target.st_mode & 0o400:
                return True
        if target.st_gid == GROUP_ID:
            if target.st_mode & 0o040:
                return True
        return target.st_mode & 0o004

    def get_object(self, file_path: AnyPath,
                   check_read_perm: bool = True) -> FakeFile:
        """Search for the specified filesystem object within the fake
        filesystem.

        Args:
            file_path: Specifies the target FakeFile object to retrieve.
            check_read_perm: If True, raises OSError if a parent directory
                does not have read permission

        Returns:
            The FakeFile object corresponding to `file_path`.

        Raises:
            OSError: if the object is not found.
        """
        path = make_string_path(file_path)
        path = self.absnormpath(self._original_path(path))
        return self.get_object_from_normpath(path, check_read_perm)

    def resolve(self, file_path: AnyStr,
                follow_symlinks: bool = True,
                allow_fd: bool = False,
                check_read_perm: bool = True,
                check_owner: bool = False) -> FakeFile:
        """Search for the specified filesystem object, resolving all links.

        Args:
            file_path: Specifies the target FakeFile object to retrieve.
            follow_symlinks: If `False`, the link itself is resolved,
                otherwise the object linked to.
            allow_fd: If `True`, `file_path` may be an open file descriptor
            check_read_perm: If True, raises OSError if a parent directory
                does not have read permission
            check_owner: If True, and check_read_perm is also True,
                only checks read permission if the current user id is
                different from the file object user id

        Returns:
          The FakeFile object corresponding to `file_path`.

        Raises:
            OSError: if the object is not found.
        """
        if isinstance(file_path, int):
            if allow_fd:
                return self.get_open_file(file_path).get_object()
            raise TypeError('path should be string, bytes or '
                            'os.PathLike, not int')

        if follow_symlinks:
            return self.get_object_from_normpath(self.resolve_path(
                file_path, check_read_perm), check_read_perm, check_owner)
        return self.lresolve(file_path)

    def lresolve(self, path: AnyPath) -> FakeFile:
        """Search for the specified object, resolving only parent links.

        This is analogous to the stat/lstat difference.  This resolves links
        *to* the object but not of the final object itself.

        Args:
            path: Specifies target FakeFile object to retrieve.

        Returns:
            The FakeFile object corresponding to path.

        Raises:
            OSError: if the object is not found.
        """
        path_str = make_string_path(path)
        if not path_str:
            raise OSError(errno.ENOENT, path_str)
        if path_str == matching_string(path_str, self.root.name):
            # The root directory will never be a link
            return self.root

        # remove trailing separator
        path_str = self._path_without_trailing_separators(path_str)
        if path_str == matching_string(path_str, '.'):
            path_str = matching_string(path_str, self.cwd)
        path_str = self._original_path(path_str)

        parent_directory, child_name = self.splitpath(path_str)
        if not parent_directory:
            parent_directory = matching_string(path_str, self.cwd)
        try:
            parent_obj = self.resolve(parent_directory)
            assert parent_obj
            if not isinstance(parent_obj, FakeDirectory):
                if not self.is_windows_fs and isinstance(parent_obj, FakeFile):
                    self.raise_os_error(errno.ENOTDIR, path_str)
                self.raise_os_error(errno.ENOENT, path_str)
            if not parent_obj.st_mode & PERM_READ:
                self.raise_os_error(errno.EACCES, parent_directory)
            return (parent_obj.get_entry(to_string(child_name)) if child_name
                    else parent_obj)
        except KeyError:
            pass
        raise OSError(errno.ENOENT, path_str)

    def add_object(self, file_path: AnyStr, file_object: AnyFile) -> None:
        """Add a fake file or directory into the filesystem at file_path.

        Args:
            file_path: The path to the file to be added relative to self.
            file_object: File or directory to add.

        Raises:
            OSError: if file_path does not correspond to a
                directory.
        """
        if not file_path:
            target_directory = self.root_dir
        else:
            target_directory = cast(FakeDirectory, self.resolve(file_path))
            if not S_ISDIR(target_directory.st_mode):
                error = errno.ENOENT if self.is_windows_fs else errno.ENOTDIR
                self.raise_os_error(error, file_path)
        target_directory.add_entry(file_object)

    def rename(self, old_file_path: AnyPath,
               new_file_path: AnyPath,
               force_replace: bool = False) -> None:
        """Renames a FakeFile object at old_file_path to new_file_path,
        preserving all properties.

        Args:
            old_file_path: Path to filesystem object to rename.
            new_file_path: Path to where the filesystem object will live
                after this call.
            force_replace: If set and destination is an existing file, it
                will be replaced even under Windows if the user has
                permissions, otherwise replacement happens under Unix only.

        Raises:
            OSError: if old_file_path does not exist.
            OSError: if new_file_path is an existing directory
                (Windows, or Posix if old_file_path points to a regular file)
            OSError: if old_file_path is a directory and new_file_path a file
            OSError: if new_file_path is an existing file and force_replace
                not set (Windows only).
            OSError: if new_file_path is an existing file and could not be
                removed (Posix, or Windows with force_replace set).
            OSError: if dirname(new_file_path) does not exist.
            OSError: if the file would be moved to another filesystem
                (e.g. mount point).
        """
        old_path = make_string_path(old_file_path)
        new_path = make_string_path(new_file_path)
        ends_with_sep = self.ends_with_path_separator(old_path)
        old_path = self.absnormpath(old_path)
        new_path = self.absnormpath(new_path)
        if not self.exists(old_path, check_link=True):
            self.raise_os_error(errno.ENOENT, old_path, 2)
        if ends_with_sep:
            self._handle_broken_link_with_trailing_sep(old_path)

        old_object = self.lresolve(old_path)
        if not self.is_windows_fs:
            self._handle_posix_dir_link_errors(
                new_path, old_path, ends_with_sep)

        if self.exists(new_path, check_link=True):
            renamed_path = self._rename_to_existing_path(
                force_replace, new_path, old_path,
                old_object, ends_with_sep)

            if renamed_path is None:
                return
            else:
                new_path = renamed_path

        old_dir, old_name = self.splitpath(old_path)
        new_dir, new_name = self.splitpath(new_path)
        if not self.exists(new_dir):
            self.raise_os_error(errno.ENOENT, new_dir)
        old_dir_object = self.resolve(old_dir)
        new_dir_object = self.resolve(new_dir)
        if old_dir_object.st_dev != new_dir_object.st_dev:
            self.raise_os_error(errno.EXDEV, old_path)
        if not S_ISDIR(new_dir_object.st_mode):
            self.raise_os_error(
                errno.EACCES if self.is_windows_fs else errno.ENOTDIR,
                new_path)
        if new_dir_object.has_parent_object(old_object):
            self.raise_os_error(errno.EINVAL, new_path)

        self._do_rename(old_dir_object, old_name, new_dir_object, new_name)

    def _do_rename(self, old_dir_object, old_name, new_dir_object, new_name):
        object_to_rename = old_dir_object.get_entry(old_name)
        old_dir_object.remove_entry(old_name, recursive=False)
        object_to_rename.name = new_name
        new_name = new_dir_object._normalized_entryname(new_name)
        old_entry = (new_dir_object.get_entry(new_name)
                     if new_name in new_dir_object.entries else None)
        try:
            if old_entry:
                # in case of overwriting remove the old entry first
                new_dir_object.remove_entry(new_name)
            new_dir_object.add_entry(object_to_rename)
        except OSError:
            # adding failed, roll back the changes before re-raising
            if old_entry and new_name not in new_dir_object.entries:
                new_dir_object.add_entry(old_entry)
            object_to_rename.name = old_name
            old_dir_object.add_entry(object_to_rename)
            raise

    def _handle_broken_link_with_trailing_sep(self, path: AnyStr) -> None:
        # note that the check for trailing sep has to be done earlier
        if self.islink(path):
            if not self.exists(path):
                error = (errno.ENOENT if self.is_macos else
                         errno.EINVAL if self.is_windows_fs else errno.ENOTDIR)
                self.raise_os_error(error, path)

    def _handle_posix_dir_link_errors(self, new_file_path: AnyStr,
                                      old_file_path: AnyStr,
                                      ends_with_sep: bool) -> None:
        if (self.isdir(old_file_path, follow_symlinks=False) and
                self.islink(new_file_path)):
            self.raise_os_error(errno.ENOTDIR, new_file_path)
        if (self.isdir(new_file_path, follow_symlinks=False) and
                self.islink(old_file_path)):
            if ends_with_sep and self.is_macos:
                return
            error = errno.ENOTDIR if ends_with_sep else errno.EISDIR
            self.raise_os_error(error, new_file_path)
        if (ends_with_sep and self.islink(old_file_path) and
                old_file_path == new_file_path and not self.is_windows_fs):
            self.raise_os_error(errno.ENOTDIR, new_file_path)

    def _rename_to_existing_path(self, force_replace: bool,
                                 new_file_path: AnyStr,
                                 old_file_path: AnyStr,
                                 old_object: FakeFile,
                                 ends_with_sep: bool) -> Optional[AnyStr]:
        new_object = self.get_object(new_file_path)
        if old_file_path == new_file_path:
            if not S_ISLNK(new_object.st_mode) and ends_with_sep:
                error = errno.EINVAL if self.is_windows_fs else errno.ENOTDIR
                self.raise_os_error(error, old_file_path)
            return None  # Nothing to do here

        if old_object == new_object:
            return self._rename_same_object(new_file_path, old_file_path)
        if S_ISDIR(new_object.st_mode) or S_ISLNK(new_object.st_mode):
            self._handle_rename_error_for_dir_or_link(
                force_replace, new_file_path,
                new_object, old_object, ends_with_sep)
        elif S_ISDIR(old_object.st_mode):
            error = errno.EEXIST if self.is_windows_fs else errno.ENOTDIR
            self.raise_os_error(error, new_file_path)
        elif self.is_windows_fs and not force_replace:
            self.raise_os_error(errno.EEXIST, new_file_path)
        else:
            self.remove_object(new_file_path)
        return new_file_path

    def _handle_rename_error_for_dir_or_link(self, force_replace: bool,
                                             new_file_path: AnyStr,
                                             new_object: FakeFile,
                                             old_object: FakeFile,
                                             ends_with_sep: bool) -> None:
        if self.is_windows_fs:
            if force_replace:
                self.raise_os_error(errno.EACCES, new_file_path)
            else:
                self.raise_os_error(errno.EEXIST, new_file_path)
        if not S_ISLNK(new_object.st_mode):
            if new_object.entries:
                if (not S_ISLNK(old_object.st_mode) or
                        not ends_with_sep or not self.is_macos):
                    self.raise_os_error(errno.ENOTEMPTY, new_file_path)
            if S_ISREG(old_object.st_mode):
                self.raise_os_error(errno.EISDIR, new_file_path)

    def _rename_same_object(self, new_file_path: AnyStr,
                            old_file_path: AnyStr) -> Optional[AnyStr]:
        do_rename = old_file_path.lower() == new_file_path.lower()
        if not do_rename:
            try:
                real_old_path = self.resolve_path(old_file_path)
                original_old_path = self._original_path(real_old_path)
                real_new_path = self.resolve_path(new_file_path)
                if (real_new_path == original_old_path and
                        (new_file_path == real_old_path) ==
                        (new_file_path.lower() ==
                         real_old_path.lower())):
                    real_object = self.resolve(old_file_path,
                                               follow_symlinks=False)
                    do_rename = (os.path.basename(old_file_path) ==
                                 real_object.name or not self.is_macos)
                else:
                    do_rename = (real_new_path.lower() ==
                                 real_old_path.lower())
                if do_rename:
                    # only case is changed in case-insensitive file
                    # system - do the rename
                    parent, file_name = self.splitpath(new_file_path)
                    new_file_path = self.joinpaths(
                        self._original_path(parent), file_name)
            except OSError:
                # ResolvePath may fail due to symlink loop issues or
                # similar - in this case just assume the paths
                # to be different
                pass
        if not do_rename:
            # hard links to the same file - nothing to do
            return None
        return new_file_path

    def remove_object(self, file_path: AnyStr) -> None:
        """Remove an existing file or directory.

        Args:
            file_path: The path to the file relative to self.

        Raises:
            OSError: if file_path does not correspond to an existing file, or
                if part of the path refers to something other than a directory.
            OSError: if the directory is in use (eg, if it is '/').
        """
        file_path = self.absnormpath(self._original_path(file_path))
        if self._is_root_path(file_path):
            self.raise_os_error(errno.EBUSY, file_path)
        try:
            dirname, basename = self.splitpath(file_path)
            target_directory = self.resolve(dirname, check_read_perm=False)
            target_directory.remove_entry(basename)
        except KeyError:
            self.raise_os_error(errno.ENOENT, file_path)
        except AttributeError:
            self.raise_os_error(errno.ENOTDIR, file_path)

    def make_string_path(self, path: AnyPath) -> AnyStr:
        path_str = make_string_path(path)
        os_sep = matching_string(path_str, os.sep)
        fake_sep = self.get_path_separator(path_str)
        return path_str.replace(os_sep, fake_sep)  # type: ignore[return-value]

    def create_dir(self, directory_path: AnyPath,
                   perm_bits: int = PERM_DEF) -> FakeDirectory:
        """Create `directory_path`, and all the parent directories.

        Helper method to set up your test faster.

        Args:
            directory_path: The full directory path to create.
            perm_bits: The permission bits as set by `chmod`.

        Returns:
            The newly created FakeDirectory object.

        Raises:
            OSError: if the directory already exists.
        """
        dir_path = self.make_string_path(directory_path)
        dir_path = self.absnormpath(dir_path)
        self._auto_mount_drive_if_needed(dir_path)
        if (self.exists(dir_path, check_link=True) and
                dir_path not in self.mount_points):
            self.raise_os_error(errno.EEXIST, dir_path)
        path_components = self._path_components(dir_path)
        current_dir = self.root

        new_dirs = []
        for component in [to_string(p) for p in path_components]:
            directory = self._directory_content(
                current_dir, to_string(component))[1]
            if not directory:
                new_dir = FakeDirectory(component, filesystem=self)
                new_dirs.append(new_dir)
                if self.is_windows_fs and current_dir == self.root:
                    current_dir = self.root_dir
                current_dir.add_entry(new_dir)
                current_dir = new_dir
            else:
                if S_ISLNK(directory.st_mode):
                    assert directory.contents
                    directory = self.resolve(directory.contents)
                    assert directory
                current_dir = cast(FakeDirectory, directory)
                if directory.st_mode & S_IFDIR != S_IFDIR:
                    self.raise_os_error(errno.ENOTDIR, current_dir.path)

        # set the permission after creating the directories
        # to allow directory creation inside a read-only directory
        for new_dir in new_dirs:
            new_dir.st_mode = S_IFDIR | perm_bits

        return current_dir

    def create_file(self, file_path: AnyPath,
                    st_mode: int = S_IFREG | PERM_DEF_FILE,
                    contents: AnyString = '',
                    st_size: Optional[int] = None,
                    create_missing_dirs: bool = True,
                    apply_umask: bool = False,
                    encoding: Optional[str] = None,
                    errors: Optional[str] = None,
                    side_effect: Optional[Callable] = None) -> FakeFile:
        """Create `file_path`, including all the parent directories along
        the way.

        This helper method can be used to set up tests more easily.

        Args:
            file_path: The path to the file to create.
            st_mode: The stat constant representing the file type.
            contents: the contents of the file. If not given and st_size is
                None, an empty file is assumed.
            st_size: file size; only valid if contents not given. If given,
                the file is considered to be in "large file mode" and trying
                to read from or write to the file will result in an exception.
            create_missing_dirs: If `True`, auto create missing directories.
            apply_umask: `True` if the current umask must be applied
                on `st_mode`.
            encoding: If `contents` is a unicode string, the encoding used
                for serialization.
            errors: The error mode used for encoding/decoding errors.
            side_effect: function handle that is executed when file is written,
                must accept the file object as an argument.

        Returns:
            The newly created FakeFile object.

        Raises:
            OSError: if the file already exists.
            OSError: if the containing directory is required and missing.
        """
        return self.create_file_internally(
            file_path, st_mode, contents, st_size, create_missing_dirs,
            apply_umask, encoding, errors, side_effect=side_effect)

    def add_real_file(self, source_path: AnyPath,
                      read_only: bool = True,
                      target_path: Optional[AnyPath] = None) -> FakeFile:
        """Create `file_path`, including all the parent directories along the
        way, for an existing real file. The contents of the real file are read
        only on demand.

        Args:
            source_path: Path to an existing file in the real file system
            read_only: If `True` (the default), writing to the fake file
                raises an exception.  Otherwise, writing to the file changes
                the fake file only.
            target_path: If given, the path of the target direction,
                otherwise it is equal to `source_path`.

        Returns:
            the newly created FakeFile object.

        Raises:
            OSError: if the file does not exist in the real file system.
            OSError: if the file already exists in the fake file system.

        .. note:: On most systems, accessing the fake file's contents may
            update both the real and fake files' `atime` (access time).
            In this particular case, `add_real_file()` violates the rule
            that `pyfakefs` must not modify the real file system.
        """
        target_path = target_path or source_path
        source_path_str = make_string_path(source_path)
        real_stat = os.stat(source_path_str)
        fake_file = self.create_file_internally(target_path,
                                                read_from_real_fs=True)

        # for read-only mode, remove the write/executable permission bits
        fake_file.stat_result.set_from_stat_result(real_stat)
        if read_only:
            fake_file.st_mode &= 0o777444
        fake_file.file_path = source_path_str
        self.change_disk_usage(fake_file.size, fake_file.name,
                               fake_file.st_dev)
        return fake_file

    def add_real_symlink(self, source_path: AnyPath,
                         target_path: Optional[AnyPath] = None) -> FakeFile:
        """Create a symlink at source_path (or target_path, if given).  It will
        point to the same path as the symlink on the real filesystem.  Relative
        symlinks will point relative to their new location.  Absolute symlinks
        will point to the same, absolute path as on the real filesystem.

        Args:
            source_path: The path to the existing symlink.
            target_path: If given, the name of the symlink in the fake
                filesystem, otherwise, the same as `source_path`.

        Returns:
            the newly created FakeFile object.

        Raises:
            OSError: if the directory does not exist in the real file system.
            OSError: if the symlink could not be created
                (see :py:meth:`create_file`).
            OSError: if the directory already exists in the fake file system.
        """
        source_path_str = make_string_path(source_path)  # TODO: add test
        source_path_str = self._path_without_trailing_separators(
            source_path_str)
        if (not os.path.exists(source_path_str) and
                not os.path.islink(source_path_str)):
            self.raise_os_error(errno.ENOENT, source_path_str)

        target = os.readlink(source_path_str)

        if target_path:
            return self.create_symlink(target_path, target)
        else:
            return self.create_symlink(source_path_str, target)

    def add_real_directory(
            self, source_path: AnyPath,
            read_only: bool = True,
            lazy_read: bool = True,
            target_path: Optional[AnyPath] = None) -> FakeDirectory:
        """Create a fake directory corresponding to the real directory at the
        specified path.  Add entries in the fake directory corresponding to
        the entries in the real directory.  Symlinks are supported.

        Args:
            source_path: The path to the existing directory.
            read_only: If set, all files under the directory are treated as
                read-only, e.g. a write access raises an exception;
                otherwise, writing to the files changes the fake files only
                as usually.
            lazy_read: If set (default), directory contents are only read when
                accessed, and only until the needed subdirectory level.

                .. note:: This means that the file system size is only updated
                  at the time the directory contents are read; set this to
                  `False` only if you are dependent on accurate file system
                  size in your test
            target_path: If given, the target directory, otherwise,
                the target directory is the same as `source_path`.

        Returns:
            the newly created FakeDirectory object.

        Raises:
            OSError: if the directory does not exist in the real file system.
            OSError: if the directory already exists in the fake file system.
        """
        source_path_str = make_string_path(source_path)  # TODO: add test
        source_path_str = self._path_without_trailing_separators(
            source_path_str)
        if not os.path.exists(source_path_str):
            self.raise_os_error(errno.ENOENT, source_path_str)
        target_path_str = make_string_path(target_path or source_path_str)
        self._auto_mount_drive_if_needed(target_path_str)
        new_dir: FakeDirectory
        if lazy_read:
            parent_path = os.path.split(target_path_str)[0]
            if self.exists(parent_path):
                parent_dir = self.get_object(parent_path)
            else:
                parent_dir = self.create_dir(parent_path)
            new_dir = FakeDirectoryFromRealDirectory(
                source_path_str, self, read_only, target_path_str)
            parent_dir.add_entry(new_dir)
        else:
            new_dir = self.create_dir(target_path_str)
            for base, _, files in os.walk(source_path_str):
                new_base = os.path.join(new_dir.path,  # type: ignore[arg-type]
                                        os.path.relpath(base, source_path_str))
                for fileEntry in os.listdir(base):
                    abs_fileEntry = os.path.join(base, fileEntry)

                    if not os.path.islink(abs_fileEntry):
                        continue

                    self.add_real_symlink(
                        abs_fileEntry, os.path.join(new_base, fileEntry))
                for fileEntry in files:
                    path = os.path.join(base, fileEntry)
                    if os.path.islink(path):
                        continue
                    self.add_real_file(path,
                                       read_only,
                                       os.path.join(new_base, fileEntry))
        return new_dir

    def add_real_paths(self, path_list: List[AnyStr],
                       read_only: bool = True,
                       lazy_dir_read: bool = True) -> None:
        """This convenience method adds multiple files and/or directories from
        the real file system to the fake file system. See `add_real_file()` and
        `add_real_directory()`.

        Args:
            path_list: List of file and directory paths in the real file
                system.
            read_only: If set, all files and files under under the directories
                are treated as read-only, e.g. a write access raises an
                exception; otherwise, writing to the files changes the fake
                files only as usually.
            lazy_dir_read: Uses lazy reading of directory contents if set
                (see `add_real_directory`)

        Raises:
            OSError: if any of the files and directories in the list
                does not exist in the real file system.
            OSError: if any of the files and directories in the list
                already exists in the fake file system.
        """
        for path in path_list:
            if os.path.isdir(path):
                self.add_real_directory(path, read_only, lazy_dir_read)
            else:
                self.add_real_file(path, read_only)

    def create_file_internally(
            self, file_path: AnyPath,
            st_mode: int = S_IFREG | PERM_DEF_FILE,
            contents: AnyString = '',
            st_size: Optional[int] = None,
            create_missing_dirs: bool = True,
            apply_umask: bool = False,
            encoding: Optional[str] = None,
            errors: Optional[str] = None,
            read_from_real_fs: bool = False,
            side_effect: Optional[Callable] = None) -> FakeFile:
        """Internal fake file creator that supports both normal fake files
        and fake files based on real files.

        Args:
            file_path: path to the file to create.
            st_mode: the stat.S_IF constant representing the file type.
            contents: the contents of the file. If not given and st_size is
                None, an empty file is assumed.
            st_size: file size; only valid if contents not given. If given,
                the file is considered to be in "large file mode" and trying
                to read from or write to the file will result in an exception.
            create_missing_dirs: if True, auto create missing directories.
            apply_umask: whether or not the current umask must be applied
                on st_mode.
            encoding: if contents is a unicode string, the encoding used for
                serialization.
            errors: the error mode used for encoding/decoding errors
            read_from_real_fs: if True, the contents are read from the real
                file system on demand.
            side_effect: function handle that is executed when file is written,
                must accept the file object as an argument.
        """
        path = self.make_string_path(file_path)
        path = self.absnormpath(path)
        if not is_int_type(st_mode):
            raise TypeError(
                'st_mode must be of int type - did you mean to set contents?')

        if self.exists(path, check_link=True):
            self.raise_os_error(errno.EEXIST, path)
        parent_directory, new_file = self.splitpath(path)
        if not parent_directory:
            parent_directory = matching_string(path, self.cwd)
        self._auto_mount_drive_if_needed(parent_directory)
        if not self.exists(parent_directory):
            if not create_missing_dirs:
                self.raise_os_error(errno.ENOENT, parent_directory)
            parent_directory = matching_string(
                path, self.create_dir(parent_directory).path)  # type: ignore
        else:
            parent_directory = self._original_path(parent_directory)
        if apply_umask:
            st_mode &= ~self.umask
        file_object: FakeFile
        if read_from_real_fs:
            file_object = FakeFileFromRealFile(to_string(path),
                                               filesystem=self,
                                               side_effect=side_effect)
        else:
            file_object = FakeFile(new_file, st_mode, filesystem=self,
                                   encoding=encoding, errors=errors,
                                   side_effect=side_effect)

        self.add_object(parent_directory, file_object)

        if st_size is None and contents is None:
            contents = ''
        if (not read_from_real_fs and
                (contents is not None or st_size is not None)):
            try:
                if st_size is not None:
                    file_object.set_large_file_size(st_size)
                else:
                    file_object.set_initial_contents(contents)  # type: ignore
            except OSError:
                self.remove_object(path)
                raise

        return file_object

    def create_symlink(self, file_path: AnyPath,
                       link_target: AnyPath,
                       create_missing_dirs: bool = True) -> FakeFile:
        """Create the specified symlink, pointed at the specified link target.

        Args:
            file_path:  path to the symlink to create
            link_target:  the target of the symlink
            create_missing_dirs: If `True`, any missing parent directories of
                file_path will be created

        Returns:
            The newly created FakeFile object.

        Raises:
            OSError: if the symlink could not be created
                (see :py:meth:`create_file`).
        """
        link_path = self.make_string_path(file_path)
        link_target_path = self.make_string_path(link_target)
        link_path = self.normcase(link_path)
        # the link path cannot end with a path separator
        if self.ends_with_path_separator(link_path):
            if self.exists(link_path):
                self.raise_os_error(errno.EEXIST, link_path)
            if self.exists(link_target_path):
                if not self.is_windows_fs:
                    self.raise_os_error(errno.ENOENT, link_path)
            else:
                if self.is_windows_fs:
                    self.raise_os_error(errno.EINVAL, link_target_path)
                if not self.exists(
                        self._path_without_trailing_separators(link_path),
                        check_link=True):
                    self.raise_os_error(errno.ENOENT, link_target_path)
                if self.is_macos:
                    # to avoid EEXIST exception, remove the link
                    # if it already exists
                    if self.exists(link_path, check_link=True):
                        self.remove_object(link_path)
                else:
                    self.raise_os_error(errno.EEXIST, link_target_path)

        # resolve the link path only if it is not a link itself
        if not self.islink(link_path):
            link_path = self.resolve_path(link_path)
        return self.create_file_internally(
            link_path, st_mode=S_IFLNK | PERM_DEF,
            contents=link_target_path,
            create_missing_dirs=create_missing_dirs)

    def create_link(self, old_path: AnyPath,
                    new_path: AnyPath,
                    follow_symlinks: bool = True,
                    create_missing_dirs: bool = True) -> FakeFile:
        """Create a hard link at new_path, pointing at old_path.

        Args:
            old_path: An existing link to the target file.
            new_path: The destination path to create a new link at.
            follow_symlinks: If False and old_path is a symlink, link the
                symlink instead of the object it points to.
            create_missing_dirs: If `True`, any missing parent directories of
                file_path will be created

        Returns:
            The FakeFile object referred to by old_path.

        Raises:
            OSError:  if something already exists at new_path.
            OSError:  if old_path is a directory.
            OSError:  if the parent directory doesn't exist.
        """
        old_path_str = make_string_path(old_path)
        new_path_str = make_string_path(new_path)
        new_path_normalized = self.absnormpath(new_path_str)
        if self.exists(new_path_normalized, check_link=True):
            self.raise_os_error(errno.EEXIST, new_path_str)

        new_parent_directory, new_basename = self.splitpath(
            new_path_normalized)
        if not new_parent_directory:
            new_parent_directory = matching_string(new_path_str, self.cwd)

        if not self.exists(new_parent_directory):
            if create_missing_dirs:
                self.create_dir(new_parent_directory)
            else:
                self.raise_os_error(errno.ENOENT, new_parent_directory)

        if self.ends_with_path_separator(old_path_str):
            error = errno.EINVAL if self.is_windows_fs else errno.ENOTDIR
            self.raise_os_error(error, old_path_str)

        if not self.is_windows_fs and self.ends_with_path_separator(new_path):
            self.raise_os_error(errno.ENOENT, old_path_str)

        # Retrieve the target file
        try:
            old_file = self.resolve(old_path_str,
                                    follow_symlinks=follow_symlinks)
        except OSError:
            self.raise_os_error(errno.ENOENT, old_path_str)

        if old_file.st_mode & S_IFDIR:
            self.raise_os_error(
                errno.EACCES if self.is_windows_fs
                else errno.EPERM, old_path_str
            )

        # abuse the name field to control the filename of the
        # newly created link
        old_file.name = new_basename  # type: ignore[assignment]
        self.add_object(new_parent_directory, old_file)
        return old_file

    def link(self, old_path: AnyPath,
             new_path: AnyPath,
             follow_symlinks: bool = True) -> FakeFile:
        """Create a hard link at new_path, pointing at old_path.

        Args:
            old_path: An existing link to the target file.
            new_path: The destination path to create a new link at.
            follow_symlinks: If False and old_path is a symlink, link the
                symlink instead of the object it points to.

        Returns:
            The FakeFile object referred to by old_path.

        Raises:
            OSError:  if something already exists at new_path.
            OSError:  if old_path is a directory.
            OSError:  if the parent directory doesn't exist.
        """
        return self.create_link(old_path, new_path, follow_symlinks,
                                create_missing_dirs=False)

    def _is_circular_link(self, link_obj: FakeFile) -> bool:
        try:
            assert link_obj.contents
            self.resolve_path(link_obj.contents)
        except OSError as exc:
            return exc.errno == errno.ELOOP
        return False

    def readlink(self, path: AnyPath) -> str:
        """Read the target of a symlink.

        Args:
            path:  symlink to read the target of.

        Returns:
            the string representing the path to which the symbolic link points.

        Raises:
            TypeError: if path is None
            OSError: (with errno=ENOENT) if path is not a valid path, or
                (with errno=EINVAL) if path is valid, but is not a symlink,
                or if the path ends with a path separator (Posix only)
        """
        if path is None:
            raise TypeError
        link_path = make_string_path(path)
        link_obj = self.lresolve(link_path)
        if S_IFMT(link_obj.st_mode) != S_IFLNK:
            self.raise_os_error(errno.EINVAL, link_path)

        if self.ends_with_path_separator(link_path):
            if not self.is_windows_fs and self.exists(link_path):
                self.raise_os_error(errno.EINVAL, link_path)
            if not self.exists(link_obj.path):  # type: ignore
                if self.is_windows_fs:
                    error = errno.EINVAL
                elif self._is_circular_link(link_obj):
                    if self.is_macos:
                        return link_obj.path  # type: ignore[return-value]
                    error = errno.ELOOP
                else:
                    error = errno.ENOENT
                self.raise_os_error(error, link_obj.path)

        assert link_obj.contents
        return link_obj.contents

    def makedir(self, dir_path: AnyPath, mode: int = PERM_DEF) -> None:
        """Create a leaf Fake directory.

        Args:
            dir_path: (str) Name of directory to create.
                Relative paths are assumed to be relative to '/'.
            mode: (int) Mode to create directory with.  This argument defaults
                to 0o777. The umask is applied to this mode.

        Raises:
            OSError: if the directory name is invalid or parent directory is
                read only or as per :py:meth:`add_object`.
        """
        dir_name = make_string_path(dir_path)
        ends_with_sep = self.ends_with_path_separator(dir_name)
        dir_name = self._path_without_trailing_separators(dir_name)
        if not dir_name:
            self.raise_os_error(errno.ENOENT, '')

        if self.is_windows_fs:
            dir_name = self.absnormpath(dir_name)
        parent_dir, _ = self.splitpath(dir_name)
        if parent_dir:
            base_dir = self.normpath(parent_dir)
            ellipsis = matching_string(parent_dir, self.path_separator + '..')
            if parent_dir.endswith(ellipsis) and not self.is_windows_fs:
                base_dir, dummy_dotdot, _ = parent_dir.partition(ellipsis)
            if not self.exists(base_dir):
                self.raise_os_error(errno.ENOENT, base_dir)

        dir_name = self.absnormpath(dir_name)
        if self.exists(dir_name, check_link=True):
            if self.is_windows_fs and dir_name == self.root_dir_name:
                error_nr = errno.EACCES
            else:
                error_nr = errno.EEXIST
            if ends_with_sep and self.is_macos and not self.exists(dir_name):
                # to avoid EEXIST exception, remove the link
                self.remove_object(dir_name)
            else:
                self.raise_os_error(error_nr, dir_name)
        head, tail = self.splitpath(dir_name)

        self.add_object(
            to_string(head),
            FakeDirectory(to_string(tail), mode & ~self.umask,
                          filesystem=self))

    def _path_without_trailing_separators(self, path: AnyStr) -> AnyStr:
        while self.ends_with_path_separator(path):
            path = path[:-1]
        return path

    def makedirs(self, dir_name: AnyStr, mode: int = PERM_DEF,
                 exist_ok: bool = False) -> None:
        """Create a leaf Fake directory and create any non-existent
        parent dirs.

        Args:
            dir_name: (str) Name of directory to create.
            mode: (int) Mode to create directory (and any necessary parent
                directories) with. This argument defaults to 0o777.
                The umask is applied to this mode.
          exist_ok: (boolean) If exist_ok is False (the default), an OSError is
                raised if the target directory already exists.

        Raises:
            OSError: if the directory already exists and exist_ok=False,
                or as per :py:meth:`create_dir`.
        """
        if not dir_name:
            self.raise_os_error(errno.ENOENT, '')
        ends_with_sep = self.ends_with_path_separator(dir_name)
        dir_name = self.absnormpath(dir_name)
        if (ends_with_sep and self.is_macos and
                self.exists(dir_name, check_link=True) and
                not self.exists(dir_name)):
            # to avoid EEXIST exception, remove the link
            self.remove_object(dir_name)

        dir_name_str = to_string(dir_name)
        path_components = self._path_components(dir_name_str)

        # Raise a permission denied error if the first existing directory
        # is not writeable.
        current_dir = self.root_dir
        for component in path_components:
            if (not hasattr(current_dir, "entries") or
                    component not in current_dir.entries):
                break
            else:
                current_dir = cast(FakeDirectory,
                                   current_dir.entries[component])
        try:
            self.create_dir(dir_name, mode & ~self.umask)
        except OSError as e:
            if e.errno == errno.EACCES:
                # permission denied - propagate exception
                raise
            if (not exist_ok or
                    not isinstance(self.resolve(dir_name), FakeDirectory)):
                if self.is_windows_fs and e.errno == errno.ENOTDIR:
                    e.errno = errno.ENOENT
                self.raise_os_error(e.errno, e.filename)

    def _is_of_type(self, path: AnyPath, st_flag: int,
                    follow_symlinks: bool = True,
                    check_read_perm: bool = True) -> bool:
        """Helper function to implement isdir(), islink(), etc.

        See the stat(2) man page for valid stat.S_I* flag values

        Args:
            path: Path to file to stat and test
            st_flag: The stat.S_I* flag checked for the file's st_mode
            check_read_perm: If True (default) False is returned for
                existing but unreadable file paths.

        Returns:
            (boolean) `True` if the st_flag is set in path's st_mode.

        Raises:
          TypeError: if path is None
        """
        if path is None:
            raise TypeError
        file_path = make_string_path(path)
        try:
            obj = self.resolve(file_path, follow_symlinks,
                               check_read_perm=check_read_perm)
            if obj:
                self.raise_for_filepath_ending_with_separator(
                    file_path, obj, macos_handling=not follow_symlinks)
                return S_IFMT(obj.st_mode) == st_flag
        except OSError:
            return False
        return False

    def isdir(self, path: AnyPath, follow_symlinks: bool = True) -> bool:
        """Determine if path identifies a directory.

        Args:
            path: Path to filesystem object.

        Returns:
            `True` if path points to a directory (following symlinks).

        Raises:
            TypeError: if path is None.
        """
        return self._is_of_type(path, S_IFDIR, follow_symlinks)

    def isfile(self, path: AnyPath, follow_symlinks: bool = True) -> bool:
        """Determine if path identifies a regular file.

        Args:
            path: Path to filesystem object.

        Returns:
            `True` if path points to a regular file (following symlinks).

        Raises:
            TypeError: if path is None.
        """
        return self._is_of_type(path, S_IFREG, follow_symlinks,
                                check_read_perm=False)

    def islink(self, path: AnyPath) -> bool:
        """Determine if path identifies a symbolic link.

        Args:
            path: Path to filesystem object.

        Returns:
            `True` if path points to a symlink (S_IFLNK set in st_mode)

        Raises:
            TypeError: if path is None.
        """
        return self._is_of_type(path, S_IFLNK, follow_symlinks=False)

    def confirmdir(
            self, target_directory: AnyStr, check_owner: bool = False
    ) -> FakeDirectory:
        """Test that the target is actually a directory, raising OSError
        if not.

        Args:
            target_directory: Path to the target directory within the fake
                filesystem.
            check_owner: If True, only checks read permission if the current
                user id is different from the file object user id

        Returns:
            The FakeDirectory object corresponding to target_directory.

        Raises:
            OSError: if the target is not a directory.
        """
        directory = cast(FakeDirectory, self.resolve(
            target_directory, check_owner=check_owner))
        if not directory.st_mode & S_IFDIR:
            self.raise_os_error(errno.ENOTDIR, target_directory, 267)
        return directory

    def remove(self, path: AnyStr) -> None:
        """Remove the FakeFile object at the specified file path.

        Args:
            path: Path to file to be removed.

        Raises:
            OSError: if path points to a directory.
            OSError: if path does not exist.
            OSError: if removal failed.
        """
        norm_path = make_string_path(path)
        norm_path = self.absnormpath(norm_path)
        if self.ends_with_path_separator(path):
            self._handle_broken_link_with_trailing_sep(norm_path)
        if self.exists(norm_path):
            obj = self.resolve(norm_path, check_read_perm=False)
            if S_IFMT(obj.st_mode) == S_IFDIR:
                link_obj = self.lresolve(norm_path)
                if S_IFMT(link_obj.st_mode) != S_IFLNK:
                    if self.is_windows_fs:
                        error = errno.EACCES
                    elif self.is_macos:
                        error = errno.EPERM
                    else:
                        error = errno.EISDIR
                    self.raise_os_error(error, norm_path)

                if path.endswith(self.get_path_separator(path)):
                    if self.is_windows_fs:
                        error = errno.EACCES
                    elif self.is_macos:
                        error = errno.EPERM
                    else:
                        error = errno.ENOTDIR
                    self.raise_os_error(error, norm_path)
            else:
                self.raise_for_filepath_ending_with_separator(path, obj)

        self.remove_object(norm_path)

    def rmdir(self, target_directory: AnyStr,
              allow_symlink: bool = False) -> None:
        """Remove a leaf Fake directory.

        Args:
            target_directory: (str) Name of directory to remove.
            allow_symlink: (bool) if `target_directory` is a symlink,
                the function just returns, otherwise it raises (Posix only)

        Raises:
            OSError: if target_directory does not exist.
            OSError: if target_directory does not point to a directory.
            OSError: if removal failed per FakeFilesystem.RemoveObject.
                Cannot remove '.'.
        """
        if target_directory == matching_string(target_directory, '.'):
            error_nr = errno.EACCES if self.is_windows_fs else errno.EINVAL
            self.raise_os_error(error_nr, target_directory)
        ends_with_sep = self.ends_with_path_separator(target_directory)
        target_directory = self.absnormpath(target_directory)
        if self.confirmdir(target_directory, check_owner=True):
            if not self.is_windows_fs and self.islink(target_directory):
                if allow_symlink:
                    return
                if not ends_with_sep or not self.is_macos:
                    self.raise_os_error(errno.ENOTDIR, target_directory)

            dir_object = self.resolve(target_directory, check_owner=True)
            if dir_object.entries:
                self.raise_os_error(errno.ENOTEMPTY, target_directory)
            self.remove_object(target_directory)

    def listdir(self, target_directory: AnyStr) -> List[AnyStr]:
        """Return a list of file names in target_directory.

        Args:
            target_directory: Path to the target directory within the
                fake filesystem.

        Returns:
            A list of file names within the target directory in arbitrary
            order. If `shuffle_listdir_results` is set, the order is not the
            same in subsequent calls to avoid tests relying on any ordering.

        Raises:
            OSError: if the target is not a directory.
        """
        target_directory = self.resolve_path(target_directory, allow_fd=True)
        directory = self.confirmdir(target_directory)
        directory_contents = list(directory.entries.keys())
        if self.shuffle_listdir_results:
            random.shuffle(directory_contents)
        return directory_contents  # type: ignore[return-value]

    def __str__(self) -> str:
        return str(self.root_dir)

    def _add_standard_streams(self) -> None:
        self._add_open_file(StandardStreamWrapper(sys.stdin))
        self._add_open_file(StandardStreamWrapper(sys.stdout))
        self._add_open_file(StandardStreamWrapper(sys.stderr))


class FakePathModule:
    """Faked os.path module replacement.

    FakePathModule should *only* be instantiated by FakeOsModule.  See the
    FakeOsModule docstring for details.
    """
    _OS_PATH_COPY: Any = _copy_module(os.path)

    devnull: ClassVar[str] = ''
    sep: ClassVar[str] = ''
    altsep: ClassVar[Optional[str]] = None
    linesep: ClassVar[str] = ''
    pathsep: ClassVar[str] = ''

    @staticmethod
    def dir() -> List[str]:
        """Return the list of patched function names. Used for patching
        functions imported from the module.
        """
        return [
            'abspath', 'dirname', 'exists', 'expanduser', 'getatime',
            'getctime', 'getmtime', 'getsize', 'isabs', 'isdir', 'isfile',
            'islink', 'ismount', 'join', 'lexists', 'normcase', 'normpath',
            'realpath', 'relpath', 'split', 'splitdrive', 'samefile'
        ]

    def __init__(self, filesystem: FakeFilesystem, os_module: 'FakeOsModule'):
        """Init.

        Args:
            filesystem: FakeFilesystem used to provide file system information
        """
        self.filesystem = filesystem
        self._os_path = self._OS_PATH_COPY
        self._os_path.os = self.os = os_module  # type: ignore[attr-defined]
        self.reset(filesystem)

    @classmethod
    def reset(cls, filesystem: FakeFilesystem) -> None:
        cls.sep = filesystem.path_separator
        cls.altsep = filesystem.alternative_path_separator
        cls.linesep = filesystem.line_separator()
        cls.devnull = 'nul' if filesystem.is_windows_fs else '/dev/null'
        cls.pathsep = ';' if filesystem.is_windows_fs else ':'

    def exists(self, path: AnyStr) -> bool:
        """Determine whether the file object exists within the fake filesystem.

        Args:
            path: The path to the file object.

        Returns:
            (bool) `True` if the file exists.
        """
        return self.filesystem.exists(path)

    def lexists(self, path: AnyStr) -> bool:
        """Test whether a path exists.  Returns True for broken symbolic links.

        Args:
          path:  path to the symlink object.

        Returns:
          bool (if file exists).
        """
        return self.filesystem.exists(path, check_link=True)

    def getsize(self, path: AnyStr):
        """Return the file object size in bytes.

        Args:
          path:  path to the file object.

        Returns:
          file size in bytes.
        """
        file_obj = self.filesystem.resolve(path)
        if (self.filesystem.ends_with_path_separator(path) and
                S_IFMT(file_obj.st_mode) != S_IFDIR):
            error_nr = (errno.EINVAL if self.filesystem.is_windows_fs
                        else errno.ENOTDIR)
            self.filesystem.raise_os_error(error_nr, path)
        return file_obj.st_size

    def isabs(self, path: AnyStr) -> bool:
        """Return True if path is an absolute pathname."""
        if self.filesystem.is_windows_fs:
            path = self.splitdrive(path)[1]
        path = make_string_path(path)
        return self.filesystem.starts_with_sep(path)

    def isdir(self, path: AnyStr) -> bool:
        """Determine if path identifies a directory."""
        return self.filesystem.isdir(path)

    def isfile(self, path: AnyStr) -> bool:
        """Determine if path identifies a regular file."""
        return self.filesystem.isfile(path)

    def islink(self, path: AnyStr) -> bool:
        """Determine if path identifies a symbolic link.

        Args:
            path: Path to filesystem object.

        Returns:
            `True` if path points to a symbolic link.

        Raises:
            TypeError: if path is None.
        """
        return self.filesystem.islink(path)

    def getmtime(self, path: AnyStr) -> float:
        """Returns the modification time of the fake file.

        Args:
            path: the path to fake file.

        Returns:
            (int, float) the modification time of the fake file
                         in number of seconds since the epoch.

        Raises:
            OSError: if the file does not exist.
        """
        try:
            file_obj = self.filesystem.resolve(path)
            return file_obj.st_mtime
        except OSError:
            self.filesystem.raise_os_error(errno.ENOENT, winerror=3)

    def getatime(self, path: AnyStr) -> float:
        """Returns the last access time of the fake file.

        Note: Access time is not set automatically in fake filesystem
            on access.

        Args:
            path: the path to fake file.

        Returns:
            (int, float) the access time of the fake file in number of seconds
                since the epoch.

        Raises:
            OSError: if the file does not exist.
        """
        try:
            file_obj = self.filesystem.resolve(path)
        except OSError:
            self.filesystem.raise_os_error(errno.ENOENT)
        return file_obj.st_atime

    def getctime(self, path: AnyStr) -> float:
        """Returns the creation time of the fake file.

        Args:
            path: the path to fake file.

        Returns:
            (int, float) the creation time of the fake file in number of
                seconds since the epoch.

        Raises:
            OSError: if the file does not exist.
        """
        try:
            file_obj = self.filesystem.resolve(path)
        except OSError:
            self.filesystem.raise_os_error(errno.ENOENT)
        return file_obj.st_ctime

    def abspath(self, path: AnyStr) -> AnyStr:
        """Return the absolute version of a path."""

        def getcwd():
            """Return the current working directory."""
            # pylint: disable=undefined-variable
            if isinstance(path, bytes):
                return self.os.getcwdb()
            else:
                return self.os.getcwd()

        path = make_string_path(path)
        if not self.isabs(path):
            path = self.join(getcwd(), path)
        elif (self.filesystem.is_windows_fs and
              self.filesystem.starts_with_sep(path)):
            cwd = getcwd()
            if self.filesystem.starts_with_drive_letter(cwd):
                path = self.join(cwd[:2], path)
        return self.normpath(path)

    def join(self, *p: AnyStr) -> AnyStr:
        """Return the completed path with a separator of the parts."""
        return self.filesystem.joinpaths(*p)

    def split(self, path: AnyStr) -> Tuple[AnyStr, AnyStr]:
        """Split the path into the directory and the filename of the path.
        """
        return self.filesystem.splitpath(path)

    def splitdrive(self, path: AnyStr) -> Tuple[AnyStr, AnyStr]:
        """Split the path into the drive part and the rest of the path, if
        supported."""
        return self.filesystem.splitdrive(path)

    def normpath(self, path: AnyStr) -> AnyStr:
        """Normalize path, eliminating double slashes, etc."""
        return self.filesystem.normpath(path)

    def normcase(self, path: AnyStr) -> AnyStr:
        """Convert to lower case under windows, replaces additional path
        separator."""
        path = self.filesystem.normcase(path)
        if self.filesystem.is_windows_fs:
            path = path.lower()
        return path

    def relpath(self, path: AnyStr, start: Optional[AnyStr] = None) -> AnyStr:
        """We mostly rely on the native implementation and adapt the
        path separator."""
        if not path:
            raise ValueError("no path specified")
        path = make_string_path(path)
        path = self.filesystem.replace_windows_root(path)
        sep = matching_string(path, self.filesystem.path_separator)
        if start is not None:
            start = make_string_path(start)
        else:
            start = matching_string(path, self.filesystem.cwd)
        start = self.filesystem.replace_windows_root(start)
        system_sep = matching_string(path, self._os_path.sep)
        if self.filesystem.alternative_path_separator is not None:
            altsep = matching_string(
                path, self.filesystem.alternative_path_separator)
            path = path.replace(altsep, system_sep)
            start = start.replace(altsep, system_sep)
        path = path.replace(sep, system_sep)
        start = start.replace(sep, system_sep)
        path = self._os_path.relpath(path, start)
        return path.replace(system_sep, sep)

    def realpath(self, filename: AnyStr, strict: bool = None) -> AnyStr:
        """Return the canonical path of the specified filename, eliminating any
        symbolic links encountered in the path.
        """
        if strict is not None and sys.version_info < (3, 10):
            raise TypeError("realpath() got an unexpected "
                            "keyword argument 'strict'")
        if strict:
            # raises in strict mode if the file does not exist
            self.filesystem.resolve(filename)
        if self.filesystem.is_windows_fs:
            return self.abspath(filename)
        filename = make_string_path(filename)
        path, ok = self._join_real_path(filename[:0], filename, {})
        path = self.abspath(path)
        return path

    def samefile(self, path1: AnyStr, path2: AnyStr) -> bool:
        """Return whether path1 and path2 point to the same file.

        Args:
            path1: first file path or path object (Python >=3.6)
            path2: second file path or path object (Python >=3.6)

        Raises:
            OSError: if one of the paths does not point to an existing
                file system object.
        """
        stat1 = self.filesystem.stat(path1)
        stat2 = self.filesystem.stat(path2)
        return (stat1.st_ino == stat2.st_ino and
                stat1.st_dev == stat2.st_dev)

    @overload
    def _join_real_path(
            self, path: str,
            rest: str,
            seen: Dict[str, Optional[str]]) -> Tuple[str, bool]: ...

    @overload
    def _join_real_path(
            self, path: bytes,
            rest: bytes,
            seen: Dict[bytes, Optional[bytes]]) -> Tuple[bytes, bool]: ...

    def _join_real_path(
            self, path: AnyStr,
            rest: AnyStr,
            seen: Dict[AnyStr, Optional[AnyStr]]) -> Tuple[AnyStr, bool]:
        """Join two paths, normalizing and eliminating any symbolic links
        encountered in the second path.
        Taken from Python source and adapted.
        """
        curdir = matching_string(path, '.')
        pardir = matching_string(path, '..')

        sep = self.filesystem.get_path_separator(path)
        if self.isabs(rest):
            rest = rest[1:]
            path = sep

        while rest:
            name, _, rest = rest.partition(sep)
            if not name or name == curdir:
                # current dir
                continue
            if name == pardir:
                # parent dir
                if path:
                    path, name = self.filesystem.splitpath(path)
                    if name == pardir:
                        path = self.filesystem.joinpaths(path, pardir, pardir)
                else:
                    path = pardir
                continue
            newpath = self.filesystem.joinpaths(path, name)
            if not self.filesystem.islink(newpath):
                path = newpath
                continue
            # Resolve the symbolic link
            if newpath in seen:
                # Already seen this path
                seen_path = seen[newpath]
                if seen_path is not None:
                    # use cached value
                    path = seen_path
                    continue
                # The symlink is not resolved, so we must have a symlink loop.
                # Return already resolved part + rest of the path unchanged.
                return self.filesystem.joinpaths(newpath, rest), False
            seen[newpath] = None  # not resolved symlink
            path, ok = self._join_real_path(
                path, matching_string(path, self.filesystem.readlink(
                    newpath)), seen)
            if not ok:
                return self.filesystem.joinpaths(path, rest), False
            seen[newpath] = path  # resolved symlink
        return path, True

    def dirname(self, path: AnyStr) -> AnyStr:
        """Returns the first part of the result of `split()`."""
        return self.split(path)[0]

    def expanduser(self, path: AnyStr) -> AnyStr:
        """Return the argument with an initial component of ~ or ~user
        replaced by that user's home directory.
        """
        path = self._os_path.expanduser(path)
        return path.replace(
            matching_string(path, self._os_path.sep),
            matching_string(path, self.sep))

    def ismount(self, path: AnyStr) -> bool:
        """Return true if the given path is a mount point.

        Args:
            path: Path to filesystem object to be checked

        Returns:
            `True` if path is a mount point added to the fake file system.
            Under Windows also returns True for drive and UNC roots
            (independent of their existence).
        """
        if not path:
            return False
        path_str = to_string(make_string_path(path))
        normed_path = self.filesystem.absnormpath(path_str)
        sep = self.filesystem.path_separator
        if self.filesystem.is_windows_fs:
            path_seps: Union[Tuple[str, Optional[str]], Tuple[str]]
            if self.filesystem.alternative_path_separator is not None:
                path_seps = (
                    sep, self.filesystem.alternative_path_separator
                )
            else:
                path_seps = (sep,)
            drive, rest = self.filesystem.splitdrive(normed_path)
            if drive and drive[:1] in path_seps:
                return (not rest) or (rest in path_seps)
            if rest in path_seps:
                return True
        for mount_point in self.filesystem.mount_points:
            if (to_string(normed_path).rstrip(sep) ==
                    to_string(mount_point).rstrip(sep)):
                return True
        return False

    def __getattr__(self, name: str) -> Any:
        """Forwards any non-faked calls to the real os.path."""
        return getattr(self._os_path, name)


class FakeOsModule:
    """Uses FakeFilesystem to provide a fake os module replacement.

    Do not create os.path separately from os, as there is a necessary circular
    dependency between os and os.path to replicate the behavior of the standard
    Python modules.  What you want to do is to just let FakeOsModule take care
    of `os.path` setup itself.

    # You always want to do this.
    filesystem = fake_filesystem.FakeFilesystem()
    my_os_module = fake_filesystem.FakeOsModule(filesystem)
    """

    use_original = False

    @staticmethod
    def dir() -> List[str]:
        """Return the list of patched function names. Used for patching
        functions imported from the module.
        """
        _dir = [
            'access', 'chdir', 'chmod', 'chown', 'close', 'fstat', 'fsync',
            'getcwd', 'lchmod', 'link', 'listdir', 'lstat', 'makedirs',
            'mkdir', 'mknod', 'open', 'read', 'readlink', 'remove',
            'removedirs', 'rename', 'rmdir', 'stat', 'symlink', 'umask',
            'unlink', 'utime', 'walk', 'write', 'getcwdb', 'replace'
        ]
        if sys.platform.startswith('linux'):
            _dir += [
                'fdatasync', 'getxattr', 'listxattr',
                'removexattr', 'setxattr'
            ]
        if use_scandir:
            _dir += ['scandir']
        return _dir

    def __init__(self, filesystem: FakeFilesystem):
        """Also exposes self.path (to fake os.path).

        Args:
            filesystem: FakeFilesystem used to provide file system information
        """
        self.filesystem = filesystem
        self.os_module: Any = os
        self.path = FakePathModule(self.filesystem, self)

    @property
    def devnull(self) -> str:
        return self.path.devnull

    @property
    def sep(self) -> str:
        return self.path.sep

    @property
    def altsep(self) -> Optional[str]:
        return self.path.altsep

    @property
    def linesep(self) -> str:
        return self.path.linesep

    @property
    def pathsep(self) -> str:
        return self.path.pathsep

    def fdopen(self, fd: int, *args: Any, **kwargs: Any) -> AnyFileWrapper:
        """Redirector to open() builtin function.

        Args:
            fd: The file descriptor of the file to open.
            *args: Pass through args.
            **kwargs: Pass through kwargs.

        Returns:
            File object corresponding to file_des.

        Raises:
            TypeError: if file descriptor is not an integer.
        """
        if not is_int_type(fd):
            raise TypeError('an integer is required')
        return FakeFileOpen(self.filesystem)(fd, *args, **kwargs)

    def _umask(self) -> int:
        """Return the current umask."""
        if self.filesystem.is_windows_fs:
            # windows always returns 0 - it has no real notion of umask
            return 0
        if sys.platform == 'win32':
            # if we are testing Unix under Windows we assume a default mask
            return 0o002
        else:
            # under Unix, we return the real umask;
            # as there is no pure getter for umask, so we have to first
            # set a mode to get the previous one and then re-set that
            mask = os.umask(0)
            os.umask(mask)
            return mask

    def open(self, path: AnyStr, flags: int, mode: Optional[int] = None, *,
             dir_fd: Optional[int] = None) -> int:
        """Return the file descriptor for a FakeFile.

        Args:
            path: the path to the file
            flags: low-level bits to indicate io operation
            mode: bits to define default permissions
                Note: only basic modes are supported, OS-specific modes are
                ignored
            dir_fd: If not `None`, the file descriptor of a directory,
                with `file_path` being relative to this directory.

        Returns:
            A file descriptor.

        Raises:
            OSError: if the path cannot be found
            ValueError: if invalid mode is given
            NotImplementedError: if `os.O_EXCL` is used without `os.O_CREAT`
        """
        path = self._path_with_dir_fd(path, self.open, dir_fd)
        if mode is None:
            if self.filesystem.is_windows_fs:
                mode = 0o666
            else:
                mode = 0o777 & ~self._umask()

        has_tmpfile_flag = (hasattr(os, 'O_TMPFILE') and
                            flags & os.O_TMPFILE == os.O_TMPFILE)
        open_modes = _OpenModes(
            must_exist=not flags & os.O_CREAT and not has_tmpfile_flag,
            can_read=not flags & os.O_WRONLY,
            can_write=flags & (os.O_RDWR | os.O_WRONLY) != 0,
            truncate=flags & os.O_TRUNC != 0,
            append=flags & os.O_APPEND != 0,
            must_not_exist=flags & os.O_EXCL != 0
        )
        if open_modes.must_not_exist and open_modes.must_exist:
            raise NotImplementedError(
                'O_EXCL without O_CREAT mode is not supported')
        if has_tmpfile_flag:
            # this is a workaround for tempfiles that do not have a filename
            # as we do not support this directly, we just add a unique filename
            # and set the file to delete on close
            path = self.filesystem.joinpaths(
                path, matching_string(path, str(uuid.uuid4())))

        if (not self.filesystem.is_windows_fs and
                self.filesystem.exists(path)):
            # handle opening directory - only allowed under Posix
            # with read-only mode
            obj = self.filesystem.resolve(path)
            if isinstance(obj, FakeDirectory):
                if ((not open_modes.must_exist and
                     not self.filesystem.is_macos)
                        or open_modes.can_write):
                    self.filesystem.raise_os_error(errno.EISDIR, path)
                dir_wrapper = FakeDirWrapper(obj, path, self.filesystem)
                file_des = self.filesystem._add_open_file(dir_wrapper)
                dir_wrapper.filedes = file_des
                return file_des

        # low level open is always binary
        str_flags = 'b'
        delete_on_close = has_tmpfile_flag
        if hasattr(os, 'O_TEMPORARY'):
            delete_on_close = flags & os.O_TEMPORARY == os.O_TEMPORARY
        fake_file = FakeFileOpen(
            self.filesystem, delete_on_close=delete_on_close, raw_io=True)(
            path, str_flags, open_modes=open_modes)
        assert not isinstance(fake_file, StandardStreamWrapper)
        if fake_file.file_object != self.filesystem.dev_null:
            self.chmod(path, mode)
        return fake_file.fileno()

    def close(self, fd: int) -> None:
        """Close a file descriptor.

        Args:
            fd: An integer file descriptor for the file object requested.

        Raises:
            OSError: bad file descriptor.
            TypeError: if file descriptor is not an integer.
        """
        file_handle = self.filesystem.get_open_file(fd)
        file_handle.close()

    def read(self, fd: int, n: int) -> bytes:
        """Read number of bytes from a file descriptor, returns bytes read.

        Args:
            fd: An integer file descriptor for the file object requested.
            n: Number of bytes to read from file.

        Returns:
            Bytes read from file.

        Raises:
            OSError: bad file descriptor.
            TypeError: if file descriptor is not an integer.
        """
        file_handle = self.filesystem.get_open_file(fd)
        if isinstance(file_handle, FakeFileWrapper):
            file_handle.raw_io = True
        if isinstance(file_handle, FakeDirWrapper):
            self.filesystem.raise_os_error(errno.EBADF, file_handle.file_path)
        return file_handle.read(n)

    def write(self, fd: int, contents: bytes) -> int:
        """Write string to file descriptor, returns number of bytes written.

        Args:
            fd: An integer file descriptor for the file object requested.
            contents: String of bytes to write to file.

        Returns:
            Number of bytes written.

        Raises:
            OSError: bad file descriptor.
            TypeError: if file descriptor is not an integer.
        """
        file_handle = cast(FakeFileWrapper, self.filesystem.get_open_file(fd))
        if isinstance(file_handle, FakeDirWrapper):
            self.filesystem.raise_os_error(errno.EBADF, file_handle.file_path)

        if isinstance(file_handle, FakePipeWrapper):
            return file_handle.write(contents)

        file_handle.raw_io = True
        file_handle._sync_io()
        file_handle.update_flush_pos()
        file_handle.write(contents)
        file_handle.flush()
        return len(contents)

    def pipe(self) -> Tuple[int, int]:
        read_fd, write_fd = os.pipe()
        read_wrapper = FakePipeWrapper(self.filesystem, read_fd, False)
        file_des = self.filesystem._add_open_file(read_wrapper)
        read_wrapper.filedes = file_des
        write_wrapper = FakePipeWrapper(self.filesystem, write_fd, True)
        file_des = self.filesystem._add_open_file(write_wrapper)
        write_wrapper.filedes = file_des
        return read_wrapper.filedes, write_wrapper.filedes

    def fstat(self, fd: int) -> FakeStatResult:
        """Return the os.stat-like tuple for the FakeFile object of file_des.

        Args:
            fd: The file descriptor of filesystem object to retrieve.

        Returns:
            The FakeStatResult object corresponding to entry_path.

        Raises:
            OSError: if the filesystem object doesn't exist.
        """
        # stat should return the tuple representing return value of os.stat
        file_object = self.filesystem.get_open_file(fd).get_object()
        assert isinstance(file_object, FakeFile)
        return file_object.stat_result.copy()

    def umask(self, mask: int) -> int:
        """Change the current umask.

        Args:
            mask: (int) The new umask value.

        Returns:
            The old umask.

        Raises:
            TypeError: if new_mask is of an invalid type.
        """
        if not is_int_type(mask):
            raise TypeError('an integer is required')
        old_umask = self.filesystem.umask
        self.filesystem.umask = mask
        return old_umask

    def chdir(self, path: AnyStr) -> None:
        """Change current working directory to target directory.

        Args:
            path: The path to new current working directory.

        Raises:
            OSError: if user lacks permission to enter the argument directory
                or if the target is not a directory.
        """
        try:
            path = self.filesystem.resolve_path(
                path, allow_fd=True)
        except OSError as exc:
            if self.filesystem.is_macos and exc.errno == errno.EBADF:
                raise OSError(errno.ENOTDIR, "Not a directory: " + str(path))
            raise
        self.filesystem.confirmdir(path)
        directory = self.filesystem.resolve(path)
        # A full implementation would check permissions all the way
        # up the tree.
        if not is_root() and not directory.st_mode | PERM_EXE:
            self.filesystem.raise_os_error(errno.EACCES, directory.name)
        self.filesystem.cwd = path  # type: ignore[assignment]

    def getcwd(self) -> str:
        """Return current working directory."""
        return to_string(self.filesystem.cwd)

    def getcwdb(self) -> bytes:
        """Return current working directory as bytes."""
        return to_bytes(self.filesystem.cwd)

    def listdir(self, path: AnyStr) -> List[AnyStr]:
        """Return a list of file names in target_directory.

        Args:
            path: Path to the target directory within the fake
                filesystem.

        Returns:
            A list of file names within the target directory in arbitrary
                order.

        Raises:
          OSError:  if the target is not a directory.
        """
        return self.filesystem.listdir(path)

    XATTR_CREATE = 1
    XATTR_REPLACE = 2

    def getxattr(self, path: AnyStr, attribute: AnyString, *,
                 follow_symlinks: bool = True) -> Optional[bytes]:
        """Return the value of the given extended filesystem attribute for
        `path`.

        Args:
            path: File path, file descriptor or path-like object (for
                Python >= 3.6).
            attribute: (str or bytes) The attribute name.
            follow_symlinks: (bool) If True (the default), symlinks in the
                path are traversed.

        Returns:
            The contents of the extended attribute as bytes or None if
            the attribute does not exist.

        Raises:
            OSError: if the path does not exist.
        """
        if not self.filesystem.is_linux:
            raise AttributeError(
                "module 'os' has no attribute 'getxattr'")

        if isinstance(attribute, bytes):
            attribute = attribute.decode(sys.getfilesystemencoding())
        file_obj = self.filesystem.resolve(path, follow_symlinks,
                                           allow_fd=True)
        return file_obj.xattr.get(attribute)

    def listxattr(self, path: Optional[AnyStr] = None, *,
                  follow_symlinks: bool = True) -> List[str]:
        """Return a list of the extended filesystem attributes on `path`.

        Args:
            path: File path, file descriptor or path-like object (for
                Python >= 3.6). If None, the current directory is used.
            follow_symlinks: (bool) If True (the default), symlinks in the
                path are traversed.

        Returns:
            A list of all attribute names for the given path as str.

        Raises:
            OSError: if the path does not exist.
        """
        if not self.filesystem.is_linux:
            raise AttributeError(
                "module 'os' has no attribute 'listxattr'")

        path_str = self.filesystem.cwd if path is None else path
        file_obj = self.filesystem.resolve(
            cast(AnyStr, path_str), follow_symlinks, allow_fd=True)
        return list(file_obj.xattr.keys())

    def removexattr(self, path: AnyStr, attribute: AnyString, *,
                    follow_symlinks: bool = True) -> None:
        """Removes the extended filesystem attribute attribute from `path`.

        Args:
            path: File path, file descriptor or path-like object (for
                Python >= 3.6).
            attribute: (str or bytes) The attribute name.
            follow_symlinks: (bool) If True (the default), symlinks in the
                path are traversed.

        Raises:
            OSError: if the path does not exist.
        """
        if not self.filesystem.is_linux:
            raise AttributeError(
                "module 'os' has no attribute 'removexattr'")

        if isinstance(attribute, bytes):
            attribute = attribute.decode(sys.getfilesystemencoding())
        file_obj = self.filesystem.resolve(path, follow_symlinks,
                                           allow_fd=True)
        if attribute in file_obj.xattr:
            del file_obj.xattr[attribute]

    def setxattr(self, path: AnyStr, attribute: AnyString, value: bytes,
                 flags: int = 0, *, follow_symlinks: bool = True) -> None:
        """Sets the value of the given extended filesystem attribute for
        `path`.

        Args:
            path: File path, file descriptor or path-like object (for
                Python >= 3.6).
            attribute: The attribute name (str or bytes).
            value: (byte-like) The value to be set.
            follow_symlinks: (bool) If True (the default), symlinks in the
                path are traversed.

        Raises:
            OSError: if the path does not exist.
            TypeError: if `value` is not a byte-like object.
        """
        if not self.filesystem.is_linux:
            raise AttributeError(
                "module 'os' has no attribute 'setxattr'")

        if isinstance(attribute, bytes):
            attribute = attribute.decode(sys.getfilesystemencoding())
        if not is_byte_string(value):
            raise TypeError('a bytes-like object is required')
        file_obj = self.filesystem.resolve(path, follow_symlinks,
                                           allow_fd=True)
        exists = attribute in file_obj.xattr
        if exists and flags == self.XATTR_CREATE:
            self.filesystem.raise_os_error(errno.ENODATA, file_obj.path)
        if not exists and flags == self.XATTR_REPLACE:
            self.filesystem.raise_os_error(errno.EEXIST, file_obj.path)
        file_obj.xattr[attribute] = value

    def scandir(self, path: str = '.') -> ScanDirIter:
        """Return an iterator of DirEntry objects corresponding to the
        entries in the directory given by path.

        Args:
            path: Path to the target directory within the fake filesystem.

        Returns:
            An iterator to an unsorted list of os.DirEntry objects for
            each entry in path.

        Raises:
            OSError: if the target is not a directory.
        """
        return scandir(self.filesystem, path)

    def walk(self, top: AnyStr, topdown: bool = True,
             onerror: Optional[bool] = None,
             followlinks: bool = False):
        """Perform an os.walk operation over the fake filesystem.

        Args:
            top: The root directory from which to begin walk.
            topdown: Determines whether to return the tuples with the root as
                the first entry (`True`) or as the last, after all the child
                directory tuples (`False`).
          onerror: If not `None`, function which will be called to handle the
                `os.error` instance provided when `os.listdir()` fails.
          followlinks: If `True`, symbolic links are followed.

        Yields:
            (path, directories, nondirectories) for top and each of its
            subdirectories.  See the documentation for the builtin os module
            for further details.
        """
        return walk(self.filesystem, top, topdown, onerror, followlinks)

    def readlink(self, path: AnyStr, dir_fd: Optional[int] = None) -> str:
        """Read the target of a symlink.

        Args:
            path:  Symlink to read the target of.
            dir_fd: If not `None`, the file descriptor of a directory,
                with `path` being relative to this directory.

        Returns:
            the string representing the path to which the symbolic link points.

        Raises:
            TypeError: if `path` is None
            OSError: (with errno=ENOENT) if path is not a valid path, or
                     (with errno=EINVAL) if path is valid, but is not a symlink
        """
        path = self._path_with_dir_fd(path, self.readlink, dir_fd)
        return self.filesystem.readlink(path)

    def stat(self, path: AnyStr, *, dir_fd: Optional[int] = None,
             follow_symlinks: bool = True) -> FakeStatResult:
        """Return the os.stat-like tuple for the FakeFile object of entry_path.

        Args:
            path:  path to filesystem object to retrieve.
            dir_fd: (int) If not `None`, the file descriptor of a directory,
                with `entry_path` being relative to this directory.
            follow_symlinks: (bool) If `False` and `entry_path` points to a
                symlink, the link itself is changed instead of the linked
                object.

        Returns:
            The FakeStatResult object corresponding to entry_path.

        Raises:
            OSError: if the filesystem object doesn't exist.
        """
        path = self._path_with_dir_fd(path, self.stat, dir_fd)
        return self.filesystem.stat(path, follow_symlinks)

    def lstat(self, path: AnyStr, *,
              dir_fd: Optional[int] = None) -> FakeStatResult:
        """Return the os.stat-like tuple for entry_path,
        not following symlinks.

        Args:
            path:  path to filesystem object to retrieve.
            dir_fd: If not `None`, the file descriptor of a directory, with
                `path` being relative to this directory.

        Returns:
            the FakeStatResult object corresponding to `path`.

        Raises:
            OSError: if the filesystem object doesn't exist.
        """
        # stat should return the tuple representing return value of os.stat
        path = self._path_with_dir_fd(path, self.lstat, dir_fd)
        return self.filesystem.stat(path, follow_symlinks=False)

    def remove(self, path: AnyStr, dir_fd: Optional[int] = None) -> None:
        """Remove the FakeFile object at the specified file path.

        Args:
            path: Path to file to be removed.
            dir_fd: If not `None`, the file descriptor of a directory,
                with `path` being relative to this directory.

        Raises:
            OSError: if path points to a directory.
            OSError: if path does not exist.
            OSError: if removal failed.
        """
        path = self._path_with_dir_fd(path, self.remove, dir_fd)
        self.filesystem.remove(path)

    def unlink(self, path: AnyStr, *, dir_fd: Optional[int] = None) -> None:
        """Remove the FakeFile object at the specified file path.

        Args:
            path: Path to file to be removed.
            dir_fd: If not `None`, the file descriptor of a directory,
                with `path` being relative to this directory.

        Raises:
            OSError: if path points to a directory.
            OSError: if path does not exist.
            OSError: if removal failed.
        """
        path = self._path_with_dir_fd(path, self.unlink, dir_fd)
        self.filesystem.remove(path)

    def rename(self, src: AnyStr, dst: AnyStr, *,
               src_dir_fd: Optional[int] = None,
               dst_dir_fd: Optional[int] = None) -> None:
        """Rename a FakeFile object at old_file_path to new_file_path,
        preserving all properties.
        Also replaces existing new_file_path object, if one existed
        (Unix only).

        Args:
            src: Path to filesystem object to rename.
            dst: Path to where the filesystem object will live
                after this call.
            src_dir_fd: If not `None`, the file descriptor of a directory,
                with `src` being relative to this directory.
            dst_dir_fd: If not `None`, the file descriptor of a directory,
                with `dst` being relative to this directory.

        Raises:
            OSError: if old_file_path does not exist.
            OSError: if new_file_path is an existing directory.
            OSError: if new_file_path is an existing file (Windows only)
            OSError: if new_file_path is an existing file and could not
                be removed (Unix)
            OSError: if `dirname(new_file)` does not exist
            OSError: if the file would be moved to another filesystem
                (e.g. mount point)
        """
        src = self._path_with_dir_fd(src, self.rename, src_dir_fd)
        dst = self._path_with_dir_fd(dst, self.rename, dst_dir_fd)
        self.filesystem.rename(src, dst)

    def renames(self, old: AnyStr, new: AnyStr):
        """Fakes `os.renames`, documentation taken from there.

        Super-rename; create directories as necessary and delete any left
        empty.  Works like rename, except creation of any intermediate
        directories needed to make the new pathname good is attempted
        first.  After the rename, directories corresponding to rightmost
        path segments of the old name will be pruned until either the
        whole path is consumed or a nonempty directory is found.

        Note: this function can fail with the new directory structure made
        if you lack permissions needed to unlink the leaf directory or
        file.

        """
        head, tail = self.filesystem.splitpath(new)
        if head and tail and not self.filesystem.exists(head):
            self.makedirs(head)
        self.rename(old, new)
        head, tail = self.filesystem.splitpath(old)
        if head and tail:
            try:
                self.removedirs(head)
            except OSError:
                pass

    def replace(self, src: AnyStr, dst: AnyStr, *,
                src_dir_fd: Optional[int] = None,
                dst_dir_fd: Optional[int] = None) -> None:
        """Renames a FakeFile object at old_file_path to new_file_path,
        preserving all properties.
        Also replaces existing new_file_path object, if one existed.

        Arg
            src: Path to filesystem object to rename.
            dst: Path to where the filesystem object will live
                after this call.
            src_dir_fd: If not `None`, the file descriptor of a directory,
                with `src` being relative to this directory.
            dst_dir_fd: If not `None`, the file descriptor of a directory,
                with `dst` being relative to this directory.

        Raises:
            OSError: if old_file_path does not exist.
            OSError: if new_file_path is an existing directory.
            OSError: if new_file_path is an existing file and could
                not be removed
            OSError: if `dirname(new_file)` does not exist
            OSError: if the file would be moved to another filesystem
                (e.g. mount point)
        """
        src = self._path_with_dir_fd(src, self.rename, src_dir_fd)
        dst = self._path_with_dir_fd(dst, self.rename, dst_dir_fd)
        self.filesystem.rename(src, dst, force_replace=True)

    def rmdir(self, path: AnyStr, *, dir_fd: Optional[int] = None) -> None:
        """Remove a leaf Fake directory.

        Args:
            path: (str) Name of directory to remove.
            dir_fd: If not `None`, the file descriptor of a directory,
                with `path` being relative to this directory.

        Raises:
            OSError: if `path` does not exist or is not a directory,
            or as per FakeFilesystem.remove_object. Cannot remove '.'.
        """
        path = self._path_with_dir_fd(path, self.rmdir, dir_fd)
        self.filesystem.rmdir(path)

    def removedirs(self, name: AnyStr) -> None:
        """Remove a leaf fake directory and all empty intermediate ones.

        Args:
            name: the directory to be removed.

        Raises:
            OSError: if target_directory does not exist or is not a directory.
            OSError: if target_directory is not empty.
        """
        name = self.filesystem.absnormpath(name)
        directory = self.filesystem.confirmdir(name)
        if directory.entries:
            self.filesystem.raise_os_error(
                errno.ENOTEMPTY, self.path.basename(name))
        else:
            self.rmdir(name)
        head, tail = self.path.split(name)
        if not tail:
            head, tail = self.path.split(head)
        while head and tail:
            head_dir = self.filesystem.confirmdir(head)
            if head_dir.entries:
                break
            # only the top-level dir may not be a symlink
            self.filesystem.rmdir(head, allow_symlink=True)
            head, tail = self.path.split(head)

    def mkdir(self, path: AnyStr, mode: int = PERM_DEF, *,
              dir_fd: Optional[int] = None) -> None:
        """Create a leaf Fake directory.

        Args:
            path: (str) Name of directory to create.
                Relative paths are assumed to be relative to '/'.
            mode: (int) Mode to create directory with.  This argument defaults
                to 0o777.  The umask is applied to this mode.
            dir_fd: If not `None`, the file descriptor of a directory,
                with `path` being relative to this directory.

        Raises:
            OSError: if the directory name is invalid or parent directory is
                read only or as per FakeFilesystem.add_object.
        """
        path = self._path_with_dir_fd(path, self.mkdir, dir_fd)
        try:
            self.filesystem.makedir(path, mode)
        except OSError as e:
            if e.errno == errno.EACCES:
                self.filesystem.raise_os_error(e.errno, path)
            raise

    def makedirs(self, name: AnyStr, mode: int = PERM_DEF,
                 exist_ok: bool = None) -> None:
        """Create a leaf Fake directory + create any non-existent parent dirs.

        Args:
            name: (str) Name of directory to create.
            mode: (int) Mode to create directory (and any necessary parent
                directories) with. This argument defaults to 0o777.
                The umask is applied to this mode.
            exist_ok: (boolean) If exist_ok is False (the default), an OSError
                is raised if the target directory already exists.

        Raises:
            OSError: if the directory already exists and exist_ok=False, or as
                per :py:meth:`FakeFilesystem.create_dir`.
        """
        if exist_ok is None:
            exist_ok = False
        self.filesystem.makedirs(name, mode, exist_ok)

    def _path_with_dir_fd(self, path: AnyStr, fct: Callable,
                          dir_fd: Optional[int]) -> AnyStr:
        """Return the path considering dir_fd. Raise on invalid parameters."""
        try:
            path = make_string_path(path)
        except TypeError:
            # the error is handled later
            path = path
        if dir_fd is not None:
            # check if fd is supported for the built-in real function
            real_fct = getattr(os, fct.__name__)
            if real_fct not in self.supports_dir_fd:
                raise NotImplementedError(
                    'dir_fd unavailable on this platform')
            if isinstance(path, int):
                raise ValueError("%s: Can't specify dir_fd without "
                                 "matching path_str" % fct.__name__)
            if not self.path.isabs(path):
                open_file = self.filesystem.get_open_file(dir_fd)
                return self.path.join(  # type: ignore[type-var, return-value]
                    cast(FakeFile, open_file.get_object()).path, path)
        return path

    def truncate(self, path: AnyStr, length: int) -> None:
        """Truncate the file corresponding to path, so that it is
         length bytes in size. If length is larger than the current size,
         the file is filled up with zero bytes.

        Args:
            path: (str or int) Path to the file, or an integer file
                descriptor for the file object.
            length: (int) Length of the file after truncating it.

        Raises:
            OSError: if the file does not exist or the file descriptor is
                invalid.
         """
        file_object = self.filesystem.resolve(path, allow_fd=True)
        file_object.size = length

    def ftruncate(self, fd: int, length: int) -> None:
        """Truncate the file corresponding to fd, so that it is
         length bytes in size. If length is larger than the current size,
         the file is filled up with zero bytes.

        Args:
            fd: (int) File descriptor for the file object.
            length: (int) Maximum length of the file after truncating it.

        Raises:
            OSError: if the file descriptor is invalid
         """
        file_object = self.filesystem.get_open_file(fd).get_object()
        if isinstance(file_object, FakeFileWrapper):
            file_object.size = length
        else:
            raise OSError(errno.EBADF, 'Invalid file descriptor')

    def access(self, path: AnyStr, mode: int, *,
               dir_fd: Optional[int] = None,
               effective_ids: bool = False,
               follow_symlinks: bool = True) -> bool:
        """Check if a file exists and has the specified permissions.

        Args:
            path: (str) Path to the file.
            mode: (int) Permissions represented as a bitwise-OR combination of
                os.F_OK, os.R_OK, os.W_OK, and os.X_OK.
            dir_fd: If not `None`, the file descriptor of a directory, with
                `path` being relative to this directory.
            effective_ids: (bool) Unused. Only here to match the signature.
            follow_symlinks: (bool) If `False` and `path` points to a symlink,
                the link itself is queried instead of the linked object.

        Returns:
            bool, `True` if file is accessible, `False` otherwise.
        """
        if effective_ids and self.filesystem.is_windows_fs:
            raise NotImplementedError(
                'access: effective_ids unavailable on this platform')
        path = self._path_with_dir_fd(path, self.access, dir_fd)
        try:
            stat_result = self.stat(path, follow_symlinks=follow_symlinks)
        except OSError as os_error:
            if os_error.errno == errno.ENOENT:
                return False
            raise
        if is_root():
            mode &= ~os.W_OK
        return (mode & ((stat_result.st_mode >> 6) & 7)) == mode

    def chmod(self, path: AnyStr, mode: int, *,
              dir_fd: Optional[int] = None,
              follow_symlinks: bool = True) -> None:
        """Change the permissions of a file as encoded in integer mode.

        Args:
            path: (str) Path to the file.
            mode: (int) Permissions.
            dir_fd: If not `None`, the file descriptor of a directory, with
                `path` being relative to this directory.
            follow_symlinks: (bool) If `False` and `path` points to a symlink,
                the link itself is queried instead of the linked object.
        """
        if (not follow_symlinks and
                (os.chmod not in os.supports_follow_symlinks or IS_PYPY)):
            raise NotImplementedError(
                "`follow_symlinks` for chmod() is not available "
                "on this system")
        path = self._path_with_dir_fd(path, self.chmod, dir_fd)
        self.filesystem.chmod(path, mode, follow_symlinks)

    def lchmod(self, path: AnyStr, mode: int) -> None:
        """Change the permissions of a file as encoded in integer mode.
        If the file is a link, the permissions of the link are changed.

        Args:
          path: (str) Path to the file.
          mode: (int) Permissions.
        """
        if self.filesystem.is_windows_fs:
            raise NameError("name 'lchmod' is not defined")
        self.filesystem.chmod(path, mode, follow_symlinks=False)

    def utime(self, path: AnyStr,
              times: Optional[Tuple[Union[int, float], Union[int, float]]] =
              None, ns: Optional[Tuple[int, int]] = None,
              dir_fd: Optional[int] = None,
              follow_symlinks: bool = True) -> None:
        """Change the access and modified times of a file.

        Args:
            path: (str) Path to the file.
            times: 2-tuple of int or float numbers, of the form (atime, mtime)
                which is used to set the access and modified times in seconds.
                If None, both times are set to the current time.
            ns: 2-tuple of int numbers, of the form (atime, mtime)  which is
                used to set the access and modified times in nanoseconds.
                If None, both times are set to the current time.
            dir_fd: If not `None`, the file descriptor of a directory,
                with `path` being relative to this directory.
            follow_symlinks: (bool) If `False` and `path` points to a symlink,
                the link itself is queried instead of the linked object.

            Raises:
                TypeError: If anything other than the expected types is
                    specified in the passed `times` or `ns` tuple,
                    or if the tuple length is not equal to 2.
                ValueError: If both times and ns are specified.
        """
        path = self._path_with_dir_fd(path, self.utime, dir_fd)
        self.filesystem.utime(
            path, times=times, ns=ns, follow_symlinks=follow_symlinks)

    def chown(self, path: AnyStr, uid: int, gid: int, *,
              dir_fd: Optional[int] = None,
              follow_symlinks: bool = True) -> None:
        """Set ownership of a faked file.

        Args:
            path: (str) Path to the file or directory.
            uid: (int) Numeric uid to set the file or directory to.
            gid: (int) Numeric gid to set the file or directory to.
            dir_fd: (int) If not `None`, the file descriptor of a directory,
                with `path` being relative to this directory.
            follow_symlinks: (bool) If `False` and path points to a symlink,
                the link itself is changed instead of the linked object.

        Raises:
            OSError: if path does not exist.

        `None` is also allowed for `uid` and `gid`.  This permits `os.rename`
        to use `os.chown` even when the source file `uid` and `gid` are
        `None` (unset).
        """
        path = self._path_with_dir_fd(path, self.chown, dir_fd)
        file_object = self.filesystem.resolve(
            path, follow_symlinks, allow_fd=True)
        if not isinstance(uid, int) or not isinstance(gid, int):
            raise TypeError("An integer is required")
        if uid != -1:
            file_object.st_uid = uid
        if gid != -1:
            file_object.st_gid = gid

    def mknod(self, path: AnyStr, mode: Optional[int] = None,
              device: int = 0, *,
              dir_fd: Optional[int] = None) -> None:
        """Create a filesystem node named 'filename'.

        Does not support device special files or named pipes as the real os
        module does.

        Args:
            path: (str) Name of the file to create
            mode: (int) Permissions to use and type of file to be created.
                Default permissions are 0o666.  Only the stat.S_IFREG file type
                is supported by the fake implementation.  The umask is applied
                to this mode.
            device: not supported in fake implementation
            dir_fd: If not `None`, the file descriptor of a directory,
                with `path` being relative to this directory.

        Raises:
          OSError: if called with unsupported options or the file can not be
          created.
        """
        if self.filesystem.is_windows_fs:
            raise AttributeError("module 'os' has no attribute 'mknode'")
        if mode is None:
            # note that a default value of 0o600 without a device type is
            # documented - this is not how it seems to work
            mode = S_IFREG | 0o600
        if device or not mode & S_IFREG and not is_root():
            self.filesystem.raise_os_error(errno.EPERM)

        path = self._path_with_dir_fd(path, self.mknod, dir_fd)
        head, tail = self.path.split(path)
        if not tail:
            if self.filesystem.exists(head, check_link=True):
                self.filesystem.raise_os_error(errno.EEXIST, path)
            self.filesystem.raise_os_error(errno.ENOENT, path)
        if tail in (matching_string(tail, '.'), matching_string(tail, '..')):
            self.filesystem.raise_os_error(errno.ENOENT, path)
        if self.filesystem.exists(path, check_link=True):
            self.filesystem.raise_os_error(errno.EEXIST, path)
        self.filesystem.add_object(head, FakeFile(
            tail, mode & ~self.filesystem.umask,
            filesystem=self.filesystem))

    def symlink(self, src: AnyStr, dst: AnyStr,
                target_is_directory: bool = False, *,
                dir_fd: Optional[int] = None) -> None:
        """Creates the specified symlink, pointed at the specified link target.

        Args:
            src: The target of the symlink.
            dst: Path to the symlink to create.
            target_is_directory: Currently ignored.
            dir_fd: If not `None`, the file descriptor of a directory,
                with `src` being relative to this directory.

        Raises:
            OSError:  if the file already exists.
        """
        src = self._path_with_dir_fd(src, self.symlink, dir_fd)
        self.filesystem.create_symlink(
            dst, src, create_missing_dirs=False)

    def link(self, src: AnyStr, dst: AnyStr, *,
             src_dir_fd: Optional[int] = None,
             dst_dir_fd: Optional[int] = None) -> None:
        """Create a hard link at new_path, pointing at old_path.

        Args:
            src: An existing path to the target file.
            dst: The destination path to create a new link at.
            src_dir_fd: If not `None`, the file descriptor of a directory,
                with `src` being relative to this directory.
            dst_dir_fd: If not `None`, the file descriptor of a directory,
                with `dst` being relative to this directory.

        Raises:
            OSError:  if something already exists at new_path.
            OSError:  if the parent directory doesn't exist.
        """
        src = self._path_with_dir_fd(src, self.link, src_dir_fd)
        dst = self._path_with_dir_fd(dst, self.link, dst_dir_fd)
        self.filesystem.link(src, dst)

    def fsync(self, fd: int) -> None:
        """Perform fsync for a fake file (in other words, do nothing).

        Args:
            fd: The file descriptor of the open file.

        Raises:
            OSError: file_des is an invalid file descriptor.
            TypeError: file_des is not an integer.
        """
        # Throw an error if file_des isn't valid
        if 0 <= fd < NR_STD_STREAMS:
            self.filesystem.raise_os_error(errno.EINVAL)
        file_object = cast(FakeFileWrapper, self.filesystem.get_open_file(fd))
        if self.filesystem.is_windows_fs:
            if (not hasattr(file_object, 'allow_update') or
                    not file_object.allow_update):
                self.filesystem.raise_os_error(
                    errno.EBADF, file_object.file_path)

    def fdatasync(self, fd: int) -> None:
        """Perform fdatasync for a fake file (in other words, do nothing).

        Args:
            fd: The file descriptor of the open file.

        Raises:
            OSError: `fd` is an invalid file descriptor.
            TypeError: `fd` is not an integer.
        """
        if self.filesystem.is_windows_fs or self.filesystem.is_macos:
            raise AttributeError("module 'os' has no attribute 'fdatasync'")
        # Throw an error if file_des isn't valid
        if 0 <= fd < NR_STD_STREAMS:
            self.filesystem.raise_os_error(errno.EINVAL)
        self.filesystem.get_open_file(fd)

    def sendfile(self, fd_out: int, fd_in: int,
                 offset: int, count: int) -> int:
        """Copy count bytes from file descriptor fd_in to file descriptor
        fd_out starting at offset.

        Args:
            fd_out: The file descriptor of the destination file.
            fd_in: The file descriptor of the source file.
            offset: The offset in bytes where to start the copy in the
                source file. If `None` (Linux only), copying is started at
                the current position, and the position is updated.
            count: The number of bytes to copy. If 0, all remaining bytes
                are copied (MacOs only).

        Raises:
            OSError: If `fd_in` or `fd_out` is an invalid file descriptor.
            TypeError: If `fd_in` or `fd_out` is not an integer.
            TypeError: If `offset` is None under MacOs.
        """
        if self.filesystem.is_windows_fs:
            raise AttributeError("module 'os' has no attribute 'sendfile'")
        if 0 <= fd_in < NR_STD_STREAMS:
            self.filesystem.raise_os_error(errno.EINVAL)
        if 0 <= fd_out < NR_STD_STREAMS:
            self.filesystem.raise_os_error(errno.EINVAL)
        source = cast(FakeFileWrapper, self.filesystem.get_open_file(fd_in))
        dest = cast(FakeFileWrapper, self.filesystem.get_open_file(fd_out))
        if self.filesystem.is_macos:
            if dest.get_object().stat_result.st_mode & 0o777000 != S_IFSOCK:
                raise OSError('Socket operation on non-socket')
        if offset is None:
            if self.filesystem.is_macos:
                raise TypeError('None is not a valid offset')
            contents = source.read(count)
        else:
            position = source.tell()
            source.seek(offset)
            if count == 0 and self.filesystem.is_macos:
                contents = source.read()
            else:
                contents = source.read(count)
            source.seek(position)
        if contents:
            written = dest.write(contents)
            dest.flush()
            return written
        return 0

    def __getattr__(self, name: str) -> Any:
        """Forwards any unfaked calls to the standard os module."""
        return getattr(self.os_module, name)


if sys.version_info > (3, 10):
    def handle_original_call(f: Callable) -> Callable:
        """Decorator used for real pathlib Path methods to ensure that
        real os functions instead of faked ones are used.
        Applied to all non-private methods of `FakeOsModule`."""
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if not f.__name__.startswith('_') and FakeOsModule.use_original:
                # remove the `self` argument for FakeOsModule methods
                if args and isinstance(args[0], FakeOsModule):
                    args = args[1:]
                return getattr(os, f.__name__)(*args, **kwargs)
            return f(*args, **kwargs)
        return wrapped

    for name, fn in inspect.getmembers(FakeOsModule, inspect.isfunction):
        setattr(FakeOsModule, name, handle_original_call(fn))


@contextmanager
def use_original_os():
    """Temporarily use original os functions instead of faked ones.
    Used to ensure that skipped modules do not use faked calls.
    """
    try:
        FakeOsModule.use_original = True
        yield
    finally:
        FakeOsModule.use_original = False


class FakeIoModule:
    """Uses FakeFilesystem to provide a fake io module replacement.

    You need a fake_filesystem to use this:
    filesystem = fake_filesystem.FakeFilesystem()
    my_io_module = fake_filesystem.FakeIoModule(filesystem)
    """

    @staticmethod
    def dir() -> List[str]:
        """Return the list of patched function names. Used for patching
        functions imported from the module.
        """
        _dir = ['open']
        if sys.version_info >= (3, 8):
            _dir.append('open_code')
        return _dir

    def __init__(self, filesystem: FakeFilesystem):
        """
        Args:
            filesystem: FakeFilesystem used to provide file system information.
        """
        self.filesystem = filesystem
        self.skip_names: List[str] = []
        self._io_module = io

    def open(self, file: Union[AnyStr, int],
             mode: str = 'r', buffering: int = -1,
             encoding: Optional[str] = None,
             errors: Optional[str] = None,
             newline: Optional[str] = None,
             closefd: bool = True,
             opener: Optional[Callable] = None) -> Union[AnyFileWrapper,
                                                         IO[Any]]:
        """Redirect the call to FakeFileOpen.
        See FakeFileOpen.call() for description.
        """
        # workaround for built-in open called from skipped modules (see #552)
        # as open is not imported explicitly, we cannot patch it for
        # specific modules; instead we check if the caller is a skipped
        # module (should work in most cases)
        stack = traceback.extract_stack(limit=2)
        module_name = os.path.splitext(stack[0].filename)[0]
        module_name = module_name.replace(os.sep, '.')
        if any([module_name == sn or module_name.endswith('.' + sn)
                for sn in self.skip_names]):
            return io.open(file, mode, buffering, encoding, errors,
                           newline, closefd, opener)
        fake_open = FakeFileOpen(self.filesystem)
        return fake_open(file, mode, buffering, encoding, errors,
                         newline, closefd, opener)

    if sys.version_info >= (3, 8):
        def open_code(self, path):
            """Redirect the call to open. Note that the behavior of the real
            function may be overridden by an earlier call to the
            PyFile_SetOpenCodeHook(). This behavior is not reproduced here.
            """
            if not isinstance(path, str):
                raise TypeError(
                    "open_code() argument 'path' must be str, not int")
            patch_mode = self.filesystem.patch_open_code
            if (patch_mode == PatchMode.AUTO and self.filesystem.exists(path)
                    or patch_mode == PatchMode.ON):
                return self.open(path, mode='rb')
            # mostly this is used for compiled code -
            # don't patch these, as the files are probably in the real fs
            return self._io_module.open_code(path)

    def __getattr__(self, name):
        """Forwards any unfaked calls to the standard io module."""
        return getattr(self._io_module, name)


if sys.platform != 'win32':
    import fcntl

    class FakeFcntlModule:
        """Replaces the fcntl module. Only valid under Linux/MacOS,
        currently just mocks the functionality away.
        """

        @staticmethod
        def dir() -> List[str]:
            """Return the list of patched function names. Used for patching
            functions imported from the module.
            """
            return ['fcntl', 'ioctl', 'flock', 'lockf']

        def __init__(self, filesystem: FakeFilesystem):
            """
            Args:
                filesystem: FakeFilesystem used to provide file system
                    information (currently not used).
            """
            self.filesystem = filesystem
            self._fcntl_module = fcntl

        def fcntl(self, fd: int, cmd: int, arg: int = 0) -> Union[int, bytes]:
            return 0 if isinstance(arg, int) else arg

        def ioctl(self, fd: int, request: int, arg: int = 0,
                  mutate_flag: bool = True) -> Union[int, bytes]:
            return 0 if isinstance(arg, int) else arg

        def flock(self, fd: int, operation: int) -> None:
            pass

        def lockf(self, fd: int, cmd: int, len: int = 0,
                  start: int = 0, whence=0) -> Any:
            pass

        def __getattr__(self, name):
            """Forwards any unfaked calls to the standard fcntl module."""
            return getattr(self._fcntl_module, name)


class FakeFileWrapper:
    """Wrapper for a stream object for use by a FakeFile object.

    If the wrapper has any data written to it, it will propagate to
    the FakeFile object on close() or flush().
    """

    def __init__(self, file_object: FakeFile,
                 file_path: AnyStr,
                 update: bool, read: bool, append: bool, delete_on_close: bool,
                 filesystem: FakeFilesystem,
                 newline: Optional[str], binary: bool, closefd: bool,
                 encoding: Optional[str], errors: Optional[str],
                 buffering: int, raw_io: bool, is_stream: bool = False):
        self.file_object = file_object
        self.file_path = file_path  # type: ignore[var-annotated]
        self._append = append
        self._read = read
        self.allow_update = update
        self._closefd = closefd
        self._file_epoch = file_object.epoch
        self.raw_io = raw_io
        self._binary = binary
        self.is_stream = is_stream
        self._changed = False
        self._buffer_size = buffering
        if self._buffer_size == 0 and not binary:
            raise ValueError("can't have unbuffered text I/O")
        # buffer_size is ignored in text mode
        elif self._buffer_size == -1 or not binary:
            self._buffer_size = io.DEFAULT_BUFFER_SIZE
        self._use_line_buffer = not binary and buffering == 1

        contents = file_object.byte_contents
        self._encoding = encoding or locale.getpreferredencoding(False)
        errors = errors or 'strict'
        self._io: Union[BinaryBufferIO, TextBufferIO] = (
            BinaryBufferIO(contents) if binary
            else TextBufferIO(contents, encoding=encoding,
                              newline=newline, errors=errors)
        )
        self._read_whence = 0
        self._read_seek = 0
        self._flush_pos = 0
        if contents:
            self._flush_pos = len(contents)
            if update:
                if not append:
                    self._io.seek(0)
                else:
                    self._io.seek(self._flush_pos)
                    self._read_seek = self._io.tell()

        if delete_on_close:
            assert filesystem, 'delete_on_close=True requires filesystem'
        self._filesystem = filesystem
        self.delete_on_close = delete_on_close
        # override, don't modify FakeFile.name, as FakeFilesystem expects
        # it to be the file name only, no directories.
        self.name = file_object.opened_as
        self.filedes: Optional[int] = None

    def __enter__(self) -> 'FakeFileWrapper':
        """To support usage of this fake file with the 'with' statement."""
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]
                 ) -> None:
        """To support usage of this fake file with the 'with' statement."""
        self.close()

    def _raise(self, message: str) -> NoReturn:
        if self.raw_io:
            self._filesystem.raise_os_error(errno.EBADF, self.file_path)
        raise io.UnsupportedOperation(message)

    def get_object(self) -> FakeFile:
        """Return the FakeFile object that is wrapped by the current instance.
        """
        return self.file_object

    def fileno(self) -> int:
        """Return the file descriptor of the file object."""
        if self.filedes is not None:
            return self.filedes
        raise OSError(errno.EBADF, 'Invalid file descriptor')

    def close(self) -> None:
        """Close the file."""
        # ignore closing a closed file
        if not self._is_open():
            return

        # for raw io, all writes are flushed immediately
        if self.allow_update and not self.raw_io:
            self.flush()
            if self._filesystem.is_windows_fs and self._changed:
                self.file_object.st_mtime = now()

        assert self.filedes is not None
        if self._closefd:
            self._filesystem._close_open_file(self.filedes)
        else:
            open_files = self._filesystem.open_files[self.filedes]
            assert open_files is not None
            open_files.remove(self)
        if self.delete_on_close:
            self._filesystem.remove_object(
                self.get_object().path)  # type: ignore[arg-type]

    @property
    def closed(self) -> bool:
        """Simulate the `closed` attribute on file."""
        return not self._is_open()

    def _try_flush(self, old_pos: int) -> None:
        """Try to flush and reset the position if it fails."""
        flush_pos = self._flush_pos
        try:
            self.flush()
        except OSError:
            # write failed - reset to previous position
            self._io.seek(old_pos)
            self._io.truncate()
            self._flush_pos = flush_pos
            raise

    def flush(self) -> None:
        """Flush file contents to 'disk'."""
        self._check_open_file()
        if self.allow_update and not self.is_stream:
            contents = self._io.getvalue()
            if self._append:
                self._sync_io()
                old_contents = self.file_object.byte_contents
                assert old_contents is not None
                contents = old_contents + contents[self._flush_pos:]
                self._set_stream_contents(contents)
            else:
                self._io.flush()
            changed = self.file_object.set_contents(contents, self._encoding)
            self.update_flush_pos()
            if changed:
                if self._filesystem.is_windows_fs:
                    self._changed = True
                else:
                    current_time = now()
                    self.file_object.st_ctime = current_time
                    self.file_object.st_mtime = current_time
            self._file_epoch = self.file_object.epoch

            if not self.is_stream:
                self._flush_related_files()

    def update_flush_pos(self) -> None:
        self._flush_pos = self._io.tell()

    def _flush_related_files(self) -> None:
        for open_files in self._filesystem.open_files[3:]:
            if open_files is not None:
                for open_file in open_files:
                    if (open_file is not self and
                            isinstance(open_file, FakeFileWrapper) and
                            self.file_object == open_file.file_object and
                            not open_file._append):
                        open_file._sync_io()

    def seek(self, offset: int, whence: int = 0) -> None:
        """Move read/write pointer in 'file'."""
        self._check_open_file()
        if not self._append:
            self._io.seek(offset, whence)
        else:
            self._read_seek = offset
            self._read_whence = whence
        if not self.is_stream:
            self.flush()

    def tell(self) -> int:
        """Return the file's current position.

        Returns:
          int, file's current position in bytes.
        """
        self._check_open_file()
        if not self.is_stream:
            self.flush()

        if not self._append:
            return self._io.tell()
        if self._read_whence:
            write_seek = self._io.tell()
            self._io.seek(self._read_seek, self._read_whence)
            self._read_seek = self._io.tell()
            self._read_whence = 0
            self._io.seek(write_seek)
        return self._read_seek

    def _sync_io(self) -> None:
        """Update the stream with changes to the file object contents."""
        if self._file_epoch == self.file_object.epoch:
            return

        contents = self.file_object.byte_contents
        assert contents is not None
        self._set_stream_contents(contents)
        self._file_epoch = self.file_object.epoch

    def _set_stream_contents(self, contents: bytes) -> None:
        whence = self._io.tell()
        self._io.seek(0)
        self._io.truncate()
        self._io.putvalue(contents)
        if not self._append:
            self._io.seek(whence)

    def _read_wrappers(self, name: str) -> Callable:
        """Wrap a stream attribute in a read wrapper.

        Returns a read_wrapper which tracks our own read pointer since the
        stream object has no concept of a different read and write pointer.

        Args:
            name: The name of the attribute to wrap. Should be a read call.

        Returns:
            The read_wrapper function.
        """
        io_attr = getattr(self._io, name)

        def read_wrapper(*args, **kwargs):
            """Wrap all read calls to the stream object.

            We do this to track the read pointer separate from the write
            pointer.  Anything that wants to read from the stream object
            while we're in append mode goes through this.

            Args:
                *args: pass through args
                **kwargs: pass through kwargs
            Returns:
                Wrapped stream object method
            """
            self._io.seek(self._read_seek, self._read_whence)
            ret_value = io_attr(*args, **kwargs)
            self._read_seek = self._io.tell()
            self._read_whence = 0
            self._io.seek(0, 2)
            return ret_value

        return read_wrapper

    def _other_wrapper(self, name: str) -> Callable:
        """Wrap a stream attribute in an other_wrapper.

        Args:
          name: the name of the stream attribute to wrap.

        Returns:
          other_wrapper which is described below.
        """
        io_attr = getattr(self._io, name)

        def other_wrapper(*args, **kwargs):
            """Wrap all other calls to the stream Object.

            We do this to track changes to the write pointer.  Anything that
            moves the write pointer in a file open for appending should move
            the read pointer as well.

            Args:
                *args: Pass through args.
                **kwargs: Pass through kwargs.

            Returns:
                Wrapped stream object method.
            """
            write_seek = self._io.tell()
            ret_value = io_attr(*args, **kwargs)
            if write_seek != self._io.tell():
                self._read_seek = self._io.tell()
                self._read_whence = 0

            return ret_value

        return other_wrapper

    def _write_wrapper(self, name: str) -> Callable:
        """Wrap a stream attribute in a write_wrapper.

        Args:
          name: the name of the stream attribute to wrap.

        Returns:
          write_wrapper which is described below.
        """
        io_attr = getattr(self._io, name)

        def write_wrapper(*args, **kwargs):
            """Wrap all other calls to the stream Object.

            We do this to track changes to the write pointer.  Anything that
            moves the write pointer in a file open for appending should move
            the read pointer as well.

            Args:
                *args: Pass through args.
                **kwargs: Pass through kwargs.

            Returns:
                Wrapped stream object method.
            """
            old_pos = self._io.tell()
            ret_value = io_attr(*args, **kwargs)
            new_pos = self._io.tell()

            # if the buffer size is exceeded, we flush
            use_line_buf = self._use_line_buffer and '\n' in args[0]
            if new_pos - self._flush_pos > self._buffer_size or use_line_buf:
                flush_all = (new_pos - old_pos > self._buffer_size or
                             use_line_buf)
                # if the current write does not exceed the buffer size,
                # we revert to the previous position and flush that,
                # otherwise we flush all
                if not flush_all:
                    self._io.seek(old_pos)
                    self._io.truncate()
                self._try_flush(old_pos)
                if not flush_all:
                    ret_value = io_attr(*args, **kwargs)
            if self._append:
                self._read_seek = self._io.tell()
                self._read_whence = 0
            return ret_value

        return write_wrapper

    def _adapt_size_for_related_files(self, size: int) -> None:
        for open_files in self._filesystem.open_files[3:]:
            if open_files is not None:
                for open_file in open_files:
                    if (open_file is not self and
                            isinstance(open_file, FakeFileWrapper) and
                            self.file_object == open_file.file_object and
                            cast(FakeFileWrapper, open_file)._append):
                        open_file._read_seek += size

    def _truncate_wrapper(self) -> Callable:
        """Wrap truncate() to allow flush after truncate.

        Returns:
            Wrapper which is described below.
        """
        io_attr = getattr(self._io, 'truncate')

        def truncate_wrapper(*args, **kwargs):
            """Wrap truncate call to call flush after truncate."""
            if self._append:
                self._io.seek(self._read_seek, self._read_whence)
            size = io_attr(*args, **kwargs)
            self.flush()
            if not self.is_stream:
                self.file_object.size = size
                buffer_size = len(self._io.getvalue())
                if buffer_size < size:
                    self._io.seek(buffer_size)
                    self._io.putvalue(b'\0' * (size - buffer_size))
                    self.file_object.set_contents(
                        self._io.getvalue(), self._encoding)
                    self._flush_pos = size
                    self._adapt_size_for_related_files(size - buffer_size)

            self.flush()
            return size

        return truncate_wrapper

    def size(self) -> int:
        """Return the content size in bytes of the wrapped file."""
        return self.file_object.st_size

    def __getattr__(self, name: str) -> Any:
        if self.file_object.is_large_file():
            raise FakeLargeFileIoException(self.file_path)

        reading = name.startswith('read') or name == 'next'
        truncate = name == 'truncate'
        writing = name.startswith('write') or truncate

        if reading or writing:
            self._check_open_file()
        if not self._read and reading:
            return self._read_error()
        if not self.allow_update and writing:
            return self._write_error()

        if reading:
            self._sync_io()
            if not self.is_stream:
                self.flush()
            if not self._filesystem.is_windows_fs:
                self.file_object.st_atime = now()
        if truncate:
            return self._truncate_wrapper()
        if self._append:
            if reading:
                return self._read_wrappers(name)
            elif not writing:
                return self._other_wrapper(name)
        if writing:
            return self._write_wrapper(name)

        return getattr(self._io, name)

    def _read_error(self) -> Callable:
        def read_error(*args, **kwargs):
            """Throw an error unless the argument is zero."""
            if args and args[0] == 0:
                if self._filesystem.is_windows_fs and self.raw_io:
                    return b'' if self._binary else u''
            self._raise('File is not open for reading.')

        return read_error

    def _write_error(self) -> Callable:
        def write_error(*args, **kwargs):
            """Throw an error."""
            if self.raw_io:
                if (self._filesystem.is_windows_fs and args
                        and len(args[0]) == 0):
                    return 0
            self._raise('File is not open for writing.')

        return write_error

    def _is_open(self) -> bool:
        if (self.filedes is not None and
                self.filedes < len(self._filesystem.open_files)):
            open_files = self._filesystem.open_files[self.filedes]
            if open_files is not None and self in open_files:
                return True
        return False

    def _check_open_file(self) -> None:
        if not self.is_stream and not self._is_open():
            raise ValueError('I/O operation on closed file')

    def __iter__(self) -> Union[Iterator[str], Iterator[bytes]]:
        if not self._read:
            self._raise('File is not open for reading')
        return self._io.__iter__()

    def __next__(self):
        if not self._read:
            self._raise('File is not open for reading')
        return next(self._io)


class StandardStreamWrapper:
    """Wrapper for a system standard stream to be used in open files list.
    """

    def __init__(self, stream_object: TextIO):
        self._stream_object = stream_object
        self.filedes: Optional[int] = None

    def get_object(self) -> TextIO:
        return self._stream_object

    def fileno(self) -> int:
        """Return the file descriptor of the wrapped standard stream."""
        if self.filedes is not None:
            return self.filedes
        raise OSError(errno.EBADF, 'Invalid file descriptor')

    def read(self, n: int = -1) -> bytes:
        return cast(bytes, self._stream_object.read())

    def close(self) -> None:
        """We do not support closing standard streams."""
        pass

    def is_stream(self) -> bool:
        return True


class FakeDirWrapper:
    """Wrapper for a FakeDirectory object to be used in open files list.
    """

    def __init__(self, file_object: FakeDirectory,
                 file_path: AnyString, filesystem: FakeFilesystem):
        self.file_object = file_object
        self.file_path = file_path
        self._filesystem = filesystem
        self.filedes: Optional[int] = None

    def get_object(self) -> FakeDirectory:
        """Return the FakeFile object that is wrapped by the current instance.
        """
        return self.file_object

    def fileno(self) -> int:
        """Return the file descriptor of the file object."""
        if self.filedes is not None:
            return self.filedes
        raise OSError(errno.EBADF, 'Invalid file descriptor')

    def close(self) -> None:
        """Close the directory."""
        assert self.filedes is not None
        self._filesystem._close_open_file(self.filedes)


class FakePipeWrapper:
    """Wrapper for a read or write descriptor of a real pipe object to be
    used in open files list.
    """

    def __init__(self, filesystem: FakeFilesystem,
                 fd: int, can_write: bool, mode: str = ''):
        self._filesystem = filesystem
        self.fd = fd  # the real file descriptor
        self.can_write = can_write
        self.file_object = None
        self.filedes: Optional[int] = None
        self.real_file = None
        if mode:
            self.real_file = open(fd, mode)

    def __enter__(self) -> 'FakePipeWrapper':
        """To support usage of this fake pipe with the 'with' statement."""
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 exc_tb: Optional[TracebackType]
                 ) -> None:
        """To support usage of this fake pipe with the 'with' statement."""
        self.close()

    def get_object(self) -> None:
        return self.file_object

    def fileno(self) -> int:
        """Return the fake file descriptor of the pipe object."""
        if self.filedes is not None:
            return self.filedes
        raise OSError(errno.EBADF, 'Invalid file descriptor')

    def read(self, numBytes: int = -1) -> bytes:
        """Read from the real pipe."""
        if self.real_file:
            return self.real_file.read(numBytes)
        return os.read(self.fd, numBytes)

    def flush(self) -> None:
        """Flush the real pipe?"""
        pass

    def write(self, contents: bytes) -> int:
        """Write to the real pipe."""
        if self.real_file:
            return self.real_file.write(contents)
        return os.write(self.fd, contents)

    def close(self) -> None:
        """Close the pipe descriptor."""
        assert self.filedes is not None
        open_files = self._filesystem.open_files[self.filedes]
        assert open_files is not None
        open_files.remove(self)
        if self.real_file:
            self.real_file.close()
        else:
            os.close(self.fd)

    def readable(self) -> bool:
        """The pipe end can either be readable or writable."""
        return not self.can_write

    def writable(self) -> bool:
        """The pipe end can either be readable or writable."""
        return self.can_write

    def seekable(self) -> bool:
        """A pipe is not seekable."""
        return False


class FakeFileOpen:
    """Faked `file()` and `open()` function replacements.

    Returns FakeFile objects in a FakeFilesystem in place of the `file()`
    or `open()` function.
    """
    __name__ = 'FakeFileOpen'

    def __init__(self, filesystem: FakeFilesystem,
                 delete_on_close: bool = False, raw_io: bool = False):
        """
        Args:
          filesystem:  FakeFilesystem used to provide file system information
          delete_on_close:  optional boolean, deletes file on close()
        """
        self.filesystem = filesystem
        self._delete_on_close = delete_on_close
        self.raw_io = raw_io

    def __call__(self, *args: Any, **kwargs: Any) -> AnyFileWrapper:
        """Redirects calls to file() or open() to appropriate method."""
        return self.call(*args, **kwargs)

    def call(self, file_: Union[AnyStr, int],
             mode: str = 'r',
             buffering: int = -1,
             encoding: Optional[str] = None,
             errors: Optional[str] = None,
             newline: Optional[str] = None,
             closefd: bool = True,
             opener: Any = None,
             open_modes: Optional[_OpenModes] = None) -> AnyFileWrapper:
        """Return a file-like object with the contents of the target
        file object.

        Args:
            file_: Path to target file or a file descriptor.
            mode: Additional file modes (all modes in `open()` are supported).
            buffering: the buffer size used for writing. Data will only be
                flushed if buffer size is exceeded. The default (-1) uses a
                system specific default buffer size. Text line mode (e.g.
                buffering=1 in text mode) is not supported.
            encoding: The encoding used to encode unicode strings / decode
                bytes.
            errors: (str) Defines how encoding errors are handled.
            newline: Controls universal newlines, passed to stream object.
            closefd: If a file descriptor rather than file name is passed,
                and this is set to `False`, then the file descriptor is kept
                open when file is closed.
            opener: an optional function object that will be called with
                `file_` and the open flags (derived from `mode`) and returns
                a file descriptor.
            open_modes: Modes for opening files if called from low-level API.

        Returns:
            A file-like object containing the contents of the target file.

        Raises:
            OSError depending on Python version / call mode:
                - if the target object is a directory
                - on an invalid path
                - if the file does not exist when it should
                - if the file exists but should not
                - if permission is denied
            ValueError: for an invalid mode or mode combination
        """
        binary = 'b' in mode

        if binary and encoding:
            raise ValueError("binary mode doesn't take an encoding argument")

        newline, open_modes = self._handle_file_mode(mode, newline, open_modes)

        # the pathlib opener is defined in a Path instance that may not be
        # patched under some circumstances; as it just calls standard open(),
        # we may ignore it, as it would not change the behavior
        if opener is not None and opener.__module__ != 'pathlib':
            # opener shall return a file descriptor, which will be handled
            # here as if directly passed
            file_ = opener(file_, self._open_flags_from_open_modes(open_modes))

        file_object, file_path, filedes, real_path = self._handle_file_arg(
            file_)
        if file_object is None and file_path is None:
            # file must be a fake pipe wrapper, find it...
            if (filedes is None or
                    len(self.filesystem.open_files) <= filedes or
                    not self.filesystem.open_files[filedes]):
                raise OSError(errno.EBADF, 'invalid pipe file descriptor')
            wrappers = self.filesystem.open_files[filedes]
            assert wrappers is not None
            existing_wrapper = wrappers[0]
            assert isinstance(existing_wrapper, FakePipeWrapper)
            wrapper = FakePipeWrapper(self.filesystem, existing_wrapper.fd,
                                      existing_wrapper.can_write, mode)
            file_des = self.filesystem._add_open_file(wrapper)
            wrapper.filedes = file_des
            return wrapper

        assert file_path is not None
        if not filedes:
            closefd = True

        if (not opener and open_modes.must_not_exist and
                (file_object or self.filesystem.islink(file_path) and
                 not self.filesystem.is_windows_fs)):
            self.filesystem.raise_os_error(errno.EEXIST, file_path)

        assert real_path is not None
        file_object = self._init_file_object(file_object,
                                             file_path, open_modes,
                                             real_path)

        if S_ISDIR(file_object.st_mode):
            if self.filesystem.is_windows_fs:
                self.filesystem.raise_os_error(errno.EACCES, file_path)
            else:
                self.filesystem.raise_os_error(errno.EISDIR, file_path)

        # If you print obj.name, the argument to open() must be printed.
        # Not the abspath, not the filename, but the actual argument.
        file_object.opened_as = file_path
        if open_modes.truncate:
            current_time = now()
            file_object.st_mtime = current_time
            if not self.filesystem.is_windows_fs:
                file_object.st_ctime = current_time

        fakefile = FakeFileWrapper(file_object,
                                   file_path,
                                   update=open_modes.can_write,
                                   read=open_modes.can_read,
                                   append=open_modes.append,
                                   delete_on_close=self._delete_on_close,
                                   filesystem=self.filesystem,
                                   newline=newline,
                                   binary=binary,
                                   closefd=closefd,
                                   encoding=encoding,
                                   errors=errors,
                                   buffering=buffering,
                                   raw_io=self.raw_io)
        if filedes is not None:
            fakefile.filedes = filedes
            # replace the file wrapper
            open_files_list = self.filesystem.open_files[filedes]
            assert open_files_list is not None
            open_files_list.append(fakefile)
        else:
            fakefile.filedes = self.filesystem._add_open_file(fakefile)
        return fakefile

    @staticmethod
    def _open_flags_from_open_modes(open_modes: _OpenModes) -> int:
        flags = 0
        if open_modes.can_read and open_modes.can_write:
            flags |= os.O_RDWR
        elif open_modes.can_read:
            flags |= os.O_RDONLY
        elif open_modes.can_write:
            flags |= os.O_WRONLY

        if open_modes.append:
            flags |= os.O_APPEND
        if open_modes.truncate:
            flags |= os.O_TRUNC
        if not open_modes.must_exist and open_modes.can_write:
            flags |= os.O_CREAT
        if open_modes.must_not_exist and open_modes.can_write:
            flags |= os.O_EXCL
        return flags

    def _init_file_object(self, file_object: Optional[FakeFile],
                          file_path: AnyStr,
                          open_modes: _OpenModes,
                          real_path: AnyString) -> FakeFile:
        if file_object:
            if (not is_root() and
                    ((open_modes.can_read and
                      not file_object.st_mode & PERM_READ)
                     or (open_modes.can_write and
                         not file_object.st_mode & PERM_WRITE))):
                self.filesystem.raise_os_error(errno.EACCES, file_path)
            if open_modes.can_write:
                if open_modes.truncate:
                    file_object.set_contents('')
        else:
            if open_modes.must_exist:
                self.filesystem.raise_os_error(errno.ENOENT, file_path)
            if self.filesystem.islink(file_path):
                link_object = self.filesystem.resolve(file_path,
                                                      follow_symlinks=False)
                assert link_object.contents is not None
                target_path = cast(AnyStr, link_object.contents)
            else:
                target_path = file_path
            if self.filesystem.ends_with_path_separator(target_path):
                error = (
                    errno.EINVAL if self.filesystem.is_windows_fs
                    else errno.ENOENT if self.filesystem.is_macos
                    else errno.EISDIR
                )
                self.filesystem.raise_os_error(error, file_path)
            file_object = self.filesystem.create_file_internally(
                real_path, create_missing_dirs=False,
                apply_umask=True)
        return file_object

    def _handle_file_arg(self, file_: Union[AnyStr, int]) -> Tuple[
            Optional[FakeFile], Optional[AnyStr],
            Optional[int], Optional[AnyStr]]:
        file_object = None
        if isinstance(file_, int):
            # opening a file descriptor
            filedes: int = file_
            wrapper = self.filesystem.get_open_file(filedes)
            if isinstance(wrapper, FakePipeWrapper):
                return None, None, filedes, None
            if isinstance(wrapper, FakeFileWrapper):
                self._delete_on_close = wrapper.delete_on_close
            file_object = cast(FakeFile, self.filesystem.get_open_file(
                filedes).get_object())
            assert file_object is not None
            path = file_object.name
            return file_object, cast(AnyStr, path), filedes, cast(AnyStr, path)

        # open a file file by path
        file_path = cast(AnyStr, file_)
        if file_path == self.filesystem.dev_null.name:
            file_object = self.filesystem.dev_null
            real_path = file_path
        else:
            real_path = self.filesystem.resolve_path(file_path)
            if self.filesystem.exists(file_path):
                file_object = self.filesystem.get_object_from_normpath(
                    real_path, check_read_perm=False)
        return file_object, file_path, None, real_path

    def _handle_file_mode(
            self, mode: str,
            newline: Optional[str],
            open_modes: Optional[_OpenModes]) -> Tuple[Optional[str],
                                                       _OpenModes]:
        orig_modes = mode  # Save original modes for error messages.
        # Normalize modes. Handle 't' and 'U'.
        if (('b' in mode and 't' in mode) or
                (sys.version_info > (3, 10) and 'U' in mode)):
            raise ValueError('Invalid mode: ' + mode)
        mode = mode.replace('t', '').replace('b', '')
        mode = mode.replace('rU', 'r').replace('U', 'r')
        if not self.raw_io:
            if mode not in _OPEN_MODE_MAP:
                raise ValueError('Invalid mode: %r' % orig_modes)
            open_modes = _OpenModes(*_OPEN_MODE_MAP[mode])
        assert open_modes is not None
        return newline, open_modes


def _run_doctest() -> TestResults:
    import doctest
    import pyfakefs
    return doctest.testmod(pyfakefs.fake_filesystem)


if __name__ == '__main__':
    _run_doctest()
