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
New in pyfakefs 3.0.

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
import errno
import fnmatch
import functools
import inspect
import os
import pathlib
import re
import sys
from pathlib import PurePath
from typing import Callable
from urllib.parse import quote_from_bytes as urlquote_from_bytes

from pyfakefs import fake_scandir
from pyfakefs.extra_packages import use_scandir
from pyfakefs.fake_filesystem import (
    FakeFileOpen, FakeFilesystem, use_original_os
)


def init_module(filesystem):
    """Initializes the fake module with the fake file system."""
    # pylint: disable=protected-access
    FakePath.filesystem = filesystem
    FakePathlibModule.PureWindowsPath._flavour = _FakeWindowsFlavour(
        filesystem)
    FakePathlibModule.PurePosixPath._flavour = _FakePosixFlavour(filesystem)


def _wrap_strfunc(strfunc):
    @functools.wraps(strfunc)
    def _wrapped(pathobj, *args, **kwargs):
        return strfunc(pathobj.filesystem, str(pathobj), *args, **kwargs)

    return staticmethod(_wrapped)


def _wrap_binary_strfunc(strfunc):
    @functools.wraps(strfunc)
    def _wrapped(pathobj1, pathobj2, *args):
        return strfunc(
            pathobj1.filesystem, str(pathobj1), str(pathobj2), *args)

    return staticmethod(_wrapped)


def _wrap_binary_strfunc_reverse(strfunc):
    @functools.wraps(strfunc)
    def _wrapped(pathobj1, pathobj2, *args):
        return strfunc(
            pathobj2.filesystem, str(pathobj2), str(pathobj1), *args)

    return staticmethod(_wrapped)


try:
    accessor = pathlib._Accessor  # type: ignore [attr-defined]
except AttributeError:
    accessor = object


class _FakeAccessor(accessor):  # type: ignore [valid-type, misc]
    """Accessor which forwards some of the functions to FakeFilesystem methods.
    """

    stat = _wrap_strfunc(FakeFilesystem.stat)

    lstat = _wrap_strfunc(
        lambda fs, path: FakeFilesystem.stat(fs, path, follow_symlinks=False))

    listdir = _wrap_strfunc(FakeFilesystem.listdir)

    if use_scandir:
        scandir = _wrap_strfunc(fake_scandir.scandir)

    if hasattr(os, "lchmod"):
        lchmod = _wrap_strfunc(lambda fs, path, mode: FakeFilesystem.chmod(
            fs, path, mode, follow_symlinks=False))
    else:
        def lchmod(self, pathobj, *args, **kwargs):
            """Raises not implemented for Windows systems."""
            raise NotImplementedError("lchmod() not available on this system")

    def chmod(self, pathobj, *args, **kwargs):
        if "follow_symlinks" in kwargs:
            if sys.version_info < (3, 10):
                raise TypeError("chmod() got an unexpected keyword "
                                "argument 'follow_symlinks'")

            if (not kwargs["follow_symlinks"] and
                    os.os_module.chmod not in os.supports_follow_symlinks):
                raise NotImplementedError(
                    "`follow_symlinks` for chmod() is not available "
                    "on this system")
        return pathobj.filesystem.chmod(str(pathobj), *args, **kwargs)

    mkdir = _wrap_strfunc(FakeFilesystem.makedir)

    unlink = _wrap_strfunc(FakeFilesystem.remove)

    rmdir = _wrap_strfunc(FakeFilesystem.rmdir)

    rename = _wrap_binary_strfunc(FakeFilesystem.rename)

    replace = _wrap_binary_strfunc(
        lambda fs, old_path, new_path: FakeFilesystem.rename(
            fs, old_path, new_path, force_replace=True))

    symlink = _wrap_binary_strfunc_reverse(
        lambda fs, file_path, link_target, target_is_directory:
        FakeFilesystem.create_symlink(fs, file_path, link_target,
                                      create_missing_dirs=False))

    if (3, 8) <= sys.version_info:
        link_to = _wrap_binary_strfunc(
            lambda fs, file_path, link_target:
            FakeFilesystem.link(fs, file_path, link_target))

    if sys.version_info >= (3, 10):
        link = _wrap_binary_strfunc(
            lambda fs, file_path, link_target:
            FakeFilesystem.link(fs, file_path, link_target))

        # this will use the fake filesystem because os is patched
        def getcwd(self):
            return os.getcwd()

    readlink = _wrap_strfunc(FakeFilesystem.readlink)

    utime = _wrap_strfunc(FakeFilesystem.utime)


