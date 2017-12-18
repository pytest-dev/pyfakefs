#! /usr/bin/env python
# -*- coding: utf-8 -*-
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

"""
Unittests for fake_pathlib.
As most of fake_pathlib is a wrapper around fake_filesystem methods, the tests
are there mostly to ensure basic functionality.
Note that many of the tests are directly taken from examples in the python docs.
"""

import os
import pathlib
import stat
import sys
import unittest

from fake_filesystem_test import RealFsTestCase
from pyfakefs import fake_pathlib

is_windows = sys.platform == 'win32'


class RealPathlibTestCase(RealFsTestCase):
    def __init__(self, methodName='runTest'):
        super(RealPathlibTestCase, self).__init__(methodName)
        self.pathlib = pathlib
        self.path = None

    def setUp(self):
        super(RealPathlibTestCase, self).setUp()
        if not self.use_real_fs():
            self.pathlib = fake_pathlib.FakePathlibModule(self.filesystem)
        self.path = self.pathlib.Path


class FakePathlibInitializationTest(RealPathlibTestCase):
    def test_initialization_type(self):
        """Make sure tests for class type will work"""
        path = self.path('/test')
        if is_windows:
            self.assertTrue(isinstance(path, self.pathlib.WindowsPath))
            self.assertTrue(isinstance(path, self.pathlib.PureWindowsPath))
            self.assertTrue(self.pathlib.PurePosixPath())
            self.assertRaises(NotImplementedError, self.pathlib.PosixPath)
        else:
            self.assertTrue(isinstance(path, self.pathlib.PosixPath))
            self.assertTrue(isinstance(path, self.pathlib.PurePosixPath))
            self.assertTrue(self.pathlib.PureWindowsPath())
            self.assertRaises(NotImplementedError, self.pathlib.WindowsPath)

    def test_init_with_segments(self):
        """Basic initialization tests - taken from pathlib.Path documentation"""
        self.assertEqual(self.path('/', 'foo', 'bar', 'baz'),
                         self.path('/foo/bar/baz'))
        self.assertEqual(self.path(), self.path('.'))
        self.assertEqual(self.path(self.path('foo'), self.path('bar')),
                         self.path('foo/bar'))
        self.assertEqual(self.path('/etc') / 'init.d' / 'reboot',
                         self.path('/etc/init.d/reboot'))

    def test_init_collapse(self):
        """Tests for collapsing path during initialization.
        Taken from pathlib.PurePath documentation.
        """
        self.assertEqual(self.path('foo//bar'), self.path('foo/bar'))
        self.assertEqual(self.path('foo/./bar'), self.path('foo/bar'))
        self.assertNotEqual(self.path('foo/../bar'), self.path('foo/bar'))
        self.assertEqual(self.path('/etc', '/usr', 'lib64'),
                         self.path('/usr/lib64'))

    def test_path_parts(self):
        sep = self.os.path.sep
        path = self.path(sep + self.os.path.join('foo', 'bar', 'setup.py'))
        self.assertEqual(path.parts, (sep, 'foo', 'bar', 'setup.py'))
        self.assertEqual(path.drive, '')
        self.assertEqual(path.root, sep)
        self.assertEqual(path.anchor, sep)
        self.assertEqual(path.name, 'setup.py')
        self.assertEqual(path.stem, 'setup')
        self.assertEqual(path.suffix, '.py')
        self.assertEqual(path.parent,
                         self.path(sep + self.os.path.join('foo', 'bar')))
        self.assertEqual(path.parents[0],
                         self.path(sep + self.os.path.join('foo', 'bar')))
        self.assertEqual(path.parents[1], self.path(sep + 'foo'))
        self.assertEqual(path.parents[2], self.path(sep))

    @unittest.skipIf(is_windows, 'POSIX specific behavior')
    def test_is_absolute_posix(self):
        self.assertTrue(self.path('/a/b').is_absolute())
        self.assertFalse(self.path('a/b').is_absolute())
        self.assertFalse(self.path('d:/b').is_absolute())

    @unittest.skipIf(not is_windows, 'Windows specific behavior')
    def test_is_absolute_windows(self):
        self.assertFalse(self.path('/a/b').is_absolute())
        self.assertFalse(self.path('a/b').is_absolute())
        self.assertTrue(self.path('d:/b').is_absolute())


class RealPathlibInitializationTest(FakePathlibInitializationTest):
    def use_real_fs(self):
        return True


