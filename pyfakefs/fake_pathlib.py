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

"""A fake implementation for pathlib working with FakeFilesystem.
Usage:
* With fake_filesystem_unittest:
  If using fake_filesystem_unittest.TestCase, pathlib gets replaced
  by fake_pathlib together with other file system related modules.

* Stand-alone with FakeFilesystem:
  `filesystem = fake_filesystem.FakeFilesystem()`
  `fake_pathlib_module = fake_filesystem.FakePathlibModule(filesystem)`
  `path = fake_pathlib_module.Path('/foo/bar')`

Note: as the implementation is based on FakeFilesystem, all faked classes
(including PurePosixPath, PosixPath, PureWindowsPath and WindowsPath)
get the properties of the underlying fake filesystem.
"""

import os
import pathlib
from urllib.parse import quote_from_bytes as urlquote_from_bytes

import sys

import functools

from pyfakefs.fake_filesystem import FakeFileOpen, FakeFilesystem


def init_module(filesystem):
    FakePath.filesystem = filesystem
    FakePathlibModule.PureWindowsPath._flavour = _FakeWindowsFlavour(filesystem)
    FakePathlibModule.PurePosixPath._flavour = _FakePosixFlavour(filesystem)


class _FakeAccessor(pathlib._Accessor):
    """Accessor which forwards some of the functions to FakeFilesystem methods."""

    def _wrap_strfunc(strfunc):
        @functools.wraps(strfunc)
        def wrapped(pathobj, *args):
            return strfunc(pathobj.filesystem, str(pathobj), *args)

        return staticmethod(wrapped)

    def _wrap_binary_strfunc(strfunc):
        @functools.wraps(strfunc)
        def wrapped(pathobjA, pathobjB, *args):
            return strfunc(pathobjA.filesystem, str(pathobjA), str(pathobjB), *args)

        return staticmethod(wrapped)

    def _wrap_binary_strfunc_reverse(strfunc):
        @functools.wraps(strfunc)
        def wrapped(pathobjA, pathobjB, *args):
            return strfunc(pathobjB.filesystem, str(pathobjB), str(pathobjA), *args)

        return staticmethod(wrapped)

    stat = _wrap_strfunc(FakeFilesystem.GetStat)

    lstat = _wrap_strfunc(lambda fs, path: FakeFilesystem.GetStat(fs, path, follow_symlinks=False))

    listdir = _wrap_strfunc(FakeFilesystem.ListDir)

    chmod = _wrap_strfunc(FakeFilesystem.ChangeMode)

    if hasattr(os, "lchmod"):
        lchmod = _wrap_strfunc(lambda fs, path: FakeFilesystem.ChangeMode(fs, path, follow_symlinks=False))
    else:
        def lchmod(self, pathobj, mode):
            raise NotImplementedError("lchmod() not available on this system")

    mkdir = _wrap_strfunc(FakeFilesystem.MakeDirectory)

    unlink = _wrap_strfunc(FakeFilesystem.RemoveFile)

    rmdir = _wrap_strfunc(FakeFilesystem.RemoveDirectory)

    rename = _wrap_binary_strfunc(FakeFilesystem.RenameObject)

    replace = _wrap_binary_strfunc(lambda fs, old_path, new_path:
                                   FakeFilesystem.RenameObject(fs, old_path, new_path, force_replace=True))

    symlink = _wrap_binary_strfunc_reverse(FakeFilesystem.CreateLink)

    utime = _wrap_strfunc(FakeFilesystem.UpdateTime)


_fake_accessor = _FakeAccessor()