_fake_accessor = _FakeAccessor()

flavour = pathlib._Flavour  # type: ignore [attr-defined]


class _FakeFlavour(flavour):  # type: ignore [valid-type, misc]
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
        self.has_drv = filesystem.is_windows_fs
        super(_FakeFlavour, self).__init__()

    @staticmethod
    def _split_extended_path(path, ext_prefix=ext_namespace_prefix):
        prefix = ''
        if path.startswith(ext_prefix):
            prefix = path[:4]
            path = path[4:]
            if path.startswith('UNC\\'):
                prefix += path[:3]
                path = '\\' + path[3:]
        return prefix, path

    def _splitroot_with_drive(self, path, sep):
        first = path[0:1]
        second = path[1:2]
        if second == sep and first == sep:
            # extended paths should also disable the collapsing of "."
            # components (according to MSDN docs).
            prefix, path = self._split_extended_path(path)
            first = path[0:1]
            second = path[1:2]
        else:
            prefix = ''
        third = path[2:3]
        if second == sep and first == sep and third != sep:
            # is a UNC path:
            # vvvvvvvvvvvvvvvvvvvvv root
            # \\machine\mountpoint\directory\etc\...
            #            directory ^^^^^^^^^^^^^^
            index = path.find(sep, 2)
            if index != -1:
                index2 = path.find(sep, index + 1)
                # a UNC path can't have two slashes in a row
                # (after the initial two)
                if index2 != index + 1:
                    if index2 == -1:
                        index2 = len(path)
                    if prefix:
                        return prefix + path[1:index2], sep, path[index2 + 1:]
                    return path[:index2], sep, path[index2 + 1:]
        drv = root = ''
        if second == ':' and first in self.drive_letters:
            drv = path[:2]
            path = path[2:]
            first = third
        if first == sep:
            root = first
            path = path.lstrip(sep)
        return prefix + drv, root, path

    @staticmethod
    def _splitroot_posix(path, sep):
        if path and path[0] == sep:
            stripped_part = path.lstrip(sep)
            if len(path) - len(stripped_part) == 2:
                return '', sep * 2, stripped_part
            return '', sep, stripped_part
        else:
            return '', '', path

    def splitroot(self, path, sep=None):
        """Split path into drive, root and rest."""
        if sep is None:
            sep = self.filesystem.path_separator
        if self.filesystem.is_windows_fs:
            return self._splitroot_with_drive(path, sep)
        return self._splitroot_posix(path, sep)

    def casefold(self, path):
        """Return the lower-case version of s for a Windows filesystem."""
        if self.filesystem.is_windows_fs:
            return path.lower()
        return path

    def casefold_parts(self, parts):
        """Return the lower-case version of parts for a Windows filesystem."""
        if self.filesystem.is_windows_fs:
            return [p.lower() for p in parts]
        return parts

    def _resolve_posix(self, path, strict):
        sep = self.sep
        seen = {}

        def _resolve(path, rest):
            if rest.startswith(sep):
                path = ''

            for name in rest.split(sep):
                if not name or name == '.':
                    # current dir
                    continue
                if name == '..':
                    # parent dir
                    path, _, _ = path.rpartition(sep)
                    continue
                newpath = path + sep + name
                if newpath in seen:
                    # Already seen this path
                    path = seen[newpath]
                    if path is not None:
                        # use cached value
                        continue
                    # The symlink is not resolved, so we must have
                    # a symlink loop.
                    raise RuntimeError("Symlink loop from %r" % newpath)
                # Resolve the symbolic link
                try:
                    target = self.filesystem.readlink(newpath)
                except OSError as e:
                    if e.errno != errno.EINVAL and strict:
                        raise
                    # Not a symlink, or non-strict mode. We just leave the path
                    # untouched.
                    path = newpath
                else:
                    seen[newpath] = None  # not resolved symlink
                    path = _resolve(path, target)
                    seen[newpath] = path  # resolved symlink

            return path

        # NOTE: according to POSIX, getcwd() cannot contain path components
        # which are symlinks.
        base = '' if path.is_absolute() else self.filesystem.cwd
        return _resolve(base, str(path)) or sep

    def _resolve_windows(self, path, strict):
        path = str(path)
        if not path:
            return os.getcwd()
        previous_s = None
        if strict:
            if not self.filesystem.exists(path):
                self.filesystem.raise_os_error(errno.ENOENT, path)
            return self.filesystem.resolve_path(path)
        else:
            while True:
                try:
                    path = self.filesystem.resolve_path(path)
                except OSError:
                    previous_s = path
                    path = self.filesystem.splitpath(path)[0]
                else:
                    if previous_s is None:
                        return path
                    return self.filesystem.joinpaths(
                        path, os.path.basename(previous_s))

    def resolve(self, path, strict):
        """Make the path absolute, resolving any symlinks."""
        if self.filesystem.is_windows_fs:
            return self._resolve_windows(path, strict)
        return self._resolve_posix(path, strict)

    def gethomedir(self, username):
        """Return the home directory of the current user."""
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
    """Flavour used by PureWindowsPath with some Windows specific
    implementations independent of FakeFilesystem properties.
    """
    reserved_names = (
            {'CON', 'PRN', 'AUX', 'NUL'} |
            {'COM%d' % i for i in range(1, 10)} |
            {'LPT%d' % i for i in range(1, 10)}
    )

    def is_reserved(self, parts):
        """Return True if the path is considered reserved under Windows."""

        # NOTE: the rules for reserved names seem somewhat complicated
        # (e.g. r"..\NUL" is reserved but not r"foo\NUL").
        # We err on the side of caution and return True for paths which are
        # not considered reserved by Windows.
        if not parts:
            return False
        if self.filesystem.is_windows_fs and parts[0].startswith('\\\\'):
            # UNC paths are never reserved
            return False
        return parts[-1].partition('.')[0].upper() in self.reserved_names

    def make_uri(self, path):
        """Return a file URI for the given path"""

        # Under Windows, file URIs use the UTF-8 encoding.
        # original version, not faked
        drive = path.drive
        if len(drive) == 2 and drive[1] == ':':
            # It's a path on a local drive => 'file:///c:/a/b'
            rest = path.as_posix()[2:].lstrip('/')
            return 'file:///%s/%s' % (
                drive, urlquote_from_bytes(rest.encode('utf-8')))
        else:
            # It's a path on a network drive => 'file://host/share/a/b'
            return ('file:' +
                    urlquote_from_bytes(path.as_posix().encode('utf-8')))

    def gethomedir(self, username):
        """Return the home directory of the current user."""

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

    def compile_pattern(self, pattern):
        return re.compile(fnmatch.translate(pattern), re.IGNORECASE).fullmatch


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

    def compile_pattern(self, pattern):
        return re.compile(fnmatch.translate(pattern)).fullmatch