@unittest.skipIf(not is_windows, 'Windows specific behavior')
class FakePathlibInitializationWithDriveTest(RealPathlibTestCase):
    def test_init_with_segments(self):
        """Basic initialization tests - taken from pathlib.Path documentation
        """
        self.assertEqual(self.path('c:/', 'foo', 'bar', 'baz'),
                         self.path('c:/foo/bar/baz'))
        self.assertEqual(self.path(), self.path('.'))
        self.assertEqual(self.path(self.path('foo'), self.path('bar')),
                         self.path('foo/bar'))
        self.assertEqual(self.path('c:/Users') / 'john' / 'data',
                         self.path('c:/Users/john/data'))

    def test_init_collapse(self):
        """Tests for collapsing path during initialization.
        Taken from pathlib.PurePath documentation.
        """
        self.assertEqual(self.path('c:/Windows', 'd:bar'),
                         self.path('d:bar'))
        self.assertEqual(self.path('c:/Windows', '/Program Files'),
                         self.path('c:/Program Files'))

    def test_path_parts(self):
        path = self.path(self.os.path.join('d:', 'python scripts', 'setup.py'))
        self.assertEqual(path.parts, ('d:', 'python scripts', 'setup.py'))
        self.assertEqual(path.drive, 'd:')
        self.assertEqual(path.root, '')
        self.assertEqual(path.anchor, 'd:')
        self.assertEqual(path.name, 'setup.py')
        self.assertEqual(path.stem, 'setup')
        self.assertEqual(path.suffix, '.py')
        self.assertEqual(path.parent,
                         self.path(self.os.path.join('d:', 'python scripts')))
        self.assertEqual(path.parents[0],
                         self.path(self.os.path.join('d:', 'python scripts')))
        self.assertEqual(path.parents[1], self.path('d:'))

    @unittest.skipIf(not is_windows, 'Windows-specifc behavior')
    def test_is_absolute(self):
        self.assertTrue(self.path('c:/a/b').is_absolute())
        self.assertFalse(self.path('/a/b').is_absolute())
        self.assertFalse(self.path('c:').is_absolute())
        self.assertTrue(self.path('//some/share').is_absolute())


class RealPathlibInitializationWithDriveTest(
    FakePathlibInitializationWithDriveTest):
    def use_real_fs(self):
        return True


class FakePathlibPurePathTest(RealPathlibTestCase):
    """Tests functionality present in PurePath class."""

    @unittest.skipIf(is_windows, 'POSIX specific behavior')
    def test_is_reserved_posix(self):
        self.assertFalse(self.path('/dev').is_reserved())
        self.assertFalse(self.path('/').is_reserved())
        self.assertFalse(self.path('COM1').is_reserved())
        self.assertFalse(self.path('nul.txt').is_reserved())

    @unittest.skipIf(not is_windows, 'Windows specific behavior')
    def test_is_reserved_windows(self):
        self.check_windows_only()
        self.assertFalse(self.path('/dev').is_reserved())
        self.assertFalse(self.path('/').is_reserved())
        self.assertTrue(self.path('COM1').is_reserved())
        self.assertTrue(self.path('nul.txt').is_reserved())

    def test_joinpath(self):
        self.assertEqual(self.path('/etc').joinpath('passwd'),
                         self.path('/etc/passwd'))
        self.assertEqual(self.path('/etc').joinpath(self.path('passwd')),
                         self.path('/etc/passwd'))
        self.assertEqual(self.path('/foo').joinpath('bar', 'baz'),
                         self.path('/foo/bar/baz'))

    def test_joinpath_drive(self):
        self.check_windows_only()
        self.assertEqual(self.path('c:').joinpath('/Program Files'),
                         self.path('c:/Program Files'))

    def test_match(self):
        self.assertTrue(self.path('a/b.py').match('*.py'))
        self.assertTrue(self.path('/a/b/c.py').match('b/*.py'))
        self.assertFalse(self.path('/a/b/c.py').match('a/*.py'))
        self.assertTrue(self.path('/a.py').match('/*.py'))
        self.assertFalse(self.path('a/b.py').match('/*.py'))

    def test_relative_to(self):
        self.assertEqual(self.path('/etc/passwd').relative_to('/'),
                         self.path('etc/passwd'))
        self.assertEqual(self.path('/etc/passwd').relative_to('/'),
                         self.path('etc/passwd'))
        self.assertRaises(ValueError, self.path('passwd').relative_to, '/usr')

    def test_with_name(self):
        self.check_windows_only()
        self.assertEqual(
            self.path('c:/Downloads/pathlib.tar.gz').with_name('setup.py'),
            self.path('c:/Downloads/setup.py'))
        self.assertRaises(ValueError, self.path('c:/').with_name, 'setup.py')

    def test_with_suffix(self):
        self.assertEqual(
            self.path('c:/Downloads/pathlib.tar.gz').with_suffix('.bz2'),
            self.path('c:/Downloads/pathlib.tar.bz2'))
        self.assertEqual(self.path('README').with_suffix('.txt'),
                         self.path('README.txt'))


class RealPathlibPurePathTest(FakePathlibPurePathTest):
    def use_real_fs(self):
        return True


