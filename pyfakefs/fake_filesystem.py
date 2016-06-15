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
#
# pylint: disable-msg=W0612,W0613,C6409

"""A fake filesystem implementation for unit testing.

Includes:
  FakeFile:  Provides the appearance of a real file.
  FakeDirectory: Provides the appearance of a real dir.
  FakeFilesystem:  Provides the appearance of a real directory hierarchy.
  FakeOsModule:  Uses FakeFilesystem to provide a fake os module replacement.
  FakePathModule:  Faked os.path module replacement.
  FakeFileOpen:  Faked file() and open() function replacements.

Usage:
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
...     print line.rstrip()
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

import errno
import heapq
import io
import os
import stat
import sys
import time
import warnings
import binascii
from collections import namedtuple

if sys.version_info < (3, 0):
  import cStringIO

__pychecker__ = 'no-reimportself'

__version__ = '2.8'

PERM_READ = 0o400      # Read permission bit.
PERM_WRITE = 0o200     # Write permission bit.
PERM_EXE = 0o100       # Write permission bit.
PERM_DEF = 0o777       # Default permission bits.
PERM_DEF_FILE = 0o666  # Default permission bits (regular file)
PERM_ALL = 0o7777      # All permission bits.

_OPEN_MODE_MAP = {
    # mode name:(file must exist, need read, need write,
    #            truncate [implies need write], append)
    'r': (True, True, False, False, False),
    'w': (False, False, True, True, False),
    'a': (False, False, True, False, True),
    'r+': (True, True, True, False, False),
    'w+': (False, True, True, True, False),
    'a+': (False, True, True, False, True),
    }

_MAX_LINK_DEPTH = 20

FAKE_PATH_MODULE_DEPRECATION = ('Do not instantiate a FakePathModule directly; '
                                'let FakeOsModule instantiate it.  See the '
                                'FakeOsModule docstring for details.')


class Error(Exception):
  pass

_is_windows = sys.platform.startswith('win')
_is_cygwin = sys.platform == 'cygwin'

if _is_windows:
  # On Windows, raise WindowsError instead of OSError if available
  OSError = WindowsError  # pylint: disable-msg=E0602,W0622


class FakeLargeFileIoException(Error):
  def __init__(self, file_path):
    Error.__init__(self,
                   'Read and write operations not supported for '
                   'fake large file: %s' % file_path)


def CopyModule(old):
  """Recompiles and creates new module object."""
  saved = sys.modules.pop(old.__name__, None)
  new = __import__(old.__name__)
  sys.modules[old.__name__] = saved
  return new


class Hexlified(object):
  """Wraps binary data in non-binary string"""
  def __init__(self, contents):
    self.contents = binascii.hexlify(contents).decode('utf-8')

  def __len__(self):
    return len(self.contents)//2

  def __getitem__(self, item):
    return self.contents.__getitem__(item)

  def recover(self, binary):
    if binary:
      return binascii.unhexlify(bytearray(self.contents, 'utf-8'))
    else:
      return binascii.unhexlify(bytearray(self.contents, 'utf-8')).decode(sys.getdefaultencoding())


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
               contents=None, filesystem=None):
    """init.

    Args:
      name:  name of the file/directory, without parent path information
      st_mode:  the stat.S_IF* constant representing the file type (i.e.
        stat.S_IFREG, stat.SIFDIR)
      contents:  the contents of the filesystem object; should be a string for
        regular files, and a list of other FakeFile or FakeDirectory objects
        for FakeDirectory objects
      filesystem: if set, the fake filesystem where the file is created
    """
    self.name = name
    self.st_mode = st_mode
    self.contents = contents
    self.filesystem = filesystem
    self.epoch = 0
    self._st_ctime = time.time()    # times are accessed through properties
    self._st_atime = self._st_ctime
    self._st_mtime = self._st_ctime
    if contents:
      self.st_size = len(contents)
    else:
      self.st_size = 0
    self.st_nlink = 0
    self.st_ino = None
    self.st_dev = None

    # Non faked features, write setter methods for faking them
    self.st_uid = None
    self.st_gid = None
    # shall be set on creating the file from the file system to get access to fs available space

  @property
  def st_ctime(self):
      return (self._st_ctime if FakeOsModule.stat_float_times()
              else int(self._st_ctime))

  @property
  def st_atime(self):
      return (self._st_atime if FakeOsModule.stat_float_times()
              else int(self._st_atime))

  @property
  def st_mtime(self):
      return (self._st_mtime if FakeOsModule.stat_float_times()
              else int(self._st_mtime))

  @st_ctime.setter
  def st_ctime(self, val):
      self._st_ctime = val

  @st_atime.setter
  def st_atime(self, val):
      self._st_atime = val

  @st_mtime.setter
  def st_mtime(self, val):
      self._st_mtime = val

  def SetLargeFileSize(self, st_size):
    """Sets the self.st_size attribute and replaces self.content with None.

    Provided specifically to simulate very large files without regards
    to their content (which wouldn't fit in memory)

    Args:
      st_size: The desired file size

    Raises:
      IOError: if the st_size is not a non-negative integer,
               or if st_size exceeds the available file system space
    """
    # the st_size should be an positive integer value
    int_types = (int, long) if sys.version_info < (3, 0) else int
    if not isinstance(st_size, int_types) or st_size < 0:
      raise IOError(errno.ENOSPC,
                    'Fake file object: can not create non negative integer '
                    'size=%r fake file' % st_size,
                    self.name)
    if self.st_size:
      self.SetSize(0)
    if self.filesystem:
      self.filesystem.ChangeDiskUsage(st_size, self.name, self.st_dev)
    self.st_size = st_size
    self.contents = None

  def IsLargeFile(self):
    """Return True if this file was initialized with size but no contents."""
    return self.contents is None

  def _SetInitialContents(self, contents):
    """Sets the file contents and size.
       Called internally after initial file creation.

    Args:
      contents: string, new content of file.

    Raises:
      IOError: if the st_size is not a non-negative integer,
               or if st_size exceeds the available file system space
    """
    if sys.version_info >= (3, 0) and isinstance(contents, bytes):
      st_size = len(contents)
      # Wrap byte arrays into a safe format
      contents = Hexlified(contents)
    elif sys.version_info < (3, 0) and isinstance(contents, str):
      st_size = len(contents)
    elif isinstance(contents, Hexlified):
      st_size = len(contents)
    else:
      st_size = len(contents.encode('utf-8'))

    if self.contents:
      self.SetSize(0)
    current_size = self.st_size or 0
    self.contents = contents
    self.st_size = st_size
    if self.filesystem:
      self.filesystem.ChangeDiskUsage(self.st_size - current_size, self.name, self.st_dev)
    self.epoch += 1

  def SetContents(self, contents):
    """Sets the file contents and size and increases the modification time.

    Args:
      contents: string, new content of file.

    Raises:
      IOError: if the st_size is not a non-negative integer,
               or if st_size exceeds the available file system space
    """
    self._SetInitialContents(contents)
    self.st_ctime = time.time()
    self.st_mtime = self._st_ctime

  def GetSize(self):
    """Returns the size in bytes of the file contents."""
    return self.st_size

  def SetSize(self, st_size):
    """Resizes file content, padding with nulls if new size exceeds the old.

    Args:
      st_size: The desired size for the file.

    Raises:
      IOError: if the st_size arg is not a non-negative integer
               or if st_size exceeds the available file system space
    """

    if not isinstance(st_size, int) or st_size < 0:
      raise IOError(errno.ENOSPC,
                    'Fake file object: can not create non negative integer '
                    'size=%r fake file' % st_size,
                    self.name)

    current_size = self.st_size or 0
    if self.filesystem:
      self.filesystem.ChangeDiskUsage(st_size - current_size, self.name, self.st_dev)
    if self.contents:
      if st_size < current_size:
        self.contents = self.contents[:st_size]
      else:
        self.contents = '%s%s' % (self.contents, '\0' * (st_size - current_size))
    self.st_size = st_size
    self.epoch += 1

  def SetATime(self, st_atime):
    """Set the self.st_atime attribute.

    Args:
      st_atime: The desired atime.
    """
    self.st_atime = st_atime

  def SetMTime(self, st_mtime):
    """Set the self.st_mtime attribute.

    Args:
      st_mtime: The desired mtime.
    """
    self.st_mtime = st_mtime

  def __str__(self):
    return '%s(%o)' % (self.name, self.st_mode)

  def SetIno(self, st_ino):
    """Set the self.st_ino attribute.

    Args:
      st_ino: The desired inode.
    """
    self.st_ino = st_ino


class FakeDirectory(FakeFile):
  """Provides the appearance of a real dir."""

  def __init__(self, name, perm_bits=PERM_DEF, filesystem=None):
    """init.

    Args:
      name:  name of the file/directory, without parent path information
      perm_bits: permission bits. defaults to 0o777.
      filesystem: if set, the fake filesystem where the directory is created
    """
    FakeFile.__init__(self, name, stat.S_IFDIR | perm_bits, {}, filesystem=filesystem)

  def AddEntry(self, path_object):
    """Adds a child FakeFile to this directory.

    Args:
      path_object:  FakeFile instance to add as a child of this directory
    """
    self.contents[path_object.name] = path_object
    path_object.st_nlink += 1
    path_object.st_dev = self.st_dev
    if self.filesystem and path_object.st_nlink == 1:
      self.filesystem.ChangeDiskUsage(path_object.GetSize(), path_object.name, self.st_dev)

  def GetEntry(self, pathname_name):
    """Retrieves the specified child file or directory.

    Args:
      pathname_name: basename of the child object to retrieve
    Returns:
      string, file contents
    Raises:
      KeyError: if no child exists by the specified name
    """
    return self.contents[pathname_name]

  def RemoveEntry(self, pathname_name):
    """Removes the specified child file or directory.

    Args:
      pathname_name: basename of the child object to remove

    Raises:
      KeyError: if no child exists by the specified name
    """
    entry = self.contents[pathname_name]
    if self.filesystem and entry.st_nlink == 1:
      self.filesystem.ChangeDiskUsage(-entry.GetSize(), pathname_name, entry.st_dev)

    entry.st_nlink -= 1
    assert entry.st_nlink >= 0

    del self.contents[pathname_name]

  def GetSize(self):
    """Get the size of all files contained in this directory tree"""
    return sum([item[1].GetSize() for item in self.contents.items()])

  def __str__(self):
    rc = super(FakeDirectory, self).__str__() + ':\n'
    for item in self.contents:
      item_desc = self.contents[item].__str__()
      for line in item_desc.split('\n'):
        if line:
          rc = rc + '  ' + line + '\n'
    return rc


class FakeFilesystem(object):
  """Provides the appearance of a real directory tree for unit testing."""
  def __init__(self, path_separator=os.path.sep, total_size=None):
    """init.

    Args:
      path_separator:  optional substitute for os.path.sep

      Example usage to emulate real file systems:
         filesystem = FakeFilesystem(alt_path_separator='/' if _is_windows else None)
    """
    self.path_separator = path_separator
    self.alternative_path_separator = os.path.altsep
    if path_separator != os.sep:
      self.alternative_path_separator = None
    self.is_case_sensitive = not _is_windows and sys.platform != 'darwin'
    self.supports_drive_letter = _is_windows
    self.root = FakeDirectory(self.path_separator, filesystem=self)
    self.cwd = self.root.name
    # We can't query the current value without changing it:
    self.umask = os.umask(0o22)
    os.umask(self.umask)
    # A list of open file objects. Their position in the list is their
    # file descriptor number
    self.open_files = []
    # A heap containing all free positions in self.open_files list
    self.free_fd_heap = []
    # last used numbers for inodes (st_ino) and devices (st_dev)
    self.last_ino = 0
    self.last_dev = 0
    self.mount_points = {}
    self.AddMountPoint(self.root.name, total_size)

  def AddMountPoint(self, path, total_size=None):
    """Adds a new mount point for a filesystem device.
       The mount point gets a new unique device number.

    Args:
      path: The root path for the ew mount path.

      total_size: the new total size of the added filesystem device in bytes
                  Defaults to infinite size.

    Returns:
        The newly created mount point dict.

    Raises:
      OSError: if trying to mount an existing mount point again
    """
    path = self.NormalizePath(path)
    if path in self.mount_points:
      raise OSError(errno.EEXIST, 'Mount point cannot be added twice', path)
    self.last_dev += 1
    self.mount_points[path] = {
      'idev': self.last_dev, 'total_size': total_size, 'used_size': 0
    }
    # special handling for root path: has been created before
    root_dir = self.root if path == self.root.name else self.CreateDirectory(path)
    root_dir.st_dev = self.last_dev
    return self.mount_points[path]

  def _AutoMountDriveIfNeeded(self, path, force=False):
    if self.supports_drive_letter and (force or not self._MountPointForPath(path)):
      drive = self.SplitDrive(path)[0]
      if drive:
        return self.AddMountPoint(path=drive)

  def _MountPointForPath(self, path):
    path = self.NormalizePath(path)
    if path in self.mount_points:
      return self.mount_points[path]
    mount_path = ''
    drive = self.SplitDrive(path)[0]
    if not self.is_case_sensitive:
      drive = drive.lower()
      path = path.lower()
    for root_path in self.mount_points:
      if not self.is_case_sensitive:
        root_path = root_path.lower()
      if drive and not root_path.startswith(drive):
          continue
      if path.startswith(root_path) and len(root_path) > len(mount_path):
        mount_path = root_path
    if mount_path:
      return self.mount_points[mount_path]
    mount_point = self._AutoMountDriveIfNeeded(path, force=True)
    assert mount_point
    return mount_point

  def _MountPointForDevice(self, idev):
    for mount_point in self.mount_points.values():
      if mount_point['idev'] == idev:
        return mount_point

  def GetDiskUsage(self, path=None):
    """Returns the total, used and free disk space in bytes as named tuple
       or placeholder values simulating unlimited space if not set.
       Note: This matches the return value of shutil.disk_usage().

    Args:
      path: The disk space is returned for the file system device where path resides.
            Defaults to the root path (e.g. '/' on Unix systems)
    """
    DiskUsage = namedtuple('usage', 'total, used, free')
    if path is None:
      mount_point = self.mount_points[self.root.name]
    else:
      mount_point = self._MountPointForPath(path)
    if mount_point and mount_point['total_size'] is not None:
      return DiskUsage(mount_point['total_size'], mount_point['used_size'],
                                   mount_point['total_size'] - mount_point['used_size'])
    return DiskUsage(1024*1024*1024*1024, 0, 1024*1024*1024*1024)

  def SetDiskUsage(self, total_size, path=None):
    """Changes the total size of the file system, preserving the used space.
       Example usage: set the size of an auto-mounted Windows drive.

    Args:
      total_size: the new total size of the filesystem in bytes

      path: The disk space is changed for the file system device where path resides.
            Defaults to the root path (e.g. '/' on Unix systems)

    Raises:
      IOError: if the new space is smaller than the used size.
    """
    if path is None:
      path = self.root.name
    mount_point = self._MountPointForPath(path)
    if mount_point['total_size'] is not None and mount_point['used_size'] > total_size:
        raise IOError(errno.ENOSPC,
                      'Fake file system: cannot change size to %r bytes - used space is larger' % total_size,
                      path)
    mount_point['total_size'] = total_size

  def ChangeDiskUsage(self, usage_change, file_path, st_dev):
    """Changes the used disk space by the given amount.

    Args:
      usage_change: number of bytes added to the used space
                    if negative, the used space will be decreased

      file_path: the path of the object needing the disk space

      st_dev: The device ID for the respective file system

    Raises:
      IOError: if usage_change exceeds the free file system space
    """
    mount_point = self._MountPointForDevice(st_dev)
    if mount_point:
      if mount_point['total_size'] is not None:
        if mount_point['total_size'] - mount_point['used_size'] < usage_change:
          raise IOError(errno.ENOSPC,
                        'Fake file system: disk is full, failed to add %r bytes' % usage_change,
                        file_path)
      mount_point['used_size'] += usage_change

  def SetIno(self, path, st_ino):
    """Set the self.st_ino attribute of file at 'path'.

    Args:
      path: Path to file.
      st_ino: The desired inode.
    """
    self.GetObject(path).SetIno(st_ino)

  def AddOpenFile(self, file_obj):
    """Adds file_obj to the list of open files on the filesystem.

    The position in the self.open_files array is the file descriptor number

    Args:
      file_obj:  file object to be added to open files list.

    Returns:
      File descriptor number for the file object.
    """
    if self.free_fd_heap:
      open_fd = heapq.heappop(self.free_fd_heap)
      self.open_files[open_fd] = file_obj
      return open_fd

    self.open_files.append(file_obj)
    return len(self.open_files) - 1

  def CloseOpenFile(self, file_obj):
    """Removes file_obj from the list of open files on the filesystem.

    Sets the entry in open_files to None.

    Args:
      file_obj:  file object to be removed to open files list.
    """
    self.open_files[file_obj.filedes] = None
    heapq.heappush(self.free_fd_heap, file_obj.filedes)

  def GetOpenFile(self, file_des):
    """Returns an open file.

    Args:
      file_des:  file descriptor of the open file.

    Raises:
      OSError: an invalid file descriptor.
      TypeError: filedes is not an integer.

    Returns:
      Open file object.
    """
    if not isinstance(file_des, int):
      raise TypeError('an integer is required')
    if (file_des >= len(self.open_files) or
        self.open_files[file_des] is None):
      raise OSError(errno.EBADF, 'Bad file descriptor', file_des)
    return self.open_files[file_des]

  def NormalizePathSeparator(self, path):
    """Replace all appearances of alternative path separator with path separator.
    Do nothing if no alternative separator is set.
    Args:
      path: the path to be normalized.
    Returns:
      The normalized path that will be used internally.
    """
    if self.alternative_path_separator is None or not path:
      return path
    return path.replace(self.alternative_path_separator, self.path_separator)

  def CollapsePath(self, path):
    """Mimics os.path.normpath using the specified path_separator.

    Mimics os.path.normpath using the path_separator that was specified
    for this FakeFilesystem.  Normalizes the path, but unlike the method
    NormalizePath, does not make it absolute.  Eliminates dot components
    (. and ..) and combines repeated path separators (//).  Initial ..
    components are left in place for relative paths.  If the result is an empty
    path, '.' is returned instead.

    This also replaces alternative path separator with path separator.  That is,
    it behaves like the real os.path.normpath on Windows if initialized with
    '\\' as path separator and  '/' as alternative separator.

    Args:
      path:  (str) The path to normalize.

    Returns:
      (str) A copy of path with empty components and dot components removed.
    """
    path = self.NormalizePathSeparator(path)
    drive, path = self.SplitDrive(path)
    is_absolute_path = path.startswith(self.path_separator)
    path_components = path.split(self.path_separator)
    collapsed_path_components = []
    for component in path_components:
      if (not component) or (component == '.'):
        continue
      if component == '..':
        if collapsed_path_components and (
            collapsed_path_components[-1] != '..'):
          # Remove an up-reference: directory/..
          collapsed_path_components.pop()
          continue
        elif is_absolute_path:
          # Ignore leading .. components if starting from the root directory.
          continue
      collapsed_path_components.append(component)
    collapsed_path = self.path_separator.join(collapsed_path_components)
    if is_absolute_path:
      collapsed_path = self.path_separator + collapsed_path
    return drive + collapsed_path or '.'

  def NormalizeCase(self, path):
    if self.is_case_sensitive or not path:
      return path
    path_components = self.GetPathComponents(path)
    normalized_components = []
    current_dir = self.root
    for component in path_components:
      dir_name, current_dir = self._DirectoryContent(current_dir, component)
      if current_dir is None or current_dir.contents is None:
        return path
      normalized_components.append(dir_name)
    normalized_path = self.path_separator.join(normalized_components)
    if path.startswith(self.path_separator) and not normalized_path.startswith(self.path_separator):
      normalized_path = self.path_separator + normalized_path
    return normalized_path

  def NormalizePath(self, path):
    """Absolutize and minimalize the given path.

    Forces all relative paths to be absolute, and normalizes the path to
    eliminate dot and empty components.

    Args:
      path:  path to normalize

    Returns:
      The normalized path relative to the current working directory, or the root
        directory if path is empty.
    """
    path = self.NormalizePathSeparator(path)
    if not path:
      path = self.path_separator
    elif not self._StartsWithRootPath(path):
      # Prefix relative paths with cwd, if cwd is not root.
      path = self.path_separator.join(
          (self.cwd != self.root.name and self.cwd or '',
           path))
    if path == '.':
      path = self.cwd
    return self.CollapsePath(path)

  def SplitPath(self, path):
    """Mimics os.path.split using the specified path_separator.

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
    path_components = path.split(self.path_separator)
    if not path_components:
      return ('', '')
    basename = path_components.pop()
    if not path_components:
      return ('', basename)
    for component in path_components:
      if component:
        # The path is not the root; it contains a non-separator component.
        # Strip all trailing separators.
        while not path_components[-1]:
          path_components.pop()
        return (drive + self.path_separator.join(path_components), basename)
    # Root path.  Collapse all leading separators.
    return (drive or self.path_separator, basename)

  def SplitDrive(self, path):
    """Splits the path into the drive part and the rest of the path, if drive letters are supported
       and a drive is present, otherwise returns an empty string and the original path.
       Taken from Windows specific implementation in Python 3.5 and slightly adapted.
    """
    if self.supports_drive_letter:
      if len(path) >= 2:
        path = self.NormalizePathSeparator(path)
        # UNC path handling is here since Python 2.7.8, back-ported from Python 3
        if sys.version_info >= (2, 7, 8):
          if (path[0:2] == self.path_separator*2) and (path[2:3] != self.path_separator):
            # UNC path handling - splits off the mount point instead of the drive
            sep_index = path.find(self.path_separator, 2)
            if sep_index == -1:
              return path[:0], path
            sep_index2 = path.find(self.path_separator, sep_index + 1)
            if sep_index2 == sep_index + 1:
              return path[:0], path
            if sep_index2 == -1:
              sep_index2 = len(path)
            return path[:sep_index2], path[sep_index2:]
        if path[1] == ':':
          return path[:2], path[2:]
    return path[:0], path

  def _JoinPathsWithDriveSupport(self, *all_paths):
    """Taken from Python 3.5 os.path.join() code in ntpath.py and slightly adapted"""
    base_path = all_paths[0]
    paths_to_add = all_paths[1:]
    seps = [self.path_separator, self.alternative_path_separator]
    result_drive, result_path = self.SplitDrive(base_path)
    for path in paths_to_add:
      drive_part, path_part = self.SplitDrive(path)
      if path_part and path_part[0] in seps:
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
      if result_path and result_path[-1] not in seps:
          result_path = result_path + self.path_separator
      result_path = result_path + path_part
    # add separator between UNC and non-absolute path
    if (result_path and result_path[0] not in seps and
        result_drive and result_drive[-1:] != ':'):
        return result_drive + self.path_separator + result_path
    return result_drive + result_path

  def JoinPaths(self, *paths):
    """Mimics os.path.join using the specified path_separator.

    Mimics os.path.join using the path_separator that was specified
    for this FakeFilesystem.

    Args:
      *paths:  (str) Zero or more paths to join.

    Returns:
      (str) The paths joined by the path separator, starting with the last
          absolute path in paths.
    """
    if len(paths) == 1:
      return paths[0]
    if self.supports_drive_letter:
      return self._JoinPathsWithDriveSupport(*paths)
    joined_path_segments = []
    for path_segment in paths:
      if self._StartsWithRootPath(path_segment):
        # An absolute path
        joined_path_segments = [path_segment]
      else:
        if (joined_path_segments and
            not joined_path_segments[-1].endswith(self.path_separator)):
          joined_path_segments.append(self.path_separator)
        if path_segment:
          joined_path_segments.append(path_segment)
    return ''.join(joined_path_segments)

  def GetPathComponents(self, path):
    """Breaks the path into a list of component names.

    Does not include the root directory as a component, as all paths
    are considered relative to the root directory for the FakeFilesystem.
    Callers should basically follow this pattern:

      file_path = self.NormalizePath(file_path)
      path_components = self.GetPathComponents(file_path)
      current_dir = self.root
      for component in path_components:
        if component not in current_dir.contents:
          raise IOError
        DoStuffWithComponent(current_dir, component)
        current_dir = current_dir.GetEntry(component)

    Args:
      path:  path to tokenize

    Returns:
      The list of names split from path
    """
    if not path or path == self.path_separator:
      return []
    drive, path = self.SplitDrive(path)
    path_components = path.split(self.path_separator)
    assert drive or path_components
    if not path_components[0]:
      # This is an absolute path.
      path_components = path_components[1:]
    if drive:
      path_components.insert(0, drive)
    return path_components

  def _StartsWithDriveLetter(self, file_path):
    return self.supports_drive_letter and len(file_path) >= 2 and file_path[0].isalpha and file_path[1] == ':'

  def _StartsWithRootPath(self, file_path):
    return (file_path.startswith(self.root.name) or
            not self.is_case_sensitive and file_path.lower().startswith(self.root.name.lower()) or
            self._StartsWithDriveLetter(file_path))

  def _IsRootPath(self, file_path):
    return (file_path == self.root.name or
            not self.is_case_sensitive and file_path.lower() == self.root.name.lower() or
            len(file_path) == 2 and self._StartsWithDriveLetter(file_path))

  def _EndsWithPathSeparator(self, file_path):
    return file_path and (file_path.endswith(self.path_separator)
                          or self.alternative_path_separator is not None
                          and file_path.endswith(self.alternative_path_separator))

  def _DirectoryContent(self, directory, component):
    if component in directory.contents:
      return component, directory.contents[component]
    if not self.is_case_sensitive:
      matching_content = [(subdir, directory.contents[subdir]) for subdir in directory.contents
                          if subdir.lower() == component.lower()]
      if matching_content:
        return matching_content[0]
    return None, None

  def Exists(self, file_path):
    """True if a path points to an existing file system object.

    Args:
      file_path:  path to examine

    Returns:
      bool(if object exists)

    Raises:
      TypeError: if file_path is None
    """
    if file_path is None:
      raise TypeError
    if not file_path:
      return False
    try:
      file_path = self.ResolvePath(file_path)
    except IOError:
      return False
    if file_path == self.root.name:
      return True
    path_components = self.GetPathComponents(file_path)
    current_dir = self.root
    for component in path_components:
      if component not in current_dir.contents:
        return False
      current_dir = current_dir.contents[component]
    return True

  def ResolvePath(self, file_path):
    """Follow a path, resolving symlinks.

    ResolvePath traverses the filesystem along the specified file path,
    resolving file names and symbolic links until all elements of the path are
    exhausted, or we reach a file which does not exist.  If all the elements
    are not consumed, they just get appended to the path resolved so far.
    This gives us the path which is as resolved as it can be, even if the file
    does not exist.

    This behavior mimics Unix semantics, and is best shown by example.  Given a
    file system that looks like this:

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
      file_path:  path to examine

    Returns:
      resolved_path (string) or None

    Raises:
      TypeError: if file_path is None
      IOError: if file_path is '' or a part of the path doesn't exist
    """

    def _ComponentsToPath(component_folders):
      path = self.path_separator.join(component_folders)
      if not self._StartsWithRootPath(path):
        path = self.path_separator + path
      return path

    def _ValidRelativePath(file_path):
      while file_path and '/..' in file_path:
        file_path = file_path[:file_path.rfind('/..')]
        if not self.Exists(self.NormalizePath(file_path)):
          return False
      return True

    def _FollowLink(link_path_components, link):
      """Follow a link w.r.t. a path resolved so far.

      The component is either a real file, which is a no-op, or a symlink.
      In the case of a symlink, we have to modify the path as built up so far
        /a/b => ../c   should yield /a/../c (which will normalize to /a/c)
        /a/b => x      should yield /a/x
        /a/b => /x/y/z should yield /x/y/z
      The modified path may land us in a new spot which is itself a
      link, so we may repeat the process.

      Args:
        link_path_components: The resolved path built up to the link so far.
        link: The link object itself.

      Returns:
        (string) the updated path resolved after following the link.

      Raises:
        IOError: if there are too many levels of symbolic link
      """
      link_path = link.contents
      # For links to absolute paths, we want to throw out everything in the
      # path built so far and replace with the link.  For relative links, we
      # have to append the link to what we have so far,
      if not link_path.startswith(self.path_separator):
        # Relative path.  Append remainder of path to what we have processed
        # so far, excluding the name of the link itself.
        # /a/b => ../c   should yield /a/../c (which will normalize to /c)
        # /a/b => d should yield a/d
        components = link_path_components[:-1]
        components.append(link_path)
        link_path = self.path_separator.join(components)
      # Don't call self.NormalizePath(), as we don't want to prepend self.cwd.
      return self.CollapsePath(link_path)

    if file_path is None:
      # file.open(None) raises TypeError, so mimic that.
      raise TypeError('Expected file system path string, received None')
    if not file_path or not _ValidRelativePath(file_path):
      # file.open('') raises IOError, so mimic that, and validate that all
      # parts of a relative path exist.
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
      if component not in current_dir.contents:
        # The component of the path at this point does not actually exist in
        # the folder.   We can't resolve the path any more.  It is legal to link
        # to a file that does not yet exist, so rather than raise an error, we
        # just append the remaining components to what return path we have built
        # so far and return that.
        resolved_components.extend(path_components)
        break
      current_dir = current_dir.contents[component]

      # Resolve any possible symlinks in the current path component.
      if stat.S_ISLNK(current_dir.st_mode):
        # This link_depth check is not really meant to be an accurate check.
        # It is just a quick hack to prevent us from looping forever on
        # cycles.
        link_depth += 1
        if link_depth > _MAX_LINK_DEPTH:
          raise IOError(errno.EMLINK,
                        'Too many levels of symbolic links: \'%s\'' %
                        _ComponentsToPath(resolved_components))
        link_path = _FollowLink(resolved_components, current_dir)

        # Following the link might result in the complete replacement of the
        # current_dir, so we evaluate the entire resulting path.
        target_components = self.GetPathComponents(link_path)
        path_components = target_components + path_components
        resolved_components = []
        current_dir = self.root
    return _ComponentsToPath(resolved_components)

  def GetObjectFromNormalizedPath(self, file_path):
    """Searches for the specified filesystem object within the fake filesystem.

    Args:
      file_path: specifies target FakeFile object to retrieve, with a
          path that has already been normalized/resolved

    Returns:
      the FakeFile object corresponding to file_path

    Raises:
      IOError: if the object is not found
    """
    if file_path == self.root.name:
      return self.root
    path_components = self.GetPathComponents(file_path)
    target_object = self.root
    try:
      for component in path_components:
        if not isinstance(target_object, FakeDirectory):
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
    """Searches for the specified filesystem object within the fake filesystem.

    Args:
      file_path: specifies target FakeFile object to retrieve

    Returns:
      the FakeFile object corresponding to file_path

    Raises:
      IOError: if the object is not found
    """
    file_path = self.NormalizePath(self.NormalizeCase(file_path))
    return self.GetObjectFromNormalizedPath(file_path)

  def ResolveObject(self, file_path):
    """Searches for the specified filesystem object, resolving all links.

    Args:
      file_path: specifies target FakeFile object to retrieve

    Returns:
      the FakeFile object corresponding to file_path

    Raises:
      IOError: if the object is not found
    """
    return self.GetObjectFromNormalizedPath(self.ResolvePath(file_path))

  def LResolveObject(self, path):
    """Searches for the specified object, resolving only parent links.

    This is analogous to the stat/lstat difference.  This resolves links *to*
    the object but not of the final object itself.

    Args:
      path: specifies target FakeFile object to retrieve

    Returns:
      the FakeFile object corresponding to path

    Raises:
      IOError: if the object is not found
    """
    if path == self.root.name:
      # The root directory will never be a link
      return self.root
    parent_directory, child_name = self.SplitPath(path)
    if not parent_directory:
      parent_directory = self.cwd
    try:
      parent_obj = self.ResolveObject(parent_directory)
      assert parent_obj
      if not isinstance(parent_obj, FakeDirectory):
        raise IOError(errno.ENOENT,
                      'No such file or directory in fake filesystem',
                      path)
      return parent_obj.GetEntry(child_name)
    except KeyError:
      raise IOError(errno.ENOENT,
                    'No such file or directory in the fake filesystem',
                    path)

  def AddObject(self, file_path, file_object):
    """Add a fake file or directory into the filesystem at file_path.

    Args:
      file_path: the path to the file to be added relative to self
      file_object: file or directory to add

    Raises:
      IOError: if file_path does not correspond to a directory
    """
    try:
      target_directory = self.GetObject(file_path)
      target_directory.AddEntry(file_object)
    except AttributeError:
      raise IOError(errno.ENOTDIR,
                    'Not a directory in the fake filesystem',
                    file_path)

  def RenameObject(self, old_file, new_file):
    """Renames a FakeFile object at old_file to new_file, preserving all properties.
       Also replaces existing new_file object, if one existed (Unix only).

    Args:
      old_file:  path to filesystem object to rename
      new_file:  path to where the filesystem object will live after this call

    Raises:
      OSError:  - if old_file does not exist
                - if new_file is an existing directory
                - if new_file is an existing file (Windows)
                - if new_file is an existing file and could not be removed (Unix)
                - if dirname(new_file) does not exist
                - if the file would be moved to another filesystem (e.g. mount point)
    """
    old_file = self.NormalizePath(old_file)
    new_file = self.NormalizePath(new_file)
    if not self.Exists(old_file):
      raise OSError(errno.ENOENT,
                    'Fake filesystem object: can not rename nonexistent file',
                    old_file)

    if self.Exists(new_file):
      if old_file == new_file:
        return    # Nothing to do here.
      new_obj = self.GetObject(new_file)
      if stat.S_ISDIR(new_obj.st_mode):
        raise OSError(errno.EEXIST,
                      'Fake filesystem object: can not rename to existing directory',
                      new_file)
      elif _is_windows:
        raise OSError(errno.EEXIST,
                      'Fake filesystem object: can not rename to existing file',
                      new_file)
      else:
        try:
          self.RemoveObject(new_file)
        except IOError as e:
          raise OSError(e.errno, e.strerror, e.filename)

    old_dir, old_name = os.path.split(old_file)
    new_dir, new_name = os.path.split(new_file)
    if not self.Exists(new_dir):
      raise OSError(errno.ENOENT, 'No such fake directory', new_dir)
    old_dir_object = self.ResolveObject(old_dir)
    new_dir_object = self.ResolveObject(new_dir)
    if old_dir_object.st_dev != new_dir_object.st_dev:
      raise OSError(errno.EXDEV,
                    'Fake filesystem object: cannot rename across file systems',
                    old_file)

    object_to_rename = old_dir_object.GetEntry(old_name)
    old_dir_object.RemoveEntry(old_name)
    object_to_rename.name = new_name
    new_dir_object.AddEntry(object_to_rename)

  def RemoveObject(self, file_path):
    """Remove an existing file or directory.

    Args:
      file_path: the path to the file relative to self

    Raises:
      IOError: if file_path does not correspond to an existing file, or if part
        of the path refers to something other than a directory
      OSError: if the directory is in use (eg, if it is '/')
    """
    file_path = self.NormalizeCase(file_path)
    if self._IsRootPath(file_path):
      raise OSError(errno.EBUSY, 'Fake device or resource busy',
                    file_path)
    try:
      dirname, basename = self.SplitPath(file_path)
      target_directory = self.GetObject(dirname)
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
    """Creates directory_path, and all the parent directories.

    Helper method to set up your test faster

    Args:
      directory_path:  directory to create
      perm_bits: permission bits
      inode: inode of directory

    Returns:
      the newly created FakeDirectory object

    Raises:
      OSError:  if the directory already exists
    """
    directory_path = self.NormalizePath(directory_path)
    self._AutoMountDriveIfNeeded(directory_path)
    if self.Exists(directory_path):
      raise OSError(errno.EEXIST,
                    'Directory exists in fake filesystem',
                    directory_path)
    path_components = self.GetPathComponents(directory_path)
    current_dir = self.root

    for component in path_components:
      if component not in current_dir.contents:
        new_dir = FakeDirectory(component, perm_bits, filesystem=self)
        current_dir.AddEntry(new_dir)
        current_dir = new_dir
      else:
        current_dir = current_dir.contents[component]

    self.last_ino += 1
    current_dir.SetIno(self.last_ino)
    return current_dir

  def CreateFile(self, file_path, st_mode=stat.S_IFREG | PERM_DEF_FILE,
                 contents='', st_size=None, create_missing_dirs=True,
                 apply_umask=False):
    """Creates file_path, including all the parent directories along the way.

    Helper method to set up your test faster.

    Args:
      file_path: path to the file to create
      st_mode: the stat.S_IF constant representing the file type
      contents: the contents of the file
      st_size: file size; only valid if contents=None
      create_missing_dirs: if True, auto create missing directories
      apply_umask: whether or not the current umask must be applied on st_mode

    Returns:
      the newly created FakeFile object

    Raises:
      IOError: if the file already exists
      IOError: if the containing directory is required and missing
    """
    file_path = self.NormalizePath(file_path)
    if self.Exists(file_path):
      raise IOError(errno.EEXIST,
                    'File already exists in fake filesystem',
                    file_path)
    parent_directory, new_file = self.SplitPath(file_path)
    if not parent_directory:
      parent_directory = self.cwd
    self._AutoMountDriveIfNeeded(parent_directory)
    if not self.Exists(parent_directory):
      if not create_missing_dirs:
        raise IOError(errno.ENOENT, 'No such fake directory', parent_directory)
      self.CreateDirectory(parent_directory)
    else:
      parent_directory = self.NormalizeCase(parent_directory)
    if apply_umask:
      st_mode &= ~self.umask
    file_object = FakeFile(new_file, st_mode, filesystem=self)
    self.last_ino += 1
    file_object.SetIno(self.last_ino)
    self.AddObject(parent_directory, file_object)

    if contents is not None or st_size is not None:
      try:
        if st_size is not None:
          file_object.SetLargeFileSize(st_size)
        else:
          file_object._SetInitialContents(contents)
      except IOError:
        self.RemoveObject(file_path)
        raise

    return file_object

  def CreateLink(self, file_path, link_target):
    """Creates the specified symlink, pointed at the specified link target.

    Args:
      file_path:  path to the symlink to create
      link_target:  the target of the symlink

    Returns:
      the newly created FakeFile object

    Raises:
      IOError:  if the file already exists
    """
    resolved_file_path = self.ResolvePath(file_path)
    return self.CreateFile(resolved_file_path, st_mode=stat.S_IFLNK | PERM_DEF,
                           contents=link_target)

  def CreateHardLink(self, old_path, new_path):
    """Create a hard link at new_path, pointing at old_path.

    Args:
      old_path: an existing link to the target file
      new_path: the destination path to create a new link at

    Returns:
      the FakeFile object referred to by old_path

    Raises:
      OSError:  if something already exists at new_path
      OSError:  if the parent directory doesn't exist
    """
    new_path_normalized = self.NormalizePath(new_path)
    if self.Exists(new_path_normalized):
      raise IOError(errno.EEXIST,
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
      old_file = self.GetObject(old_path)
    except:
      raise OSError(errno.ENOENT,
                    'No such file or directory in fake filesystem',
                    old_path)

    # abuse the name field to control the filename of the newly created link
    old_file.name = new_basename
    self.AddObject(new_parent_directory, old_file)
    return old_file

  def __str__(self):
    return str(self.root)


class FakePathModule(object):
  """Faked os.path module replacement.

  FakePathModule should *only* be instantiated by FakeOsModule.  See the
  FakeOsModule docstring for details.
  """
  _OS_PATH_COPY = CopyModule(os.path)

  def __init__(self, filesystem, os_module=None):
    """Init.

    Args:
      filesystem:  FakeFilesystem used to provide file system information
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
    """Determines whether the file object exists within the fake filesystem.

    Args:
      path:  path to the file object

    Returns:
      bool (if file exists)
    """
    return self.filesystem.Exists(path)

  def lexists(self, path):
    """Test whether a path exists.  Returns True for broken symbolic links.

    Args:
      path:  path to the symlnk object

    Returns:
      bool (if file exists)
    """
    return self.exists(path) or self.islink(path)

  def getsize(self, path):
    """Return the file object size in bytes.

    Args:
      path:  path to the file object

    Returns:
      file size in bytes
    """
    file_obj = self.filesystem.GetObject(path)
    return file_obj.st_size

  def _istype(self, path, st_flag):
    """Helper function to implement isdir(), islink(), etc.

    See the stat(2) man page for valid stat.S_I* flag values

    Args:
      path:  path to file to stat and test
      st_flag:  the stat.S_I* flag checked for the file's st_mode

    Returns:
      boolean (the st_flag is set in path's st_mode)

    Raises:
      TypeError: if path is None
    """
    if path is None:
      raise TypeError
    try:
      obj = self.filesystem.ResolveObject(path)
      if obj:
        return stat.S_IFMT(obj.st_mode) == st_flag
    except IOError:
      return False
    return False

  def isabs(self, path):
    if self.filesystem.supports_drive_letter:
      path = self.splitdrive(path)[1]
    if _is_windows:
      return len(path) > 0 and path[0] in (self.sep, self.altsep)
    else:
      return path.startswith(self.sep) or self.altsep is not None and path.startswith(self.altsep)

  def isdir(self, path):
    """Determines if path identifies a directory."""
    return self._istype(path, stat.S_IFDIR)

  def isfile(self, path):
    """Determines if path identifies a regular file."""
    return self._istype(path, stat.S_IFREG)

  def islink(self, path):
    """Determines if path identifies a symbolic link.

    Args:
      path: path to filesystem object.

    Returns:
      boolean (the st_flag is set in path's st_mode)

    Raises:
      TypeError: if path is None
    """
    if path is None:
      raise TypeError
    try:
      link_obj = self.filesystem.LResolveObject(path)
      return stat.S_IFMT(link_obj.st_mode) == stat.S_IFLNK
    except IOError:
      return False
    except KeyError:
      return False
    return False

  def getmtime(self, path):
    """Returns the mtime of the file."""
    try:
      file_obj = self.filesystem.GetObject(path)
    except IOError as e:
      raise OSError(errno.ENOENT, str(e))
    return file_obj.st_mtime

  def abspath(self, path):
    """Return the absolute version of a path."""
    def getcwd():
      if sys.version_info < (3, 0) and isinstance(path, unicode):
        return self.os.getcwdu()
      else:
        return self.os.getcwd()

    if not self.isabs(path):
      path = self.join(getcwd(), path)
    elif (self.filesystem.supports_drive_letter and
        path.startswith(self.sep) or self.altsep is not None and path.startswith(self.altsep)):
      cwd = getcwd()
      if self.filesystem._StartsWithDriveLetter(cwd):
        path = self.join(cwd[:2], path)
    return self.normpath(path)

  def join(self, *p):
    """Returns the completed path with a separator of the parts."""
    return self.filesystem.JoinPaths(*p)

  def splitdrive(self, path):
    """Splits the path into the drive part and the rest of the path, if supported."""
    return self.filesystem.SplitDrive(path)

  def normpath(self, path):
    """Normalize path, eliminating double slashes, etc."""
    return self.filesystem.CollapsePath(path)

  def normcase(self, path):
    """Converts to lower case under windows, replaces additional path separator"""
    path = self.filesystem.NormalizePathSeparator(path)
    if _is_windows:
      path = path.lower()
    return path

  if _is_windows:

    def relpath(self, path, start=None):
      """ntpath.relpath() needs the cwd passed in the start argument."""
      if start is None:
        start = self.filesystem.cwd
      path = self._os_path.relpath(path, start)
      return path.replace(self._os_path.sep, self.filesystem.path_separator)

    realpath = abspath

  def expanduser(self, path):
    return self._os_path.expanduser(path).replace(self._os_path.sep, self.sep)

  def ismount(self, path):
    """Returns true if the given path is a mount point.

    Args:
      path:  path to filesystem object to be checked

    Returns:
      True if path is a mount point added to the fake file system.
      Under Windows also returns True for drive and UNC roots (independent of their existence).
    """
    if not path:
      return False
    normed_path = self.filesystem.NormalizePath(path)
    if self.filesystem.supports_drive_letter:
      if self.filesystem.alternative_path_separator is not None:
        path_seps = (self.filesystem.path_separator, self.filesystem.alternative_path_separator)
      else:
        path_seps = (self.filesystem.path_separator, )
      drive, rest = self.filesystem.SplitDrive(normed_path)
      if drive and drive[0] in path_seps:
        return (not rest) or (rest in path_seps)
      if rest in path_seps:
        return True
    for mount_point in self.filesystem.mount_points:
      if (normed_path.rstrip(self.filesystem.path_separator) ==
            mount_point.rstrip(self.filesystem.path_separator)):
        return True
    return False

  def __getattr__(self, name):
    """Forwards any non-faked calls to the real os.path."""
    return getattr(self._os_path, name)


class FakeOsModule(object):
  """Uses FakeFilesystem to provide a fake os module replacement.

  Do not create os.path separately from os, as there is a necessary circular
  dependency between os and os.path to replicate the behavior of the standard
  Python modules.  What you want to do is to just let FakeOsModule take care of
  os.path setup itself.

  # You always want to do this.
  filesystem = fake_filesystem.FakeFilesystem()
  my_os_module = fake_filesystem.FakeOsModule(filesystem)
  """

  _stat_float_times = sys.version_info >= (2, 5)

  def __init__(self, filesystem, os_path_module=None):
    """Also exposes self.path (to fake os.path).

    Args:
      filesystem:  FakeFilesystem used to provide file system information
      os_path_module: (deprecated) optional FakePathModule instance
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
      *args: pass through args
      **kwargs: pass through kwargs

    Returns:
      File object corresponding to file_des.

    Raises:
      TypeError: if file descriptor is not an integer.
    """
    if not isinstance(args[0], int):
      raise TypeError('an integer is required')
    return FakeFileOpen(self.filesystem)(*args, **kwargs)

  def _fdopen_ver2(self, file_des, mode='r', bufsize=None):
    """Returns an open file object connected to the file descriptor file_des.

    Args:
      file_des: An integer file descriptor for the file object requested.
      mode: additional file flags. Currently checks to see if the mode matches
        the mode of the requested file object.
      bufsize: ignored. (Used for signature compliance with __builtin__.fdopen)

    Returns:
      File object corresponding to file_des.

    Raises:
      OSError: if bad file descriptor or incompatible mode is given.
      TypeError: if file descriptor is not an integer.
    """
    if not isinstance(file_des, int):
      raise TypeError('an integer is required')

    try:
      return FakeFileOpen(self.filesystem).Call(file_des, mode=mode)
    except IOError as e:
      raise OSError(e)

  def open(self, file_path, flags, mode=None):
    """Returns the file descriptor for a FakeFile.

    WARNING: This implementation only implements creating a file. Please fill
    out the remainder for your needs.

    Args:
      file_path: the path to the file
      flags: low-level bits to indicate io operation
      mode: bits to define default permissions

    Returns:
      A file descriptor.

    Raises:
      OSError: if the path cannot be found
      ValueError: if invalid mode is given
      NotImplementedError: if an unsupported flag is passed in
    """
    if flags & os.O_CREAT:
      fake_file = FakeFileOpen(self.filesystem)(file_path, 'w')
      if mode:
        self.chmod(file_path, mode)
      return fake_file.fileno()
    else:
      raise NotImplementedError('FakeOsModule.open')

  def close(self, file_des):
    """Closes a file descriptor.

    Args:
      file_des: An integer file descriptor for the file object requested.

    Raises:
      OSError: bad file descriptor.
      TypeError: if file descriptor is not an integer.
    """
    fh = self.filesystem.GetOpenFile(file_des)
    fh.close()

  def read(self, file_des, num_bytes):
    """Reads number of bytes from a file descriptor, returns bytes read.

    Args:
      file_des: An integer file descriptor for the file object requested.
      num_bytes: Number of bytes to read from file.

    Returns:
      Bytes read from file.

    Raises:
      OSError: bad file descriptor.
      TypeError: if file descriptor is not an integer.
    """
    fh = self.filesystem.GetOpenFile(file_des)
    return fh.read(num_bytes)

  def write(self, file_des, contents):
    """Writes string to file descriptor, returns number of bytes written.

    Args:
      file_des: An integer file descriptor for the file object requested.
      contents: String of bytes to write to file.

    Returns:
      Number of bytes written.

    Raises:
      OSError: bad file descriptor.
      TypeError: if file descriptor is not an integer.
    """
    fh = self.filesystem.GetOpenFile(file_des)
    fh.write(contents)
    fh.flush()
    return len(contents)

  @classmethod
  def stat_float_times(cls, newvalue=None):
    """Determine whether a file's time stamps are reported as floats or ints.

    Calling without arguments returns the current value. The value is shared
    by all instances of FakeOsModule.

    Args:
      newvalue: if True, mtime, ctime, atime are reported as floats.
        Else, as ints (rounding down).
    """
    if newvalue is not None:
      cls._stat_float_times = bool(newvalue)
    return cls._stat_float_times

  def fstat(self, file_des):
    """Returns the os.stat-like tuple for the FakeFile object of file_des.

    Args:
      file_des:  file descriptor of filesystem object to retrieve

    Returns:
      the os.stat_result object corresponding to entry_path

    Raises:
      OSError: if the filesystem object doesn't exist.
    """
    # stat should return the tuple representing return value of os.stat
    stats = self.filesystem.GetOpenFile(file_des).GetObject()
    st_obj = os.stat_result((stats.st_mode, stats.st_ino, stats.st_dev,
                             stats.st_nlink, stats.st_uid, stats.st_gid,
                             stats.st_size, stats.st_atime,
                             stats.st_mtime, stats.st_ctime))
    return st_obj

  def _ConfirmDir(self, target_directory):
    """Tests that the target is actually a directory, raising OSError if not.

    Args:
      target_directory:  path to the target directory within the fake
        filesystem

    Returns:
      the FakeFile object corresponding to target_directory

    Raises:
      OSError:  if the target is not a directory
    """
    try:
      directory = self.filesystem.GetObject(target_directory)
    except IOError as e:
      raise OSError(e.errno, e.strerror, target_directory)
    if not directory.st_mode & stat.S_IFDIR:
      raise OSError(errno.ENOTDIR,
                    'Fake os module: not a directory',
                    target_directory)
    return directory

  def umask(self, new_mask):
    """Change the current umask.

    Args:
      new_mask: An integer.

    Returns:
      The old mask.

    Raises:
      TypeError: new_mask is of an invalid type.
    """
    if not isinstance(new_mask, int):
      raise TypeError('an integer is required')
    old_umask = self.filesystem.umask
    self.filesystem.umask = new_mask
    return old_umask

  def chdir(self, target_directory):
    """Change current working directory to target directory.

    Args:
      target_directory:  path to new current working directory

    Raises:
      OSError: if user lacks permission to enter the argument directory or if
               the target is not a directory
    """
    target_directory = self.filesystem.ResolvePath(target_directory)
    self._ConfirmDir(target_directory)
    directory = self.filesystem.GetObject(target_directory)
    # A full implementation would check permissions all the way up the tree.
    if not directory.st_mode | PERM_EXE:
      raise OSError(errno.EACCES, 'Fake os module: permission denied',
                    directory)
    self.filesystem.cwd = target_directory

  def getcwd(self):
    """Return current working directory."""
    return self.filesystem.cwd

  def getcwdu(self):
    """Return current working directory. Deprecated in Python 3."""
    if sys.version_info >= (3, 0):
      raise AttributeError('no attribute getcwdu')
    return unicode(self.filesystem.cwd)

  def listdir(self, target_directory):
    """Returns a sorted list of filenames in target_directory.

    Args:
      target_directory:  path to the target directory within the fake
        filesystem

    Returns:
      a sorted list of file names within the target directory

    Raises:
      OSError:  if the target is not a directory
    """
    target_directory = self.filesystem.ResolvePath(target_directory)
    directory = self._ConfirmDir(target_directory)
    return sorted(directory.contents)

  def _ClassifyDirectoryContents(self, root):
    """Classify contents of a directory as files/directories.

    Args:
      root: (str) Directory to examine.

    Returns:
      (tuple) A tuple consisting of three values: the directory examined, a
      list containing all of the directory entries, and a list containing all
      of the non-directory entries.  (This is the same format as returned by
      the os.walk generator.)

    Raises:
      Nothing on its own, but be ready to catch exceptions generated by
      underlying mechanisms like os.listdir.
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
    """Performs an os.walk operation over the fake filesystem.

    Args:
      top:  root directory from which to begin walk
      topdown:  determines whether to return the tuples with the root as the
        first entry (True) or as the last, after all the child directory
        tuples (False)
      onerror:  if not None, function which will be called to handle the
        os.error instance provided when os.listdir() fails

    Yields:
      (path, directories, nondirectories) for top and each of its
      subdirectories.  See the documentation for the builtin os module for
      further details.
    """
    top = self.path.normpath(top)
    if not followlinks and self.path.islink(top):
      return
    try:
      top_contents = self._ClassifyDirectoryContents(top)
    except OSError as e:
      top_contents = None
      if onerror is not None:
        onerror(e)

    if top_contents is not None:
      if topdown:
        yield top_contents

      for directory in top_contents[1]:
        if not followlinks and self.path.islink(directory):
            continue
        for contents in self.walk(self.path.join(top, directory),
                                  topdown=topdown, onerror=onerror, followlinks=followlinks):
          yield contents

      if not topdown:
        yield top_contents

  def readlink(self, path):
    """Reads the target of a symlink.

    Args:
      path:  symlink to read the target of

    Returns:
      the string representing the path to which the symbolic link points.

    Raises:
      TypeError: if path is None
      OSError: (with errno=ENOENT) if path is not a valid path, or
               (with errno=EINVAL) if path is valid, but is not a symlink
    """
    if path is None:
      raise TypeError
    try:
      link_obj = self.filesystem.LResolveObject(path)
    except IOError:
      raise OSError(errno.ENOENT, 'Fake os module: path does not exist', path)
    if stat.S_IFMT(link_obj.st_mode) != stat.S_IFLNK:
      raise OSError(errno.EINVAL, 'Fake os module: not a symlink', path)
    return link_obj.contents

  def stat(self, entry_path):
    """Returns the os.stat-like tuple for the FakeFile object of entry_path.

    Args:
      entry_path:  path to filesystem object to retrieve

    Returns:
      the os.stat_result object corresponding to entry_path

    Raises:
      OSError: if the filesystem object doesn't exist.
    """
    # stat should return the tuple representing return value of os.stat
    try:
      stats = self.filesystem.ResolveObject(entry_path)
      st_obj = os.stat_result((stats.st_mode, stats.st_ino, stats.st_dev,
                               stats.st_nlink, stats.st_uid, stats.st_gid,
                               stats.st_size, stats.st_atime,
                               stats.st_mtime, stats.st_ctime))
      return st_obj
    except IOError as io_error:
      raise OSError(io_error.errno, io_error.strerror, entry_path)

  def lstat(self, entry_path):
    """Returns the os.stat-like tuple for entry_path, not following symlinks.

    Args:
      entry_path:  path to filesystem object to retrieve

    Returns:
      the os.stat_result object corresponding to entry_path

    Raises:
      OSError: if the filesystem object doesn't exist.
    """
    # stat should return the tuple representing return value of os.stat
    try:
      stats = self.filesystem.LResolveObject(entry_path)
      st_obj = os.stat_result((stats.st_mode, stats.st_ino, stats.st_dev,
                               stats.st_nlink, stats.st_uid, stats.st_gid,
                               stats.st_size, stats.st_atime,
                               stats.st_mtime, stats.st_ctime))
      return st_obj
    except IOError as io_error:
      raise OSError(io_error.errno, io_error.strerror, entry_path)

  def remove(self, path):
    """Removes the FakeFile object representing the specified file."""
    path = self.filesystem.NormalizePath(path)
    if self.path.isdir(path) and not self.path.islink(path):
      raise OSError(errno.EISDIR, "Is a directory: '%s'" % path)
    try:
      self.filesystem.RemoveObject(path)
    except IOError as e:
      raise OSError(e.errno, e.strerror, e.filename)

  # As per the documentation unlink = remove.
  unlink = remove

  def rename(self, old_file, new_file):
    """Renames a FakeFile object at old_file to new_file, preserving all properties.
    Also replaces existing new_file object, if one existed (Unix only).

    Args:
      old_file:  path to filesystem object to rename
      new_file:  path to where the filesystem object will live after this call

    Raises:
      OSError:  - if old_file does not exist
                - new_file is an existing directory,
                - if new_file is an existing file (Windows)
                - if new_file is an existing file and could not be removed (Unix)
                - if dirname(new_file) does not exist
                - if the file would be moved to another filesystem (e.g. mount point)
    """
    self.filesystem.RenameObject(old_file, new_file)

  def rmdir(self, target_directory):
    """Remove a leaf Fake directory.

    Args:
      target_directory: (str) Name of directory to remove.

    Raises:
      OSError: if target_directory does not exist or is not a directory,
      or as per FakeFilesystem.RemoveObject. Cannot remove '.'.
    """
    if target_directory == '.':
      raise OSError(errno.EINVAL, 'Invalid argument: \'.\'')
    target_directory = self.filesystem.NormalizePath(target_directory)
    if self._ConfirmDir(target_directory):
      if self.listdir(target_directory):
        raise OSError(errno.ENOTEMPTY, 'Fake Directory not empty',
                      target_directory)
      try:
        self.filesystem.RemoveObject(target_directory)
      except IOError as e:
        raise OSError(e.errno, e.strerror, e.filename)

  def removedirs(self, target_directory):
    """Remove a leaf Fake directory and all empty intermediate ones."""
    target_directory = self.filesystem.NormalizePath(target_directory)
    directory = self._ConfirmDir(target_directory)
    if directory.contents:
      raise OSError(errno.ENOTEMPTY, 'Fake Directory not empty',
                    self.path.basename(target_directory))
    else:
      self.rmdir(target_directory)
    head, tail = self.path.split(target_directory)
    if not tail:
      head, tail = self.path.split(head)
    while head and tail:
      head_dir = self._ConfirmDir(head)
      if head_dir.contents:
        break
      self.rmdir(head)
      head, tail = self.path.split(head)

  def mkdir(self, dir_name, mode=PERM_DEF):
    """Create a leaf Fake directory.

    Args:
      dir_name: (str) Name of directory to create.  Relative paths are assumed
        to be relative to '/'.
      mode: (int) Mode to create directory with.  This argument defaults to
        0o777.  The umask is applied to this mode.

    Raises:
      OSError: if the directory name is invalid or parent directory is read only
      or as per FakeFilesystem.AddObject.
    """
    if self.filesystem._EndsWithPathSeparator(dir_name):
      dir_name = dir_name[:-1]

    parent_dir, _ = self.path.split(dir_name)
    if parent_dir:
      base_dir = self.path.normpath(parent_dir)
      if parent_dir.endswith(self.sep + '..'):
        base_dir, unused_dotdot, _ = parent_dir.partition(self.sep + '..')
      if not self.filesystem.Exists(base_dir):
        raise OSError(errno.ENOENT, 'No such fake directory', base_dir)

    dir_name = self.filesystem.NormalizePath(dir_name)
    if self.filesystem.Exists(dir_name):
      raise OSError(errno.EEXIST, 'Fake object already exists', dir_name)
    head, tail = self.path.split(dir_name)
    directory_object = self.filesystem.GetObject(head)
    if not directory_object.st_mode & PERM_WRITE:
      raise OSError(errno.EACCES, 'Permission Denied', dir_name)

    self.filesystem.AddObject(
        head, FakeDirectory(tail, mode & ~self.filesystem.umask))

  def makedirs(self, dir_name, mode=PERM_DEF):
    """Create a leaf Fake directory + create any non-existent parent dirs.

    Args:
      dir_name: (str) Name of directory to create.
      mode: (int) Mode to create directory (and any necessary parent
        directories) with. This argument defaults to 0o777.  The umask is
        applied to this mode.

    Raises:
      OSError: if the directory already exists or as per
      FakeFilesystem.CreateDirectory
    """
    dir_name = self.filesystem.NormalizePath(dir_name)
    path_components = self.filesystem.GetPathComponents(dir_name)

    # Raise a permission denied error if the first existing directory is not
    # writeable.
    current_dir = self.filesystem.root
    for component in path_components:
      if component not in current_dir.contents:
        if not current_dir.st_mode & PERM_WRITE:
          raise OSError(errno.EACCES, 'Permission Denied', dir_name)
        else:
          break
      else:
        current_dir = current_dir.contents[component]

    self.filesystem.CreateDirectory(dir_name, mode & ~self.filesystem.umask)

  def access(self, path, mode):
    """Check if a file exists and has the specified permissions.

    Args:
      path: (str) Path to the file.
      mode: (int) Permissions represented as a bitwise-OR combination of
          os.F_OK, os.R_OK, os.W_OK, and os.X_OK.
    Returns:
      boolean, True if file is accessible, False otherwise
    """
    try:
      st = self.stat(path)
    except OSError as os_error:
      if os_error.errno == errno.ENOENT:
        return False
      raise
    return (mode & ((st.st_mode >> 6) & 7)) == mode

  def chmod(self, path, mode):
    """Change the permissions of a file as encoded in integer mode.

    Args:
      path: (str) Path to the file.
      mode: (int) Permissions
    """
    try:
      file_object = self.filesystem.GetObject(path)
    except IOError as io_error:
      if io_error.errno == errno.ENOENT:
        raise OSError(errno.ENOENT,
                      'No such file or directory in fake filesystem',
                      path)
      raise
    file_object.st_mode = ((file_object.st_mode & ~PERM_ALL) |
                           (mode & PERM_ALL))
    file_object.st_ctime = time.time()

  def utime(self, path, times):
    """Change the access and modified times of a file.

    Args:
      path: (str) Path to the file.
      times: 2-tuple of numbers, of the form (atime, mtime) which is used to set
          the access and modified times, respectively. If None, file's access
          and modified times are set to the current time.

    Raises:
      TypeError: If anything other than integers is specified in passed tuple or
          number of elements in the tuple is not equal to 2.
    """
    try:
      file_object = self.filesystem.ResolveObject(path)
    except IOError as io_error:
      if io_error.errno == errno.ENOENT:
        raise OSError(errno.ENOENT,
                      'No such file or directory in fake filesystem',
                      path)
      raise
    if times is None:
      file_object.st_atime = time.time()
      file_object.st_mtime = time.time()
    else:
      if len(times) != 2:
        raise TypeError('utime() arg 2 must be a tuple (atime, mtime)')
      for t in times:
        if not isinstance(t, (int, float)):
          raise TypeError('atime and mtime must be numbers')

      file_object.st_atime = times[0]
      file_object.st_mtime = times[1]

  def chown(self, path, uid, gid):
    """Set ownership of a faked file.

    Args:
      path: (str) Path to the file or directory.
      uid: (int) Numeric uid to set the file or directory to.
      gid: (int) Numeric gid to set the file or directory to.

    `None` is also allowed for `uid` and `gid`.  This permits `os.rename` to
    use `os.chown` even when the source file `uid` and `gid` are `None` (unset).
    """
    try:
      file_object = self.filesystem.GetObject(path)
    except IOError as io_error:
      if io_error.errno == errno.ENOENT:
        raise OSError(errno.ENOENT,
                      'No such file or directory in fake filesystem',
                      path)
    if not ((isinstance(uid, int) or uid is None) and
            (isinstance(gid, int) or gid is None)):
        raise TypeError("An integer is required")
    if uid != -1:
      file_object.st_uid = uid
    if gid != -1:
      file_object.st_gid = gid

  def mknod(self, filename, mode=None, device=None):
    """Create a filesystem node named 'filename'.

    Does not support device special files or named pipes as the real os
    module does.

    Args:
      filename: (str) Name of the file to create
      mode: (int) permissions to use and type of file to be created.
        Default permissions are 0o666.  Only the stat.S_IFREG file type
        is supported by the fake implementation.  The umask is applied
        to this mode.
      device: not supported in fake implementation

    Raises:
      OSError: if called with unsupported options or the file can not be
      created.
    """
    if mode is None:
      mode = stat.S_IFREG | PERM_DEF_FILE
    if device or not mode & stat.S_IFREG:
      raise OSError(errno.EINVAL,
                    'Fake os mknod implementation only supports '
                    'regular files.')

    head, tail = self.path.split(filename)
    if not tail:
      if self.filesystem.Exists(head):
        raise OSError(errno.EEXIST, 'Fake filesystem: %s: %s' % (
            os.strerror(errno.EEXIST), filename))
      raise OSError(errno.ENOENT, 'Fake filesystem: %s: %s' % (
          os.strerror(errno.ENOENT), filename))
    if tail == '.' or tail == '..' or self.filesystem.Exists(filename):
      raise OSError(errno.EEXIST, 'Fake fileystem: %s: %s' % (
          os.strerror(errno.EEXIST), filename))
    try:
      self.filesystem.AddObject(head, FakeFile(tail,
                                               mode & ~self.filesystem.umask,
                                               filesystem=self.filesystem))
    except IOError:
      raise OSError(errno.ENOTDIR, 'Fake filesystem: %s: %s' % (
          os.strerror(errno.ENOTDIR), filename))

  def symlink(self, link_target, path):
    """Creates the specified symlink, pointed at the specified link target.

    Args:
      link_target:  the target of the symlink
      path:  path to the symlink to create

    Returns:
      None

    Raises:
      IOError:  if the file already exists
    """
    self.filesystem.CreateLink(path, link_target)

  def link(self, oldpath, newpath):
      self.filesystem.CreateHardLink(oldpath, newpath)

  def fsync(self, file_des):
    """Perform fsync for a fake file (in other words, do nothing).

    Args:
      file_des:  file descriptor of the open file.

    Raises:
      OSError: file_des is an invalid file descriptor.
      TypeError: file_des is not an integer.

    Returns:
      None
    """
    # Throw an error if file_des isn't valid
    self.filesystem.GetOpenFile(file_des)

  def fdatasync(self, file_des):
    """Perform fdatasync for a fake file (in other words, do nothing).

    Args:
      file_des:  file descriptor of the open file.

    Raises:
      OSError: file_des is an invalid file descriptor.
      TypeError: file_des is not an integer.

    Returns:
      None
    """
    # Throw an error if file_des isn't valid
    self.filesystem.GetOpenFile(file_des)

  def __getattr__(self, name):
    """Forwards any unfaked calls to the standard os module."""
    return getattr(self._os_module, name)

class FakeIoModule(object):
  """Uses FakeFilesystem to provide a fake io module replacement.
     Currently only used to wrap io.open() which is an alias to open()

  # You need a fake_filesystem to use this:
  filesystem = fake_filesystem.FakeFilesystem()
  my_io_module = fake_filesystem.FakeIoModule(filesystem)
  """

  def __init__(self, filesystem):
    """
    Args:
      filesystem:  FakeFilesystem used to provide file system information
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
    return FakeFileOpen(self.filesystem).Call(
      file_path, mode, buffering, encoding, errors, newline, closefd, opener)

  def __getattr__(self, name):
    """Forwards any unfaked calls to the standard io module."""
    return getattr(self._io_module, name)


class FakeFileWrapper(object):
  """Wrapper for a StringIO object for use by a FakeFile object.

  If the wrapper has any data written to it, it will propagate to
  the FakeFile object on close() or flush().
  """
  if sys.version_info < (3, 0):
    _OPERATION_ERROR = IOError
  else:
    _OPERATION_ERROR = io.UnsupportedOperation

  def __init__(self, file_object, file_path, update=False, read=False, append=False,
               delete_on_close=False, filesystem=None, newline=None,
               binary=True, closefd=True):
    self._file_object = file_object
    self._file_path = file_path
    self._append = append
    self._read = read
    self._update = update
    self._closefd = closefd
    self._file_epoch = file_object.epoch
    contents = file_object.contents
    newline_arg = {} if binary else {'newline': newline}
    if contents and isinstance(contents, Hexlified):
      contents = contents.recover(binary)
    if sys.version_info >= (3, 0):
      if binary:
        if contents and isinstance(contents, str):
          contents = bytes(contents, 'ascii')
      else:
        io_class = io.StringIO
    else:
      io_class = cStringIO.StringIO
    if contents:
      if update:
        self._io = io_class(**newline_arg)
        self._io.write(contents)
        if not append:
          self._io.seek(0)
        else:
          self._read_whence = 0
          if read:
            self._read_seek = 0
          else:
            self._read_seek = self._io.tell()
      else:
        self._io = io_class(contents, **newline_arg)
    else:
      self._io = io_class(**newline_arg)
      self._read_whence = 0
      self._read_seek = 0
    if delete_on_close:
      assert filesystem, 'delete_on_close=True requires filesystem='
    self._filesystem = filesystem
    self._delete_on_close = delete_on_close
    # override, don't modify FakeFile.name, as FakeFilesystem expects
    # it to be the file name only, no directories.
    self.name = file_object.opened_as

  def __enter__(self):
    """To support usage of this fake file with the 'with' statement."""
    return self

  def __exit__(self, type, value, traceback):  # pylint: disable-msg=W0622
    """To support usage of this fake file with the 'with' statement."""
    self.close()

  def GetObject(self):
    """Returns FakeFile object that is wrapped by current class."""
    return self._file_object

  def fileno(self):
    """Returns file descriptor of file object."""
    return self.filedes

  def close(self):
    """File close."""
    if self._update:
      self._file_object.SetContents(self._io.getvalue())
    if self._closefd:
      self._filesystem.CloseOpenFile(self)
    if self._delete_on_close:
      self._filesystem.RemoveObject(self.name)

  def flush(self):
    """Flush file contents to 'disk'."""
    if self._update:
      self._file_object.SetContents(self._io.getvalue())
      self._file_epoch = self._file_object.epoch

  def seek(self, offset, whence=0):
    """Move read/write pointer in 'file'."""
    if not self._append:
      self._io.seek(offset, whence)
    else:
      self._read_seek = offset
      self._read_whence = whence

  def tell(self):
    """Return the file's current position.

    Returns:
      int, file's current position in bytes.
    """
    if not self._append:
      return self._io.tell()
    if self._read_whence:
      write_seek = self._io.tell()
      self._io.seek(self._read_seek, self._read_whence)
      self._read_seek = self._io.tell()
      self._read_whence = 0
      self._io.seek(write_seek)
    return self._read_seek

  def _UpdateStringIO(self):
    """Updates the StringIO with changes to the file object contents."""
    if self._file_epoch == self._file_object.epoch:
      return
    whence = self._io.tell()
    self._io.seek(0)
    self._io.truncate()
    self._io.write(self._file_object.contents)
    self._io.seek(whence)
    self._file_epoch = self._file_object.epoch

  def _ReadWrappers(self, name):
    """Wrap a StringIO attribute in a read wrapper.

    Returns a read_wrapper which tracks our own read pointer since the
    StringIO object has no concept of a different read and write pointer.

    Args:
      name: the name StringIO attribute to wrap.  Should be a read call.

    Returns:
      either a read_error or read_wrapper function.
    """
    io_attr = getattr(self._io, name)

    def read_wrapper(*args, **kwargs):
      """Wrap all read calls to the StringIO Object.

      We do this to track the read pointer separate from the write
      pointer.  Anything that wants to read from the StringIO object
      while we're in append mode goes through this.

      Args:
        *args: pass through args
        **kwargs: pass through kwargs
      Returns:
        Wrapped StringIO object method
      """
      self._io.seek(self._read_seek, self._read_whence)
      ret_value = io_attr(*args, **kwargs)
      self._read_seek = self._io.tell()
      self._read_whence = 0
      self._io.seek(0, 2)
      return ret_value
    return read_wrapper

  def _OtherWrapper(self, name):
    """Wrap a StringIO attribute in an other_wrapper.

    Args:
      name: the name of the StringIO attribute to wrap.

    Returns:
      other_wrapper which is described below.
    """
    io_attr = getattr(self._io, name)

    def other_wrapper(*args, **kwargs):
      """Wrap all other calls to the StringIO Object.

      We do this to track changes to the write pointer.  Anything that
      moves the write pointer in a file open for appending should move
      the read pointer as well.

      Args:
        *args: pass through args
        **kwargs: pass through kwargs
      Returns:
        Wrapped StringIO object method
      """
      write_seek = self._io.tell()
      ret_value = io_attr(*args, **kwargs)
      if write_seek != self._io.tell():
        self._read_seek = self._io.tell()
        self._read_whence = 0
        self._file_object.st_size += (self._read_seek - write_seek)
      return ret_value
    return other_wrapper

  def Size(self):
    return self._file_object.st_size

  def __getattr__(self, name):
    if self._file_object.IsLargeFile():
      raise FakeLargeFileIoException(self._file_path)

    # errors on called method vs. open mode
    if not self._read and name.startswith('read'):
      def read_error(*args, **kwargs):
        """Throw an error unless the argument is zero."""
        if args and args[0] == 0:
          return ''
        raise self._OPERATION_ERROR('File is not open for reading.')
      return read_error
    if not self._update and (name.startswith('write')
                             or name == 'truncate'):
      def write_error(*args, **kwargs):
        """Throw an error."""
        raise self._OPERATION_ERROR('File is not open for writing.')
      return write_error

    if name.startswith('read'):
      self._UpdateStringIO()
    if self._append:
      if name.startswith('read'):
        return self._ReadWrappers(name)
      else:
        return self._OtherWrapper(name)
    return getattr(self._io, name)

  def __iter__(self):
    if not self._read:
      raise self._OPERATION_ERROR('File is not open for reading')
    return self._io.__iter__()


class FakeFileOpen(object):
  """Faked file() and open() function replacements.

  Returns FakeFile objects in a FakeFilesystem in place of the file()
  or open() function.
  """

  def __init__(self, filesystem, delete_on_close=False):
    """init.

    Args:
      filesystem:  FakeFilesystem used to provide file system information
      delete_on_close:  optional boolean, deletes file on close()
    """
    self.filesystem = filesystem
    self._delete_on_close = delete_on_close

  def __call__(self, *args, **kwargs):
    """Redirects calls to file() or open() to appropriate method."""
    if sys.version_info < (3, 0):
      return self._call_ver2(*args, **kwargs)
    else:
      return self.Call(*args, **kwargs)

  def _call_ver2(self, file_path, mode='r', buffering=-1, flags=None):
    """Limits args of open() or file() for Python 2.x versions."""
    # Backwards compatibility, mode arg used to be named flags
    mode = flags or mode
    return self.Call(file_path, mode, buffering)

  def Call(self, file_, mode='r', buffering=-1, encoding=None,
           errors=None, newline=None, closefd=True, opener=None):
    """Returns a StringIO object with the contents of the target file object.

    Args:
      file_: path to target file or a file descriptor
      mode: additional file modes. All r/w/a r+/w+/a+ modes are supported.
        't', and 'U' are ignored, e.g., 'wU' is treated as 'w'. 'b' sets
        binary mode, no end of line translations in StringIO.
      buffering: ignored. (Used for signature compliance with __builtin__.open)
      encoding: ignored, strings have no encoding
      errors: ignored, this relates to encoding
      newline: controls universal newlines, passed to StringIO object
      closefd: if a file descriptor rather than file name is passed, and set
        to false, then the file descriptor is kept open when file is closed
      opener: not supported

    Returns:
      a StringIO object containing the contents of the target file

    Raises:
      IOError: if the target object is a directory, the path is invalid or
        permission is denied.
    """
    orig_modes = mode  # Save original mdoes for error messages.
    # Binary mode for non 3.x or set by mode
    binary = sys.version_info < (3, 0) or 'b' in mode
    # Normalize modes. Ignore 't' and 'U'.
    mode = mode.replace('t', '').replace('b', '')
    mode = mode.replace('rU', 'r').replace('U', 'r')

    if mode not in _OPEN_MODE_MAP:
      raise IOError('Invalid mode: %r' % orig_modes)

    must_exist, need_read, need_write, truncate, append = _OPEN_MODE_MAP[mode]

    file_object = None
    filedes = None
    # opening a file descriptor
    if isinstance(file_, int):
      filedes = file_
      file_object = self.filesystem.GetOpenFile(filedes).GetObject()
      file_path = file_object.name
    else:
      file_path = file_
      real_path = self.filesystem.ResolvePath(file_path)
      if self.filesystem.Exists(file_path):
        file_object = self.filesystem.GetObjectFromNormalizedPath(real_path)
      closefd = True

    if file_object:
      if ((need_read and not file_object.st_mode & PERM_READ) or
          (need_write and not file_object.st_mode & PERM_WRITE)):
        raise IOError(errno.EACCES, 'Permission denied', file_path)
      if need_write:
        if truncate:
          file_object.SetContents('')
    else:
      if must_exist:
        raise IOError(errno.ENOENT, 'No such file or directory', file_path)
      file_object = self.filesystem.CreateFile(
          real_path, create_missing_dirs=False, apply_umask=True)

    if stat.S_ISDIR(file_object.st_mode):
      raise IOError(errno.EISDIR, 'Fake file object: is a directory', file_path)

    # if you print obj.name, the argument to open() must be printed. Not the
    # abspath, not the filename, but the actual argument.
    file_object.opened_as = file_path

    fakefile = FakeFileWrapper(file_object,
                               file_path,
                               update=need_write,
                               read=need_read,
                               append=append,
                               delete_on_close=self._delete_on_close,
                               filesystem=self.filesystem,
                               newline=newline,
                               binary=binary,
                               closefd=closefd)
    if filedes is not None:
      fakefile.filedes = filedes
    else:
      fakefile.filedes = self.filesystem.AddOpenFile(fakefile)
    return fakefile


def _RunDoctest():
  # pylint: disable-msg=C6204
  import doctest
  from pyfakefs import fake_filesystem  # pylint: disable-msg=W0406
  return doctest.testmod(fake_filesystem)


if __name__ == '__main__':
  _RunDoctest()
