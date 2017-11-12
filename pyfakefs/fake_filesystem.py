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
  * FakeFile:  Provides the appearance of a real file.
  * FakeDirectory: Provides the appearance of a real directory.
  * FakeFilesystem:  Provides the appearance of a real directory hierarchy.
  * FakeOsModule:  Uses FakeFilesystem to provide a fake os module replacement.
  * FakePathModule:  Faked os.path module replacement.
  * FakeFileOpen:  Faked file() and open() function replacements.

:Usage:

>>> from pyfakefs import fake_filesystem
>>> filesystem = fake_filesystem.FakeFilesystem()
>>> os_module = fake_filesystem.FakeOsModule(filesystem)
>>> pathname = '/a/new/dir/new-file'

Create a new file object, creating parent directory objects as needed:

>>> os_module.path.exists(pathname)
False
>>> new_file = filesystem.CreateFile(pathname)

File objects can't be overwritten:

>>> os_module.path.exists(pathname)
True
>>> try:
...   filesystem.CreateFile(pathname)
... except IOError as e:
...   assert e.errno == errno.EEXIST, 'unexpected errno: %d' % e.errno
...   assert e.strerror == 'File already exists in fake filesystem'

Remove a file object:

>>> filesystem.RemoveObject(pathname)
>>> os_module.path.exists(pathname)
False

Create a new file object at the previous path:

>>> beatles_file = filesystem.CreateFile(pathname,
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

>>> os_module.listdir(pathname)  #doctest: +NORMALIZE_WHITESPACE
Traceback (most recent call last):
  File "fake_filesystem.py", line 291, in listdir
    raise OSError(errno.ENOTDIR,
OSError: [Errno 20] Fake os module: not a directory: '/a/new/dir/new-file'

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
import codecs
import errno
import heapq
import io
import locale
import platform
import os
import sys
import time
import warnings

from collections import namedtuple

import stat
from copy import copy

__pychecker__ = 'no-reimportself'

__version__ = '3.3'

PERM_READ = 0o400  # Read permission bit.
PERM_WRITE = 0o200  # Write permission bit.
PERM_EXE = 0o100  # Execute permission bit.
PERM_DEF = 0o777  # Default permission bits.
PERM_DEF_FILE = 0o666  # Default permission bits (regular file)
PERM_ALL = 0o7777  # All permission bits.

_OpenModes = namedtuple(
    'open_modes',
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
}

if sys.version_info[0] < 3 and sys.platform != 'win32':
    _OPEN_MODE_MAP['rw'] = (True, True, True, False, False, False)

if sys.version_info >= (3, 3):
    _OPEN_MODE_MAP['x'] = (False, False, True, False, False, True)
    _OPEN_MODE_MAP['x+'] = (False, True, True, False, False, True)

if sys.platform.startswith('linux'):
    # on newer Linux system, the default maximum recursion depth is 40
    # we ignore older systems here
    _MAX_LINK_DEPTH = 40
else:
    # on MacOS and Windows, the maximum recursion depth is 32
    _MAX_LINK_DEPTH = 32

FAKE_PATH_MODULE_DEPRECATION = ('Do not instantiate a FakePathModule directly; '
                                'let FakeOsModule instantiate it.  See the '
                                'FakeOsModule docstring for details.')

NR_STD_STREAMS = 3


def is_int_type(val):
    int_types = (int, long) if sys.version_info[0] < 3 else int  # pylint: disable=undefined-variable
    return isinstance(val, int_types)


class FakeLargeFileIoException(Exception):
    """Exception thrown on unsupported operations for fake large files.
    Fake large files have a size with no real content.
    """

    def __init__(self, file_path):
        super(FakeLargeFileIoException, self).__init__(
            'Read and write operations not supported for '
            'fake large file: %s' % file_path)


def CopyModule(old):
    """Recompiles and creates new module object."""
    saved = sys.modules.pop(old.__name__, None)
    new = __import__(old.__name__)
    sys.modules[old.__name__] = saved
    return new


class _FakeStatResult(object):
    """Mimics os.stat_result for use as return type of `stat()` and similar.
    This is needed as `os.stat_result` has no possibility to set
    nanosecond times directly.
    """
    long_type = long if sys.version_info[0] == 2 else int

    def __init__(self, is_windows, initial_time=None):
        self.use_float = FakeOsModule.stat_float_times
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

    def __eq__(self, other):
        return (
            isinstance(other, _FakeStatResult) and
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
        """Return a copy where the float usage is hard-coded to mimic the behavior
        of the real os.stat_result.
        """
        use_float = self.use_float()
        stat_result = copy(self)
        stat_result.use_float = lambda: use_float
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

    @property
    def st_ctime(self):
        """Return the creation time in seconds."""
        ctime = self._st_ctime_ns / 1e9
        return ctime if self.use_float() else int(ctime)

    @property
    def st_atime(self):
        """Return the access time in seconds."""
        atime = self._st_atime_ns / 1e9
        return atime if self.use_float() else int(atime)

    @property
    def st_mtime(self):
        """Return the modification time in seconds."""
        mtime = self._st_mtime_ns / 1e9
        return mtime if self.use_float() else int(mtime)

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
        if self.st_mode & stat.S_IFLNK == stat.S_IFLNK and self.is_windows:
            return 0
        return self._st_size

    @st_size.setter
    def st_size(self, val):
        self._st_size = val

    def __getitem__(self, item):
        """Implement item access to mimic `os.stat_result` behavior."""
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


class FakeFile(object):
    """Provides the appearance of a real file.

    Attributes currently faked out:
        st_mode: user-specified, otherwise S_IFREG
        st_ctime: the time.time() timestamp of the file change time (updated
        each time a file's attributes is modified).
        st_atime: the time.time() timestamp when the file was last accessed.
        st_mtime: the time.time() timestamp when the file was last modified.
        st_size: the size of the file
        st_nlink: the number of hard links to the file
        st_ino: the inode number - a unique number identifying the file
        st_dev: a unique number identifying the (fake) file system device the file belongs to

    Other attributes needed by os.stat are assigned default value of None
    these include: st_uid, st_gid
    """

    def __init__(self, name, st_mode=stat.S_IFREG | PERM_DEF_FILE,
                 contents=None, filesystem=None, encoding=None, errors=None):
        """init.

        Args:
            name: Name of the file/directory, without parent path information
            st_mode: The stat.S_IF* constant representing the file type (i.e.
                stat.S_IFREG, stat.S_IFDIR)
            contents: The contents of the filesystem object; should be a string
                or byte object for regular files, and a list of other
                FakeFile or FakeDirectory objects for FakeDirectory objects
            filesystem: The fake filesystem where the file is created.
            encoding: If contents is a unicode string, the encoding used
                for serialization.
            errors: The error mode used for encoding/decoding errors.
        """
        # to be backwards compatible regarding argument order, we raise on None
        if filesystem is None:
            raise ValueError('filesystem shall not be None')
        self.filesystem = filesystem

        self.name = name
        self.stat_result = _FakeStatResult(
            filesystem.is_windows_fs, time.time())
        self.stat_result.st_mode = st_mode
        self.encoding = encoding
        self.errors = errors or 'strict'
        self._byte_contents = self._encode_contents(contents)
        self.stat_result.st_size = (
            len(self._byte_contents) if self._byte_contents is not None else 0)
        self.epoch = 0
        self.parent_dir = None

    @property
    def byte_contents(self):
        return self._byte_contents

    @property
    def contents(self):
        """Return the contents as string with the original encoding."""
        if sys.version_info[0] > 2 and isinstance(self.byte_contents, bytes):
            return self.byte_contents.decode(
                self.encoding or locale.getpreferredencoding(False),
                errors=self.errors)
        return self.byte_contents

    def SetLargeFileSize(self, st_size):
        """Sets the self.st_size attribute and replaces self.content with None.

        Provided specifically to simulate very large files without regards
        to their content (which wouldn't fit in memory).
        Note that read/write operations with such a file raise FakeLargeFileIoException.

        Args:
          st_size: (int) The desired file size

        Raises:
          IOError: if the st_size is not a non-negative integer,
                   or if st_size exceeds the available file system space
        """
        self._check_positive_int(st_size)
        if self.st_size:
            self.SetSize(0)
        self.filesystem.ChangeDiskUsage(st_size, self.name, self.st_dev)
        self.st_size = st_size
        self._byte_contents = None

    def _check_positive_int(self, size):
        # the size should be an positive integer value
        int_types = (int, long) if sys.version_info[0] == 2 else int  # pylint: disable=undefined-variable
        if not isinstance(size, int_types) or size < 0:
            raise IOError(errno.ENOSPC,
                          'Fake file object: size must be a non-negative integer, but is %s'
                          % size, self.name)

    def IsLargeFile(self):
        """Return True if this file was initialized with size but no contents."""
        return self._byte_contents is None

    def _encode_contents(self, contents):
        # pylint: disable=undefined-variable
        if sys.version_info[0] > 2 and isinstance(contents, str):
            contents = bytes(contents, self.encoding or locale.getpreferredencoding(False), self.errors)
        elif sys.version_info[0] == 2 and isinstance(contents, unicode):
            contents = contents.encode(self.encoding or locale.getpreferredencoding(False), self.errors)
        return contents

    def _set_initial_contents(self, contents):
        """Sets the file contents and size.
           Called internally after initial file creation.

        Args:
          contents: string, new content of file.
        Raises:
          IOError: if the st_size is not a non-negative integer,
                   or if st_size exceeds the available file system space
        """
        contents = self._encode_contents(contents)
        st_size = len(contents)

        if self._byte_contents:
            self.SetSize(0)
        current_size = self.st_size or 0
        self.filesystem.ChangeDiskUsage(st_size - current_size, self.name, self.st_dev)
        self._byte_contents = contents
        self.st_size = st_size
        self.epoch += 1

    def SetContents(self, contents, encoding=None):
        """Sets the file contents and size and increases the modification time.

        Args:
          contents: (str, bytes, unicode) new content of file.
          encoding: (str) the encoding to be used for writing the contents
                    if they are a unicode string.
                    If not given, the locale preferred encoding is used.

        Raises:
          IOError: if the st_size is not a non-negative integer,
                   or if st_size exceeds the available file system space.
        """
        self.encoding = encoding
        self._set_initial_contents(contents)
        current_time = time.time()
        self.st_ctime = current_time
        self.st_mtime = current_time

    def GetSize(self):
        """Returns the size in bytes of the file contents."""
        return self.st_size

    def GetPath(self):
        """Return the full path of the current object."""
        names = []
        obj = self
        while obj:
            names.insert(0, obj.name)
            obj = obj.parent_dir
        sep = self.filesystem._path_separator(self.name)
        return self.filesystem.NormalizePath(sep.join(names[1:]))

    def SetSize(self, st_size):
        """Resizes file content, padding with nulls if new size exceeds the old.

        Args:
          st_size: The desired size for the file.

        Raises:
          IOError: if the st_size arg is not a non-negative integer
                   or if st_size exceeds the available file system space
        """

        self._check_positive_int(st_size)
        current_size = self.st_size or 0
        self.filesystem.ChangeDiskUsage(st_size - current_size, self.name, self.st_dev)
        if self._byte_contents:
            if st_size < current_size:
                self._byte_contents = self._byte_contents[:st_size]
            else:
                if sys.version_info < (3, 0):
                    self._byte_contents = '%s%s' % (
                        self._byte_contents, '\0' * (st_size - current_size))
                else:
                    self._byte_contents += b'\0' * (st_size - current_size)
        self.st_size = st_size
        self.epoch += 1

    def SetATime(self, st_atime):
        """Set the self.st_atime attribute.

        Args:
          st_atime: The desired access time.
        """
        self.st_atime = st_atime

    def SetMTime(self, st_mtime):
        """Set the self.st_mtime attribute.

        Args:
          st_mtime: The desired modification time.
        """
        self.st_mtime = st_mtime

    def SetCTime(self, st_ctime):
        """Set the self.st_ctime attribute.

        Args:
          st_ctime: The desired creation time.
        """
        self.st_ctime = st_ctime

    def __getattr__(self, item):
        """Forward some properties to stat_result."""
        return getattr(self.stat_result, item)

    def __setattr__(self, key, value):
        """Forward some properties to stat_result."""
        if key in ('st_mode', 'st_ino', 'st_dev', 'st_nlink', 'st_uid', 'st_gid',
                   'st_size', 'st_atime', 'st_mtime', 'st_ctime',
                   'st_atime_ns', 'st_mtime_ns', 'st_ctime_ns'):
            return setattr(self.stat_result, key, value)
        return super(FakeFile, self).__setattr__(key, value)

    def __str__(self):
        return '%s(%o)' % (self.name, self.st_mode)

    def SetIno(self, st_ino):
        """Set the self.st_ino attribute.
        Note that a unique inode is assigned automatically to a new fake file.
        Using this function does not guarantee uniqueness and should used with caution.

        Args:
          st_ino: (int) The desired inode.
        """
        self.st_ino = st_ino


class FakeFileFromRealFile(FakeFile):
    """Represents a fake file copied from the real file system.
    
    The contents of the file are read on demand only.
    """

    def __init__(self, file_path, filesystem, read_only=True):
        """init.

        Args:
            file_path: path to the existing file.
            filesystem: the fake filesystem where the file is created.
            read_only: if set, the file is treated as read-only, e.g. a write access raises an exception;
                otherwise, writing to the file changes the fake file only as usually.

        Raises:
            OSError: if the file does not exist in the real file system.
        """
        real_stat = os.stat(file_path)
        # for read-only mode, remove the write/executable permission bits
        super(FakeFileFromRealFile, self).__init__(name=os.path.basename(file_path),
                                                   filesystem=filesystem)
        self.stat_result.set_from_stat_result(real_stat)
        if read_only:
            self.st_mode &= 0o777444
        self.file_path = file_path
        self.contents_read = False

    @property
    def byte_contents(self):
        if not self.contents_read:
            self.contents_read = True
            with io.open(self.file_path, 'rb') as f:
                self._byte_contents = f.read()
        # On MacOS and BSD, the above io.open() updates atime on the real file
        self.st_atime = os.stat(self.file_path).st_atime
        return self._byte_contents

    def IsLargeFile(self):
        """The contents are never faked."""
        return False


class FakeDirectory(FakeFile):
    """Provides the appearance of a real directory."""

    def __init__(self, name, perm_bits=PERM_DEF, filesystem=None):
        """init.

        Args:
          name:  name of the file/directory, without parent path information
          perm_bits: permission bits. defaults to 0o777.
          filesystem: if set, the fake filesystem where the directory is created
        """
        FakeFile.__init__(self, name, stat.S_IFDIR | perm_bits, {}, filesystem=filesystem)
        # directories have the link count of contained entries, inclusing '.' and '..'
        self.st_nlink += 1

    def SetContents(self, contents, encoding=None):
        if self.filesystem.is_windows_fs and sys.version_info[0] > 2:
            error_class = OSError
        else:
            error_class = IOError
        raise error_class(errno.EISDIR, 'Trying to write to directory')

    @property
    def contents(self):
        """Return the list of contained directory entries."""
        return self.byte_contents

    @property
    def ordered_dirs(self):
        """Return the list of contained directory entry names ordered by creation order."""
        return [item[0] for item in sorted(
            self.byte_contents.items(), key=lambda entry: entry[1].st_ino)]

    def AddEntry(self, path_object):
        """Adds a child FakeFile to this directory.

        Args:
            path_object:  FakeFile instance to add as a child of this directory.

        Raises:
            OSError: if the directory has no write permission (Posix only)
            OSError: if the file or directory to be added already exists
        """
        if not self.st_mode & PERM_WRITE and not self.filesystem.is_windows_fs:
            exception = IOError if sys.version_info[0] < 3 else OSError
            raise exception(errno.EACCES, 'Permission Denied', self.GetPath())

        if path_object.name in self.contents:
            raise OSError(errno.EEXIST,
                          'Object already exists in fake filesystem',
                          self.GetPath())

        self.contents[path_object.name] = path_object
        path_object.parent_dir = self
        self.st_nlink += 1
        path_object.st_nlink += 1
        path_object.st_dev = self.st_dev
        if path_object.st_nlink == 1:
            self.filesystem.ChangeDiskUsage(path_object.GetSize(), path_object.name, self.st_dev)

    def GetEntry(self, pathname_name):
        """Retrieves the specified child file or directory entry.

        Args:
            pathname_name: The basename of the child object to retrieve.

        Returns:
            The fake file or directory object.

        Raises:
            KeyError: if no child exists by the specified name.
        """
        pathname_name = self._normalized_entryname(pathname_name)
        return self.contents[pathname_name]

    def _normalized_entryname(self, pathname_name):
        if not self.filesystem.is_case_sensitive:
            matching_names = [name for name in self.contents
                              if name.lower() == pathname_name.lower()]
            if matching_names:
                pathname_name = matching_names[0]
        return pathname_name

    def RemoveEntry(self, pathname_name, recursive=True):
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
        entry = self.GetEntry(pathname_name)
        if self.filesystem.is_windows_fs:
            if entry.st_mode & PERM_WRITE == 0:
                raise OSError(errno.EACCES, 'Trying to remove object '
                                            'without write permission',
                              pathname_name)
            if self.filesystem.HasOpenFile(entry):
                raise OSError(errno.EACCES, 'Trying to remove an open file',
                              pathname_name)
        else:
            if self.st_mode & (PERM_WRITE | PERM_EXE) != PERM_WRITE | PERM_EXE:
                raise OSError(errno.EACCES, 'Trying to remove object '
                                            'without parent dir permission',
                              pathname_name)

        if recursive and isinstance(entry, FakeDirectory):
            while entry.contents:
                entry.RemoveEntry(list(entry.contents)[0])
        elif entry.st_nlink == 1:
            self.filesystem.ChangeDiskUsage(-entry.GetSize(), pathname_name, entry.st_dev)

        self.st_nlink -= 1
        entry.st_nlink -= 1
        assert entry.st_nlink >= 0

        del self.contents[pathname_name]

    def GetSize(self):
        """Return the total size of all files contained in this directory tree.
        """
        return sum([item[1].GetSize() for item in self.contents.items()])

    def HasParentObject(self, dir_object):
        """Return `True` if dir_object is a direct or indirect parent directory,
        or if both are the same object."""
        obj = self
        while obj:
            if obj == dir_object:
                return True
            obj = obj.parent_dir
        return False

    def __str__(self):
        description = super(FakeDirectory, self).__str__() + ':\n'
        for item in self.contents:
            item_desc = self.contents[item].__str__()
            for line in item_desc.split('\n'):
                if line:
                    description = description + '  ' + line + '\n'
        return description


class FakeDirectoryFromRealDirectory(FakeDirectory):
    """Represents a fake directory copied from the real file system.
    
    The contents of the directory are read on demand only.
    """

    def __init__(self, dir_path, filesystem, read_only):
        """init.

        Args:
            dir_path: Full directory path.
            filesystem: The fake filesystem where the directory is created.
            read_only: If set, all files under the directory are treated
                as read-only, e.g. a write access raises an exception;
                otherwise, writing to the files changes the fake files
                only as usually.
                
        Raises:
            OSError: if the directory does not exist in the real file system
        """
        real_stat = os.stat(dir_path)
        super(FakeDirectoryFromRealDirectory, self).__init__(
            name=os.path.split(dir_path)[1],
            perm_bits=real_stat.st_mode,
            filesystem=filesystem)

        self.st_ctime = real_stat.st_ctime
        self.st_atime = real_stat.st_atime
        self.st_mtime = real_stat.st_mtime
        self.st_gid = real_stat.st_gid
        self.st_uid = real_stat.st_uid
        self.dir_path = dir_path
        self.read_only = read_only
        self.contents_read = False

    @property
    def contents(self):
        """Return the list of contained directory entries, loading them
        if not already loaded."""
        if not self.contents_read:
            self.contents_read = True
            self.filesystem.add_real_paths(
                [os.path.join(self.dir_path, entry) for entry in os.listdir(self.dir_path)],
                read_only=self.read_only)
        return self.byte_contents

    def GetSize(self):
        # we cannot get the size until the contents are loaded
        if not self.contents_read:
            return 0
        return super(FakeDirectoryFromRealDirectory, self).GetSize()


class FakeFilesystem(object):
    """Provides the appearance of a real directory tree for unit testing.

    Attributes:
        path_separator: The path separator, corresponds to `os.path.sep`.
        alternative_path_separator: Corresponds to `os.path.altsep`.
        is_windows_fs: `True` in a Windows file system, `False` otherwise.
        is_case_sensitive: `True` if a case-sensitive file system is assumed.
        root: The root `FakeDirectory` entry of the file system.
        cwd: The current working directory path.
        umask: The umask used for newly created files, see `os.umask`.
    """

    def __init__(self, path_separator=os.path.sep, total_size=None):
        """init.

        Args:
            path_separator:  optional substitute for os.path.sep
            total_size: if not None, the total size in bytes of the
            root filesystem.

        Example usage to emulate real file systems:
            filesystem = FakeFilesystem(
                alt_path_separator='/' if _is_windows else None)

        """
        self.path_separator = path_separator
        self.alternative_path_separator = os.path.altsep
        if path_separator != os.sep:
            self.alternative_path_separator = None

        # is_windows_fs can be used to test the behavior of pyfakefs under Windows fs
        # on non-Windows systems and vice verse
        # is it used to support drive letters, UNC path and some other Windows-specific features
        self.is_windows_fs = sys.platform == 'win32'

        # can be used to test some Darwin-specific behavior under other systems
        self.is_macos = sys.platform == 'darwin'

        # is_case_sensitive can be used to test pyfakefs for case-sensitive
        # file systems on non-case-sensitive systems and vice verse
        self.is_case_sensitive = not (self.is_windows_fs or self.is_macos)

        self.root = FakeDirectory(self.path_separator, filesystem=self)
        self.cwd = self.root.name
        # We can't query the current value without changing it:
        self.umask = os.umask(0o22)
        os.umask(self.umask)
        # A list of open file objects. Their position in the list is their
        # file descriptor number
        self.open_files = []
        # A heap containing all free positions in self.open_files list
        self._free_fd_heap = []
        # last used numbers for inodes (st_ino) and devices (st_dev)
        self._last_ino = 0
        self._last_dev = 0
        self.mount_points = {}
        self.AddMountPoint(self.root.name, total_size)
        self._add_standard_streams()

    def raise_os_error(self, errno, winerror, message, filename=''):
        if (sys.platform == 'win32' and self.is_windows_fs and
                    sys.version_info[0] < 3):
            raise WindowsError(winerror, message, filename)
        raise OSError(errno, message, filename)

    @staticmethod
    def _matching_string(matched, string):
        """Return the string as byte or unicode depending 
        on the type of matched, assuming string is an ASCII string.
        """
        if string is None:
            return string
        if sys.version_info < (3, ):
            if isinstance(matched, unicode):
                return unicode(string)
        else:
            if isinstance(matched, bytes) and isinstance(string, str):
                return string.encode(locale.getpreferredencoding(False))
        return string

    def _path_separator(self, path):
        """Return the path separator as the same type as path"""
        return self._matching_string(path, self.path_separator)

    def _alternative_path_separator(self, path):
        """Return the alternative path separator as the same type as path"""
        return self._matching_string(path, self.alternative_path_separator)

    def _IsLinkSupported(self):
        # Python 3.2 supports links in Windows
        return not self.is_windows_fs or sys.version_info >= (3, 2)

    def AddMountPoint(self, path, total_size=None):
        """Add a new mount point for a filesystem device.
        The mount point gets a new unique device number.

        Args:
            path: The root path for the new mount path.

            total_size: The new total size of the added filesystem device
                in bytes. Defaults to infinite size.

        Returns:
            The newly created mount point dict.

        Raises:
            OSError: if trying to mount an existing mount point again.
        """
        path = self.NormalizePath(path)
        if path in self.mount_points:
            raise OSError(errno.EEXIST,
                          'Mount point cannot be added twice', path)
        self._last_dev += 1
        self.mount_points[path] = {
            'idev': self._last_dev, 'total_size': total_size, 'used_size': 0
        }
        # special handling for root path: has been created before
        root_dir = self.root if path == self.root.name else self.CreateDirectory(path)
        root_dir.st_dev = self._last_dev
        return self.mount_points[path]

    def _AutoMountDriveIfNeeded(self, path, force=False):
        if self.is_windows_fs and (force or not self._MountPointForPath(path)):
            drive = self.SplitDrive(path)[0]
            if drive:
                return self.AddMountPoint(path=drive)

    def _MountPointForPath(self, path):
        def to_str(string):
            """Convert the str, unicode or byte object to a str
            using the default encoding."""
            if string is None or isinstance(string, str):
                return string
            if sys.version_info < (3, 0):
                return string.encode(locale.getpreferredencoding(False))
            else:
                return string.decode(locale.getpreferredencoding(False))

        path = self.NormalizePath(self.NormalizeCase(path))
        if path in self.mount_points:
            return self.mount_points[path]
        mount_path = self._matching_string(path, '')
        drive = self.SplitDrive(path)[:1]
        for root_path in self.mount_points:
            root_path = self._matching_string(path, root_path)
            if drive and not root_path.startswith(drive):
                continue
            if path.startswith(root_path) and len(root_path) > len(mount_path):
                mount_path = root_path
        if mount_path:
            return self.mount_points[to_str(mount_path)]
        mount_point = self._AutoMountDriveIfNeeded(path, force=True)
        assert mount_point
        return mount_point

    def _MountPointForDevice(self, idev):
        for mount_point in self.mount_points.values():
            if mount_point['idev'] == idev:
                return mount_point

    def GetDiskUsage(self, path=None):
        """Return the total, used and free disk space in bytes as named tuple,
        or placeholder values simulating unlimited space if not set.
        Note: This matches the return value of shutil.disk_usage().

        Args:
            path: The disk space is returned for the file system device where
                path resides.
                Defaults to the root path (e.g. '/' on Unix systems).
        """
        DiskUsage = namedtuple('usage', 'total, used, free')
        if path is None:
            mount_point = self.mount_points[self.root.name]
        else:
            mount_point = self._MountPointForPath(path)
        if mount_point and mount_point['total_size'] is not None:
            return DiskUsage(mount_point['total_size'], mount_point['used_size'],
                             mount_point['total_size'] - mount_point['used_size'])
        return DiskUsage(1024 * 1024 * 1024 * 1024, 0, 1024 * 1024 * 1024 * 1024)

    def SetDiskUsage(self, total_size, path=None):
        """Changes the total size of the file system, preserving the used space.
        Example usage: set the size of an auto-mounted Windows drive.

        Args:
            total_size: The new total size of the filesystem in bytes.

            path: The disk space is changed for the file system device where
                path resides.
                Defaults to the root path (e.g. '/' on Unix systems).

        Raises:
            IOError: if the new space is smaller than the used size.
        """
        if path is None:
            path = self.root.name
        mount_point = self._MountPointForPath(path)
        if mount_point['total_size'] is not None and mount_point['used_size'] > total_size:
            raise IOError(errno.ENOSPC,
                          'Fake file system: cannot change size to %r bytes - '
                          'used space is larger' % total_size, path)
        mount_point['total_size'] = total_size

    def ChangeDiskUsage(self, usage_change, file_path, st_dev):
        """Change the used disk space by the given amount.

        Args:
            usage_change: Number of bytes added to the used space.
                If negative, the used space will be decreased.

            file_path: The path of the object needing the disk space.

            st_dev: The device ID for the respective file system.

        Raises:
            IOError: if usage_change exceeds the free file system space
        """
        mount_point = self._MountPointForDevice(st_dev)
        if mount_point:
            total_size = mount_point['total_size']
            if total_size is not None:
                if total_size - mount_point['used_size'] < usage_change:
                    raise IOError(errno.ENOSPC,
                                  'Fake file system: disk is full, '
                                  'failed to add %r bytes'
                                  % usage_change, file_path)
            mount_point['used_size'] += usage_change

    def GetStat(self, entry_path, follow_symlinks=True):
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
            file_object = self.ResolveObject(
                entry_path, follow_symlinks, allow_fd=True)
            return file_object.stat_result.copy()
        except IOError as io_error:
            self.raise_os_error(io_error.errno, io_error.errno,
                                io_error.strerror, entry_path)

    def ChangeMode(self, path, mode, follow_symlinks=True):
        """Change the permissions of a file as encoded in integer mode.

        Args:
            path: (str) Path to the file.
            mode: (int) Permissions.
            follow_symlinks: If `False` and `path` points to a symlink,
                the link itself is affected instead of the linked object.
        """
        try:
            file_object = self.ResolveObject(path, follow_symlinks, allow_fd=True)
        except IOError as io_error:
            if io_error.errno == errno.ENOENT:
                raise OSError(errno.ENOENT,
                              'No such file or directory in fake filesystem',
                              path)
            raise
        if self.is_windows_fs:
            if mode & PERM_WRITE:
                file_object.st_mode = file_object.st_mode | 0o222
            else:
                file_object.st_mode = file_object.st_mode & 0o777555
        else:
            file_object.st_mode = ((file_object.st_mode & ~PERM_ALL) |
                                   (mode & PERM_ALL))
        file_object.st_ctime = time.time()

    def UpdateTime(self, path, times=None, ns=None, follow_symlinks=True):
        """Change the access and modified times of a file.

        Args:
            path: (str) Path to the file.
            times: 2-tuple of int or float numbers, of the form (atime, mtime) 
                which is used to set the access and modified times in seconds. 
                If None, both times are set to the current time.
            ns: 2-tuple of int numbers, of the form (atime, mtime)  which is 
                used to set the access and modified times in nanoseconds. 
                If None, both times are set to the current time.
                New in Python 3.3.
            follow_symlinks: If `False` and entry_path points to a symlink, 
                the link itself is queried instead of the linked object. 
                New in Python 3.3.
    
            Raises:
                TypeError: If anything other than the expected types is 
                    specified in the passed `times` or `ns` tuple, 
                    or if the tuple length is not equal to 2.
                ValueError: If both times and ns are specified.
        """
        if times is not None and ns is not None:
            raise ValueError("utime: you may specify either 'times' or 'ns' but not both")
        if times is not None and len(times) != 2:
            raise TypeError("utime: 'times' must be either a tuple of two ints or None")
        if ns is not None and len(ns) != 2:
            raise TypeError("utime: 'ns' must be a tuple of two ints")

        try:
            file_object = self.ResolveObject(path, follow_symlinks, allow_fd=True)
        except IOError as io_error:
            if io_error.errno == errno.ENOENT:
                raise OSError(errno.ENOENT,
                              'No such file or directory in fake filesystem',
                              path)
            raise
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
            current_time = time.time()
            file_object.st_atime = current_time
            file_object.st_mtime = current_time

    def SetIno(self, path, st_ino):
        """Set the self.st_ino attribute of file at 'path'.
        Note that a unique inode is assigned automatically to a new fake file.
        Using this function does not guarantee uniqueness and should used
        with caution.

        Args:
            path: Path to file.
            st_ino: The desired inode.
        """
        self.GetObject(path).SetIno(st_ino)

    def AddOpenFile(self, file_obj):
        """Add file_obj to the list of open files on the filesystem.

        The position in the self.open_files array is the file descriptor number.

        Args:
            file_obj: File object to be added to open files list.

        Returns:
            File descriptor number for the file object.
        """
        if self._free_fd_heap:
            open_fd = heapq.heappop(self._free_fd_heap)
            self.open_files[open_fd] = file_obj
            return open_fd

        self.open_files.append(file_obj)
        return len(self.open_files) - 1

    def CloseOpenFile(self, file_des):
        """Remove file object with given descriptor from the list
        of open files.

        Sets the entry in open_files to None.

        Args:
            file_des: Descriptor of file object to be removed from
            open files list.
        """
        self.open_files[file_des] = None
        heapq.heappush(self._free_fd_heap, file_des)

    def GetOpenFile(self, file_des):
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
        if (file_des >= len(self.open_files) or
                self.open_files[file_des] is None):
            raise OSError(errno.EBADF, 'Bad file descriptor', file_des)
        return self.open_files[file_des]

    def HasOpenFile(self, file_object):
        """Return True if the given file object is in the list of open files.

        Args:
            file_object: The FakeFile object to be checked.

        Returns:
            `True` if the file is open.
        """
        return (file_object in [wrapper.GetObject()
                                for wrapper in self.open_files if wrapper])

    def NormalizePathSeparator(self, path):
        """Replace all appearances of alternative path separator
        with path separator.
        Do nothing if no alternative separator is set.

        Args:
            path: The path to be normalized.

        Returns:
            The normalized path that will be used internally.
        """
        if sys.version_info >= (3, 6):
            path = os.fspath(path)
        if self.alternative_path_separator is None or not path:
            return path
        return path.replace(self._alternative_path_separator(path),
                            self._path_separator(path))

    def CollapsePath(self, path):
        """Mimic os.path.normpath using the specified path_separator.

        Mimics os.path.normpath using the path_separator that was specified
        for this FakeFilesystem. Normalizes the path, but unlike the method
        NormalizePath, does not make it absolute.  Eliminates dot components
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
        path = self.NormalizePathSeparator(path)
        drive, path = self.SplitDrive(path)
        sep = self._path_separator(path)
        is_absolute_path = path.startswith(sep)
        ends_with_path_sep = path.endswith(sep)
        path_components = path.split(sep)
        collapsed_path_components = []
        dot = self._matching_string(path, '.')
        dotdot = self._matching_string(path, '..')
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

    def NormalizeCase(self, path):
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
                normalized_components.extend(path_components[len(normalized_components):])
            sep = self._path_separator(path)
            normalized_path = sep.join(normalized_components)
            if path.startswith(sep) and not normalized_path.startswith(sep):
                normalized_path = sep + normalized_path
            return normalized_path

        if self.is_case_sensitive or not path:
            return path
        path_components = self.GetPathComponents(path)
        normalized_components = []
        current_dir = self.root
        for component in path_components:
            if not isinstance(current_dir, FakeDirectory):
                return components_to_path()
            dir_name, current_dir = self._DirectoryContent(current_dir, component)
            if current_dir is None or (
                            isinstance(current_dir, FakeDirectory) and
                            current_dir._byte_contents is None and
                            current_dir.st_size == 0):
                return components_to_path()
            normalized_components.append(dir_name)
        return components_to_path()

    def NormalizePath(self, path):
        """Absolutize and minimalize the given path.

        Forces all relative paths to be absolute, and normalizes the path to
        eliminate dot and empty components.

        Args:
            path:  Path to normalize.

        Returns:
            The normalized path relative to the current working directory,
            or the root directory if path is empty.
        """
        path = self.NormalizePathSeparator(path)
        cwd = self._matching_string(path, self.cwd)
        if not path:
            path = self.path_separator
        elif not self._StartsWithRootPath(path):
            # Prefix relative paths with cwd, if cwd is not root.
            root_name = self._matching_string(path, self.root.name)
            empty = self._matching_string(path, '')
            path = self._path_separator(path).join(
                (cwd != root_name and cwd or empty, path))
        if path == self._matching_string(path, '.'):
            path = cwd
        return self.CollapsePath(path)

    def SplitPath(self, path):
        """Mimic os.path.split using the specified path_separator.

        Mimics os.path.split using the path_separator that was specified
        for this FakeFilesystem.

        Args:
            path:  (str) The path to split.

        Returns:
            (str) A duple (pathname, basename) for which pathname does not
            end with a slash, and basename does not contain a slash.
        """
        drive, path = self.SplitDrive(path)
        path = self.NormalizePathSeparator(path)
        sep = self._path_separator(path)
        path_components = path.split(sep)
        if not path_components:
            return ('', '')
        basename = path_components.pop()
        if not path_components:
            return ('', basename)
        for component in path_components:
            if component:
                # The path is not the root; it contains a non-separator
                # component. Strip all trailing separators.
                while not path_components[-1]:
                    path_components.pop()
                return (drive + sep.join(path_components), basename)
        # Root path.  Collapse all leading separators.
        return (drive or sep, basename)

    def SplitDrive(self, path):
        """Splits the path into the drive part and the rest of the path.

        Taken from Windows specific implementation in Python 3.5
        and slightly adapted.

        Args:
            path: the full path to be split.

        Returns:
            A tuple of the drive part and the rest of the path, or of
            an empty string and the full path if drive letters are
            not supported or no drive is present.
        """
        if sys.version_info >= (3, 6):
            path = os.fspath(path)
        if self.is_windows_fs:
            if len(path) >= 2:
                path = self.NormalizePathSeparator(path)
                sep = self._path_separator(path)
                # UNC path handling is here since Python 2.7.8,
                # back-ported from Python 3
                if sys.version_info >= (2, 7, 8):
                    if (path[0:2] == sep * 2) and (
                            path[2:3] != sep):
                        # UNC path handling - splits off the mount point
                        # instead of the drive
                        sep_index = path.find(sep, 2)
                        if sep_index == -1:
                            return path[:0], path
                        sep_index2 = path.find(sep, sep_index + 1)
                        if sep_index2 == sep_index + 1:
                            return path[:0], path
                        if sep_index2 == -1:
                            sep_index2 = len(path)
                        return path[:sep_index2], path[sep_index2:]
                if path[1:2] == self._matching_string(path, ':'):
                    return path[:2], path[2:]
        return path[:0], path

    def _JoinPathsWithDriveSupport(self, *all_paths):
        """Taken from Python 3.5 os.path.join() code in ntpath.py
        and slightly adapted"""
        base_path = all_paths[0]
        paths_to_add = all_paths[1:]
        sep = self._path_separator(base_path)
        seps = [sep, self._alternative_path_separator(base_path)]
        result_drive, result_path = self.SplitDrive(base_path)
        for path in paths_to_add:
            drive_part, path_part = self.SplitDrive(path)
            if path_part and path_part[:1] in seps:
                # Second path is absolute
                if drive_part or not result_drive:
                    result_drive = drive_part
                result_path = path_part
                continue
            elif drive_part and drive_part != result_drive:
                if self.is_case_sensitive or drive_part.lower() != result_drive.lower():
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
        colon = self._matching_string(base_path, ':')
        if (result_path and result_path[:1] not in seps and
                result_drive and result_drive[-1:] != colon):
            return result_drive + sep + result_path
        return result_drive + result_path

    def JoinPaths(self, *paths):
        """Mimic os.path.join using the specified path_separator.

        Args:
            *paths:  (str) Zero or more paths to join.

        Returns:
            (str) The paths joined by the path separator, starting with
            the last absolute path in paths.
        """
        if sys.version_info >= (3, 6):
            paths = [os.fspath(path) for path in paths]
        if len(paths) == 1:
            return paths[0]
        if self.is_windows_fs:
            return self._JoinPathsWithDriveSupport(*paths)
        joined_path_segments = []
        sep = self._path_separator(paths[0])
        for path_segment in paths:
            if self._StartsWithRootPath(path_segment):
                # An absolute path
                joined_path_segments = [path_segment]
            else:
                if (joined_path_segments and
                        not joined_path_segments[-1].endswith(sep)):
                    joined_path_segments.append(sep)
                if path_segment:
                    joined_path_segments.append(path_segment)
        return self._matching_string(paths[0], '').join(joined_path_segments)

    def GetPathComponents(self, path):
        """Breaks the path into a list of component names.

        Does not include the root directory as a component, as all paths
        are considered relative to the root directory for the FakeFilesystem.
        Callers should basically follow this pattern:

        >>> file_path = self.NormalizePath(file_path)
        >>> path_components = self.GetPathComponents(file_path)
        >>> current_dir = self.root
        >>> for component in path_components:
        >>>     if component not in current_dir.contents:
        >>>         raise IOError
        >>>     DoStuffWithComponent(current_dir, component)
        >>>     current_dir = current_dir.GetEntry(component)

        Args:
            path:  Path to tokenize.

        Returns:
            The list of names split from path.
        """
        if not path or path == self._path_separator(path):
            return []
        drive, path = self.SplitDrive(path)
        path_components = path.split(self._path_separator(path))
        assert drive or path_components
        if not path_components[0]:
            # This is an absolute path.
            path_components = path_components[1:]
        if drive:
            path_components.insert(0, drive)
        return path_components

    def StartsWithDriveLetter(self, file_path):
        """Return True if file_path starts with a drive letter.

        Args:
            file_path: the full path to be examined.

        Returns:
            `True` if drive letter support is enabled in the filesystem and
            the path starts with a drive letter.
        """
        colon = self._matching_string(file_path, ':')
        return (self.is_windows_fs and len(file_path) >= 2 and
                file_path[:1].isalpha and (file_path[1:2]) == colon)

    def _StartsWithRootPath(self, file_path):
        root_name = self._matching_string(file_path, self.root.name)
        return (file_path.startswith(root_name) or
                not self.is_case_sensitive and file_path.lower().startswith(
                    root_name.lower()) or
                self.StartsWithDriveLetter(file_path))

    def _IsRootPath(self, file_path):
        root_name = self._matching_string(file_path, self.root.name)
        return (file_path == root_name or
                not self.is_case_sensitive and file_path.lower() == root_name.lower() or
                len(file_path) == 2 and self.StartsWithDriveLetter(file_path))

    def _EndsWithPathSeparator(self, file_path):
        return file_path and (file_path.endswith(self._path_separator(file_path))
                              or self.alternative_path_separator is not None
                              and file_path.endswith(self._alternative_path_separator(file_path)))

    def _DirectoryContent(self, directory, component):
        if not isinstance(directory, FakeDirectory):
            return None, None
        if component in directory.contents:
            return component, directory.contents[component]
        if not self.is_case_sensitive:
            matching_content = [(subdir, directory.contents[subdir]) for subdir in
                                directory.contents
                                if subdir.lower() == component.lower()]
            if matching_content:
                return matching_content[0]

        return None, None

    def Exists(self, file_path, check_link=False):
        """Return true if a path points to an existing file system object.

        Args:
            file_path:  The path to examine.

        Returns:
            (bool) True if the corresponding object exists.

        Raises:
            TypeError: if file_path is None.
        """
        if check_link and self.IsLink(file_path):
            return True
        if sys.version_info >= (3, 6):
            file_path = os.fspath(file_path)
        if file_path is None:
            raise TypeError
        if not file_path:
            return False
        try:
            file_path = self.ResolvePath(file_path)
        except (IOError, OSError):
            return False
        if file_path == self.root.name:
            return True
        path_components = self.GetPathComponents(file_path)
        current_dir = self.root
        for component in path_components:
            current_dir = self._DirectoryContent(current_dir, component)[1]
            if not current_dir:
                return False
        return True

    @staticmethod
    def _to_string(path):
        if sys.version_info[0] > 2 and isinstance(path, bytes):
            path = path.decode(locale.getpreferredencoding(False))
        return path

    def ResolvePath(self, file_path, allow_fd=False, raw_io=True):
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
            raw_io: `True` if called from low-level I/O functions.

        Returns:
            The resolved_path (string) or None.

        Raises:
            TypeError: if file_path is None.
            IOError: if file_path is '' or a part of the path doesn't exist.
        """

        def _ComponentsToPath(component_folders):
            sep = self._path_separator(
                component_folders[0]) if component_folders else self.path_separator
            path = sep.join(component_folders)
            if not self._StartsWithRootPath(path):
                path = sep + path
            return path

        def _ValidRelativePath(file_path):
            if self.is_windows_fs:
                return True
            slash_dotdot = self._matching_string(
                file_path, self.path_separator + '..')
            while file_path and slash_dotdot in file_path:
                file_path = file_path[:file_path.rfind(slash_dotdot)]
                if not self.Exists(self.NormalizePath(file_path)):
                    return False
            return True

        def _FollowLink(link_path_components, link):
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
                IOError: if there are too many levels of symbolic link
            """
            link_path = link.contents
            sep = self._path_separator(link_path)
            alt_sep = self._alternative_path_separator(link_path)
            # For links to absolute paths, we want to throw out everything
            # in the path built so far and replace with the link. For relative
            # links, we have to append the link to what we have so far,
            if (not link_path.startswith(sep) and
                    (alt_sep is None or not link_path.startswith(alt_sep))):
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
            return self.CollapsePath(link_path)

        if (allow_fd and sys.version_info >= (3, 3) and
                isinstance(file_path, int)):
            return self.GetOpenFile(file_path).GetObject().GetPath()

        if sys.version_info >= (3, 6):
            file_path = os.fspath(file_path)
        if file_path is None:
            # file.open(None) raises TypeError, so mimic that.
            raise TypeError('Expected file system path string, received None')
        file_path = self._to_string(file_path)
        if not file_path or not _ValidRelativePath(file_path):
            # file.open('') raises IOError, so mimic that, and validate that
            # all parts of a relative path exist.
            raise IOError(errno.ENOENT,
                          'No such file or directory: \'%s\'' % file_path)
        file_path = self.NormalizePath(self.NormalizeCase(file_path))
        if self._IsRootPath(file_path):
            return file_path

        current_dir = self.root
        path_components = self.GetPathComponents(file_path)

        resolved_components = []
        link_depth = 0
        while path_components:
            component = path_components.pop(0)
            resolved_components.append(component)
            current_dir = self._DirectoryContent(current_dir, component)[1]
            if current_dir is None:
                # The component of the path at this point does not actually
                # exist in the folder.  We can't resolve the path any more.
                # It is legal to link to a file that does not yet exist, so
                # rather than raise an error, we just append the remaining
                # components to what return path we have built so far and
                # return that.
                resolved_components.extend(path_components)
                break

            # Resolve any possible symlinks in the current path component.
            if stat.S_ISLNK(current_dir.st_mode):
                # This link_depth check is not really meant to be an accurate
                # check. It is just a quick hack to prevent us from looping
                # forever on cycles.
                if link_depth > _MAX_LINK_DEPTH:
                    error_class = OSError if raw_io else IOError
                    raise error_class(
                        errno.ELOOP,
                        'Too many levels of symbolic links: \'%s\'' %
                        _ComponentsToPath(resolved_components))
                link_path = _FollowLink(resolved_components, current_dir)

                # Following the link might result in the complete replacement
                # of the current_dir, so we evaluate the entire resulting path.
                target_components = self.GetPathComponents(link_path)
                path_components = target_components + path_components
                resolved_components = []
                current_dir = self.root
                link_depth += 1
        return _ComponentsToPath(resolved_components)

    def GetObjectFromNormalizedPath(self, file_path):
        """Search for the specified filesystem object within the fake
        filesystem.

        Args:
            file_path: Specifies target FakeFile object to retrieve, with a
                path that has already been normalized/resolved.

        Returns:
            The FakeFile object corresponding to file_path.

        Raises:
            IOError: if the object is not found.
        """
        if sys.version_info >= (3, 6):
            file_path = os.fspath(file_path)
        if file_path == self.root.name:
            return self.root
        file_path = self.NormalizeCase(file_path)
        path_components = self.GetPathComponents(file_path)
        target_object = self.root
        try:
            for component in path_components:
                if stat.S_ISLNK(target_object.st_mode):
                    target_object = self.ResolveObject(target_object.contents)
                if not stat.S_ISDIR(target_object.st_mode):
                    if not self.is_windows_fs:
                        raise IOError(errno.ENOTDIR,
                                      'Not a directory in fake filesystem',
                                      file_path)
                    raise IOError(errno.ENOENT,
                                  'No such file or directory in fake filesystem',
                                  file_path)
                target_object = target_object.GetEntry(component)
        except KeyError:
            raise IOError(errno.ENOENT,
                          'No such file or directory in fake filesystem',
                          file_path)
        return target_object

    def GetObject(self, file_path):
        """Search for the specified filesystem object within the fake
        filesystem.

        Args:
            file_path: Specifies target FakeFile object to retrieve.

        Returns:
            The FakeFile object corresponding to file_path.

        Raises:
            IOError: if the object is not found.
        """
        if sys.version_info >= (3, 6):
            file_path = os.fspath(file_path)
        file_path = self.NormalizePath(file_path)
        return self.GetObjectFromNormalizedPath(file_path)

    def ResolveObject(self, file_path, follow_symlinks=True, allow_fd=False):
        """Search for the specified filesystem object, resolving all links.

        Args:
            file_path: Specifies target FakeFile object to retrieve.
            follow_symlinks: If `False`, the link itself is resolved,
                otherwise the object linked to.
            allow_fd: If `True`, `file_path` may be an open file descriptor

        Returns:
          The FakeFile object corresponding to file_path.

        Raises:
            IOError: if the object is not found.
        """
        if isinstance(file_path, int):
            if allow_fd and sys.version_info >= (3, 3):
                return self.GetOpenFile(file_path).GetObject()
            raise TypeError('path should be string, bytes or '
                            'os.PathLike (if supported), not int')

        if follow_symlinks:
            if sys.version_info >= (3, 6):
                file_path = os.fspath(file_path)
            return self.GetObjectFromNormalizedPath(self.ResolvePath(file_path))
        return self.LResolveObject(file_path)

    def LResolveObject(self, path):
        """Search for the specified object, resolving only parent links.

        This is analogous to the stat/lstat difference.  This resolves links *to*
        the object but not of the final object itself.

        Args:
            path: Specifies target FakeFile object to retrieve.

        Returns:
            The FakeFile object corresponding to path.

        Raises:
            IOError: if the object is not found.
        """
        if sys.version_info >= (3, 6):
            path = os.fspath(path)
        if path == self.root.name:
            # The root directory will never be a link
            return self.root

        # remove trailing separator
        sep = self._path_separator(path)
        alt_sep = self._alternative_path_separator(path)
        if path.endswith(sep) or (alt_sep and path.endswith(alt_sep)):
            path = path[:-1]
        path = self.NormalizeCase(path)

        parent_directory, child_name = self.SplitPath(path)
        if not parent_directory:
            parent_directory = self.cwd
        try:
            parent_obj = self.ResolveObject(parent_directory)
            assert parent_obj
            if not isinstance(parent_obj, FakeDirectory):
                if not self.is_windows_fs and isinstance(parent_obj, FakeFile):
                    raise IOError(errno.ENOTDIR,
                                  'The parent object is not a directory', path)
                raise IOError(errno.ENOENT,
                              'No such file or directory in fake filesystem',
                              path)
            return parent_obj.GetEntry(child_name)
        except KeyError:
            raise IOError(errno.ENOENT,
                          'No such file or directory in the fake filesystem',
                          path)

    def AddObject(self, file_path, file_object, error_class=OSError):
        """Add a fake file or directory into the filesystem at file_path.

        Args:
            file_path: The path to the file to be added relative to self.
            file_object: File or directory to add.
            error_class: The error class to be thrown if file_path does
                not correspond to a directory (used internally(

        Raises:
            IOError or OSError: if file_path does not correspond to a
                directory.
        """
        if not file_path:
            target_directory = self.root
        else:
            target_directory = self.ResolveObject(file_path)
            if not stat.S_ISDIR(target_directory.st_mode):
                error = errno.ENOENT if self.is_windows_fs else errno.ENOTDIR
                raise error_class(error,
                              'Not a directory in the fake filesystem',
                              file_path)
        target_directory.AddEntry(file_object)

    def RenameObject(self, old_file_path, new_file_path, force_replace=False):
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
        old_file_path = self.NormalizeCase(self.NormalizePath(old_file_path))
        new_file_path = self.NormalizePath(new_file_path)
        if not self.Exists(old_file_path, check_link=True):
            self.raise_os_error(errno.ENOENT, 2,
                                 'Fake filesystem object: '
                                 'can not rename nonexistent file',
                                old_file_path)

        old_object = self.LResolveObject(old_file_path)
        if not self.is_windows_fs:
            if (self.IsDir(old_file_path, follow_symlinks=False) and
                    self.IsLink(new_file_path)):
                raise OSError(errno.ENOTDIR,
                              'Cannot rename directory to symlink',
                              new_file_path)
            if (self.IsDir(new_file_path, follow_symlinks=False) and
                    self.IsLink(old_file_path)):
                raise OSError(errno.EISDIR,
                              'Cannot rename symlink to directory',
                              new_file_path)

        if self.Exists(new_file_path, check_link=True):
            if old_file_path == new_file_path:
                return  # Nothing to do here.

            new_object = self.GetObject(new_file_path)
            if old_object == new_object:
                doRename = old_file_path.lower() == new_file_path.lower()
                if not doRename:
                    try:
                        real_old_path = self.ResolvePath(old_file_path)
                        real_new_path = self.ResolvePath(new_file_path)
                        if (real_new_path == real_old_path and
                                new_file_path.lower() != real_new_path.lower()):
                            doRename = not self.is_macos
                        else:
                            doRename = real_new_path.lower() == real_old_path.lower()
                        if doRename:
                            # only case is changed in case-insensitive file system
                            # - do the rename
                            parent, file_name = self.SplitPath(new_file_path)
                            new_file_path = self.JoinPaths(
                                self.NormalizeCase(parent), file_name)
                    except (IOError, OSError):
                        # ResolvePath may fail due to symlink loop issues or similar -
                        # in this case just assume the paths different
                        pass
                if not doRename:
                    # hard links to the same file - nothing to do
                    return

            elif (stat.S_ISDIR(new_object.st_mode) or
                      stat.S_ISLNK(new_object.st_mode)):
                if self.is_windows_fs:
                    if force_replace:
                        raise OSError(errno.EACCES,
                                      'Fake filesystem object: '
                                      'can not replace existing directory',
                                      new_file_path)
                    else:
                        raise OSError(errno.EEXIST,
                                      'Fake filesystem object: '
                                      'can not rename to existing directory',
                                      new_file_path)
                if not stat.S_ISLNK(new_object.st_mode):
                    if new_object.contents:
                        raise OSError(errno.ENOTEMPTY,
                                      'Fake filesystem object: '
                                      'can not rename to non-empty directory',
                                      new_file_path)
                    if stat.S_ISREG(old_object.st_mode):
                        raise OSError(errno.EISDIR,
                                      'Fake filesystem object: '
                                      'cannot rename file to directory',
                                      new_file_path)
            elif stat.S_ISDIR(old_object.st_mode):
                error = errno.EEXIST if self.is_windows_fs else errno.ENOTDIR
                raise OSError(error,
                              'Fake filesystem object: '
                              'cannot rename directory to file',
                              new_file_path)
            elif self.is_windows_fs and not force_replace:
                raise OSError(errno.EEXIST,
                              'Fake filesystem object: '
                              'can not rename to existing file',
                              new_file_path)
            else:
                try:
                    self.RemoveObject(new_file_path)
                except IOError as exc:
                    raise OSError(exc.errno, exc.strerror, exc.filename)

        old_dir, old_name = self.SplitPath(old_file_path)
        new_dir, new_name = self.SplitPath(new_file_path)
        if not self.Exists(new_dir):
            raise OSError(errno.ENOENT, 'No such fake directory', new_dir)
        old_dir_object = self.ResolveObject(old_dir)
        new_dir_object = self.ResolveObject(new_dir)
        if old_dir_object.st_dev != new_dir_object.st_dev:
            raise OSError(errno.EXDEV,
                          'Fake filesystem object: '
                          'cannot rename across file systems',
                          old_file_path)
        if not stat.S_ISDIR(new_dir_object.st_mode):
            raise OSError(errno.EACCES if self.is_windows_fs else errno.ENOTDIR,
                          'Fake filesystem object: '
                          'target parent is not a directory',
                          new_file_path)
        if new_dir_object.HasParentObject(old_object):
            raise OSError(errno.EINVAL,
                          'Fake filesystem object: invalid target for rename',
                          new_file_path)

        object_to_rename = old_dir_object.GetEntry(old_name)
        old_dir_object.RemoveEntry(old_name, recursive=False)
        object_to_rename.name = new_name
        new_name = new_dir_object._normalized_entryname(new_name)
        if new_name in new_dir_object.contents:
            # in case of overwriting remove the old entry first
            new_dir_object.RemoveEntry(new_name)
        new_dir_object.AddEntry(object_to_rename)

    def RemoveObject(self, file_path):
        """Remove an existing file or directory.

        Args:
            file_path: The path to the file relative to self.

        Raises:
            IOError: if file_path does not correspond to an existing file, or
                if part of the path refers to something other than a directory.
            OSError: if the directory is in use (eg, if it is '/').
        """
        file_path = self.NormalizePath(self.NormalizeCase(file_path))
        if self._IsRootPath(file_path):
            raise OSError(errno.EBUSY, 'Fake device or resource busy',
                          file_path)
        try:
            dirname, basename = self.SplitPath(file_path)
            target_directory = self.ResolveObject(dirname)
            target_directory.RemoveEntry(basename)
        except KeyError:
            raise IOError(errno.ENOENT,
                          'No such file or directory in the fake filesystem',
                          file_path)
        except AttributeError:
            raise IOError(errno.ENOTDIR,
                          'Not a directory in the fake filesystem',
                          file_path)

    def CreateDirectory(self, directory_path, perm_bits=PERM_DEF):
        """Create directory_path, and all the parent directories.

        Helper method to set up your test faster.

        Args:
            directory_path: The full directory path to create.
            perm_bits: The permission bits as set by `chmod`.

        Returns:
            The newly created FakeDirectory object.

        Raises:
            OSError: if the directory already exists.
        """
        directory_path = self.NormalizePath(directory_path)
        self._AutoMountDriveIfNeeded(directory_path)
        if self.Exists(directory_path, check_link=True):
            raise OSError(errno.EEXIST,
                          'Directory exists in fake filesystem',
                          directory_path)
        path_components = self.GetPathComponents(directory_path)
        current_dir = self.root

        new_dirs = []
        for component in path_components:
            directory = self._DirectoryContent(current_dir, component)[1]
            if not directory:
                new_dir = FakeDirectory(component, filesystem=self)
                new_dirs.append(new_dir)
                current_dir.AddEntry(new_dir)
                current_dir = new_dir
            else:
                if stat.S_ISLNK(directory.st_mode):
                    directory = self.ResolveObject(directory.contents)
                current_dir = directory
                if directory.st_mode & stat.S_IFDIR != stat.S_IFDIR:
                    raise OSError(errno.ENOTDIR, 'Not a directory', current_dir.GetPath())

        # set the permission after creating the directories
        # to allow directory creation inside a read-only directory
        for new_dir in new_dirs:
            new_dir.st_mode = stat.S_IFDIR | perm_bits

        self._last_ino += 1
        current_dir.SetIno(self._last_ino)
        return current_dir

    def CreateFile(self, file_path, st_mode=stat.S_IFREG | PERM_DEF_FILE,
                   contents='', st_size=None, create_missing_dirs=True,
                   apply_umask=False, encoding=None, errors=None):
        """Create file_path, including all the parent directories along the way.

        This helper method can be used to set up tests more easily.

        Args:
            file_path: The path to the file to create.
            st_mode: The stat constant representing the file type.
            contents: The contents of the file.
            st_size: The file size; only valid if contents not given.
            create_missing_dirs: If `True`, auto create missing directories.
            apply_umask: `True` if the current umask must be applied on st_mode.
            encoding: Ff contents is a unicode string, the encoding used
                for serialization.
            errors: The error mode used for encoding/decoding errors.

        Returns:
            The newly created FakeFile object.

        Raises:
            IOError: if the file already exists.
            IOError: if the containing directory is required and missing.
        """
        return self.CreateFileInternally(
            file_path, st_mode, contents, st_size, create_missing_dirs,
            apply_umask, encoding, errors)

    def add_real_file(self, file_path, read_only=True):
        """Create file_path, including all the parent directories along the
        way, for an existing real file. The contents of the real file are read
        only on demand.

        Args:
            file_path: Path to an existing file in the real file system
            read_only: If `True` (the default), writing to the fake file
                raises an exception.  Otherwise, writing to the file changes
                the fake file only.

        Returns:
            the newly created FakeFile object.

        Raises:
            OSError: if the file does not exist in the real file system.
            IOError: if the file already exists in the fake file system.

        .. note:: On MacOS and BSD, accessing the fake file's contents will update \
                  both the real and fake files' `atime.` (access time).  In this \
                  particular case, `add_real_file()` violates the rule that `pyfakefs` \
                  must not modify the real file system. \
                  \
                  Further, Windows offers the option to enable atime, and older \
                  versions of Linux may also modify atime.
        """
        return self.CreateFileInternally(file_path,
                                         read_from_real_fs=True,
                                         read_only=read_only)

    def add_real_directory(self, dir_path, read_only=True, lazy_read=True):
        """Create a fake directory corresponding to the real directory at the specified
        path.  Add entries in the fake directory corresponding to the entries in the
        real directory.

        Args:
            dir_path: The path to the existing directory.
            read_only: If set, all files under the directory are treated as
                read-only, e.g. a write access raises an exception;
                otherwise, writing to the files changes the fake files only
                as usually.
            lazy_read: If set (default), directory contents are only read when
                accessed, and only until the needed subdirectory level.
                *Note:* this means that the file system size is only updated
                at the time the directory contents are read; set this to
                `False` only if you are dependent on accurate file system
                size in your test

        Returns:
            the newly created FakeDirectory object.

        Raises:
            OSError: if the directory does not exist in the real file system.
            IOError: if the directory already exists in the fake file system.
        """
        if not os.path.exists(dir_path):
            raise IOError(errno.ENOENT, 'No such directory', dir_path)
        if lazy_read:
            parent_path = os.path.split(dir_path)[0]
            if self.Exists(parent_path):
                parent_dir = self.GetObject(parent_path)
            else:
                parent_dir = self.CreateDirectory(parent_path)
            new_dir = FakeDirectoryFromRealDirectory(dir_path, filesystem=self, read_only=read_only)
            parent_dir.AddEntry(new_dir)
            self._last_ino += 1
            new_dir.SetIno(self._last_ino)
        else:
            new_dir = self.CreateDirectory(dir_path)
            for base, _, files in os.walk(dir_path):
                for fileEntry in files:
                    self.add_real_file(os.path.join(base, fileEntry), read_only)
        return new_dir

    def add_real_paths(self, path_list, read_only=True, lazy_dir_read=True):
        """This convenience method adds multiple files and/or directories from the
        real file system to the fake file system. See `add_real_file()` and
        `add_real_directory()`.

        Args:
            path_list: List of file and directory paths in the real file system.
            read_only: If set, all files and files under under the directories are treated as read-only,
                e.g. a write access raises an exception;
                otherwise, writing to the files changes the fake files only as usually.
            lazy_dir_read: Uses lazy reading of directory contents if set
                (see `add_real_directory`)

        Raises:
            OSError: if any of the files and directories in the list does not exist in the real file system.
            OSError: if any of the files and directories in the list already exists in the fake file system.
        """
        for path in path_list:
            if os.path.isdir(path):
                self.add_real_directory(path, read_only, lazy_dir_read)
            else:
                self.add_real_file(path, read_only)

    def CreateFileInternally(self, file_path, st_mode=stat.S_IFREG | PERM_DEF_FILE,
                             contents='', st_size=None, create_missing_dirs=True,
                             apply_umask=False, encoding=None, errors=None,
                             read_from_real_fs=False, read_only=True, raw_io=False):
        """Internal fake file creator that supports both normal fake files and fake
        files based on real files.

        Args:
            file_path: path to the file to create.
            st_mode: the stat.S_IF constant representing the file type.
            contents: the contents of the file.
            st_size: file size; only valid if contents not given.
            create_missing_dirs: if True, auto create missing directories.
            apply_umask: whether or not the current umask must be applied on st_mode.
            encoding: if contents is a unicode string, the encoding used for serialization.
            errors: the error mode used for encoding/decoding errors
            read_from_real_fs: if True, the contents are reaf from the real file system on demand.
            read_only: if set, the file is treated as read-only, e.g. a write access raises an exception;
                otherwise, writing to the file changes the fake file only as usually.
            raw_io: `True` if called from low-level API (`os.open`)
        """
        error_class = OSError if raw_io else IOError
        file_path = self.NormalizePath(file_path)
        if not is_int_type(st_mode):
            raise TypeError('st_mode must be of int type - did you mean to set contents?')

        if self.Exists(file_path, check_link=True):
            raise OSError(errno.EEXIST,
                              'File already exists in fake filesystem',
                              file_path)
        parent_directory, new_file = self.SplitPath(file_path)
        if not parent_directory:
            parent_directory = self.cwd
        self._AutoMountDriveIfNeeded(parent_directory)
        if not self.Exists(parent_directory):
            if not create_missing_dirs:
                raise error_class(errno.ENOENT, 'No such fake directory', parent_directory)
            self.CreateDirectory(parent_directory)
        else:
            parent_directory = self.NormalizeCase(parent_directory)
        if apply_umask:
            st_mode &= ~self.umask
        if read_from_real_fs:
            file_object = FakeFileFromRealFile(file_path, filesystem=self, read_only=read_only)
        else:
            file_object = FakeFile(new_file, st_mode, filesystem=self, encoding=encoding, errors=errors)

        self._last_ino += 1
        file_object.SetIno(self._last_ino)
        self.AddObject(parent_directory, file_object, error_class)

        if not read_from_real_fs and (contents is not None or st_size is not None):
            try:
                if st_size is not None:
                    file_object.SetLargeFileSize(st_size)
                else:
                    file_object._set_initial_contents(contents)
            except IOError:
                self.RemoveObject(file_path)
                raise

        return file_object

    # pylint: disable=unused-argument
    def CreateLink(self, file_path, link_target, create_missing_dirs=True):
        """Create the specified symlink, pointed at the specified link target.

        Args:
            file_path:  path to the symlink to create
            link_target:  the target of the symlink
            create_missing_dirs: If `True`, any missing parent directories of
                file_path will be created

        Returns:
            The newly created FakeFile object.

        Raises:
            OSError:  if the symlink could not be created (see `CreateFile`).
            OSError:  if on Windows before Python 3.2.
        """
        if not self._IsLinkSupported():
            raise OSError("Symbolic links are not supported on Windows before Python 3.2")

        # the link path cannot end with a path separator
        file_path = self.NormalizePathSeparator(file_path)
        if file_path.endswith(self.path_separator):
            if self.Exists(file_path):
                raise OSError(errno.EEXIST, 'File exists')
            if not self.is_windows_fs:
                raise OSError(errno.ENOENT, 'No such file or directory')

        # resolve the link path only if it is not a link itself
        if not self.IsLink(file_path):
            file_path = self.ResolvePath(file_path)
        if sys.version_info >= (3, 6):
            link_target = os.fspath(link_target)
        return self.CreateFileInternally(file_path, st_mode=stat.S_IFLNK | PERM_DEF,
                               contents=link_target, create_missing_dirs=create_missing_dirs,
                               raw_io=True)

    def CreateHardLink(self, old_path, new_path):
        """Create a hard link at new_path, pointing at old_path.

        Args:
            old_path: An existing link to the target file.
            new_path: The destination path to create a new link at.

        Returns:
            The FakeFile object referred to by old_path.

        Raises:
            OSError:  if something already exists at new_path.
            OSError:  if old_path is a directory.
            OSError:  if the parent directory doesn't exist.
            OSError:  if on Windows before Python 3.2.
        """
        if not self._IsLinkSupported():
            raise OSError("Links are not supported on Windows before Python 3.2")
        new_path_normalized = self.NormalizePath(new_path)
        if self.Exists(new_path_normalized, check_link=True):
            raise OSError(errno.EEXIST,
                          'File already exists in fake filesystem',
                          new_path)

        new_parent_directory, new_basename = self.SplitPath(new_path_normalized)
        if not new_parent_directory:
            new_parent_directory = self.cwd

        if not self.Exists(new_parent_directory):
            raise OSError(errno.ENOENT, 'No such fake directory',
                          new_parent_directory)

        # Retrieve the target file
        try:
            old_file = self.ResolveObject(old_path)
        except:
            raise OSError(errno.ENOENT,
                          'No such file or directory in fake filesystem',
                          old_path)

        if old_file.st_mode & stat.S_IFDIR:
            raise OSError(errno.EACCES if self.is_windows_fs else errno.EPERM,
                          'Cannot create hard link to directory',
                          old_path)

        # abuse the name field to control the filename of the newly created link
        old_file.name = new_basename
        self.AddObject(new_parent_directory, old_file)
        return old_file

    def ReadLink(self, path):
        """Read the target of a symlink.

        Args:
            path:  symlink to read the target of.

        Returns:
            the string representing the path to which the symbolic link points.

        Raises:
            TypeError: if path is None
            OSError: (with errno=ENOENT) if path is not a valid path, or
                (with errno=EINVAL) if path is valid, but is not a symlink.
        """
        if path is None:
            raise TypeError
        try:
            link_obj = self.LResolveObject(path)
        except IOError as exc:
            raise OSError(exc.errno, 'Fake path does not exist', path)
        if stat.S_IFMT(link_obj.st_mode) != stat.S_IFLNK:
            raise OSError(errno.EINVAL, 'Fake filesystem: not a symlink', path)
        return link_obj.contents

    def MakeDirectory(self, dir_name, mode=PERM_DEF):
        """Create a leaf Fake directory.

        Args:
            dir_name: (str) Name of directory to create.
                Relative paths are assumed to be relative to '/'.
            mode: (int) Mode to create directory with.  This argument defaults
                to 0o777. The umask is applied to this mode.

        Raises:
            OSError: if the directory name is invalid or parent directory is
                read only or as per `FakeFilesystem.AddObject()`.
        """
        if sys.version_info >= (3, 6):
            dir_name = os.fspath(dir_name)
        if self._EndsWithPathSeparator(dir_name):
            dir_name = dir_name[:-1]
        if not dir_name:
            raise OSError(errno.ENOENT, 'Empty directory name')

        if self.is_windows_fs:
            dir_name = self.NormalizePath(dir_name)
        parent_dir, _ = self.SplitPath(dir_name)
        if parent_dir:
            base_dir = self.CollapsePath(parent_dir)
            ellipsis = self._matching_string(parent_dir, self.path_separator + '..')
            if parent_dir.endswith(ellipsis) and not self.is_windows_fs:
                base_dir, dummy_dotdot, _ = parent_dir.partition(ellipsis)
            if not self.Exists(base_dir):
                raise OSError(errno.ENOENT, 'No such fake directory', base_dir)

        dir_name = self.NormalizePath(dir_name)
        if self.Exists(dir_name, check_link=True):
            if self.is_windows_fs and dir_name == self.path_separator:
                error_nr = errno.EACCES
            else:
                error_nr = errno.EEXIST
            raise OSError(error_nr, 'Fake object already exists', dir_name)
        head, tail = self.SplitPath(dir_name)

        self.AddObject(
            head, FakeDirectory(tail, mode & ~self.umask, filesystem=self))

    def MakeDirectories(self, dir_name, mode=PERM_DEF, exist_ok=False):
        """Create a leaf Fake directory and create any non-existent parent dirs.

        Args:
            dir_name: (str) Name of directory to create.
            mode: (int) Mode to create directory (and any necessary parent
                directories) with. This argument defaults to 0o777.
                The umask is applied to this mode.
          exist_ok: (boolean) If exist_ok is False (the default), an OSError is
                raised if the target directory already exists.
                New in Python 3.2.

        Raises:
          OSError: if the directory already exists and exist_ok=False, or as per
          `FakeFilesystem.CreateDirectory()`.
        """
        dir_name = self.NormalizePath(dir_name)
        path_components = self.GetPathComponents(dir_name)

        # Raise a permission denied error if the first existing directory is not
        # writeable.
        current_dir = self.root
        for component in path_components:
            if (component not in current_dir.contents
                or not isinstance(current_dir.contents, dict)):
                break
            else:
                current_dir = current_dir.contents[component]
        try:
            self.CreateDirectory(dir_name, mode & ~self.umask)
        except (IOError, OSError) as e:
            if (not exist_ok or
                    not isinstance(self.ResolveObject(dir_name), FakeDirectory)):
                if self.is_windows_fs and e.errno == errno.ENOTDIR:
                    e.errno = errno.ENOENT
                raise OSError(e.errno, e.strerror, e.filename)

    def _IsType(self, path, st_flag, follow_symlinks=True):
        """Helper function to implement isdir(), islink(), etc.

        See the stat(2) man page for valid stat.S_I* flag values

        Args:
            path: Path to file to stat and test
            st_flag: The stat.S_I* flag checked for the file's st_mode

        Returns:
            (boolean) `True` if the st_flag is set in path's st_mode.

        Raises:
          TypeError: if path is None
        """
        if sys.version_info >= (3, 6):
            path = os.fspath(path)
        if path is None:
            raise TypeError
        try:
            obj = self.ResolveObject(path, follow_symlinks)
            if obj:
                return stat.S_IFMT(obj.st_mode) == st_flag
        except (IOError, OSError):
            return False
        return False

    def IsDir(self, path, follow_symlinks=True):
        """Determine if path identifies a directory.

        Args:
            path: Path to filesystem object.

        Returns:
            `True` if path points to a directory (following symlinks).

        Raises:
            TypeError: if path is None.
        """
        return self._IsType(path, stat.S_IFDIR, follow_symlinks)

    def IsFile(self, path, follow_symlinks=True):
        """Determine if path identifies a regular file.

        Args:
            path: Path to filesystem object.

        Returns:
            `True` if path points to a regular file (following symlinks).

        Raises:
            TypeError: if path is None.
        """
        return self._IsType(path, stat.S_IFREG, follow_symlinks)

    def IsLink(self, path):
        """Determine if path identifies a symbolic link.

        Args:
            path: Path to filesystem object.

        Returns:
            `True` if path points to a symlink (S_IFLNK set in st_mode)

        Raises:
            TypeError: if path is None.
        """
        return self._IsType(path, stat.S_IFLNK, follow_symlinks=False)

    def ConfirmDir(self, target_directory):
        """Test that the target is actually a directory, raising OSError if not.

        Args:
            target_directory: Path to the target directory within the fake
                filesystem.

        Returns:
            The FakeDirectory object corresponding to target_directory.

        Raises:
            OSError: if the target is not a directory.
        """
        try:
            directory = self.ResolveObject(target_directory)
        except IOError as exc:
            raise OSError(exc.errno, exc.strerror, target_directory)
        if not directory.st_mode & stat.S_IFDIR:
            if self.is_windows_fs and sys.version_info[0] < 3:
                error_nr = errno.EINVAL
            else:
                error_nr = errno.ENOTDIR
            self.raise_os_error(error_nr, 267,
                                 'Fake os module: not a directory',
                                target_directory)
        return directory

    def RemoveFile(self, path):
        """Remove the FakeFile object at the specified file path.

        Args:
            path: Path to file to be removed.

        Raises:
            OSError: if path points to a directory.
            OSError: if path does not exist.
            OSError: if removal failed.
        """
        path = self.NormalizePath(path)
        if self.Exists(path):
            obj = self.ResolveObject(path)
            if stat.S_IFMT(obj.st_mode) == stat.S_IFDIR:
                link_obj = self.LResolveObject(path)
                if stat.S_IFMT(link_obj.st_mode) != stat.S_IFLNK:
                    if self.is_windows_fs:
                        error = errno.EACCES
                    elif self.is_macos:
                        error = errno.EPERM
                    else:
                        error = errno.EISDIR
                    raise OSError(error, "Is a directory: '%s'" % path)

        try:
            self.RemoveObject(path)
        except IOError as exc:
            raise OSError(exc.errno, exc.strerror, exc.filename)

    def RemoveDirectory(self, target_directory, allow_symlink=False):
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
        if target_directory in (b'.', u'.'):
            error_nr = errno.EACCES if self.is_windows_fs else errno.EINVAL
            raise OSError(error_nr, 'Invalid argument: \'.\'')
        target_directory = self.NormalizePath(target_directory)
        if self.ConfirmDir(target_directory):
            if not self.is_windows_fs and self.IsLink(target_directory):
                if allow_symlink:
                    return
                raise OSError(errno.ENOTDIR, 'Cannot remove symlink', target_directory)

            dir_object = self.ResolveObject(target_directory)
            if dir_object.contents:
                raise OSError(errno.ENOTEMPTY, 'Fake Directory not empty',
                              target_directory)
            try:
                self.RemoveObject(target_directory)
            except IOError as exc:
                raise OSError(exc.errno, exc.strerror, exc.filename)

    def ListDir(self, target_directory):
        """Return a list of file names in target_directory.

        Args:
            target_directory: Path to the target directory within the
                fake filesystem.

        Returns:
            A list of file names within the target directory in arbitrary order.

        Raises:
            OSError: if the target is not a directory.
        """
        target_directory = self.ResolvePath(target_directory, allow_fd=True)
        directory = self.ConfirmDir(target_directory)
        directory_contents = directory.contents
        return list(directory_contents.keys())

    if sys.version_info >= (3, 5):
        class DirEntry():
            """Emulates os.DirEntry. Note that we did not enforce keyword only arguments."""

            def __init__(self, filesystem):
                """Initialize the dir entry with unset values.

                Args:
                    filesystem: the fake filesystem used for implementation.
                """
                self._filesystem = filesystem
                self.name = ''
                self.path = ''
                self._inode = None
                self._islink = False
                self._isdir = False
                self._statresult = None
                self._statresult_symlink = None

            def inode(self):
                """Return the inode number of the entry."""
                if self._inode is None:
                    self.stat(follow_symlinks=False)
                return self._inode

            def is_dir(self, follow_symlinks=True):
                """Return True if this entry is a directory entry.

                Args:
                    follow_symlinks: If True, also return True if this entry is a symlink
                                    pointing to a directory.

                Returns:
                    True if this entry is an existing directory entry, or if
                    follow_symlinks is set, and this entry points to an existing directory entry.
                """
                return self._isdir and (follow_symlinks or not self._islink)

            def is_file(self, follow_symlinks=True):
                """Return True if this entry is a regular file entry.

                Args:
                    follow_symlinks: If True, also return True if this entry is a symlink
                                    pointing to a regular file.

                Returns:
                    True if this entry is an existing file entry, or if
                    follow_symlinks is set, and this entry points to an existing file entry.
                """
                return not self._isdir and (follow_symlinks or not self._islink)

            def is_symlink(self):
                """Return True if this entry is a symbolic link (even if broken)."""
                return self._islink

            def stat(self, follow_symlinks=True):
                """Return a stat_result object for this entry.

                Args:
                    follow_symlinks: If False and the entry is a symlink, return the
                        result for the symlink, otherwise for the object it points to.
                """
                if follow_symlinks:
                    if self._statresult_symlink is None:
                        file_object = self._filesystem.ResolveObject(self.path)
                        if self._filesystem.is_windows_fs:
                            file_object.st_nlink = 0
                        self._statresult_symlink = file_object.stat_result.copy()
                    return self._statresult_symlink

                if self._statresult is None:
                    file_object = self._filesystem.LResolveObject(self.path)
                    self._inode = file_object.st_ino
                    if self._filesystem.is_windows_fs:
                        file_object.st_nlink = 0
                    self._statresult = file_object.stat_result.copy()
                return self._statresult

        class ScanDirIter:
            """Iterator for DirEntry objects returned from `scandir()`
            function."""

            def __init__(self, filesystem, path):
                self.filesystem = filesystem
                self.path = self.filesystem.ResolvePath(path)
                contents = {}
                try:
                    contents = self.filesystem.ConfirmDir(path).contents
                except OSError:
                    pass
                self.contents_iter = iter(contents)

            def __iter__(self):
                return self

            def __next__(self):
                entry = self.contents_iter.__next__()
                dir_entry = self.filesystem.DirEntry(self.filesystem)
                dir_entry.name = entry
                dir_entry.path = self.filesystem.JoinPaths(self.path, dir_entry.name)
                dir_entry._isdir = self.filesystem.IsDir(dir_entry.path)
                dir_entry._islink = self.filesystem.IsLink(dir_entry.path)
                return dir_entry

            if sys.version_info >= (3, 6):
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc_val, exc_tb):
                    self.close()

                def close(self):
                    pass

        def ScanDir(self, path=''):
            """Return an iterator of DirEntry objects corresponding to the entries
            in the directory given by path.

            Args:
                path: Path to the target directory within the fake filesystem.

            Returns:
                an iterator to an unsorted list of os.DirEntry objects for
                each entry in path.

            Raises:
                OSError: if the target is not a directory.
            """
            return self.ScanDirIter(self, path)

    def __str__(self):
        return str(self.root)

    def _add_standard_streams(self):
        self.AddOpenFile(StandardStreamWrapper(sys.stdin))
        self.AddOpenFile(StandardStreamWrapper(sys.stdout))
        self.AddOpenFile(StandardStreamWrapper(sys.stderr))


class FakePathModule(object):
    """Faked os.path module replacement.

    FakePathModule should *only* be instantiated by FakeOsModule.  See the
    FakeOsModule docstring for details.
    """
    _OS_PATH_COPY = CopyModule(os.path)

    def __init__(self, filesystem, os_module=None):
        """Init.

        Args:
            filesystem: FakeFilesystem used to provide file system information
            os_module: (deprecated) FakeOsModule to assign to self.os
        """
        self.filesystem = filesystem
        self._os_path = self._OS_PATH_COPY
        if os_module is None:
            warnings.warn(FAKE_PATH_MODULE_DEPRECATION, DeprecationWarning,
                          stacklevel=2)
        self._os_path.os = self.os = os_module
        self.sep = self.filesystem.path_separator
        self.altsep = self.filesystem.alternative_path_separator

    def exists(self, path):
        """Determine whether the file object exists within the fake filesystem.

        Args:
            path: The path to the file object.

        Returns:
            (bool) `True` if the file exists.
        """
        return self.filesystem.Exists(path)

    def lexists(self, path):
        """Test whether a path exists.  Returns True for broken symbolic links.

        Args:
          path:  path to the symlink object.

        Returns:
          bool (if file exists).
        """
        return self.filesystem.Exists(path, check_link=True)

    def getsize(self, path):
        """Return the file object size in bytes.

        Args:
          path:  path to the file object.

        Returns:
          file size in bytes.
        """
        try:
            file_obj = self.filesystem.ResolveObject(path)
            return file_obj.st_size
        except IOError as exc:
            raise os.error(exc.errno, exc.strerror)

    def isabs(self, path):
        """Return True if path is an absolute pathname."""
        if self.filesystem.is_windows_fs:
            path = self.splitdrive(path)[1]
        if sys.version_info >= (3, 6):
            path = os.fspath(path)
        sep = self.filesystem._path_separator(path)
        altsep = self.filesystem._alternative_path_separator(path)
        if self.filesystem.is_windows_fs:
            return len(path) > 0 and path[:1] in (sep, altsep)
        else:
            return path.startswith(sep) or altsep is not None and path.startswith(altsep)

    def isdir(self, path):
        """Determine if path identifies a directory."""
        return self.filesystem.IsDir(path)

    def isfile(self, path):
        """Determine if path identifies a regular file."""
        return self.filesystem.IsFile(path)

    def islink(self, path):
        """Determine if path identifies a symbolic link.

        Args:
            path: Path to filesystem object.

        Returns:
            `True` if path points to a symbolic link.

        Raises:
            TypeError: if path is None.
        """
        return self.filesystem.IsLink(path)

    def getmtime(self, path):
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
            file_obj = self.filesystem.ResolveObject(path)
        except IOError as exc:
            self.filesystem.raise_os_error(errno.ENOENT, 3, str(exc))
        return file_obj.st_mtime

    def getatime(self, path):
        """Returns the last access time of the fake file.

        Note: Access time is not set automatically in fake filesystem on access.

        Args:
            path: the path to fake file.

        Returns:
            (int, float) the access time of the fake file in number of seconds since the epoch.

        Raises:
            OSError: if the file does not exist.
        """
        try:
            file_obj = self.filesystem.ResolveObject(path)
        except IOError as exc:
            raise OSError(errno.ENOENT, str(exc))
        return file_obj.st_atime

    def getctime(self, path):
        """Returns the creation time of the fake file.

        Args:
            path: the path to fake file.

        Returns:
            (int, float) the creation time of the fake file in number of seconds since the epoch.

        Raises:
            OSError: if the file does not exist.
        """
        try:
            file_obj = self.filesystem.ResolveObject(path)
        except IOError as exc:
            raise OSError(errno.ENOENT, str(exc))
        return file_obj.st_ctime

    def abspath(self, path):
        """Return the absolute version of a path."""

        def getcwd():
            """Return the current working directory."""
            # pylint: disable=undefined-variable
            if sys.version_info[0] == 2 and isinstance(path, unicode):
                return self.os.getcwdu()
            elif sys.version_info[0] > 2 and isinstance(path, bytes):
                return self.os.getcwdb()
            else:
                return self.os.getcwd()

        if sys.version_info >= (3, 6):
            path = os.fspath(path)

        sep = self.filesystem._path_separator(path)
        altsep = self.filesystem._alternative_path_separator(path)
        if not self.isabs(path):
            path = self.join(getcwd(), path)
        elif (self.filesystem.is_windows_fs and
              path.startswith(sep) or altsep is not None and
              path.startswith(altsep)):
            cwd = getcwd()
            if self.filesystem.StartsWithDriveLetter(cwd):
                path = self.join(cwd[:2], path)
        return self.normpath(path)

    def join(self, *p):
        """Return the completed path with a separator of the parts."""
        return self.filesystem.JoinPaths(*p)

    def split(self, path):
        """Split the path into the directory and the filename of the path.
        """
        return self.filesystem.SplitPath(path)

    def splitdrive(self, path):
        """Split the path into the drive part and the rest of the path, if
        supported."""
        return self.filesystem.SplitDrive(path)

    def normpath(self, path):
        """Normalize path, eliminating double slashes, etc."""
        return self.filesystem.CollapsePath(path)

    def normcase(self, path):
        """Convert to lower case under windows, replaces additional path
        separator."""
        path = self.filesystem.NormalizePathSeparator(path)
        if self.filesystem.is_windows_fs:
            path = path.lower()
        return path

    def relpath(self, path, start=None):
        """We mostly rely on the native implementation and adapt the path separator."""
        if not path:
            raise ValueError("no path specified")
        if sys.version_info >= (3, 6):
            path = os.fspath(path)
            if start is not None:
                start = os.fspath(start)
        if start is None:
            start = self.filesystem.cwd
        if self.filesystem.alternative_path_separator is not None:
            path = path.replace(self.filesystem.alternative_path_separator, self._os_path.sep)
            start = start.replace(self.filesystem.alternative_path_separator, self._os_path.sep)
        path = path.replace(self.filesystem.path_separator, self._os_path.sep)
        start = start.replace(self.filesystem.path_separator, self._os_path.sep)
        path = self._os_path.relpath(path, start)
        return path.replace(self._os_path.sep, self.filesystem.path_separator)

    def realpath(self, filename):
        """Return the canonical path of the specified filename, eliminating any
        symbolic links encountered in the path.
        """
        if self.filesystem.is_windows_fs:
            return self.abspath(filename)
        if sys.version_info >= (3, 6):
            filename = os.fspath(filename)
        path, ok = self._joinrealpath(filename[:0], filename, {})
        return self.abspath(path)

    if sys.platform != 'win32' or sys.version_info >= (3, 2):
        def samefile(self, path1, path2):
            """Return whether path1 and path2 point to the same file.
            Windows support new in Python 3.2.

            Args:
                path1: first file path or path object (Python >=3.6)
                path2: second file path or path object (Python >=3.6)

            Raises:
                OSError: if one of the paths does not point to an existing
                    file system object.
            """
            stat1 = self.filesystem.GetStat(path1)
            stat2 = self.filesystem.GetStat(path2)
            return stat1.st_ino == stat2.st_ino and stat1.st_dev == stat2.st_dev

    def _joinrealpath(self, path, rest, seen):
        """Join two paths, normalizing and eliminating any symbolic links
        encountered in the second path.
        Taken from Python source and adapted.
        """
        curdir = self.filesystem._matching_string(path, '.')
        pardir = self.filesystem._matching_string(path, '..')

        sep = self.filesystem._path_separator(path)
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
                    path, name = self.filesystem.SplitPath(path)
                    if name == pardir:
                        path = self.filesystem.JoinPaths(path, pardir, pardir)
                else:
                    path = pardir
                continue
            newpath = self.filesystem.JoinPaths(path, name)
            if not self.filesystem.IsLink(newpath):
                path = newpath
                continue
            # Resolve the symbolic link
            if newpath in seen:
                # Already seen this path
                path = seen[newpath]
                if path is not None:
                    # use cached value
                    continue
                # The symlink is not resolved, so we must have a symlink loop.
                # Return already resolved part + rest of the path unchanged.
                return self.filesystem.JoinPaths(newpath, rest), False
            seen[newpath] = None  # not resolved symlink
            path, ok = self._joinrealpath(path, self.filesystem.ReadLink(newpath), seen)
            if not ok:
                return self.filesystem.JoinPaths(path, rest), False
            seen[newpath] = path  # resolved symlink
        return path, True

    def dirname(self, path):
        """Returns the first part of the result of `split()`."""
        return self.split(path)[0]

    def expanduser(self, path):
        """Return the argument with an initial component of ~ or ~user
        replaced by that user's home directory.
        """
        return self._os_path.expanduser(path).replace(self._os_path.sep, self.sep)

    def ismount(self, path):
        """Return true if the given path is a mount point.

        Args:
            path: Path to filesystem object to be checked

        Returns:
            `True` if path is a mount point added to the fake file system.
            Under Windows also returns True for drive and UNC roots
            (independent of their existence).
        """
        if sys.version_info >= (3, 6):
            path = os.fspath(path)
        if not path:
            return False
        normed_path = self.filesystem.NormalizePath(path)
        sep = self.filesystem._path_separator(path)
        if self.filesystem.is_windows_fs:
            if self.filesystem.alternative_path_separator is not None:
                path_seps = (
                    sep, self.filesystem._alternative_path_separator(path)
                )
            else:
                path_seps = (sep,)
            drive, rest = self.filesystem.SplitDrive(normed_path)
            if drive and drive[:1] in path_seps:
                return (not rest) or (rest in path_seps)
            if rest in path_seps:
                return True
        for mount_point in self.filesystem.mount_points:
            if (normed_path.rstrip(sep) == mount_point.rstrip(sep)):
                return True
        return False

    if sys.version_info < (3, 0):
        def walk(self, top, func, arg):
            """Directory tree walk with callback function.

            Args:
                top: Root path to traverse. The root itself is not included
                    in the called elements.
                func: Function to be called for each visited path node.
                arg: First argument to be called with func (apart from
                    dirname and filenames).
            """
            try:
                names = self.filesystem.ListDir(top)
            except os.error:
                return
            func(arg, top, names)
            for name in names:
                name = self.filesystem.JoinPaths(top, name)
                if self.filesystem.is_windows_fs:
                    if self.filesystem.IsDir(name):
                        self.walk(name, func, arg)
                else:
                    try:
                        st = self.filesystem.GetStat(name, follow_symlinks=False)
                    except os.error:
                        continue
                    if stat.S_ISDIR(st.st_mode):
                        self.walk(name, func, arg)

    def __getattr__(self, name):
        """Forwards any non-faked calls to the real os.path."""
        return getattr(self._os_path, name)


class FakeOsModule(object):
    """Uses FakeFilesystem to provide a fake os module replacement.

    Do not create os.path separately from os, as there is a necessary circular
    dependency between os and os.path to replicate the behavior of the standard
    Python modules.  What you want to do is to just let FakeOsModule take care
    of `os.path` setup itself.

    # You always want to do this.
    filesystem = fake_filesystem.FakeFilesystem()
    my_os_module = fake_filesystem.FakeOsModule(filesystem)
    """

    _stat_float_times = sys.version_info >= (2, 5)

    def __init__(self, filesystem, os_path_module=None):
        """Also exposes self.path (to fake os.path).

        Args:
            filesystem: FakeFilesystem used to provide file system information
            os_path_module: (deprecated) Optional FakePathModule instance
        """
        self.filesystem = filesystem
        self.sep = filesystem.path_separator
        self.altsep = filesystem.alternative_path_separator
        self._os_module = os
        if os_path_module is None:
            self.path = FakePathModule(self.filesystem, self)
        else:
            warnings.warn(FAKE_PATH_MODULE_DEPRECATION, DeprecationWarning,
                          stacklevel=2)
            self.path = os_path_module
        if sys.version_info < (3, 0):
            self.fdopen = self._fdopen_ver2
        else:
            self.fdopen = self._fdopen

    def _fdopen(self, *args, **kwargs):
        """Redirector to open() builtin function.

        Args:
            *args: Pass through args.
            **kwargs: Pass through kwargs.

        Returns:
            File object corresponding to file_des.

        Raises:
            TypeError: if file descriptor is not an integer.
        """
        if not is_int_type(args[0]):
            raise TypeError('an integer is required')
        return FakeFileOpen(self.filesystem)(*args, **kwargs)

    def _fdopen_ver2(self, file_des, mode='r', bufsize=None):  # pylint: disable=unused-argument
        """Returns an open file object connected to the file descriptor file_des.

        Args:
            file_des: An integer file descriptor for the file object requested.
            mode: Additional file flags. Currently checks to see if the mode
                matches the mode of the requested file object.
            bufsize: ignored. (Used for signature compliance with
                __builtin__.fdopen)

        Returns:
            File object corresponding to file_des.

        Raises:
            OSError: if bad file descriptor or incompatible mode is given.
            TypeError: if file descriptor is not an integer.
        """
        if not is_int_type(file_des):
            raise TypeError('an integer is required')

        try:
            return FakeFileOpen(self.filesystem).Call(file_des, mode=mode)
        except IOError as exc:
            raise OSError(exc)

    def _umask(self):
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


    def open(self, file_path, flags, mode=None, dir_fd=None):
        """Return the file descriptor for a FakeFile.

        Args:
            file_path: the path to the file
            flags: low-level bits to indicate io operation
            mode: bits to define default permissions
                Note: only basic modes are supported, OS-specific modes are ignored
            dir_fd: If not `None`, the file descriptor of a directory,
                with `file_path` being relative to this directory.
                New in Python 3.3.

        Returns:
            A file descriptor.

        Raises:
            IOError: if the path cannot be found
            ValueError: if invalid mode is given
            NotImplementedError: if `os.O_EXCL` is used without `os.O_CREAT`
        """
        file_path = self._path_with_dir_fd(file_path, self.open, dir_fd)
        if mode is None:
            if self.filesystem.is_windows_fs:
                mode = 0o666
            else:
                mode = 0o777 & ~self._umask()

        open_modes = _OpenModes(
            must_exist=not flags & os.O_CREAT,
            can_read=not flags & os.O_WRONLY,
            can_write=flags & (os.O_RDWR | os.O_WRONLY),
            truncate=flags & os.O_TRUNC,
            append=flags & os.O_APPEND,
            must_not_exist=flags & os.O_EXCL
        )
        if open_modes.must_not_exist and open_modes.must_exist:
            raise NotImplementedError('O_EXCL without O_CREAT mode is not supported')

        if (not self.filesystem.is_windows_fs and
                self.filesystem.Exists(file_path)):
            # handle opening directory - only allowed under Posix with read-only mode
            obj = self.filesystem.ResolveObject(file_path)
            if isinstance(obj, FakeDirectory):
                if ((not open_modes.must_exist and not self.filesystem.is_macos)
                        or open_modes.can_write):
                    raise OSError(errno.EISDIR, 'Fake directory exists')
                dir_wrapper = FakeDirWrapper(obj, file_path, self.filesystem)
                file_des = self.filesystem.AddOpenFile(dir_wrapper)
                dir_wrapper.filedes = file_des
                return file_des

        # low level open is always binary
        str_flags = 'b'
        delete_on_close = False
        if hasattr(os, 'O_TEMPORARY'):
            delete_on_close = flags & os.O_TEMPORARY == os.O_TEMPORARY
        fake_file = FakeFileOpen(self.filesystem,
                                 delete_on_close=delete_on_close,
                                 raw_io=True)(file_path, str_flags, open_modes=open_modes)
        self.chmod(file_path, mode)
        return fake_file.fileno()

    def close(self, file_des):
        """Close a file descriptor.

        Args:
            file_des: An integer file descriptor for the file object requested.

        Raises:
            OSError: bad file descriptor.
            TypeError: if file descriptor is not an integer.
        """
        file_handle = self.filesystem.GetOpenFile(file_des)
        file_handle.close()

    def read(self, file_des, num_bytes):
        """Read number of bytes from a file descriptor, returns bytes read.

        Args:
            file_des: An integer file descriptor for the file object requested.
            num_bytes: Number of bytes to read from file.

        Returns:
            Bytes read from file.

        Raises:
            OSError: bad file descriptor.
            TypeError: if file descriptor is not an integer.
        """
        file_handle = self.filesystem.GetOpenFile(file_des)
        file_handle.raw_io = True
        return file_handle.read(num_bytes)

    def write(self, file_des, contents):
        """Write string to file descriptor, returns number of bytes written.

        Args:
            file_des: An integer file descriptor for the file object requested.
            contents: String of bytes to write to file.

        Returns:
            Number of bytes written.

        Raises:
            OSError: bad file descriptor.
            TypeError: if file descriptor is not an integer.
        """
        file_handle = self.filesystem.GetOpenFile(file_des)
        if isinstance(file_handle, FakeDirWrapper):
            raise OSError(errno.EBADF, 'Cannot write to directory')
        file_handle.raw_io = True
        file_handle._sync_io()
        file_handle.write(contents)
        file_handle.flush()
        return len(contents)

    @classmethod
    def stat_float_times(cls, newvalue=None):
        """Determine whether a file's time stamps are reported as floats or ints.

        Calling without arguments returns the current value. The value is shared
        by all instances of FakeOsModule.

        Args:
            newvalue: If `True`, mtime, ctime, atime are reported as floats.
                Otherwise, they are returned as ints (rounding down).
        """
        if newvalue is not None:
            cls._stat_float_times = bool(newvalue)
        return cls._stat_float_times

    def fstat(self, file_des):
        """Return the os.stat-like tuple for the FakeFile object of file_des.

        Args:
            file_des: The file descriptor of filesystem object to retrieve.

        Returns:
            The FakeStatResult object corresponding to entry_path.

        Raises:
            OSError: if the filesystem object doesn't exist.
        """
        # stat should return the tuple representing return value of os.stat
        file_object = self.filesystem.GetOpenFile(file_des).GetObject()
        return file_object.stat_result.copy()

    def umask(self, new_mask):
        """Change the current umask.

        Args:
            new_mask: (int) The new umask value.

        Returns:
            The old umask.

        Raises:
            TypeError: if new_mask is of an invalid type.
        """
        if not is_int_type(new_mask):
            raise TypeError('an integer is required')
        old_umask = self.filesystem.umask
        self.filesystem.umask = new_mask
        return old_umask

    def chdir(self, target_directory):
        """Change current working directory to target directory.

        Args:
            target_directory: The path to new current working directory.

        Raises:
            OSError: if user lacks permission to enter the argument directory
                or if the target is not a directory.
        """
        target_directory = self.filesystem.ResolvePath(target_directory, allow_fd=True)
        self.filesystem.ConfirmDir(target_directory)
        directory = self.filesystem.ResolveObject(target_directory)
        # A full implementation would check permissions all the way up the tree.
        if not directory.st_mode | PERM_EXE:
            raise OSError(errno.EACCES, 'Fake os module: permission denied',
                          directory)
        self.filesystem.cwd = target_directory

    def getcwd(self):
        """Return current working directory."""
        return self.filesystem.cwd

    if sys.version_info < (3, ):
        def getcwdu(self):
            """Return current working directory as unicode. Python 2 only."""
            return unicode(self.filesystem.cwd)  # pylint: disable=undefined-variable

    else:
        def getcwdb(self):
            """Return current working directory as bytes. Python 3 only."""
            return bytes(self.filesystem.cwd, locale.getpreferredencoding(False))

    def listdir(self, target_directory):
        """Return a list of file names in target_directory.

        Args:
            target_directory: Path to the target directory within the fake
                filesystem.

        Returns:
            A list of file names within the target directory in arbitrary
                order.

        Raises:
          OSError:  if the target is not a directory.
        """
        return self.filesystem.ListDir(target_directory)

    if sys.platform.startswith('linux') and sys.version_info >= (3, 3):
        def listxattr(self, path=None, follow_symlinks=True):
            """Dummy implementation that returns an empty list - used by shutil."""
            return []

    if sys.version_info >= (3, 5):
        def scandir(self, path=''):
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
            return self.filesystem.ScanDir(path)

    def _ClassifyDirectoryContents(self, root):
        """Classify contents of a directory as files/directories.

        Args:
            root: (str) Directory to examine.

        Returns:
            (tuple) A tuple consisting of three values: the directory examined,
            a list containing all of the directory entries, and a list
            containing all of the non-directory entries.
            (This is the same format as returned by the `os.walk` generator.)

        Raises:
            Nothing on its own, but be ready to catch exceptions generated by
            underlying mechanisms like `os.listdir`.
        """
        dirs = []
        files = []
        for entry in self.listdir(root):
            if self.path.isdir(self.path.join(root, entry)):
                dirs.append(entry)
            else:
                files.append(entry)
        return (root, dirs, files)

    def walk(self, top, topdown=True, onerror=None, followlinks=False):
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
        def do_walk(top, topMost=False):
            top = self.path.normpath(top)
            if not topMost and not followlinks and self.path.islink(top):
                return
            try:
                top_contents = self._ClassifyDirectoryContents(top)
            except OSError as exc:
                top_contents = None
                if onerror is not None:
                    onerror(exc)

            if top_contents is not None:
                if topdown:
                    yield top_contents

                for directory in top_contents[1]:
                    if not followlinks and self.path.islink(directory):
                        continue
                    for contents in do_walk(self.path.join(top, directory)):
                        yield contents

                if not topdown:
                    yield top_contents

        return do_walk(top, topMost=True)


    def readlink(self, path, dir_fd=None):
        """Read the target of a symlink.

        Args:
            path:  Symlink to read the target of.
            dir_fd: If not `None`, the file descriptor of a directory,
                with `path` being relative to this directory.
                New in Python 3.3.

        Returns:
            the string representing the path to which the symbolic link points.

        Raises:
            TypeError: if `path` is None
            OSError: (with errno=ENOENT) if path is not a valid path, or
                     (with errno=EINVAL) if path is valid, but is not a symlink.
        """
        path = self._path_with_dir_fd(path, self.readlink, dir_fd)
        return self.filesystem.ReadLink(path)

    def stat(self, entry_path, dir_fd=None, follow_symlinks=None):
        """Return the os.stat-like tuple for the FakeFile object of entry_path.

        Args:
            entry_path:  path to filesystem object to retrieve.
            dir_fd: (int) If not `None`, the file descriptor of a directory,
                with `entry_path` being relative to this directory.
                New in Python 3.3.
            follow_symlinks: (bool) If `False` and `entry_path` points to a symlink,
                the link itself is changed instead of the linked object.
                New in Python 3.3.

        Returns:
            The FakeStatResult object corresponding to entry_path.

        Raises:
            OSError: if the filesystem object doesn't exist.
        """
        if follow_symlinks is None:
            follow_symlinks = True
        elif sys.version_info < (3, 3):
            raise TypeError("stat() got an unexpected keyword argument 'follow_symlinks'")
        entry_path = self._path_with_dir_fd(entry_path, self.stat, dir_fd)
        return self.filesystem.GetStat(entry_path, follow_symlinks)

    def lstat(self, entry_path, dir_fd=None):
        """Return the os.stat-like tuple for entry_path, not following symlinks.

        Args:
            entry_path:  path to filesystem object to retrieve.
            dir_fd: If not `None`, the file descriptor of a directory, with
                `entry_path` being relative to this directory.
                New in Python 3.3.

        Returns:
            the FakeStatResult object corresponding to `entry_path`.

        Raises:
            OSError: if the filesystem object doesn't exist.
        """
        # stat should return the tuple representing return value of os.stat
        entry_path = self._path_with_dir_fd(entry_path, self.lstat, dir_fd)
        return self.filesystem.GetStat(entry_path, follow_symlinks=False)

    def remove(self, path, dir_fd=None):
        """Remove the FakeFile object at the specified file path.

        Args:
            path: Path to file to be removed.
            dir_fd: If not `None`, the file descriptor of a directory,
                with `path` being relative to this directory.
                New in Python 3.3.

        Raises:
            OSError: if path points to a directory.
            OSError: if path does not exist.
            OSError: if removal failed.
        """
        path = self._path_with_dir_fd(path, self.remove, dir_fd)
        self.filesystem.RemoveFile(path)

    def unlink(self, path, dir_fd=None):
        """Remove the FakeFile object at the specified file path.

        Args:
            path: Path to file to be removed.
            dir_fd: If not `None`, the file descriptor of a directory,
                with `path` being relative to this directory.
                New in Python 3.3.

        Raises:
            OSError: if path points to a directory.
            OSError: if path does not exist.
            OSError: if removal failed.
        """
        path = self._path_with_dir_fd(path, self.unlink, dir_fd)
        self.filesystem.RemoveFile(path)

    def rename(self, old_file_path, new_file_path, dir_fd=None):
        """Rename a FakeFile object at old_file_path to new_file_path,
        preserving all properties.
        Also replaces existing new_file_path object, if one existed (Unix only).

        Args:
            old_file_path:  Path to filesystem object to rename.
            new_file_path:  Path to where the filesystem object will live after this call.
            dir_fd: If not `None`, the file descriptor of a directory,
                with `old_file_path` being relative to this directory.
                New in Python 3.3.

        Raises:
            OSError: if old_file_path does not exist.
            OSError: if new_file_path is an existing directory.
            OSError: if new_file_path is an existing file (Windows only)
            OSError: if new_file_path is an existing file and could not be removed (Unix)
            OSError: if `dirname(new_file)` does not exist
            OSError: if the file would be moved to another filesystem (e.g. mount point)
        """
        old_file_path = self._path_with_dir_fd(old_file_path, self.rename, dir_fd)
        self.filesystem.RenameObject(old_file_path, new_file_path)

    if sys.version_info >= (3, 3):
        def replace(self, old_file_path, new_file_path):
            """Renames a FakeFile object at old_file_path to new_file_path,
            preserving all properties.
            Also replaces existing new_file_path object, if one existed.

            Args:
                old_file_path: Path to filesystem object to rename.
                new_file_path: Path to where the filesystem object will live
                    after this call.

            Raises:
                OSError: if old_file_path does not exist.
                OSError: if new_file_path is an existing directory.
                OSError: if new_file_path is an existing file and could
                    not be removed
                OSError: if `dirname(new_file)` does not exist
                OSError: if the file would be moved to another filesystem
                    (e.g. mount point)
            """
            self.filesystem.RenameObject(old_file_path, new_file_path, force_replace=True)

    def rmdir(self, target_directory, dir_fd=None):
        """Remove a leaf Fake directory.

        Args:
            target_directory: (str) Name of directory to remove.
            dir_fd: If not `None`, the file descriptor of a directory,
                with `target_directory` being relative to this directory.
                New in Python 3.3.

        Raises:
            OSError: if target_directory does not exist or is not a directory,
            or as per FakeFilesystem.RemoveObject. Cannot remove '.'.
        """
        target_directory= self._path_with_dir_fd(target_directory, self.rmdir, dir_fd)
        self.filesystem.RemoveDirectory(target_directory)

    def removedirs(self, target_directory):
        """Remove a leaf fake directory and all empty intermediate ones.

        Args:
            target_directory: the directory to be removed.

        Raises:
            OSError: if target_directory does not exist or is not a directory.
            OSError: if target_directory is not empty.
        """
        target_directory = self.filesystem.NormalizePath(target_directory)
        directory = self.filesystem.ConfirmDir(target_directory)
        if directory.contents:
            raise OSError(errno.ENOTEMPTY, 'Fake Directory not empty',
                          self.path.basename(target_directory))
        else:
            self.rmdir(target_directory)
        head, tail = self.path.split(target_directory)
        if not tail:
            head, tail = self.path.split(head)
        while head and tail:
            head_dir = self.filesystem.ConfirmDir(head)
            if head_dir.contents:
                break
            # only the top-level dir may not be a symlink
            self.filesystem.RemoveDirectory(head, allow_symlink=True)
            head, tail = self.path.split(head)

    def mkdir(self, dir_name, mode=PERM_DEF, dir_fd=None):
        """Create a leaf Fake directory.

        Args:
            dir_name: (str) Name of directory to create.
                Relative paths are assumed to be relative to '/'.
            mode: (int) Mode to create directory with.  This argument defaults to
                0o777.  The umask is applied to this mode.
            dir_fd: If not `None`, the file descriptor of a directory,
                with `dir_name` being relative to this directory.
                New in Python 3.3.

        Raises:
            OSError: if the directory name is invalid or parent directory is read only
                or as per FakeFilesystem.AddObject.
        """
        dir_name = self._path_with_dir_fd(dir_name, self.mkdir, dir_fd)
        try:
            self.filesystem.MakeDirectory(dir_name, mode)
        except IOError as e:
            if e.errno == errno.EACCES:
                raise OSError(e.errno, os.strerror(e.errno), dir_name)
            raise

    def makedirs(self, dir_name, mode=PERM_DEF, exist_ok=None):
        """Create a leaf Fake directory + create any non-existent parent dirs.

        Args:
            dir_name: (str) Name of directory to create.
            mode: (int) Mode to create directory (and any necessary parent
                directories) with. This argument defaults to 0o777.
                The umask is applied to this mode.
            exist_ok: (boolean) If exist_ok is False (the default), an OSError
                is raised if the target directory already exists.
                New in Python 3.2.

        Raises:
          OSError: if the directory already exists and exist_ok=False, or as per
          `FakeFilesystem.CreateDirectory()`.
        """
        if exist_ok is None:
            exist_ok = False
        elif sys.version_info < (3, 2):
            raise TypeError("makedir() got an unexpected keyword argument 'exist_ok'")
        self.filesystem.MakeDirectories(dir_name, mode, exist_ok)

    def _path_with_dir_fd(self, path, fct, dir_fd):
        """Return the path considering dir_fd. Raise on nmvalid parameters."""
        if dir_fd is not None:
            if sys.version_info < (3, 3):
                raise TypeError(
                    "%s() got an unexpected keyword argument 'dir_fd'" % fct.__name__)
            # check if fd is supported for the built-in real function
            real_fct = getattr(os, fct.__name__)
            if real_fct not in self.supports_dir_fd:
                raise NotImplementedError('dir_fd unavailable on this platform')
            if isinstance(path, int):
                raise ValueError(
                    "%s: Can't specify dir_fd without matching path" % fct.__name__)
            if not self.path.isabs(path):
                return self.path.join(
                    self.filesystem.GetOpenFile(dir_fd).GetObject().GetPath(), path)
        return path

    def access(self, path, mode, dir_fd=None, follow_symlinks=None):
        """Check if a file exists and has the specified permissions.

        Args:
            path: (str) Path to the file.
            mode: (int) Permissions represented as a bitwise-OR combination of
                os.F_OK, os.R_OK, os.W_OK, and os.X_OK.
            dir_fd: If not `None`, the file descriptor of a directory, with
                `path` being relative to this directory.
                New in Python 3.3.
            follow_symlinks: (bool) If `False` and `path` points to a symlink,
                the link itself is queried instead of the linked object.
                New in Python 3.3.

        Returns:
            bool, `True` if file is accessible, `False` otherwise.
        """
        if follow_symlinks is not None and sys.version_info < (3, 3):
            raise TypeError("access() got an unexpected keyword argument 'follow_symlinks'")
        path = self._path_with_dir_fd(path, self.access, dir_fd)
        try:
            stat_result = self.stat(path, follow_symlinks=follow_symlinks)
        except OSError as os_error:
            if os_error.errno == errno.ENOENT:
                return False
            raise
        return (mode & ((stat_result.st_mode >> 6) & 7)) == mode

    def chmod(self, path, mode, dir_fd=None, follow_symlinks=None):
        """Change the permissions of a file as encoded in integer mode.

        Args:
            path: (str) Path to the file.
            mode: (int) Permissions.
            dir_fd: If not `None`, the file descriptor of a directory, with `path`
                being relative to this directory.
                New in Python 3.3.
            follow_symlinks: (bool) If `False` and `path` points to a symlink,
                the link itself is queried instead of the linked object.
                New in Python 3.3.
        """
        if follow_symlinks is None:
            follow_symlinks = True
        elif sys.version_info < (3, 3):
            raise TypeError("chmod() got an unexpected keyword argument 'follow_symlinks'")
        path = self._path_with_dir_fd(path, self.chmod, dir_fd)
        self.filesystem.ChangeMode(path, mode, follow_symlinks)

    def lchmod(self, path, mode):
        """Change the permissions of a file as encoded in integer mode.
        If the file is a link, the permissions of the link are changed.

        Args:
          path: (str) Path to the file.
          mode: (int) Permissions.
        """
        if self.filesystem.is_windows_fs:
            raise (NameError, "name 'lchmod' is not defined")
        self.filesystem.ChangeMode(path, mode, follow_symlinks=False)

    def utime(self, path, times=None, ns=None, dir_fd=None, follow_symlinks=None):
        """Change the access and modified times of a file.

        Args:
            path: (str) Path to the file.
            times: 2-tuple of int or float numbers, of the form (atime, mtime) 
                which is used to set the access and modified times in seconds. 
                If None, both times are set to the current time.
            ns: 2-tuple of int numbers, of the form (atime, mtime)  which is 
                used to set the access and modified times in nanoseconds. 
                If None, both times are set to the current time.
                New in Python 3.3.
            dir_fd: If not `None`, the file descriptor of a directory, with `path`
                being relative to this directory.
                New in Python 3.3.
            follow_symlinks: (bool) If `False` and `path` points to a symlink,
                the link itself is queried instead of the linked object.
                New in Python 3.3.
    
            Raises:
                TypeError: If anything other than the expected types is 
                    specified in the passed `times` or `ns` tuple, 
                    or if the tuple length is not equal to 2.
                ValueError: If both times and ns are specified.
        """
        if follow_symlinks is None:
            follow_symlinks = True
        elif sys.version_info < (3, 3):
            raise TypeError("utime() got an unexpected keyword argument 'follow_symlinks'")
        path = self._path_with_dir_fd(path, self.utime, dir_fd)
        if ns is not None and sys.version_info < (3, 3):
            raise TypeError("utime() got an unexpected keyword argument 'ns'")

        self.filesystem.UpdateTime(path, times, ns, follow_symlinks)

    def chown(self, path, uid, gid, dir_fd=None, follow_symlinks=None):
        """Set ownership of a faked file.

        Args:
            path: (str) Path to the file or directory.
            uid: (int) Numeric uid to set the file or directory to.
            gid: (int) Numeric gid to set the file or directory to.
            dir_fd: (int) If not `None`, the file descriptor of a directory,
                with `path` being relative to this directory.
                New in Python 3.3.
            follow_symlinks: (bool) If `False` and path points to a symlink,
                the link itself is changed instead of the linked object.
                New in Python 3.3.

        Raises:
            OSError: if path does not exist.

        `None` is also allowed for `uid` and `gid`.  This permits `os.rename` to
        use `os.chown` even when the source file `uid` and `gid` are `None` (unset).
        """
        if follow_symlinks is None:
            follow_symlinks = True
        elif sys.version_info < (3, 3):
            raise TypeError("chown() got an unexpected keyword argument 'follow_symlinks'")
        path = self._path_with_dir_fd(path, self.chown, dir_fd)
        try:
            file_object = self.filesystem.ResolveObject(path, follow_symlinks, allow_fd=True)
        except IOError as io_error:
            if io_error.errno == errno.ENOENT:
                raise OSError(errno.ENOENT,
                              'No such file or directory in fake filesystem',
                              path)
            raise
        if not ((is_int_type(uid) or uid is None) and
                (is_int_type(gid) or gid is None)):
            raise TypeError("An integer is required")
        if uid != -1:
            file_object.st_uid = uid
        if gid != -1:
            file_object.st_gid = gid

    def mknod(self, filename, mode=None, device=None, dir_fd=None):
        """Create a filesystem node named 'filename'.

        Does not support device special files or named pipes as the real os
        module does.

        Args:
            filename: (str) Name of the file to create
            mode: (int) Permissions to use and type of file to be created.
                Default permissions are 0o666.  Only the stat.S_IFREG file type
                is supported by the fake implementation.  The umask is applied
                to this mode.
            device: not supported in fake implementation
            dir_fd: If not `None`, the file descriptor of a directory,
                with `filename` being relative to this directory.
                New in Python 3.3.

        Raises:
          OSError: if called with unsupported options or the file can not be
          created.
        """
        if self.filesystem.is_windows_fs:
            raise(AttributeError, "module 'os' has no attribute 'mknode'")
        if mode is None:
            # note that a default value of 0o600 without a device type is
            # documented - this is not how it seems to work
            mode = stat.S_IFREG | 0o600
        if device or not mode & stat.S_IFREG:
            raise OSError(errno.EPERM,
                          'Fake os mknod implementation only supports '
                          'regular files.')

        filename = self._path_with_dir_fd(filename, self.mknod, dir_fd)
        head, tail = self.path.split(filename)
        if not tail:
            if self.filesystem.Exists(head, check_link=True):
                raise OSError(errno.EEXIST, 'Fake filesystem: %s: %s' % (
                    os.strerror(errno.EEXIST), filename))
            raise OSError(errno.ENOENT, 'Fake filesystem: %s: %s' % (
                os.strerror(errno.ENOENT), filename))
        if tail in (b'.', u'.', b'..', u'..'):
            raise OSError(errno.ENOENT, 'Fake fileystem: %s: %s' % (
                os.strerror(errno.ENOENT), filename))
        if self.filesystem.Exists(filename, check_link=True):
            raise OSError(errno.EEXIST, 'Fake fileystem: %s: %s' % (
                os.strerror(errno.EEXIST), filename))
        try:
            self.filesystem.AddObject(head, FakeFile(
                tail, mode & ~self.filesystem.umask,
                filesystem=self.filesystem))
        except IOError as e:
            raise OSError(e.errno, 'Fake filesystem: %s: %s' % (
                os.strerror(e.errno), filename))

    def symlink(self, link_target, path, dir_fd=None):
        """Creates the specified symlink, pointed at the specified link target.

        Args:
            link_target: The target of the symlink.
            path: Path to the symlink to create.
            dir_fd: If not `None`, the file descriptor of a directory,
                with `link_target` being relative to this directory.
                New in Python 3.3.

        Raises:
            OSError:  if the file already exists.
        """
        link_target = self._path_with_dir_fd(link_target, self.symlink, dir_fd)
        self.filesystem.CreateLink(path, link_target, create_missing_dirs=False)

    def link(self, oldpath, newpath, dir_fd=None):
        """Create a hard link at new_path, pointing at old_path.

        Args:
            old_path: An existing link to the target file.
            new_path: The destination path to create a new link at.
            dir_fd: If not `None`, the file descriptor of a directory, with `oldpath`
                being relative to this directory.
                New in Python 3.3.

        Returns:
            The FakeFile object referred to by `oldpath`.

        Raises:
            OSError:  if something already exists at new_path.
            OSError:  if the parent directory doesn't exist.
            OSError:  if on Windows before Python 3.2.
        """
        oldpath = self._path_with_dir_fd(oldpath, self.link, dir_fd)
        self.filesystem.CreateHardLink(oldpath, newpath)

    def fsync(self, file_des):
        """Perform fsync for a fake file (in other words, do nothing).

        Args:
            file_des: The file descriptor of the open file.

        Raises:
            OSError: file_des is an invalid file descriptor.
            TypeError: file_des is not an integer.
        """
        # Throw an error if file_des isn't valid
        if 0 <= file_des < NR_STD_STREAMS:
            raise OSError(errno.EINVAL, 'Invalid file descriptor')
        file_object = self.filesystem.GetOpenFile(file_des)
        if self.filesystem.is_windows_fs:
            if (not hasattr(file_object, 'allow_update') or
                    not file_object.allow_update):
                raise OSError(errno.EBADF, 'File is not open for writing')



    def fdatasync(self, file_des):
        """Perform fdatasync for a fake file (in other words, do nothing).

        Args:
            file_des: The file descriptor of the open file.

        Raises:
            OSError: file_des is an invalid file descriptor.
            TypeError: file_des is not an integer.
        """
        # Throw an error if file_des isn't valid
        if self.filesystem.is_windows_fs or self.filesystem.is_macos:
            raise AttributeError("module 'os' has no attribute 'fdatasync'")
        if 0 <= file_des < NR_STD_STREAMS:
            raise OSError(errno.EINVAL, 'Invalid file descriptor')
        self.filesystem.GetOpenFile(file_des)

    def __getattr__(self, name):
        """Forwards any unfaked calls to the standard os module."""
        return getattr(self._os_module, name)


class FakeIoModule(object):
    """Uses FakeFilesystem to provide a fake io module replacement.

    Currently only used to wrap `io.open()` which is an alias to `open()`.

    You need a fake_filesystem to use this:
    filesystem = fake_filesystem.FakeFilesystem()
    my_io_module = fake_filesystem.FakeIoModule(filesystem)
    """

    def __init__(self, filesystem):
        """
        Args:
            filesystem: FakeFilesystem used to provide file system information.
        """
        self.filesystem = filesystem
        self._io_module = io

    def open(self, file_path, mode='r', buffering=-1, encoding=None,
             errors=None, newline=None, closefd=True, opener=None):
        """Redirect the call to FakeFileOpen.
        See FakeFileOpen.Call() for description.
        """
        if opener is not None and sys.version_info < (3, 3):
            raise TypeError("open() got an unexpected keyword argument 'opener'")
        fake_open = FakeFileOpen(self.filesystem, use_io=True)
        return fake_open(file_path, mode, buffering, encoding, errors, newline, closefd, opener)

    def __getattr__(self, name):
        """Forwards any unfaked calls to the standard io module."""
        return getattr(self._io_module, name)


class FakeFileWrapper(object):
    """Wrapper for a stream object for use by a FakeFile object.

    If the wrapper has any data written to it, it will propagate to
    the FakeFile object on close() or flush().
    """
    def __init__(self, file_object, file_path, update=False, read=False,
                 append=False, delete_on_close=False, filesystem=None,
                 newline=None, binary=True, closefd=True, encoding=None,
                 errors=None, raw_io=False, is_stream=False, use_io=True):
        self._file_object = file_object
        self._file_path = file_path
        self._append = append
        self._read = read
        self.allow_update = update
        self._closefd = closefd
        self._file_epoch = file_object.epoch
        self.raw_io = raw_io
        self._binary = binary
        self.is_stream = is_stream
        contents = file_object.byte_contents
        self._encoding = encoding
        errors = errors or 'strict'
        if encoding:
            file_wrapper = FakeFileWrapper(
                file_object, file_path, update, read, append,
                delete_on_close=False, filesystem=filesystem,
                newline=None, binary=True, closefd=closefd, is_stream=True)
            codec_info = codecs.lookup(encoding)
            self._io = codecs.StreamReaderWriter(file_wrapper, codec_info.streamreader,
                                                 codec_info.streamwriter, errors)
        else:
            if not binary and sys.version_info >= (3, 0):
                io_class = io.StringIO
            else:
                io_class = io.BytesIO
            io_args = {} if binary else {'newline': newline}
            if contents and not binary:
                contents = contents.decode(encoding or locale.getpreferredencoding(False),
                                           errors=errors)
            if contents and not update:
                self._io = io_class(contents, **io_args)
            else:
                self._io = io_class(**io_args)

        if contents:
            if update:
                if not encoding:  # already written with encoding
                    self._io.write(contents)
                if not append:
                    self._io.seek(0)
                else:
                    self._read_whence = 0
                    if read and not use_io:
                        self._read_seek = 0
                    else:
                        self._read_seek = self._io.tell()
        else:
            self._read_whence = 0
            self._read_seek = 0

        if delete_on_close:
            assert filesystem, 'delete_on_close=True requires filesystem'
        self._filesystem = filesystem
        self.delete_on_close = delete_on_close
        # override, don't modify FakeFile.name, as FakeFilesystem expects
        # it to be the file name only, no directories.
        self.name = file_object.opened_as
        self.filedes = None

    def __enter__(self):
        """To support usage of this fake file with the 'with' statement."""
        return self

    def __exit__(self, type, value, traceback):  # pylint: disable=redefined-builtin
        """To support usage of this fake file with the 'with' statement."""
        self.close()

    def _raise(self, message):
        if self.raw_io:
            raise OSError(errno.EBADF, message)
        if sys.version_info[0] == 2:
            raise IOError(message)
        raise io.UnsupportedOperation(message)

    def GetObject(self):
        """Return the FakeFile object that is wrapped by the current instance."""
        return self._file_object

    def fileno(self):
        """Return the file descriptor of the file object."""
        return self.filedes

    def close(self):
        """Close the file."""
        # ignore closing a closed file
        if self not in self._filesystem.open_files:
            return
        # for raw io, all writes are flushed immediately
        if self.allow_update and not self.raw_io:
            self._file_object.SetContents(self._io.getvalue(), self._encoding)
        if self._closefd:
            self._filesystem.CloseOpenFile(self.filedes)
        if self.delete_on_close:
            self._filesystem.RemoveObject(self.GetObject().GetPath())

    def flush(self):
        """Flush file contents to 'disk'."""
        self._check_open_file()
        if self.allow_update:
            self._io.flush()
            self._file_object.SetContents(self._io.getvalue(), self._encoding)
            self._file_epoch = self._file_object.epoch

    def seek(self, offset, whence=0):
        """Move read/write pointer in 'file'."""
        self._check_open_file()
        if not self._append:
            self._io.seek(offset, whence)
        else:
            self._read_seek = offset
            self._read_whence = whence
        if not self.is_stream:
            self.flush()

    def tell(self):
        """Return the file's current position.

        Returns:
          int, file's current position in bytes.
        """
        self._check_open_file()
        if self._flushes_after_tell():
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

    def _flushes_after_read(self):
        return (not self.is_stream and
                (not self._filesystem.is_windows_fs or
                 sys.version_info[0] > 2))

    def _flushes_after_tell(self):
        return (not self.is_stream and
                (self._filesystem.is_macos or
                 sys.version_info[0] > 2))

    def _sync_io(self):
        """Update the stream with changes to the file object contents."""
        if self._file_epoch == self._file_object.epoch:
            return

        if isinstance(self._io, io.BytesIO):
            contents = self._file_object.byte_contents
        else:
            contents = self._file_object.contents

        is_stream_reader_writer = isinstance(self._io, codecs.StreamReaderWriter)
        if is_stream_reader_writer:
            self._io.stream.allow_update = True
        whence = self._io.tell()
        self._io.seek(0)
        self._io.truncate()
        self._io.write(contents)
        if self._append:
            self._io.seek(0, os.SEEK_END)
        else:
            self._io.seek(whence)

        if is_stream_reader_writer:
            self._io.stream.allow_update = False
        self._file_epoch = self._file_object.epoch

    def _read_wrapper(self, name):
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

    def _other_wrapper(self, name, writing):
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
            if not writing or sys.version_info[0] > 2:
                return ret_value

        return other_wrapper

    def _truncate_wrapper(self):
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
                self._file_object.SetSize(size)
                buffer_size = len(self._io.getvalue())
                if buffer_size < size:
                    self._io.seek(buffer_size)
                    self._io.write('\0' * (size - buffer_size))
                    self._file_object.SetContents(self._io.getvalue(), self._encoding)
            if sys.version_info[0] > 2:
                return size

        return truncate_wrapper

    def _write_wrapper(self, name):
        """Wrap write() to adapt return value for Python 2.

        Returns:
            Wrapper which is described below.
        """
        io_attr = getattr(self._io, name)

        def write_wrapper(*args, **kwargs):
            """Wrap trunctae call to call flush after truncate."""
            ret_value = io_attr(*args, **kwargs)
            if sys.version_info[0] > 2:
                return ret_value

        return write_wrapper

    def Size(self):
        """Return the content size in bytes of the wrapped file."""
        return self._file_object.st_size

    def __getattr__(self, name):
        if self._file_object.IsLargeFile():
            raise FakeLargeFileIoException(self._file_path)

        reading = name.startswith('read') or name == 'next'
        truncate = name == 'truncate'
        writing = name.startswith('write') or truncate
        if reading or writing:
            self._check_open_file()
        if not self._read and reading:
            def read_error(*args, **kwargs):
                """Throw an error unless the argument is zero."""
                if args and args[0] == 0:
                    if self._filesystem.is_windows_fs and self.raw_io:
                        return b'' if self._binary else u''
                self._raise('File is not open for reading.')

            return read_error

        if not self.allow_update and writing:
            def write_error(*args, **kwargs):
                """Throw an error."""
                if self.raw_io:
                    if self._filesystem.is_windows_fs and args and len(args[0]) == 0:
                        return 0
                self._raise('File is not open for writing.')

            return write_error

        if reading:
            self._sync_io()
            if self._flushes_after_read():
                self.flush()
        if truncate:
            return self._truncate_wrapper()
        if self._append:
            if reading:
                return self._read_wrapper(name)
            else:
                return self._other_wrapper(name, writing)
        if writing:
            return self._write_wrapper(name)

        return getattr(self._io, name)

    def _check_open_file(self):
        if not self.is_stream and not self in self._filesystem.open_files:
            raise ValueError('I/O operation on closed file')

    def __iter__(self):
        if not self._read:
            self._raise('File is not open for reading')
        return self._io.__iter__()


class StandardStreamWrapper(object):
    """Wrapper for a system standard stream to be used in open files list.
    """
    def __init__(self, stream_object):
        self._stream_object = stream_object
        self.filedes = None

    def GetObject(self):
        return self._stream_object

    def fileno(self):
        """Return the file descriptor of the wrapped standard stream."""
        return self.filedes

    def close(self):
        """We do not support closing standard streams."""
        pass


class FakeDirWrapper(object):
    """Wrapper for a FakeDirectory object to be used in open files list.
    """
    def __init__(self, file_object, file_path, filesystem):
        self._file_object = file_object
        self._file_path = file_path
        self._filesystem = filesystem
        self.filedes = None

    def GetObject(self):
        """Return the FakeFile object that is wrapped by the current instance."""
        return self._file_object

    def fileno(self):
        """Return the file descriptor of the file object."""
        return self.filedes

    def close(self):
        """Close the directory."""
        self._filesystem.CloseOpenFile(self.filedes)


class FakeFileOpen(object):
    """Faked `file()` and `open()` function replacements.

    Returns FakeFile objects in a FakeFilesystem in place of the `file()`
    or `open()` function.
    """
    __name__ = 'FakeFileOpen'

    def __init__(self, filesystem, delete_on_close=False, use_io=False, raw_io=False):
        """init.

        Args:
          filesystem:  FakeFilesystem used to provide file system information
          delete_on_close:  optional boolean, deletes file on close()
          use_io: if True, the io.open() version is used (ignored for Python 3,
                  where io.open() is an alias to open() )
        """
        self.filesystem = filesystem
        self._delete_on_close = delete_on_close
        self._use_io = (use_io or sys.version_info[0] > 2 or
                        platform.python_implementation() == 'PyPy' or
                        self.filesystem.is_macos)
        self.raw_io = raw_io

    def __call__(self, *args, **kwargs):
        """Redirects calls to file() or open() to appropriate method."""
        if self._use_io:
            return self.Call(*args, **kwargs)
        else:
            return self._call_ver2(*args, **kwargs)

    def _call_ver2(self, file_path, mode='r', buffering=-1, flags=None, open_modes=None):
        """Limits args of open() or file() for Python 2.x versions."""
        # Backwards compatibility, mode arg used to be named flags
        mode = flags or mode
        return self.Call(file_path, mode, buffering, open_modes=open_modes)

    def Call(self, file_, mode='r', buffering=-1, encoding=None,
             errors=None, newline=None, closefd=True, opener=None,
             open_modes=None):
        """Return a file-like object with the contents of the target file object.

        Args:
            file_: Path to target file or a file descriptor.
            mode: Additional file modes. All r/w/a/x r+/w+/a+ modes are
                supported. 't', and 'U' are ignored, e.g., 'wU' is treated
                as 'w'. 'b' sets binary mode, no end of line translations
                in StringIO.
            buffering: ignored. (Used for signature compliance with
                __builtin__.open)
            encoding: The encoding used to encode unicode strings / decode
                bytes.
            errors: (str) Defines how encoding errors are handled.
            newline: Controls universal newlines, passed to stream object.
            closefd: If a file descriptor rather than file name is passed,
                and this is set to `False`, then the file descriptor is kept
                open when file is closed.
            opener: not supported.
            open_modes: Modes for opening files if called from low-level API.

        Returns:
            A file-like object containing the contents of the target file.

        Raises:
            IOError: if the target object is a directory, the path is invalid
                or permission is denied.
        """
        orig_modes = mode  # Save original modes for error messages.
        # Binary mode for non 3.x or set by mode
        binary = sys.version_info[0] == 2 or 'b' in mode
        # Normalize modes. Ignore 't' and 'U'.
        mode = mode.replace('t', '').replace('b', '')
        mode = mode.replace('rU', 'r').replace('U', 'r')

        if not self.raw_io:
            if mode not in _OPEN_MODE_MAP:
                raise ValueError('Invalid mode: %r' % orig_modes)
            open_modes = _OpenModes(*_OPEN_MODE_MAP[mode])

        file_object = None
        filedes = None
        # opening a file descriptor
        if isinstance(file_, int):
            filedes = file_
            wrapper = self.filesystem.GetOpenFile(filedes)
            self._delete_on_close = wrapper.delete_on_close
            file_object = self.filesystem.GetOpenFile(filedes).GetObject()
            file_path = file_object.name
        else:
            file_path = file_
            real_path = self.filesystem.ResolvePath(file_path, raw_io=self.raw_io)
            if self.filesystem.Exists(file_path):
                file_object = self.filesystem.GetObjectFromNormalizedPath(real_path)
            closefd = True

        error_class = OSError if self.raw_io else IOError
        if (open_modes.must_not_exist and
                (file_object or self.filesystem.IsLink(file_path) and
                 not self.filesystem.is_windows_fs)):
            raise error_class(errno.EEXIST, 'File exists', file_path)
        if file_object:
            if ((open_modes.can_read and not file_object.st_mode & PERM_READ) or
                    (open_modes.can_write and not file_object.st_mode & PERM_WRITE)):
                raise error_class(errno.EACCES, 'Permission denied', file_path)
            if open_modes.can_write:
                if open_modes.truncate:
                    file_object.SetContents('')
        else:
            if open_modes.must_exist:
                raise error_class(errno.ENOENT, 'No such file or directory', file_path)
            file_object = self.filesystem.CreateFileInternally(
                real_path, create_missing_dirs=False, apply_umask=True, raw_io=self.raw_io)

        if stat.S_ISDIR(file_object.st_mode):
            if self.filesystem.is_windows_fs:
                raise error_class(errno.EACCES, 'Fake file object: is a directory', file_path)
            else:
                raise error_class(errno.EISDIR, 'Fake file object: is a directory', file_path)

        # if you print obj.name, the argument to open() must be printed. Not the
        # abspath, not the filename, but the actual argument.
        file_object.opened_as = file_path

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
                                   raw_io=self.raw_io,
                                   use_io=self._use_io)
        if filedes is not None:
            fakefile.filedes = filedes
            # replace the file wrapper
            self.filesystem.open_files[filedes] = fakefile
        else:
            fakefile.filedes = self.filesystem.AddOpenFile(fakefile)
        return fakefile


def _RunDoctest():
    import doctest
    from pyfakefs import fake_filesystem  # pylint: disable=import-self
    return doctest.testmod(fake_filesystem)


if __name__ == '__main__':
    _RunDoctest()