class FakePathlibFileObjectPropertyTest(RealPathlibTestCase):
    def setUp(self):
        super(FakePathlibFileObjectPropertyTest, self).setUp()
        self.file_path = self.make_path('home', 'jane', 'test.py')
        self.create_file(self.file_path, contents=b'a' * 100)
        self.create_dir(self.make_path('home', 'john'))
        try:
            self.skip_if_symlink_not_supported()
        except unittest.SkipTest:
            return
        self.create_symlink(self.make_path('john'), self.make_path('home', 'john'))
        self.file_link_path = self.make_path('test.py')
        self.create_symlink(self.file_link_path, self.file_path)
        self.create_symlink(self.make_path('broken_dir_link'),
                            self.make_path('home', 'none'))
        self.create_symlink(self.make_path('broken_file_link'),
                            self.make_path('home', 'none', 'test.py'))

    def test_exists(self):
        self.skip_if_symlink_not_supported()
        self.assertTrue(self.path(self.file_path).exists())
        self.assertTrue(self.path(
            self.make_path('home', 'jane')).exists())
        self.assertFalse(self.path(
            self.make_path('home', 'jane', 'test')).exists())
        self.assertTrue(self.path(
            self.make_path('john')).exists())
        self.assertTrue(self.path(
            self.file_link_path).exists())
        self.assertFalse(self.path(
            self.make_path('broken_dir_link')).exists())
        self.assertFalse(self.path(
            self.make_path('broken_file_link')).exists())

    def test_is_dir(self):
        self.skip_if_symlink_not_supported()
        self.assertFalse(self.path(
            self.file_path).is_dir())
        self.assertTrue(self.path(
            self.make_path('home/jane')).is_dir())
        self.assertTrue(self.path(
            self.make_path('john')).is_dir())
        self.assertFalse(self.path(
            self.file_link_path).is_dir())
        self.assertFalse(self.path(
            self.make_path('broken_dir_link')).is_dir())
        self.assertFalse(self.path(
            self.make_path('broken_file_link')).is_dir())

    def test_is_file(self):
        self.skip_if_symlink_not_supported()
        self.assertTrue(self.path(
            self.make_path('home/jane/test.py')).is_file())
        self.assertFalse(self.path(
            self.make_path('home/jane')).is_file())
        self.assertFalse(self.path(
            self.make_path('john')).is_file())
        self.assertTrue(self.path(
            self.file_link_path).is_file())
        self.assertFalse(self.path(
            self.make_path('broken_dir_link')).is_file())
        self.assertFalse(self.path(
            self.make_path('broken_file_link')).is_file())

    def test_is_symlink(self):
        self.skip_if_symlink_not_supported()
        self.assertFalse(self.path(
            self.make_path('home/jane/test.py')).is_symlink())
        self.assertFalse(self.path(
            self.make_path('home/jane')).is_symlink())
        self.assertTrue(self.path(
            self.make_path('john')).is_symlink())
        self.assertTrue(self.path(
            self.file_link_path).is_symlink())
        self.assertTrue(self.path(
            self.make_path('broken_dir_link')).is_symlink())
        self.assertTrue(self.path(
            self.make_path('broken_file_link')).is_symlink())

    def test_stat(self):
        self.skip_if_symlink_not_supported()
        file_stat = self.os.stat(self.file_path)

        stat_result = self.path(self.file_link_path).stat()
        self.assertFalse(stat_result.st_mode & stat.S_IFDIR)
        self.assertTrue(stat_result.st_mode & stat.S_IFREG)
        self.assertEqual(stat_result.st_ino, file_stat.st_ino)
        self.assertEqual(stat_result.st_size, 100)
        self.assertEqual(stat_result.st_mtime, file_stat.st_mtime)
        self.assertEqual(stat_result[stat.ST_MTIME], int(file_stat.st_mtime))

    def check_lstat(self, expected_size):
        self.skip_if_symlink_not_supported()
        link_stat = self.os.lstat(self.file_link_path)

        stat_result = self.path(self.file_link_path).lstat()
        self.assertTrue(stat_result.st_mode & stat.S_IFREG)
        self.assertTrue(stat_result.st_mode & stat.S_IFLNK)
        self.assertEqual(stat_result.st_ino, link_stat.st_ino)
        self.assertEqual(stat_result.st_size, expected_size)
        self.assertEqual(stat_result.st_mtime, link_stat.st_mtime)

    @unittest.skipIf(is_windows, 'POSIX specific behavior')
    def test_lstat_posix(self):
        self.check_lstat(len(self.file_path))

    @unittest.skipIf(not is_windows, 'Windows specific behavior')
    def test_lstat_windows(self):
        self.skip_if_symlink_not_supported()
        self.check_lstat(0)

    def test_chmod(self):
        self.check_linux_only()
        self.path(self.file_link_path).chmod(0o444)
        file_stat = self.os.stat(self.file_path)
        self.assertEqual(file_stat.st_mode, stat.S_IFREG | 0o444)
        link_stat = self.os.lstat(self.file_link_path)
        # we get stat.S_IFLNK | 0o755 under MacOs
        self.assertEqual(link_stat.st_mode, stat.S_IFLNK | 0o777)

    @unittest.skipIf(sys.platform == 'darwin',
                     'Different behavior under MacOs')
    def test_lchmod(self):
        self.skip_if_symlink_not_supported()
        file_stat = self.os.stat(self.file_path)
        link_stat = self.os.lstat(self.file_link_path)
        if not hasattr(os, "lchmod"):
            self.assertRaises(NotImplementedError,
                              self.path(self.file_link_path).lchmod, 0o444)
        else:
            self.path(self.file_link_path).lchmod(0o444)
            self.assertEqual(file_stat.st_mode, stat.S_IFREG | 0o666)
            # we get stat.S_IFLNK | 0o755 under MacOs
            self.assertEqual(link_stat.st_mode, stat.S_IFLNK | 0o444)

    def test_resolve(self):
        self.create_dir(self.make_path('antoine', 'docs'))
        self.create_file(self.make_path('antoine', 'setup.py'))
        self.os.chdir(self.make_path('antoine'))
        # use real path to handle symlink /var to /private/var in MacOs
        self.assertEqual(self.path().resolve(),
                         self.path(
                             self.os.path.realpath(self.make_path('antoine'))))
        self.assertEqual(
            self.path(self.os.path.join('docs', '..', 'setup.py')).resolve(),
            self.path(
                self.os.path.realpath(self.make_path('antoine', 'setup.py'))))

    @unittest.skipIf(sys.version_info >= (3, 6),
                     'Changed behavior in Python 3.6')
    def test_resolve_nonexisting_file(self):
        path = self.path('/foo/bar')
        self.assertRaises(FileNotFoundError, path.resolve)

    @unittest.skipIf(sys.version_info >= (3, 6),
                     'Changed behavior in Python 3.6')
    def test_resolve_file_as_parent_windows(self):
        self.check_windows_only()
        self.create_file(self.make_path('a_file'))
        path = self.path(self.make_path('a_file', 'this can not exist'))
        self.assertRaises(FileNotFoundError, path.resolve)

    @unittest.skipIf(sys.version_info >= (3, 6),
                     'Changed behavior in Python 3.6')
    def test_resolve_file_as_parent_posix(self):
        self.check_posix_only()
        self.create_file(self.make_path('a_file'))
        path = self.path(self.make_path('', 'a_file', 'this can not exist'))
        self.assertRaises(NotADirectoryError, path.resolve)

    @unittest.skipIf(sys.version_info < (3, 6),
                     'Changed behavior in Python 3.6')
    def test_resolve_nonexisting_file(self):
        path = self.path(
            self.make_path('/path', 'to', 'file', 'this can not exist'))
        self.assertTrue(path, path.resolve())
        self.assertRaises(FileNotFoundError, path.resolve, strict=True)

    def test_cwd(self):
        dir_path = self.make_path('jane')
        self.create_dir(dir_path)
        self.os.chdir(dir_path)
        self.assertEqual(self.path.cwd(),
                         self.path(self.os.path.realpath(dir_path)))

    @unittest.skipIf(sys.version_info < (3, 5), 'New in version 3.5')
    def test_expanduser(self):
        if is_windows:
            self.assertEqual(self.path('~').expanduser(),
                             self.path(
                                 os.environ['USERPROFILE'].replace('\\', '/')))
        else:
            self.assertEqual(self.path('~').expanduser(),
                             self.path(os.environ['HOME']))

    @unittest.skipIf(sys.version_info < (3, 5), 'New in version 3.5')
    def test_home(self):
        if is_windows:
            self.assertEqual(self.path.home(),
                             self.path(
                                 os.environ['USERPROFILE'].replace('\\', '/')))
        else:
            self.assertEqual(self.path.home(),
                             self.path(os.environ['HOME']))