class _FakeFlavour(pathlib._Flavour):
    """Fake Flavour implementation used by PurePath and _Flavour"""

    filesystem = None
    sep = '/'
    altsep = None
    has_drv = False

    ext_namespace_prefix = '\\\\?\\'

    drive_letters = (
        set(chr(x) for x in range(ord('a'), ord('z') + 1)) |
        set(chr(x) for x in range(ord('A'), ord('Z') + 1))
    )

    def __init__(self, filesystem):
        self.filesystem = filesystem
        self.sep = filesystem.path_separator
        self.altsep = filesystem.alternative_path_separator
        self.has_drv = filesystem.supports_drive_letter
        super(_FakeFlavour, self).__init__()

    def _split_extended_path(self, s, ext_prefix=ext_namespace_prefix):
        prefix = ''
        if s.startswith(ext_prefix):
            prefix = s[:4]
            s = s[4:]
            if s.startswith('UNC\\'):
                prefix += s[:3]
                s = '\\' + s[3:]
        return prefix, s

    def _splitroot_with_drive(self, part, sep):
        first = part[0:1]
        second = part[1:2]
        if (second == sep and first == sep):
            # XXX extended paths should also disable the collapsing of "."
            # components (according to MSDN docs).
            prefix, part = self._split_extended_path(part)
            first = part[0:1]
            second = part[1:2]
        else:
            prefix = ''
        third = part[2:3]
        if (second == sep and first == sep and third != sep):
            # is a UNC path:
            # vvvvvvvvvvvvvvvvvvvvv root
            # \\machine\mountpoint\directory\etc\...
            #            directory ^^^^^^^^^^^^^^
            index = part.find(sep, 2)
            if index != -1:
                index2 = part.find(sep, index + 1)
                # a UNC path can't have two slashes in a row
                # (after the initial two)
                if index2 != index + 1:
                    if index2 == -1:
                        index2 = len(part)
                    if prefix:
                        return prefix + part[1:index2], sep, part[index2 + 1:]
                    else:
                        return part[:index2], sep, part[index2 + 1:]
        drv = root = ''
        if second == ':' and first in self.drive_letters:
            drv = part[:2]
            part = part[2:]
            first = third
        if first == sep:
            root = first
            part = part.lstrip(sep)
        return prefix + drv, root, part

    def _splitroot_posix(self, part, sep):
        if part and part[0] == sep:
            stripped_part = part.lstrip(sep)
            if len(part) - len(stripped_part) == 2:
                return '', sep * 2, stripped_part
            else:
                return '', sep, stripped_part
        else:
            return '', '', part

    def splitroot(self, part, sep=None):
        if sep is None:
            sep = self.filesystem.path_separator
        if self.filesystem.supports_drive_letter:
            return self._splitroot_with_drive(part, sep)
        return self._splitroot_posix(part, sep)

    def casefold(self, s):
        if self.filesystem.is_case_sensitive:
            return s
        return s.lower()

    def casefold_parts(self, parts):
        if self.filesystem.is_case_sensitive:
            return parts
        return [p.lower() for p in parts]

    def resolve(self, path):
        return self.filesystem.ResolvePath(str(path))

    def gethomedir(self, username):
        if not username:
            try:
                return os.environ['HOME']
            except KeyError:
                import pwd
                return pwd.getpwuid(os.getuid()).pw_dir
        else:
            import pwd
            try:
                return pwd.getpwnam(username).pw_dir
            except KeyError:
                raise RuntimeError("Can't determine home directory "
                                   "for %r" % username)