class FakePath(pathlib.Path):
    """Replacement for pathlib.Path. Reimplement some methods to use
    fake filesystem. The rest of the methods work as they are, as they will
    use the fake accessor.
    New in pyfakefs 3.0.
    """

    # the underlying fake filesystem
    filesystem = None

    def __new__(cls, *args, **kwargs):
        """Creates the correct subclass based on OS."""
        if cls is FakePathlibModule.Path:
            cls = (FakePathlibModule.WindowsPath
                   if cls.filesystem.is_windows_fs
                   else FakePathlibModule.PosixPath)
        self = cls._from_parts(args)
        return self

    @classmethod
    def _from_parts(cls, args, init=False):  # pylint: disable=unused-argument
        # Overwritten to call _init to set the fake accessor,
        # which is not done since Python 3.10
        self = object.__new__(cls)
        self._init()
        drv, root, parts = self._parse_args(args)
        self._drv = drv
        self._root = root
        self._parts = parts
        return self

    @classmethod
    def _from_parsed_parts(cls, drv, root, parts):
        # Overwritten to call _init to set the fake accessor,
        # which is not done since Python 3.10
        self = object.__new__(cls)
        self._init()
        self._drv = drv
        self._root = root
        self._parts = parts
        return self

    def _init(self, template=None):
        """Initializer called from base class."""
        self._accessor = _fake_accessor
        self._closed = False

    def _path(self):
        """Returns the underlying path string as used by the fake filesystem.
        """
        return str(self)

    @classmethod
    def cwd(cls):
        """Return a new path pointing to the current working directory
        (as returned by os.getcwd()).
        """
        return cls(cls.filesystem.cwd)

    def resolve(self, strict=None):
        """Make the path absolute, resolving all symlinks on the way and also
        normalizing it (for example turning slashes into backslashes
        under Windows).

        Args:
            strict: If False (default) no exception is raised if the path
                does not exist.
                New in Python 3.6.

        Raises:
            OSError: if the path doesn't exist (strict=True or Python < 3.6)
        """
        if sys.version_info >= (3, 6):
            if strict is None:
                strict = False
        else:
            if strict is not None:
                raise TypeError(
                    "resolve() got an unexpected keyword argument 'strict'")
            strict = True
        if self._closed:
            self._raise_closed()
        path = self._flavour.resolve(self, strict=strict)
        if path is None:
            self.stat()
            path = str(self.absolute())
        path = self.filesystem.absnormpath(path)
        return FakePath(path)

    def open(self, mode='r', buffering=-1, encoding=None,
             errors=None, newline=None):
        """Open the file pointed by this path and return a fake file object.

        Raises:
            OSError: if the target object is a directory, the path is invalid
                or permission is denied.
        """
        if self._closed:
            self._raise_closed()
        return FakeFileOpen(self.filesystem)(
            self._path(), mode, buffering, encoding, errors, newline)

    def read_bytes(self):
        """Open the fake file in bytes mode, read it, and close the file.

        Raises:
            OSError: if the target object is a directory, the path is
                invalid or permission is denied.
        """
        with FakeFileOpen(self.filesystem)(self._path(), mode='rb') as f:
            return f.read()

    def read_text(self, encoding=None, errors=None):
        """
        Open the fake file in text mode, read it, and close the file.
        """
        with FakeFileOpen(self.filesystem)(self._path(), mode='r',
                                           encoding=encoding,
                                           errors=errors) as f:
            return f.read()

    def write_bytes(self, data):
        """Open the fake file in bytes mode, write to it, and close the file.
        Args:
            data: the bytes to be written
        Raises:
            OSError: if the target object is a directory, the path is
                invalid or permission is denied.
        """
        # type-check for the buffer interface before truncating the file
        view = memoryview(data)
        with FakeFileOpen(self.filesystem)(self._path(), mode='wb') as f:
            return f.write(view)

    def write_text(self, data, encoding=None, errors=None, newline=None):
        """Open the fake file in text mode, write to it, and close
        the file.

        Args:
            data: the string to be written
            encoding: the encoding used for the string; if not given, the
                default locale encoding is used
            errors: (str) Defines how encoding errors are handled.
            newline: Controls universal newlines, passed to stream object.
                New in Python 3.10.
        Raises:
            TypeError: if data is not of type 'str'.
            OSError: if the target object is a directory, the path is
                invalid or permission is denied.
        """
        if not isinstance(data, str):
            raise TypeError('data must be str, not %s' %
                            data.__class__.__name__)
        if newline is not None and sys.version_info < (3, 10):
            raise TypeError("write_text() got an unexpected "
                            "keyword argument 'newline'")
        with FakeFileOpen(self.filesystem)(self._path(),
                                           mode='w',
                                           encoding=encoding,
                                           errors=errors,
                                           newline=newline) as f:
            return f.write(data)

    @classmethod
    def home(cls):
        """Return a new path pointing to the user's home directory (as
        returned by os.path.expanduser('~')).
        """
        home = os.path.expanduser("~")
        if cls.filesystem.is_windows_fs != (os.name == 'nt'):
            username = os.path.split(home)[1]
            if cls.filesystem.is_windows_fs:
                home = os.path.join('C:', 'Users', username)
            else:
                home = os.path.join('home', username)
            if not cls.filesystem.exists(home):
                cls.filesystem.create_dir(home)
        return cls(home.replace(os.sep, cls.filesystem.path_separator))

    def samefile(self, other_path):
        """Return whether other_path is the same or not as this file
        (as returned by os.path.samefile()).

        Args:
            other_path: A path object or string of the file object
            to be compared with

        Raises:
            OSError: if the filesystem object doesn't exist.
        """
        st = self.stat()
        try:
            other_st = other_path.stat()
        except AttributeError:
            other_st = self.filesystem.stat(other_path)
        return (st.st_ino == other_st.st_ino and
                st.st_dev == other_st.st_dev)

    def expanduser(self):
        """ Return a new path with expanded ~ and ~user constructs
        (as returned by os.path.expanduser)
        """
        return FakePath(os.path.expanduser(self._path())
                        .replace(os.path.sep,
                                 self.filesystem.path_separator))

    def touch(self, mode=0o666, exist_ok=True):
        """Create a fake file for the path with the given access mode,
        if it doesn't exist.

        Args:
            mode: the file mode for the file if it does not exist
            exist_ok: if the file already exists and this is True, nothing
                happens, otherwise FileExistError is raised

        Raises:
            FileExistsError: if the file exists and exits_ok is False.
        """
        if self._closed:
            self._raise_closed()
        if self.exists():
            if exist_ok:
                self.filesystem.utime(self._path(), times=None)
            else:
                self.filesystem.raise_os_error(errno.EEXIST, self._path())
        else:
            fake_file = self.open('w')
            fake_file.close()
            self.chmod(mode)