class RealPathlibFileObjectPropertyTest(FakePathlibFileObjectPropertyTest):
    def use_real_fs(self):
        return True


class FakePathlibPathFileOperationTest(RealPathlibTestCase):
    """Tests methods related to file and directory handling."""

    def test_exists(self):
        self.skip_if_symlink_not_supported()
        self.create_file(self.make_path('home', 'jane', 'test.py'))
        self.create_dir(self.make_path('home', 'john'))
        self.create_symlink(self.make_path('john'), self.make_path('home', 'john'))
        self.create_symlink(self.make_path('none'), self.make_path('home', 'none'))

        self.assertTrue(
            self.path(self.make_path('home', 'jane', 'test.py')).exists())
        self.assertTrue(self.path(self.make_path('home', 'jane')).exists())
        self.assertTrue(self.path(self.make_path('john')).exists())
        self.assertFalse(self.path(self.make_path('none')).exists())
        self.assertFalse(
            self.path(self.make_path('home', 'jane', 'test')).exists())

    def test_open(self):
        self.create_dir(self.make_path('foo'))
        self.assertRaises(OSError,
                          self.path(self.make_path('foo', 'bar.txt')).open)
        self.path(self.make_path('foo', 'bar.txt')).open('w').close()
        self.assertTrue(self.os.path.exists(self.make_path('foo', 'bar.txt')))

    @unittest.skipIf(sys.version_info < (3, 5), 'New in version 3.5')
    def test_read_text(self):
        self.create_file(self.make_path('text_file'),
                         contents='ерунда', encoding='cyrillic')
        file_path = self.path(self.make_path('text_file'))
        self.assertEqual(file_path.read_text(encoding='cyrillic'), 'ерунда')

    @unittest.skipIf(sys.version_info < (3, 5), 'New in version 3.5')
    def test_write_text(self):
        path_name = self.make_path('text_file')
        file_path = self.path(path_name)
        file_path.write_text('ανοησίες', encoding='greek')
        self.assertTrue(self.os.path.exists(path_name))
        self.check_contents(path_name, 'ανοησίες'.encode('greek'))

    @unittest.skipIf(sys.version_info < (3, 5), 'New in version 3.5')
    def test_read_bytes(self):
        path_name = self.make_path('binary_file')
        self.create_file(path_name, contents=b'Binary file contents')
        file_path = self.path(path_name)
        self.assertEqual(file_path.read_bytes(), b'Binary file contents')

    @unittest.skipIf(sys.version_info < (3, 5), 'New in version 3.5')
    def test_write_bytes(self):
        path_name = self.make_path('binary_file')
        file_path = self.path(path_name)
        file_path.write_bytes(b'Binary file contents')
        self.assertTrue(self.os.path.exists(path_name))
        self.check_contents(path_name, b'Binary file contents')

    def test_rename(self):
        file_name = self.make_path('foo', 'bar.txt')
        self.create_file(file_name, contents='test')
        new_file_name = self.make_path('foo', 'baz.txt')
        self.path(file_name).rename(new_file_name)
        self.assertFalse(self.os.path.exists(file_name))
        self.check_contents(new_file_name, 'test')

    def test_replace(self):
        self.create_file(self.make_path('foo', 'bar.txt'), contents='test')
        self.create_file(self.make_path('bar', 'old.txt'), contents='replaced')
        self.path(self.make_path('bar', 'old.txt')).replace(
            self.make_path('foo', 'bar.txt'))
        self.assertFalse(self.os.path.exists(self.make_path('bar', 'old.txt')))
        self.check_contents(self.make_path('foo', 'bar.txt'), 'replaced')

    def test_unlink(self):
        file_path = self.make_path('foo', 'bar.txt')
        self.create_file(file_path, contents='test')
        self.assertTrue(self.os.path.exists(file_path))
        self.path(file_path).unlink()
        self.assertFalse(self.os.path.exists(file_path))

    def test_touch_non_existing(self):
        self.create_dir(self.make_path('foo'))
        file_name = self.make_path('foo', 'bar.txt')
        self.path(file_name).touch(mode=0o444)
        self.check_contents(file_name, '')
        self.assertTrue(self.os.stat(file_name).st_mode, stat.S_IFREG | 0o444)

    def test_touch_existing(self):
        file_name = self.make_path('foo', 'bar.txt')
        self.create_file(file_name, contents='test')
        file_path = self.path(file_name)
        self.assertRaises(FileExistsError, file_path.touch, exist_ok=False)
        file_path.touch()
        self.check_contents(file_name, 'test')

    @unittest.skipIf(sys.version_info < (3, 5), 'New in version 3.5')
    def test_samefile(self):
        file_name = self.make_path('foo', 'bar.txt')
        self.create_file(file_name)
        file_name2 = self.make_path('foo', 'baz.txt')
        self.create_file(file_name2)
        self.assertRaises(OSError,
                          self.path(self.make_path('foo', 'other')).samefile,
                          self.make_path('foo', 'other.txt'))
        path = self.path(file_name)
        other_name = self.make_path('foo', 'other.txt')
        self.assertRaises(OSError, path.samefile, other_name)
        self.assertRaises(OSError, path.samefile, self.path(other_name))
        self.assertFalse(path.samefile(file_name2))
        self.assertFalse(path.samefile(self.path(file_name2)))
        self.assertTrue(
            path.samefile(self.make_path('foo', '..', 'foo', 'bar.txt')))
        self.assertTrue(path.samefile(
            self.path(self.make_path('foo', '..', 'foo', 'bar.txt'))))

    def test_symlink_to(self):
        self.skip_if_symlink_not_supported()
        file_name = self.make_path('foo', 'bar.txt')
        self.create_file(file_name)
        link_name = self.make_path('link_to_bar')
        path = self.path(link_name)
        path.symlink_to(file_name)
        self.assertTrue(self.os.path.exists(link_name))
        # file_obj = self.filesystem.ResolveObject(file_name)
        # linked_file_obj = self.filesystem.ResolveObject(link_name)
        # self.assertEqual(file_obj, linked_file_obj)
        # link__obj = self.filesystem.LResolveObject(link_name)
        self.assertTrue(path.is_symlink())

    def test_mkdir(self):
        dir_name = self.make_path('foo', 'bar')
        self.assertRaises(FileNotFoundError, self.path(dir_name).mkdir)
        self.path(dir_name).mkdir(parents=True)
        self.assertTrue(self.os.path.exists(dir_name))
        self.assertRaises(FileExistsError, self.path(dir_name).mkdir)

    @unittest.skipIf(sys.version_info < (3, 5),
                     'exist_ok argument new in Python 3.5')
    def test_mkdir_exist_ok(self):
        dir_name = self.make_path('foo', 'bar')
        self.create_dir(dir_name)
        self.path(dir_name).mkdir(exist_ok=True)
        file_name = self.os.path.join(dir_name, 'baz')
        self.create_file(file_name)
        self.assertRaises(FileExistsError, self.path(file_name).mkdir,
                          exist_ok=True)

    def test_rmdir(self):
        dir_name = self.make_path('foo', 'bar')
        self.create_dir(dir_name)
        self.path(dir_name).rmdir()
        self.assertFalse(self.os.path.exists(dir_name))
        self.assertTrue(self.os.path.exists(self.make_path('foo')))
        self.create_file(self.make_path('foo', 'baz'))
        self.assertRaises(OSError, self.path(self.make_path('foo')).rmdir)
        self.assertTrue(self.os.path.exists(self.make_path('foo')))

    def test_iterdir(self):
        self.create_file(self.make_path('foo', 'bar', 'file1'))
        self.create_file(self.make_path('foo', 'bar', 'file2'))
        self.create_file(self.make_path('foo', 'bar', 'file3'))
        path = self.path(self.make_path('foo', 'bar'))
        contents = [entry for entry in path.iterdir()]
        self.assertEqual(3, len(contents))
        self.assertIn(self.path(self.make_path('foo', 'bar', 'file2')),
                      contents)

    def test_glob(self):
        self.create_file(self.make_path('foo', 'setup.py'))
        self.create_file(self.make_path('foo', 'all_tests.py'))
        self.create_file(self.make_path('foo', 'README.md'))
        self.create_file(self.make_path('foo', 'setup.pyc'))
        path = self.path(self.make_path('foo'))
        self.assertEqual(sorted(path.glob('*.py')),
                         [self.path(self.make_path('foo', 'all_tests.py')),
                          self.path(self.make_path('foo', 'setup.py'))])

    def test_glob_case_windows(self):
        self.check_windows_only()
        self.create_file(self.make_path('foo', 'setup.py'))
        self.create_file(self.make_path('foo', 'all_tests.PY'))
        self.create_file(self.make_path('foo', 'README.md'))
        self.create_file(self.make_path('foo', 'example.Py'))
        path = self.path(self.make_path('foo'))
        self.assertEqual(sorted(path.glob('*.py')),
                         [self.path(self.make_path('foo', 'all_tests.PY')),
                          self.path(self.make_path('foo', 'example.Py')),
                          self.path(self.make_path('foo', 'setup.py'))])

    def test_glob_case_posix(self):
        self.check_posix_only()
        self.create_file(self.make_path('foo', 'setup.py'))
        self.create_file(self.make_path('foo', 'all_tests.PY'))
        self.create_file(self.make_path('foo', 'README.md'))
        self.create_file(self.make_path('foo', 'example.Py'))
        path = self.path(self.make_path('foo'))
        self.assertEqual(sorted(path.glob('*.py')),
                         [self.path(self.make_path('foo', 'setup.py'))])