class _FakeWindowsFlavour(_FakeFlavour):
    """Flavour used by PureWindowsPath with some Windows specific implementations
    independent of FakeFilesystem properties.
    """
    reserved_names = (
        {'CON', 'PRN', 'AUX', 'NUL'} |
        {'COM%d' % i for i in range(1, 10)} |
        {'LPT%d' % i for i in range(1, 10)}
    )

    def is_reserved(self, parts):
        # NOTE: the rules for reserved names seem somewhat complicated
        # (e.g. r"..\NUL" is reserved but not r"foo\NUL").
        # We err on the side of caution and return True for paths which are
        # not considered reserved by Windows.
        if not parts:
            return False
        if self.filesystem.supports_drive_letter and parts[0].startswith('\\\\'):
            # UNC paths are never reserved
            return False
        return parts[-1].partition('.')[0].upper() in self.reserved_names

    def make_uri(self, path):
        # Under Windows, file URIs use the UTF-8 encoding.
        # original version, not faked
        # todo: make this part dependent on drive support, add encoding as property
        drive = path.drive
        if len(drive) == 2 and drive[1] == ':':
            # It's a path on a local drive => 'file:///c:/a/b'
            rest = path.as_posix()[2:].lstrip('/')
            return 'file:///%s/%s' % (
                drive, urlquote_from_bytes(rest.encode('utf-8')))
        else:
            # It's a path on a network drive => 'file://host/share/a/b'
            return 'file:' + urlquote_from_bytes(path.as_posix().encode('utf-8'))

    def gethomedir(self, username):
        # original version, not faked
        if 'HOME' in os.environ:
            userhome = os.environ['HOME']
        elif 'USERPROFILE' in os.environ:
            userhome = os.environ['USERPROFILE']
        elif 'HOMEPATH' in os.environ:
            try:
                drv = os.environ['HOMEDRIVE']
            except KeyError:
                drv = ''
            userhome = drv + os.environ['HOMEPATH']
        else:
            raise RuntimeError("Can't determine home directory")

        if username:
            # Try to guess user home directory.  By default all users
            # directories are located in the same place and are named by
            # corresponding usernames.  If current user home directory points
            # to nonstandard place, this guess is likely wrong.
            if os.environ['USERNAME'] != username:
                drv, root, parts = self.parse_parts((userhome,))
                if parts[-1] != os.environ['USERNAME']:
                    raise RuntimeError("Can't determine home directory "
                                       "for %r" % username)
                parts[-1] = username
                if drv or root:
                    userhome = drv + root + self.join(parts[1:])
                else:
                    userhome = self.join(parts)
        return userhome


class _FakePosixFlavour(_FakeFlavour):
    """Flavour used by PurePosixPath with some Unix specific implementations
    independent of FakeFilesystem properties.
    """

    def is_reserved(self, parts):
        return False

    def make_uri(self, path):
        # We represent the path using the local filesystem encoding,
        # for portability to other applications.
        bpath = bytes(path)
        return 'file://' + urlquote_from_bytes(bpath)

    def gethomedir(self, username):
        # original version, not faked
        if not username:
            try:
                return os.environ['HOME']
            except KeyError:
                import pwd
                return pwd.getpwuid(os.getuid()).pw_dir
        else:
            import pwd
            try:
                return pwd.getpwnam(username).pw_dir
            except KeyError:
                raise RuntimeError("Can't determine home directory "
                                   "for %r" % username)