class FakePathlibModule:
    """Uses FakeFilesystem to provide a fake pathlib module replacement.
    Can be used to replace both the standard `pathlib` module and the
    `pathlib2` package available on PyPi.

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

    class PurePosixPath(PurePath):
        """A subclass of PurePath, that represents non-Windows filesystem
        paths"""
        __slots__ = ()

    class PureWindowsPath(PurePath):
        """A subclass of PurePath, that represents Windows filesystem paths"""
        __slots__ = ()

    class WindowsPath(FakePath, PureWindowsPath):
        """A subclass of Path and PureWindowsPath that represents
        concrete Windows filesystem paths.
        """
        __slots__ = ()

        def owner(self):
            raise NotImplementedError(
                "Path.owner() is unsupported on this system")

        def group(self):
            raise NotImplementedError(
                "Path.group() is unsupported on this system")

        def is_mount(self):
            raise NotImplementedError(
                "Path.is_mount() is unsupported on this system")

    class PosixPath(FakePath, PurePosixPath):
        """A subclass of Path and PurePosixPath that represents
        concrete non-Windows filesystem paths.
        """
        __slots__ = ()

        def owner(self):
            """Return the username of the file owner.
             It is assumed that `st_uid` is related to a real user,
             otherwise `KeyError` is raised.
            """
            import pwd

            return pwd.getpwuid(self.stat().st_uid).pw_name

        def group(self):
            """Return the group name of the file group.
            It is assumed that `st_gid` is related to a real group,
            otherwise `KeyError` is raised.
            """
            import grp

            return grp.getgrgid(self.stat().st_gid).gr_name

    Path = FakePath

    def __getattr__(self, name):
        """Forwards any unfaked calls to the standard pathlib module."""
        return getattr(self._pathlib_module, name)


class FakePathlibPathModule:
    """Patches `pathlib.Path` by passing all calls to FakePathlibModule."""
    fake_pathlib = None

    def __init__(self, filesystem=None):
        if self.fake_pathlib is None:
            self.__class__.fake_pathlib = FakePathlibModule(filesystem)

    def __call__(self, *args, **kwargs):
        return self.fake_pathlib.Path(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.fake_pathlib.Path, name)

    @classmethod
    def __instancecheck__(cls, instance):
        # fake the inheritance to pass isinstance checks - see #666
        return isinstance(instance, PurePath)


class RealPath(pathlib.Path):
    """Replacement for `pathlib.Path` if it shall not be faked.
    Needed because `Path` in `pathlib` is always faked, even if `pathlib`
    itself is not.
    """
    _flavour = (pathlib._WindowsFlavour() if os.name == 'nt'  # type:ignore
                else pathlib._PosixFlavour())  # type:ignore

    def __new__(cls, *args, **kwargs):
        """Creates the correct subclass based on OS."""
        if cls is RealPathlibModule.Path:
            cls = (RealPathlibModule.WindowsPath if os.name == 'nt'
                   else RealPathlibModule.PosixPath)
        self = cls._from_parts(args)
        return self


if sys.version_info > (3, 10):
    def with_original_os(f: Callable) -> Callable:
        """Decorator used for real pathlib Path methods to ensure that
        real os functions instead of faked ones are used."""
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            with use_original_os():
                return f(*args, **kwargs)
        return wrapped

    for name, fn in inspect.getmembers(RealPath, inspect.isfunction):
        setattr(RealPath, name, with_original_os(fn))


class RealPathlibPathModule:
    """Patches `pathlib.Path` by passing all calls to RealPathlibModule."""
    real_pathlib = None

    @classmethod
    def __instancecheck__(cls, instance):
        # as we cannot derive from pathlib.Path, we fake
        # the inheritance to pass isinstance checks - see #666
        return isinstance(instance, PurePath)

    def __init__(self):
        if self.real_pathlib is None:
            self.__class__.real_pathlib = RealPathlibModule()

    def __call__(self, *args, **kwargs):
        return RealPath(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.real_pathlib.Path, name)


class RealPathlibModule:
    """Used to replace `pathlib` for skipped modules.
    As the original `pathlib` is always patched to use the fake path,
    we need to provide a version which does not do this.
    """

    def __init__(self):
        self._pathlib_module = pathlib

    class PurePosixPath(PurePath):
        """A subclass of PurePath, that represents Posix filesystem paths"""
        __slots__ = ()

    class PureWindowsPath(PurePath):
        """A subclass of PurePath, that represents Windows filesystem paths"""
        __slots__ = ()

    if sys.platform == 'win32':
        class WindowsPath(RealPath, PureWindowsPath):
            """A subclass of Path and PureWindowsPath that represents
            concrete Windows filesystem paths.
            """
            __slots__ = ()
    else:
        class PosixPath(RealPath, PurePosixPath):
            """A subclass of Path and PurePosixPath that represents
            concrete non-Windows filesystem paths.
            """
            __slots__ = ()

    Path = RealPath

    def __getattr__(self, name):
        """Forwards any unfaked calls to the standard pathlib module."""
        return getattr(self._pathlib_module, name)