class RealPathlibPathFileOperationTest(FakePathlibPathFileOperationTest):
    def use_real_fs(self):
        return True


@unittest.skipIf(sys.version_info < (3, 6),
                 'path-like objects new in Python 3.6')
class FakePathlibUsageInOsFunctionsTest(RealPathlibTestCase):
    """Test that many os / os.path functions accept a path-like object since Python 3.6.
    The functionality of these functions is testd elsewhere, we just check that they
    accept a fake path object as an argument.
    """

    def test_join(self):
        dir1 = 'foo'
        dir2 = 'bar'
        dir = self.os.path.join(dir1, dir2)
        self.assertEqual(dir, self.os.path.join(self.path(dir1), dir2))
        self.assertEqual(dir, self.os.path.join(dir1, self.path(dir2)))
        self.assertEqual(dir,
                         self.os.path.join(self.path(dir1), self.path(dir2)))

    def test_normcase(self):
        dir1 = self.make_path('Foo', 'Bar', 'Baz')
        self.assertEqual(self.os.path.normcase(dir1),
                         self.os.path.normcase(self.path(dir1)))

    def test_normpath(self):
        dir1 = self.make_path('foo', 'bar', '..', 'baz')
        self.assertEqual(self.os.path.normpath(dir1),
                         self.os.path.normpath(self.path(dir1)))

    def test_realpath(self):
        dir1 = self.make_path('foo', 'bar', '..', 'baz')
        self.assertEqual(self.os.path.realpath(dir1),
                         self.os.path.realpath(self.path(dir1)))

    def test_relpath(self):
        path_foo = self.make_path('path', 'to', 'foo')
        path_bar = self.make_path('path', 'to', 'bar')
        rel_path = self.os.path.relpath(path_foo, path_bar)
        self.assertEqual(rel_path,
                         self.os.path.relpath(self.path(path_foo), path_bar))
        self.assertEqual(rel_path,
                         self.os.path.relpath(path_foo, self.path(path_bar)))
        self.assertEqual(rel_path, self.os.path.relpath(self.path(path_foo),
                                                        self.path(path_bar)))

    def test_split(self):
        dir1 = self.make_path('Foo', 'Bar', 'Baz')
        self.assertEqual(self.os.path.split(dir1),
                         self.os.path.split(self.path(dir1)))

    def test_splitdrive(self):
        dir1 = self.make_path('C:', 'Foo', 'Bar', 'Baz')
        self.assertEqual(self.os.path.splitdrive(dir1),
                         self.os.path.splitdrive(self.path(dir1)))

    def test_abspath(self):
        dir1 = self.make_path('foo', 'bar', '..', 'baz')
        self.assertEqual(self.os.path.abspath(dir1),
                         self.os.path.abspath(self.path(dir1)))

    def test_exists(self):
        dir1 = self.make_path('foo', 'bar', '..', 'baz')
        self.assertEqual(self.os.path.exists(dir1),
                         self.os.path.exists(self.path(dir1)))

    def test_lexists(self):
        dir1 = self.make_path('foo', 'bar', '..', 'baz')
        self.assertEqual(self.os.path.lexists(dir1),
                         self.os.path.lexists(self.path(dir1)))

    def test_expanduser(self):
        dir1 = self.os.path.join('~', 'foo')
        self.assertEqual(self.os.path.expanduser(dir1),
                         self.os.path.expanduser(self.path(dir1)))

    def test_getmtime(self):
        self.skip_real_fs()
        dir1 = self.make_path('foo', 'bar1.txt')
        path_obj = self.filesystem.create_file(dir1)
        path_obj._st_mtime = 24
        self.assertEqual(self.os.path.getmtime(dir1),
                         self.os.path.getmtime(self.path(dir1)))

    def test_getctime(self):
        self.skip_real_fs()
        dir1 = self.make_path('foo', 'bar1.txt')
        path_obj = self.filesystem.create_file(dir1)
        path_obj.st_ctime = 42
        self.assertEqual(self.os.path.getctime(dir1),
                         self.os.path.getctime(self.path(dir1)))

    def test_getatime(self):
        self.skip_real_fs()
        dir1 = self.make_path('foo', 'bar1.txt')
        path_obj = self.filesystem.create_file(dir1)
        path_obj.SetATime(11)
        self.assertEqual(self.os.path.getatime(dir1),
                         self.os.path.getatime(self.path(dir1)))

    def test_getsize(self):
        path = self.make_path('foo', 'bar', 'baz')
        self.create_file(path, contents='1234567')
        self.assertEqual(self.os.path.getsize(path),
                         self.os.path.getsize(self.path(path)))

    def test_isabs(self):
        path = self.make_path('foo', 'bar', '..', 'baz')
        self.assertEqual(self.os.path.isabs(path),
                         self.os.path.isabs(self.path(path)))

    def test_isfile(self):
        path = self.make_path('foo', 'bar', 'baz')
        self.create_file(path)
        self.assertEqual(self.os.path.isfile(path),
                         self.os.path.isfile(self.path(path)))

    def test_islink(self):
        path = self.make_path('foo', 'bar', 'baz')
        self.create_file(path)
        self.assertEqual(self.os.path.islink(path),
                         self.os.path.islink(self.path(path)))

    def test_isdir(self):
        path = self.make_path('foo', 'bar', 'baz')
        self.create_file(path)
        self.assertEqual(self.os.path.isdir(path),
                         self.os.path.isdir(self.path(path)))

    def test_ismount(self):
        path = self.os.path.sep
        self.assertEqual(self.os.path.ismount(path),
                         self.os.path.ismount(self.path(path)))

    def test_access(self):
        path = self.make_path('foo', 'bar', 'baz')
        self.create_file(path, contents='1234567')
        self.assertEqual(self.os.access(path, os.R_OK),
                         self.os.access(self.path(path), os.R_OK))

    def test_chdir(self):
        path = self.make_path('foo', 'bar', 'baz')
        self.create_dir(path)
        self.os.chdir(self.path(path))
        # use real path to handle symlink /var to /private/var in MacOs
        self.assertEqual(self.os.path.realpath(path), self.os.getcwd())

    def test_chmod(self):
        path = self.make_path('some_file')
        self.create_file(path)
        self.os.chmod(self.path(path), 0o444)
        self.assertEqual(stat.S_IMODE(0o444),
                         stat.S_IMODE(self.os.stat(path).st_mode))
        self.os.chmod(self.path(path), 0o666)

    def test_link(self):
        self.skip_if_symlink_not_supported()
        file1_path = self.make_path('test_file1')
        file2_path = self.make_path('test_file2')
        self.create_file(file1_path)
        self.os.link(self.path(file1_path), file2_path)
        self.assertTrue(self.os.path.exists(file2_path))
        self.os.unlink(file2_path)
        self.os.link(self.path(file1_path), self.path(file2_path))
        self.assertTrue(self.os.path.exists(file2_path))
        self.os.unlink(file2_path)
        self.os.link(file1_path, self.path(file2_path))
        self.assertTrue(self.os.path.exists(file2_path))

    def test_listdir(self):
        path = self.make_path('foo', 'bar')
        self.create_dir(path)
        self.create_file(path + 'baz.txt')
        self.assertEqual(self.os.listdir(path),
                         self.os.listdir(self.path(path)))

    def test_mkdir(self):
        path = self.make_path('foo')
        self.os.mkdir(self.path(path))
        self.assertTrue(self.os.path.exists(path))

    def test_makedirs(self):
        path = self.make_path('foo', 'bar')
        self.os.makedirs(self.path(path))
        self.assertTrue(self.os.path.exists(path))

    @unittest.skipIf(is_windows, 'os.readlink seems not to support '
                                 'path-like objects under Windows')
    def test_readlink(self):
        link_path = self.make_path('foo', 'bar', 'baz')
        target = self.make_path('tarJAY')
        self.create_symlink(link_path, target)
        self.assertEqual(self.os.readlink(self.path(link_path)), target)

    def test_remove(self):
        path = self.make_path('test.txt')
        self.create_file(path)
        self.os.remove(self.path(path))
        self.assertFalse(self.os.path.exists(path))

    def test_rename(self):
        path1 = self.make_path('test1.txt')
        path2 = self.make_path('test2.txt')
        self.create_file(path1)
        self.os.rename(self.path(path1), path2)
        self.assertTrue(self.os.path.exists(path2))
        self.os.rename(self.path(path2), self.path(path1))
        self.assertTrue(self.os.path.exists(path1))

    def test_replace(self):
        path1 = self.make_path('test1.txt')
        path2 = self.make_path('test2.txt')
        self.create_file(path1)
        self.os.replace(self.path(path1), path2)
        self.assertTrue(self.os.path.exists(path2))
        self.os.replace(self.path(path2), self.path(path1))
        self.assertTrue(self.os.path.exists(path1))

    def test_rmdir(self):
        path = self.make_path('foo', 'bar')
        self.create_dir(path)
        self.os.rmdir(self.path(path))
        self.assertFalse(self.os.path.exists(path))

    def test_scandir(self):
        directory = self.make_path('xyzzy', 'plugh')
        self.create_dir(directory)
        self.create_file(self.os.path.join(directory, 'test.txt'))
        dir_entries = [entry for entry in
                       self.os.scandir(self.path(directory))]
        self.assertEqual(1, len(dir_entries))

    def test_symlink(self):
        self.skip_if_symlink_not_supported()
        file_path = self.make_path('test_file1')
        link_path = self.make_path('link')
        self.create_file(file_path)
        self.os.symlink(self.path(file_path), link_path)
        self.assertTrue(self.os.path.exists(link_path))
        self.os.remove(link_path)
        self.os.symlink(self.path(file_path), self.path(link_path))
        self.assertTrue(self.os.path.exists(link_path))

    def test_stat(self):
        path = self.make_path('foo', 'bar', 'baz')
        self.create_file(path, contents='1234567')
        self.assertEqual(self.os.stat(path), self.os.stat(self.path(path)))

    def test_utime(self):
        path = self.make_path('some_file')
        self.create_file(path, contents='test')
        self.os.utime(self.path(path), (1, 2))
        st = self.os.stat(path)
        self.assertEqual(1, st.st_atime)
        self.assertEqual(2, st.st_mtime)


class RealPathlibUsageInOsFunctionsTest(FakePathlibUsageInOsFunctionsTest):
    def use_real_fs(self):
        return True


if __name__ == '__main__':
    unittest.main()
