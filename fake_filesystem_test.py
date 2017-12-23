#! /usr/bin/env python
# -*- coding: utf-8 -*-
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

"""Unittest for fake_filesystem module."""

import errno
import io
import locale
import os
import platform
import shutil
import stat
import sys
import tempfile
import time
import unittest

from pyfakefs import fake_filesystem
from pyfakefs.fake_filesystem import FakeFileOpen
from pyfakefs.fake_filesystem_unittest import has_scandir


class _DummyTime(object):
    """Mock replacement for time.time. Increases returned time on access."""

    def __init__(self, curr_time, increment):
        self.curr_time = curr_time
        self.increment = increment
        self.started = False

    def start(self):
        self.started = True

    def __call__(self, *args, **kwargs):
        if self.started:
            self.curr_time += self.increment
        return self.curr_time


class TestCase(unittest.TestCase):
    is_windows = sys.platform == 'win32'
    is_cygwin = sys.platform == 'cygwin'
    is_macos = sys.platform == 'darwin'
    is_python2 = sys.version_info[0] < 3
    symlinks_can_be_tested = None

    def assert_mode_equal(self, expected, actual):
        return self.assertEqual(stat.S_IMODE(expected), stat.S_IMODE(actual))

    def assert_raises_io_error(self, subtype, expression, *args, **kwargs):
        try:
            expression(*args, **kwargs)
            self.fail('No exception was raised, IOError expected')
        except IOError as exc:
            self.assertEqual(exc.errno, subtype)

    def assert_raises_os_error(self, subtype, expression, *args, **kwargs):
        try:
            expression(*args, **kwargs)
            self.fail('No exception was raised, OSError expected')
        except OSError as exc:
            self.assertEqual(exc.errno, subtype)


class RealFsTestMixin(object):
    def __init__(self):
        self.filesystem = None
        self.open = open
        self.os = os
        self.is_python2 = sys.version_info[0] == 2
        if self.use_real_fs():
            self.base_path = tempfile.mkdtemp()
        else:
            self.base_path = self.path_separator() + 'basepath'

    @property
    def is_windows_fs(self):
        return TestCase.is_windows

    @property
    def is_macos(self):
        return TestCase.is_macos

    @property
    def is_pypy(self):
        return platform.python_implementation() == 'PyPy'

    def use_real_fs(self):
        return False

    def path_separator(self):
        return '/'

    def check_windows_only(self):
        if self.use_real_fs():
            if not TestCase.is_windows:
                raise unittest.SkipTest(
                    'Testing Windows specific functionality')
        else:
            self.filesystem.is_windows_fs = True
            self.filesystem.is_macos = False

    def check_linux_only(self):
        if self.use_real_fs():
            if TestCase.is_macos or TestCase.is_windows:
                raise unittest.SkipTest(
                    'Testing Linux specific functionality')
        else:
            self.filesystem.is_windows_fs = False
            self.filesystem.is_macos = False

    def check_macos_only(self):
        if self.use_real_fs():
            if not TestCase.is_macos:
                raise unittest.SkipTest(
                    'Testing MacOS specific functionality')
        else:
            self.filesystem.is_windows_fs = False
            self.filesystem.is_macos = True

    def check_linux_and_windows(self):
        if self.use_real_fs():
            if TestCase.is_macos:
                raise unittest.SkipTest(
                    'Testing non-MacOs functionality')
        else:
            self.filesystem.is_macos = False

    def check_case_insensitive_fs(self):
        if self.use_real_fs():
            if not TestCase.is_macos and not TestCase.is_windows:
                raise unittest.SkipTest(
                    'Testing case insensitive specific functionality')
        else:
            self.filesystem.is_case_sensitive = False

    def check_case_sensitive_fs(self):
        if self.use_real_fs():
            if TestCase.is_macos or TestCase.is_windows:
                raise unittest.SkipTest(
                    'Testing case sensitive specific functionality')
        else:
            self.filesystem.is_case_sensitive = True

    def check_posix_only(self):
        if self.use_real_fs():
            if TestCase.is_windows:
                raise unittest.SkipTest(
                    'Testing Posix specific functionality')
        else:
            self.filesystem.is_windows_fs = False

    def skip_real_fs(self):
        if self.use_real_fs():
            raise unittest.SkipTest('Only tests fake FS')

    def skip_real_fs_failure(self, skip_windows=True, skip_posix=True,
                             skip_macos=True, skip_linux=True,
                             skip_python2=True, skip_python3=True):
        if True:
            if (self.use_real_fs() and
                    (TestCase.is_windows and skip_windows or
                                 not TestCase.is_windows
                             and skip_macos and skip_linux or
                             TestCase.is_macos and skip_macos or
                                 not TestCase.is_windows and
                                 not TestCase.is_macos and skip_linux or
                             not TestCase.is_windows and skip_posix) and
                    (TestCase.is_python2 and skip_python2 or
                             not TestCase.is_python2 and skip_python3)):
                raise unittest.SkipTest(
                    'Skipping because FakeFS does not match real FS')

    def symlink_can_be_tested(self):
        if not TestCase.is_windows or not self.use_real_fs():
            return True
        if TestCase.symlinks_can_be_tested is None:
            link_path = self.make_path('link')
            try:
                self.os.symlink(self.base_path, link_path)
                TestCase.symlinks_can_be_tested = True
                self.os.remove(link_path)
            except OSError:
                TestCase.symlinks_can_be_tested = False
        return TestCase.symlinks_can_be_tested

    def skip_if_symlink_not_supported(self):
        if (self.use_real_fs() and TestCase.is_windows or
                not self.use_real_fs() and self.filesystem.is_windows_fs):
            if sys.version_info < (3, 3):
                raise unittest.SkipTest(
                    'Symlinks are not supported under Windows '
                    'before Python 3.3')
        if not self.symlink_can_be_tested():
            raise unittest.SkipTest(
                'Symlinks under Windows need admin privileges')

    def make_path(self, *args):
        if not self.is_python2 and isinstance(args[0], bytes):
            base_path = self.base_path.encode()
        else:
            base_path = self.base_path

        if isinstance(args[0], (list, tuple)):
            path = base_path
            for arg in args[0]:
                path = self.os.path.join(path, arg)
            return path
        return self.os.path.join(base_path, *args)

    def create_dir(self, dir_path):
        existing_path = dir_path
        components = []
        while existing_path and not self.os.path.exists(existing_path):
            existing_path, component = self.os.path.split(existing_path)
            components.insert(0, component)
        for component in components:
            existing_path = self.os.path.join(existing_path, component)
            self.os.mkdir(existing_path)
            self.os.chmod(existing_path, 0o777)

    def create_file(self, file_path, contents=None, encoding=None):
        self.create_dir(self.os.path.dirname(file_path))
        mode = ('wb' if not self.is_python2 and isinstance(contents, bytes)
                else 'w')

        if encoding is not None:
            open_fct = lambda: self.open(file_path, mode, encoding=encoding)
        else:
            open_fct = lambda: self.open(file_path, mode)
        with open_fct() as f:
            if contents is not None:
                f.write(contents)
        self.os.chmod(file_path, 0o666)

    def create_symlink(self, link_path, target_path):
        self.create_dir(self.os.path.dirname(link_path))
        self.os.symlink(target_path, link_path)

    def check_contents(self, file_path, contents):
        mode = ('rb' if not self.is_python2 and isinstance(contents, bytes)
                else 'r')
        with self.open(file_path, mode) as f:
            self.assertEqual(contents, f.read())

    def not_dir_error(self):
        error = errno.ENOTDIR
        if self.is_windows_fs and self.is_python2:
            error = errno.EINVAL
        return error


class RealFsTestCase(TestCase, RealFsTestMixin):
    def __init__(self, methodName='runTest'):
        TestCase.__init__(self, methodName)
        RealFsTestMixin.__init__(self)

    def setUp(self):
        if not self.use_real_fs():
            self.filesystem = fake_filesystem.FakeFilesystem(
                path_separator=self.path_separator())
            self.open = fake_filesystem.FakeFileOpen(self.filesystem)
            self.os = fake_filesystem.FakeOsModule(self.filesystem)
            self.filesystem.create_dir(self.base_path)

    @property
    def is_windows_fs(self):
        if self.use_real_fs():
            return self.is_windows
        return self.filesystem.is_windows_fs

    @property
    def is_macos(self):
        if self.use_real_fs():
            return TestCase.is_macos
        return self.filesystem.is_macos

    def tearDown(self):
        if self.use_real_fs():
            self.os.chdir(os.path.dirname(self.base_path))
            shutil.rmtree(self.base_path, ignore_errors=True)


class FakeDirectoryUnitTest(TestCase):
    def setUp(self):
        self.orig_time = time.time
        time.time = _DummyTime(10, 1)
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.fake_file = fake_filesystem.FakeFile(
            'foobar', contents='dummy_file', filesystem=self.filesystem)
        self.fake_dir = fake_filesystem.FakeDirectory(
            'somedir', filesystem=self.filesystem)

    def tearDown(self):
        time.time = self.orig_time

    def test_new_file_and_directory(self):
        self.assertTrue(stat.S_IFREG & self.fake_file.st_mode)
        self.assertTrue(stat.S_IFDIR & self.fake_dir.st_mode)
        self.assertEqual({}, self.fake_dir.contents)
        self.assertEqual(10, self.fake_file.st_ctime)

    def test_add_entry(self):
        self.fake_dir.add_entry(self.fake_file)
        self.assertEqual({'foobar': self.fake_file}, self.fake_dir.contents)

    def test_get_entry(self):
        self.fake_dir.add_entry(self.fake_file)
        self.assertEqual(self.fake_file, self.fake_dir.get_entry('foobar'))

    def test_path(self):
        self.filesystem.root.add_entry(self.fake_dir)
        self.fake_dir.add_entry(self.fake_file)
        self.assertEqual('/somedir/foobar', self.fake_file.path)

    def test_remove_entry(self):
        self.fake_dir.add_entry(self.fake_file)
        self.assertEqual(self.fake_file, self.fake_dir.get_entry('foobar'))
        self.fake_dir.remove_entry('foobar')
        self.assertRaises(KeyError, self.fake_dir.get_entry, 'foobar')

    def test_should_throw_if_set_size_is_not_integer(self):
        def set_size():
            self.fake_file.size = 0.1

        self.assert_raises_io_error(errno.ENOSPC, set_size)

    def test_should_throw_if_set_size_is_negative(self):
        def set_size():
            self.fake_file.size = -1

        self.assert_raises_io_error(errno.ENOSPC, set_size)

    def test_produce_empty_file_if_set_size_is_zero(self):
        self.fake_file.size = 0
        self.assertEqual('', self.fake_file.contents)

    def test_sets_content_empty_if_set_size_is_zero(self):
        self.fake_file.size = 0
        self.assertEqual('', self.fake_file.contents)

    def test_truncate_file_if_size_is_smaller_than_current_size(self):
        self.fake_file.size = 6
        self.assertEqual('dummy_', self.fake_file.contents)

    def test_leave_file_unchanged_if_size_is_equal_to_current_size(self):
        self.fake_file.size = 10
        self.assertEqual('dummy_file', self.fake_file.contents)

    def test_set_contents_to_dir_raises(self):
        # Regression test for #276
        self.filesystem.is_windows_fs = True
        error_check = (self.assert_raises_io_error if self.is_python2
                       else self.assert_raises_os_error)
        error_check(errno.EISDIR, self.fake_dir.set_contents, 'a')
        self.filesystem.is_windows_fs = False
        self.assert_raises_io_error(errno.EISDIR, self.fake_dir.set_contents, 'a')

    def test_pads_file_content_with_nullbytes_if_size_is_greater_than_current_size(self):
        self.fake_file.size = 13
        self.assertEqual('dummy_file\0\0\0', self.fake_file.contents)

    def test_set_m_time(self):
        self.assertEqual(10, self.fake_file.st_mtime)
        self.fake_file.st_mtime = 13
        self.assertEqual(13, self.fake_file.st_mtime)
        self.fake_file.st_mtime = 131
        self.assertEqual(131, self.fake_file.st_mtime)

    def test_file_inode(self):
        filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        fake_os = fake_filesystem.FakeOsModule(filesystem)
        file_path = 'some_file1'
        filesystem.create_file(file_path, contents='contents here1')
        self.assertLess(0, fake_os.stat(file_path)[stat.ST_INO])

        file_obj = filesystem.get_object(file_path)
        file_obj.st_ino = 43
        self.assertEqual(43, fake_os.stat(file_path)[stat.ST_INO])

    def test_directory_inode(self):
        filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        fake_os = fake_filesystem.FakeOsModule(filesystem)
        dirpath = 'testdir'
        filesystem.create_dir(dirpath)
        self.assertLess(0, fake_os.stat(dirpath)[stat.ST_INO])

        dir_obj = filesystem.get_object(dirpath)
        dir_obj.st_ino = 43
        self.assertEqual(43, fake_os.stat(dirpath)[stat.ST_INO])

    def test_ordered_dirs(self):
        filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        filesystem.create_dir('/foo')
        filesystem.create_file('/foo/2')
        filesystem.create_file('/foo/4')
        filesystem.create_file('/foo/1')
        filesystem.create_file('/foo/3')
        fake_dir = filesystem.get_object('/foo')
        self.assertEqual(['2', '4', '1', '3'], fake_dir.ordered_dirs)


class SetLargeFileSizeTest(TestCase):
    def setUp(self):
        filesystem = fake_filesystem.FakeFilesystem()
        self.fake_file = fake_filesystem.FakeFile('foobar',
                                                  filesystem=filesystem)

    def test_should_throw_if_size_is_not_integer(self):
        self.assert_raises_io_error(errno.ENOSPC,
                                    self.fake_file.set_large_file_size, 0.1)

    def test_should_throw_if_size_is_negative(self):
        self.assert_raises_io_error(errno.ENOSPC,
                                    self.fake_file.set_large_file_size, -1)

    def test_sets_content_none_if_size_is_non_negative_integer(self):
        self.fake_file.set_large_file_size(1000000000)
        self.assertEqual(None, self.fake_file.contents)
        self.assertEqual(1000000000, self.fake_file.st_size)


class NormalizePathTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.root_name = '/'

    def test_empty_path_should_get_normalized_to_root_path(self):
        self.assertEqual(self.root_name, self.filesystem.absnormpath(''))

    def test_root_path_remains_unchanged(self):
        self.assertEqual(self.root_name,
                         self.filesystem.absnormpath(self.root_name))

    def test_relative_path_forced_to_cwd(self):
        path = 'bar'
        self.filesystem.cwd = '/foo'
        self.assertEqual('/foo/bar', self.filesystem.absnormpath(path))

    def test_absolute_path_remains_unchanged(self):
        path = '/foo/bar'
        self.assertEqual(path, self.filesystem.absnormpath(path))

    def test_dotted_path_is_normalized(self):
        path = '/foo/..'
        self.assertEqual('/', self.filesystem.absnormpath(path))
        path = 'foo/../bar'
        self.assertEqual('/bar', self.filesystem.absnormpath(path))

    def test_dot_path_is_normalized(self):
        path = '.'
        self.assertEqual('/', self.filesystem.absnormpath(path))


class GetPathComponentsTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.root_name = '/'

    def test_root_path_should_return_empty_list(self):
        self.assertEqual([], self.filesystem._path_components(self.root_name))

    def test_empty_path_should_return_empty_list(self):
        self.assertEqual([], self.filesystem._path_components(''))

    def test_relative_path_with_one_component_should_return_component(self):
        self.assertEqual(['foo'], self.filesystem._path_components('foo'))

    def test_absolute_path_with_one_component_should_return_component(self):
        self.assertEqual(['foo'], self.filesystem._path_components('/foo'))

    def test_two_level_relative_path_should_return_components(self):
        self.assertEqual(['foo', 'bar'],
                         self.filesystem._path_components('foo/bar'))

    def test_two_level_absolute_path_should_return_components(self):
        self.assertEqual(['foo', 'bar'],
                         self.filesystem._path_components('/foo/bar'))


class FakeFilesystemUnitTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.root_name = '/'
        self.fake_file = fake_filesystem.FakeFile(
            'foobar', filesystem=self.filesystem)
        self.fake_child = fake_filesystem.FakeDirectory(
            'foobaz', filesystem=self.filesystem)
        self.fake_grandchild = fake_filesystem.FakeDirectory(
            'quux', filesystem=self.filesystem)

    def test_new_filesystem(self):
        self.assertEqual('/', self.filesystem.path_separator)
        self.assertTrue(stat.S_IFDIR & self.filesystem.root.st_mode)
        self.assertEqual(self.root_name, self.filesystem.root.name)
        self.assertEqual({}, self.filesystem.root.contents)

    def test_none_raises_type_error(self):
        self.assertRaises(TypeError, self.filesystem.exists, None)

    def test_empty_string_does_not_exist(self):
        self.assertFalse(self.filesystem.exists(''))

    def test_exists_root(self):
        self.assertTrue(self.filesystem.exists(self.root_name))

    def test_exists_unadded_file(self):
        self.assertFalse(self.filesystem.exists(self.fake_file.name))

    def test_not_exists_subpath_named_like_file_contents(self):
        # Regression test for #219
        file_path = "/foo/bar"
        self.filesystem.create_file(file_path, contents='baz')
        self.assertFalse(self.filesystem.exists(file_path + "/baz"))

    def test_get_root_object(self):
        self.assertEqual(self.filesystem.root,
                         self.filesystem.get_object(self.root_name))

    def test_add_object_to_root(self):
        self.filesystem.add_object(self.root_name, self.fake_file)
        self.assertEqual({'foobar': self.fake_file},
                         self.filesystem.root.contents)

    def test_exists_added_file(self):
        self.filesystem.add_object(self.root_name, self.fake_file)
        self.assertTrue(self.filesystem.exists(self.fake_file.name))

    def test_exists_relative_path_posix(self):
        self.filesystem.is_windows_fs = False
        self.filesystem.create_file('/a/b/file_one')
        self.filesystem.create_file('/a/c/file_two')
        self.assertTrue(self.filesystem.exists('a/b/../c/file_two'))
        self.assertTrue(self.filesystem.exists('/a/c/../b/file_one'))
        self.assertTrue(self.filesystem.exists('/a/c/../../a/b/file_one'))
        self.assertFalse(self.filesystem.exists('a/b/../z/d'))
        self.assertFalse(self.filesystem.exists('a/b/../z/../c/file_two'))
        self.filesystem.cwd = '/a/c'
        self.assertTrue(self.filesystem.exists('../b/file_one'))
        self.assertTrue(self.filesystem.exists('../../a/b/file_one'))
        self.assertTrue(self.filesystem.exists('../../a/b/../../a/c/file_two'))
        self.assertFalse(self.filesystem.exists('../z/file_one'))
        self.assertFalse(self.filesystem.exists('../z/../c/file_two'))

    def test_exists_relative_path_windows(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.is_macos = False
        self.filesystem.create_file('/a/b/file_one')
        self.filesystem.create_file('/a/c/file_two')
        self.assertTrue(self.filesystem.exists('a/b/../c/file_two'))
        self.assertTrue(self.filesystem.exists('/a/c/../b/file_one'))
        self.assertTrue(self.filesystem.exists('/a/c/../../a/b/file_one'))
        self.assertFalse(self.filesystem.exists('a/b/../z/d'))
        self.assertTrue(self.filesystem.exists('a/b/../z/../c/file_two'))
        self.filesystem.cwd = '/a/c'
        self.assertTrue(self.filesystem.exists('../b/file_one'))
        self.assertTrue(self.filesystem.exists('../../a/b/file_one'))
        self.assertTrue(self.filesystem.exists('../../a/b/../../a/c/file_two'))
        self.assertFalse(self.filesystem.exists('../z/file_one'))
        self.assertTrue(self.filesystem.exists('../z/../c/file_two'))

    def test_get_object_from_root(self):
        self.filesystem.add_object(self.root_name, self.fake_file)
        self.assertEqual(self.fake_file, self.filesystem.get_object('foobar'))

    def test_get_nonexistent_object_from_root_error(self):
        self.filesystem.add_object(self.root_name, self.fake_file)
        self.assertEqual(self.fake_file, self.filesystem.get_object('foobar'))
        self.assert_raises_io_error(
            errno.ENOENT, self.filesystem.get_object, 'some_bogus_filename')

    def test_remove_object_from_root(self):
        self.filesystem.add_object(self.root_name, self.fake_file)
        self.filesystem.remove_object(self.fake_file.name)
        self.assert_raises_io_error(
            errno.ENOENT, self.filesystem.get_object, self.fake_file.name)

    def test_remove_nonexisten_object_from_root_error(self):
        self.assert_raises_io_error(
            errno.ENOENT, self.filesystem.remove_object, 'some_bogus_filename')

    def test_exists_removed_file(self):
        self.filesystem.add_object(self.root_name, self.fake_file)
        self.filesystem.remove_object(self.fake_file.name)
        self.assertFalse(self.filesystem.exists(self.fake_file.name))

    def test_add_object_to_child(self):
        self.filesystem.add_object(self.root_name, self.fake_child)
        self.filesystem.add_object(self.fake_child.name, self.fake_file)
        self.assertEqual(
            {self.fake_file.name: self.fake_file},
            self.filesystem.root.get_entry(self.fake_child.name).contents)

    def test_add_object_to_regular_file_error_posix(self):
        self.filesystem.is_windows_fs = False
        self.filesystem.add_object(self.root_name, self.fake_file)
        self.assert_raises_os_error(errno.ENOTDIR,
                                    self.filesystem.add_object,
                                    self.fake_file.name, self.fake_file)

    def test_add_object_to_regular_file_error_windows(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.add_object(self.root_name, self.fake_file)
        self.assert_raises_os_error(errno.ENOENT,
                                    self.filesystem.add_object,
                                    self.fake_file.name, self.fake_file)

    def test_exists_file_added_to_child(self):
        self.filesystem.add_object(self.root_name, self.fake_child)
        self.filesystem.add_object(self.fake_child.name, self.fake_file)
        path = self.filesystem.joinpaths(self.fake_child.name,
                                         self.fake_file.name)
        self.assertTrue(self.filesystem.exists(path))

    def test_get_object_from_child(self):
        self.filesystem.add_object(self.root_name, self.fake_child)
        self.filesystem.add_object(self.fake_child.name, self.fake_file)
        self.assertEqual(self.fake_file,
                         self.filesystem.get_object(
                             self.filesystem.joinpaths(self.fake_child.name,
                                                       self.fake_file.name)))

    def test_get_nonexistent_object_from_child_error(self):
        self.filesystem.add_object(self.root_name, self.fake_child)
        self.filesystem.add_object(self.fake_child.name, self.fake_file)
        self.assert_raises_io_error(errno.ENOENT, self.filesystem.get_object,
                                    self.filesystem.joinpaths(
                                        self.fake_child.name,
                                        'some_bogus_filename'))

    def test_remove_object_from_child(self):
        self.filesystem.add_object(self.root_name, self.fake_child)
        self.filesystem.add_object(self.fake_child.name, self.fake_file)
        target_path = self.filesystem.joinpaths(self.fake_child.name,
                                                self.fake_file.name)
        self.filesystem.remove_object(target_path)
        self.assert_raises_io_error(errno.ENOENT, self.filesystem.get_object,
                                    target_path)

    def test_remove_object_from_child_error(self):
        self.filesystem.add_object(self.root_name, self.fake_child)
        self.assert_raises_io_error(errno.ENOENT, self.filesystem.remove_object,
                                    self.filesystem.joinpaths(
                                        self.fake_child.name,
                                        'some_bogus_filename'))

    def test_remove_object_from_non_directory_error(self):
        self.filesystem.add_object(self.root_name, self.fake_file)
        self.assert_raises_io_error(
            errno.ENOTDIR, self.filesystem.remove_object,
            self.filesystem.joinpaths(
                '%s' % self.fake_file.name,
                'file_does_not_matter_since_parent_not_a_directory'))

    def test_exists_file_removed_from_child(self):
        self.filesystem.add_object(self.root_name, self.fake_child)
        self.filesystem.add_object(self.fake_child.name, self.fake_file)
        path = self.filesystem.joinpaths(self.fake_child.name,
                                         self.fake_file.name)
        self.filesystem.remove_object(path)
        self.assertFalse(self.filesystem.exists(path))

    def test_operate_on_grandchild_directory(self):
        self.filesystem.add_object(self.root_name, self.fake_child)
        self.filesystem.add_object(self.fake_child.name, self.fake_grandchild)
        grandchild_directory = self.filesystem.joinpaths(self.fake_child.name,
                                                         self.fake_grandchild.name)
        grandchild_file = self.filesystem.joinpaths(grandchild_directory,
                                                    self.fake_file.name)
        self.assertRaises(IOError, self.filesystem.get_object, grandchild_file)
        self.filesystem.add_object(grandchild_directory, self.fake_file)
        self.assertEqual(self.fake_file,
                         self.filesystem.get_object(grandchild_file))
        self.assertTrue(self.filesystem.exists(grandchild_file))
        self.filesystem.remove_object(grandchild_file)
        self.assertRaises(IOError, self.filesystem.get_object, grandchild_file)
        self.assertFalse(self.filesystem.exists(grandchild_file))

    def test_create_directory_in_root_directory(self):
        path = 'foo'
        self.filesystem.create_dir(path)
        new_dir = self.filesystem.get_object(path)
        self.assertEqual(os.path.basename(path), new_dir.name)
        self.assertTrue(stat.S_IFDIR & new_dir.st_mode)

    def test_create_directory_in_root_directory_already_exists_error(self):
        path = 'foo'
        self.filesystem.create_dir(path)
        self.assert_raises_os_error(
            errno.EEXIST, self.filesystem.create_dir, path)

    def test_create_directory(self):
        path = 'foo/bar/baz'
        self.filesystem.create_dir(path)
        new_dir = self.filesystem.get_object(path)
        self.assertEqual(os.path.basename(path), new_dir.name)
        self.assertTrue(stat.S_IFDIR & new_dir.st_mode)

        # Create second directory to make sure first is OK.
        path = '%s/quux' % path
        self.filesystem.create_dir(path)
        new_dir = self.filesystem.get_object(path)
        self.assertEqual(os.path.basename(path), new_dir.name)
        self.assertTrue(stat.S_IFDIR & new_dir.st_mode)

    def test_create_directory_already_exists_error(self):
        path = 'foo/bar/baz'
        self.filesystem.create_dir(path)
        self.assert_raises_os_error(
            errno.EEXIST, self.filesystem.create_dir, path)

    def test_create_file_in_read_only_directory_raises_in_posix(self):
        self.filesystem.is_windows_fs = False
        dir_path = '/foo/bar'
        self.filesystem.create_dir(dir_path, perm_bits=0o555)
        file_path = dir_path + '/baz'
        if sys.version_info[0] < 3:
            self.assert_raises_io_error(errno.EACCES, self.filesystem.create_file,
                                        file_path)
        else:
            self.assert_raises_os_error(errno.EACCES, self.filesystem.create_file,
                                        file_path)

    def test_create_file_in_read_only_directory_possible_in_windows(self):
        self.filesystem.is_windows_fs = True
        dir_path = 'C:/foo/bar'
        self.filesystem.create_dir(dir_path, perm_bits=0o555)
        file_path = dir_path + '/baz'
        self.filesystem.create_file(file_path)
        self.assertTrue(self.filesystem.exists(file_path))

    def test_create_file_in_current_directory(self):
        path = 'foo'
        contents = 'dummy data'
        self.filesystem.create_file(path, contents=contents)
        self.assertTrue(self.filesystem.exists(path))
        self.assertFalse(self.filesystem.exists(os.path.dirname(path)))
        path = './%s' % path
        self.assertTrue(self.filesystem.exists(os.path.dirname(path)))

    def test_create_file_in_root_directory(self):
        path = '/foo'
        contents = 'dummy data'
        self.filesystem.create_file(path, contents=contents)
        new_file = self.filesystem.get_object(path)
        self.assertTrue(self.filesystem.exists(path))
        self.assertTrue(self.filesystem.exists(os.path.dirname(path)))
        self.assertEqual(os.path.basename(path), new_file.name)
        self.assertTrue(stat.S_IFREG & new_file.st_mode)
        self.assertEqual(contents, new_file.contents)

    def test_create_file_with_size_but_no_content_creates_large_file(self):
        path = 'large_foo_bar'
        self.filesystem.create_file(path, st_size=100000000)
        new_file = self.filesystem.get_object(path)
        self.assertEqual(None, new_file.contents)
        self.assertEqual(100000000, new_file.st_size)

    def test_create_file_in_root_directory_already_exists_error(self):
        path = 'foo'
        self.filesystem.create_file(path)
        self.assert_raises_os_error(
            errno.EEXIST, self.filesystem.create_file, path)

    def test_create_file(self):
        path = 'foo/bar/baz'
        retval = self.filesystem.create_file(path, contents='dummy_data')
        self.assertTrue(self.filesystem.exists(path))
        self.assertTrue(self.filesystem.exists(os.path.dirname(path)))
        new_file = self.filesystem.get_object(path)
        self.assertEqual(os.path.basename(path), new_file.name)
        self.assertTrue(stat.S_IFREG & new_file.st_mode)
        self.assertEqual(new_file, retval)

    def test_create_file_with_incorrect_mode_type(self):
        self.assertRaises(TypeError, self.filesystem.create_file, 'foo', 'bar')

    def test_create_file_already_exists_error(self):
        path = 'foo/bar/baz'
        self.filesystem.create_file(path, contents='dummy_data')
        self.assert_raises_os_error(
            errno.EEXIST, self.filesystem.create_file, path)

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def test_create_link(self):
        path = 'foo/bar/baz'
        target_path = 'foo/bar/quux'
        new_file = self.filesystem.create_symlink(path, 'quux')
        # Neither the path not the final target exists before we actually write to
        # one of them, even though the link appears in the file system.
        self.assertFalse(self.filesystem.exists(path))
        self.assertFalse(self.filesystem.exists(target_path))
        self.assertTrue(stat.S_IFLNK & new_file.st_mode)

        # but once we write the linked to file, they both will exist.
        self.filesystem.create_file(target_path)
        self.assertTrue(self.filesystem.exists(path))
        self.assertTrue(self.filesystem.exists(target_path))

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def test_resolve_object(self):
        target_path = 'dir/target'
        target_contents = '0123456789ABCDEF'
        link_name = 'x'
        self.filesystem.create_dir('dir')
        self.filesystem.create_file('dir/target', contents=target_contents)
        self.filesystem.create_symlink(link_name, target_path)
        obj = self.filesystem.resolve(link_name)
        self.assertEqual('target', obj.name)
        self.assertEqual(target_contents, obj.contents)

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def check_lresolve_object(self):
        target_path = 'dir/target'
        target_contents = '0123456789ABCDEF'
        link_name = 'x'
        self.filesystem.create_dir('dir')
        self.filesystem.create_file('dir/target', contents=target_contents)
        self.filesystem.create_symlink(link_name, target_path)
        obj = self.filesystem.lresolve(link_name)
        self.assertEqual(link_name, obj.name)
        self.assertEqual(target_path, obj.contents)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def test_lresolve_object_windows(self):
        self.filesystem.is_windows_fs = True
        self.check_lresolve_object()

    def test_lresolve_object_posix(self):
        self.filesystem.is_windows_fs = False
        self.check_lresolve_object()

    def check_directory_access_on_file(self, error_subtype):
        self.filesystem.create_file('not_a_dir')
        self.assert_raises_io_error(
            error_subtype, self.filesystem.resolve, 'not_a_dir/foo')
        self.assert_raises_io_error(
            error_subtype, self.filesystem.lresolve, 'not_a_dir/foo/bar')

    def test_directory_access_on_file_windows(self):
        self.filesystem.is_windows_fs = True
        self.check_directory_access_on_file(errno.ENOENT)

    def test_directory_access_on_file_posix(self):
        self.filesystem.is_windows_fs = False
        self.check_directory_access_on_file(errno.ENOTDIR)


class CaseInsensitiveFakeFilesystemTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.filesystem.is_case_sensitive = False
        self.os = fake_filesystem.FakeOsModule(self.filesystem)
        self.path = self.os.path

    def test_get_object(self):
        self.filesystem.create_dir('/foo/bar')
        self.filesystem.create_file('/foo/bar/baz')
        self.assertTrue(self.filesystem.get_object('/Foo/Bar/Baz'))

    def test_remove_object(self):
        self.filesystem.create_dir('/foo/bar')
        self.filesystem.create_file('/foo/bar/baz')
        self.filesystem.remove_object('/Foo/Bar/Baz')
        self.assertFalse(self.filesystem.exists('/foo/bar/baz'))

    def test_exists(self):
        self.filesystem.create_dir('/Foo/Bar')
        self.assertTrue(self.filesystem.exists('/Foo/Bar'))
        self.assertTrue(self.filesystem.exists('/foo/bar'))

        self.filesystem.create_file('/foo/Bar/baz')
        self.assertTrue(self.filesystem.exists('/Foo/bar/BAZ'))
        self.assertTrue(self.filesystem.exists('/foo/bar/baz'))

    def test_create_directory_with_different_case_root(self):
        self.filesystem.create_dir('/Foo/Bar')
        self.filesystem.create_dir('/foo/bar/baz')
        dir1 = self.filesystem.get_object('/Foo/Bar')
        dir2 = self.filesystem.get_object('/foo/bar')
        self.assertEqual(dir1, dir2)

    def test_create_file_with_different_case_dir(self):
        self.filesystem.create_dir('/Foo/Bar')
        self.filesystem.create_file('/foo/bar/baz')
        dir1 = self.filesystem.get_object('/Foo/Bar')
        dir2 = self.filesystem.get_object('/foo/bar')
        self.assertEqual(dir1, dir2)

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def test_resolve_path(self):
        self.filesystem.create_dir('/foo/baz')
        self.filesystem.create_symlink('/Foo/Bar', './baz/bip')
        self.assertEqual('/foo/baz/bip',
                         self.filesystem.resolve_path('/foo/bar'))

    def test_isdir_isfile(self):
        self.filesystem.create_file('foo/bar')
        self.assertTrue(self.path.isdir('Foo'))
        self.assertFalse(self.path.isfile('Foo'))
        self.assertTrue(self.path.isfile('Foo/Bar'))
        self.assertFalse(self.path.isdir('Foo/Bar'))

    def test_getsize(self):
        file_path = 'foo/bar/baz'
        self.filesystem.create_file(file_path, contents='1234567')
        self.assertEqual(7, self.path.getsize('FOO/BAR/BAZ'))

    def test_getsize_with_looping_symlink(self):
        self.filesystem.is_windows_fs = False
        dir_path = '/foo/bar'
        self.filesystem.create_dir(dir_path)
        link_path = dir_path + "/link"
        link_target = link_path + "/link"
        self.os.symlink(link_target, link_path)
        self.assert_raises_os_error(errno.ELOOP, self.os.path.getsize, link_path)

    def test_get_mtime(self):
        test_file = self.filesystem.create_file('foo/bar1.txt')
        test_file.st_mtime = 24
        self.assertEqual(24, self.path.getmtime('Foo/Bar1.TXT'))

    def test_get_object_with_file_size(self):
        self.filesystem.create_file('/Foo/Bar', st_size=10)
        self.assertTrue(self.filesystem.get_object('/foo/bar'))


class CaseSensitiveFakeFilesystemTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.filesystem.is_case_sensitive = True
        self.os = fake_filesystem.FakeOsModule(self.filesystem)
        self.path = self.os.path

    def test_get_object(self):
        self.filesystem.create_dir('/foo/bar')
        self.filesystem.create_file('/foo/bar/baz')
        self.assertRaises(IOError, self.filesystem.get_object, '/Foo/Bar/Baz')

    def test_remove_object(self):
        self.filesystem.create_dir('/foo/bar')
        self.filesystem.create_file('/foo/bar/baz')
        self.assertRaises(
            IOError, self.filesystem.remove_object, '/Foo/Bar/Baz')
        self.assertTrue(self.filesystem.exists('/foo/bar/baz'))

    def test_exists(self):
        self.filesystem.create_dir('/Foo/Bar')
        self.assertTrue(self.filesystem.exists('/Foo/Bar'))
        self.assertFalse(self.filesystem.exists('/foo/bar'))

        self.filesystem.create_file('/foo/Bar/baz')
        self.assertFalse(self.filesystem.exists('/Foo/bar/BAZ'))
        self.assertFalse(self.filesystem.exists('/foo/bar/baz'))

    def test_create_directory_with_different_case_root(self):
        self.filesystem.create_dir('/Foo/Bar')
        self.filesystem.create_dir('/foo/bar/baz')
        dir1 = self.filesystem.get_object('/Foo/Bar')
        dir2 = self.filesystem.get_object('/foo/bar')
        self.assertNotEqual(dir1, dir2)

    def test_create_file_with_different_case_dir(self):
        self.filesystem.create_dir('/Foo/Bar')
        self.filesystem.create_file('/foo/bar/baz')
        dir1 = self.filesystem.get_object('/Foo/Bar')
        dir2 = self.filesystem.get_object('/foo/bar')
        self.assertNotEqual(dir1, dir2)

    def test_isdir_isfile(self):
        self.filesystem.create_file('foo/bar')
        self.assertFalse(self.path.isdir('Foo'))
        self.assertFalse(self.path.isfile('Foo'))
        self.assertFalse(self.path.isfile('Foo/Bar'))
        self.assertFalse(self.path.isdir('Foo/Bar'))

    def test_getsize(self):
        file_path = 'foo/bar/baz'
        self.filesystem.create_file(file_path, contents='1234567')
        self.assertRaises(os.error, self.path.getsize, 'FOO/BAR/BAZ')

    def test_get_mtime(self):
        test_file = self.filesystem.create_file('foo/bar1.txt')
        test_file.st_mtime = 24
        self.assert_raises_os_error(
            errno.ENOENT, self.path.getmtime, 'Foo/Bar1.TXT')


class FakeOsModuleTestBase(RealFsTestCase):
    def createTestFile(self, path):
        self.create_file(path)
        self.assertTrue(self.os.path.exists(path))
        st = self.os.stat(path)
        self.assertEqual(0o666, stat.S_IMODE(st.st_mode))
        self.assertTrue(st.st_mode & stat.S_IFREG)
        self.assertFalse(st.st_mode & stat.S_IFDIR)

    def createTestDirectory(self, path):
        self.create_dir(path)
        self.assertTrue(self.os.path.exists(path))
        st = self.os.stat(path)
        self.assertEqual(0o777, stat.S_IMODE(st.st_mode))
        self.assertFalse(st.st_mode & stat.S_IFREG)
        self.assertTrue(st.st_mode & stat.S_IFDIR)


class FakeOsModuleTest(FakeOsModuleTestBase):
    def setUp(self):
        super(FakeOsModuleTest, self).setUp()
        self.rwx = self.os.R_OK | self.os.W_OK | self.os.X_OK
        self.rw = self.os.R_OK | self.os.W_OK

    def test_chdir(self):
        """chdir should work on a directory."""
        directory = self.make_path('foo')
        self.create_dir(directory)
        self.os.chdir(directory)

    def test_chdir_fails_non_exist(self):
        """chdir should raise OSError if the target does not exist."""
        directory = self.make_path('no', 'such', 'directory')
        self.assert_raises_os_error(errno.ENOENT, self.os.chdir, directory)

    def test_chdir_fails_non_directory(self):
        """chdir should raise OSError if the target is not a directory."""
        filename = self.make_path('foo', 'bar')
        self.create_file(filename)
        self.assert_raises_os_error(self.not_dir_error(), self.os.chdir, filename)

    def test_consecutive_chdir(self):
        """Consecutive relative chdir calls should work."""
        dir1 = self.make_path('foo')
        dir2 = 'bar'
        full_dirname = self.os.path.join(dir1, dir2)
        self.create_dir(full_dirname)
        self.os.chdir(dir1)
        self.os.chdir(dir2)
        # use real path to handle symlink /var to /private/var in MacOs
        self.assertEqual(os.path.realpath(self.os.getcwd()),
                         os.path.realpath(full_dirname))

    def test_backwards_chdir(self):
        """chdir into '..' should behave appropriately."""
        # skipping real fs test - can't test root dir
        self.skip_real_fs()
        rootdir = self.os.getcwd()
        dirname = 'foo'
        abs_dirname = self.os.path.abspath(dirname)
        self.filesystem.create_dir(dirname)
        self.os.chdir(dirname)
        self.assertEqual(abs_dirname, self.os.getcwd())
        self.os.chdir('..')
        self.assertEqual(rootdir, self.os.getcwd())
        self.os.chdir(self.os.path.join(dirname, '..'))
        self.assertEqual(rootdir, self.os.getcwd())

    def test_get_cwd(self):
        # skipping real fs test - can't test root dir
        self.skip_real_fs()
        dirname = self.make_path('foo', 'bar')
        self.create_dir(dirname)
        self.assertEqual(self.os.getcwd(), self.os.path.sep)
        self.os.chdir(dirname)
        self.assertEqual(self.os.getcwd(), dirname)

    def test_listdir(self):
        directory = self.make_path('xyzzy', 'plugh')
        files = ['foo', 'bar', 'baz']
        for f in files:
            self.create_file(self.os.path.join(directory, f))
        files.sort()
        self.assertEqual(files, sorted(self.os.listdir(directory)))

    @unittest.skipIf(sys.version_info < (3, 3),
                     'file descriptor as path new in Python 3.3')
    def test_listdir_uses_open_fd_as_path(self):
        self.check_posix_only()
        if os.listdir not in os.supports_fd:
            self.skip_real_fs()
        self.assert_raises_os_error(errno.EBADF, self.os.listdir, 500)
        dir_path = self.make_path('xyzzy', 'plugh')
        files = ['foo', 'bar', 'baz']
        for f in files:
            self.create_file(self.os.path.join(dir_path, f))
        files.sort()

        path_des = self.os.open(dir_path, os.O_RDONLY)
        self.assertEqual(files, sorted(self.os.listdir(path_des)))

    def test_listdir_returns_list(self):
        directory_root = self.make_path('xyzzy')
        self.os.mkdir(directory_root)
        directory = self.os.path.join(directory_root, 'bug')
        self.os.mkdir(directory)
        self.create_file(self.make_path(directory, 'foo'))
        self.assertEqual(['foo'], self.os.listdir(directory))

    def test_listdir_on_symlink(self):
        self.skip_if_symlink_not_supported()
        directory = self.make_path('xyzzy')
        files = ['foo', 'bar', 'baz']
        for f in files:
            self.create_file(self.make_path(directory, f))
        self.create_symlink(self.make_path('symlink'), self.make_path('xyzzy'))
        files.sort()
        self.assertEqual(files,
                         sorted(self.os.listdir(self.make_path('symlink'))))

    def test_listdir_error(self):
        file_path = self.make_path('foo', 'bar', 'baz')
        self.create_file(file_path)
        self.assert_raises_os_error(self.not_dir_error(),
                                    self.os.listdir, file_path)

    def test_exists_current_dir(self):
        self.assertTrue(self.os.path.exists('.'))

    def test_listdir_current(self):
        files = ['foo', 'bar', 'baz']
        for f in files:
            self.create_file(self.make_path(f))
        files.sort()
        self.assertEqual(files, sorted(self.os.listdir(self.base_path)))

    def test_fdopen(self):
        # under Windows and Python2, hangs in closing file
        self.skip_real_fs_failure(skip_posix=False, skip_python3=False)
        file_path1 = self.make_path('some_file1')
        self.create_file(file_path1, contents='contents here1')
        with self.open(file_path1, 'r') as fake_file1:
            fileno = fake_file1.fileno()
            fake_file2 = self.os.fdopen(fileno)
            self.assertNotEqual(fake_file2, fake_file1)

        self.assertRaises(TypeError, self.os.fdopen, None)
        self.assertRaises(TypeError, self.os.fdopen, 'a string')

    def test_out_of_range_fdopen(self):
        # test some file descriptor that is clearly out of range
        self.assert_raises_os_error(errno.EBADF, self.os.fdopen, 100)

    def test_closed_file_descriptor(self):
        # under Windows and Python2, hangs in tearDown
        self.skip_real_fs_failure(skip_posix=False, skip_python3=False)
        first_path = self.make_path('some_file1')
        second_path = self.make_path('some_file2')
        third_path = self.make_path('some_file3')
        self.create_file(first_path, contents='contents here1')
        self.create_file(second_path, contents='contents here2')
        self.create_file(third_path, contents='contents here3')

        fake_file1 = self.open(first_path, 'r')
        fake_file2 = self.open(second_path, 'r')
        fake_file3 = self.open(third_path, 'r')
        fileno1 = fake_file1.fileno()
        fileno2 = fake_file2.fileno()
        fileno3 = fake_file3.fileno()

        self.os.close(fileno2)
        self.assert_raises_os_error(errno.EBADF, self.os.close, fileno2)
        self.assertEqual(fileno1, fake_file1.fileno())
        self.assertEqual(fileno3, fake_file3.fileno())

        with self.os.fdopen(fileno1) as f:
            self.assertFalse(f is fake_file1)
        with self.os.fdopen(fileno3) as f:
            self.assertFalse(f is fake_file3)
        self.assert_raises_os_error(errno.EBADF, self.os.fdopen, fileno2)

    def test_fdopen_mode(self):
        self.skip_real_fs()
        file_path1 = self.make_path('some_file1')
        self.create_file(file_path1, contents='contents here1')
        self.os.chmod(file_path1, (stat.S_IFREG | 0o666) ^ stat.S_IWRITE)

        fake_file1 = self.open(file_path1, 'r')
        fileno1 = fake_file1.fileno()
        self.os.fdopen(fileno1)
        self.os.fdopen(fileno1, 'r')
        exception = OSError if self.is_python2 else IOError
        self.assertRaises(exception, self.os.fdopen, fileno1, 'w')

    def test_fstat(self):
        directory = self.make_path('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.create_file(file_path, contents='ABCDE')
        with self.open(file_path) as file_obj:
            fileno = file_obj.fileno()
            self.assertTrue(stat.S_IFREG & self.os.fstat(fileno)[stat.ST_MODE])
            self.assertTrue(stat.S_IFREG & self.os.fstat(fileno).st_mode)
            self.assertEqual(5, self.os.fstat(fileno)[stat.ST_SIZE])

    def test_stat(self):
        directory = self.make_path('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.create_file(file_path, contents='ABCDE')
        self.assertTrue(stat.S_IFDIR & self.os.stat(directory)[stat.ST_MODE])
        self.assertTrue(stat.S_IFREG & self.os.stat(file_path)[stat.ST_MODE])
        self.assertTrue(stat.S_IFREG & self.os.stat(file_path).st_mode)
        self.assertEqual(5, self.os.stat(file_path)[stat.ST_SIZE])

    @unittest.skipIf(sys.version_info < (3, 3),
                     'file descriptor as path new in Python 3.3')
    def test_stat_uses_open_fd_as_path(self):
        self.skip_real_fs()
        self.assert_raises_os_error(errno.EBADF, self.os.stat, 5)
        file_path = self.make_path('foo', 'bar')
        self.create_file(file_path)

        with self.open(file_path) as f:
            self.assertTrue(
                stat.S_IFREG & self.os.stat(f.filedes)[stat.ST_MODE])

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def test_stat_no_follow_symlinks_posix(self):
        """Test that stat with follow_symlinks=False behaves like lstat."""
        self.check_posix_only()
        directory = self.make_path('xyzzy')
        base_name = 'plugh'
        file_contents = 'frobozz'
        # Just make sure we didn't accidentally make our test data meaningless.
        self.assertNotEqual(len(base_name), len(file_contents))
        file_path = self.os.path.join(directory, base_name)
        link_path = self.os.path.join(directory, 'link')
        self.create_file(file_path, contents=file_contents)
        self.create_symlink(link_path, base_name)
        self.assertEqual(len(file_contents),
                         self.os.stat(file_path, follow_symlinks=False)[
                             stat.ST_SIZE])
        self.assertEqual(len(base_name),
                         self.os.stat(link_path, follow_symlinks=False)[
                             stat.ST_SIZE])

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def test_stat_no_follow_symlinks_windows(self):
        """Test that stat with follow_symlinks=False behaves like lstat."""
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        directory = self.make_path('xyzzy')
        base_name = 'plugh'
        file_contents = 'frobozz'
        # Just make sure we didn't accidentally make our test data meaningless.
        self.assertNotEqual(len(base_name), len(file_contents))
        file_path = self.os.path.join(directory, base_name)
        link_path = self.os.path.join(directory, 'link')
        self.create_file(file_path, contents=file_contents)
        self.create_symlink(link_path, base_name)
        self.assertEqual(len(file_contents),
                         self.os.stat(file_path, follow_symlinks=False)[
                             stat.ST_SIZE])
        self.assertEqual(0,
                         self.os.stat(link_path, follow_symlinks=False)[
                             stat.ST_SIZE])

    def test_lstat_size_posix(self):
        self.check_posix_only()
        directory = self.make_path('xyzzy')
        base_name = 'plugh'
        file_contents = 'frobozz'
        # Just make sure we didn't accidentally make our test data meaningless.
        self.assertNotEqual(len(base_name), len(file_contents))
        file_path = self.os.path.join(directory, base_name)
        link_path = self.os.path.join(directory, 'link')
        self.create_file(file_path, contents=file_contents)
        self.create_symlink(link_path, base_name)
        self.assertEqual(len(file_contents),
                         self.os.lstat(file_path)[stat.ST_SIZE])
        self.assertEqual(len(base_name),
                         self.os.lstat(link_path)[stat.ST_SIZE])

    def test_lstat_size_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        directory = self.make_path('xyzzy')
        base_name = 'plugh'
        file_contents = 'frobozz'
        # Just make sure we didn't accidentally make our test data meaningless.
        self.assertNotEqual(len(base_name), len(file_contents))
        file_path = self.os.path.join(directory, base_name)
        link_path = self.os.path.join(directory, 'link')
        self.create_file(file_path, contents=file_contents)
        self.create_symlink(link_path, base_name)
        self.assertEqual(len(file_contents),
                         self.os.lstat(file_path)[stat.ST_SIZE])
        self.assertEqual(0,
                         self.os.lstat(link_path)[stat.ST_SIZE])

    @unittest.skipIf(sys.version_info < (3, 3),
                     'file descriptor as path new in Python 3.3')
    def test_lstat_uses_open_fd_as_path(self):
        self.skip_if_symlink_not_supported()
        if os.lstat not in os.supports_fd:
            self.skip_real_fs()
        self.assert_raises_os_error(errno.EBADF, self.os.lstat, 5)
        file_path = self.make_path('foo', 'bar')
        link_path = self.make_path('foo', 'link')
        file_contents = b'contents'
        self.create_file(file_path, contents=file_contents)
        self.create_symlink(link_path, file_path)

        with self.open(file_path) as f:
            self.assertEqual(len(file_contents),
                             self.os.lstat(f.filedes)[stat.ST_SIZE])

    def test_stat_non_existent_file(self):
        # set up
        file_path = self.make_path('non', 'existent', 'file')
        self.assertFalse(self.os.path.exists(file_path))
        # actual tests
        try:
            # Use try-catch to check exception attributes.
            self.os.stat(file_path)
            self.fail('Exception is expected.')  # COV_NF_LINE
        except OSError as os_error:
            self.assertEqual(errno.ENOENT, os_error.errno)
            self.assertEqual(file_path, os_error.filename)

    def test_readlink(self):
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('foo', 'bar', 'baz')
        target = self.make_path('tarJAY')
        self.create_symlink(link_path, target)
        self.assertEqual(self.os.readlink(link_path), target)

    def check_readlink_raises_if_path_is_not_a_link(self):
        file_path = self.make_path('foo', 'bar', 'eleventyone')
        self.create_file(file_path)
        self.assert_raises_os_error(errno.EINVAL, self.os.readlink, file_path)

    def test_readlink_raises_if_path_is_not_a_link_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        self.check_readlink_raises_if_path_is_not_a_link()

    def test_readlink_raises_if_path_is_not_a_link_posix(self):
        self.check_posix_only()
        self.check_readlink_raises_if_path_is_not_a_link()

    def check_readlink_raises_if_path_has_file(self, error_subtype):
        self.create_file(self.make_path('a_file'))
        file_path = self.make_path('a_file', 'foo')
        self.assert_raises_os_error(error_subtype, self.os.readlink, file_path)
        file_path = self.make_path('a_file', 'foo', 'bar')
        self.assert_raises_os_error(error_subtype, self.os.readlink, file_path)

    def test_readlink_raises_if_path_has_file_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        self.check_readlink_raises_if_path_has_file(errno.ENOENT)

    def test_readlink_raises_if_path_has_file_posix(self):
        self.check_posix_only()
        self.check_readlink_raises_if_path_has_file(errno.ENOTDIR)

    def test_readlink_raises_if_path_does_not_exist(self):
        self.skip_if_symlink_not_supported()
        self.assert_raises_os_error(errno.ENOENT, self.os.readlink,
                                    '/this/path/does/not/exist')

    def test_readlink_raises_if_path_is_none(self):
        self.skip_if_symlink_not_supported()
        self.assertRaises(TypeError, self.os.readlink, None)

    def test_readlink_with_links_in_path(self):
        self.skip_if_symlink_not_supported()
        self.create_symlink(self.make_path('meyer', 'lemon', 'pie'),
                            self.make_path('yum'))
        self.create_symlink(self.make_path('geo', 'metro'),
                            self.make_path('meyer'))
        self.assertEqual(self.make_path('yum'),
                         self.os.readlink(
                             self.make_path('geo', 'metro', 'lemon', 'pie')))

    def test_readlink_with_chained_links_in_path(self):
        self.skip_if_symlink_not_supported()
        self.create_symlink(self.make_path(
            'eastern', 'european', 'wolfhounds', 'chase'),
            self.make_path('cats'))
        self.create_symlink(self.make_path('russian'),
                            self.make_path('eastern', 'european'))
        self.create_symlink(self.make_path('dogs'),
                            self.make_path('russian', 'wolfhounds'))
        self.assertEqual(self.make_path('cats'),
                         self.os.readlink(self.make_path('dogs', 'chase')))

    def check_remove_dir(self, dir_error):
        directory = self.make_path('xyzzy')
        dir_path = self.os.path.join(directory, 'plugh')
        self.create_dir(dir_path)
        self.assertTrue(self.os.path.exists(dir_path))
        self.assert_raises_os_error(dir_error, self.os.remove, dir_path)
        self.assertTrue(self.os.path.exists(dir_path))
        self.os.chdir(directory)
        self.assert_raises_os_error(dir_error, self.os.remove, dir_path)
        self.assertTrue(self.os.path.exists(dir_path))
        self.assert_raises_os_error(errno.ENOENT, self.os.remove, '/plugh')

    def test_remove_dir_linux(self):
        self.check_linux_only()
        self.check_remove_dir(errno.EISDIR)

    def test_remove_dir_mac_os(self):
        self.check_macos_only()
        self.check_remove_dir(errno.EPERM)

    def test_remove_dir_windows(self):
        self.check_windows_only()
        self.check_remove_dir(errno.EACCES)

    def test_remove_file(self):
        directory = self.make_path('zzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.create_file(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.os.remove(file_path)
        self.assertFalse(self.os.path.exists(file_path))

    def test_remove_file_no_directory(self):
        directory = self.make_path('zzy')
        file_name = 'plugh'
        file_path = self.os.path.join(directory, file_name)
        self.create_file(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.os.chdir(directory)
        self.os.remove(file_name)
        self.assertFalse(self.os.path.exists(file_path))

    def test_remove_file_with_read_permission_raises_in_windows(self):
        self.check_windows_only()
        path = self.make_path('foo', 'bar')
        self.create_file(path)
        self.os.chmod(path, 0o444)
        self.assert_raises_os_error(errno.EACCES, self.os.remove, path)
        self.os.chmod(path, 0o666)

    def test_remove_file_with_read_permission_shall_succeed_in_posix(self):
        self.check_posix_only()
        path = self.make_path('foo', 'bar')
        self.create_file(path)
        self.os.chmod(path, 0o444)
        self.os.remove(path)
        self.assertFalse(self.os.path.exists(path))

    def test_remove_file_without_parent_permission_raises_in_posix(self):
        self.check_posix_only()
        parent_dir = self.make_path('foo')
        path = self.os.path.join(parent_dir, 'bar')
        self.create_file(path)
        self.os.chmod(parent_dir, 0o666)  # missing execute permission
        self.assert_raises_os_error(errno.EACCES, self.os.remove, path)
        self.os.chmod(parent_dir, 0o555)  # missing write permission
        self.assert_raises_os_error(errno.EACCES, self.os.remove, path)
        self.os.chmod(parent_dir, 0o333)
        self.os.remove(path)
        self.assertFalse(self.os.path.exists(path))

    def test_remove_open_file_fails_under_windows(self):
        self.check_windows_only()
        path = self.make_path('foo', 'bar')
        self.create_file(path)
        with self.open(path, 'r'):
            self.assert_raises_os_error(errno.EACCES, self.os.remove, path)
        self.assertTrue(self.os.path.exists(path))

    def test_remove_open_file_possible_under_posix(self):
        self.check_posix_only()
        path = self.make_path('foo', 'bar')
        self.create_file(path)
        self.open(path, 'r')
        self.os.remove(path)
        self.assertFalse(self.os.path.exists(path))

    def test_remove_file_relative_path(self):
        self.skip_real_fs()
        original_dir = self.os.getcwd()
        directory = self.make_path('zzy')
        subdirectory = self.os.path.join(directory, 'zzy')
        file_name = 'plugh'
        file_path = self.os.path.join(directory, file_name)
        file_path_relative = self.os.path.join('..', file_name)
        self.create_file(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.create_dir(subdirectory)
        self.assertTrue(self.os.path.exists(subdirectory))
        self.os.chdir(subdirectory)
        self.os.remove(file_path_relative)
        self.assertFalse(self.os.path.exists(file_path_relative))
        self.os.chdir(original_dir)
        self.assertFalse(self.os.path.exists(file_path))

    def check_remove_dir_raises_error(self, dir_error):
        directory = self.make_path('zzy')
        self.create_dir(directory)
        self.assert_raises_os_error(dir_error, self.os.remove, directory)

    def test_remove_dir_raises_error_linux(self):
        self.check_linux_only()
        self.check_remove_dir_raises_error(errno.EISDIR)

    def test_remove_dir_raises_error_mac_os(self):
        self.check_macos_only()
        self.check_remove_dir_raises_error(errno.EPERM)

    def test_remove_dir_raises_error_windows(self):
        self.check_windows_only()
        self.check_remove_dir_raises_error(errno.EACCES)

    def test_remove_symlink_to_dir(self):
        self.skip_if_symlink_not_supported()
        directory = self.make_path('zzy')
        link = self.make_path('link_to_dir')
        self.create_dir(directory)
        self.os.symlink(directory, link)
        self.assertTrue(self.os.path.exists(directory))
        self.assertTrue(self.os.path.exists(link))
        self.os.remove(link)
        self.assertTrue(self.os.path.exists(directory))
        self.assertFalse(self.os.path.exists(link))

    def test_unlink_raises_if_not_exist(self):
        file_path = self.make_path('file', 'does', 'not', 'exist')
        self.assertFalse(self.os.path.exists(file_path))
        self.assert_raises_os_error(errno.ENOENT, self.os.unlink, file_path)

    def test_rename_to_nonexistent_file(self):
        """Can rename a file to an unused name."""
        directory = self.make_path('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.create_file(old_file_path, contents='test contents')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertFalse(self.os.path.exists(new_file_path))
        self.os.rename(old_file_path, new_file_path)
        self.assertFalse(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.check_contents(new_file_path, 'test contents')

    def test_rename_dir_to_symlink_posix(self):
        self.check_posix_only()
        link_path = self.make_path('link')
        dir_path = self.make_path('dir')
        link_target = self.os.path.join(dir_path, 'link_target')
        self.create_dir(dir_path)
        self.os.symlink(link_target, link_path)
        self.assert_raises_os_error(errno.ENOTDIR, self.os.rename, dir_path,
                                    link_path)

    def test_rename_dir_to_symlink_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('link')
        dir_path = self.make_path('dir')
        link_target = self.os.path.join(dir_path, 'link_target')
        self.create_dir(dir_path)
        self.os.symlink(link_target, link_path)
        self.assert_raises_os_error(errno.EEXIST, self.os.rename, dir_path,
                                    link_path)

    def test_rename_file_to_symlink(self):
        self.check_posix_only()
        link_path = self.make_path('file_link')
        file_path = self.make_path('file')
        self.os.symlink(file_path, link_path)
        self.create_file(file_path)
        self.os.rename(file_path, link_path)
        self.assertFalse(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.exists(link_path))
        self.assertTrue(self.os.path.isfile(link_path))

    def test_rename_symlink_to_symlink(self):
        self.check_posix_only()
        base_path = self.make_path('foo', 'bar')
        self.create_dir(base_path)
        link_path1 = self.os.path.join(base_path, 'link1')
        link_path2 = self.os.path.join(base_path, 'link2')
        self.os.symlink(base_path, link_path1)
        self.os.symlink(base_path, link_path2)
        self.os.rename(link_path1, link_path2)
        self.assertFalse(self.os.path.exists(link_path1))
        self.assertTrue(self.os.path.exists(link_path2))

    def test_rename_symlink_to_symlink_for_parent_raises(self):
        self.check_posix_only()
        dir_link = self.make_path('dir_link')
        dir_path = self.make_path('dir')
        dir_in_dir_path = self.os.path.join(dir_link, 'inner_dir')
        self.create_dir(dir_path)
        self.os.symlink(dir_path, dir_link)
        self.create_dir(dir_in_dir_path)
        self.assert_raises_os_error(errno.EINVAL, self.os.rename, dir_path,
                                    dir_in_dir_path)

    def test_recursive_rename_raises(self):
        self.check_posix_only()
        base_path = self.make_path('foo', 'bar')
        self.create_dir(base_path)
        new_path = self.os.path.join(base_path, 'new_dir')
        self.assert_raises_os_error(errno.EINVAL, self.os.rename, base_path,
                                    new_path)

    def test_rename_file_to_parent_dir_file(self):
        # Regression test for issue 230
        dir_path = self.make_path('dir')
        self.create_dir(dir_path)
        file_path = self.make_path('old_file')
        new_file_path = self.os.path.join(dir_path, 'new_file')
        self.create_file(file_path)
        self.os.rename(file_path, new_file_path)

    def test_rename_with_target_parent_file_raises_posix(self):
        self.check_posix_only()
        file_path = self.make_path('foo', 'baz')
        self.create_file(file_path)
        self.assert_raises_os_error(errno.ENOTDIR, self.os.rename, file_path,
                                    file_path + '/new')

    def test_rename_with_target_parent_file_raises_windows(self):
        self.check_windows_only()
        file_path = self.make_path('foo', 'baz')
        self.create_file(file_path)
        self.assert_raises_os_error(errno.EACCES, self.os.rename, file_path,
                                    self.os.path.join(file_path, 'new'))

    def test_rename_symlink_to_source(self):
        self.check_posix_only()
        base_path = self.make_path('foo')
        link_path = self.os.path.join(base_path, 'slink')
        file_path = self.os.path.join(base_path, 'file')
        self.create_file(file_path)
        self.os.symlink(file_path, link_path)
        self.os.rename(link_path, file_path)
        self.assertFalse(self.os.path.exists(file_path))

    def test_rename_symlink_to_dir_raises(self):
        self.check_posix_only()
        base_path = self.make_path('foo', 'bar')
        link_path = self.os.path.join(base_path, 'dir_link')
        dir_path = self.os.path.join(base_path, 'dir')
        self.create_dir(dir_path)
        self.os.symlink(dir_path, link_path)
        self.assert_raises_os_error(errno.EISDIR, self.os.rename, link_path,
                                    dir_path)

    def test_rename_broken_symlink(self):
        self.check_posix_only()
        base_path = self.make_path('foo')
        self.create_dir(base_path)
        link_path = self.os.path.join(base_path, 'slink')
        file_path = self.os.path.join(base_path, 'file')
        self.os.symlink(file_path, link_path)
        self.os.rename(link_path, file_path)
        self.assertFalse(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.lexists(file_path))
        self.assertFalse(self.os.path.exists(link_path))

    def test_rename_directory(self):
        """Can rename a directory to an unused name."""
        for old_path, new_path in [('wxyyw', 'xyzzy'), ('abccb', 'cdeed')]:
            old_path = self.make_path(old_path)
            new_path = self.make_path(new_path)
            self.create_file(self.os.path.join(old_path, 'plugh'),
                             contents='test')
            self.assertTrue(self.os.path.exists(old_path))
            self.assertFalse(self.os.path.exists(new_path))
            self.os.rename(old_path, new_path)
            self.assertFalse(self.os.path.exists(old_path))
            self.assertTrue(self.os.path.exists(new_path))
            self.check_contents(self.os.path.join(new_path, 'plugh'), 'test')
            if not self.use_real_fs():
                self.assertEqual(3,
                                 self.filesystem.get_object(new_path).st_nlink)

    def check_rename_directory_to_existing_file_raises(self, error_nr):
        dir_path = self.make_path('dir')
        file_path = self.make_path('file')
        self.create_dir(dir_path)
        self.create_file(file_path)
        self.assert_raises_os_error(error_nr, self.os.rename, dir_path,
                                    file_path)

    def test_rename_directory_to_existing_file_raises_posix(self):
        self.check_posix_only()
        self.check_rename_directory_to_existing_file_raises(errno.ENOTDIR)

    def test_rename_directory_to_existing_file_raises_windows(self):
        self.check_windows_only()
        self.check_rename_directory_to_existing_file_raises(errno.EEXIST)

    def test_rename_to_existing_directory_should_raise_under_windows(self):
        """Renaming to an existing directory raises OSError under Windows."""
        self.check_windows_only()
        old_path = self.make_path('foo', 'bar')
        new_path = self.make_path('foo', 'baz')
        self.create_dir(old_path)
        self.create_dir(new_path)
        self.assert_raises_os_error(errno.EEXIST, self.os.rename, old_path,
                                    new_path)

    def test_rename_to_a_hardlink_of_same_file_should_do_nothing(self):
        self.skip_real_fs_failure(skip_posix=False)
        self.skip_if_symlink_not_supported()
        file_path = self.make_path('dir', 'file')
        self.create_file(file_path)
        link_path = self.make_path('link')
        self.os.link(file_path, link_path)
        self.os.rename(file_path, link_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.exists(link_path))

    def test_hardlink_works_with_symlink(self):
        self.check_posix_only()
        base_path = self.make_path('foo')
        self.create_dir(base_path)
        symlink_path = self.os.path.join(base_path, 'slink')
        self.os.symlink(base_path, symlink_path)
        file_path = self.os.path.join(base_path, 'slink', 'beta')
        self.create_file(file_path)
        link_path = self.os.path.join(base_path, 'slink', 'gamma')
        self.os.link(file_path, link_path)
        self.assertTrue(self.os.path.exists(link_path))

    @unittest.skipIf(sys.version_info < (3, 3), 'replace is new in Python 3.3')
    def test_replace_existing_directory_should_raise_under_windows(self):
        """Renaming to an existing directory raises OSError under Windows."""
        self.check_windows_only()
        old_path = self.make_path('foo', 'bar')
        new_path = self.make_path('foo', 'baz')
        self.create_dir(old_path)
        self.create_dir(new_path)
        self.assert_raises_os_error(errno.EACCES, self.os.replace, old_path,
                                    new_path)

    def test_rename_to_existing_directory_under_posix(self):
        """Renaming to an existing directory changes the existing directory
        under Posix."""
        self.check_posix_only()
        old_path = self.make_path('foo', 'bar')
        new_path = self.make_path('xyzzy')
        self.create_dir(self.os.path.join(old_path, 'sub'))
        self.create_dir(new_path)
        self.os.rename(old_path, new_path)
        self.assertTrue(
            self.os.path.exists(self.os.path.join(new_path, 'sub')))
        self.assertFalse(self.os.path.exists(old_path))

    def test_rename_file_to_existing_directory_raises_under_posix(self):
        self.check_posix_only()
        file_path = self.make_path('foo', 'bar', 'baz')
        new_path = self.make_path('xyzzy')
        self.create_file(file_path)
        self.create_dir(new_path)
        self.assert_raises_os_error(errno.EISDIR, self.os.rename, file_path,
                                    new_path)

    def test_rename_to_existing_directory_under_posix_raises_if_not_empty(self):
        """Renaming to an existing directory changes the existing directory
        under Posix."""
        self.check_posix_only()
        old_path = self.make_path('foo', 'bar')
        new_path = self.make_path('foo', 'baz')
        self.create_dir(self.os.path.join(old_path, 'sub'))
        self.create_dir(self.os.path.join(new_path, 'sub'))

        # not testing specific subtype:
        # raises errno.ENOTEMPTY under Ubuntu 16.04, MacOS and pyfakefs
        # but raises errno.EEXIST at least under Ubunto 14.04
        self.assertRaises(OSError, self.os.rename, old_path, new_path)

    def test_rename_to_another_device_should_raise(self):
        """Renaming to another filesystem device raises OSError."""
        self.skip_real_fs()
        self.filesystem.add_mount_point('/mount')
        old_path = '/foo/bar'
        new_path = '/mount/bar'
        self.filesystem.create_file(old_path)
        self.assert_raises_os_error(errno.EXDEV, self.os.rename, old_path,
                                    new_path)

    def test_rename_to_existent_file_posix(self):
        """Can rename a file to a used name under Unix."""
        self.check_posix_only()
        directory = self.make_path('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.create_file(old_file_path, contents='test contents 1')
        self.create_file(new_file_path, contents='test contents 2')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.os.rename(old_file_path, new_file_path)
        self.assertFalse(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.check_contents(new_file_path, 'test contents 1')

    def test_rename_to_existent_file_windows(self):
        """Renaming a file to a used name raises OSError under Windows."""
        self.check_windows_only()
        directory = self.make_path('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.create_file(old_file_path, contents='test contents 1')
        self.create_file(new_file_path, contents='test contents 2')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.assert_raises_os_error(errno.EEXIST, self.os.rename, old_file_path,
                                    new_file_path)

    @unittest.skipIf(sys.version_info < (3, 3), 'replace is new in Python 3.3')
    def test_replace_to_existent_file(self):
        """Replaces an existing file (does not work with `rename()` under
        Windows)."""
        directory = self.make_path('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.create_file(old_file_path, contents='test contents 1')
        self.create_file(new_file_path, contents='test contents 2')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.os.replace(old_file_path, new_file_path)
        self.assertFalse(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.check_contents(new_file_path, 'test contents 1')

    def test_rename_to_nonexistent_dir(self):
        """Can rename a file to a name in a nonexistent dir."""
        directory = self.make_path('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(
            directory, 'no_such_path', 'plugh_new')
        self.create_file(old_file_path, contents='test contents')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertFalse(self.os.path.exists(new_file_path))
        self.assert_raises_os_error(errno.ENOENT, self.os.rename, old_file_path,
                                    new_file_path)
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertFalse(self.os.path.exists(new_file_path))
        self.check_contents(old_file_path, 'test contents')

    def test_rename_nonexistent_file_should_raise_error(self):
        """Can't rename a file that doesn't exist."""
        self.assert_raises_os_error(errno.ENOENT, self.os.rename,
                                    'nonexistent-foo', 'doesn\'t-matter-bar')

    def test_rename_empty_dir(self):
        """Test a rename of an empty directory."""
        directory = self.make_path('xyzzy')
        before_dir = self.os.path.join(directory, 'empty')
        after_dir = self.os.path.join(directory, 'unused')
        self.create_dir(before_dir)
        self.assertTrue(
            self.os.path.exists(self.os.path.join(before_dir, '.')))
        self.assertFalse(self.os.path.exists(after_dir))
        self.os.rename(before_dir, after_dir)
        self.assertFalse(self.os.path.exists(before_dir))
        self.assertTrue(self.os.path.exists(self.os.path.join(after_dir, '.')))

    def test_rename_symlink(self):
        self.check_posix_only()
        base_path = self.make_path('foo', 'bar')
        self.create_dir(base_path)
        link_path = self.os.path.join(base_path, 'link')
        self.os.symlink(base_path, link_path)
        file_path = self.os.path.join(link_path, 'file')
        new_file_path = self.os.path.join(link_path, 'new')
        self.create_file(file_path)
        self.os.rename(file_path, new_file_path)
        self.assertFalse(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.exists(new_file_path))

    def test_rename_dir(self):
        """Test a rename of a directory."""
        directory = self.make_path('xyzzy')
        before_dir = self.os.path.join(directory, 'before')
        before_file = self.os.path.join(directory, 'before', 'file')
        after_dir = self.os.path.join(directory, 'after')
        after_file = self.os.path.join(directory, 'after', 'file')
        self.create_dir(before_dir)
        self.create_file(before_file, contents='payload')
        self.assertTrue(self.os.path.exists(before_dir))
        self.assertTrue(self.os.path.exists(before_file))
        self.assertFalse(self.os.path.exists(after_dir))
        self.assertFalse(self.os.path.exists(after_file))
        self.os.rename(before_dir, after_dir)
        self.assertFalse(self.os.path.exists(before_dir))
        self.assertFalse(self.os.path.exists(before_file))
        self.assertTrue(self.os.path.exists(after_dir))
        self.assertTrue(self.os.path.exists(after_file))
        self.check_contents(after_file, 'payload')

    def test_rename_preserves_stat(self):
        """Test if rename preserves mtime."""
        self.check_posix_only()
        self.skip_real_fs()
        directory = self.make_path('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.create_file(old_file_path)
        old_file = self.filesystem.get_object(old_file_path)
        old_file.SetMTime(old_file.st_mtime - 3600)
        self.os.chown(old_file_path, 200, 200)
        self.os.chmod(old_file_path, 0o222)
        self.create_file(new_file_path)
        new_file = self.filesystem.get_object(new_file_path)
        self.assertNotEqual(new_file.st_mtime, old_file.st_mtime)
        self.os.rename(old_file_path, new_file_path)
        new_file = self.filesystem.get_object(new_file_path)
        self.assertEqual(new_file.st_mtime, old_file.st_mtime)
        self.assertEqual(new_file.st_mode, old_file.st_mode)
        self.assertEqual(new_file.st_uid, old_file.st_uid)
        self.assertEqual(new_file.st_gid, old_file.st_gid)

    def test_rename_same_filenames(self):
        """Test renaming when old and new names are the same."""
        directory = self.make_path('xyzzy')
        file_contents = 'Spam eggs'
        file_path = self.os.path.join(directory, 'eggs')
        self.create_file(file_path, contents=file_contents)
        self.os.rename(file_path, file_path)
        self.check_contents(file_path, file_contents)

    def test_rmdir(self):
        """Can remove a directory."""
        directory = self.make_path('xyzzy')
        sub_dir = self.make_path('xyzzy', 'abccd')
        other_dir = self.make_path('xyzzy', 'cdeed')
        self.create_dir(directory)
        self.assertTrue(self.os.path.exists(directory))
        self.os.rmdir(directory)
        self.assertFalse(self.os.path.exists(directory))
        self.create_dir(sub_dir)
        self.create_dir(other_dir)
        self.os.chdir(sub_dir)
        self.os.rmdir('../cdeed')
        self.assertFalse(self.os.path.exists(other_dir))
        self.os.chdir('..')
        self.os.rmdir('abccd')
        self.assertFalse(self.os.path.exists(sub_dir))

    def test_rmdir_raises_if_not_empty(self):
        """Raises an exception if the target directory is not empty."""
        directory = self.make_path('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.create_file(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.assert_raises_os_error(errno.ENOTEMPTY, self.os.rmdir, directory)

    def check_rmdir_raises_if_not_directory(self, error_nr):
        """Raises an exception if the target is not a directory."""
        directory = self.make_path('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.create_file(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.assert_raises_os_error(self.not_dir_error(),
                                    self.os.rmdir, file_path)
        self.assert_raises_os_error(error_nr, self.os.rmdir, '.')

    def test_rmdir_raises_if_not_directory_posix(self):
        self.check_posix_only()
        self.check_rmdir_raises_if_not_directory(errno.EINVAL)

    def test_rmdir_raises_if_not_directory_windows(self):
        self.check_windows_only()
        self.check_rmdir_raises_if_not_directory(errno.EACCES)

    def test_rmdir_raises_if_not_exist(self):
        """Raises an exception if the target does not exist."""
        directory = self.make_path('xyzzy')
        self.assertFalse(self.os.path.exists(directory))
        self.assert_raises_os_error(errno.ENOENT, self.os.rmdir, directory)

    def test_rmdir_via_symlink(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        base_path = self.make_path('foo', 'bar')
        dir_path = self.os.path.join(base_path, 'alpha')
        self.create_dir(dir_path)
        link_path = self.os.path.join(base_path, 'beta')
        self.os.symlink(base_path, link_path)
        self.os.rmdir(link_path + '/alpha')
        self.assertFalse(self.os.path.exists(dir_path))

    def remove_dirs_check(self, directory):
        self.assertTrue(self.os.path.exists(directory))
        self.os.removedirs(directory)
        return not self.os.path.exists(directory)

    def test_removedirs(self):
        # no exception raised
        self.skip_real_fs()
        data = ['test1', ('test1', 'test2'), ('test1', 'extra'),
                ('test1', 'test2', 'test3')]
        for directory in data:
            self.create_dir(self.make_path(directory))
            self.assertTrue(self.os.path.exists(self.make_path(directory)))
        self.assert_raises_os_error(errno.ENOTEMPTY, self.remove_dirs_check,
                                    self.make_path(data[0]))
        self.assert_raises_os_error(errno.ENOTEMPTY, self.remove_dirs_check,
                                    self.make_path(data[1]))

        self.assertTrue(self.remove_dirs_check(self.make_path(data[3])))
        self.assertTrue(self.os.path.exists(self.make_path(data[0])))
        self.assertFalse(self.os.path.exists(self.make_path(data[1])))
        self.assertTrue(self.os.path.exists(self.make_path(data[2])))

        # Should raise because '/test1/extra' is all that is left, and
        # removedirs('/test1/extra') will eventually try to rmdir('/').
        self.assert_raises_os_error(errno.EBUSY, self.remove_dirs_check,
                                    self.make_path(data[2]))

        # However, it will still delete '/test1') in the process.
        self.assertFalse(self.os.path.exists(self.make_path(data[0])))

        self.create_dir(self.make_path('test1', 'test2'))
        # Add this to the root directory to avoid raising an exception.
        self.filesystem.create_dir(self.make_path('test3'))
        self.assertTrue(self.remove_dirs_check(self.make_path('test1', 'test2')))
        self.assertFalse(self.os.path.exists(self.make_path('test1', 'test2')))
        self.assertFalse(self.os.path.exists(self.make_path('test1')))

    def test_removedirs_raises_if_removing_root(self):
        """Raises exception if asked to remove '/'."""
        self.skip_real_fs()
        self.os.rmdir(self.base_path)
        directory = self.os.path.sep
        self.assertTrue(self.os.path.exists(directory))
        self.assert_raises_os_error(errno.EBUSY, self.os.removedirs, directory)

    def test_removedirs_raises_if_cascade_removing_root(self):
        """Raises exception if asked to remove '/' as part of a
        larger operation.

        All of other directories should still be removed, though.
        """
        self.skip_real_fs()
        directory = self.make_path('foo', 'bar')
        self.create_dir(directory)
        self.assertTrue(self.os.path.exists(directory))
        self.assert_raises_os_error(errno.EBUSY, self.os.removedirs, directory)
        head, unused_tail = self.os.path.split(directory)
        while head != self.os.path.sep:
            self.assertFalse(self.os.path.exists(directory))
            head, unused_tail = self.os.path.split(head)

    def test_removedirs_with_trailing_slash(self):
        """removedirs works on directory names with trailing slashes."""
        # separate this case from the removing-root-directory case
        self.create_dir(self.make_path('baz'))
        directory = self.make_path('foo', 'bar')
        self.create_dir(directory)
        self.assertTrue(self.os.path.exists(directory))
        self.os.removedirs(directory)
        self.assertFalse(self.os.path.exists(directory))

    def test_remove_dirs_with_top_symlink_fails(self):
        self.check_posix_only()
        dir_path = self.make_path('dir')
        dir_link = self.make_path('dir_link')
        self.create_dir(dir_path)
        self.os.symlink(dir_path, dir_link)
        self.assert_raises_os_error(errno.ENOTDIR, self.os.removedirs, dir_link)

    def test_remove_dirs_with_non_top_symlink_succeeds(self):
        self.check_posix_only()
        dir_path = self.make_path('dir')
        dir_link = self.make_path('dir_link')
        self.create_dir(dir_path)
        self.os.symlink(dir_path, dir_link)
        dir_in_dir = self.os.path.join(dir_link, 'dir2')
        self.create_dir(dir_in_dir)
        self.os.removedirs(dir_in_dir)
        self.assertFalse(self.os.path.exists(dir_in_dir))
        # ensure that the symlink is not removed
        self.assertTrue(self.os.path.exists(dir_link))

    def test_mkdir(self):
        """mkdir can create a relative directory."""
        self.skip_real_fs()
        directory = 'xyzzy'
        self.assertFalse(self.filesystem.exists(directory))
        self.os.mkdir(directory)
        self.assertTrue(self.filesystem.exists('/%s' % directory))
        self.os.chdir(directory)
        self.os.mkdir(directory)
        self.assertTrue(
            self.filesystem.exists('/%s/%s' % (directory, directory)))
        self.os.chdir(directory)
        self.os.mkdir('../abccb')
        self.assertTrue(self.os.path.exists('/%s/abccb' % directory))

    def test_mkdir_with_trailing_slash(self):
        """mkdir can create a directory named with a trailing slash."""
        directory = self.make_path('foo')
        self.assertFalse(self.os.path.exists(directory))
        self.os.mkdir(directory)
        self.assertTrue(self.os.path.exists(directory))
        self.assertTrue(self.os.path.exists(self.make_path('foo')))

    def test_mkdir_raises_if_empty_directory_name(self):
        """mkdir raises exeption if creating directory named ''."""
        directory = ''
        self.assert_raises_os_error(errno.ENOENT, self.os.mkdir, directory)

    def test_mkdir_raises_if_no_parent(self):
        """mkdir raises exception if parent directory does not exist."""
        parent = 'xyzzy'
        directory = '%s/foo' % (parent,)
        self.assertFalse(self.os.path.exists(parent))
        self.assert_raises_os_error(errno.ENOENT, self.os.mkdir, directory)

    def test_mkdir_raises_on_symlink_in_posix(self):
        self.check_posix_only()
        base_path = self.make_path('foo', 'bar')
        link_path = self.os.path.join(base_path, 'link_to_dir')
        dir_path = self.os.path.join(base_path, 'dir')
        self.create_dir(dir_path)
        self.os.symlink(dir_path, link_path)
        self.assert_raises_os_error(errno.ENOTDIR, self.os.rmdir, link_path)

    def test_mkdir_removes_symlink_in_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        base_path = self.make_path('foo', 'bar')
        link_path = self.os.path.join(base_path, 'link_to_dir')
        dir_path = self.os.path.join(base_path, 'dir')
        self.create_dir(dir_path)
        self.os.symlink(dir_path, link_path)
        self.os.rmdir(link_path)
        self.assertFalse(self.os.path.exists(link_path))
        self.assertTrue(self.os.path.exists(dir_path))

    def test_mkdir_raises_if_directory_exists(self):
        """mkdir raises exception if directory already exists."""
        directory = self.make_path('xyzzy')
        self.create_dir(directory)
        self.assertTrue(self.os.path.exists(directory))
        self.assert_raises_os_error(errno.EEXIST, self.os.mkdir, directory)

    def test_mkdir_raises_if_file_exists(self):
        """mkdir raises exception if name already exists as a file."""
        directory = self.make_path('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.create_file(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.assert_raises_os_error(errno.EEXIST, self.os.mkdir, file_path)

    def check_mkdir_raises_if_parent_is_file(self, error_type):
        """mkdir raises exception if name already exists as a file."""
        directory = self.make_path('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.create_file(file_path)
        self.assert_raises_os_error(error_type, self.os.mkdir,
                                    self.os.path.join(file_path, 'ff'))

    def test_mkdir_raises_if_parent_is_file_posix(self):
        self.check_posix_only()
        self.check_mkdir_raises_if_parent_is_file(errno.ENOTDIR)

    def test_mkdir_raises_if_parent_is_file_windows(self):
        self.check_windows_only()
        self.check_mkdir_raises_if_parent_is_file(errno.ENOENT)

    def test_mkdir_raises_with_slash_dot_posix(self):
        """mkdir raises exception if mkdir foo/. (trailing /.)."""
        self.check_posix_only()
        self.assert_raises_os_error(errno.EEXIST,
                                    self.os.mkdir, self.os.sep + '.')
        directory = self.make_path('xyzzy', '.')
        self.assert_raises_os_error(errno.ENOENT, self.os.mkdir, directory)
        self.create_dir(self.make_path('xyzzy'))
        self.assert_raises_os_error(errno.EEXIST, self.os.mkdir, directory)

    def test_mkdir_raises_with_slash_dot_windows(self):
        """mkdir raises exception if mkdir foo/. (trailing /.)."""
        self.check_windows_only()
        self.assert_raises_os_error(errno.EACCES,
                                    self.os.mkdir, self.os.sep + '.')
        directory = self.make_path('xyzzy', '.')
        self.os.mkdir(directory)
        self.create_dir(self.make_path('xyzzy'))
        self.assert_raises_os_error(errno.EEXIST, self.os.mkdir, directory)

    def test_mkdir_raises_with_double_dots_posix(self):
        """mkdir raises exception if mkdir foo/foo2/../foo3."""
        self.check_posix_only()
        self.assert_raises_os_error(errno.EEXIST,
                                    self.os.mkdir, self.os.sep + '..')
        directory = self.make_path('xyzzy', 'dir1', 'dir2', '..', '..', 'dir3')
        self.assert_raises_os_error(errno.ENOENT, self.os.mkdir, directory)
        self.create_dir(self.make_path('xyzzy'))
        self.assert_raises_os_error(errno.ENOENT, self.os.mkdir, directory)
        self.create_dir(self.make_path('xyzzy', 'dir1'))
        self.assert_raises_os_error(errno.ENOENT, self.os.mkdir, directory)
        self.create_dir(self.make_path('xyzzy', 'dir1', 'dir2'))
        self.os.mkdir(directory)
        self.assertTrue(self.os.path.exists(directory))
        directory = self.make_path('xyzzy', 'dir1', '..')
        self.assert_raises_os_error(errno.EEXIST, self.os.mkdir, directory)

    def test_mkdir_raises_with_double_dots_windows(self):
        """mkdir raises exception if mkdir foo/foo2/../foo3."""
        self.check_windows_only()
        self.assert_raises_os_error(errno.EACCES,
                                    self.os.mkdir, self.os.sep + '..')
        directory = self.make_path(
            'xyzzy', 'dir1', 'dir2', '..', '..', 'dir3')
        self.assert_raises_os_error(errno.ENOENT, self.os.mkdir, directory)
        self.create_dir(self.make_path('xyzzy'))
        self.os.mkdir(directory)
        self.assertTrue(self.os.path.exists(directory))
        directory = self.make_path('xyzzy', 'dir1', '..')
        self.assert_raises_os_error(errno.EEXIST, self.os.mkdir, directory)

    def test_mkdir_raises_if_parent_is_read_only(self):
        """mkdir raises exception if parent is read only."""
        self.check_posix_only()
        directory = self.make_path('a')
        self.os.mkdir(directory)

        # Change directory permissions to be read only.
        self.os.chmod(directory, 0o400)

        directory = self.make_path('a', 'b')
        self.assert_raises_os_error(errno.EACCES, self.os.mkdir, directory)

    def test_mkdir_with_with_symlink_parent(self):
        self.check_posix_only()
        dir_path = self.make_path('foo', 'bar')
        self.create_dir(dir_path)
        link_path = self.make_path('foo', 'link')
        self.os.symlink(dir_path, link_path)
        new_dir = self.os.path.join(link_path, 'new_dir')
        self.os.mkdir(new_dir)
        self.assertTrue(self.os.path.exists(new_dir))

    def test_makedirs(self):
        """makedirs can create a directory even if parent does not exist."""
        parent = self.make_path('xyzzy')
        directory = self.os.path.join(parent, 'foo')
        self.assertFalse(self.os.path.exists(parent))
        self.os.makedirs(directory)
        self.assertTrue(self.os.path.exists(directory))

    def check_makedirs_raises_if_parent_is_file(self, error_type):
        """makedirs raises exception if a parent component exists as a file."""
        file_path = self.make_path('xyzzy')
        directory = self.os.path.join(file_path, 'plugh')
        self.create_file(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.assert_raises_os_error(error_type, self.os.makedirs, directory)

    def test_makedirs_raises_if_parent_is_file_posix(self):
        self.check_posix_only()
        self.check_makedirs_raises_if_parent_is_file(errno.ENOTDIR)

    def test_makedirs_raises_if_parent_is_file_windows(self):
        self.check_windows_only()
        self.check_makedirs_raises_if_parent_is_file(errno.ENOENT)

    def test_makedirs_raises_if_parent_is_broken_link(self):
        self.check_posix_only()
        link_path = self.make_path('broken_link')
        self.os.symlink(self.make_path('bogus'), link_path)
        self.assert_raises_os_error(errno.ENOENT, self.os.makedirs,
                                    self.os.path.join(link_path, 'newdir'))

    def test_makedirs_raises_if_parent_is_looping_link(self):
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('link')
        link_target = self.os.path.join(link_path, 'link')
        self.os.symlink(link_target, link_path)
        self.assert_raises_os_error(errno.EEXIST, self.os.makedirs, link_path)

    def test_makedirs_if_parent_is_symlink(self):
        self.check_posix_only()
        base_dir = self.make_path('foo', 'bar')
        self.create_dir(base_dir)
        link_dir = self.os.path.join(base_dir, 'linked')
        self.os.symlink(base_dir, link_dir)
        new_dir = self.os.path.join(link_dir, 'f')
        self.os.makedirs(new_dir)
        self.assertTrue(self.os.path.exists(new_dir))

    def test_makedirs_raises_if_access_denied(self):
        """makedirs raises exception if access denied."""
        self.check_posix_only()
        directory = self.make_path('a')
        self.os.mkdir(directory)

        # Change directory permissions to be read only.
        self.os.chmod(directory, 0o400)

        directory = self.make_path('a', 'b')
        self.assertRaises(Exception, self.os.makedirs, directory)

    @unittest.skipIf(sys.version_info < (3, 2),
                     'os.makedirs(exist_ok) argument new in version 3.2')
    def test_makedirs_exist_ok(self):
        """makedirs uses the exist_ok argument"""
        directory = self.make_path('xyzzy', 'foo')
        self.create_dir(directory)
        self.assertTrue(self.os.path.exists(directory))

        self.assert_raises_os_error(errno.EEXIST, self.os.makedirs, directory)
        self.os.makedirs(directory, exist_ok=True)
        self.assertTrue(self.os.path.exists(directory))

    # test fsync and fdatasync
    def test_fsync_raises_on_non_int(self):
        self.assertRaises(TypeError, self.os.fsync, "zero")

    def test_fdatasync_raises_on_non_int(self):
        self.check_linux_only()
        self.assertRaises(TypeError, self.os.fdatasync, "zero")

    def test_fsync_raises_on_invalid_fd(self):
        self.assert_raises_os_error(errno.EBADF, self.os.fsync, 100)

    def test_fdatasync_raises_on_invalid_fd(self):
        # No open files yet
        self.check_linux_only()
        self.assert_raises_os_error(errno.EINVAL, self.os.fdatasync, 0)
        self.assert_raises_os_error(errno.EBADF, self.os.fdatasync, 100)

    def test_fsync_pass_posix(self):
        self.check_posix_only()
        test_file_path = self.make_path('test_file')
        self.create_file(test_file_path, contents='dummy file contents')
        with self.open(test_file_path, 'r') as test_file:
            test_fd = test_file.fileno()
            # Test that this doesn't raise anything
            self.os.fsync(test_fd)
            # And just for sanity, double-check that this still raises
            self.assert_raises_os_error(errno.EBADF, self.os.fsync, test_fd + 1)

    def test_fsync_pass_windows(self):
        self.check_windows_only()
        test_file_path = self.make_path('test_file')
        self.create_file(test_file_path, contents='dummy file contents')
        with self.open(test_file_path, 'r+') as test_file:
            test_fd = test_file.fileno()
            # Test that this doesn't raise anything
            self.os.fsync(test_fd)
            # And just for sanity, double-check that this still raises
            self.assert_raises_os_error(errno.EBADF, self.os.fsync, test_fd + 1)
        with self.open(test_file_path, 'r') as test_file:
            test_fd = test_file.fileno()
            self.assert_raises_os_error(errno.EBADF, self.os.fsync, test_fd)

    def test_fdatasync_pass(self):
        # setup
        self.check_linux_only()
        test_file_path = self.make_path('test_file')
        self.create_file(test_file_path, contents='dummy file contents')
        test_file = self.open(test_file_path, 'r')
        test_fd = test_file.fileno()
        # Test that this doesn't raise anything
        self.os.fdatasync(test_fd)
        # And just for sanity, double-check that this still raises
        self.assert_raises_os_error(errno.EBADF, self.os.fdatasync, test_fd + 1)

    def test_access700(self):
        # set up
        self.check_posix_only()
        path = self.make_path('some_file')
        self.createTestFile(path)
        self.os.chmod(path, 0o700)
        self.assert_mode_equal(0o700, self.os.stat(path).st_mode)
        # actual tests
        self.assertTrue(self.os.access(path, self.os.F_OK))
        self.assertTrue(self.os.access(path, self.os.R_OK))
        self.assertTrue(self.os.access(path, self.os.W_OK))
        self.assertTrue(self.os.access(path, self.os.X_OK))
        self.assertTrue(self.os.access(path, self.rwx))

    def test_access600(self):
        # set up
        self.check_posix_only()
        path = self.make_path('some_file')
        self.createTestFile(path)
        self.os.chmod(path, 0o600)
        self.assert_mode_equal(0o600, self.os.stat(path).st_mode)
        # actual tests
        self.assertTrue(self.os.access(path, self.os.F_OK))
        self.assertTrue(self.os.access(path, self.os.R_OK))
        self.assertTrue(self.os.access(path, self.os.W_OK))
        self.assertFalse(self.os.access(path, self.os.X_OK))
        self.assertFalse(self.os.access(path, self.rwx))
        self.assertTrue(self.os.access(path, self.rw))

    def test_access400(self):
        # set up
        self.check_posix_only()
        path = self.make_path('some_file')
        self.createTestFile(path)
        self.os.chmod(path, 0o400)
        self.assert_mode_equal(0o400, self.os.stat(path).st_mode)
        # actual tests
        self.assertTrue(self.os.access(path, self.os.F_OK))
        self.assertTrue(self.os.access(path, self.os.R_OK))
        self.assertFalse(self.os.access(path, self.os.W_OK))
        self.assertFalse(self.os.access(path, self.os.X_OK))
        self.assertFalse(self.os.access(path, self.rwx))
        self.assertFalse(self.os.access(path, self.rw))

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def test_access_symlink(self):
        self.skip_if_symlink_not_supported()
        self.skip_real_fs()
        path = self.make_path('some_file')
        self.createTestFile(path)
        link_path = self.make_path('link_to_some_file')
        self.create_symlink(link_path, path)
        self.os.chmod(link_path, 0o400)

        # test file
        self.assertTrue(self.os.access(link_path, self.os.F_OK))
        self.assertTrue(self.os.access(link_path, self.os.R_OK))
        self.assertFalse(self.os.access(link_path, self.os.W_OK))
        self.assertFalse(self.os.access(link_path, self.os.X_OK))
        self.assertFalse(self.os.access(link_path, self.rwx))
        self.assertFalse(self.os.access(link_path, self.rw))

        # test link itself
        self.assertTrue(
            self.os.access(link_path, self.os.F_OK, follow_symlinks=False))
        self.assertTrue(
            self.os.access(link_path, self.os.R_OK, follow_symlinks=False))
        self.assertTrue(
            self.os.access(link_path, self.os.W_OK, follow_symlinks=False))
        self.assertTrue(
            self.os.access(link_path, self.os.X_OK, follow_symlinks=False))
        self.assertTrue(
            self.os.access(link_path, self.rwx, follow_symlinks=False))
        self.assertTrue(
            self.os.access(link_path, self.rw, follow_symlinks=False))

    def test_access_non_existent_file(self):
        # set up
        path = self.make_path('non', 'existent', 'file')
        self.assertFalse(self.os.path.exists(path))
        # actual tests
        self.assertFalse(self.os.access(path, self.os.F_OK))
        self.assertFalse(self.os.access(path, self.os.R_OK))
        self.assertFalse(self.os.access(path, self.os.W_OK))
        self.assertFalse(self.os.access(path, self.os.X_OK))
        self.assertFalse(self.os.access(path, self.rwx))
        self.assertFalse(self.os.access(path, self.rw))

    def test_chmod(self):
        # set up
        self.check_posix_only()
        self.skip_real_fs()
        path = self.make_path('some_file')
        self.createTestFile(path)
        # actual tests
        self.os.chmod(path, 0o6543)
        st = self.os.stat(path)
        self.assert_mode_equal(0o6543, st.st_mode)
        self.assertTrue(st.st_mode & stat.S_IFREG)
        self.assertFalse(st.st_mode & stat.S_IFDIR)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'file descriptor as path new in Python 3.3')
    def test_chmod_uses_open_fd_as_path(self):
        self.check_posix_only()
        self.skip_real_fs()
        self.assert_raises_os_error(errno.EBADF, self.os.chmod, 5, 0o6543)
        path = self.make_path('some_file')
        self.createTestFile(path)

        with self.open(path) as f:
            self.os.chmod(f.filedes, 0o6543)
            st = self.os.stat(path)
            self.assert_mode_equal(0o6543, st.st_mode)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def test_chmod_follow_symlink(self):
        self.check_posix_only()
        if self.use_real_fs() and not 'chmod' in os.supports_follow_symlinks:
            raise unittest.SkipTest('follow_symlinks not available')
        path = self.make_path('some_file')
        self.createTestFile(path)
        link_path = self.make_path('link_to_some_file')
        self.create_symlink(link_path, path)
        self.os.chmod(link_path, 0o6543)

        st = self.os.stat(link_path)
        self.assert_mode_equal(0o6543, st.st_mode)
        st = self.os.stat(link_path, follow_symlinks=False)
        self.assert_mode_equal(0o777, st.st_mode)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def test_chmod_no_follow_symlink(self):
        self.check_posix_only()
        if self.use_real_fs() and not 'chmod' in os.supports_follow_symlinks:
            raise unittest.SkipTest('follow_symlinks not available')
        path = self.make_path('some_file')
        self.createTestFile(path)
        link_path = self.make_path('link_to_some_file')
        self.create_symlink(link_path, path)
        self.os.chmod(link_path, 0o6543, follow_symlinks=False)

        st = self.os.stat(link_path)
        self.assert_mode_equal(0o666, st.st_mode)
        st = self.os.stat(link_path, follow_symlinks=False)
        self.assert_mode_equal(0o6543, st.st_mode)

    def test_lchmod(self):
        """lchmod shall behave like chmod with follow_symlinks=True
        since Python 3.3"""
        self.check_posix_only()
        self.skip_real_fs()
        path = self.make_path('some_file')
        self.createTestFile(path)
        link_path = self.make_path('link_to_some_file')
        self.create_symlink(link_path, path)
        self.os.lchmod(link_path, 0o6543)

        st = self.os.stat(link_path)
        self.assert_mode_equal(0o666, st.st_mode)
        st = self.os.lstat(link_path)
        self.assert_mode_equal(0o6543, st.st_mode)

    def test_chmod_dir(self):
        # set up
        self.check_posix_only()
        self.skip_real_fs()
        path = self.make_path('some_dir')
        self.createTestDirectory(path)
        # actual tests
        self.os.chmod(path, 0o1234)
        st = self.os.stat(path)
        self.assert_mode_equal(0o1234, st.st_mode)
        self.assertFalse(st.st_mode & stat.S_IFREG)
        self.assertTrue(st.st_mode & stat.S_IFDIR)

    def test_chmod_non_existent(self):
        # set up
        path = self.make_path('non', 'existent', 'file')
        self.assertFalse(self.os.path.exists(path))
        # actual tests
        try:
            # Use try-catch to check exception attributes.
            self.os.chmod(path, 0o777)
            self.fail('Exception is expected.')  # COV_NF_LINE
        except OSError as os_error:
            self.assertEqual(errno.ENOENT, os_error.errno)
            self.assertEqual(path, os_error.filename)

    def test_chown_existing_file(self):
        # set up
        self.skip_real_fs()
        file_path = self.make_path('some_file')
        self.create_file(file_path)
        # first set it make sure it's set
        self.os.chown(file_path, 100, 101)
        st = self.os.stat(file_path)
        self.assertEqual(st[stat.ST_UID], 100)
        self.assertEqual(st[stat.ST_GID], 101)
        # we can make sure it changed
        self.os.chown(file_path, 200, 201)
        st = self.os.stat(file_path)
        self.assertEqual(st[stat.ST_UID], 200)
        self.assertEqual(st[stat.ST_GID], 201)
        # setting a value to -1 leaves it unchanged
        self.os.chown(file_path, -1, -1)
        st = self.os.stat(file_path)
        self.assertEqual(st[stat.ST_UID], 200)
        self.assertEqual(st[stat.ST_GID], 201)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'file descriptor as path new in Python 3.3')
    def test_chown_uses_open_fd_as_path(self):
        self.check_posix_only()
        self.skip_real_fs()
        self.assert_raises_os_error(errno.EBADF, self.os.chown, 5, 100, 101)
        file_path = self.make_path('foo', 'bar')
        self.create_file(file_path)

        with self.open(file_path) as f:
            self.os.chown(f.filedes, 100, 101)
            st = self.os.stat(file_path)
            self.assertEqual(st[stat.ST_UID], 100)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def test_chown_follow_symlink(self):
        self.skip_real_fs()
        file_path = self.make_path('some_file')
        self.create_file(file_path)
        link_path = self.make_path('link_to_some_file')
        self.create_symlink(link_path, file_path)

        self.os.chown(link_path, 100, 101)
        st = self.os.stat(link_path)
        self.assertEqual(st[stat.ST_UID], 100)
        self.assertEqual(st[stat.ST_GID], 101)
        st = self.os.stat(link_path, follow_symlinks=False)
        self.assertNotEqual(st[stat.ST_UID], 100)
        self.assertNotEqual(st[stat.ST_GID], 101)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def test_chown_no_follow_symlink(self):
        self.skip_real_fs()
        file_path = self.make_path('some_file')
        self.create_file(file_path)
        link_path = self.make_path('link_to_some_file')
        self.create_symlink(link_path, file_path)

        self.os.chown(link_path, 100, 101, follow_symlinks=False)
        st = self.os.stat(link_path)
        self.assertNotEqual(st[stat.ST_UID], 100)
        self.assertNotEqual(st[stat.ST_GID], 101)
        st = self.os.stat(link_path, follow_symlinks=False)
        self.assertEqual(st[stat.ST_UID], 100)
        self.assertEqual(st[stat.ST_GID], 101)

    def test_chown_bad_arguments(self):
        """os.chown() with bad args (Issue #30)"""
        self.check_posix_only()
        file_path = self.make_path('some_file')
        self.create_file(file_path)
        self.assertRaises(TypeError, self.os.chown, file_path, 'username', -1)
        self.assertRaises(TypeError, self.os.chown, file_path, -1, 'groupname')

    def test_chown_nonexisting_file_should_raise_os_error(self):
        self.check_posix_only()
        file_path = self.make_path('some_file')
        self.assertFalse(self.os.path.exists(file_path))
        self.assert_raises_os_error(errno.ENOENT, self.os.chown, file_path, 100,
                                    100)

    def test_classify_directory_contents(self):
        """Directory classification should work correctly."""
        root_directory = self.make_path('foo')
        test_directories = ['bar1', 'baz2']
        test_files = ['baz1', 'bar2', 'baz3']
        self.create_dir(root_directory)
        for directory in test_directories:
            directory = self.os.path.join(root_directory, directory)
            self.create_dir(directory)
        for test_file in test_files:
            test_file = self.os.path.join(root_directory, test_file)
            self.create_file(test_file)

        test_directories.sort()
        test_files.sort()
        generator = self.os.walk(root_directory)
        root, dirs, files = next(generator)
        dirs.sort()
        files.sort()
        self.assertEqual(root_directory, root)
        self.assertEqual(test_directories, dirs)
        self.assertEqual(test_files, files)

    # os.mknod does not work under MacOS due to permission issues
    # so we test it under Linux only
    def test_mk_nod_can_create_a_file(self):
        self.check_linux_only()
        filename = self.make_path('foo')
        self.assertFalse(self.os.path.exists(filename))
        self.os.mknod(filename)
        self.assertTrue(self.os.path.exists(filename))
        self.assertEqual(stat.S_IFREG | 0o600, self.os.stat(filename).st_mode)

    def test_mk_nod_raises_if_empty_file_name(self):
        self.check_linux_only()
        filename = ''
        self.assert_raises_os_error(errno.ENOENT, self.os.mknod, filename)

    def test_mk_nod_raises_if_parent_dir_doesnt_exist(self):
        self.check_linux_only()
        parent = self.make_path('xyzzy')
        filename = self.os.path.join(parent, 'foo')
        self.assertFalse(self.os.path.exists(parent))
        self.assert_raises_os_error(errno.ENOENT, self.os.mknod, filename)

    def test_mk_nod_raises_if_file_exists(self):
        self.check_linux_only()
        filename = self.make_path('tmp', 'foo')
        self.create_file(filename)
        self.assertTrue(self.os.path.exists(filename))
        self.assert_raises_os_error(errno.EEXIST, self.os.mknod, filename)

    def test_mk_nod_raises_if_filename_is_dot(self):
        self.check_linux_only()
        filename = self.make_path('tmp', '.')
        self.assert_raises_os_error(errno.ENOENT, self.os.mknod, filename)

    def test_mk_nod_raises_if_filename_is_double_dot(self):
        self.check_linux_only()
        filename = self.make_path('tmp', '..')
        self.assert_raises_os_error(errno.ENOENT, self.os.mknod, filename)

    def test_mknod_empty_tail_for_existing_file_raises(self):
        self.check_linux_only()
        filename = self.make_path('foo')
        self.create_file(filename)
        self.assertTrue(self.os.path.exists(filename))
        self.assert_raises_os_error(errno.EEXIST, self.os.mknod, filename)

    def test_mknod_empty_tail_for_nonexistent_file_raises(self):
        self.check_linux_only()
        filename = self.make_path('tmp', 'foo')
        self.assert_raises_os_error(errno.ENOENT, self.os.mknod, filename)

    def test_mknod_raises_if_filename_is_empty_string(self):
        self.check_linux_only()
        filename = ''
        self.assert_raises_os_error(errno.ENOENT, self.os.mknod, filename)

    def test_mknod_raises_if_unsupported_options(self):
        self.check_posix_only()
        filename = 'abcde'
        self.assert_raises_os_error(errno.EPERM, self.os.mknod, filename,
                                    stat.S_IFCHR)

    def test_mknod_raises_if_parent_is_not_a_directory(self):
        self.check_linux_only()
        filename1 = self.make_path('foo')
        self.create_file(filename1)
        self.assertTrue(self.os.path.exists(filename1))
        filename2 = self.make_path('foo', 'bar')
        self.assert_raises_os_error(errno.ENOTDIR, self.os.mknod, filename2)

    def test_symlink(self):
        self.skip_if_symlink_not_supported()
        file_path = self.make_path('foo', 'bar', 'baz')
        self.create_dir(self.make_path('foo', 'bar'))
        self.os.symlink('bogus', file_path)
        self.assertTrue(self.os.path.lexists(file_path))
        self.assertFalse(self.os.path.exists(file_path))
        self.create_file(self.make_path('foo', 'bar', 'bogus'))
        self.assertTrue(self.os.path.lexists(file_path))
        self.assertTrue(self.os.path.exists(file_path))

    def test_symlink_on_nonexisting_path_raises(self):
        self.check_posix_only()
        dir_path = self.make_path('bar')
        link_path = self.os.path.join(dir_path, 'bar')
        self.assert_raises_os_error(errno.ENOENT, self.os.symlink, link_path,
                                    link_path)
        self.assert_raises_os_error(errno.ENOENT, self.os.symlink, dir_path,
                                    link_path)

    def test_symlink_with_path_ending_with_sep_in_posix(self):
        self.check_posix_only()
        dirPath = self.make_path('dir')
        self.create_dir(dirPath)
        self.assert_raises_os_error(errno.EEXIST, self.os.symlink,
                                    self.base_path, dirPath + self.os.sep)

        dirPath = self.make_path('bar')
        self.assert_raises_os_error(errno.ENOENT, self.os.symlink,
                                    self.base_path, dirPath + self.os.sep)

    def test_symlink_with_path_ending_with_sep_in_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        dirPath = self.make_path('dir')
        self.create_dir(dirPath)
        self.assert_raises_os_error(errno.EEXIST, self.os.symlink,
                                    self.base_path, dirPath + self.os.sep)

        dirPath = self.make_path('bar')
        # does not raise under Windows
        self.os.symlink(self.base_path, dirPath + self.os.sep)

    # hard link related tests
    def test_link_bogus(self):
        # trying to create a link from a non-existent file should fail
        self.skip_if_symlink_not_supported()
        self.assert_raises_os_error(errno.ENOENT,
                                    self.os.link, '/nonexistent_source',
                                    '/link_dest')

    def test_link_delete(self):
        self.skip_if_symlink_not_supported()

        file1_path = self.make_path('test_file1')
        file2_path = self.make_path('test_file2')
        contents1 = 'abcdef'
        # Create file
        self.create_file(file1_path, contents=contents1)
        # link to second file
        self.os.link(file1_path, file2_path)
        # delete first file
        self.os.unlink(file1_path)
        # assert that second file exists, and its contents are the same
        self.assertTrue(self.os.path.exists(file2_path))
        with self.open(file2_path) as f:
            self.assertEqual(f.read(), contents1)

    def test_link_update(self):
        self.skip_if_symlink_not_supported()

        file1_path = self.make_path('test_file1')
        file2_path = self.make_path('test_file2')
        contents1 = 'abcdef'
        contents2 = 'ghijkl'
        # Create file and link
        self.create_file(file1_path, contents=contents1)
        self.os.link(file1_path, file2_path)
        # assert that the second file contains contents1
        with self.open(file2_path) as f:
            self.assertEqual(f.read(), contents1)
        # update the first file
        with self.open(file1_path, 'w') as f:
            f.write(contents2)
        # assert that second file contains contents2
        with self.open(file2_path) as f:
            self.assertEqual(f.read(), contents2)

    def test_link_non_existent_parent(self):
        self.skip_if_symlink_not_supported()
        file1_path = self.make_path('test_file1')
        breaking_link_path = self.make_path('nonexistent', 'test_file2')
        contents1 = 'abcdef'
        # Create file and link
        self.create_file(file1_path, contents=contents1)

        # trying to create a link under a non-existent directory should fail
        self.assert_raises_os_error(errno.ENOENT,
                                    self.os.link, file1_path, breaking_link_path)

    def test_link_is_existing_file(self):
        self.skip_if_symlink_not_supported()
        file_path = self.make_path('foo', 'bar')
        self.create_file(file_path)
        self.assert_raises_os_error(errno.EEXIST, self.os.link, file_path,
                                    file_path)

    def test_link_target_is_dir_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        dir_path = self.make_path('foo', 'bar')
        link_path = self.os.path.join(dir_path, 'link')
        self.create_dir(dir_path)
        self.assert_raises_os_error(errno.EACCES, self.os.link, dir_path,
                                    link_path)

    def test_link_target_is_dir_posix(self):
        self.check_posix_only()
        dir_path = self.make_path('foo', 'bar')
        link_path = self.os.path.join(dir_path, 'link')
        self.create_dir(dir_path)
        self.assert_raises_os_error(errno.EPERM, self.os.link, dir_path,
                                    link_path)

    def test_link_count1(self):
        """Test that hard link counts are updated correctly."""
        self.skip_if_symlink_not_supported()
        file1_path = self.make_path('test_file1')
        file2_path = self.make_path('test_file2')
        file3_path = self.make_path('test_file3')
        self.create_file(file1_path)
        # initial link count should be one
        self.assertEqual(self.os.stat(file1_path).st_nlink, 1)
        self.os.link(file1_path, file2_path)
        # the count should be incremented for each hard link created
        self.assertEqual(self.os.stat(file1_path).st_nlink, 2)
        self.assertEqual(self.os.stat(file2_path).st_nlink, 2)
        # Check that the counts are all updated together
        self.os.link(file2_path, file3_path)
        self.assertEqual(self.os.stat(file1_path).st_nlink, 3)
        self.assertEqual(self.os.stat(file2_path).st_nlink, 3)
        self.assertEqual(self.os.stat(file3_path).st_nlink, 3)
        # Counts should be decremented when links are removed
        self.os.unlink(file3_path)
        self.assertEqual(self.os.stat(file1_path).st_nlink, 2)
        self.assertEqual(self.os.stat(file2_path).st_nlink, 2)
        # check that it gets decremented correctly again
        self.os.unlink(file1_path)
        self.assertEqual(self.os.stat(file2_path).st_nlink, 1)

    def test_nlink_for_directories(self):
        self.skip_real_fs()
        self.create_dir(self.make_path('foo', 'bar'))
        self.create_file(self.make_path('foo', 'baz'))
        self.assertEqual(2, self.filesystem.get_object(
            self.make_path('foo', 'bar')).st_nlink)
        self.assertEqual(4, self.filesystem.get_object(
            self.make_path('foo')).st_nlink)
        self.create_file(self.make_path('foo', 'baz2'))
        self.assertEqual(5, self.filesystem.get_object(
            self.make_path('foo')).st_nlink)

    def test_umask(self):
        self.check_posix_only()
        umask = os.umask(0o22)
        os.umask(umask)
        self.assertEqual(umask, self.os.umask(0o22))

    def test_mkdir_umask_applied(self):
        """mkdir creates a directory with umask applied."""
        self.check_posix_only()
        self.os.umask(0o22)
        dir1 = self.make_path('dir1')
        self.os.mkdir(dir1)
        self.assert_mode_equal(0o755, self.os.stat(dir1).st_mode)
        self.os.umask(0o67)
        dir2 = self.make_path('dir2')
        self.os.mkdir(dir2)
        self.assert_mode_equal(0o710, self.os.stat(dir2).st_mode)

    def test_makedirs_umask_applied(self):
        """makedirs creates a directories with umask applied."""
        self.check_posix_only()
        self.os.umask(0o22)
        self.os.makedirs(self.make_path('p1', 'dir1'))
        self.assert_mode_equal(0o755, self.os.stat(self.make_path('p1')).st_mode)
        self.assert_mode_equal(0o755,
                               self.os.stat(self.make_path('p1', 'dir1')).st_mode)
        self.os.umask(0o67)
        self.os.makedirs(self.make_path('p2', 'dir2'))
        self.assert_mode_equal(0o710, self.os.stat(self.make_path('p2')).st_mode)
        self.assert_mode_equal(0o710,
                               self.os.stat(self.make_path('p2', 'dir2')).st_mode)

    def test_mknod_umask_applied(self):
        """mkdir creates a device with umask applied."""
        # skipping MacOs due to mknod permission issues
        self.check_linux_only()
        self.os.umask(0o22)
        node1 = self.make_path('nod1')
        self.os.mknod(node1, stat.S_IFREG | 0o666)
        self.assert_mode_equal(0o644, self.os.stat(node1).st_mode)
        self.os.umask(0o27)
        node2 = self.make_path('nod2')
        self.os.mknod(node2, stat.S_IFREG | 0o666)
        self.assert_mode_equal(0o640, self.os.stat(node2).st_mode)

    def test_open_umask_applied(self):
        """open creates a file with umask applied."""
        self.check_posix_only()
        self.os.umask(0o22)
        file1 = self.make_path('file1')
        self.open(file1, 'w').close()
        self.assert_mode_equal(0o644, self.os.stat(file1).st_mode)
        self.os.umask(0o27)
        file2 = self.make_path('file2')
        self.open(file2, 'w').close()
        self.assert_mode_equal(0o640, self.os.stat(file2).st_mode)


class RealOsModuleTest(FakeOsModuleTest):
    def use_real_fs(self):
        return True


class FakeOsModuleTestCaseInsensitiveFS(FakeOsModuleTestBase):
    def setUp(self):
        super(FakeOsModuleTestCaseInsensitiveFS, self).setUp()
        self.check_case_insensitive_fs()
        self.rwx = self.os.R_OK | self.os.W_OK | self.os.X_OK
        self.rw = self.os.R_OK | self.os.W_OK

    def test_chdir_fails_non_directory(self):
        """chdir should raise OSError if the target is not a directory."""
        filename = self.make_path('foo', 'bar')
        self.create_file(filename)
        filename1 = self.make_path('Foo', 'Bar')
        self.assert_raises_os_error(self.not_dir_error(), self.os.chdir, filename1)

    def test_listdir_returns_list(self):
        directory_root = self.make_path('xyzzy')
        self.os.mkdir(directory_root)
        directory = self.os.path.join(directory_root, 'bug')
        self.os.mkdir(directory)
        directory_upper = self.make_path('XYZZY', 'BUG')
        self.create_file(self.make_path(directory, 'foo'))
        self.assertEqual(['foo'], self.os.listdir(directory_upper))

    def test_listdir_on_symlink(self):
        self.skip_if_symlink_not_supported()
        directory = self.make_path('xyzzy')
        files = ['foo', 'bar', 'baz']
        for f in files:
            self.create_file(self.make_path(directory, f))
        self.create_symlink(self.make_path('symlink'), self.make_path('xyzzy'))
        files.sort()
        self.assertEqual(files,
                         sorted(self.os.listdir(self.make_path('SymLink'))))

    def test_fdopen_mode(self):
        self.skip_real_fs()
        file_path1 = self.make_path('some_file1')
        file_path2 = self.make_path('Some_File1')
        file_path3 = self.make_path('SOME_file1')
        self.create_file(file_path1, contents='contents here1')
        self.os.chmod(file_path2, (stat.S_IFREG | 0o666) ^ stat.S_IWRITE)

        fake_file1 = self.open(file_path3, 'r')
        fileno1 = fake_file1.fileno()
        self.os.fdopen(fileno1)
        self.os.fdopen(fileno1, 'r')
        exception = OSError if self.is_python2 else IOError
        self.assertRaises(exception, self.os.fdopen, fileno1, 'w')

    def test_stat(self):
        directory = self.make_path('xyzzy')
        directory1 = self.make_path('XYZZY')
        file_path = self.os.path.join(directory, 'plugh')
        self.create_file(file_path, contents='ABCDE')
        self.assertTrue(stat.S_IFDIR & self.os.stat(directory1)[stat.ST_MODE])
        file_path1 = self.os.path.join(directory1, 'Plugh')
        self.assertTrue(stat.S_IFREG & self.os.stat(file_path1)[stat.ST_MODE])
        self.assertTrue(stat.S_IFREG & self.os.stat(file_path1).st_mode)
        self.assertEqual(5, self.os.stat(file_path1)[stat.ST_SIZE])

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def test_stat_no_follow_symlinks_posix(self):
        """Test that stat with follow_symlinks=False behaves like lstat."""
        self.check_posix_only()
        directory = self.make_path('xyzzy')
        base_name = 'plugh'
        file_contents = 'frobozz'
        # Just make sure we didn't accidentally make our test data meaningless.
        self.assertNotEqual(len(base_name), len(file_contents))
        file_path = self.os.path.join(directory, base_name)
        link_path = self.os.path.join(directory, 'link')
        self.create_file(file_path, contents=file_contents)
        self.create_symlink(link_path, base_name)
        self.assertEqual(len(file_contents),
                         self.os.stat(file_path.upper(), follow_symlinks=False)[
                             stat.ST_SIZE])
        self.assertEqual(len(base_name),
                         self.os.stat(link_path.upper(), follow_symlinks=False)[
                             stat.ST_SIZE])

    def test_lstat_posix(self):
        self.check_posix_only()
        directory = self.make_path('xyzzy')
        base_name = 'plugh'
        file_contents = 'frobozz'
        # Just make sure we didn't accidentally make our test data meaningless.
        self.assertNotEqual(len(base_name), len(file_contents))
        file_path = self.os.path.join(directory, base_name)
        link_path = self.os.path.join(directory, 'link')
        self.create_file(file_path, contents=file_contents)
        self.create_symlink(link_path, base_name)
        self.assertEqual(len(file_contents),
                         self.os.lstat(file_path.upper())[stat.ST_SIZE])
        self.assertEqual(len(base_name),
                         self.os.lstat(link_path.upper())[stat.ST_SIZE])

    def test_readlink(self):
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('foo', 'bar', 'baz')
        target = self.make_path('tarJAY')
        self.create_symlink(link_path, target)
        self.assertEqual(self.os.readlink(link_path.upper()), target)

    def check_readlink_raises_if_path_not_a_link(self):
        file_path = self.make_path('foo', 'bar', 'eleventyone')
        self.create_file(file_path)
        self.assert_raises_os_error(errno.EINVAL,
                                    self.os.readlink, file_path.upper())

    def test_readlink_raises_if_path_not_a_link_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        self.check_readlink_raises_if_path_not_a_link()

    def test_readlink_raises_if_path_not_a_link_posix(self):
        self.check_posix_only()
        self.check_readlink_raises_if_path_not_a_link()

    def check_readlink_raises_if_path_has_file(self, error_subtype):
        self.create_file(self.make_path('a_file'))
        file_path = self.make_path('a_file', 'foo')
        self.assert_raises_os_error(error_subtype,
                                    self.os.readlink, file_path.upper())
        file_path = self.make_path('a_file', 'foo', 'bar')
        self.assert_raises_os_error(error_subtype,
                                    self.os.readlink, file_path.upper())

    def test_readlink_raises_if_path_has_file_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        self.check_readlink_raises_if_path_has_file(errno.ENOENT)

    def test_readlink_raises_if_path_has_file_posix(self):
        self.check_posix_only()
        self.check_readlink_raises_if_path_has_file(errno.ENOTDIR)

    def test_readlink_with_links_in_path(self):
        self.skip_if_symlink_not_supported()
        self.create_symlink(self.make_path('meyer', 'lemon', 'pie'),
                            self.make_path('yum'))
        self.create_symlink(self.make_path('geo', 'metro'),
                            self.make_path('Meyer'))
        self.assertEqual(self.make_path('yum'),
                         self.os.readlink(
                             self.make_path('Geo', 'Metro', 'Lemon', 'Pie')))

    def test_readlink_with_chained_links_in_path(self):
        self.skip_if_symlink_not_supported()
        self.create_symlink(self.make_path(
            'eastern', 'european', 'wolfhounds', 'chase'),
            self.make_path('cats'))
        self.create_symlink(self.make_path('russian'),
                            self.make_path('Eastern', 'European'))
        self.create_symlink(self.make_path('dogs'),
                            self.make_path('Russian', 'Wolfhounds'))
        self.assertEqual(self.make_path('cats'),
                         self.os.readlink(self.make_path('DOGS', 'Chase')))

    def check_remove_dir(self, dir_error):
        directory = self.make_path('xyzzy')
        dir_path = self.os.path.join(directory, 'plugh')
        self.create_dir(dir_path)
        dir_path = dir_path.upper()
        self.assertTrue(self.os.path.exists(dir_path.upper()))
        self.assert_raises_os_error(dir_error, self.os.remove, dir_path)
        self.assertTrue(self.os.path.exists(dir_path))
        self.os.chdir(directory)
        self.assert_raises_os_error(dir_error, self.os.remove, dir_path)
        self.assertTrue(self.os.path.exists(dir_path))
        self.assert_raises_os_error(errno.ENOENT, self.os.remove, '/Plugh')

    def test_remove_dir_mac_os(self):
        self.check_macos_only()
        self.check_remove_dir(errno.EPERM)

    def test_remove_dir_windows(self):
        self.check_windows_only()
        self.check_remove_dir(errno.EACCES)

    def test_remove_file(self):
        directory = self.make_path('zzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.create_file(file_path)
        self.assertTrue(self.os.path.exists(file_path.upper()))
        self.os.remove(file_path.upper())
        self.assertFalse(self.os.path.exists(file_path))

    def test_remove_file_no_directory(self):
        directory = self.make_path('zzy')
        file_name = 'plugh'
        file_path = self.os.path.join(directory, file_name)
        self.create_file(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.os.chdir(directory.upper())
        self.os.remove(file_name.upper())
        self.assertFalse(self.os.path.exists(file_path))

    def test_remove_open_file_fails_under_windows(self):
        self.check_windows_only()
        path = self.make_path('foo', 'bar')
        self.create_file(path)
        with self.open(path, 'r'):
            self.assert_raises_os_error(errno.EACCES,
                                        self.os.remove, path.upper())
        self.assertTrue(self.os.path.exists(path))

    def test_remove_open_file_possible_under_posix(self):
        self.check_posix_only()
        path = self.make_path('foo', 'bar')
        self.create_file(path)
        self.open(path, 'r')
        self.os.remove(path.upper())
        self.assertFalse(self.os.path.exists(path))

    def test_remove_file_relative_path(self):
        self.skip_real_fs()
        original_dir = self.os.getcwd()
        directory = self.make_path('zzy')
        subdirectory = self.os.path.join(directory, 'zzy')
        file_name = 'plugh'
        file_path = self.os.path.join(directory, file_name)
        file_path_relative = self.os.path.join('..', file_name)
        self.create_file(file_path.upper())
        self.assertTrue(self.os.path.exists(file_path))
        self.create_dir(subdirectory)
        self.assertTrue(self.os.path.exists(subdirectory))
        self.os.chdir(subdirectory.upper())
        self.os.remove(file_path_relative.upper())
        self.assertFalse(self.os.path.exists(file_path_relative))
        self.os.chdir(original_dir.upper())
        self.assertFalse(self.os.path.exists(file_path))

    def check_remove_dir_raises_error(self, dir_error):
        directory = self.make_path('zzy')
        self.create_dir(directory)
        self.assert_raises_os_error(dir_error,
                                    self.os.remove, directory.upper())

    def test_remove_dir_raises_error_mac_os(self):
        self.check_macos_only()
        self.check_remove_dir_raises_error(errno.EPERM)

    def test_remove_dir_raises_error_windows(self):
        self.check_windows_only()
        self.check_remove_dir_raises_error(errno.EACCES)

    def test_remove_symlink_to_dir(self):
        self.skip_if_symlink_not_supported()
        directory = self.make_path('zzy')
        link = self.make_path('link_to_dir')
        self.create_dir(directory)
        self.os.symlink(directory, link)
        self.assertTrue(self.os.path.exists(directory))
        self.assertTrue(self.os.path.exists(link))
        self.os.remove(link.upper())
        self.assertTrue(self.os.path.exists(directory))
        self.assertFalse(self.os.path.exists(link))

    def test_rename_dir_to_symlink_posix(self):
        self.check_posix_only()
        link_path = self.make_path('link')
        dir_path = self.make_path('dir')
        link_target = self.os.path.join(dir_path, 'link_target')
        self.create_dir(dir_path)
        self.os.symlink(link_target.upper(), link_path.upper())
        self.assert_raises_os_error(errno.ENOTDIR, self.os.rename, dir_path,
                                    link_path)

    def test_rename_dir_to_symlink_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('link')
        dir_path = self.make_path('dir')
        link_target = self.os.path.join(dir_path, 'link_target')
        self.create_dir(dir_path)
        self.os.symlink(link_target.upper(), link_path.upper())
        self.assert_raises_os_error(errno.EEXIST, self.os.rename, dir_path,
                                    link_path)

    def test_rename_dir_to_existing_dir(self):
        # Regression test for #317
        self.check_posix_only()
        dest_dir_path = self.make_path('Dest')
        new_dest_dir_path = self.make_path('dest')
        self.os.mkdir(dest_dir_path)
        source_dir_path = self.make_path('src')
        self.os.mkdir(source_dir_path)
        self.os.rename(source_dir_path, new_dest_dir_path)
        self.assertEqual(['dest'], self.os.listdir(self.base_path))

    def test_rename_file_to_symlink(self):
        self.check_posix_only()
        link_path = self.make_path('file_link')
        file_path = self.make_path('file')
        self.os.symlink(file_path, link_path)
        self.create_file(file_path)
        self.os.rename(file_path.upper(), link_path)
        self.assertFalse(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.exists(link_path.upper()))
        self.assertTrue(self.os.path.isfile(link_path.upper()))

    def test_rename_symlink_to_symlink(self):
        self.check_posix_only()
        base_path = self.make_path('foo', 'bar')
        self.create_dir(base_path)
        link_path1 = self.os.path.join(base_path, 'link1')
        link_path2 = self.os.path.join(base_path, 'link2')
        self.os.symlink(base_path.upper(), link_path1)
        self.os.symlink(base_path, link_path2)
        self.os.rename(link_path1.upper(), link_path2.upper())
        self.assertFalse(self.os.path.exists(link_path1))
        self.assertTrue(self.os.path.exists(link_path2))

    def test_rename_symlink_to_symlink_for_parent_raises(self):
        self.check_posix_only()
        dir_link = self.make_path('dir_link')
        dir_path = self.make_path('dir')
        dir_in_dir_path = self.os.path.join(dir_link, 'inner_dir')
        self.create_dir(dir_path)
        self.os.symlink(dir_path.upper(), dir_link)
        self.create_dir(dir_in_dir_path)
        self.assert_raises_os_error(errno.EINVAL, self.os.rename, dir_path,
                                    dir_in_dir_path.upper())

    def test_rename_directory_to_linked_dir(self):
        # Regression test for #314
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('link')
        self.os.symlink(self.base_path, link_path)
        link_subdir = self.os.path.join(link_path, 'dir')
        dir_path = self.make_path('Dir')
        self.os.mkdir(dir_path)
        self.os.rename(dir_path, link_subdir)
        self.assertEqual(['dir', 'link'],
                         sorted(self.os.listdir(self.base_path)))

    def test_recursive_rename_raises(self):
        self.check_posix_only()
        base_path = self.make_path('foo', 'bar')
        self.create_dir(base_path)
        new_path = self.os.path.join(base_path, 'new_dir')
        self.assert_raises_os_error(errno.EINVAL, self.os.rename,
                                    base_path.upper(), new_path)

    def test_rename_with_target_parent_file_raises_posix(self):
        self.check_posix_only()
        file_path = self.make_path('foo', 'baz')
        self.create_file(file_path)
        self.assert_raises_os_error(errno.ENOTDIR, self.os.rename, file_path,
                                    file_path.upper() + '/new')

    def test_rename_with_target_parent_file_raises_windows(self):
        self.check_windows_only()
        file_path = self.make_path('foo', 'baz')
        self.create_file(file_path)
        self.assert_raises_os_error(errno.EACCES, self.os.rename, file_path,
                                    self.os.path.join(file_path.upper(), 'new'))

    def test_rename_looping_symlink(self):
        # Regression test for #315
        self.skip_if_symlink_not_supported()
        path_lower = self.make_path('baz')
        path_upper = self.make_path('BAZ')
        self.os.symlink(path_lower, path_upper)
        self.os.rename(path_upper, path_lower)
        self.assertEqual(['baz'], self.os.listdir(self.base_path))

    def test_rename_symlink_to_source(self):
        self.check_posix_only()
        base_path = self.make_path('foo')
        link_path = self.os.path.join(base_path, 'slink')
        file_path = self.os.path.join(base_path, 'file')
        self.create_file(file_path)
        self.os.symlink(file_path, link_path)
        self.os.rename(link_path.upper(), file_path.upper())
        self.assertFalse(self.os.path.exists(file_path))

    def test_rename_symlink_to_dir_raises(self):
        self.check_posix_only()
        base_path = self.make_path('foo', 'bar')
        link_path = self.os.path.join(base_path, 'dir_link')
        dir_path = self.os.path.join(base_path, 'dir')
        self.create_dir(dir_path)
        self.os.symlink(dir_path, link_path.upper())
        self.assert_raises_os_error(errno.EISDIR, self.os.rename, link_path,
                                    dir_path.upper())

    def test_rename_broken_symlink(self):
        self.check_posix_only()
        base_path = self.make_path('foo')
        self.create_dir(base_path)
        link_path = self.os.path.join(base_path, 'slink')
        file_path = self.os.path.join(base_path, 'file')
        self.os.symlink(file_path.upper(), link_path)
        self.os.rename(link_path.upper(), file_path)
        self.assertFalse(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.lexists(file_path))
        self.assertFalse(self.os.path.exists(link_path))

    def test_change_case_in_case_insensitive_file_system(self):
        """Can use `rename()` to change filename case in a case-insensitive
         file system."""
        old_file_path = self.make_path('fileName')
        new_file_path = self.make_path('FileNAME')
        self.create_file(old_file_path, contents='test contents')
        self.assertEqual(['fileName'], self.os.listdir(self.base_path))
        self.os.rename(old_file_path, new_file_path)
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.assertEqual(['FileNAME'], self.os.listdir(self.base_path))

    def test_rename_symlink_with_changed_case(self):
        # Regression test for #313
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('link')
        self.os.symlink(self.base_path, link_path)
        link_path = self.os.path.join(link_path, 'link')
        link_path_upper = self.make_path('link', 'LINK')
        self.os.rename(link_path_upper, link_path)

    def test_rename_directory(self):
        """Can rename a directory to an unused name."""
        for old_path, new_path in [('wxyyw', 'xyzzy'), ('abccb', 'cdeed')]:
            old_path = self.make_path(old_path)
            new_path = self.make_path(new_path)
            self.create_file(self.os.path.join(old_path, 'plugh'),
                             contents='test')
            self.assertTrue(self.os.path.exists(old_path))
            self.assertFalse(self.os.path.exists(new_path))
            self.os.rename(old_path.upper(), new_path.upper())
            self.assertFalse(self.os.path.exists(old_path))
            self.assertTrue(self.os.path.exists(new_path))
            self.check_contents(self.os.path.join(new_path, 'plugh'), 'test')
            if not self.use_real_fs():
                self.assertEqual(3,
                                 self.filesystem.get_object(new_path).st_nlink)

    def check_rename_directory_to_existing_file_raises(self, error_nr):
        dir_path = self.make_path('dir')
        file_path = self.make_path('file')
        self.create_dir(dir_path)
        self.create_file(file_path)
        self.assert_raises_os_error(error_nr, self.os.rename, dir_path,
                                    file_path.upper())

    def test_rename_directory_to_existing_file_raises_posix(self):
        self.check_posix_only()
        self.check_rename_directory_to_existing_file_raises(errno.ENOTDIR)

    def test_rename_directory_to_existing_file_raises_windows(self):
        self.check_windows_only()
        self.check_rename_directory_to_existing_file_raises(errno.EEXIST)

    def test_rename_to_existing_directory_should_raise_under_windows(self):
        """Renaming to an existing directory raises OSError under Windows."""
        self.check_windows_only()
        old_path = self.make_path('foo', 'bar')
        new_path = self.make_path('foo', 'baz')
        self.create_dir(old_path)
        self.create_dir(new_path)
        self.assert_raises_os_error(errno.EEXIST, self.os.rename,
                                    old_path.upper(),
                                    new_path.upper())

    def test_rename_to_a_hardlink_of_same_file_should_do_nothing(self):
        self.skip_real_fs_failure(skip_posix=False)
        self.skip_if_symlink_not_supported()
        file_path = self.make_path('dir', 'file')
        self.create_file(file_path)
        link_path = self.make_path('link')
        self.os.link(file_path.upper(), link_path)
        self.os.rename(file_path, link_path.upper())
        self.assertTrue(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.exists(link_path))

    def test_rename_with_incorrect_source_case(self):
        # Regression test for #308
        base_path = self.make_path('foo')
        path0 = self.os.path.join(base_path, 'bar')
        path1 = self.os.path.join(base_path, 'Bar')
        self.create_dir(path0)
        self.os.rename(path1, path0)
        self.assertTrue(self.os.path.exists(path0))

    def test_rename_symlink_to_other_case_does_nothing_in_mac_os(self):
        # Regression test for #318
        self.check_macos_only()
        path0 = self.make_path("beta")
        self.os.symlink(self.base_path, path0)
        path0 = self.make_path("beta", "Beta")
        path1 = self.make_path("Beta")
        self.os.rename(path0, path1)
        self.assertEqual(['beta'], sorted(self.os.listdir(path0)))

    def test_rename_symlink_to_other_case_works_in_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        path0 = self.make_path("beta")
        self.os.symlink(self.base_path, path0)
        path0 = self.make_path("beta", "Beta")
        path1 = self.make_path("Beta")
        self.os.rename(path0, path1)
        self.assertEqual(['Beta'], sorted(self.os.listdir(path0)))

    def test_stat_with_mixed_case(self):
        # Regression test for #310
        self.skip_if_symlink_not_supported()
        base_path = self.make_path('foo')
        path = self.os.path.join(base_path, 'bar')
        self.create_dir(path)
        path = self.os.path.join(path, 'Bar')
        self.os.symlink(base_path, path)
        path = self.os.path.join(path, 'Bar')
        # used to raise
        self.os.stat(path)

    def test_hardlink_works_with_symlink(self):
        self.check_posix_only()
        base_path = self.make_path('foo')
        self.create_dir(base_path)
        symlink_path = self.os.path.join(base_path, 'slink')
        self.os.symlink(base_path.upper(), symlink_path)
        file_path = self.os.path.join(base_path, 'slink', 'beta')
        self.create_file(file_path)
        link_path = self.os.path.join(base_path, 'Slink', 'gamma')
        self.os.link(file_path, link_path)
        self.assertTrue(self.os.path.exists(link_path))

    @unittest.skipIf(sys.version_info < (3, 3), 'replace is new in Python 3.3')
    def test_replace_existing_directory_should_raise_under_windows(self):
        """Renaming to an existing directory raises OSError under Windows."""
        self.check_windows_only()
        old_path = self.make_path('foo', 'bar')
        new_path = self.make_path('foo', 'baz')
        self.create_dir(old_path)
        self.create_dir(new_path)
        self.assert_raises_os_error(errno.EACCES, self.os.replace, old_path,
                                    new_path.upper())

    def test_rename_to_existing_directory_under_posix(self):
        """Renaming to an existing directory changes the existing directory
        under Posix."""
        self.check_posix_only()
        old_path = self.make_path('foo', 'bar')
        new_path = self.make_path('xyzzy')
        self.create_dir(self.os.path.join(old_path, 'sub'))
        self.create_dir(new_path)
        self.os.rename(old_path.upper(), new_path.upper())
        self.assertTrue(
            self.os.path.exists(self.os.path.join(new_path, 'sub')))
        self.assertFalse(self.os.path.exists(old_path))

    def test_rename_file_to_existing_directory_raises_under_posix(self):
        self.check_posix_only()
        file_path = self.make_path('foo', 'bar', 'baz')
        new_path = self.make_path('xyzzy')
        self.create_file(file_path)
        self.create_dir(new_path)
        self.assert_raises_os_error(errno.EISDIR, self.os.rename,
                                    file_path.upper(),
                                    new_path.upper())

    def test_rename_to_existent_file_posix(self):
        """Can rename a file to a used name under Unix."""
        self.check_posix_only()
        directory = self.make_path('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.create_file(old_file_path, contents='test contents 1')
        self.create_file(new_file_path, contents='test contents 2')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.os.rename(old_file_path.upper(), new_file_path.upper())
        self.assertFalse(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.check_contents(new_file_path, 'test contents 1')

    def test_rename_to_existent_file_windows(self):
        """Renaming a file to a used name raises OSError under Windows."""
        self.check_windows_only()
        directory = self.make_path('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.create_file(old_file_path, contents='test contents 1')
        self.create_file(new_file_path, contents='test contents 2')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.assert_raises_os_error(errno.EEXIST, self.os.rename,
                                    old_file_path.upper(),
                                    new_file_path.upper())

    @unittest.skipIf(sys.version_info < (3, 3), 'replace is new in Python 3.3')
    def test_replace_to_existent_file(self):
        """Replaces an existing file (does not work with `rename()` under
        Windows)."""
        directory = self.make_path('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.create_file(old_file_path, contents='test contents 1')
        self.create_file(new_file_path, contents='test contents 2')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.os.replace(old_file_path.upper(), new_file_path.upper())
        self.assertFalse(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.check_contents(new_file_path, 'test contents 1')

    def test_rename_to_nonexistent_dir(self):
        """Can rename a file to a name in a nonexistent dir."""
        directory = self.make_path('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(
            directory, 'no_such_path', 'plugh_new')
        self.create_file(old_file_path, contents='test contents')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertFalse(self.os.path.exists(new_file_path))
        self.assert_raises_os_error(errno.ENOENT, self.os.rename,
                                    old_file_path.upper(),
                                    new_file_path.upper())
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertFalse(self.os.path.exists(new_file_path))
        self.check_contents(old_file_path, 'test contents')

    def test_rename_case_only_with_symlink_parent(self):
        # Regression test for #319
        self.skip_if_symlink_not_supported()
        self.os.symlink(self.base_path, self.make_path('link'))
        dir_upper = self.make_path('link', 'Alpha')
        self.os.mkdir(dir_upper)
        dir_lower = self.make_path('alpha')
        self.os.rename(dir_upper, dir_lower)
        self.assertEqual(['alpha', 'link'],
                         sorted(self.os.listdir(self.base_path)))

    def test_rename_dir(self):
        """Test a rename of a directory."""
        directory = self.make_path('xyzzy')
        before_dir = self.os.path.join(directory, 'before')
        before_file = self.os.path.join(directory, 'before', 'file')
        after_dir = self.os.path.join(directory, 'after')
        after_file = self.os.path.join(directory, 'after', 'file')
        self.create_dir(before_dir)
        self.create_file(before_file, contents='payload')
        self.assertTrue(self.os.path.exists(before_dir.upper()))
        self.assertTrue(self.os.path.exists(before_file.upper()))
        self.assertFalse(self.os.path.exists(after_dir.upper()))
        self.assertFalse(self.os.path.exists(after_file.upper()))
        self.os.rename(before_dir.upper(), after_dir)
        self.assertFalse(self.os.path.exists(before_dir.upper()))
        self.assertFalse(self.os.path.exists(before_file.upper()))
        self.assertTrue(self.os.path.exists(after_dir.upper()))
        self.assertTrue(self.os.path.exists(after_file.upper()))
        self.check_contents(after_file, 'payload')

    def test_rename_same_filenames(self):
        """Test renaming when old and new names are the same."""
        directory = self.make_path('xyzzy')
        file_contents = 'Spam eggs'
        file_path = self.os.path.join(directory, 'eggs')
        self.create_file(file_path, contents=file_contents)
        self.os.rename(file_path, file_path.upper())
        self.check_contents(file_path, file_contents)

    def test_rmdir(self):
        """Can remove a directory."""
        directory = self.make_path('xyzzy')
        sub_dir = self.make_path('xyzzy', 'abccd')
        other_dir = self.make_path('xyzzy', 'cdeed')
        self.create_dir(directory)
        self.assertTrue(self.os.path.exists(directory))
        self.os.rmdir(directory)
        self.assertFalse(self.os.path.exists(directory))
        self.create_dir(sub_dir)
        self.create_dir(other_dir)
        self.os.chdir(sub_dir)
        self.os.rmdir('../CDEED')
        self.assertFalse(self.os.path.exists(other_dir))
        self.os.chdir('..')
        self.os.rmdir('AbcCd')
        self.assertFalse(self.os.path.exists(sub_dir))

    def test_rmdir_via_symlink(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        base_path = self.make_path('foo', 'bar')
        dir_path = self.os.path.join(base_path, 'alpha')
        self.create_dir(dir_path)
        link_path = self.os.path.join(base_path, 'beta')
        self.os.symlink(base_path, link_path)
        self.os.rmdir(link_path + '/Alpha')
        self.assertFalse(self.os.path.exists(dir_path))

    def test_remove_dirs_with_non_top_symlink_succeeds(self):
        self.check_posix_only()
        dir_path = self.make_path('dir')
        dir_link = self.make_path('dir_link')
        self.create_dir(dir_path)
        self.os.symlink(dir_path, dir_link)
        dir_in_dir = self.os.path.join(dir_link, 'dir2')
        self.create_dir(dir_in_dir)
        self.os.removedirs(dir_in_dir.upper())
        self.assertFalse(self.os.path.exists(dir_in_dir))
        # ensure that the symlink is not removed
        self.assertTrue(self.os.path.exists(dir_link))

    def test_mkdir_raises_on_symlink_in_posix(self):
        self.check_posix_only()
        base_path = self.make_path('foo', 'bar')
        link_path = self.os.path.join(base_path, 'link_to_dir')
        dir_path = self.os.path.join(base_path, 'dir')
        self.create_dir(dir_path)
        self.os.symlink(dir_path.upper(), link_path.upper())
        self.assert_raises_os_error(errno.ENOTDIR, self.os.rmdir, link_path)

    def test_mkdir_removes_symlink_in_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        base_path = self.make_path('foo', 'bar')
        link_path = self.os.path.join(base_path, 'link_to_dir')
        dir_path = self.os.path.join(base_path, 'dir')
        self.create_dir(dir_path)
        self.os.symlink(dir_path.upper(), link_path.upper())
        self.os.rmdir(link_path)
        self.assertFalse(self.os.path.exists(link_path))
        self.assertTrue(self.os.path.exists(dir_path))

    def test_mkdir_raises_if_directory_exists(self):
        """mkdir raises exception if directory already exists."""
        directory = self.make_path('xyzzy')
        self.create_dir(directory)
        self.assertTrue(self.os.path.exists(directory))
        self.assert_raises_os_error(errno.EEXIST,
                                    self.os.mkdir, directory.upper())

    def test_mkdir_raises_if_file_exists(self):
        """mkdir raises exception if name already exists as a file."""
        directory = self.make_path('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.create_file(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.assert_raises_os_error(errno.EEXIST,
                                    self.os.mkdir, file_path.upper())

    def test_mkdir_raises_if_symlink_exists(self):
        # Regression test for #309
        self.skip_if_symlink_not_supported()
        path1 = self.make_path('baz')
        self.os.symlink(path1, path1)
        path2 = self.make_path('Baz')
        self.assert_raises_os_error(errno.EEXIST, self.os.mkdir, path2)

    def check_mkdir_raises_if_parent_is_file(self, error_type):
        """mkdir raises exception if name already exists as a file."""
        directory = self.make_path('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.create_file(file_path)
        self.assert_raises_os_error(error_type, self.os.mkdir,
                                    self.os.path.join(file_path.upper(),
                                                      'ff'))

    def test_mkdir_raises_if_parent_is_file_posix(self):
        self.check_posix_only()
        self.check_mkdir_raises_if_parent_is_file(errno.ENOTDIR)

    def test_mkdir_raises_if_parent_is_file_windows(self):
        self.check_windows_only()
        self.check_mkdir_raises_if_parent_is_file(errno.ENOENT)

    def test_makedirs(self):
        """makedirs can create a directory even if parent does not exist."""
        parent = self.make_path('xyzzy')
        directory = self.os.path.join(parent, 'foo')
        self.assertFalse(self.os.path.exists(parent))
        self.os.makedirs(directory.upper())
        self.assertTrue(self.os.path.exists(directory))

    def check_makedirs_raises_if_parent_is_file(self, error_type):
        """makedirs raises exception if a parent component exists as a file."""
        file_path = self.make_path('xyzzy')
        directory = self.os.path.join(file_path, 'plugh')
        self.create_file(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.assert_raises_os_error(error_type, self.os.makedirs,
                                    directory.upper())

    def test_makedirs_raises_if_parent_is_file_posix(self):
        self.check_posix_only()
        self.check_makedirs_raises_if_parent_is_file(errno.ENOTDIR)

    def test_makedirs_raises_if_parent_is_file_windows(self):
        self.check_windows_only()
        self.check_makedirs_raises_if_parent_is_file(errno.ENOENT)

    def test_makedirs_raises_if_parent_is_broken_link(self):
        self.check_posix_only()
        link_path = self.make_path('broken_link')
        self.os.symlink(self.make_path('bogus'), link_path)
        self.assert_raises_os_error(errno.ENOENT, self.os.makedirs,
                                    self.os.path.join(link_path.upper(),
                                                      'newdir'))

    @unittest.skipIf(sys.version_info < (3, 2),
                     'os.makedirs(exist_ok) argument new in version 3.2')
    def test_makedirs_exist_ok(self):
        """makedirs uses the exist_ok argument"""
        directory = self.make_path('xyzzy', 'foo')
        self.create_dir(directory)
        self.assertTrue(self.os.path.exists(directory))

        self.assert_raises_os_error(errno.EEXIST, self.os.makedirs,
                                    directory.upper())
        self.os.makedirs(directory.upper(), exist_ok=True)
        self.assertTrue(self.os.path.exists(directory))

    # test fsync and fdatasync
    def test_fsync_pass(self):
        test_file_path = self.make_path('test_file')
        self.create_file(test_file_path, contents='dummy file contents')
        test_file = self.open(test_file_path.upper(), 'r+')
        test_fd = test_file.fileno()
        # Test that this doesn't raise anything
        self.os.fsync(test_fd)
        # And just for sanity, double-check that this still raises
        self.assert_raises_os_error(errno.EBADF, self.os.fsync, test_fd + 1)

    def test_chmod(self):
        # set up
        self.check_posix_only()
        self.skip_real_fs()
        path = self.make_path('some_file')
        self.createTestFile(path)
        # actual tests
        self.os.chmod(path.upper(), 0o6543)
        st = self.os.stat(path)
        self.assert_mode_equal(0o6543, st.st_mode)
        self.assertTrue(st.st_mode & stat.S_IFREG)
        self.assertFalse(st.st_mode & stat.S_IFDIR)

    def test_symlink(self):
        self.skip_if_symlink_not_supported()
        file_path = self.make_path('foo', 'bar', 'baz')
        self.create_dir(self.make_path('foo', 'bar'))
        self.os.symlink('bogus', file_path.upper())
        self.assertTrue(self.os.path.lexists(file_path))
        self.assertFalse(self.os.path.exists(file_path))
        self.create_file(self.make_path('Foo', 'Bar', 'Bogus'))
        self.assertTrue(self.os.path.lexists(file_path))
        self.assertTrue(self.os.path.exists(file_path))

    # hard link related tests
    def test_link_delete(self):
        self.skip_if_symlink_not_supported()

        file1_path = self.make_path('test_file1')
        file2_path = self.make_path('test_file2')
        contents1 = 'abcdef'
        # Create file
        self.create_file(file1_path, contents=contents1)
        # link to second file
        self.os.link(file1_path.upper(), file2_path)
        # delete first file
        self.os.unlink(file1_path)
        # assert that second file exists, and its contents are the same
        self.assertTrue(self.os.path.exists(file2_path))
        with self.open(file2_path.upper()) as f:
            self.assertEqual(f.read(), contents1)

    def test_link_is_existing_file(self):
        self.skip_if_symlink_not_supported()
        file_path = self.make_path('foo', 'bar')
        self.create_file(file_path)
        self.assert_raises_os_error(errno.EEXIST, self.os.link,
                                    file_path.upper(), file_path.upper())

    def test_link_is_broken_symlink(self):
        # Regression test for #311
        self.skip_if_symlink_not_supported()
        self.check_case_insensitive_fs()
        file_path = self.make_path('baz')
        self.create_file(file_path)
        path_lower = self.make_path('foo')
        self.os.symlink(path_lower, path_lower)
        path_upper = self.make_path('Foo')
        self.assert_raises_os_error(errno.EEXIST,
                                    self.os.link, file_path, path_upper)

    def test_link_with_changed_case(self):
        # Regression test for #312
        self.skip_if_symlink_not_supported()
        self.check_case_insensitive_fs()
        link_path = self.make_path('link')
        self.os.symlink(self.base_path, link_path)
        link_path = self.os.path.join(link_path, 'Link')
        self.assertTrue(self.os.lstat(link_path))


class RealOsModuleTestCaseInsensitiveFS(FakeOsModuleTestCaseInsensitiveFS):
    def use_real_fs(self):
        return True


class FakeOsModuleTimeTest(FakeOsModuleTestBase):
    def setUp(self):
        super(FakeOsModuleTimeTest, self).setUp()
        self.orig_time = time.time
        self.dummy_time = None
        self.setDummyTime(200)

    def tearDown(self):
        time.time = self.orig_time
        super(FakeOsModuleTimeTest, self).tearDown()

    def setDummyTime(self, start):
        self.dummy_time = _DummyTime(start, 20)
        time.time = self.dummy_time

    def test_chmod_st_ctime(self):
        # set up
        file_path = 'some_file'
        self.filesystem.create_file(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.dummy_time.start()

        st = self.os.stat(file_path)
        self.assertEqual(200, st.st_ctime)
        # tests
        self.os.chmod(file_path, 0o765)
        st = self.os.stat(file_path)
        self.assertEqual(220, st.st_ctime)

    def test_utime_sets_current_time_if_args_is_none(self):
        # set up
        path = self.make_path('some_file')
        self.createTestFile(path)
        self.dummy_time.start()

        st = self.os.stat(path)
        # 200 is the current time established in setUp().
        self.assertEqual(200, st.st_atime)
        self.assertEqual(200, st.st_mtime)
        # actual tests
        self.os.utime(path, None)
        st = self.os.stat(path)
        self.assertEqual(220, st.st_atime)
        self.assertEqual(220, st.st_mtime)

    def test_utime_sets_current_time_if_args_is_none_with_floats(self):
        # set up
        # we set os.stat_float_times() to False, so atime/ctime/mtime
        # are converted as ints (seconds since epoch)
        self.setDummyTime(200.9123)
        path = '/some_file'
        fake_filesystem.FakeOsModule.stat_float_times(False)
        self.createTestFile(path)
        self.dummy_time.start()

        st = self.os.stat(path)
        # 200 is the current time established above (if converted to int).
        self.assertEqual(200, st.st_atime)
        self.assertTrue(isinstance(st.st_atime, int))
        self.assertEqual(200, st.st_mtime)
        self.assertTrue(isinstance(st.st_mtime, int))

        if sys.version_info >= (3, 3):
            self.assertEqual(200912300000, st.st_atime_ns)
            self.assertEqual(200912300000, st.st_mtime_ns)

        self.assertEqual(200, st.st_mtime)
        # actual tests
        self.os.utime(path, None)
        st = self.os.stat(path)
        self.assertEqual(220, st.st_atime)
        self.assertTrue(isinstance(st.st_atime, int))
        self.assertEqual(220, st.st_mtime)
        self.assertTrue(isinstance(st.st_mtime, int))
        if sys.version_info >= (3, 3):
            self.assertEqual(220912300000, st.st_atime_ns)
            self.assertEqual(220912300000, st.st_mtime_ns)

    def test_utime_sets_current_time_if_args_is_none_with_floats_n_sec(self):
        fake_filesystem.FakeOsModule.stat_float_times(False)

        self.setDummyTime(200.9123)
        path = self.make_path('some_file')
        self.createTestFile(path)
        test_file = self.filesystem.get_object(path)

        self.dummy_time.start()
        st = self.os.stat(path)
        self.assertEqual(200, st.st_ctime)
        self.assertEqual(200, test_file.st_ctime)
        self.assertTrue(isinstance(st.st_ctime, int))
        self.assertTrue(isinstance(test_file.st_ctime, int))

        self.os.stat_float_times(True)  # first time float time
        self.assertEqual(200, st.st_ctime)  # st does not change
        self.assertEqual(200.9123, test_file.st_ctime)  # but the file does
        self.assertTrue(isinstance(st.st_ctime, int))
        self.assertTrue(isinstance(test_file.st_ctime, float))

        self.os.stat_float_times(False)  # reverting to int
        self.assertEqual(200, test_file.st_ctime)
        self.assertTrue(isinstance(test_file.st_ctime, int))

        self.assertEqual(200, st.st_ctime)
        self.assertTrue(isinstance(st.st_ctime, int))

        self.os.stat_float_times(True)
        st = self.os.stat(path)
        # 200.9123 not converted to int
        self.assertEqual(200.9123, test_file.st_atime, test_file.st_mtime)
        self.assertEqual(200.9123, st.st_atime, st.st_mtime)
        self.os.utime(path, None)
        st = self.os.stat(path)
        self.assertEqual(220.9123, st.st_atime)
        self.assertEqual(220.9123, st.st_mtime)

    def test_utime_sets_specified_time(self):
        # set up
        path = self.make_path('some_file')
        self.createTestFile(path)
        st = self.os.stat(path)
        # actual tests
        self.os.utime(path, (1, 2))
        st = self.os.stat(path)
        self.assertEqual(1, st.st_atime)
        self.assertEqual(2, st.st_mtime)

    def test_utime_dir(self):
        # set up
        path = '/some_dir'
        self.createTestDirectory(path)
        # actual tests
        self.os.utime(path, (1.0, 2.0))
        st = self.os.stat(path)
        self.assertEqual(1.0, st.st_atime)
        self.assertEqual(2.0, st.st_mtime)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def test_utime_follow_symlinks(self):
        path = self.make_path('some_file')
        self.createTestFile(path)
        link_path = '/link_to_some_file'
        self.filesystem.create_symlink(link_path, path)

        self.os.utime(link_path, (1, 2))
        st = self.os.stat(link_path)
        self.assertEqual(1, st.st_atime)
        self.assertEqual(2, st.st_mtime)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def test_utime_no_follow_symlinks(self):
        path = self.make_path('some_file')
        self.createTestFile(path)
        link_path = '/link_to_some_file'
        self.filesystem.create_symlink(link_path, path)

        self.os.utime(link_path, (1, 2), follow_symlinks=False)
        st = self.os.stat(link_path)
        self.assertNotEqual(1, st.st_atime)
        self.assertNotEqual(2, st.st_mtime)
        st = self.os.stat(link_path, follow_symlinks=False)
        self.assertEqual(1, st.st_atime)
        self.assertEqual(2, st.st_mtime)

    def test_utime_non_existent(self):
        path = '/non/existent/file'
        self.assertFalse(self.os.path.exists(path))
        self.assert_raises_os_error(errno.ENOENT, self.os.utime, path, (1, 2))

    def test_utime_invalid_times_arg_raises(self):
        path = '/some_dir'
        self.createTestDirectory(path)

        # the error message differs with different Python versions
        # we don't expect the same message here
        self.assertRaises(TypeError, self.os.utime, path, (1, 2, 3))
        self.assertRaises(TypeError, self.os.utime, path, (1, 'str'))

    @unittest.skipIf(sys.version_info < (3, 3), 'ns new in Python 3.3')
    def test_utime_sets_specified_time_in_ns(self):
        # set up
        path = self.make_path('some_file')
        self.createTestFile(path)
        self.dummy_time.start()

        st = self.os.stat(path)
        # actual tests
        self.os.utime(path, ns=(200000000, 400000000))
        st = self.os.stat(path)
        self.assertEqual(0.2, st.st_atime)
        self.assertEqual(0.4, st.st_mtime)

    @unittest.skipIf(sys.version_info < (3, 3), 'ns new in Python 3.3')
    def test_utime_incorrect_ns_argument_raises(self):
        file_path = 'some_file'
        self.filesystem.create_file(file_path)

        self.assertRaises(TypeError, self.os.utime, file_path, ns=(200000000))
        self.assertRaises(TypeError, self.os.utime, file_path, ns=('a', 'b'))
        self.assertRaises(ValueError, self.os.utime, file_path, times=(1, 2),
                          ns=(100, 200))

    @unittest.skipIf(sys.version_info < (3, 3),
                     'file descriptor as path new in Python 3.3')
    def test_utime_uses_open_fd_as_path(self):
        if os.utime not in os.supports_fd:
            self.skip_real_fs()
        self.assert_raises_os_error(errno.EBADF, self.os.utime, 5, (1, 2))
        path = self.make_path('some_file')
        self.createTestFile(path)

        with FakeFileOpen(self.filesystem)(path) as f:
            self.os.utime(f.filedes, times=(1, 2))
            st = self.os.stat(path)
            self.assertEqual(1, st.st_atime)
            self.assertEqual(2, st.st_mtime)


class FakeOsModuleLowLevelFileOpTest(FakeOsModuleTestBase):
    """Test low level functions `os.open()`, `os.read()` and `os.write()`."""

    def test_open_read_only(self):
        file_path = self.make_path('file1')
        self.create_file(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_RDONLY)
        self.assertEqual(b'contents', self.os.read(file_des, 8))
        self.assert_raises_os_error(errno.EBADF, self.os.write, file_des, b'test')
        self.os.close(file_des)

    def test_open_read_only_write_zero_bytes_posix(self):
        self.check_posix_only()
        file_path = self.make_path('file1')
        self.create_file(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_RDONLY)
        self.assert_raises_os_error(errno.EBADF, self.os.write, file_des, b'test')
        self.os.close(file_des)

    def test_open_read_only_write_zero_bytes_windows(self):
        # under Windows, writing an empty string to a read only file
        # is not an error
        self.check_windows_only()
        file_path = self.make_path('file1')
        self.create_file(file_path, contents=b'contents')
        file_des = self.os.open(file_path, os.O_RDONLY)
        self.assertEqual(0, self.os.write(file_des, b''))
        self.os.close(file_des)

    def test_open_write_only(self):
        file_path = self.make_path('file1')
        file_obj = self.create_file(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_WRONLY)
        self.assertEqual(4, self.os.write(file_des, b'test'))
        self.check_contents(file_path, b'testents')
        self.os.close(file_des)

    def test_open_write_only_raises_on_read(self):
        file_path = self.make_path('file1')
        self.create_file(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_WRONLY)
        self.assert_raises_os_error(errno.EBADF, self.os.read, file_des, 5)
        self.os.close(file_des)
        file_des = self.os.open(file_path, os.O_WRONLY | os.O_TRUNC)
        self.assert_raises_os_error(errno.EBADF, self.os.read, file_des, 5)
        self.os.close(file_des)
        file_path2 = self.make_path('file2')
        file_des = self.os.open(file_path2, os.O_CREAT | os.O_WRONLY)
        self.assert_raises_os_error(errno.EBADF, self.os.read, file_des, 5)
        self.os.close(file_des)
        file_des = self.os.open(file_path2,
                                os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        self.assert_raises_os_error(errno.EBADF, self.os.read, file_des, 5)
        self.os.close(file_des)

    def test_open_write_only_read_zero_bytes_posix(self):
        self.check_posix_only()
        file_path = self.make_path('file1')
        file_des = self.os.open(file_path, os.O_CREAT | os.O_WRONLY)
        self.assert_raises_os_error(errno.EBADF, self.os.read, file_des, 0)
        self.os.close(file_des)

    def test_open_write_only_read_zero_bytes_windows(self):
        # under Windows, reading 0 bytes from a write only file is not an error
        self.check_windows_only()
        file_path = self.make_path('file1')
        file_des = self.os.open(file_path, os.O_CREAT | os.O_WRONLY)
        self.assertEqual(b'', self.os.read(file_des, 0))
        self.os.close(file_des)

    def test_open_read_write(self):
        file_path = self.make_path('file1')
        self.create_file(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_RDWR)
        self.assertEqual(4, self.os.write(file_des, b'test'))
        self.check_contents(file_path, b'testents')
        self.os.close(file_des)

    def test_open_create_is_read_only(self):
        file_path = self.make_path('file1')
        file_des = self.os.open(file_path, os.O_CREAT)
        self.assertEqual(b'', self.os.read(file_des, 1))
        self.assert_raises_os_error(errno.EBADF, self.os.write, file_des, b'foo')
        self.os.close(file_des)

    def test_open_create_truncate_is_read_only(self):
        file_path = self.make_path('file1')
        file_des = self.os.open(file_path, os.O_CREAT | os.O_TRUNC)
        self.assertEqual(b'', self.os.read(file_des, 1))
        self.assert_raises_os_error(errno.EBADF, self.os.write, file_des, b'foo')
        self.os.close(file_des)

    def test_open_raises_if_does_not_exist(self):
        file_path = self.make_path('file1')
        self.assert_raises_os_error(errno.ENOENT, self.os.open, file_path,
                                    os.O_RDONLY)
        self.assert_raises_os_error(errno.ENOENT, self.os.open, file_path,
                                    os.O_WRONLY)
        self.assert_raises_os_error(errno.ENOENT, self.os.open, file_path,
                                    os.O_RDWR)

    def test_exclusive_open_raises_without_create_mode(self):
        self.skip_real_fs()
        file_path = self.make_path('file1')
        self.assertRaises(NotImplementedError, self.os.open, file_path,
                          os.O_EXCL)
        self.assertRaises(NotImplementedError, self.os.open, file_path,
                          os.O_EXCL | os.O_WRONLY)
        self.assertRaises(NotImplementedError, self.os.open, file_path,
                          os.O_EXCL | os.O_RDWR)
        self.assertRaises(NotImplementedError, self.os.open, file_path,
                          os.O_EXCL | os.O_TRUNC | os.O_APPEND)

    def test_open_raises_if_parent_does_not_exist(self):
        path = self.make_path('alpha', 'alpha')
        self.assert_raises_os_error(errno.ENOENT, self.os.open, path,
                                    os.O_CREAT | os.O_WRONLY | os.O_TRUNC)

    def test_open_truncate(self):
        file_path = self.make_path('file1')
        self.create_file(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_RDWR | os.O_TRUNC)
        self.assertEqual(b'', self.os.read(file_des, 8))
        self.assertEqual(4, self.os.write(file_des, b'test'))
        self.check_contents(file_path, b'test')
        self.os.close(file_des)

    @unittest.skipIf(not TestCase.is_windows,
                     'O_TEMPORARY only present in Windows')
    def test_temp_file(self):
        file_path = self.make_path('file1')
        fd = self.os.open(file_path, os.O_CREAT | os.O_RDWR | os.O_TEMPORARY)
        self.assertTrue(self.os.path.exists(file_path))
        self.os.close(fd)
        self.assertFalse(self.os.path.exists(file_path))

    def test_open_append(self):
        file_path = self.make_path('file1')
        self.create_file(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_WRONLY | os.O_APPEND)
        self.assertEqual(4, self.os.write(file_des, b'test'))
        self.check_contents(file_path, b'contentstest')
        self.os.close(file_des)

    def test_open_create(self):
        file_path = self.make_path('file1')
        file_des = self.os.open(file_path, os.O_RDWR | os.O_CREAT)
        self.assertTrue(self.os.path.exists(file_path))
        self.assertEqual(4, self.os.write(file_des, b'test'))
        self.check_contents(file_path, 'test')
        self.os.close(file_des)

    def test_can_read_after_create_exclusive(self):
        self.check_posix_only()
        path1 = self.make_path('alpha')
        file_des = self.os.open(path1, os.O_CREAT | os.O_EXCL)
        self.assertEqual(b'', self.os.read(file_des, 0))
        self.assert_raises_os_error(errno.EBADF, self.os.write, file_des, b'')
        self.os.close(file_des)

    def test_open_create_mode_posix(self):
        self.check_posix_only()
        file_path = self.make_path('file1')
        file_des = self.os.open(file_path, os.O_WRONLY | os.O_CREAT, 0o700)
        self.assertTrue(self.os.path.exists(file_path))
        self.assert_raises_os_error(errno.EBADF, self.os.read, file_des, 5)
        self.assertEqual(4, self.os.write(file_des, b'test'))
        self.assert_mode_equal(0o700, self.os.stat(file_path).st_mode)
        self.os.close(file_des)

    def test_open_create_mode_windows(self):
        self.check_windows_only()
        file_path = self.make_path('file1')
        file_des = self.os.open(file_path, os.O_WRONLY | os.O_CREAT, 0o700)
        self.assertTrue(self.os.path.exists(file_path))
        self.assert_raises_os_error(errno.EBADF, self.os.read, file_des, 5)
        self.assertEqual(4, self.os.write(file_des, b'test'))
        self.assert_mode_equal(0o666, self.os.stat(file_path).st_mode)
        self.os.close(file_des)

    def testOpenCreateMode444Windows(self):
        self.check_windows_only()
        file_path = self.make_path('file1')
        file_des = self.os.open(file_path, os.O_WRONLY | os.O_CREAT, 0o442)
        self.assert_mode_equal(0o444, self.os.stat(file_path).st_mode)
        self.os.close(file_des)

    def testOpenCreateMode666Windows(self):
        self.check_windows_only()
        file_path = self.make_path('file1')
        file_des = self.os.open(file_path, os.O_WRONLY | os.O_CREAT, 0o224)
        self.assert_mode_equal(0o666, self.os.stat(file_path).st_mode)
        self.os.close(file_des)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Exclusive mode new in Python 3.3')
    def test_open_exclusive(self):
        file_path = self.make_path('file1')
        file_des = self.os.open(file_path, os.O_RDWR | os.O_EXCL | os.O_CREAT)
        self.assertTrue(self.os.path.exists(file_path))
        self.os.close(file_des)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Exclusive mode new in Python 3.3')
    def test_open_exclusive_raises_if_file_exists(self):
        file_path = self.make_path('file1')
        self.create_file(file_path, contents=b'contents')
        self.assert_raises_io_error(errno.EEXIST, self.os.open, file_path,
                                    os.O_RDWR | os.O_EXCL | os.O_CREAT)
        self.assert_raises_io_error(errno.EEXIST, self.os.open, file_path,
                                    os.O_RDWR | os.O_EXCL | os.O_CREAT)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Exclusive mode new in Python 3.3')
    def test_open_exclusive_raises_if_symlink_exists_in_posix(self):
        self.check_posix_only()
        link_path = self.make_path('link')
        link_target = self.make_path('link_target')
        self.os.symlink(link_target, link_path)
        self.assert_raises_os_error(
            errno.EEXIST, self.os.open, link_path,
            os.O_CREAT | os.O_WRONLY | os.O_TRUNC | os.O_EXCL)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Exclusive mode new in Python 3.3')
    def test_open_exclusive_if_symlink_exists_works_in_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('link')
        link_target = self.make_path('link_target')
        self.os.symlink(link_target, link_path)
        fd = self.os.open(link_path,
                          os.O_CREAT | os.O_WRONLY | os.O_TRUNC | os.O_EXCL)
        self.os.close(fd)

    def test_open_directory_raises_under_windows(self):
        self.check_windows_only()
        dir_path = self.make_path('dir')
        self.create_dir(dir_path)
        self.assert_raises_os_error(errno.EACCES, self.os.open, dir_path,
                                    os.O_RDONLY)
        self.assert_raises_os_error(errno.EACCES, self.os.open, dir_path,
                                    os.O_WRONLY)
        self.assert_raises_os_error(errno.EACCES, self.os.open, dir_path,
                                    os.O_RDWR)

    def test_open_directory_for_writing_raises_under_posix(self):
        self.check_posix_only()
        dir_path = self.make_path('dir')
        self.create_dir(dir_path)
        self.assert_raises_os_error(errno.EISDIR, self.os.open, dir_path,
                                    os.O_WRONLY)
        self.assert_raises_os_error(errno.EISDIR, self.os.open, dir_path,
                                    os.O_RDWR)

    def test_open_directory_read_only_under_posix(self):
        self.check_posix_only()
        self.skip_real_fs()
        dir_path = self.make_path('dir')
        self.create_dir(dir_path)
        file_des = self.os.open(dir_path, os.O_RDONLY)
        self.assertEqual(3, file_des)

    def test_opening_existing_directory_in_creation_mode(self):
        self.check_linux_only()
        dir_path = self.make_path("alpha")
        self.os.mkdir(dir_path)
        self.assert_raises_os_error(errno.EISDIR,
                                    self.os.open, dir_path, os.O_CREAT)

    def test_writing_to_existing_directory(self):
        self.check_macos_only()
        dir_path = self.make_path("alpha")
        self.os.mkdir(dir_path)
        fd = self.os.open(dir_path, os.O_CREAT)
        self.assert_raises_os_error(errno.EBADF, self.os.write, fd, b'')

    def test_opening_existing_directory_in_write_mode(self):
        self.check_posix_only()
        dir_path = self.make_path("alpha")
        self.os.mkdir(dir_path)
        self.assert_raises_os_error(errno.EISDIR,
                                    self.os.open, dir_path, os.O_WRONLY)

    def test_open_mode_posix(self):
        self.check_posix_only()
        self.skip_real_fs()
        file_path = self.make_path('baz')
        file_des = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        stat0 = self.os.fstat(file_des)
        # not a really good test as this replicates the code,
        # but we don't know the umask at the test system
        self.assertEqual(0o100777 & ~self.os._umask(), stat0.st_mode)
        self.os.close(file_des)

    def test_open_mode_windows(self):
        self.check_windows_only()
        file_path = self.make_path('baz')
        file_des = self.os.open(file_path,
                                os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        stat0 = self.os.fstat(file_des)
        self.assertEqual(0o100666, stat0.st_mode)
        self.os.close(file_des)

    def test_write_read(self):
        file_path = self.make_path('file1')
        self.create_file(file_path, contents=b'orig contents')
        new_contents = b'1234567890abcdef'

        with self.open(file_path, 'wb') as fh:
            fileno = fh.fileno()
            self.assertEqual(len(new_contents),
                             self.os.write(fileno, new_contents))
            self.check_contents(file_path, new_contents)

        with self.open(file_path, 'rb') as fh:
            fileno = fh.fileno()
            self.assertEqual(b'', self.os.read(fileno, 0))
            self.assertEqual(new_contents[0:2], self.os.read(fileno, 2))
            self.assertEqual(new_contents[2:10], self.os.read(fileno, 8))
            self.assertEqual(new_contents[10:], self.os.read(fileno, 100))
            self.assertEqual(b'', self.os.read(fileno, 10))

        self.assert_raises_os_error(errno.EBADF, self.os.write, fileno,
                                    new_contents)
        self.assert_raises_os_error(errno.EBADF, self.os.read, fileno, 10)

    def test_write_from_different_f_ds(self):
        # Regression test for #211
        file_path = self.make_path('baz')
        fd0 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        fd1 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        self.os.write(fd0, b'aaaa')
        self.os.write(fd1, b'bb')
        self.assertEqual(4, self.os.path.getsize(file_path))
        self.check_contents(file_path, b'bbaa')
        self.os.close(fd1)
        self.os.close(fd0)

    def test_write_from_different_f_ds_with_append(self):
        # Regression test for #268
        file_path = self.make_path('baz')
        fd0 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        fd1 = self.os.open(file_path, os.O_WRONLY | os.O_APPEND)
        self.os.write(fd0, b'aaa')
        self.os.write(fd1, b'bbb')
        self.assertEqual(6, self.os.path.getsize(file_path))
        self.check_contents(file_path, b'aaabbb')
        self.os.close(fd1)
        self.os.close(fd0)

    def test_read_only_read_after_write(self):
        # Regression test for #269
        self.check_posix_only()
        file_path = self.make_path('foo', 'bar', 'baz')
        self.create_file(file_path, contents=b'test')
        fd0 = self.os.open(file_path, os.O_CREAT)
        fd1 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        self.assertEqual(b'', self.os.read(fd0, 0))
        self.os.close(fd1)
        self.os.close(fd0)

    def test_read_after_closing_write_descriptor(self):
        # Regression test for #271
        file_path = self.make_path('baz')
        fd0 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        fd1 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        fd2 = self.os.open(file_path, os.O_CREAT)
        self.os.write(fd1, b'abc')
        self.os.close(fd0)
        self.assertEqual(b'abc', self.os.read(fd2, 3))
        self.os.close(fd2)
        self.os.close(fd1)

    def test_writing_behind_end_of_file(self):
        # Regression test for #273
        file_path = self.make_path('baz')
        fd1 = self.os.open(file_path, os.O_CREAT)
        fd2 = self.os.open(file_path, os.O_RDWR)
        self.os.write(fd2, b'm')
        fd3 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        self.assertEqual(b'', self.os.read(fd2, 1))
        self.os.write(fd2, b'm')
        self.assertEqual(b'\x00m', self.os.read(fd1, 2))
        self.os.close(fd1)
        self.os.close(fd2)
        self.os.close(fd3)


class RealOsModuleLowLevelFileOpTest(FakeOsModuleLowLevelFileOpTest):
    def use_real_fs(self):
        return True


class FakeOsModuleWalkTest(FakeOsModuleTestBase):
    def assertWalkResults(self, expected, top, topdown=True,
                          followlinks=False):
        # as the result of walk is unsorted, we have to check against sorted results
        result = [step for step in self.os.walk(
            top, topdown=topdown, followlinks=followlinks)]
        result = sorted(result, key=lambda lst: lst[0])
        expected = sorted(expected, key=lambda lst: lst[0])
        self.assertEqual(len(expected), len(result))
        for entry, expected_entry in zip(result, expected):
            self.assertEqual(expected_entry[0], entry[0])
            self.assertEqual(expected_entry[1], sorted(entry[1]))
            self.assertEqual(expected_entry[2], sorted(entry[2]))

    def ResetErrno(self):
        """Reset the last seen errno."""
        self.last_errno = False

    def StoreErrno(self, os_error):
        """Store the last errno we saw."""
        self.last_errno = os_error.errno

    def GetErrno(self):
        """Return the last errno we saw."""
        return self.last_errno

    def test_walk_top_down(self):
        """Walk down ordering is correct."""
        base_dir = self.make_path('foo')
        self.create_file(self.os.path.join(base_dir, '1.txt'))
        self.create_file(self.os.path.join(base_dir, 'bar1', '2.txt'))
        self.create_file(self.os.path.join(base_dir, 'bar1', 'baz', '3.txt'))
        self.create_file(self.os.path.join(base_dir, 'bar2', '4.txt'))
        expected = [
            (base_dir, ['bar1', 'bar2'], ['1.txt']),
            (self.os.path.join(base_dir, 'bar1'), ['baz'], ['2.txt']),
            (self.os.path.join(base_dir, 'bar1', 'baz'), [], ['3.txt']),
            (self.os.path.join(base_dir, 'bar2'), [], ['4.txt']),
        ]
        self.assertWalkResults(expected, base_dir)

    def test_walk_bottom_up(self):
        """Walk up ordering is correct."""
        base_dir = self.make_path('foo')
        self.create_file(self.os.path.join(base_dir, 'bar1', 'baz', '1.txt'))
        self.create_file(self.os.path.join(base_dir, 'bar1', '2.txt'))
        self.create_file(self.os.path.join(base_dir, 'bar2', '3.txt'))
        self.create_file(self.os.path.join(base_dir, '4.txt'))

        expected = [
            (self.os.path.join(base_dir, 'bar1', 'baz'), [], ['1.txt']),
            (self.os.path.join(base_dir, 'bar1'), ['baz'], ['2.txt']),
            (self.os.path.join(base_dir, 'bar2'), [], ['3.txt']),
            (base_dir, ['bar1', 'bar2'], ['4.txt']),
        ]
        self.assertWalkResults(expected, self.make_path('foo'), topdown=False)

    def test_walk_raises_if_non_existent(self):
        """Raises an exception when attempting to walk
         non-existent directory."""
        directory = self.make_path('foo', 'bar')
        self.assertEqual(False, self.os.path.exists(directory))
        generator = self.os.walk(directory)
        self.assertRaises(StopIteration, next, generator)

    def test_walk_raises_if_not_directory(self):
        """Raises an exception when attempting to walk a non-directory."""
        filename = self.make_path('foo', 'bar')
        self.create_file(filename)
        generator = self.os.walk(filename)
        self.assertRaises(StopIteration, next, generator)

    def test_walk_calls_on_error_if_non_existent(self):
        """Calls onerror with correct errno when walking
        non-existent directory."""
        self.ResetErrno()
        directory = self.make_path('foo', 'bar')
        self.assertEqual(False, self.os.path.exists(directory))
        # Calling os.walk on a non-existent directory should trigger
        # a call to the onerror method.
        # We do not actually care what, if anything, is returned.
        for unused_entry in self.os.walk(directory, onerror=self.StoreErrno):
            pass
        self.assertTrue(self.GetErrno() in (errno.ENOTDIR, errno.ENOENT))

    def test_walk_calls_on_error_if_not_directory(self):
        """Calls onerror with correct errno when walking non-directory."""
        self.ResetErrno()
        filename = self.make_path('foo' 'bar')
        self.create_file(filename)
        self.assertEqual(True, self.os.path.exists(filename))
        # Calling `os.walk` on a file should trigger a call to the
        # `onerror` method.
        # We do not actually care what, if anything, is returned.
        for unused_entry in self.os.walk(filename, onerror=self.StoreErrno):
            pass
        self.assertTrue(self.GetErrno() in (self.not_dir_error(),
                                            errno.EACCES))

    def test_walk_skips_removed_directories(self):
        """Caller can modify list of directories to visit while walking."""
        root = self.make_path('foo')
        visit = 'visit'
        no_visit = 'no_visit'
        self.create_file(self.os.path.join(root, 'bar'))
        self.create_file(self.os.path.join(root, visit, '1.txt'))
        self.create_file(self.os.path.join(root, visit, '2.txt'))
        self.create_file(self.os.path.join(root, no_visit, '3.txt'))
        self.create_file(self.os.path.join(root, no_visit, '4.txt'))

        generator = self.os.walk(self.make_path('foo'))
        root_contents = next(generator)
        root_contents[1].remove(no_visit)

        visited_visit_directory = False

        for root, _dirs, _files in iter(generator):
            self.assertEqual(False, root.endswith(self.os.path.sep + no_visit))
            if root.endswith(self.os.path.sep + visit):
                visited_visit_directory = True

        self.assertEqual(True, visited_visit_directory)

    def test_walk_followsymlink_disabled(self):
        self.check_posix_only()
        base_dir = self.make_path('foo')
        link_dir = self.make_path('linked')
        self.create_file(self.os.path.join(link_dir, 'subfile'))
        self.create_file(self.os.path.join(base_dir, 'bar', 'baz'))
        self.create_file(self.os.path.join(base_dir, 'bar', 'xyzzy', 'plugh'))
        self.create_symlink(self.os.path.join(base_dir, 'created_link'), link_dir)

        expected = [
            (base_dir, ['bar', 'created_link'], []),
            (self.os.path.join(base_dir, 'bar'), ['xyzzy'], ['baz']),
            (self.os.path.join(base_dir, 'bar', 'xyzzy'), [], ['plugh']),
        ]
        self.assertWalkResults(expected, base_dir, followlinks=False)

        expected = [(self.os.path.join(base_dir, 'created_link'),
                     [], ['subfile'])]
        self.assertWalkResults(expected,
                               self.os.path.join(base_dir, 'created_link'),
                               followlinks=False)

    def test_walk_followsymlink_enabled(self):
        self.check_posix_only()
        base_dir = self.make_path('foo')
        link_dir = self.make_path('linked')
        self.create_file(self.os.path.join(link_dir, 'subfile'))
        self.create_file(self.os.path.join(base_dir, 'bar', 'baz'))
        self.create_file(self.os.path.join(base_dir, 'bar', 'xyzzy', 'plugh'))
        self.create_symlink(self.os.path.join(base_dir, 'created_link'),
                            self.os.path.join(link_dir))

        expected = [
            (base_dir, ['bar', 'created_link'], []),
            (self.os.path.join(base_dir, 'bar'), ['xyzzy'], ['baz']),
            (self.os.path.join(base_dir, 'bar', 'xyzzy'), [], ['plugh']),
            (self.os.path.join(base_dir, 'created_link'), [], ['subfile']),
        ]
        self.assertWalkResults(expected, base_dir, followlinks=True)

        expected = [(self.os.path.join(base_dir, 'created_link'),
                     [], ['subfile'])]
        self.assertWalkResults(expected,
                               self.os.path.join(base_dir, 'created_link'),
                               followlinks=True)


class RealOsModuleWalkTest(FakeOsModuleWalkTest):
    def use_real_fs(self):
        return True


@unittest.skipIf(sys.version_info < (3, 3),
                 'dir_fd argument was introduced in Python 3.3')
class FakeOsModuleDirFdTest(FakeOsModuleTestBase):
    def setUp(self):
        super(FakeOsModuleDirFdTest, self).setUp()
        self.os.supports_dir_fd = set()
        self.filesystem.is_windows_fs = False
        self.filesystem.create_dir('/foo/bar')
        self.dir_fd = self.os.open('/foo', os.O_RDONLY)
        self.filesystem.create_file('/foo/baz')

    def test_access(self):
        self.assertRaises(
            NotImplementedError, self.os.access, 'baz', self.os.F_OK,
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.access)
        self.assertTrue(
            self.os.access('baz', self.os.F_OK, dir_fd=self.dir_fd))

    def test_chmod(self):
        self.assertRaises(
            NotImplementedError, self.os.chmod, 'baz', 0o6543,
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.chmod)
        self.os.chmod('baz', 0o6543, dir_fd=self.dir_fd)
        st = self.os.stat('/foo/baz')
        self.assert_mode_equal(0o6543, st.st_mode)

    @unittest.skipIf(not hasattr(os, 'chown'),
                     'chown not on all platforms available')
    def test_chown(self):
        self.assertRaises(
            NotImplementedError, self.os.chown, 'baz', 100, 101,
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.chown)
        self.os.chown('baz', 100, 101, dir_fd=self.dir_fd)
        st = self.os.stat('/foo/baz')
        self.assertEqual(st[stat.ST_UID], 100)
        self.assertEqual(st[stat.ST_GID], 101)

    def test_link(self):
        self.assertRaises(
            NotImplementedError, self.os.link, 'baz', '/bat',
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.link)
        self.os.link('baz', '/bat', dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/bat'))

    def test_symlink(self):
        self.assertRaises(
            NotImplementedError, self.os.symlink, 'baz', '/bat',
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.symlink)
        self.os.symlink('baz', '/bat', dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/bat'))

    def test_readlink(self):
        self.filesystem.create_symlink('/meyer/lemon/pie', '/foo/baz')
        self.filesystem.create_symlink('/geo/metro', '/meyer')
        self.assertRaises(
            NotImplementedError, self.os.readlink, '/geo/metro/lemon/pie',
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.readlink)
        self.assertEqual('/foo/baz', self.os.readlink(
            '/geo/metro/lemon/pie', dir_fd=self.dir_fd))

    def test_stat(self):
        self.assertRaises(
            NotImplementedError, self.os.stat, 'baz', dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.stat)
        st = self.os.stat('baz', dir_fd=self.dir_fd)
        self.assertEqual(st.st_mode, 0o100666)

    def test_lstat(self):
        self.assertRaises(
            NotImplementedError, self.os.lstat, 'baz', dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.lstat)
        st = self.os.lstat('baz', dir_fd=self.dir_fd)
        self.assertEqual(st.st_mode, 0o100666)

    def test_mkdir(self):
        self.assertRaises(
            NotImplementedError, self.os.mkdir, 'newdir', dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.mkdir)
        self.os.mkdir('newdir', dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/foo/newdir'))

    def test_rmdir(self):
        self.assertRaises(
            NotImplementedError, self.os.rmdir, 'bar', dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.rmdir)
        self.os.rmdir('bar', dir_fd=self.dir_fd)
        self.assertFalse(self.os.path.exists('/foo/bar'))

    @unittest.skipIf(not hasattr(os, 'mknod'),
                     'mknod not on all platforms available')
    def test_mknod(self):
        self.assertRaises(
            NotImplementedError, self.os.mknod, 'newdir', dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.mknod)
        self.os.mknod('newdir', dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/foo/newdir'))

    def test_rename(self):
        self.assertRaises(
            NotImplementedError, self.os.rename, 'baz', '/foo/batz',
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.rename)
        self.os.rename('bar', '/foo/batz', dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/foo/batz'))

    def test_remove(self):
        self.assertRaises(
            NotImplementedError, self.os.remove, 'baz', dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.remove)
        self.os.remove('baz', dir_fd=self.dir_fd)
        self.assertFalse(self.os.path.exists('/foo/baz'))

    def test_unlink(self):
        self.assertRaises(
            NotImplementedError, self.os.unlink, 'baz', dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.unlink)
        self.os.unlink('baz', dir_fd=self.dir_fd)
        self.assertFalse(self.os.path.exists('/foo/baz'))

    def test_utime(self):
        self.assertRaises(
            NotImplementedError, self.os.utime, 'baz', (1, 2),
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.utime)
        self.os.utime('baz', (1, 2), dir_fd=self.dir_fd)
        st = self.os.stat('/foo/baz')
        self.assertEqual(1, st.st_atime)
        self.assertEqual(2, st.st_mtime)

    def test_open(self):
        self.assertRaises(
            NotImplementedError, self.os.open, 'baz', os.O_RDONLY,
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.open)
        fd = self.os.open('baz', os.O_RDONLY, dir_fd=self.dir_fd)
        self.assertLess(0, fd)


@unittest.skipIf(sys.version_info < (3, 5) and not has_scandir,
                 'os.scandir was introduced in Python 3.5')
class FakeScandirTest(FakeOsModuleTestBase):
    def setUp(self):
        super(FakeScandirTest, self).setUp()

        self.supports_symlinks = (not self.is_windows or
                                  not self.use_real_fs() and not self.is_python2)

        if has_scandir:
            if self.use_real_fs():
                from scandir import scandir
            else:
                import pyfakefs.fake_scandir
                scandir = lambda p: pyfakefs.fake_scandir.scandir(self.filesystem, p)
        else:
            scandir = self.os.scandir

        directory = self.make_path('xyzzy', 'plugh')
        link_dir = self.make_path('linked', 'plugh')
        self.linked_file_path = self.os.path.join(link_dir, 'file')
        self.linked_dir_path = self.os.path.join(link_dir, 'dir')

        self.create_dir(self.linked_dir_path)
        self.create_file(self.linked_file_path, contents=b'a' * 10)
        self.dir_path = self.os.path.join(directory, 'dir')
        self.create_dir(self.dir_path)
        self.file_path = self.os.path.join(directory, 'file')
        self.create_file(self.file_path, contents=b'b' * 50)
        self.file_link_path = self.os.path.join(directory, 'link_file')
        if self.supports_symlinks:
            self.create_symlink(self.file_link_path, self.linked_file_path)
            self.dir_link_path = self.os.path.join(directory, 'link_dir')
            self.create_symlink(self.dir_link_path, self.linked_dir_path)
        self.dir_entries = [entry for entry in scandir(directory)]
        self.dir_entries = sorted(self.dir_entries,
                                  key=lambda entry: entry.name)

    def test_paths(self):
        sorted_names = ['dir', 'file']
        if self.supports_symlinks:
            sorted_names.extend(['link_dir', 'link_file'])

        self.assertEqual(len(sorted_names), len(self.dir_entries))
        self.assertEqual(sorted_names,
                         [entry.name for entry in self.dir_entries])
        self.assertEqual(self.dir_path, self.dir_entries[0].path)

    def test_isfile(self):
        self.assertFalse(self.dir_entries[0].is_file())
        self.assertTrue(self.dir_entries[1].is_file())
        if self.supports_symlinks:
            self.assertFalse(self.dir_entries[2].is_file())
            self.assertFalse(self.dir_entries[2].is_file(follow_symlinks=False))
            self.assertTrue(self.dir_entries[3].is_file())
            self.assertFalse(self.dir_entries[3].is_file(follow_symlinks=False))

    def test_isdir(self):
        self.assertTrue(self.dir_entries[0].is_dir())
        self.assertFalse(self.dir_entries[1].is_dir())
        if self.supports_symlinks:
            self.assertTrue(self.dir_entries[2].is_dir())
            self.assertFalse(self.dir_entries[2].is_dir(follow_symlinks=False))
            self.assertFalse(self.dir_entries[3].is_dir())
            self.assertFalse(self.dir_entries[3].is_dir(follow_symlinks=False))

    def test_is_link(self):
        if self.supports_symlinks:
            self.assertFalse(self.dir_entries[0].is_symlink())
            self.assertFalse(self.dir_entries[1].is_symlink())
            self.assertTrue(self.dir_entries[2].is_symlink())
            self.assertTrue(self.dir_entries[3].is_symlink())

    def test_inode(self):
        if has_scandir and self.is_windows and self.use_real_fs():
            self.skipTest('inode seems not to work in scandir module under Windows')
        self.assertEqual(self.os.stat(self.dir_path).st_ino,
                         self.dir_entries[0].inode())
        self.assertEqual(self.os.stat(self.file_path).st_ino,
                         self.dir_entries[1].inode())
        if self.supports_symlinks:
            self.assertEqual(self.os.lstat(self.dir_link_path).st_ino,
                             self.dir_entries[2].inode())
            self.assertEqual(self.os.lstat(self.file_link_path).st_ino,
                             self.dir_entries[3].inode())

    def check_stat(self, expected_size):
        self.assertEqual(50, self.dir_entries[1].stat().st_size)
        self.assertEqual(
            self.os.stat(self.dir_path).st_ctime,
            self.dir_entries[0].stat().st_ctime)

        if self.supports_symlinks:
            self.assertEqual(10, self.dir_entries[3].stat().st_size)
            self.assertEqual(expected_size,
                             self.dir_entries[3].stat(
                                 follow_symlinks=False).st_size)
            self.assertEqual(
                self.os.stat(self.linked_dir_path).st_mtime,
                self.dir_entries[2].stat().st_mtime)

    @unittest.skipIf(TestCase.is_windows, 'POSIX specific behavior')
    def test_stat_posix(self):
        self.check_stat(len(self.linked_file_path))

    @unittest.skipIf(not TestCase.is_windows, 'Windows specific behavior')
    def test_stat_windows(self):
        self.check_stat(0)

    def test_index_access_to_stat_times_returns_int(self):
        self.assertEqual(self.os.stat(self.dir_path)[stat.ST_CTIME],
                         int(self.dir_entries[0].stat().st_ctime))
        if self.supports_symlinks:
            self.assertEqual(self.os.stat(self.linked_dir_path)[stat.ST_MTIME],
                             int(self.dir_entries[2].stat().st_mtime))

    def test_stat_ino_dev(self):
        if self.supports_symlinks:
            file_stat = self.os.stat(self.linked_file_path)
            self.assertEqual(file_stat.st_ino, self.dir_entries[3].stat().st_ino)
            self.assertEqual(file_stat.st_dev, self.dir_entries[3].stat().st_dev)


class RealScandirTest(FakeScandirTest):
    def use_real_fs(self):
        return True


class StatPropagationTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.os = fake_filesystem.FakeOsModule(self.filesystem)
        self.open = fake_filesystem.FakeFileOpen(self.filesystem)

    def test_file_size_updated_via_close(self):
        """test that file size gets updated via close()."""
        file_dir = 'xyzzy'
        file_path = 'xyzzy/close'
        content = 'This is a test.'
        self.os.mkdir(file_dir)
        fh = self.open(file_path, 'w')
        self.assertEqual(0, self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual('', self.filesystem.get_object(file_path).contents)
        fh.write(content)
        self.assertEqual(0, self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual('', self.filesystem.get_object(file_path).contents)
        fh.close()
        self.assertEqual(len(content), self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual(content,
                         self.filesystem.get_object(file_path).contents)

    def test_file_size_not_reset_after_close(self):
        file_dir = 'xyzzy'
        file_path = 'xyzzy/close'
        self.os.mkdir(file_dir)
        size = 1234
        # The file has size, but no content. When the file is opened for reading,
        # its size should be preserved.
        self.filesystem.create_file(file_path, st_size=size)
        fh = self.open(file_path, 'r')
        fh.close()
        self.assertEqual(size, self.open(file_path, 'r').size())

    def test_file_size_after_write(self):
        file_path = 'test_file'
        original_content = 'abcdef'
        original_size = len(original_content)
        self.filesystem.create_file(file_path, contents=original_content)
        added_content = 'foo bar'
        expected_size = original_size + len(added_content)
        fh = self.open(file_path, 'a')
        fh.write(added_content)
        self.assertEqual(original_size, fh.size())
        fh.close()
        self.assertEqual(expected_size, self.open(file_path, 'r').size())

    def test_large_file_size_after_write(self):
        file_path = 'test_file'
        original_content = 'abcdef'
        original_size = len(original_content)
        self.filesystem.create_file(file_path, st_size=original_size)
        added_content = 'foo bar'
        fh = self.open(file_path, 'a')
        self.assertRaises(fake_filesystem.FakeLargeFileIoException,
                          lambda: fh.write(added_content))

    def test_file_size_updated_via_flush(self):
        """test that file size gets updated via flush()."""
        file_dir = 'xyzzy'
        file_name = 'flush'
        file_path = self.os.path.join(file_dir, file_name)
        content = 'This might be a test.'
        self.os.mkdir(file_dir)
        fh = self.open(file_path, 'w')
        self.assertEqual(0, self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual('', self.filesystem.get_object(file_path).contents)
        fh.write(content)
        self.assertEqual(0, self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual('', self.filesystem.get_object(file_path).contents)
        fh.flush()
        self.assertEqual(len(content), self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual(content,
                         self.filesystem.get_object(file_path).contents)
        fh.close()
        self.assertEqual(len(content), self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual(content,
                         self.filesystem.get_object(file_path).contents)

    def test_file_size_truncation(self):
        """test that file size gets updated via open()."""
        file_dir = 'xyzzy'
        file_path = 'xyzzy/truncation'
        content = 'AAA content.'

        # pre-create file with content
        self.os.mkdir(file_dir)
        fh = self.open(file_path, 'w')
        fh.write(content)
        fh.close()
        self.assertEqual(len(content), self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual(content,
                         self.filesystem.get_object(file_path).contents)

        # test file truncation
        fh = self.open(file_path, 'w')
        self.assertEqual(0, self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual('', self.filesystem.get_object(file_path).contents)
        fh.close()


class OsPathInjectionRegressionTest(TestCase):
    """Test faking os.path before calling os.walk.

  Found when investigating a problem with
  gws/tools/labrat/rat_utils_unittest, which was faking out os.path
  before calling os.walk.
  """

    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.os_path = os.path
        # The bug was that when os.path gets faked, the FakePathModule doesn't get
        # called in self.os.walk().  FakePathModule now insists that it is created
        # as part of FakeOsModule.
        self.os = fake_filesystem.FakeOsModule(self.filesystem)

    def tearDown(self):
        os.path = self.os_path

    def test_create_top_level_directory(self):
        top_level_dir = '/x'
        self.assertFalse(self.filesystem.exists(top_level_dir))
        self.filesystem.create_dir(top_level_dir)
        self.assertTrue(self.filesystem.exists('/'))
        self.assertTrue(self.filesystem.exists(top_level_dir))
        self.filesystem.create_dir('%s/po' % top_level_dir)
        self.filesystem.create_file('%s/po/control' % top_level_dir)
        self.filesystem.create_file('%s/po/experiment' % top_level_dir)
        self.filesystem.create_dir('%s/gv' % top_level_dir)
        self.filesystem.create_file('%s/gv/control' % top_level_dir)

        expected = [
            ('/', ['x'], []),
            ('/x', ['gv', 'po'], []),
            ('/x/gv', [], ['control']),
            ('/x/po', [], ['control', 'experiment']),
        ]
        # as the result is unsorted, we have to check against sorted results
        result = sorted([step for step in self.os.walk('/')],
                        key=lambda l: l[0])
        self.assertEqual(len(expected), len(result))
        for entry, expected_entry in zip(result, expected):
            self.assertEqual(expected_entry[0], entry[0])
            self.assertEqual(expected_entry[1], sorted(entry[1]))
            self.assertEqual(expected_entry[2], sorted(entry[2]))


class FakePathModuleTest(TestCase):
    def setUp(self):
        self.orig_time = time.time
        time.time = _DummyTime(10, 1)
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='!')
        self.os = fake_filesystem.FakeOsModule(self.filesystem)
        self.path = self.os.path

    def tearDown(self):
        time.time = self.orig_time

    def check_abspath(self, is_windows):
        # the implementation differs in Windows and Posix, so test both
        self.filesystem.is_windows_fs = is_windows
        filename = u'foo'
        abspath = u'!%s' % filename
        self.filesystem.create_file(abspath)
        self.assertEqual(abspath, self.path.abspath(abspath))
        self.assertEqual(abspath, self.path.abspath(filename))
        self.assertEqual(abspath, self.path.abspath(u'..!%s' % filename))

    def test_abspath_windows(self):
        self.check_abspath(is_windows=True)

    def test_abspath_posix(self):
        """abspath should return a consistent representation of a file."""
        self.check_abspath(is_windows=False)

    def check_abspath_bytes(self, is_windows):
        """abspath should return a consistent representation of a file."""
        self.filesystem.is_windows_fs = is_windows
        filename = b'foo'
        abspath = b'!' + filename
        self.filesystem.create_file(abspath)
        self.assertEqual(abspath, self.path.abspath(abspath))
        self.assertEqual(abspath, self.path.abspath(filename))
        self.assertEqual(abspath, self.path.abspath(b'..!' + filename))

    def test_abspath_bytes_windows(self):
        self.check_abspath_bytes(is_windows=True)

    def test_abspath_bytes_posix(self):
        self.check_abspath_bytes(is_windows=False)

    def test_abspath_deals_with_relative_non_root_path(self):
        """abspath should correctly handle relative paths from a non-! directory.

    This test is distinct from the basic functionality test because
    fake_filesystem has historically been based in !.
    """
        filename = '!foo!bar!baz'
        file_components = filename.split(self.path.sep)
        basedir = '!%s' % (file_components[0],)
        self.filesystem.create_file(filename)
        self.os.chdir(basedir)
        self.assertEqual(basedir, self.path.abspath(self.path.curdir))
        self.assertEqual('!', self.path.abspath('..'))
        self.assertEqual(self.path.join(basedir, file_components[1]),
                         self.path.abspath(file_components[1]))

    def test_abs_path_with_drive_component(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.cwd = 'C:!foo'
        self.assertEqual('C:!foo!bar', self.path.abspath('bar'))
        self.assertEqual('C:!foo!bar', self.path.abspath('C:bar'))
        self.assertEqual('C:!foo!bar', self.path.abspath('!foo!bar'))

    def test_isabs_with_drive_component(self):
        self.filesystem.is_windows_fs = False
        self.assertFalse(self.path.isabs('C:!foo'))
        self.assertTrue(self.path.isabs('!'))
        self.filesystem.is_windows_fs = True
        self.assertTrue(self.path.isabs('C:!foo'))
        self.assertTrue(self.path.isabs('!'))

    def test_relpath(self):
        path_foo = '!path!to!foo'
        path_bar = '!path!to!bar'
        path_other = '!some!where!else'
        self.assertRaises(ValueError, self.path.relpath, None)
        self.assertRaises(ValueError, self.path.relpath, '')
        self.assertEqual('path!to!foo', self.path.relpath(path_foo))
        self.assertEqual('..!foo',
                         self.path.relpath(path_foo, path_bar))
        self.assertEqual('..!..!..%s' % path_other,
                         self.path.relpath(path_other, path_bar))
        self.assertEqual('.',
                         self.path.relpath(path_bar, path_bar))

    def test_realpath_vs_abspath(self):
        self.filesystem.is_windows_fs = False
        self.filesystem.create_file('!george!washington!bridge')
        self.filesystem.create_symlink('!first!president', '!george!washington')
        self.assertEqual('!first!president!bridge',
                         self.os.path.abspath('!first!president!bridge'))
        self.assertEqual('!george!washington!bridge',
                         self.os.path.realpath('!first!president!bridge'))
        self.os.chdir('!first!president')
        self.assertEqual('!george!washington!bridge',
                         self.os.path.realpath('bridge'))

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 2),
                     'No Windows support before 3.2')
    def test_samefile(self):
        file_path1 = '!foo!bar!baz'
        file_path2 = '!foo!bar!boo'
        self.filesystem.create_file(file_path1)
        self.filesystem.create_file(file_path2)
        self.assertTrue(self.path.samefile(file_path1, file_path1))
        self.assertFalse(self.path.samefile(file_path1, file_path2))
        self.assertTrue(
            self.path.samefile(file_path1, '!foo!..!foo!bar!..!bar!baz'))

    def test_exists(self):
        file_path = 'foo!bar!baz'
        self.filesystem.create_file(file_path)
        self.assertTrue(self.path.exists(file_path))
        self.assertFalse(self.path.exists('!some!other!bogus!path'))

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def test_lexists(self):
        file_path = 'foo!bar!baz'
        self.filesystem.create_dir('foo!bar')
        self.filesystem.create_symlink(file_path, 'bogus')
        self.assertTrue(self.path.lexists(file_path))
        self.assertFalse(self.path.exists(file_path))
        self.filesystem.create_file('foo!bar!bogus')
        self.assertTrue(self.path.exists(file_path))

    def test_dirname_with_drive(self):
        self.filesystem.is_windows_fs = True
        self.assertEqual(u'c:!foo',
                         self.path.dirname(u'c:!foo!bar'))
        self.assertEqual(b'c:!',
                         self.path.dirname(b'c:!foo'))
        self.assertEqual(u'!foo',
                         self.path.dirname(u'!foo!bar'))
        self.assertEqual(b'!',
                         self.path.dirname(b'!foo'))
        self.assertEqual(u'c:foo',
                         self.path.dirname(u'c:foo!bar'))
        self.assertEqual(b'c:',
                         self.path.dirname(b'c:foo'))
        self.assertEqual(u'foo',
                         self.path.dirname(u'foo!bar'))

    def test_dirname(self):
        dirname = 'foo!bar'
        self.assertEqual(dirname, self.path.dirname('%s!baz' % dirname))

    def test_join_strings(self):
        components = [u'foo', u'bar', u'baz']
        self.assertEqual(u'foo!bar!baz', self.path.join(*components))

    def test_join_bytes(self):
        components = [b'foo', b'bar', b'baz']
        self.assertEqual(b'foo!bar!baz', self.path.join(*components))

    def test_expand_user(self):
        if self.is_windows:
            self.assertEqual(self.path.expanduser('~'),
                             self.os.environ['USERPROFILE'].replace('\\', '!'))
        else:
            self.assertEqual(self.path.expanduser('~'),
                             self.os.environ['HOME'].replace('/', '!'))

    @unittest.skipIf(TestCase.is_windows or TestCase.is_cygwin,
                     'only tested on unix systems')
    def test_expand_root(self):
        if sys.platform == 'darwin':
            roothome = '!var!root'
        else:
            roothome = '!root'
        self.assertEqual(self.path.expanduser('~root'), roothome)

    def test_getsize_path_nonexistent(self):
        file_path = 'foo!bar!baz'
        self.assertRaises(os.error, self.path.getsize, file_path)

    def test_getsize_file_empty(self):
        file_path = 'foo!bar!baz'
        self.filesystem.create_file(file_path)
        self.assertEqual(0, self.path.getsize(file_path))

    def test_getsize_file_non_zero_size(self):
        file_path = 'foo!bar!baz'
        self.filesystem.create_file(file_path, contents='1234567')
        self.assertEqual(7, self.path.getsize(file_path))

    def test_getsize_dir_empty(self):
        # For directories, only require that the size is non-negative.
        dir_path = 'foo!bar'
        self.filesystem.create_dir(dir_path)
        size = self.path.getsize(dir_path)
        self.assertFalse(int(size) < 0,
                         'expected non-negative size; actual: %s' % size)

    def test_getsize_dir_non_zero_size(self):
        # For directories, only require that the size is non-negative.
        dir_path = 'foo!bar'
        self.filesystem.create_file(self.filesystem.joinpaths(dir_path, 'baz'))
        size = self.path.getsize(dir_path)
        self.assertFalse(int(size) < 0,
                         'expected non-negative size; actual: %s' % size)

    def test_isdir(self):
        self.filesystem.create_file('foo!bar')
        self.assertTrue(self.path.isdir('foo'))
        self.assertFalse(self.path.isdir('foo!bar'))
        self.assertFalse(self.path.isdir('it_dont_exist'))

    def test_isdir_with_cwd_change(self):
        self.filesystem.create_file('!foo!bar!baz')
        self.assertTrue(self.path.isdir('!foo'))
        self.assertTrue(self.path.isdir('!foo!bar'))
        self.assertTrue(self.path.isdir('foo'))
        self.assertTrue(self.path.isdir('foo!bar'))
        self.filesystem.cwd = '!foo'
        self.assertTrue(self.path.isdir('!foo'))
        self.assertTrue(self.path.isdir('!foo!bar'))
        self.assertTrue(self.path.isdir('bar'))

    def test_isfile(self):
        self.filesystem.create_file('foo!bar')
        self.assertFalse(self.path.isfile('foo'))
        self.assertTrue(self.path.isfile('foo!bar'))
        self.assertFalse(self.path.isfile('it_dont_exist'))

    def test_get_mtime(self):
        test_file = self.filesystem.create_file('foo!bar1.txt')
        time.time.start()
        self.assertEqual(10, test_file.st_mtime)
        test_file.st_mtime = 24
        self.assertEqual(24, self.path.getmtime('foo!bar1.txt'))

    def test_get_mtime_raises_os_error(self):
        self.assertFalse(self.path.exists('it_dont_exist'))
        self.assert_raises_os_error(errno.ENOENT, self.path.getmtime,
                                    'it_dont_exist')

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def test_islink(self):
        self.filesystem.create_dir('foo')
        self.filesystem.create_file('foo!regular_file')
        self.filesystem.create_symlink('foo!link_to_file', 'regular_file')
        self.assertFalse(self.path.islink('foo'))

        # An object can be both a link and a file or file, according to the
        # comments in Python/Lib/posixpath.py.
        self.assertTrue(self.path.islink('foo!link_to_file'))
        self.assertTrue(self.path.isfile('foo!link_to_file'))

        self.assertTrue(self.path.isfile('foo!regular_file'))
        self.assertFalse(self.path.islink('foo!regular_file'))

        self.assertFalse(self.path.islink('it_dont_exist'))

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def test_is_link_case_sensitive(self):
        # Regression test for #306
        self.filesystem.is_case_sensitive = False
        self.filesystem.create_dir('foo')
        self.filesystem.create_symlink('foo!bar', 'foo')
        self.assertTrue(self.path.islink('foo!Bar'))

    def test_ismount(self):
        self.assertFalse(self.path.ismount(''))
        self.assertTrue(self.path.ismount('!'))
        self.assertFalse(self.path.ismount('!mount!'))
        self.filesystem.add_mount_point('!mount')
        self.assertTrue(self.path.ismount('!mount'))
        self.assertTrue(self.path.ismount('!mount!'))

    def test_ismount_with_drive_letters(self):
        self.filesystem.is_windows_fs = True
        self.assertTrue(self.path.ismount('!'))
        self.assertTrue(self.path.ismount('c:!'))
        self.assertFalse(self.path.ismount('c:'))
        self.assertTrue(self.path.ismount('z:!'))
        self.filesystem.add_mount_point('!mount')
        self.assertTrue(self.path.ismount('!mount'))
        self.assertTrue(self.path.ismount('!mount!'))

    @unittest.skipIf(sys.version_info < (2, 7, 8),
                     'UNC path support since Python 2.7.8')
    def test_ismount_with_unc_paths(self):
        self.filesystem.is_windows_fs = True
        self.assertTrue(self.path.ismount('!!a!'))
        self.assertTrue(self.path.ismount('!!a!b'))
        self.assertTrue(self.path.ismount('!!a!b!'))
        self.assertFalse(self.path.ismount('!a!b!'))
        self.assertFalse(self.path.ismount('!!a!b!c'))

    def test_ismount_with_alternate_path_separator(self):
        self.filesystem.alternative_path_separator = '!'
        self.filesystem.add_mount_point('!mount')
        self.assertTrue(self.path.ismount('!mount'))
        self.assertTrue(self.path.ismount('!mount!'))
        self.assertTrue(self.path.ismount('!mount!!'))
        self.filesystem.is_windows_fs = True
        self.assertTrue(self.path.ismount('Z:!'))

    @unittest.skipIf(sys.version_info >= (3, 0),
                     'os.path.walk removed in Python 3')
    def test_walk(self):
        self.filesystem.create_file('!foo!bar!baz')
        self.filesystem.create_file('!foo!bar!xyzzy!plugh')
        visited_nodes = []

        def RecordVisitedNodes(visited, dirname, fnames):
            visited.extend(((dirname, fname) for fname in fnames))

        self.path.walk('!foo', RecordVisitedNodes, visited_nodes)
        expected = [('!foo', 'bar'),
                    ('!foo!bar', 'baz'),
                    ('!foo!bar', 'xyzzy'),
                    ('!foo!bar!xyzzy', 'plugh')]
        self.assertEqual(expected, sorted(visited_nodes))

    @unittest.skipIf(sys.version_info >= (3, 0) or TestCase.is_windows,
                     'os.path.walk deprecrated in Python 3, cannot be properly '
                     'tested in win32')
    def test_walk_from_nonexistent_top_does_not_throw(self):
        visited_nodes = []

        def RecordVisitedNodes(visited, dirname, fnames):
            visited.extend(((dirname, fname) for fname in fnames))

        self.path.walk('!foo', RecordVisitedNodes, visited_nodes)
        self.assertEqual([], visited_nodes)

    def test_getattr_forward_to_real_os_path(self):
        """Forwards any non-faked calls to os.path."""
        self.assertTrue(hasattr(self.path, 'sep'),
                        'Get a faked os.path function')
        private_path_function = None
        if (2, 7) <= sys.version_info < (3, 6):
            if self.is_windows:
                if sys.version_info >= (3, 0):
                    private_path_function = '_get_bothseps'
                else:
                    private_path_function = '_abspath_split'
            else:
                private_path_function = '_joinrealpath'
        if private_path_function:
            self.assertTrue(hasattr(self.path, private_path_function),
                            'Get a real os.path function '
                            'not implemented in fake os.path')
        self.assertFalse(hasattr(self.path, 'nonexistent'))


class FakeFileOpenTestBase(RealFsTestCase):
    def path_separator(self):
        return '!'


class FakeFileOpenTest(FakeFileOpenTestBase):
    def setUp(self):
        super(FakeFileOpenTest, self).setUp()
        self.orig_time = time.time

    def tearDown(self):
        super(FakeFileOpenTest, self).tearDown()
        time.time = self.orig_time

    def test_open_no_parent_dir(self):
        """Expect raise when opening a file in a missing directory."""
        file_path = self.make_path('foo', 'bar.txt')
        self.assert_raises_io_error(errno.ENOENT, self.open, file_path, 'w')

    def test_delete_on_close(self):
        self.skip_real_fs()
        file_dir = 'boo'
        file_path = 'boo!far'
        self.os.mkdir(file_dir)
        self.open = fake_filesystem.FakeFileOpen(self.filesystem,
                                                 delete_on_close=True)
        with self.open(file_path, 'w'):
            self.assertTrue(self.filesystem.exists(file_path))
        self.assertFalse(self.filesystem.exists(file_path))

    def test_no_delete_on_close_by_default(self):
        file_path = self.make_path('czar')
        with self.open(file_path, 'w'):
            self.assertTrue(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.exists(file_path))

    def test_compatibility_of_with_statement(self):
        self.skip_real_fs()
        self.open = fake_filesystem.FakeFileOpen(self.filesystem,
                                                 delete_on_close=True)
        file_path = 'foo'
        self.assertFalse(self.os.path.exists(file_path))
        with self.open(file_path, 'w') as _:
            self.assertTrue(self.os.path.exists(file_path))
        # After the 'with' statement, the close() method should have been called.
        self.assertFalse(self.os.path.exists(file_path))

    def test_unicode_contents(self):
        file_path = self.make_path('foo')
        # note that this will work only if the string can be represented
        # by the locale preferred encoding - which under Windows is
        # usually not UTF-8, but something like Latin1, depending on the locale
        text_fractions = 'Ümläüts'
        with self.open(file_path, 'w') as f:
            f.write(text_fractions)
        with self.open(file_path) as f:
            contents = f.read()
        self.assertEqual(contents, text_fractions)

    @unittest.skipIf(sys.version_info >= (3, 0),
                     'Python2 specific string handling')
    def testByteContentsPy2(self):
        file_path = self.make_path('foo')
        byte_fractions = b'\xe2\x85\x93 \xe2\x85\x94 \xe2\x85\x95 \xe2\x85\x96'
        with self.open(file_path, 'w') as f:
            f.write(byte_fractions)
        with self.open(file_path) as f:
            contents = f.read()
        self.assertEqual(contents, byte_fractions)

    @unittest.skipIf(sys.version_info < (3, 0),
                     'Python3 specific string handling')
    def testByteContentsPy3(self):
        file_path = self.make_path('foo')
        byte_fractions = b'\xe2\x85\x93 \xe2\x85\x94 \xe2\x85\x95 \xe2\x85\x96'
        with self.open(file_path, 'wb') as f:
            f.write(byte_fractions)
        # the encoding has to be specified, otherwise the locale default
        # is used which can be different on different systems
        with self.open(file_path, encoding='utf-8') as f:
            contents = f.read()
        self.assertEqual(contents, byte_fractions.decode('utf-8'))

    def test_write_str_read_bytes(self):
        file_path = self.make_path('foo')
        str_contents = 'Äsgül'
        with self.open(file_path, 'w') as f:
            f.write(str_contents)
        with self.open(file_path, 'rb') as f:
            contents = f.read()
        if sys.version_info < (3, 0):
            self.assertEqual(str_contents, contents)
        else:
            self.assertEqual(str_contents, contents.decode(
                locale.getpreferredencoding(False)))

    def test_byte_contents(self):
        file_path = self.make_path('foo')
        byte_fractions = b'\xe2\x85\x93 \xe2\x85\x94 \xe2\x85\x95 \xe2\x85\x96'
        with self.open(file_path, 'wb') as f:
            f.write(byte_fractions)
        with self.open(file_path, 'rb') as f:
            contents = f.read()
        self.assertEqual(contents, byte_fractions)

    def test_open_valid_file(self):
        contents = [
            'I am he as\n',
            'you are he as\n',
            'you are me and\n',
            'we are all together\n'
        ]
        file_path = self.make_path('bar.txt')
        self.create_file(file_path, contents=''.join(contents))
        with self.open(file_path) as fake_file:
            self.assertEqual(contents, fake_file.readlines())

    def test_open_valid_args(self):
        # FIXME: under Windows, line endings are not handled correctly
        self.skip_real_fs_failure(skip_posix=False, skip_python2=False)
        contents = [
            "Bang bang Maxwell's silver hammer\n",
            'Came down on her head',
        ]
        file_path = self.make_path('abbey_road', 'maxwell')
        self.create_file(file_path, contents=''.join(contents))

        self.assertEqual(
            contents, self.open(file_path, mode='r', buffering=1).readlines())
        if sys.version_info >= (3, 0):
            self.assertEqual(
                contents, self.open(file_path, mode='r', buffering=1,
                                    errors='strict', newline='\n',
                                    opener=None).readlines())

    @unittest.skipIf(sys.version_info < (3, 0),
                     'only tested on 3.0 or greater')
    def test_open_newline_arg(self):
        # FIXME: line endings are not handled correctly in pyfakefs
        self.skip_real_fs_failure()
        file_path = self.make_path('some_file')
        file_contents = b'two\r\nlines'
        self.create_file(file_path, contents=file_contents)
        fake_file = self.open(file_path, mode='r', newline=None)
        self.assertEqual(['two\n', 'lines'], fake_file.readlines())
        fake_file = self.open(file_path, mode='r', newline='')
        self.assertEqual(['two\r\n', 'lines'], fake_file.readlines())
        fake_file = self.open(file_path, mode='r', newline='\r')
        self.assertEqual(['two\r', '\r', 'lines'], fake_file.readlines())
        fake_file = self.open(file_path, mode='r', newline='\n')
        self.assertEqual(['two\r\n', 'lines'], fake_file.readlines())
        fake_file = self.open(file_path, mode='r', newline='\r\n')
        self.assertEqual(['two\r\r\n', 'lines'], fake_file.readlines())

    def test_open_valid_file_with_cwd(self):
        contents = [
            'I am he as\n',
            'you are he as\n',
            'you are me and\n',
            'we are all together\n'
        ]
        file_path = self.make_path('bar.txt')
        self.create_file(file_path, contents=''.join(contents))
        self.os.chdir(self.base_path)
        self.assertEqual(contents, self.open(file_path).readlines())

    def test_iterate_over_file(self):
        contents = [
            "Bang bang Maxwell's silver hammer",
            'Came down on her head',
        ]
        file_path = self.make_path('abbey_road', 'maxwell')
        self.create_file(file_path, contents='\n'.join(contents))
        with self.open(file_path) as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    def test_open_directory_error(self):
        directory_path = self.make_path('foo')
        self.os.mkdir(directory_path)
        if self.is_windows:
            if self.is_python2:
                self.assert_raises_io_error(errno.EACCES, self.open.__call__,
                                            directory_path)
            else:
                self.assert_raises_os_error(errno.EACCES, self.open.__call__,
                                            directory_path)
        else:
            self.assert_raises_io_error(errno.EISDIR, self.open.__call__,
                                        directory_path)

    def test_create_file_with_write(self):
        contents = [
            "Here comes the sun, little darlin'",
            'Here comes the sun, and I say,',
            "It's alright",
        ]
        file_dir = self.make_path('abbey_road')
        file_path = self.os.path.join(file_dir, 'here_comes_the_sun')
        self.os.mkdir(file_dir)
        with self.open(file_path, 'w') as fake_file:
            for line in contents:
                fake_file.write(line + '\n')
        with self.open(file_path) as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    def test_create_file_with_append(self):
        contents = [
            "Here comes the sun, little darlin'",
            'Here comes the sun, and I say,',
            "It's alright",
        ]
        file_dir = self.make_path('abbey_road')
        file_path = self.os.path.join(file_dir, 'here_comes_the_sun')
        self.os.mkdir(file_dir)
        with self.open(file_path, 'a') as fake_file:
            for line in contents:
                fake_file.write(line + '\n')
        with self.open(file_path) as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    @unittest.skipIf(not TestCase.is_python2, 'Python2 specific test')
    def testExclusiveModeNotValidInPython2(self):
        file_path = self.make_path('bar')
        self.assertRaises(ValueError, self.open, file_path, 'x')
        self.assertRaises(ValueError, self.open, file_path, 'xb')

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Exclusive mode new in Python 3.3')
    def test_exclusive_create_file_failure(self):
        self.skip_if_symlink_not_supported()
        file_path = self.make_path('bar')
        self.create_file(file_path)
        self.assert_raises_io_error(errno.EEXIST, self.open, file_path, 'x')
        self.assert_raises_io_error(errno.EEXIST, self.open, file_path, 'xb')

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Exclusive mode new in Python 3.3')
    def test_exclusive_create_file(self):
        file_dir = self.make_path('foo')
        file_path = self.os.path.join(file_dir, 'bar')
        self.os.mkdir(file_dir)
        contents = 'String contents'
        with self.open(file_path, 'x') as fake_file:
            fake_file.write(contents)
        with self.open(file_path) as fake_file:
            self.assertEqual(contents, fake_file.read())

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Exclusive mode new in Python 3.3')
    def test_exclusive_create_binary_file(self):
        file_dir = self.make_path('foo')
        file_path = self.os.path.join(file_dir, 'bar')
        self.os.mkdir(file_dir)
        contents = b'Binary contents'
        with self.open(file_path, 'xb') as fake_file:
            fake_file.write(contents)
        with self.open(file_path, 'rb') as fake_file:
            self.assertEqual(contents, fake_file.read())

    def test_overwrite_existing_file(self):
        file_path = self.make_path('overwite')
        self.create_file(file_path, contents='To disappear')
        new_contents = [
            'Only these lines',
            'should be in the file.',
        ]
        with self.open(file_path, 'w') as fake_file:
            for line in new_contents:
                fake_file.write(line + '\n')
        with self.open(file_path) as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(new_contents, result)

    def test_append_existing_file(self):
        file_path = self.make_path('appendfile')
        contents = [
            'Contents of original file'
            'Appended contents',
        ]

        self.create_file(file_path, contents=contents[0])
        with self.open(file_path, 'a') as fake_file:
            for line in contents[1:]:
                fake_file.write(line + '\n')
        with self.open(file_path) as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    def test_open_with_wplus(self):
        # set up
        file_path = self.make_path('wplus_file')
        self.create_file(file_path, contents='old contents')
        self.assertTrue(self.os.path.exists(file_path))
        with self.open(file_path, 'r') as fake_file:
            self.assertEqual('old contents', fake_file.read())
        # actual tests
        with self.open(file_path, 'w+') as fake_file:
            fake_file.write('new contents')
            fake_file.seek(0)
            self.assertTrue('new contents', fake_file.read())

    def test_open_with_wplus_truncation(self):
        # set up
        file_path = self.make_path('wplus_file')
        self.create_file(file_path, contents='old contents')
        self.assertTrue(self.os.path.exists(file_path))
        with self.open(file_path, 'r') as fake_file:
            self.assertEqual('old contents', fake_file.read())
        # actual tests
        with self.open(file_path, 'w+') as fake_file:
            fake_file.seek(0)
            self.assertEqual('', fake_file.read())

    def test_open_with_append_flag(self):
        # FIXME: under Windows, line endings are not handled correctly
        self.skip_real_fs_failure(skip_posix=False)
        contents = [
            'I am he as\n',
            'you are he as\n',
            'you are me and\n',
            'we are all together\n'
        ]
        additional_contents = [
            'These new lines\n',
            'like you a lot.\n'
        ]
        file_path = self.make_path('appendfile')
        self.create_file(file_path, contents=''.join(contents))
        with self.open(file_path, 'a') as fake_file:
            expected_error = (IOError if sys.version_info < (3,)
                              else io.UnsupportedOperation)
            self.assertRaises(expected_error, fake_file.read, 0)
            self.assertRaises(expected_error, fake_file.readline)
            self.assertEqual(len(''.join(contents)), fake_file.tell())
            fake_file.seek(0)
            self.assertEqual(0, fake_file.tell())
            fake_file.writelines(additional_contents)
        with self.open(file_path) as fake_file:
            self.assertEqual(
                contents + additional_contents, fake_file.readlines())

    def check_append_with_aplus(self):
        file_path = self.make_path('aplus_file')
        self.create_file(file_path, contents='old contents')
        self.assertTrue(self.os.path.exists(file_path))
        with self.open(file_path, 'r') as fake_file:
            self.assertEqual('old contents', fake_file.read())

        if self.filesystem:
            # need to recreate FakeFileOpen for OS specific initialization
            self.open = fake_filesystem.FakeFileOpen(self.filesystem,
                                                     delete_on_close=True)
        with self.open(file_path, 'a+') as fake_file:
            if self.is_python2 and not self.is_macos and not self.is_pypy:
                self.assertEqual(0, fake_file.tell())
                fake_file.seek(12)
            else:
                self.assertEqual(12, fake_file.tell())
            fake_file.write('new contents')
            self.assertEqual(24, fake_file.tell())
            fake_file.seek(0)
            self.assertEqual('old contentsnew contents', fake_file.read())

    def test_append_with_aplus_mac_os(self):
        self.check_macos_only()
        self.check_append_with_aplus()

    def test_append_with_aplus_linux_windows(self):
        self.check_linux_and_windows()
        self.check_append_with_aplus()

    def test_append_with_aplus_read_with_loop(self):
        # set up
        file_path = self.make_path('aplus_file')
        self.create_file(file_path, contents='old contents')
        self.assertTrue(self.os.path.exists(file_path))
        with self.open(file_path, 'r') as fake_file:
            self.assertEqual('old contents', fake_file.read())
        # actual tests
        with self.open(file_path, 'a+') as fake_file:
            fake_file.seek(0)
            fake_file.write('new contents')
            fake_file.seek(0)
            for line in fake_file:
                self.assertEqual('old contentsnew contents', line)

    def test_read_empty_file_with_aplus(self):
        file_path = self.make_path('aplus_file')
        with self.open(file_path, 'a+') as fake_file:
            self.assertEqual('', fake_file.read())

    def test_read_with_rplus(self):
        # set up
        file_path = self.make_path('rplus_file')
        self.create_file(file_path, contents='old contents here')
        self.assertTrue(self.os.path.exists(file_path))
        with self.open(file_path, 'r') as fake_file:
            self.assertEqual('old contents here', fake_file.read())
        # actual tests
        with self.open(file_path, 'r+') as fake_file:
            self.assertEqual('old contents here', fake_file.read())
            fake_file.seek(0)
            fake_file.write('new contents')
            fake_file.seek(0)
            self.assertEqual('new contents here', fake_file.read())

    def test_open_st_ctime(self):
        # set up
        self.skip_real_fs()
        time.time = _DummyTime(100, 10)
        file_path = self.make_path('some_file')
        self.assertFalse(self.os.path.exists(file_path))
        # tests
        fake_file = self.open(file_path, 'w')
        time.time.start()
        st = self.os.stat(file_path)
        self.assertEqual(100, st.st_ctime)
        self.assertEqual(100, st.st_mtime)
        fake_file.close()
        st = self.os.stat(file_path)
        self.assertEqual(110, st.st_ctime)
        self.assertEqual(110, st.st_mtime)

        fake_file = self.open(file_path, 'w')
        st = self.os.stat(file_path)
        # truncating the file cause an additional stat update
        self.assertEqual(120, st.st_ctime)
        self.assertEqual(120, st.st_mtime)
        fake_file.close()
        st = self.os.stat(file_path)
        self.assertEqual(130, st.st_ctime)
        self.assertEqual(130, st.st_mtime)

        fake_file = self.open(file_path, 'w+')
        st = self.os.stat(file_path)
        self.assertEqual(140, st.st_ctime)
        self.assertEqual(140, st.st_mtime)
        fake_file.close()
        st = self.os.stat(file_path)
        self.assertEqual(150, st.st_ctime)
        self.assertEqual(150, st.st_mtime)

        fake_file = self.open(file_path, 'a')
        st = self.os.stat(file_path)
        # not updating m_time or c_time here, since no truncating.
        self.assertEqual(150, st.st_ctime)
        self.assertEqual(150, st.st_mtime)
        fake_file.close()
        st = self.os.stat(file_path)
        self.assertEqual(160, st.st_ctime)
        self.assertEqual(160, st.st_mtime)

        fake_file = self.open(file_path, 'r')
        st = self.os.stat(file_path)
        self.assertEqual(160, st.st_ctime)
        self.assertEqual(160, st.st_mtime)
        fake_file.close()
        st = self.os.stat(file_path)
        self.assertEqual(160, st.st_ctime)
        self.assertEqual(160, st.st_mtime)

    def _CreateWithPermission(self, file_path, perm_bits):
        self.create_file(file_path)
        self.os.chmod(file_path, perm_bits)
        st = self.os.stat(file_path)
        self.assert_mode_equal(perm_bits, st.st_mode)
        self.assertTrue(st.st_mode & stat.S_IFREG)
        self.assertFalse(st.st_mode & stat.S_IFDIR)

    def testOpenFlags700(self):
        # set up
        self.check_posix_only()
        file_path = self.make_path('target_file')
        self._CreateWithPermission(file_path, 0o700)
        # actual tests
        self.open(file_path, 'r').close()
        self.open(file_path, 'w').close()
        self.open(file_path, 'w+').close()
        self.assertRaises(ValueError, self.open, file_path, 'INV')

    def testOpenFlags400(self):
        # set up
        self.check_posix_only()
        file_path = self.make_path('target_file')
        self._CreateWithPermission(file_path, 0o400)
        # actual tests
        self.open(file_path, 'r').close()
        self.assert_raises_io_error(errno.EACCES, self.open, file_path, 'w')
        self.assert_raises_io_error(errno.EACCES, self.open, file_path, 'w+')

    def testOpenFlags200(self):
        # set up
        self.check_posix_only()
        file_path = self.make_path('target_file')
        self._CreateWithPermission(file_path, 0o200)
        # actual tests
        self.assertRaises(IOError, self.open, file_path, 'r')
        self.open(file_path, 'w').close()
        self.assertRaises(IOError, self.open, file_path, 'w+')

    def testOpenFlags100(self):
        # set up
        self.check_posix_only()
        file_path = self.make_path('target_file')
        self._CreateWithPermission(file_path, 0o100)
        # actual tests 4
        self.assertRaises(IOError, self.open, file_path, 'r')
        self.assertRaises(IOError, self.open, file_path, 'w')
        self.assertRaises(IOError, self.open, file_path, 'w+')

    def test_follow_link_read(self):
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('foo', 'bar', 'baz')
        target = self.make_path('tarJAY')
        target_contents = 'real baz contents'
        self.create_file(target, contents=target_contents)
        self.create_symlink(link_path, target)
        self.assertEqual(target, self.os.readlink(link_path))
        fh = self.open(link_path, 'r')
        got_contents = fh.read()
        fh.close()
        self.assertEqual(target_contents, got_contents)

    def test_follow_link_write(self):
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('foo', 'bar', 'TBD')
        target = self.make_path('tarJAY')
        target_contents = 'real baz contents'
        self.create_symlink(link_path, target)
        self.assertFalse(self.os.path.exists(target))

        with self.open(link_path, 'w') as fh:
            fh.write(target_contents)
        with self.open(target, 'r') as fh:
            got_contents = fh.read()
        self.assertEqual(target_contents, got_contents)

    def test_follow_intra_path_link_write(self):
        # Test a link in the middle of of a file path.
        self.skip_if_symlink_not_supported()
        link_path = self.os.path.join(
            self.base_path, 'foo', 'build', 'local_machine', 'output', '1')
        target = self.make_path('tmp', 'output', '1')
        self.create_dir(self.make_path('tmp', 'output'))
        self.create_symlink(self.os.path.join(
            self.base_path, 'foo', 'build', 'local_machine'),
            self.make_path('tmp'))

        self.assertFalse(self.os.path.exists(link_path))
        self.assertFalse(self.os.path.exists(target))

        target_contents = 'real baz contents'
        with self.open(link_path, 'w') as fh:
            fh.write(target_contents)
        with self.open(target, 'r') as fh:
            got_contents = fh.read()
        self.assertEqual(target_contents, got_contents)

    def test_open_raises_on_symlink_loop(self):
        # Regression test for #274
        self.check_posix_only()
        file_dir = self.make_path('foo')
        self.os.mkdir(file_dir)
        file_path = self.os.path.join(file_dir, 'baz')
        self.os.symlink(file_path, file_path)
        self.assert_raises_io_error(errno.ELOOP, self.open, file_path)

    def test_file_descriptors_for_different_files(self):
        first_path = self.make_path('some_file1')
        self.create_file(first_path, contents='contents here1')
        second_path = self.make_path('some_file2')
        self.create_file(second_path, contents='contents here2')
        third_path = self.make_path('some_file3')
        self.create_file(third_path, contents='contents here3')

        with self.open(first_path) as fake_file1:
            with self.open(second_path) as fake_file2:
                with self.open(third_path) as fake_file3:
                    fileno2 = fake_file2.fileno()
                    self.assertGreater(fileno2, fake_file1.fileno())
                    self.assertGreater(fake_file3.fileno(), fileno2)

    def test_file_descriptors_for_the_same_file_are_different(self):
        first_path = self.make_path('some_file1')
        self.create_file(first_path, contents='contents here1')
        second_path = self.make_path('some_file2')
        self.create_file(second_path, contents='contents here2')
        with self.open(first_path) as fake_file1:
            with self.open(second_path) as fake_file2:
                with self.open(first_path) as fake_file1a:
                    fileno2 = fake_file2.fileno()
                    self.assertGreater(fileno2, fake_file1.fileno())
                    self.assertGreater(fake_file1a.fileno(), fileno2)

    def test_reused_file_descriptors_do_not_affect_others(self):
        first_path = self.make_path('some_file1')
        self.create_file(first_path, contents='contents here1')
        second_path = self.make_path('some_file2')
        self.create_file(second_path, contents='contents here2')
        third_path = self.make_path('some_file3')
        self.create_file(third_path, contents='contents here3')

        with self.open(first_path, 'r') as fake_file1:
            with self.open(second_path, 'r') as fake_file2:
                fake_file3 = self.open(third_path, 'r')
                fake_file1a = self.open(first_path, 'r')
                fileno1 = fake_file1.fileno()
                fileno2 = fake_file2.fileno()
                fileno3 = fake_file3.fileno()
                fileno4 = fake_file1a.fileno()

        with self.open(second_path, 'r') as fake_file2:
            with self.open(first_path, 'r') as fake_file1b:
                self.assertEqual(fileno1, fake_file2.fileno())
                self.assertEqual(fileno2, fake_file1b.fileno())
                self.assertEqual(fileno3, fake_file3.fileno())
                self.assertEqual(fileno4, fake_file1a.fileno())
        fake_file3.close()
        fake_file1a.close()

    def test_intertwined_read_write(self):
        file_path = self.make_path('some_file')
        self.create_file(file_path)

        with self.open(file_path, 'a') as writer:
            with self.open(file_path, 'r') as reader:
                writes = ['hello', 'world\n', 'somewhere\nover', 'the\n',
                          'rainbow']
                reads = []
                # when writes are flushes, they are piped to the reader
                for write in writes:
                    writer.write(write)
                    writer.flush()
                    reads.append(reader.read())
                    reader.flush()
                self.assertEqual(writes, reads)
                writes = ['nothing', 'to\nsee', 'here']
                reads = []
                # when writes are not flushed, the reader doesn't read
                # anything new
                for write in writes:
                    writer.write(write)
                    reads.append(reader.read())
                self.assertEqual(['' for _ in writes], reads)

    @unittest.skipIf(sys.version_info < (3, 0),
                     'Python 3 specific string handling')
    def testIntertwinedReadWritePython3Str(self):
        file_path = self.make_path('some_file')
        self.create_file(file_path)

        with self.open(file_path, 'a', encoding='utf-8') as writer:
            with self.open(file_path, 'r', encoding='utf-8') as reader:
                writes = ['привет', 'мир\n', 'где-то\за', 'радугой']
                reads = []
                # when writes are flushes, they are piped to the reader
                for write in writes:
                    writer.write(write)
                    writer.flush()
                    reads.append(reader.read())
                    reader.flush()
                self.assertEqual(writes, reads)
                writes = ['ничего', 'не\nвидно']
                reads = []
                # when writes are not flushed, the reader doesn't
                # read anything new
                for write in writes:
                    writer.write(write)
                    reads.append(reader.read())
                self.assertEqual(['' for _ in writes], reads)

    def test_open_io_errors(self):
        file_path = self.make_path('some_file')
        self.create_file(file_path)

        with self.open(file_path, 'a') as fh:
            self.assertRaises(IOError, fh.read)
            self.assertRaises(IOError, fh.readlines)
        with self.open(file_path, 'w') as fh:
            self.assertRaises(IOError, fh.read)
            self.assertRaises(IOError, fh.readlines)
        with self.open(file_path, 'r') as fh:
            self.assertRaises(IOError, fh.truncate)
            self.assertRaises(IOError, fh.write, 'contents')
            self.assertRaises(IOError, fh.writelines, ['con', 'tents'])

        def _IteratorOpen(file_path, mode):
            for _ in self.open(file_path, mode):
                pass

        self.assertRaises(IOError, _IteratorOpen, file_path, 'w')
        self.assertRaises(IOError, _IteratorOpen, file_path, 'a')

    def test_open_raises_io_error_if_parent_is_file_posix(self):
        self.check_posix_only()
        file_path = self.make_path('bar')
        self.create_file(file_path)
        file_path = self.os.path.join(file_path, 'baz')
        self.assert_raises_io_error(errno.ENOTDIR, self.open, file_path, 'w')

    def test_open_raises_io_error_if_parent_is_file_windows(self):
        self.check_windows_only()
        file_path = self.make_path('bar')
        self.create_file(file_path)
        file_path = self.os.path.join(file_path, 'baz')
        self.assert_raises_io_error(errno.ENOENT, self.open, file_path, 'w')

    def test_can_read_from_block_device(self):
        self.skip_real_fs()
        device_path = 'device'
        self.filesystem.create_file(device_path, stat.S_IFBLK
                                    | fake_filesystem.PERM_ALL)
        with self.open(device_path, 'r') as fh:
            self.assertEqual('', fh.read())

    def test_truncate_flushes_contents(self):
        # Regression test for #285
        file_path = self.make_path('baz')
        self.create_file(file_path)
        with self.open(file_path, 'w') as f0:
            f0.write('test')
            f0.truncate()
            self.assertEqual(4, self.os.path.getsize(file_path))

    def test_that_read_over_end_does_not_reset_position(self):
        # Regression test for #286
        file_path = self.make_path('baz')
        self.create_file(file_path)
        with self.open(file_path) as f0:
            f0.seek(2)
            f0.read()
            self.assertEqual(2, f0.tell())

    def test_accessing_closed_file_raises(self):
        # Regression test for #275, #280
        if self.is_pypy:
            raise unittest.SkipTest('Different exceptions with PyPy')
        file_path = self.make_path('foo')
        self.create_file(file_path, contents=b'test')
        fake_file = self.open(file_path, 'r')
        fake_file.close()
        self.assertRaises(ValueError, lambda: fake_file.read(1))
        self.assertRaises(ValueError, lambda: fake_file.write('a'))
        self.assertRaises(ValueError, lambda: fake_file.readline())
        self.assertRaises(ValueError, lambda: fake_file.truncate())
        self.assertRaises(ValueError, lambda: fake_file.tell())
        self.assertRaises(ValueError, lambda: fake_file.seek(1))
        self.assertRaises(ValueError, lambda: fake_file.flush())

    @unittest.skipIf(sys.version_info >= (3,),
                     'file.next() not available in Python 3')
    def test_next_raises_on_closed_file(self):
        # Regression test for #284
        file_path = self.make_path('foo')
        with self.open(file_path, 'w') as f0:
            f0.write('test')
            f0.seek(0)
            self.assertRaises(IOError, lambda: f0.next())

    def test_accessing_open_file_with_another_handle_raises(self):
        # Regression test for #282
        if self.is_pypy:
            raise unittest.SkipTest('Different exceptions with PyPy')
        file_path = self.make_path('foo')
        f0 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        fake_file = self.open(file_path, 'r')
        fake_file.close()
        self.assertRaises(ValueError, lambda: fake_file.read(1))
        self.assertRaises(ValueError, lambda: fake_file.write('a'))
        self.os.close(f0)

    def test_tell_flushes_under_mac_os(self):
        # Regression test for #288
        self.check_macos_only()
        file_path = self.make_path('foo')
        with self.open(file_path, 'w') as f0:
            f0.write('test')
            self.assertEqual(4, f0.tell())
            self.assertEqual(4, self.os.path.getsize(file_path))

    def testTellFlushesInPython3(self):
        # Regression test for #288
        self.check_linux_and_windows()
        file_path = self.make_path('foo')
        with self.open(file_path, 'w') as f0:
            f0.write('test')
            self.assertEqual(4, f0.tell())
            expected = 0 if sys.version_info < (3,) else 4
            self.assertEqual(expected, self.os.path.getsize(file_path))

    def test_read_flushes_under_posix(self):
        # Regression test for #278
        self.check_posix_only()
        file_path = self.make_path('foo')
        with self.open(file_path, 'a+') as f0:
            f0.write('test')
            self.assertEqual('', f0.read())
            self.assertEqual(4, self.os.path.getsize(file_path))

    def testReadFlushesUnderWindowsInPython3(self):
        # Regression test for #278
        self.check_windows_only()
        file_path = self.make_path('foo')
        with self.open(file_path, 'w+') as f0:
            f0.write('test')
            f0.read()
            expected = 0 if sys.version_info[0] < 3 else 4
            self.assertEqual(expected, self.os.path.getsize(file_path))

    def test_seek_flushes(self):
        # Regression test for #290
        file_path = self.make_path('foo')
        with self.open(file_path, 'w') as f0:
            f0.write('test')
            self.assertEqual(0, self.os.path.getsize(file_path))
            f0.seek(3)
            self.assertEqual(4, self.os.path.getsize(file_path))

    def test_truncate_flushes(self):
        # Regression test for #291
        file_path = self.make_path('foo')
        with self.open(file_path, 'a') as f0:
            f0.write('test')
            self.assertEqual(0, self.os.path.getsize(file_path))
            f0.truncate()
            self.assertEqual(4, self.os.path.getsize(file_path))

    def check_seek_outside_and_truncate_sets_size(self, mode):
        # Regression test for #294 and #296
        file_path = self.make_path('baz')
        with self.open(file_path, mode) as f0:
            f0.seek(1)
            f0.truncate()
            self.assertEqual(1, f0.tell())
            self.assertEqual(1, self.os.path.getsize(file_path))
            f0.seek(1)
            self.assertEqual(1, self.os.path.getsize(file_path))
        self.assertEqual(1, self.os.path.getsize(file_path))

    def test_seek_outside_and_truncate_sets_size_in_write_mode(self):
        # Regression test for #294
        self.check_seek_outside_and_truncate_sets_size('w')

    def test_seek_outside_and_truncate_sets_size_in_append_mode(self):
        # Regression test for #295
        self.check_seek_outside_and_truncate_sets_size('a')

    def test_closing_closed_file_does_nothing(self):
        # Regression test for #299
        file_path = self.make_path('baz')
        f0 = self.open(file_path, 'w')
        f0.close()
        with self.open(file_path) as f1:
            # would close f1 if not handled
            f0.close()
            self.assertEqual('', f1.read())

    def test_truncate_flushes_zeros(self):
        # Regression test for #301
        file_path = self.make_path('baz')
        with self.open(file_path, 'w') as f0:
            with self.open(file_path) as f1:
                f0.seek(1)
                f0.truncate()
                self.assertEqual('\0', f1.read())

    def test_byte_filename(self):
        file_path = self.make_path(b'test')
        with self.open(file_path, 'wb') as f:
            f.write(b'test')
        with self.open(file_path, 'rb') as f:
            self.assertEqual(b'test', f.read())

    def test_unicode_filename(self):
        file_path = self.make_path(u'тест')
        with self.open(file_path, 'wb') as f:
            f.write(b'test')
        with self.open(file_path, 'rb') as f:
            self.assertEqual(b'test', f.read())


class RealFileOpenTest(FakeFileOpenTest):
    def use_real_fs(self):
        return True


class OpenFileWithEncodingTest(FakeFileOpenTestBase):
    """Tests that are similar to some open file tests above but using
    an explicit text encoding."""

    def setUp(self):
        super(OpenFileWithEncodingTest, self).setUp()
        if self.use_real_fs():
            self.open = io.open
        else:
            self.open = fake_filesystem.FakeFileOpen(self.filesystem,
                                                     use_io=True)
        self.file_path = self.make_path('foo')

    def test_write_str_read_bytes(self):
        str_contents = u'علي بابا'
        with self.open(self.file_path, 'w', encoding='arabic') as f:
            f.write(str_contents)
        with self.open(self.file_path, 'rb') as f:
            contents = f.read()
        self.assertEqual(str_contents, contents.decode('arabic'))

    def test_write_str_error_modes(self):
        str_contents = u'علي بابا'
        with self.open(self.file_path, 'w', encoding='cyrillic') as f:
            self.assertRaises(UnicodeEncodeError, f.write, str_contents)

        with self.open(self.file_path, 'w', encoding='ascii',
                       errors='xmlcharrefreplace') as f:
            f.write(str_contents)
        with self.open(self.file_path, 'r', encoding='ascii') as f:
            contents = f.read()
        self.assertEqual('&#1593;&#1604;&#1610; &#1576;&#1575;&#1576;&#1575;',
                         contents)

        if sys.version_info >= (3, 5):
            with self.open(self.file_path, 'w', encoding='ascii',
                           errors='namereplace') as f:
                f.write(str_contents)
            with self.open(self.file_path, 'r', encoding='ascii') as f:
                contents = f.read()
            self.assertEqual(
                r'\N{ARABIC LETTER AIN}\N{ARABIC LETTER LAM}\N{ARABIC LETTER YEH} '
                r'\N{ARABIC LETTER BEH}\N{ARABIC LETTER ALEF}\N{ARABIC LETTER BEH}'
                r'\N{ARABIC LETTER ALEF}', contents)

    def test_read_str_error_modes(self):
        str_contents = u'علي بابا'
        with self.open(self.file_path, 'w', encoding='arabic') as f:
            f.write(str_contents)

        # default strict encoding
        with self.open(self.file_path, encoding='ascii') as f:
            self.assertRaises(UnicodeDecodeError, f.read)
        with self.open(self.file_path, encoding='ascii',
                       errors='replace') as f:
            contents = f.read()
        self.assertNotEqual(str_contents, contents)

        if sys.version_info >= (3, 5):
            with self.open(self.file_path, encoding='ascii',
                           errors='backslashreplace') as f:
                contents = f.read()
            self.assertEqual(r'\xd9\xe4\xea \xc8\xc7\xc8\xc7', contents)

    def test_write_and_read_str(self):
        str_contents = u'علي بابا'
        with self.open(self.file_path, 'w', encoding='arabic') as f:
            f.write(str_contents)
        with self.open(self.file_path, 'r', encoding='arabic') as f:
            contents = f.read()
        self.assertEqual(str_contents, contents)

    def test_create_file_with_append(self):
        contents = [
            u'Allons enfants de la Patrie,'
            u'Le jour de gloire est arrivé!',
            u'Contre nous de la tyrannie,',
            u'L’étendard sanglant est levé.',
        ]
        with self.open(self.file_path, 'a', encoding='utf-8') as fake_file:
            for line in contents:
                fake_file.write(line + '\n')
        with self.open(self.file_path, encoding='utf-8') as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    def test_append_existing_file(self):
        contents = [
            u'Оригинальное содержание'
            u'Дополнительное содержание',
        ]
        self.create_file(self.file_path, contents=contents[0],
                         encoding='cyrillic')
        with self.open(self.file_path, 'a', encoding='cyrillic') as fake_file:
            for line in contents[1:]:
                fake_file.write(line + '\n')
        with self.open(self.file_path, encoding='cyrillic') as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    def test_open_with_wplus(self):
        self.create_file(self.file_path,
                         contents=u'старое содержание',
                         encoding='cyrillic')
        with self.open(self.file_path, 'r', encoding='cyrillic') as fake_file:
            self.assertEqual(u'старое содержание', fake_file.read())

        with self.open(self.file_path, 'w+', encoding='cyrillic') as fake_file:
            fake_file.write(u'новое содержание')
            fake_file.seek(0)
            self.assertTrue(u'новое содержание', fake_file.read())

    def test_open_with_append_flag(self):
        # FIXME: under Windows, line endings are not handled correctly
        self.skip_real_fs_failure(skip_posix=False)
        contents = [
            u'Калинка,\n',
            u'калинка,\n',
            u'калинка моя,\n'
        ]
        additional_contents = [
            u'В саду ягода-малинка,\n',
            u'малинка моя.\n'
        ]
        self.create_file(self.file_path, contents=''.join(contents),
                         encoding='cyrillic')
        with self.open(self.file_path, 'a', encoding='cyrillic') as fake_file:
            expected_error = (IOError if sys.version_info < (3,)
                              else io.UnsupportedOperation)
            self.assertRaises(expected_error, fake_file.read, 0)
            self.assertRaises(expected_error, fake_file.readline)
            self.assertEqual(len(''.join(contents)), fake_file.tell())
            fake_file.seek(0)
            self.assertEqual(0, fake_file.tell())
            fake_file.writelines(additional_contents)
        with self.open(self.file_path, encoding='cyrillic') as fake_file:
            self.assertEqual(contents + additional_contents, fake_file.readlines())

    def test_append_with_aplus(self):
        self.create_file(self.file_path,
                         contents=u'старое содержание',
                         encoding='cyrillic')
        fake_file = self.open(self.file_path, 'r', encoding='cyrillic')
        fake_file.close()

        with self.open(self.file_path, 'a+', encoding='cyrillic') as fake_file:
            self.assertEqual(17, fake_file.tell())
            fake_file.write(u'новое содержание')
            self.assertEqual(33, fake_file.tell())
            fake_file.seek(0)
            self.assertEqual(u'старое содержаниеновое содержание',
                             fake_file.read())

    def test_read_with_rplus(self):
        self.create_file(self.file_path,
                         contents=u'старое содержание здесь',
                         encoding='cyrillic')
        fake_file = self.open(self.file_path, 'r', encoding='cyrillic')
        fake_file.close()

        with self.open(self.file_path, 'r+', encoding='cyrillic') as fake_file:
            self.assertEqual(u'старое содержание здесь', fake_file.read())
            fake_file.seek(0)
            fake_file.write(u'новое  содержание')
            fake_file.seek(0)
            self.assertEqual(u'новое  содержание здесь', fake_file.read())


class OpenRealFileWithEncodingTest(OpenFileWithEncodingTest):
    def use_real_fs(self):
        return True


class OpenWithFileDescriptorTest(FakeFileOpenTestBase):
    @unittest.skipIf(sys.version_info < (3, 0),
                     'only tested on 3.0 or greater')
    def test_open_with_file_descriptor(self):
        file_path = self.make_path('this', 'file')
        self.create_file(file_path)
        fd = self.os.open(file_path, os.O_CREAT)
        self.assertEqual(fd, self.open(fd, 'r').fileno())

    @unittest.skipIf(sys.version_info < (3, 0),
                     'only tested on 3.0 or greater')
    def test_closefd_with_file_descriptor(self):
        file_path = self.make_path('this', 'file')
        self.create_file(file_path)
        fd = self.os.open(file_path, os.O_CREAT)
        fh = self.open(fd, 'r', closefd=False)
        fh.close()
        self.assertIsNotNone(self.filesystem.open_files[fd])
        fh = self.open(fd, 'r', closefd=True)
        fh.close()
        self.assertIsNone(self.filesystem.open_files[fd])


class OpenWithRealFileDescriptorTest(FakeFileOpenTestBase):
    def use_real_fs(self):
        return True


class OpenWithBinaryFlagsTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='!')
        self.open = fake_filesystem.FakeFileOpen(self.filesystem)
        self.os = fake_filesystem.FakeOsModule(self.filesystem)
        self.file_path = 'some_file'
        self.file_contents = b'real binary contents: \x1f\x8b'
        self.filesystem.create_file(self.file_path,
                                    contents=self.file_contents)

    def OpenFakeFile(self, mode):
        return self.open(self.file_path, mode=mode)

    def OpenFileAndSeek(self, mode):
        fake_file = self.open(self.file_path, mode=mode)
        fake_file.seek(0, 2)
        return fake_file

    def WriteAndReopenFile(self, fake_file, mode='rb', encoding=None):
        fake_file.write(self.file_contents)
        fake_file.close()
        args = {'mode': mode}
        if encoding:
            args['encoding'] = encoding
        return self.open(self.file_path, **args)

    def test_read_binary(self):
        fake_file = self.OpenFakeFile('rb')
        self.assertEqual(self.file_contents, fake_file.read())

    def test_write_binary(self):
        fake_file = self.OpenFileAndSeek('wb')
        self.assertEqual(0, fake_file.tell())
        fake_file = self.WriteAndReopenFile(fake_file, mode='rb')
        self.assertEqual(self.file_contents, fake_file.read())
        # Attempt to reopen the file in text mode
        fake_file = self.OpenFakeFile('wb')
        if sys.version_info >= (3, 0):
            fake_file = self.WriteAndReopenFile(fake_file, mode='r',
                                                encoding='ascii')
            self.assertRaises(UnicodeDecodeError, fake_file.read)
        else:
            fake_file = self.WriteAndReopenFile(fake_file, mode='r')
            self.assertEqual(self.file_contents, fake_file.read())

    def test_write_and_read_binary(self):
        fake_file = self.OpenFileAndSeek('w+b')
        self.assertEqual(0, fake_file.tell())
        fake_file = self.WriteAndReopenFile(fake_file, mode='rb')
        self.assertEqual(self.file_contents, fake_file.read())


class OpenWithIgnoredFlagsTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='!')
        self.open = fake_filesystem.FakeFileOpen(self.filesystem)
        self.os = fake_filesystem.FakeOsModule(self.filesystem)
        self.file_path = 'some_file'
        self.read_contents = self.file_contents = 'two\r\nlines'
        # For python 3.x, text file newlines are converted to \n
        if sys.version_info >= (3, 0):
            self.read_contents = 'two\nlines'
        self.filesystem.create_file(self.file_path,
                                    contents=self.file_contents)
        # It's reasonable to assume the file exists at this point

    def OpenFakeFile(self, mode):
        return self.open(self.file_path, mode=mode)

    def OpenFileAndSeek(self, mode):
        fake_file = self.open(self.file_path, mode=mode)
        fake_file.seek(0, 2)
        return fake_file

    def WriteAndReopenFile(self, fake_file, mode='r'):
        fake_file.write(self.file_contents)
        fake_file.close()
        return self.open(self.file_path, mode=mode)

    def test_read_text(self):
        fake_file = self.OpenFakeFile('rt')
        self.assertEqual(self.read_contents, fake_file.read())

    def test_read_universal_newlines(self):
        fake_file = self.OpenFakeFile('rU')
        self.assertEqual(self.read_contents, fake_file.read())

    def test_universal_newlines(self):
        fake_file = self.OpenFakeFile('U')
        self.assertEqual(self.read_contents, fake_file.read())

    def test_write_text(self):
        fake_file = self.OpenFileAndSeek('wt')
        self.assertEqual(0, fake_file.tell())
        fake_file = self.WriteAndReopenFile(fake_file)
        self.assertEqual(self.read_contents, fake_file.read())

    def test_write_and_read_text_binary(self):
        fake_file = self.OpenFileAndSeek('w+bt')
        self.assertEqual(0, fake_file.tell())
        if sys.version_info >= (3, 0):
            self.assertRaises(TypeError, fake_file.write, self.file_contents)
        else:
            fake_file = self.WriteAndReopenFile(fake_file, mode='rb')
            self.assertEqual(self.file_contents, fake_file.read())


class OpenWithInvalidFlagsTest(FakeFileOpenTestBase):
    def test_capital_r(self):
        self.assertRaises(ValueError, self.open, 'some_file', 'R')

    def test_capital_w(self):
        self.assertRaises(ValueError, self.open, 'some_file', 'W')

    def test_capital_a(self):
        self.assertRaises(ValueError, self.open, 'some_file', 'A')

    def test_lower_u(self):
        self.assertRaises(ValueError, self.open, 'some_file', 'u')

    def test_lower_rw(self):
        if self.is_python2 and sys.platform != 'win32':
            self.assert_raises_io_error(
                errno.ENOENT, self.open, 'some_file', 'rw')
        else:
            self.assertRaises(ValueError, self.open, 'some_file', 'rw')


class OpenWithInvalidFlagsRealFsTest(OpenWithInvalidFlagsTest):
    def use_real_fs(self):
        return True


class ResolvePathTest(FakeFileOpenTestBase):
    def __WriteToFile(self, file_name):
        fh = self.open(file_name, 'w')
        fh.write('x')
        fh.close()

    def test_none_filepath_raises_type_error(self):
        self.assertRaises(TypeError, self.open, None, 'w')

    def test_empty_filepath_raises_io_error(self):
        self.assertRaises(IOError, self.open, '', 'w')

    def test_normal_path(self):
        self.__WriteToFile('foo')
        self.assertTrue(self.filesystem.exists('foo'))

    def test_link_within_same_directory(self):
        self.skip_if_symlink_not_supported()
        final_target = '!foo!baz'
        self.filesystem.create_symlink('!foo!bar', 'baz')
        self.__WriteToFile('!foo!bar')
        self.assertTrue(self.filesystem.exists(final_target))
        self.assertEqual(1, self.os.stat(final_target)[stat.ST_SIZE])

    def test_link_to_sub_directory(self):
        self.skip_if_symlink_not_supported()
        final_target = '!foo!baz!bip'
        self.filesystem.create_dir('!foo!baz')
        self.filesystem.create_symlink('!foo!bar', 'baz!bip')
        self.__WriteToFile('!foo!bar')
        self.assertTrue(self.filesystem.exists(final_target))
        self.assertEqual(1, self.os.stat(final_target)[stat.ST_SIZE])
        self.assertTrue(self.filesystem.exists('!foo!baz'))
        # Make sure that intermediate directory got created.
        new_dir = self.filesystem.get_object('!foo!baz')
        self.assertTrue(stat.S_IFDIR & new_dir.st_mode)

    def test_link_to_parent_directory(self):
        self.skip_if_symlink_not_supported()
        final_target = '!baz!bip'
        self.filesystem.create_dir('!foo')
        self.filesystem.create_dir('!baz')
        self.filesystem.create_symlink('!foo!bar', '..!baz')
        self.__WriteToFile('!foo!bar!bip')
        self.assertTrue(self.filesystem.exists(final_target))
        self.assertEqual(1, self.os.stat(final_target)[stat.ST_SIZE])
        self.assertTrue(self.filesystem.exists('!foo!bar'))

    def test_link_to_absolute_path(self):
        self.skip_if_symlink_not_supported()
        final_target = '!foo!baz!bip'
        self.filesystem.create_dir('!foo!baz')
        self.filesystem.create_symlink('!foo!bar', final_target)
        self.__WriteToFile('!foo!bar')
        self.assertTrue(self.filesystem.exists(final_target))

    def test_relative_links_work_after_chdir(self):
        self.skip_if_symlink_not_supported()
        final_target = '!foo!baz!bip'
        self.filesystem.create_dir('!foo!baz')
        self.filesystem.create_symlink('!foo!bar', '.!baz!bip')
        self.assertEqual(final_target,
                         self.filesystem.resolve_path('!foo!bar'))

        self.assertTrue(self.os.path.islink('!foo!bar'))
        self.os.chdir('!foo')
        self.assertEqual('!foo', self.os.getcwd())
        self.assertTrue(self.os.path.islink('bar'))

        self.assertEqual('!foo!baz!bip',
                         self.filesystem.resolve_path('bar'))

        self.__WriteToFile('!foo!bar')
        self.assertTrue(self.filesystem.exists(final_target))

    def test_absolute_links_work_after_chdir(self):
        self.skip_if_symlink_not_supported()
        final_target = '!foo!baz!bip'
        self.filesystem.create_dir('!foo!baz')
        self.filesystem.create_symlink('!foo!bar', final_target)
        self.assertEqual(final_target,
                         self.filesystem.resolve_path('!foo!bar'))

        os_module = fake_filesystem.FakeOsModule(self.filesystem)
        self.assertTrue(os_module.path.islink('!foo!bar'))
        os_module.chdir('!foo')
        self.assertEqual('!foo', os_module.getcwd())
        self.assertTrue(os_module.path.islink('bar'))

        self.assertEqual('!foo!baz!bip',
                         self.filesystem.resolve_path('bar'))

        self.__WriteToFile('!foo!bar')
        self.assertTrue(self.filesystem.exists(final_target))

    def test_chdir_through_relative_link(self):
        self.skip_if_symlink_not_supported()
        self.filesystem.create_dir('!x!foo')
        self.filesystem.create_dir('!x!bar')
        self.filesystem.create_symlink('!x!foo!bar', '..!bar')
        self.assertEqual('!x!bar', self.filesystem.resolve_path('!x!foo!bar'))

        self.os.chdir('!x!foo')
        self.assertEqual('!x!foo', self.os.getcwd())
        self.assertEqual('!x!bar', self.filesystem.resolve_path('bar'))

        self.os.chdir('bar')
        self.assertEqual('!x!bar', self.os.getcwd())

    @unittest.skipIf(sys.version_info < (3, 3),
                     'file descriptor as path new in Python 3.3')
    def test_chdir_uses_open_fd_as_path(self):
        self.filesystem.is_windows_fs = False
        self.assert_raises_os_error(errno.EBADF, self.os.chdir, 5)
        dir_path = '!foo!bar'
        self.filesystem.create_dir(dir_path)

        path_des = self.os.open(dir_path, os.O_RDONLY)
        self.os.chdir(path_des)
        self.os.close(path_des)
        self.assertEqual(dir_path, self.os.getcwd())

    def test_read_link_to_link(self):
        # Write into the final link target and read back from a file which will
        # point to that.
        self.skip_if_symlink_not_supported()
        self.filesystem.create_symlink('!foo!bar', 'link')
        self.filesystem.create_symlink('!foo!link', 'baz')
        self.__WriteToFile('!foo!baz')
        fh = self.open('!foo!bar', 'r')
        self.assertEqual('x', fh.read())

    def test_write_link_to_link(self):
        self.skip_if_symlink_not_supported()
        final_target = '!foo!baz'
        self.filesystem.create_symlink('!foo!bar', 'link')
        self.filesystem.create_symlink('!foo!link', 'baz')
        self.__WriteToFile('!foo!bar')
        self.assertTrue(self.filesystem.exists(final_target))

    def test_multiple_links(self):
        self.skip_if_symlink_not_supported()
        self.os.makedirs('!a!link1!c!link2')

        self.filesystem.create_symlink('!a!b', 'link1')
        self.assertEqual('!a!link1', self.filesystem.resolve_path('!a!b'))
        self.assertEqual('!a!link1!c', self.filesystem.resolve_path('!a!b!c'))

        self.filesystem.create_symlink('!a!link1!c!d', 'link2')
        self.assertTrue(self.filesystem.exists('!a!link1!c!d'))
        self.assertTrue(self.filesystem.exists('!a!b!c!d'))

        final_target = '!a!link1!c!link2!e'
        self.assertFalse(self.filesystem.exists(final_target))
        self.__WriteToFile('!a!b!c!d!e')
        self.assertTrue(self.filesystem.exists(final_target))

    def test_utime_link(self):
        """os.utime() and os.stat() via symbolic link (issue #49)"""
        self.skip_if_symlink_not_supported()
        self.filesystem.create_dir('!foo!baz')
        self.__WriteToFile('!foo!baz!bip')
        link_name = '!foo!bar'
        self.filesystem.create_symlink(link_name, '!foo!baz!bip')

        self.os.utime(link_name, (1, 2))
        st = self.os.stat(link_name)
        self.assertEqual(1, st.st_atime)
        self.assertEqual(2, st.st_mtime)
        self.os.utime(link_name, (3, 4))
        st = self.os.stat(link_name)
        self.assertEqual(3, st.st_atime)
        self.assertEqual(4, st.st_mtime)

    def test_too_many_links(self):
        self.filesystem.is_windows_fs = False
        self.filesystem.create_symlink('!a!loop', 'loop')
        self.assertFalse(self.filesystem.exists('!a!loop'))

    def test_that_drive_letters_are_preserved(self):
        self.filesystem.is_windows_fs = True
        self.assertEqual('c:!foo!bar',
                         self.filesystem.resolve_path('c:!foo!!bar'))

    @unittest.skipIf(sys.version_info < (2, 7, 8),
                     'UNC path support since Python 2.7.8')
    def test_that_unc_paths_are_preserved(self):
        self.filesystem.is_windows_fs = True
        self.assertEqual('!!foo!bar!baz',
                         self.filesystem.resolve_path('!!foo!bar!baz!!'))


class PathManipulationTestBase(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='|')


class CollapsePathPipeSeparatorTest(PathManipulationTestBase):
    """Tests CollapsePath (mimics os.path.normpath) using |
    as path separator."""

    def test_empty_path_becomes_dot_path(self):
        self.assertEqual('.', self.filesystem.normpath(''))

    def test_dot_path_unchanged(self):
        self.assertEqual('.', self.filesystem.normpath('.'))

    def test_slashes_are_not_collapsed(self):
        """Tests that '/' is not treated specially if the
        path separator is '|'.

    In particular, multiple slashes should not be collapsed.
    """
        self.assertEqual('/', self.filesystem.normpath('/'))
        self.assertEqual('/////', self.filesystem.normpath('/////'))

    def test_root_path(self):
        self.assertEqual('|', self.filesystem.normpath('|'))

    def test_multiple_separators_collapsed_into_root_path(self):
        self.assertEqual('|', self.filesystem.normpath('|||||'))

    def test_all_dot_paths_removed_but_one(self):
        self.assertEqual('.', self.filesystem.normpath('.|.|.|.'))

    def test_all_dot_paths_removed_if_another_path_component_exists(self):
        self.assertEqual('|', self.filesystem.normpath('|.|.|.|'))
        self.assertEqual('foo|bar', self.filesystem.normpath('foo|.|.|.|bar'))

    def test_ignores_up_level_references_starting_from_root(self):
        self.assertEqual('|', self.filesystem.normpath('|..|..|..|'))
        self.assertEqual(
            '|', self.filesystem.normpath('|..|..|foo|bar|..|..|'))
        self.filesystem.is_windows_fs = False  # shall not be handled as UNC path
        self.assertEqual('|', self.filesystem.normpath('||..|.|..||'))

    def test_conserves_up_level_references_starting_from_current_directory(self):
        self.assertEqual(
            '..|..', self.filesystem.normpath('..|foo|bar|..|..|..'))

    def test_combine_dot_and_up_level_references_in_absolute_path(self):
        self.assertEqual(
            '|yes', self.filesystem.normpath('|||||.|..|||yes|no|..|.|||'))

    def test_dots_in_path_collapses_to_last_path(self):
        self.assertEqual(
            'bar', self.filesystem.normpath('foo|..|bar'))
        self.assertEqual(
            'bar', self.filesystem.normpath('foo|..|yes|..|no|..|bar'))


class SplitPathTest(PathManipulationTestBase):
    """Tests SplitPath (which mimics os.path.split)
    using | as path separator."""

    def test_empty_path(self):
        self.assertEqual(('', ''), self.filesystem.splitpath(''))

    def test_no_separators(self):
        self.assertEqual(('', 'ab'), self.filesystem.splitpath('ab'))

    def test_slashes_do_not_split(self):
        """Tests that '/' is not treated specially if the
        path separator is '|'."""
        self.assertEqual(('', 'a/b'), self.filesystem.splitpath('a/b'))

    def test_eliminate_trailing_separators_from_head(self):
        self.assertEqual(('a', 'b'), self.filesystem.splitpath('a|b'))
        self.assertEqual(('a', 'b'), self.filesystem.splitpath('a|||b'))
        self.assertEqual(('|a', 'b'), self.filesystem.splitpath('|a||b'))
        self.assertEqual(('a|b', 'c'), self.filesystem.splitpath('a|b|c'))
        self.assertEqual(('|a|b', 'c'), self.filesystem.splitpath('|a|b|c'))

    def test_root_separator_is_not_stripped(self):
        self.assertEqual(('|', ''), self.filesystem.splitpath('|||'))
        self.assertEqual(('|', 'a'), self.filesystem.splitpath('|a'))
        self.assertEqual(('|', 'a'), self.filesystem.splitpath('|||a'))

    def test_empty_tail_if_path_ends_in_separator(self):
        self.assertEqual(('a|b', ''), self.filesystem.splitpath('a|b|'))

    def test_empty_path_components_are_preserved_in_head(self):
        self.assertEqual(('|a||b', 'c'), self.filesystem.splitpath('|a||b||c'))


class JoinPathTest(PathManipulationTestBase):
    """Tests JoinPath (which mimics os.path.join) using | as path separator."""

    def test_one_empty_component(self):
        self.assertEqual('', self.filesystem.joinpaths(''))

    def test_multiple_empty_components(self):
        self.assertEqual('', self.filesystem.joinpaths('', '', ''))

    def test_separators_not_stripped_from_single_component(self):
        self.assertEqual('||a||', self.filesystem.joinpaths('||a||'))

    def test_one_separator_added_between_components(self):
        self.assertEqual('a|b|c|d',
                         self.filesystem.joinpaths('a', 'b', 'c', 'd'))

    def test_no_separator_added_for_components_ending_in_separator(self):
        self.assertEqual('a|b|c', self.filesystem.joinpaths('a|', 'b|', 'c'))
        self.assertEqual('a|||b|||c',
                         self.filesystem.joinpaths('a|||', 'b|||', 'c'))

    def test_components_preceding_absolute_component_are_ignored(self):
        self.assertEqual('|c|d',
                         self.filesystem.joinpaths('a', '|b', '|c', 'd'))

    def test_one_separator_added_for_trailing_empty_components(self):
        self.assertEqual('a|', self.filesystem.joinpaths('a', ''))
        self.assertEqual('a|', self.filesystem.joinpaths('a', '', ''))

    def test_no_separator_added_for_leading_empty_components(self):
        self.assertEqual('a', self.filesystem.joinpaths('', 'a'))

    def test_internal_empty_components_ignored(self):
        self.assertEqual('a|b', self.filesystem.joinpaths('a', '', 'b'))
        self.assertEqual('a|b|', self.filesystem.joinpaths('a|', '', 'b|'))


class PathSeparatorTest(TestCase):
    def test_os_path_sep_matches_fake_filesystem_separator(self):
        filesystem = fake_filesystem.FakeFilesystem(path_separator='!')
        fake_os = fake_filesystem.FakeOsModule(filesystem)
        self.assertEqual('!', fake_os.sep)
        self.assertEqual('!', fake_os.path.sep)


class NormalizeCaseTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.filesystem.is_case_sensitive = False

    def test_normalize_case(self):
        self.filesystem.create_file('/Foo/Bar')
        self.assertEqual('/Foo/Bar',
                         self.filesystem._original_path('/foo/bar'))
        self.assertEqual('/Foo/Bar',
                         self.filesystem._original_path('/FOO/BAR'))

    def test_normalize_case_for_drive(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.create_file('C:/Foo/Bar')
        self.assertEqual('C:/Foo/Bar',
                         self.filesystem._original_path('c:/foo/bar'))
        self.assertEqual('C:/Foo/Bar',
                         self.filesystem._original_path('C:/FOO/BAR'))

    def test_normalize_case_for_non_existing_file(self):
        self.filesystem.create_dir('/Foo/Bar')
        self.assertEqual('/Foo/Bar/baz',
                         self.filesystem._original_path('/foo/bar/baz'))
        self.assertEqual('/Foo/Bar/BAZ',
                         self.filesystem._original_path('/FOO/BAR/BAZ'))

    @unittest.skipIf(not TestCase.is_windows,
                     'Regression test for Windows problem only')
    def test_normalize_case_for_lazily_added_empty_file(self):
        # regression test for specific issue with added empty real files
        filesystem = fake_filesystem.FakeFilesystem()
        real_dir_path = os.path.join(os.path.dirname(__file__), 'pyfakefs')
        filesystem.add_real_directory(real_dir_path)
        initPyPath = os.path.join(real_dir_path, '__init__.py')
        self.assertEqual(initPyPath,
                         filesystem._original_path(initPyPath.upper()))


class AlternativePathSeparatorTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='!')
        self.filesystem.alternative_path_separator = '?'

    def test_initial_value(self):
        filesystem = fake_filesystem.FakeFilesystem()
        if self.is_windows:
            self.assertEqual('/', filesystem.alternative_path_separator)
        else:
            self.assertIsNone(filesystem.alternative_path_separator)

        filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.assertIsNone(filesystem.alternative_path_separator)

    def test_alt_sep(self):
        fake_os = fake_filesystem.FakeOsModule(self.filesystem)
        self.assertEqual('?', fake_os.altsep)
        self.assertEqual('?', fake_os.path.altsep)

    def test_collapse_path_with_mixed_separators(self):
        self.assertEqual('!foo!bar', self.filesystem.normpath('!foo??bar'))

    def test_normalize_path_with_mixed_separators(self):
        path = 'foo?..?bar'
        self.assertEqual('!bar', self.filesystem.absnormpath(path))

    def test_exists_with_mixed_separators(self):
        self.filesystem.create_file('?foo?bar?baz')
        self.filesystem.create_file('!foo!bar!xyzzy!plugh')
        self.assertTrue(self.filesystem.exists('!foo!bar!baz'))
        self.assertTrue(self.filesystem.exists('?foo?bar?xyzzy?plugh'))


class DriveLetterSupportTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='!')
        self.filesystem.is_windows_fs = True

    def test_initial_value(self):
        filesystem = fake_filesystem.FakeFilesystem()
        if self.is_windows:
            self.assertTrue(filesystem.is_windows_fs)
        else:
            self.assertFalse(filesystem.is_windows_fs)

    def test_collapse_path(self):
        self.assertEqual('c:!foo!bar',
                         self.filesystem.normpath('c:!!foo!!bar'))

    @unittest.skipIf(sys.version_info < (2, 7, 8),
                     'UNC path support since Python 2.7.8')
    def test_collapse_unc_path(self):
        self.assertEqual('!!foo!bar!baz',
                         self.filesystem.normpath('!!foo!bar!!baz!!'))

    def test_normalize_path_str(self):
        self.filesystem.cwd = u''
        self.assertEqual(u'c:!foo!bar',
                         self.filesystem.absnormpath(u'c:!foo!!bar'))
        self.filesystem.cwd = u'c:!foo'
        self.assertEqual(u'c:!foo!bar', self.filesystem.absnormpath(u'bar'))

    def test_normalize_path_bytes(self):
        self.filesystem.cwd = b''
        self.assertEqual(b'c:!foo!bar',
                         self.filesystem.absnormpath(b'c:!foo!!bar'))
        self.filesystem.cwd = b'c:!foo'
        self.assertEqual(b'c:!foo!bar', self.filesystem.absnormpath(b'bar'))

    def test_split_path_str(self):
        self.assertEqual((u'c:!foo', u'bar'),
                         self.filesystem.splitpath(u'c:!foo!bar'))
        self.assertEqual((u'c:!', u'foo'),
                         self.filesystem.splitpath(u'c:!foo'))
        self.assertEqual((u'!foo', u'bar'),
                         self.filesystem.splitpath(u'!foo!bar'))
        self.assertEqual((u'!', u'foo'),
                         self.filesystem.splitpath(u'!foo'))
        self.assertEqual((u'c:foo', u'bar'),
                         self.filesystem.splitpath(u'c:foo!bar'))
        self.assertEqual((u'c:', u'foo'),
                         self.filesystem.splitpath(u'c:foo'))
        self.assertEqual((u'foo', u'bar'),
                         self.filesystem.splitpath(u'foo!bar'))

    def test_split_path_bytes(self):
        self.assertEqual((b'c:!foo', b'bar'),
                         self.filesystem.splitpath(b'c:!foo!bar'))
        self.assertEqual((b'c:!', b'foo'),
                         self.filesystem.splitpath(b'c:!foo'))
        self.assertEqual((b'!foo', b'bar'),
                         self.filesystem.splitpath(b'!foo!bar'))
        self.assertEqual((b'!', b'foo'),
                         self.filesystem.splitpath(b'!foo'))
        self.assertEqual((b'c:foo', b'bar'),
                         self.filesystem.splitpath(b'c:foo!bar'))
        self.assertEqual((b'c:', b'foo'),
                         self.filesystem.splitpath(b'c:foo'))
        self.assertEqual((b'foo', b'bar'),
                         self.filesystem.splitpath(b'foo!bar'))

    def test_characters_before_root_ignored_in_join_paths(self):
        self.assertEqual('c:d', self.filesystem.joinpaths('b', 'c:', 'd'))

    def test_resolve_path(self):
        self.assertEqual('c:!foo!bar',
                         self.filesystem.resolve_path('c:!foo!bar'))

    def test_get_path_components(self):
        self.assertEqual(['c:', 'foo', 'bar'],
                         self.filesystem._path_components('c:!foo!bar'))
        self.assertEqual(['c:'], self.filesystem._path_components('c:'))

    def test_split_drive_str(self):
        self.assertEqual((u'c:', u'!foo!bar'),
                         self.filesystem.splitdrive(u'c:!foo!bar'))
        self.assertEqual((u'', u'!foo!bar'),
                         self.filesystem.splitdrive(u'!foo!bar'))
        self.assertEqual((u'c:', u'foo!bar'),
                         self.filesystem.splitdrive(u'c:foo!bar'))
        self.assertEqual((u'', u'foo!bar'),
                         self.filesystem.splitdrive(u'foo!bar'))

    def test_split_drive_bytes(self):
        self.assertEqual((b'c:', b'!foo!bar'),
                         self.filesystem.splitdrive(b'c:!foo!bar'))
        self.assertEqual((b'', b'!foo!bar'),
                         self.filesystem.splitdrive(b'!foo!bar'))

    @unittest.skipIf(sys.version_info < (2, 7, 8),
                     'UNC path support since Python 2.7.8')
    def test_split_drive_with_unc_path(self):
        self.assertEqual(('!!foo!bar', '!baz'),
                         self.filesystem.splitdrive('!!foo!bar!baz'))
        self.assertEqual(('', '!!foo'), self.filesystem.splitdrive('!!foo'))
        self.assertEqual(('', '!!foo!!bar'),
                         self.filesystem.splitdrive('!!foo!!bar'))
        self.assertEqual(('!!foo!bar', '!!'),
                         self.filesystem.splitdrive('!!foo!bar!!'))


class DiskSpaceTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='!',
                                                         total_size=100)
        self.os = fake_filesystem.FakeOsModule(self.filesystem)

    def test_disk_usage_on_file_creation(self):
        fake_open = fake_filesystem.FakeFileOpen(self.filesystem)

        total_size = 100
        self.filesystem.add_mount_point('mount', total_size)

        def create_too_large_file():
            with fake_open('!mount!file', 'w') as dest:
                dest.write('a' * (total_size + 1))

        self.assertRaises((OSError, IOError), create_too_large_file)

        self.assertEqual(0, self.filesystem.get_disk_usage('!mount').used)

        with fake_open('!mount!file', 'w') as dest:
            dest.write('a' * total_size)

        self.assertEqual(total_size,
                         self.filesystem.get_disk_usage('!mount').used)

    def test_file_system_size_after_large_file_creation(self):
        filesystem = fake_filesystem.FakeFilesystem(path_separator='!',
                                                    total_size=1024 * 1024 * 1024 * 100)
        filesystem.create_file('!foo!baz', st_size=1024 * 1024 * 1024 * 10)
        self.assertEqual((1024 * 1024 * 1024 * 100,
                          1024 * 1024 * 1024 * 10,
                          1024 * 1024 * 1024 * 90),
                         filesystem.get_disk_usage())

    def test_file_system_size_after_binary_file_creation(self):
        self.filesystem.create_file('!foo!bar', contents=b'xyzzy')
        self.assertEqual((100, 5, 95), self.filesystem.get_disk_usage())

    def test_file_system_size_after_ascii_string_file_creation(self):
        self.filesystem.create_file('!foo!bar', contents=u'complicated')
        self.assertEqual((100, 11, 89), self.filesystem.get_disk_usage())

    def testFileSystemSizeAfter2ByteUnicodeStringFileCreation(self):
        self.filesystem.create_file('!foo!bar', contents=u'сложно',
                                    encoding='utf-8')
        self.assertEqual((100, 12, 88), self.filesystem.get_disk_usage())

    def testFileSystemSizeAfter3ByteUnicodeStringFileCreation(self):
        self.filesystem.create_file('!foo!bar', contents=u'複雑',
                                    encoding='utf-8')
        self.assertEqual((100, 6, 94), self.filesystem.get_disk_usage())

    def test_file_system_size_after_file_deletion(self):
        self.filesystem.create_file('!foo!bar', contents=b'xyzzy')
        self.filesystem.create_file('!foo!baz', st_size=20)
        self.filesystem.remove_object('!foo!bar')
        self.assertEqual((100, 20, 80), self.filesystem.get_disk_usage())

    def test_file_system_size_after_directory_removal(self):
        self.filesystem.create_file('!foo!bar', st_size=10)
        self.filesystem.create_file('!foo!baz', st_size=20)
        self.filesystem.create_file('!foo1!bar', st_size=40)
        self.filesystem.remove_object('!foo')
        self.assertEqual((100, 40, 60), self.filesystem.get_disk_usage())

    def test_creating_file_with_fitting_content(self):
        initial_usage = self.filesystem.get_disk_usage()

        try:
            self.filesystem.create_file('!foo!bar', contents=b'a' * 100)
        except IOError:
            self.fail(
                'File with contents fitting into disk space could not be written.')

        self.assertEqual(initial_usage.used + 100,
                         self.filesystem.get_disk_usage().used)

    def test_creating_file_with_content_too_large(self):
        def create_large_file():
            self.filesystem.create_file('!foo!bar', contents=b'a' * 101)

        initial_usage = self.filesystem.get_disk_usage()

        self.assertRaises(IOError, create_large_file)

        self.assertEqual(initial_usage, self.filesystem.get_disk_usage())

    def test_creating_file_with_fitting_size(self):
        initial_usage = self.filesystem.get_disk_usage()

        try:
            self.filesystem.create_file('!foo!bar', st_size=100)
        except IOError:
            self.fail(
                'File with size fitting into disk space could not be written.')

        self.assertEqual(initial_usage.used + 100,
                         self.filesystem.get_disk_usage().used)

    def test_creating_file_with_size_too_large(self):
        initial_usage = self.filesystem.get_disk_usage()

        def create_large_file():
            self.filesystem.create_file('!foo!bar', st_size=101)

        self.assertRaises(IOError, create_large_file)

        self.assertEqual(initial_usage, self.filesystem.get_disk_usage())

    def test_resize_file_with_fitting_size(self):
        file_object = self.filesystem.create_file('!foo!bar', st_size=50)
        try:
            file_object.set_large_file_size(100)
            file_object.set_contents(b'a' * 100)
        except IOError:
            self.fail(
                'Resizing file failed although disk space was sufficient.')

    def test_resize_file_with_size_too_large(self):
        file_object = self.filesystem.create_file('!foo!bar', st_size=50)
        self.assert_raises_io_error(errno.ENOSPC, file_object.set_large_file_size,
                                    200)
        self.assert_raises_io_error(errno.ENOSPC, file_object.set_contents,
                                    'a' * 150)

    def test_file_system_size_after_directory_rename(self):
        self.filesystem.create_file('!foo!bar', st_size=20)
        self.os.rename('!foo', '!baz')
        self.assertEqual(20, self.filesystem.get_disk_usage().used)

    def test_file_system_size_after_file_rename(self):
        self.filesystem.create_file('!foo!bar', st_size=20)
        self.os.rename('!foo!bar', '!foo!baz')
        self.assertEqual(20, self.filesystem.get_disk_usage().used)

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def test_that_hard_link_does_not_change_used_size(self):
        file1_path = 'test_file1'
        file2_path = 'test_file2'
        self.filesystem.create_file(file1_path, st_size=20)
        self.assertEqual(20, self.filesystem.get_disk_usage().used)
        # creating a hard link shall not increase used space
        self.os.link(file1_path, file2_path)
        self.assertEqual(20, self.filesystem.get_disk_usage().used)
        # removing a file shall not decrease used space
        # if a hard link still exists
        self.os.unlink(file1_path)
        self.assertEqual(20, self.filesystem.get_disk_usage().used)
        self.os.unlink(file2_path)
        self.assertEqual(0, self.filesystem.get_disk_usage().used)

    def test_that_the_size_of_correct_mount_point_is_used(self):
        self.filesystem.add_mount_point('!mount_limited', total_size=50)
        self.filesystem.add_mount_point('!mount_unlimited')

        self.assert_raises_io_error(errno.ENOSPC,
                                    self.filesystem.create_file,
                                    '!mount_limited!foo', st_size=60)
        self.assert_raises_io_error(errno.ENOSPC, self.filesystem.create_file,
                                    '!bar', st_size=110)

        try:
            self.filesystem.create_file('!foo', st_size=60)
            self.filesystem.create_file('!mount_limited!foo', st_size=40)
            self.filesystem.create_file('!mount_unlimited!foo',
                                        st_size=1000000)
        except IOError:
            self.fail('File with contents fitting into '
                      'disk space could not be written.')

    def test_that_disk_usage_of_correct_mount_point_is_used(self):
        self.filesystem.add_mount_point('!mount1', total_size=20)
        self.filesystem.add_mount_point('!mount1!bar!mount2', total_size=50)

        self.filesystem.create_file('!foo!bar', st_size=10)
        self.filesystem.create_file('!mount1!foo!bar', st_size=10)
        self.filesystem.create_file('!mount1!bar!mount2!foo!bar', st_size=10)

        self.assertEqual(90, self.filesystem.get_disk_usage('!foo').free)
        self.assertEqual(10,
                         self.filesystem.get_disk_usage('!mount1!foo').free)
        self.assertEqual(40, self.filesystem.get_disk_usage(
            '!mount1!bar!mount2').free)

    def test_set_larger_disk_size(self):
        self.filesystem.add_mount_point('!mount1', total_size=20)
        self.assert_raises_io_error(errno.ENOSPC,
                                    self.filesystem.create_file, '!mount1!foo',
                                    st_size=100)
        self.filesystem.set_disk_usage(total_size=200, path='!mount1')
        self.filesystem.create_file('!mount1!foo', st_size=100)
        self.assertEqual(100,
                         self.filesystem.get_disk_usage('!mount1!foo').free)

    def test_set_smaller_disk_size(self):
        self.filesystem.add_mount_point('!mount1', total_size=200)
        self.filesystem.create_file('!mount1!foo', st_size=100)
        self.assert_raises_io_error(errno.ENOSPC,
                                    self.filesystem.set_disk_usage, total_size=50,
                                    path='!mount1')
        self.filesystem.set_disk_usage(total_size=150, path='!mount1')
        self.assertEqual(50,
                         self.filesystem.get_disk_usage('!mount1!foo').free)

    def test_disk_size_on_unlimited_disk(self):
        self.filesystem.add_mount_point('!mount1')
        self.filesystem.create_file('!mount1!foo', st_size=100)
        self.filesystem.set_disk_usage(total_size=1000, path='!mount1')
        self.assertEqual(900,
                         self.filesystem.get_disk_usage('!mount1!foo').free)

    def test_disk_size_on_auto_mounted_drive_on_file_creation(self):
        self.filesystem.is_windows_fs = True
        # drive d: shall be auto-mounted and the used size adapted
        self.filesystem.create_file('d:!foo!bar', st_size=100)
        self.filesystem.set_disk_usage(total_size=1000, path='d:')
        self.assertEqual(self.filesystem.get_disk_usage('d:!foo').free, 900)

    def test_disk_size_on_auto_mounted_drive_on_directory_creation(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.create_dir('d:!foo!bar')
        self.filesystem.create_file('d:!foo!bar!baz', st_size=100)
        self.filesystem.create_file('d:!foo!baz', st_size=100)
        self.filesystem.set_disk_usage(total_size=1000, path='d:')
        self.assertEqual(self.filesystem.get_disk_usage('d:!foo').free, 800)

    @unittest.skipIf(sys.version_info < (3, 0),
                     'Tests byte contents in Python3')
    def test_copying_preserves_byte_contents(self):
        source_file = self.filesystem.create_file('foo', contents=b'somebytes')
        dest_file = self.filesystem.create_file('bar')
        dest_file.set_contents(source_file.contents)
        self.assertEqual(dest_file.contents, source_file.contents)


class MountPointTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='!',
                                                         total_size=100)
        self.filesystem.add_mount_point('!foo')
        self.filesystem.add_mount_point('!bar')
        self.filesystem.add_mount_point('!foo!baz')

    def test_that_new_mount_points_get_new_device_number(self):
        self.assertEqual(1, self.filesystem.get_object('!').st_dev)
        self.assertEqual(2, self.filesystem.get_object('!foo').st_dev)
        self.assertEqual(3, self.filesystem.get_object('!bar').st_dev)
        self.assertEqual(4, self.filesystem.get_object('!foo!baz').st_dev)

    def test_that_new_directories_get_correct_device_number(self):
        self.assertEqual(1, self.filesystem.create_dir('!foo1!bar').st_dev)
        self.assertEqual(2, self.filesystem.create_dir('!foo!bar').st_dev)
        self.assertEqual(4,
                         self.filesystem.create_dir('!foo!baz!foo!bar').st_dev)

    def test_that_new_files_get_correct_device_number(self):
        self.assertEqual(1, self.filesystem.create_file('!foo1!bar').st_dev)
        self.assertEqual(2, self.filesystem.create_file('!foo!bar').st_dev)
        self.assertEqual(4, self.filesystem.create_file(
            '!foo!baz!foo!bar').st_dev)

    def test_that_mount_point_cannot_be_added_twice(self):
        self.assert_raises_os_error(errno.EEXIST, self.filesystem.add_mount_point,
                                    '!foo')
        self.assert_raises_os_error(errno.EEXIST, self.filesystem.add_mount_point,
                                    '!foo!')

    def test_that_drives_are_auto_mounted(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.create_dir('d:!foo!bar')
        self.filesystem.create_file('d:!foo!baz')
        self.filesystem.create_file('z:!foo!baz')
        self.assertEqual(5, self.filesystem.get_object('d:').st_dev)
        self.assertEqual(5, self.filesystem.get_object('d:!foo!bar').st_dev)
        self.assertEqual(5, self.filesystem.get_object('d:!foo!baz').st_dev)
        self.assertEqual(6, self.filesystem.get_object('z:!foo!baz').st_dev)

    def test_that_drives_are_auto_mounted_case_insensitive(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.is_case_sensitive = False
        self.filesystem.create_dir('D:!foo!bar')
        self.filesystem.create_file('e:!foo!baz')
        self.assertEqual(5, self.filesystem.get_object('D:').st_dev)
        self.assertEqual(5, self.filesystem.get_object('d:!foo!bar').st_dev)
        self.assertEqual(6, self.filesystem.get_object('e:!foo').st_dev)
        self.assertEqual(6, self.filesystem.get_object('E:!Foo!Baz').st_dev)

    @unittest.skipIf(sys.version_info < (2, 7, 8),
                     'UNC path support since Python 2.7.8')
    def test_that_unc_paths_are_auto_mounted(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.create_dir('!!foo!bar!baz')
        self.filesystem.create_file('!!foo!bar!bip!bop')
        self.assertEqual(5, self.filesystem.get_object('!!foo!bar').st_dev)
        self.assertEqual(5, self.filesystem.get_object(
            '!!foo!bar!bip!bop').st_dev)


class RealFileSystemAccessTest(TestCase):
    def setUp(self):
        # use the real path separator to work with the real file system
        self.filesystem = fake_filesystem.FakeFilesystem()
        self.fake_open = fake_filesystem.FakeFileOpen(self.filesystem)

    def test_add_non_existing_real_file_raises(self):
        nonexisting_path = os.path.join('nonexisting', 'test.txt')
        self.assertRaises(OSError, self.filesystem.add_real_file,
                          nonexisting_path)
        self.assertFalse(self.filesystem.exists(nonexisting_path))

    def test_add_non_existing_real_directory_raises(self):
        nonexisting_path = '/nonexisting'
        self.assert_raises_io_error(errno.ENOENT,
                                    self.filesystem.add_real_directory,
                                    nonexisting_path)
        self.assertFalse(self.filesystem.exists(nonexisting_path))

    def test_existing_fake_file_raises(self):
        real_file_path = __file__
        self.filesystem.create_file(real_file_path)
        self.assert_raises_os_error(errno.EEXIST, self.filesystem.add_real_file,
                                    real_file_path)

    def test_existing_fake_directory_raises(self):
        real_dir_path = os.path.dirname(__file__)
        self.filesystem.create_dir(real_dir_path)
        self.assert_raises_os_error(errno.EEXIST,
                                    self.filesystem.add_real_directory,
                                    real_dir_path)

    def check_fake_file_stat(self, fake_file, real_file_path):
        self.assertTrue(self.filesystem.exists(real_file_path))
        real_stat = os.stat(real_file_path)
        self.assertIsNone(fake_file._byte_contents)
        self.assertEqual(fake_file.st_size, real_stat.st_size)
        self.assertAlmostEqual(fake_file.st_ctime, real_stat.st_ctime,
                               places=5)
        self.assertAlmostEqual(fake_file.st_atime, real_stat.st_atime,
                               places=5)
        self.assertAlmostEqual(fake_file.st_mtime, real_stat.st_mtime,
                               places=5)
        self.assertEqual(fake_file.st_uid, real_stat.st_uid)
        self.assertEqual(fake_file.st_gid, real_stat.st_gid)

    def check_read_only_file(self, fake_file, real_file_path):
        with open(real_file_path, 'rb') as f:
            real_contents = f.read()
        self.assertEqual(fake_file.byte_contents, real_contents)
        self.assert_raises_io_error(errno.EACCES, self.fake_open, real_file_path,
                                    'w')

    def check_writable_file(self, fake_file, real_file_path):
        with open(real_file_path, 'rb') as f:
            real_contents = f.read()
        self.assertEqual(fake_file.byte_contents, real_contents)
        with self.fake_open(real_file_path, 'wb') as f:
            f.write(b'test')
        with open(real_file_path, 'rb') as f:
            real_contents1 = f.read()
        self.assertEqual(real_contents1, real_contents)
        with self.fake_open(real_file_path, 'rb') as f:
            fake_contents = f.read()
        self.assertEqual(fake_contents, b'test')

    def test_add_existing_real_file_read_only(self):
        real_file_path = __file__
        fake_file = self.filesystem.add_real_file(real_file_path)
        self.check_fake_file_stat(fake_file, real_file_path)
        self.assertEqual(fake_file.st_mode & 0o333, 0)
        self.check_read_only_file(fake_file, real_file_path)

    def test_add_existing_real_file_read_write(self):
        real_file_path = os.path.realpath(__file__)
        fake_file = self.filesystem.add_real_file(real_file_path,
                                                  read_only=False)

        self.check_fake_file_stat(fake_file, real_file_path)
        self.assertEqual(fake_file.st_mode, os.stat(real_file_path).st_mode)
        self.check_writable_file(fake_file, real_file_path)

    def test_add_existing_real_directory_read_only(self):
        real_dir_path = os.path.join(os.path.dirname(__file__), 'pyfakefs')
        self.filesystem.add_real_directory(real_dir_path)
        self.assertTrue(self.filesystem.exists(real_dir_path))
        self.assertTrue(self.filesystem.exists(
            os.path.join(real_dir_path, 'fake_filesystem.py')))
        self.assertTrue(self.filesystem.exists(
            os.path.join(real_dir_path, 'fake_pathlib.py')))

        file_path = os.path.join(real_dir_path, 'fake_filesystem_shutil.py')
        fake_file = self.filesystem.resolve(file_path)
        self.check_fake_file_stat(fake_file, file_path)
        self.check_read_only_file(fake_file, file_path)

    def test_add_existing_real_directory_tree(self):
        real_dir_path = os.path.dirname(__file__)
        self.filesystem.add_real_directory(real_dir_path)
        self.assertTrue(
            self.filesystem.exists(
                os.path.join(real_dir_path, 'fake_filesystem_test.py')))
        self.assertTrue(
            self.filesystem.exists(
                os.path.join(real_dir_path, 'pyfakefs', 'fake_filesystem.py')))
        self.assertTrue(
            self.filesystem.exists(
                os.path.join(real_dir_path, 'pyfakefs', '__init__.py')))

    def test_get_object_from_lazily_added_real_directory(self):
        self.filesystem.is_case_sensitive = True
        real_dir_path = os.path.dirname(__file__)
        self.filesystem.add_real_directory(real_dir_path)
        self.assertTrue(self.filesystem.get_object(
            os.path.join(real_dir_path, 'pyfakefs', 'fake_filesystem.py')))
        self.assertTrue(
            self.filesystem.get_object(
                os.path.join(real_dir_path, 'pyfakefs', '__init__.py')))

    def test_add_existing_real_directory_lazily(self):
        disk_size = 1024 * 1024 * 1024
        real_dir_path = os.path.join(os.path.dirname(__file__), 'pyfakefs')
        self.filesystem.set_disk_usage(disk_size, real_dir_path)
        self.filesystem.add_real_directory(real_dir_path)

        # the directory contents have not been read, the the disk usage
        # has not changed
        self.assertEqual(disk_size,
                         self.filesystem.get_disk_usage(real_dir_path).free)
        # checking for existence shall read the directory contents
        self.assertTrue(
            self.filesystem.get_object(
                os.path.join(real_dir_path, 'fake_filesystem.py')))
        # so now the free disk space shall have decreased
        self.assertGreater(disk_size,
                           self.filesystem.get_disk_usage(real_dir_path).free)

    def test_add_existing_real_directory_not_lazily(self):
        disk_size = 1024 * 1024 * 1024
        real_dir_path = os.path.join(os.path.dirname(__file__), 'pyfakefs')
        self.filesystem.set_disk_usage(disk_size, real_dir_path)
        self.filesystem.add_real_directory(real_dir_path, lazy_read=False)

        # the directory has been read, so the file sizes have
        # been subtracted from the free space
        self.assertGreater(disk_size,
                           self.filesystem.get_disk_usage(real_dir_path).free)

    def test_add_existing_real_directory_read_write(self):
        real_dir_path = os.path.join(os.path.dirname(__file__), 'pyfakefs')
        self.filesystem.add_real_directory(real_dir_path, read_only=False)
        self.assertTrue(self.filesystem.exists(real_dir_path))
        self.assertTrue(self.filesystem.exists(
            os.path.join(real_dir_path, 'fake_filesystem.py')))
        self.assertTrue(self.filesystem.exists(
            os.path.join(real_dir_path, 'fake_pathlib.py')))

        file_path = os.path.join(real_dir_path, 'pytest_plugin.py')
        fake_file = self.filesystem.resolve(file_path)
        self.check_fake_file_stat(fake_file, file_path)
        self.check_writable_file(fake_file, file_path)

    def test_add_existing_real_paths_read_only(self):
        real_file_path = os.path.realpath(__file__)
        real_dir_path = os.path.join(os.path.dirname(__file__), 'pyfakefs')
        self.filesystem.add_real_paths([real_file_path, real_dir_path])

        fake_file = self.filesystem.resolve(real_file_path)
        self.check_fake_file_stat(fake_file, real_file_path)
        self.check_read_only_file(fake_file, real_file_path)

        real_file_path = os.path.join(real_dir_path,
                                      'fake_filesystem_shutil.py')
        fake_file = self.filesystem.resolve(real_file_path)
        self.check_fake_file_stat(fake_file, real_file_path)
        self.check_read_only_file(fake_file, real_file_path)

    def test_add_existing_real_paths_read_write(self):
        real_file_path = os.path.realpath(__file__)
        real_dir_path = os.path.join(os.path.dirname(__file__), 'pyfakefs')
        self.filesystem.add_real_paths([real_file_path, real_dir_path],
                                       read_only=False)

        fake_file = self.filesystem.resolve(real_file_path)
        self.check_fake_file_stat(fake_file, real_file_path)
        self.check_writable_file(fake_file, real_file_path)

        real_file_path = os.path.join(real_dir_path, 'fake_pathlib.py')
        fake_file = self.filesystem.resolve(real_file_path)
        self.check_fake_file_stat(fake_file, real_file_path)
        self.check_writable_file(fake_file, real_file_path)


if __name__ == '__main__':
    unittest.main()