class FakePath(pathlib.Path):
    """Replacement for pathlib.Path. Reimplement some methods to use fake filesystem.
    The rest of the methods work as they are, as they will use the fake accessor.
    """

    # the underlying fake filesystem
    filesystem = None

    def __new__(cls, *args, **kwargs):
        """Creates the correct subclass based on OS."""
        if cls is FakePathlibModule.Path:
            cls = FakePathlibModule.WindowsPath if os.name == 'nt' else FakePathlibModule.PosixPath
        self = cls._from_parts(args, init=True)
        return self

    def _path(self):
        """Returns the underlying path string as used by the fake filesystem."""
        return str(self)

    def _init(self, template=None):
        """Initializer called from base class."""
        self._accessor = _fake_accessor
        self._closed = False

    @classmethod
    def cwd(cls):
        """Return a new path pointing to the current working directory
        (as returned by os.getcwd()).
        """
        return cls(cls.filesystem.cwd)

    @classmethod
    def home(cls):
        """Return a new path pointing to the user's home directory (as
        returned by os.path.expanduser('~')).
        """
        return cls(cls()._flavour.gethomedir(None).
                   replace(os.sep, cls.filesystem.path_separator))

    def samefile(self, other_path):
        """Return whether other_path is the same or not as this file
        (as returned by os.path.samefile()).

        Args:
            other_path: a path object or string of the file object to be compared with

        Raises:
          OSError: if the filesystem object doesn't exist.
        """
        st = self.stat()
        try:
            other_st = other_path.stat()
        except AttributeError:
            other_st = self.filesystem.GetStat(other_path)
        return st.st_ino == other_st.st_ino and st.st_dev == other_st.st_dev

    def resolve(self):
        """Make the path absolute, resolving all symlinks on the way and also
        normalizing it (for example turning slashes into backslashes under Windows).

        Raises:
            IOError: if the path doesn't exist
        """
        if self._closed:
            self._raise_closed()
        path = self.filesystem.ResolvePath(self._path())
        return FakePath(path)

    def open(self, mode='r', buffering=-1, encoding=None,
             errors=None, newline=None):
        """Open the file pointed by this path and return a fake file object.

        Raises:
            IOError: if the target object is a directory, the path is invalid or
                permission is denied.
        """
        if self._closed:
            self._raise_closed()
        return FakeFileOpen(self.filesystem)(self._path(), mode, buffering, encoding, errors, newline)

    if sys.version_info >= (3, 5):
        def read_bytes(self):
            """Open the fake file in bytes mode, read it, and close the file.

            Raises:
                IOError: if the target object is a directory, the path is invalid or
                    permission is denied.
            """
            with FakeFileOpen(self.filesystem)(self._path(), mode='rb') as f:
                return f.read()

        def read_text(self, encoding=None, errors=None):
            """
            Open the fake file in text mode, read it, and close the file.
            """
            with FakeFileOpen(self.filesystem)(
                    self._path(), mode='r', encoding=encoding, errors=errors) as f:
                return f.read()

        def write_bytes(self, data):
            """Open the fake file in bytes mode, write to it, and close the file.
            Args:
                data: the bytes to be written
            Raises:
                IOError: if the target object is a directory, the path is invalid or
                    permission is denied.
            """
            # type-check for the buffer interface before truncating the file
            view = memoryview(data)
            with FakeFileOpen(self.filesystem)(self._path(), mode='wb') as f:
                return f.write(view)

        def write_text(self, data, encoding=None, errors=None):
            """Open the fake file in text mode, write to it, and close the file.

            Args:
                data: the string to be written
                encoding: the encoding used for the string; if not given, the
                    default locale encoding is used
                errors: ignored
            Raises:
                TypeError: if data is not of type 'str'
                IOError: if the target object is a directory, the path is invalid or
                    permission is denied.
            """
            if not isinstance(data, str):
                raise TypeError('data must be str, not %s' %
                                data.__class__.__name__)
            with FakeFileOpen(self.filesystem)(self._path(), mode='w', encoding=encoding, errors=errors) as f:
                return f.write(data)

    def touch(self, mode=0o666, exist_ok=True):
        """Create a fake file for the path with the given access mode, if it doesn't exist.

        Args:
            mode: the file mode for the file if it does not exist
            exist_ok: if the file already exists and this is True, nothinh happens,
                otherwise FileExistError is raised

        Raises:
            FileExistsError if the file exists and exits_ok is False.
        """
        if self._closed:
            self._raise_closed()
        if self.exists():
            if exist_ok:
                self.filesystem.UpdateTime(self._path(), None)
            else:
                raise FileExistsError
        else:
            fake_file = self.open('w')
            fake_file.close()
            self.chmod(mode)

    def expanduser(self):
        """ Return a new path with expanded ~ and ~user constructs
        (as returned by os.path.expanduser)
        """
        return FakePath(os.path.expanduser(self._path())
                        .replace(os.path.sep, self.filesystem.path_separator))


class FakePathlibModule(object):
    """Uses FakeFilesystem to provide a fake pathlib module replacement.

    You need a fake_filesystem to use this:
    `filesystem = fake_filesystem.FakeFilesystem()`
    `fake_pathlib_module = fake_filesystem.FakePathlibModule(filesystem)`
    """

    def __init__(self, filesystem):
        """
        Initializes the module with the given filesystem.

        Args:
            filesystem: FakeFilesystem used to provide file system information
        """
        init_module(filesystem)
        self._pathlib_module = pathlib

    class PurePosixPath(pathlib.PurePath):
        __slots__ = ()

    class PureWindowsPath(pathlib.PurePath):
        __slots__ = ()

    if sys.platform == 'win32':
        class WindowsPath(FakePath, PureWindowsPath):
            __slots__ = ()
    else:
        class PosixPath(FakePath, PurePosixPath):
            __slots__ = ()

    Path = FakePath

    def __getattr__(self, name):
        """Forwards any unfaked calls to the standard pathlib module."""
        return getattr(self._pathlib_module, name)
