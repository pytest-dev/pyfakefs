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

import contextlib
import errno
import os
import stat
import sys
import unittest

from pyfakefs import fake_filesystem
from pyfakefs.fake_filesystem import (
    set_uid, set_gid, is_root, reset_ids, OSType
)
from pyfakefs.helpers import IS_WIN
from pyfakefs.tests.test_utils import TestCase, RealFsTestCase, time_mock


class FakeDirectoryUnitTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.os = fake_filesystem.FakeOsModule(self.filesystem)
        self.time = time_mock(10, 1)
        self.time.start()
        self.fake_file = fake_filesystem.FakeFile(
            'foobar', contents='dummy_file', filesystem=self.filesystem)
        self.fake_dir = fake_filesystem.FakeDirectory(
            'somedir', filesystem=self.filesystem)

    def tearDown(self):
        self.time.stop()

    def test_new_file_and_directory(self):
        self.assertTrue(stat.S_IFREG & self.fake_file.st_mode)
        self.assertTrue(stat.S_IFDIR & self.fake_dir.st_mode)
        self.assertEqual({}, self.fake_dir.entries)

    def test_add_entry(self):
        self.fake_dir.add_entry(self.fake_file)
        self.assertEqual({'foobar': self.fake_file},
                         self.fake_dir.entries)

    def test_get_entry(self):
        self.fake_dir.add_entry(self.fake_file)
        self.assertEqual(self.fake_file, self.fake_dir.get_entry('foobar'))

    def test_path(self):
        root_dir = self.filesystem.root_dir_name
        self.filesystem.root.add_entry(self.fake_dir)
        self.fake_dir.add_entry(self.fake_file)
        self.assertEqual(f'{root_dir}somedir/foobar', self.fake_file.path)
        self.assertEqual(f'{root_dir}somedir', self.fake_dir.path)

    def test_path_with_drive(self):
        self.filesystem.is_windows_fs = True
        dir_path = 'C:/foo/bar/baz'
        self.filesystem.create_dir(dir_path)
        dir_object = self.filesystem.get_object(dir_path)
        self.assertEqual(dir_path, dir_object.path)

    def test_path_after_chdir(self):
        root_dir = self.filesystem.root_dir_name
        dir_path = '/foo/bar/baz'
        self.filesystem.create_dir(dir_path)
        self.os.chdir(dir_path)
        dir_object = self.filesystem.get_object(dir_path)
        self.assertEqual(f'{root_dir}foo/bar/baz', dir_object.path)

    def test_path_after_chdir_with_drive(self):
        self.filesystem.is_windows_fs = True
        dir_path = 'C:/foo/bar/baz'
        self.filesystem.create_dir(dir_path)
        self.os.chdir(dir_path)
        dir_object = self.filesystem.get_object(dir_path)
        self.assertEqual(dir_path, dir_object.path)

    def test_remove_entry(self):
        self.fake_dir.add_entry(self.fake_file)
        self.assertEqual(self.fake_file, self.fake_dir.get_entry('foobar'))
        self.fake_dir.remove_entry('foobar')
        with self.assertRaises(KeyError):
            self.fake_dir.get_entry('foobar')

    def test_should_throw_if_set_size_is_not_integer(self):
        with self.raises_os_error(errno.ENOSPC):
            self.fake_file.size = 0.1

    def test_should_throw_if_set_size_is_negative(self):
        with self.raises_os_error(errno.ENOSPC):
            self.fake_file.size = -1

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
        with self.raises_os_error(errno.EISDIR):
            self.fake_dir.set_contents('a')
        self.filesystem.is_windows_fs = False
        with self.raises_os_error(errno.EISDIR):
            self.fake_dir.set_contents('a')

    def test_pads_with_nullbytes_if_size_is_greater_than_current_size(self):
        self.fake_file.size = 13
        self.assertEqual('dummy_file\0\0\0', self.fake_file.contents)

    def test_set_m_time(self):
        self.assertEqual(10, self.fake_file.st_mtime)
        self.fake_file.st_mtime = 14
        self.assertEqual(14, self.fake_file.st_mtime)
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

    def test_directory_size(self):
        fs = fake_filesystem.FakeFilesystem(path_separator='/')
        foo_dir = fs.create_dir('/foo')
        fs.create_file('/foo/bar.txt', st_size=20)
        bar_dir = fs.create_dir('/foo/bar/')
        fs.create_file('/foo/bar/baz1.txt', st_size=30)
        fs.create_file('/foo/bar/baz2.txt', st_size=40)
        foo1_dir = fs.create_dir('/foo1')
        fs.create_file('/foo1/bar.txt', st_size=50)
        fs.create_file('/foo1/bar/baz/file', st_size=60)
        self.assertEqual(90, foo_dir.size)
        self.assertEqual(70, bar_dir.size)
        self.assertEqual(110, foo1_dir.size)
        self.assertEqual(200, fs.root_dir.size)
        with self.raises_os_error(errno.EISDIR):
            foo1_dir.size = 100

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
        with self.raises_os_error(errno.ENOSPC):
            self.fake_file.set_large_file_size(0.1)

    def test_should_throw_if_size_is_negative(self):
        with self.raises_os_error(errno.ENOSPC):
            self.fake_file.set_large_file_size(-1)

    def test_sets_content_none_if_size_is_non_negative_integer(self):
        self.fake_file.set_large_file_size(1000000000)
        self.assertEqual(None, self.fake_file.contents)
        self.assertEqual(1000000000, self.fake_file.st_size)


class NormalizePathTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.root_name = self.filesystem.root_dir_name

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
        path = 'foo/bar'
        self.assertEqual(self.root_name + path, self.filesystem.absnormpath(
            path))

    def test_dotted_path_is_normalized(self):
        path = '/foo/..'
        self.assertEqual(self.filesystem.root_dir_name,
                         self.filesystem.absnormpath(path))
        path = 'foo/../bar'
        self.assertEqual(f'{self.filesystem.root_dir_name}bar',
                         self.filesystem.absnormpath(path))

    def test_dot_path_is_normalized(self):
        path = '.'
        self.assertEqual(self.root_name, self.filesystem.absnormpath(path))


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
        self.root_name = self.filesystem.root_dir_name
        self.fake_file = fake_filesystem.FakeFile(
            'foobar', filesystem=self.filesystem)
        self.fake_child = fake_filesystem.FakeDirectory(
            'foobaz', filesystem=self.filesystem)
        self.fake_grandchild = fake_filesystem.FakeDirectory(
            'quux', filesystem=self.filesystem)

    def test_new_filesystem(self):
        self.assertEqual('/', self.filesystem.path_separator)
        self.assertTrue(stat.S_IFDIR & self.filesystem.root.st_mode)
        self.assertEqual({}, self.filesystem.root_dir.entries)

    def test_none_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.filesystem.exists(None)

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
        self.assertEqual(self.filesystem.root_dir,
                         self.filesystem.get_object(self.root_name))

    def test_add_object_to_root(self):
        self.filesystem.add_object(self.root_name, self.fake_file)
        self.assertEqual({'foobar': self.fake_file},
                         self.filesystem.root_dir.entries)

    def test_windows_root_dir_name(self):
        self.filesystem.is_windows_fs = True
        self.assertEqual('C:/', self.filesystem.root_dir_name)
        self.filesystem.cwd = 'E:/foo'
        self.assertEqual('E:/', self.filesystem.root_dir_name)
        self.filesystem.cwd = '//foo/bar'
        self.assertEqual('//foo/bar/', self.filesystem.root_dir_name)

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
        self.filesystem.cwd = 'C:/a/c'
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
        with self.raises_os_error(errno.ENOENT):
            self.filesystem.get_object('some_bogus_filename')

    def test_remove_object_from_root(self):
        self.filesystem.add_object(self.root_name, self.fake_file)
        self.filesystem.remove_object(self.fake_file.name)
        with self.raises_os_error(errno.ENOENT):
            self.filesystem.get_object(self.fake_file.name)

    def test_remove_nonexisten_object_from_root_error(self):
        with self.raises_os_error(errno.ENOENT):
            self.filesystem.remove_object('some_bogus_filename')

    def test_exists_removed_file(self):
        self.filesystem.add_object(self.root_name, self.fake_file)
        self.filesystem.remove_object(self.fake_file.name)
        self.assertFalse(self.filesystem.exists(self.fake_file.name))

    def test_add_object_to_child(self):
        self.filesystem.add_object(self.root_name, self.fake_child)
        self.filesystem.add_object(self.fake_child.name, self.fake_file)
        self.assertEqual(
            {self.fake_file.name: self.fake_file},
            self.filesystem.root_dir.get_entry(self.fake_child.name).entries)

    def test_add_object_to_regular_file_error_posix(self):
        self.filesystem.is_windows_fs = False
        self.filesystem.add_object(
            self.filesystem.root_dir_name, self.fake_file)
        with self.raises_os_error(errno.ENOTDIR):
            self.filesystem.add_object(self.fake_file.name, self.fake_file)

    def test_add_object_to_regular_file_error_windows(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.add_object(self.root_name, self.fake_file)
        with self.raises_os_error(errno.ENOENT):
            self.filesystem.add_object(self.fake_file.name, self.fake_file)

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
        with self.raises_os_error(errno.ENOENT):
            self.filesystem.get_object(self.filesystem.joinpaths(
                self.fake_child.name, 'some_bogus_filename'))

    def test_remove_object_from_child(self):
        self.filesystem.add_object(self.root_name, self.fake_child)
        self.filesystem.add_object(self.fake_child.name, self.fake_file)
        target_path = self.filesystem.joinpaths(self.fake_child.name,
                                                self.fake_file.name)
        self.filesystem.remove_object(target_path)
        with self.raises_os_error(errno.ENOENT):
            self.filesystem.get_object(target_path)

    def test_remove_object_from_child_error(self):
        self.filesystem.add_object(self.root_name, self.fake_child)
        with self.raises_os_error(errno.ENOENT):
            self.filesystem.remove_object(
                self.filesystem.joinpaths(self.fake_child.name,
                                          'some_bogus_filename'))

    def test_remove_object_from_non_directory_error(self):
        self.filesystem.add_object(self.root_name, self.fake_file)
        with self.raises_os_error(errno.ENOTDIR):
            self.filesystem.remove_object(
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
        grandchild_directory = self.filesystem.joinpaths(
            self.fake_child.name, self.fake_grandchild.name)
        grandchild_file = self.filesystem.joinpaths(
            grandchild_directory, self.fake_file.name)
        with self.assertRaises(OSError):
            self.filesystem.get_object(grandchild_file)
        self.filesystem.add_object(grandchild_directory, self.fake_file)
        self.assertEqual(self.fake_file,
                         self.filesystem.get_object(grandchild_file))
        self.assertTrue(self.filesystem.exists(grandchild_file))
        self.filesystem.remove_object(grandchild_file)
        with self.assertRaises(OSError):
            self.filesystem.get_object(grandchild_file)
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
        with self.raises_os_error(errno.EEXIST):
            self.filesystem.create_dir(path)

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
        with self.raises_os_error(errno.EEXIST):
            self.filesystem.create_dir(path)

    def test_create_file_in_read_only_directory_raises_in_posix(self):
        self.filesystem.is_windows_fs = False
        dir_path = '/foo/bar'
        self.filesystem.create_dir(dir_path, perm_bits=0o555)
        file_path = dir_path + '/baz'

        if not is_root():
            with self.raises_os_error(errno.EACCES):
                self.filesystem.create_file(file_path)
        else:
            self.filesystem.create_file(file_path)
            self.assertTrue(self.filesystem.exists(file_path))

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
        with self.raises_os_error(errno.EEXIST):
            self.filesystem.create_file(path)

    def test_create_file(self):
        path = 'foo/bar/baz'
        retval = self.filesystem.create_file(path, contents='dummy_data')
        self.assertTrue(self.filesystem.exists(path))
        self.assertTrue(self.filesystem.exists(os.path.dirname(path)))
        new_file = self.filesystem.get_object(path)
        self.assertEqual(os.path.basename(path), new_file.name)
        if IS_WIN:
            self.assertEqual(1, new_file.st_uid)
            self.assertEqual(1, new_file.st_gid)
        else:
            self.assertEqual(os.getuid(), new_file.st_uid)
            self.assertEqual(os.getgid(), new_file.st_gid)
        self.assertEqual(new_file, retval)

    def test_create_file_with_changed_ids(self):
        path = 'foo/bar/baz'
        set_uid(42)
        set_gid(2)
        self.filesystem.create_file(path)
        self.assertTrue(self.filesystem.exists(path))
        new_file = self.filesystem.get_object(path)
        self.assertEqual(42, new_file.st_uid)
        self.assertEqual(2, new_file.st_gid)
        reset_ids()

    def test_empty_file_created_for_none_contents(self):
        fake_open = fake_filesystem.FakeFileOpen(self.filesystem)
        path = 'foo/bar/baz'
        self.filesystem.create_file(path, contents=None)
        with fake_open(path) as f:
            self.assertEqual('', f.read())

    def test_create_file_with_incorrect_mode_type(self):
        with self.assertRaises(TypeError):
            self.filesystem.create_file('foo', 'bar')

    def test_create_file_already_exists_error(self):
        path = 'foo/bar/baz'
        self.filesystem.create_file(path, contents='dummy_data')
        with self.raises_os_error(errno.EEXIST):
            self.filesystem.create_file(path)

    def test_create_link(self):
        path = 'foo/bar/baz'
        target_path = 'foo/bar/quux'
        new_file = self.filesystem.create_symlink(path, 'quux')
        # Neither the path nor the final target exists before we actually
        # write to one of them, even though the link appears in the file
        # system.
        self.assertFalse(self.filesystem.exists(path))
        self.assertFalse(self.filesystem.exists(target_path))
        self.assertTrue(stat.S_IFLNK & new_file.st_mode)

        # but once we write the linked to file, they both will exist.
        self.filesystem.create_file(target_path)
        self.assertTrue(self.filesystem.exists(path))
        self.assertTrue(self.filesystem.exists(target_path))

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

    def test_lresolve_object_windows(self):
        self.filesystem.is_windows_fs = True
        self.check_lresolve_object()

    def test_lresolve_object_posix(self):
        self.filesystem.is_windows_fs = False
        self.check_lresolve_object()

    def check_directory_access_on_file(self, error_subtype):
        self.filesystem.create_file('not_a_dir')
        with self.raises_os_error(error_subtype):
            self.filesystem.resolve('not_a_dir/foo')
        with self.raises_os_error(error_subtype):
            self.filesystem.lresolve('not_a_dir/foo/bar')

    def test_directory_access_on_file_windows(self):
        self.filesystem.is_windows_fs = True
        self.check_directory_access_on_file(errno.ENOENT)

    def test_directory_access_on_file_posix(self):
        self.filesystem.is_windows_fs = False
        self.check_directory_access_on_file(errno.ENOTDIR)

    def test_pickle_fs(self):
        """Regression test for #445"""
        import pickle
        self.filesystem.open_files = []
        p = pickle.dumps(self.filesystem)
        fs = pickle.loads(p)
        self.assertEqual(str(fs.root), str(self.filesystem.root))
        self.assertEqual(fs.mount_points, self.filesystem.mount_points)


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

    def test_resolve_path(self):
        self.filesystem.create_dir('/foo/baz')
        self.filesystem.create_symlink('/Foo/Bar', './baz/bip')
        self.assertEqual(f'{self.filesystem.root_dir_name}foo/baz/bip',
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
        with self.raises_os_error(errno.ELOOP):
            self.os.path.getsize(link_path)

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
        with self.assertRaises(OSError):
            self.filesystem.get_object('/Foo/Bar/Baz')

    def test_remove_object(self):
        self.filesystem.create_dir('/foo/bar')
        self.filesystem.create_file('/foo/bar/baz')
        with self.assertRaises(OSError):
            self.filesystem.remove_object('/Foo/Bar/Baz')
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
        with self.assertRaises(os.error):
            self.path.getsize('FOO/BAR/BAZ')

    def test_get_mtime(self):
        test_file = self.filesystem.create_file('foo/bar1.txt')
        test_file.st_mtime = 24
        with self.raises_os_error(errno.ENOENT):
            self.path.getmtime('Foo/Bar1.TXT')


class OsPathInjectionRegressionTest(TestCase):
    """Test faking os.path before calling os.walk.

  Found when investigating a problem with
  gws/tools/labrat/rat_utils_unittest, which was faking out os.path
  before calling os.walk.
  """

    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.os_path = os.path
        # The bug was that when os.path gets faked, the FakePathModule doesn't
        # get called in self.os.walk(). FakePathModule now insists that it is
        # created as part of FakeOsModule.
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
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='!')
        self.os = fake_filesystem.FakeOsModule(self.filesystem)
        self.path = self.os.path

    def check_abspath(self, is_windows):
        # the implementation differs in Windows and Posix, so test both
        self.filesystem.is_windows_fs = is_windows
        filename = 'foo'
        abspath = self.filesystem.root_dir_name + filename
        self.filesystem.create_file(abspath)
        self.assertEqual(abspath, self.path.abspath(abspath))
        self.assertEqual(abspath, self.path.abspath(filename))
        self.assertEqual(abspath, self.path.abspath('..!%s' % filename))

    def test_abspath_windows(self):
        self.check_abspath(is_windows=True)

    def test_abspath_posix(self):
        """abspath should return a consistent representation of a file."""
        self.check_abspath(is_windows=False)

    def check_abspath_bytes(self, is_windows):
        """abspath should return a consistent representation of a file."""
        self.filesystem.is_windows_fs = is_windows
        filename = b'foo'
        abspath = self.filesystem.root_dir_name.encode() + filename
        self.filesystem.create_file(abspath)
        self.assertEqual(abspath, self.path.abspath(abspath))
        self.assertEqual(abspath, self.path.abspath(filename))
        self.assertEqual(abspath, self.path.abspath(b'..!' + filename))

    def test_abspath_bytes_windows(self):
        self.check_abspath_bytes(is_windows=True)

    def test_abspath_bytes_posix(self):
        self.check_abspath_bytes(is_windows=False)

    def test_abspath_deals_with_relative_non_root_path(self):
        """abspath should correctly handle relative paths from a
        non-! directory.

        This test is distinct from the basic functionality test because
        fake_filesystem has historically been based in !.
        """
        filename = '!foo!bar!baz'
        file_components = filename.split(self.path.sep)
        root_name = self.filesystem.root_dir_name
        basedir = f'{root_name}{file_components[0]}'
        self.filesystem.create_file(filename)
        self.os.chdir(basedir)
        self.assertEqual(basedir, self.path.abspath(self.path.curdir))
        self.assertEqual(root_name, self.path.abspath('..'))
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
        self.assertFalse(self.path.isabs(b'C:!foo'))
        self.assertTrue(self.path.isabs('!'))
        self.assertTrue(self.path.isabs(b'!'))
        self.filesystem.is_windows_fs = True
        self.assertTrue(self.path.isabs('C:!foo'))
        self.assertTrue(self.path.isabs(b'C:!foo'))
        self.assertTrue(self.path.isabs('!'))
        self.assertTrue(self.path.isabs(b'!'))

    def test_relpath(self):
        path_foo = '!path!to!foo'
        path_bar = '!path!to!bar'
        path_other = '!some!where!else'
        with self.assertRaises(ValueError):
            self.path.relpath(None)
        with self.assertRaises(ValueError):
            self.path.relpath('')
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
        self.filesystem.create_symlink('!first!president',
                                       '!george!washington')
        self.assertEqual('!first!president!bridge',
                         self.os.path.abspath('!first!president!bridge'))
        self.assertEqual('!george!washington!bridge',
                         self.os.path.realpath('!first!president!bridge'))
        self.os.chdir('!first!president')
        self.assertEqual('!george!washington!bridge',
                         self.os.path.realpath('bridge'))

    @unittest.skipIf(sys.version_info < (3, 10), "'strict' new in Python 3.10")
    def test_realpath_strict(self):
        self.filesystem.create_file('!foo!bar')
        root_dir = self.filesystem.root_dir_name
        self.filesystem.cwd = f'{root_dir}foo'
        self.assertEqual(f'{root_dir}foo!baz',
                         self.os.path.realpath('baz', strict=False))
        with self.raises_os_error(errno.ENOENT):
            self.os.path.realpath('baz', strict=True)
        self.assertEqual(f'{root_dir}foo!bar',
                         self.os.path.realpath('bar', strict=True))

    def test_samefile(self):
        file_path1 = '!foo!bar!baz'
        file_path2 = '!foo!bar!boo'
        self.filesystem.create_file(file_path1)
        self.filesystem.create_file(file_path2)
        self.assertTrue(self.path.samefile(file_path1, file_path1))
        self.assertFalse(self.path.samefile(file_path1, file_path2))
        self.assertTrue(
            self.path.samefile(file_path1, '!foo!..!foo!bar!..!bar!baz'))
        self.assertTrue(
            self.path.samefile(file_path1, b'!foo!..!foo!bar!..!bar!baz'))

    def test_exists(self):
        file_path = 'foo!bar!baz'
        file_path_bytes = b'foo!bar!baz'
        self.filesystem.create_file(file_path)
        self.assertTrue(self.path.exists(file_path))
        self.assertTrue(self.path.exists(file_path_bytes))
        self.assertFalse(self.path.exists('!some!other!bogus!path'))

    def test_exists_with_drive(self):
        self.filesystem.os = OSType.WINDOWS
        self.filesystem.add_mount_point('F:')
        self.assertTrue(self.path.exists('C:'))
        self.assertTrue(self.path.exists('c:\\'))
        self.assertTrue(self.path.exists('f:'))
        self.assertTrue(self.path.exists('F:\\'))
        self.assertFalse(self.path.exists('Z:'))
        self.assertFalse(self.path.exists('z:\\'))

    def test_lexists(self):
        file_path = 'foo!bar!baz'
        file_path_bytes = b'foo!bar!baz'
        self.filesystem.create_dir('foo!bar')
        self.filesystem.create_symlink(file_path, 'bogus')
        self.assertTrue(self.path.lexists(file_path))
        self.assertTrue(self.path.lexists(file_path_bytes))
        self.assertFalse(self.path.exists(file_path))
        self.assertFalse(self.path.exists(file_path_bytes))
        self.filesystem.create_file('foo!bar!bogus')
        self.assertTrue(self.path.exists(file_path))

    def test_dirname_with_drive(self):
        self.filesystem.is_windows_fs = True
        self.assertEqual('c:!foo',
                         self.path.dirname('c:!foo!bar'))
        self.assertEqual(b'c:!',
                         self.path.dirname(b'c:!foo'))
        self.assertEqual('!foo',
                         self.path.dirname('!foo!bar'))
        self.assertEqual(b'!',
                         self.path.dirname(b'!foo'))
        self.assertEqual('c:foo',
                         self.path.dirname('c:foo!bar'))
        self.assertEqual(b'c:',
                         self.path.dirname(b'c:foo'))
        self.assertEqual('foo',
                         self.path.dirname('foo!bar'))

    def test_dirname(self):
        dirname = 'foo!bar'
        self.assertEqual(dirname, self.path.dirname('%s!baz' % dirname))

    def test_join_strings(self):
        components = ['foo', 'bar', 'baz']
        self.assertEqual('foo!bar!baz', self.path.join(*components))

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
        with self.assertRaises(os.error):
            self.path.getsize(file_path)

    def test_getsize_file_empty(self):
        file_path = 'foo!bar!baz'
        self.filesystem.create_file(file_path)
        self.assertEqual(0, self.path.getsize(file_path))

    def test_getsize_file_non_zero_size(self):
        file_path = 'foo!bar!baz'
        file_path_bytes = b'foo!bar!baz'
        self.filesystem.create_file(file_path, contents='1234567')
        self.assertEqual(7, self.path.getsize(file_path))
        self.assertEqual(7, self.path.getsize(file_path_bytes))

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
        self.assertTrue(self.path.isdir(b'foo'))
        self.assertFalse(self.path.isdir('foo!bar'))
        self.assertFalse(self.path.isdir('it_dont_exist'))

    def test_isdir_with_cwd_change(self):
        self.filesystem.create_file('!foo!bar!baz')
        self.assertTrue(self.path.isdir('!foo'))
        self.assertTrue(self.path.isdir('!foo!bar'))
        self.assertTrue(self.path.isdir('foo'))
        self.assertTrue(self.path.isdir('foo!bar'))
        self.filesystem.cwd = f'{self.filesystem.root_dir_name}foo'
        self.assertTrue(self.path.isdir('!foo'))
        self.assertTrue(self.path.isdir('!foo!bar'))
        self.assertTrue(self.path.isdir('bar'))

    def test_isfile(self):
        self.filesystem.create_file('foo!bar')
        self.assertFalse(self.path.isfile('foo'))
        self.assertTrue(self.path.isfile('foo!bar'))
        self.assertTrue(self.path.isfile(b'foo!bar'))
        self.assertFalse(self.path.isfile('it_dont_exist'))

    def test_get_mtime(self):
        test_file = self.filesystem.create_file('foo!bar1.txt')
        self.assertNotEqual(24, self.path.getmtime('foo!bar1.txt'))
        test_file.st_mtime = 24
        self.assertEqual(24, self.path.getmtime('foo!bar1.txt'))
        self.assertEqual(24, self.path.getmtime(b'foo!bar1.txt'))

    def test_get_mtime_raises_os_error(self):
        self.assertFalse(self.path.exists('does_not_exist'))
        with self.raises_os_error(errno.ENOENT):
            self.path.getmtime('does_not_exist')

    def test_islink(self):
        self.filesystem.create_dir('foo')
        self.filesystem.create_file('foo!regular_file')
        self.filesystem.create_symlink('foo!link_to_file', 'regular_file')
        self.assertFalse(self.path.islink('foo'))

        # An object can be both a link and a file or file, according to the
        # comments in Python/Lib/posixpath.py.
        self.assertTrue(self.path.islink('foo!link_to_file'))
        self.assertTrue(self.path.isfile('foo!link_to_file'))
        self.assertTrue(self.path.islink(b'foo!link_to_file'))
        self.assertTrue(self.path.isfile(b'foo!link_to_file'))

        self.assertTrue(self.path.isfile('foo!regular_file'))
        self.assertFalse(self.path.islink('foo!regular_file'))

        self.assertFalse(self.path.islink('it_dont_exist'))

    def test_is_link_case_sensitive(self):
        # Regression test for #306
        self.filesystem.is_case_sensitive = False
        self.filesystem.create_dir('foo')
        self.filesystem.create_symlink('foo!bar', 'foo')
        self.assertTrue(self.path.islink('foo!Bar'))

    def test_ismount(self):
        self.assertFalse(self.path.ismount(''))
        self.assertTrue(self.path.ismount('!'))
        self.assertTrue(self.path.ismount(b'!'))
        self.assertFalse(self.path.ismount('!mount!'))
        self.filesystem.add_mount_point('!mount')
        self.assertTrue(self.path.ismount('!mount'))
        self.assertTrue(self.path.ismount(b'!mount'))
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

    def test_getattr_forward_to_real_os_path(self):
        """Forwards any non-faked calls to os.path."""
        self.assertTrue(hasattr(self.path, 'sep'),
                        'Get a faked os.path function')
        private_path_function = None
        if sys.version_info < (3, 6):
            if self.is_windows:
                private_path_function = '_get_bothseps'
            else:
                private_path_function = '_join_real_path'
        if private_path_function:
            self.assertTrue(hasattr(self.path, private_path_function),
                            'Get a real os.path function '
                            'not implemented in fake os.path')
        self.assertFalse(hasattr(self.path, 'nonexistent'))


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
        self.filesystem.is_windows_fs = False  # not an UNC path
        self.assertEqual('|', self.filesystem.normpath('||..|.|..||'))

    def test_conserves_up_level_references_starting_from_current_dir(self):
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
        self.assertEqual(('|||', ''), self.filesystem.splitpath('|||'))
        self.assertEqual(('|', 'a'), self.filesystem.splitpath('|a'))
        self.assertEqual(('|||', 'a'), self.filesystem.splitpath('|||a'))

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
        self.assertEqual(f'{self.filesystem.root_dir_name}Foo/Bar',
                         self.filesystem._original_path('/foo/bar'))
        self.assertEqual(f'{self.filesystem.root_dir_name}Foo/Bar',
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
        self.assertEqual(f'{self.filesystem.root_dir_name}Foo/Bar/baz',
                         self.filesystem._original_path('/foo/bar/baz'))
        self.assertEqual(f'{self.filesystem.root_dir_name}Foo/Bar/BAZ',
                         self.filesystem._original_path('/FOO/BAR/BAZ'))

    @unittest.skipIf(not TestCase.is_windows,
                     'Regression test for Windows problem only')
    def test_normalize_case_for_lazily_added_empty_file(self):
        # regression test for specific issue with added empty real files
        filesystem = fake_filesystem.FakeFilesystem()
        real_dir_path = os.path.split(
            os.path.dirname(os.path.abspath(__file__)))[0]
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
        self.assertEqual(f'{self.filesystem.root_dir_name}bar',
                         self.filesystem.absnormpath(path))

    def test_exists_with_mixed_separators(self):
        self.filesystem.create_file('?foo?bar?baz')
        self.filesystem.create_file('!foo!bar!xyzzy!plugh')
        self.assertTrue(self.filesystem.exists('!foo!bar!baz'))
        self.assertTrue(self.filesystem.exists('?foo?bar?xyzzy?plugh'))


class DriveLetterSupportTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='!')
        self.filesystem.alternative_path_separator = '^'
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

    def test_collapse_unc_path(self):
        self.assertEqual('!!foo!bar!baz',
                         self.filesystem.normpath('!!foo!bar!!baz!!'))

    def test_normalize_path_str(self):
        self.filesystem.cwd = ''
        self.assertEqual('c:!foo!bar',
                         self.filesystem.absnormpath('c:!foo!!bar'))
        self.filesystem.cwd = 'c:!foo'
        self.assertEqual('c:!foo!bar', self.filesystem.absnormpath('bar'))

    def test_normalize_path_bytes(self):
        self.filesystem.cwd = b''
        self.assertEqual(b'c:!foo!bar',
                         self.filesystem.absnormpath(b'c:!foo!!bar'))
        self.filesystem.cwd = b'c:!foo'
        self.assertEqual(b'c:!foo!bar', self.filesystem.absnormpath(b'bar'))

    def test_split_path_str(self):
        self.assertEqual(('c:!foo', 'bar'),
                         self.filesystem.splitpath('c:!foo!bar'))
        self.assertEqual(('c:!', 'foo'),
                         self.filesystem.splitpath('c:!foo'))
        self.assertEqual(('!foo', 'bar'),
                         self.filesystem.splitpath('!foo!bar'))
        self.assertEqual(('!', 'foo'),
                         self.filesystem.splitpath('!foo'))
        self.assertEqual(('c:foo', 'bar'),
                         self.filesystem.splitpath('c:foo!bar'))
        self.assertEqual(('c:', 'foo'),
                         self.filesystem.splitpath('c:foo'))
        self.assertEqual(('foo', 'bar'),
                         self.filesystem.splitpath('foo!bar'))

    def test_split_with_alt_separator(self):
        self.assertEqual(('a^b', 'c'), self.filesystem.splitpath('a^b^c'))
        self.assertEqual(('a^b!c', 'd'), self.filesystem.splitpath('a^b!c^d'))
        self.assertEqual(('a^b!c', 'd'), self.filesystem.splitpath('a^b!c!d'))
        self.assertEqual((b'a^b', b'c'), self.filesystem.splitpath(b'a^b^c'))
        self.assertEqual((b'a^b!c', b'd'),
                         self.filesystem.splitpath(b'a^b!c^d'))
        self.assertEqual((b'a^b!c', b'd'),
                         self.filesystem.splitpath(b'a^b!c!d'))

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
        self.assertEqual('C:!foo!bar',
                         self.filesystem.resolve_path('C:!foo!bar'))

    def test_get_path_components(self):
        self.assertEqual(['c:', 'foo', 'bar'],
                         self.filesystem._path_components('c:!foo!bar'))
        self.assertEqual(['c:'], self.filesystem._path_components('c:'))

    def test_split_drive_str(self):
        self.assertEqual(('c:', '!foo!bar'),
                         self.filesystem.splitdrive('c:!foo!bar'))
        self.assertEqual(('', '!foo!bar'),
                         self.filesystem.splitdrive('!foo!bar'))
        self.assertEqual(('c:', 'foo!bar'),
                         self.filesystem.splitdrive('c:foo!bar'))
        self.assertEqual(('', 'foo!bar'),
                         self.filesystem.splitdrive('foo!bar'))

    def test_split_drive_bytes(self):
        self.assertEqual((b'c:', b'!foo!bar'),
                         self.filesystem.splitdrive(b'c:!foo!bar'))
        self.assertEqual((b'', b'!foo!bar'),
                         self.filesystem.splitdrive(b'!foo!bar'))

    def test_split_drive_alt_sep(self):
        self.assertEqual(('c:', '^foo^bar'),
                         self.filesystem.splitdrive('c:^foo^bar'))
        self.assertEqual(('', 'foo^bar'),
                         self.filesystem.splitdrive('foo^bar'))
        self.assertEqual(('', 'foo^bar!baz'),
                         self.filesystem.splitdrive('foo^bar!baz'))
        self.assertEqual((b'c:', b'^foo^bar'),
                         self.filesystem.splitdrive(b'c:^foo^bar'))
        self.assertEqual((b'', b'^foo^bar'),
                         self.filesystem.splitdrive(b'^foo^bar'))
        self.assertEqual((b'', b'^foo^bar!baz'),
                         self.filesystem.splitdrive(b'^foo^bar!baz'))

    def test_split_drive_with_unc_path(self):
        self.assertEqual(('!!foo!bar', '!baz'),
                         self.filesystem.splitdrive('!!foo!bar!baz'))
        self.assertEqual(('', '!!foo'), self.filesystem.splitdrive('!!foo'))
        self.assertEqual(('', '!!foo!!bar'),
                         self.filesystem.splitdrive('!!foo!!bar'))
        self.assertEqual(('!!foo!bar', '!!'),
                         self.filesystem.splitdrive('!!foo!bar!!'))

    def test_split_drive_with_unc_path_alt_sep(self):
        self.assertEqual(('^^foo^bar', '!baz'),
                         self.filesystem.splitdrive('^^foo^bar!baz'))
        self.assertEqual(('', '^^foo'), self.filesystem.splitdrive('^^foo'))
        self.assertEqual(('', '^^foo^^bar'),
                         self.filesystem.splitdrive('^^foo^^bar'))
        self.assertEqual(('^^foo^bar', '^^'),
                         self.filesystem.splitdrive('^^foo^bar^^'))

    def test_split_path_with_drive(self):
        self.assertEqual(('d:!foo', 'baz'),
                         self.filesystem.splitpath('d:!foo!baz'))
        self.assertEqual(('d:!foo!baz', ''),
                         self.filesystem.splitpath('d:!foo!baz!'))
        self.assertEqual(('c:', ''),
                         self.filesystem.splitpath('c:'))
        self.assertEqual(('c:!', ''),
                         self.filesystem.splitpath('c:!'))
        self.assertEqual(('c:!!', ''),
                         self.filesystem.splitpath('c:!!'))

    def test_split_path_with_drive_alt_sep(self):
        self.assertEqual(('d:^foo', 'baz'),
                         self.filesystem.splitpath('d:^foo^baz'))
        self.assertEqual(('d:^foo^baz', ''),
                         self.filesystem.splitpath('d:^foo^baz^'))
        self.assertEqual(('c:', ''),
                         self.filesystem.splitpath('c:'))
        self.assertEqual(('c:^', ''),
                         self.filesystem.splitpath('c:^'))
        self.assertEqual(('c:^^', ''),
                         self.filesystem.splitpath('c:^^'))

    def test_split_path_with_unc_path(self):
        self.assertEqual(('!!foo!bar!', 'baz'),
                         self.filesystem.splitpath('!!foo!bar!baz'))
        self.assertEqual(('!!foo!bar', ''),
                         self.filesystem.splitpath('!!foo!bar'))
        self.assertEqual(('!!foo!bar!!', ''),
                         self.filesystem.splitpath('!!foo!bar!!'))

    def test_split_path_with_unc_path_alt_sep(self):
        self.assertEqual(('^^foo^bar^', 'baz'),
                         self.filesystem.splitpath('^^foo^bar^baz'))
        self.assertEqual(('^^foo^bar', ''),
                         self.filesystem.splitpath('^^foo^bar'))
        self.assertEqual(('^^foo^bar^^', ''),
                         self.filesystem.splitpath('^^foo^bar^^'))


class DiskSpaceTest(TestCase):
    def setUp(self):
        self.fs = fake_filesystem.FakeFilesystem(path_separator='!',
                                                 total_size=100)
        self.os = fake_filesystem.FakeOsModule(self.fs)
        self.open = fake_filesystem.FakeFileOpen(self.fs)

    def test_disk_usage_on_file_creation(self):
        total_size = 100
        self.fs.add_mount_point('!mount', total_size)

        def create_too_large_file():
            with self.open('!mount!file', 'w') as dest:
                dest.write('a' * (total_size + 1))

        with self.assertRaises(OSError):
            create_too_large_file()

        self.assertEqual(0, self.fs.get_disk_usage('!mount').used)

        with self.open('!mount!file', 'w') as dest:
            dest.write('a' * total_size)

        self.assertEqual(total_size,
                         self.fs.get_disk_usage('!mount').used)

    def test_disk_usage_on_automounted_drive(self):
        self.fs.is_windows_fs = True
        self.fs.reset(total_size=100)
        self.fs.create_file('!foo!bar', st_size=50)
        self.assertEqual(0, self.fs.get_disk_usage('D:!').used)
        self.fs.cwd = 'E:!foo'
        self.assertEqual(0, self.fs.get_disk_usage('!foo').used)

    def test_disk_usage_on_mounted_paths(self):
        self.fs.add_mount_point('!foo', total_size=200)
        self.fs.add_mount_point('!foo!bar', total_size=400)
        self.fs.create_file('!baz', st_size=50)
        self.fs.create_file('!foo!baz', st_size=60)
        self.fs.create_file('!foo!bar!baz', st_size=100)
        self.assertEqual(50, self.fs.get_disk_usage('!').used)
        self.assertEqual(60, self.fs.get_disk_usage('!foo').used)
        self.assertEqual(100, self.fs.get_disk_usage('!foo!bar').used)
        self.assertEqual(400, self.fs.get_disk_usage('!foo!bar').total)

    def test_file_system_size_after_large_file_creation(self):
        filesystem = fake_filesystem.FakeFilesystem(
            path_separator='!', total_size=1024 * 1024 * 1024 * 100)
        filesystem.create_file('!foo!baz', st_size=1024 * 1024 * 1024 * 10)
        self.assertEqual((1024 * 1024 * 1024 * 100,
                          1024 * 1024 * 1024 * 10,
                          1024 * 1024 * 1024 * 90),
                         filesystem.get_disk_usage())

    def test_file_system_size_after_binary_file_creation(self):
        self.fs.create_file('!foo!bar', contents=b'xyzzy')
        self.assertEqual((100, 5, 95), self.fs.get_disk_usage())

    def test_file_system_size_after_ascii_string_file_creation(self):
        self.fs.create_file('!foo!bar', contents='complicated')
        self.assertEqual((100, 11, 89), self.fs.get_disk_usage())

    def test_filesystem_size_after_2byte_unicode_file_creation(self):
        self.fs.create_file('!foo!bar', contents='сложно',
                            encoding='utf-8')
        self.assertEqual((100, 12, 88), self.fs.get_disk_usage())

    def test_filesystem_size_after_3byte_unicode_file_creation(self):
        self.fs.create_file('!foo!bar', contents='複雑',
                            encoding='utf-8')
        self.assertEqual((100, 6, 94), self.fs.get_disk_usage())

    def test_file_system_size_after_file_deletion(self):
        self.fs.create_file('!foo!bar', contents=b'xyzzy')
        self.fs.create_file('!foo!baz', st_size=20)
        self.fs.remove_object('!foo!bar')
        self.assertEqual((100, 20, 80), self.fs.get_disk_usage())

    def test_file_system_size_after_directory_removal(self):
        self.fs.create_file('!foo!bar', st_size=10)
        self.fs.create_file('!foo!baz', st_size=20)
        self.fs.create_file('!foo1!bar', st_size=40)
        self.fs.remove_object('!foo')
        self.assertEqual((100, 40, 60), self.fs.get_disk_usage())

    def test_creating_file_with_fitting_content(self):
        initial_usage = self.fs.get_disk_usage()

        try:
            self.fs.create_file('!foo!bar', contents=b'a' * 100)
        except OSError:
            self.fail('File with contents fitting into disk space '
                      'could not be written.')

        self.assertEqual(initial_usage.used + 100,
                         self.fs.get_disk_usage().used)

    def test_creating_file_with_content_too_large(self):
        def create_large_file():
            self.fs.create_file('!foo!bar', contents=b'a' * 101)

        initial_usage = self.fs.get_disk_usage()

        with self.assertRaises(OSError):
            create_large_file()

        self.assertEqual(initial_usage, self.fs.get_disk_usage())

    def test_creating_file_with_fitting_size(self):
        initial_usage = self.fs.get_disk_usage()

        try:
            self.fs.create_file('!foo!bar', st_size=100)
        except OSError:
            self.fail(
                'File with size fitting into disk space could not be written.')

        self.assertEqual(initial_usage.used + 100,
                         self.fs.get_disk_usage().used)

    def test_creating_file_with_size_too_large(self):
        initial_usage = self.fs.get_disk_usage()

        def create_large_file():
            self.fs.create_file('!foo!bar', st_size=101)

        with self.assertRaises(OSError):
            create_large_file()

        self.assertEqual(initial_usage, self.fs.get_disk_usage())

    def test_resize_file_with_fitting_size(self):
        file_object = self.fs.create_file('!foo!bar', st_size=50)
        try:
            file_object.set_large_file_size(100)
            file_object.set_contents(b'a' * 100)
        except OSError:
            self.fail(
                'Resizing file failed although disk space was sufficient.')

    def test_resize_file_with_size_too_large(self):
        file_object = self.fs.create_file('!foo!bar', st_size=50)
        with self.raises_os_error(errno.ENOSPC):
            file_object.set_large_file_size(200)
        with self.raises_os_error(errno.ENOSPC):
            file_object.set_contents('a' * 150)

    def test_file_system_size_after_directory_rename(self):
        self.fs.create_file('!foo!bar', st_size=20)
        self.os.rename('!foo', '!baz')
        self.assertEqual(20, self.fs.get_disk_usage().used)

    def test_file_system_size_after_file_rename(self):
        self.fs.create_file('!foo!bar', st_size=20)
        self.os.rename('!foo!bar', '!foo!baz')
        self.assertEqual(20, self.fs.get_disk_usage().used)

    def test_that_hard_link_does_not_change_used_size(self):
        file1_path = 'test_file1'
        file2_path = 'test_file2'
        self.fs.create_file(file1_path, st_size=20)
        self.assertEqual(20, self.fs.get_disk_usage().used)
        # creating a hard link shall not increase used space
        self.os.link(file1_path, file2_path)
        self.assertEqual(20, self.fs.get_disk_usage().used)
        # removing a file shall not decrease used space
        # if a hard link still exists
        self.os.unlink(file1_path)
        self.assertEqual(20, self.fs.get_disk_usage().used)
        self.os.unlink(file2_path)
        self.assertEqual(0, self.fs.get_disk_usage().used)

    def test_that_the_size_of_correct_mount_point_is_used(self):
        self.fs.add_mount_point('!mount_limited', total_size=50)
        self.fs.add_mount_point('!mount_unlimited')

        with self.raises_os_error(errno.ENOSPC):
            self.fs.create_file('!mount_limited!foo', st_size=60)
        with self.raises_os_error(errno.ENOSPC):
            self.fs.create_file('!bar', st_size=110)

        try:
            self.fs.create_file('!foo', st_size=60)
            self.fs.create_file('!mount_limited!foo', st_size=40)
            self.fs.create_file('!mount_unlimited!foo',
                                st_size=1000000)
        except OSError:
            self.fail('File with contents fitting into '
                      'disk space could not be written.')

    def test_that_disk_usage_of_correct_mount_point_is_used(self):
        self.fs.add_mount_point('!mount1', total_size=20)
        self.fs.add_mount_point('!mount1!bar!mount2', total_size=50)

        self.fs.create_file('!foo!bar', st_size=10)
        self.fs.create_file('!mount1!foo!bar', st_size=10)
        self.fs.create_file('!mount1!bar!mount2!foo!bar', st_size=10)

        self.assertEqual(90, self.fs.get_disk_usage('!foo').free)
        self.assertEqual(10,
                         self.fs.get_disk_usage('!mount1!foo').free)
        self.assertEqual(40, self.fs.get_disk_usage(
            '!mount1!bar!mount2').free)

    def test_set_larger_disk_size(self):
        self.fs.add_mount_point('!mount1', total_size=20)
        with self.raises_os_error(errno.ENOSPC):
            self.fs.create_file('!mount1!foo', st_size=100)
        self.fs.set_disk_usage(total_size=200, path='!mount1')
        self.fs.create_file('!mount1!foo', st_size=100)
        self.assertEqual(100,
                         self.fs.get_disk_usage('!mount1!foo').free)

    def test_set_smaller_disk_size(self):
        self.fs.add_mount_point('!mount1', total_size=200)
        self.fs.create_file('!mount1!foo', st_size=100)
        with self.raises_os_error(errno.ENOSPC):
            self.fs.set_disk_usage(total_size=50, path='!mount1')
        self.fs.set_disk_usage(total_size=150, path='!mount1')
        self.assertEqual(50,
                         self.fs.get_disk_usage('!mount1!foo').free)

    def test_disk_size_on_unlimited_disk(self):
        self.fs.add_mount_point('!mount1')
        self.fs.create_file('!mount1!foo', st_size=100)
        self.fs.set_disk_usage(total_size=1000, path='!mount1')
        self.assertEqual(900,
                         self.fs.get_disk_usage('!mount1!foo').free)

    def test_disk_size_on_auto_mounted_drive_on_file_creation(self):
        self.fs.is_windows_fs = True
        # drive d: shall be auto-mounted and the used size adapted
        self.fs.create_file('d:!foo!bar', st_size=100)
        self.fs.set_disk_usage(total_size=1000, path='d:')
        self.assertEqual(self.fs.get_disk_usage('d:!foo').free, 900)

    def test_disk_size_on_auto_mounted_drive_on_directory_creation(self):
        self.fs.is_windows_fs = True
        self.fs.create_dir('d:!foo!bar')
        self.fs.create_file('d:!foo!bar!baz', st_size=100)
        self.fs.create_file('d:!foo!baz', st_size=100)
        self.fs.set_disk_usage(total_size=1000, path='d:')
        self.assertEqual(800, self.fs.get_disk_usage('d:!foo').free)

    def test_copying_preserves_byte_contents(self):
        source_file = self.fs.create_file('foo', contents=b'somebytes')
        dest_file = self.fs.create_file('bar')
        dest_file.set_contents(source_file.contents)
        self.assertEqual(dest_file.contents, source_file.contents)

    def test_diskusage_after_open_write(self):
        with self.open('bar.txt', 'w') as f:
            f.write('a' * 60)
            f.flush()
        self.assertEqual(60, self.fs.get_disk_usage()[1])

    def test_disk_full_after_reopened(self):
        with self.open('bar.txt', 'w') as f:
            f.write('a' * 60)
        with self.open('bar.txt') as f:
            self.assertEqual('a' * 60, f.read())
        with self.raises_os_error(errno.ENOSPC):
            with self.open('bar.txt', 'w') as f:
                f.write('b' * 110)
                with self.raises_os_error(errno.ENOSPC):
                    f.flush()
        with self.open('bar.txt') as f:
            self.assertEqual('', f.read())

    def test_disk_full_append(self):
        file_path = 'bar.txt'
        with self.open(file_path, 'w') as f:
            f.write('a' * 60)
        with self.open(file_path) as f:
            self.assertEqual('a' * 60, f.read())
        with self.raises_os_error(errno.ENOSPC):
            with self.open(file_path, 'a') as f:
                f.write('b' * 41)
                with self.raises_os_error(errno.ENOSPC):
                    f.flush()
        with self.open('bar.txt') as f:
            self.assertEqual(f.read(), 'a' * 60)

    def test_disk_full_after_reopened_rplus_seek(self):
        with self.open('bar.txt', 'w') as f:
            f.write('a' * 60)
        with self.open('bar.txt') as f:
            self.assertEqual(f.read(), 'a' * 60)
        with self.raises_os_error(errno.ENOSPC):
            with self.open('bar.txt', 'r+') as f:
                f.seek(50)
                f.write('b' * 60)
                with self.raises_os_error(errno.ENOSPC):
                    f.flush()
        with self.open('bar.txt') as f:
            self.assertEqual(f.read(), 'a' * 60)


class MountPointTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='!',
                                                         total_size=100)

    def add_mount_points(self):
        self.filesystem.add_mount_point('!foo')
        self.filesystem.add_mount_point('!bar')
        self.filesystem.add_mount_point('!foo!baz')

    def test_that_new_mount_points_get_new_device_number(self):
        self.add_mount_points()
        self.assertEqual(1, self.filesystem.get_object('!').st_dev)
        self.assertEqual(2, self.filesystem.get_object('!foo').st_dev)
        self.assertEqual(3, self.filesystem.get_object('!bar').st_dev)
        self.assertEqual(4, self.filesystem.get_object('!foo!baz').st_dev)

    def test_that_new_directories_get_correct_device_number(self):
        self.add_mount_points()
        self.assertEqual(1, self.filesystem.create_dir('!foo1!bar').st_dev)
        self.assertEqual(2, self.filesystem.create_dir('!foo!bar').st_dev)
        self.assertEqual(4,
                         self.filesystem.create_dir('!foo!baz!foo!bar').st_dev)

    def test_that_new_files_get_correct_device_number(self):
        self.add_mount_points()
        self.assertEqual(1, self.filesystem.create_file('!foo1!bar').st_dev)
        self.assertEqual(2, self.filesystem.create_file('!foo!bar').st_dev)
        self.assertEqual(4, self.filesystem.create_file(
            '!foo!baz!foo!bar').st_dev)

    def test_that_mount_point_cannot_be_added_twice(self):
        self.add_mount_points()
        with self.raises_os_error(errno.EEXIST):
            self.filesystem.add_mount_point('!foo')
        with self.raises_os_error(errno.EEXIST):
            self.filesystem.add_mount_point('!foo!')

    def test_that_drives_are_auto_mounted(self):
        self.filesystem.is_windows_fs = True
        self.add_mount_points()
        self.filesystem.create_dir('d:!foo!bar')
        self.filesystem.create_file('d:!foo!baz')
        self.filesystem.create_file('z:!foo!baz')
        self.assertEqual(5, self.filesystem.get_object('d:').st_dev)
        self.assertEqual(5, self.filesystem.get_object('d:!foo!bar').st_dev)
        self.assertEqual(5, self.filesystem.get_object('d:!foo!baz').st_dev)
        self.assertEqual(6, self.filesystem.get_object('z:!foo!baz').st_dev)

    def test_that_drives_are_auto_mounted_case_insensitive(self):
        self.filesystem.is_windows_fs = True
        self.add_mount_points()
        self.filesystem.is_case_sensitive = False
        self.filesystem.create_dir('D:!foo!bar')
        self.filesystem.create_file('e:!foo!baz')
        self.assertEqual(5, self.filesystem.get_object('D:').st_dev)
        self.assertEqual(5, self.filesystem.get_object('d:!foo!bar').st_dev)
        self.assertEqual(6, self.filesystem.get_object('e:!foo').st_dev)
        self.assertEqual(6, self.filesystem.get_object('E:!Foo!Baz').st_dev)

    def test_that_unc_paths_are_auto_mounted(self):
        self.filesystem.is_windows_fs = True
        self.add_mount_points()
        self.filesystem.create_dir('!!foo!bar!baz')
        self.filesystem.create_file('!!foo!bar!bip!bop')
        self.assertEqual(5, self.filesystem.get_object('!!foo!bar').st_dev)
        self.assertEqual(5, self.filesystem.get_object(
            '!!foo!bar!bip!bop').st_dev)


class ConvenienceMethodTest(RealFsTestCase):

    def test_create_link_with_non_existent_parent(self):
        self.skip_if_symlink_not_supported()
        file1_path = self.make_path('test_file1')
        link_path = self.make_path('nonexistent', 'test_file2')

        self.filesystem.create_file(file1_path, contents='link test')
        self.assertEqual(self.os.stat(file1_path).st_nlink, 1)
        self.filesystem.create_link(file1_path, link_path)
        self.assertEqual(self.os.stat(file1_path).st_nlink, 2)
        self.assertTrue(self.filesystem.exists(link_path))

    def test_create_symlink_with_non_existent_parent(self):
        self.skip_if_symlink_not_supported()
        file1_path = self.make_path('test_file1')
        link_path = self.make_path('nonexistent', 'test_file2')

        self.filesystem.create_file(file1_path, contents='symlink test')
        self.filesystem.create_symlink(link_path, file1_path)
        self.assertTrue(self.filesystem.exists(link_path))
        self.assertTrue(self.filesystem.islink(link_path))


class RealFileSystemAccessTest(RealFsTestCase):
    def setUp(self):
        # use the real path separator to work with the real file system
        self.filesystem = fake_filesystem.FakeFilesystem()
        self.fake_open = fake_filesystem.FakeFileOpen(self.filesystem)
        self.pyfakefs_path = os.path.split(
            os.path.dirname(os.path.abspath(__file__)))[0]
        self.root_path = os.path.split(self.pyfakefs_path)[0]

    def test_add_non_existing_real_file_raises(self):
        nonexisting_path = os.path.join('nonexisting', 'test.txt')
        with self.assertRaises(OSError):
            self.filesystem.add_real_file(nonexisting_path)
        self.assertFalse(self.filesystem.exists(nonexisting_path))

    def test_add_non_existing_real_directory_raises(self):
        nonexisting_path = '/nonexisting'
        with self.raises_os_error(errno.ENOENT):
            self.filesystem.add_real_directory(nonexisting_path)
        self.assertFalse(self.filesystem.exists(nonexisting_path))

    def test_existing_fake_file_raises(self):
        real_file_path = __file__
        self.filesystem.create_file(real_file_path)
        with self.raises_os_error(errno.EEXIST):
            self.filesystem.add_real_file(real_file_path)

    def test_existing_fake_directory_raises(self):
        self.filesystem.create_dir(self.root_path)
        with self.raises_os_error(errno.EEXIST):
            self.filesystem.add_real_directory(self.root_path)

    def check_fake_file_stat(self, fake_file, real_file_path,
                             target_path=None):
        if target_path is None or target_path == real_file_path:
            self.assertTrue(self.filesystem.exists(real_file_path))
        else:
            self.assertFalse(self.filesystem.exists(real_file_path))
            self.assertTrue(self.filesystem.exists(target_path))

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
        if not is_root():
            with self.raises_os_error(errno.EACCES):
                self.fake_open(real_file_path, 'w')
        else:
            with self.fake_open(real_file_path, 'w'):
                pass

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
        real_file_path = os.path.abspath(__file__)
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

    def test_add_real_file_to_existing_path(self):
        real_file_path = os.path.abspath(__file__)
        self.filesystem.create_file('/foo/bar')
        with self.raises_os_error(errno.EEXIST):
            self.filesystem.add_real_file(real_file_path,
                                          target_path='/foo/bar')

    def test_add_real_file_to_non_existing_path(self):
        real_file_path = os.path.abspath(__file__)
        fake_file = self.filesystem.add_real_file(real_file_path,
                                                  target_path='/foo/bar')
        self.check_fake_file_stat(fake_file, real_file_path,
                                  target_path='/foo/bar')

    def test_write_to_real_file(self):
        # regression test for #470
        real_file_path = os.path.abspath(__file__)
        self.filesystem.add_real_file(real_file_path, read_only=False)
        with self.fake_open(real_file_path, 'w') as f:
            f.write('foo')

        with self.fake_open(real_file_path, 'rb') as f:
            self.assertEqual(b'foo', f.read())

    def test_add_existing_real_directory_read_only(self):
        self.filesystem.add_real_directory(self.pyfakefs_path)
        self.assertTrue(self.filesystem.exists(self.pyfakefs_path))
        self.assertTrue(self.filesystem.exists(
            os.path.join(self.pyfakefs_path, 'fake_filesystem.py')))
        self.assertTrue(self.filesystem.exists(
            os.path.join(self.pyfakefs_path, 'fake_pathlib.py')))

        file_path = os.path.join(self.pyfakefs_path,
                                 'fake_filesystem_shutil.py')
        fake_file = self.filesystem.resolve(file_path)
        self.check_fake_file_stat(fake_file, file_path)
        self.check_read_only_file(fake_file, file_path)

    def test_add_existing_real_directory_tree(self):
        self.filesystem.add_real_directory(self.root_path)
        self.assertTrue(
            self.filesystem.exists(
                os.path.join(self.root_path, 'pyfakefs', 'tests',
                             'fake_filesystem_test.py')))
        self.assertTrue(
            self.filesystem.exists(
                os.path.join(self.root_path, 'pyfakefs',
                             'fake_filesystem.py')))
        self.assertTrue(
            self.filesystem.exists(
                os.path.join(self.root_path, 'pyfakefs', '__init__.py')))

    @contextlib.contextmanager
    def create_symlinks(self, symlinks):
        for link in symlinks:
            os.symlink(link[0], link[1])

        yield

        for link in symlinks:
            os.unlink(link[1])

    def test_add_existing_real_directory_symlink(self):
        fake_open = fake_filesystem.FakeFileOpen(self.filesystem)
        real_directory = os.path.join(self.root_path, 'pyfakefs', 'tests')
        symlinks = [
            ('..', os.path.join(
                real_directory, 'fixtures', 'symlink_dir_relative')),
            ('../all_tests.py', os.path.join(
                real_directory, 'fixtures', 'symlink_file_relative')),
            (real_directory, os.path.join(
                real_directory, 'fixtures', 'symlink_dir_absolute')),
            (os.path.join(real_directory, 'all_tests.py'), os.path.join(
                real_directory, 'fixtures', 'symlink_file_absolute')),
            ('/etc/something', os.path.join(
                real_directory, 'fixtures', 'symlink_file_absolute_outside')),
        ]

        self.filesystem.create_file('/etc/something')

        with fake_open('/etc/something', 'w') as f:
            f.write('good morning')

        try:
            with self.create_symlinks(symlinks):
                self.filesystem.add_real_directory(
                    real_directory, lazy_read=False)
        except OSError:
            if self.is_windows:
                raise unittest.SkipTest(
                    'Symlinks under Windows need admin privileges')
            raise

        for link in symlinks:
            self.assertTrue(self.filesystem.islink(link[1]))

        # relative
        self.assertTrue(
            self.filesystem.exists(
                os.path.join(self.root_path, 'pyfakefs', 'tests',
                             'fixtures/symlink_dir_relative')))
        self.assertTrue(
            self.filesystem.exists(
                os.path.join(self.root_path, 'pyfakefs', 'tests',
                             'fixtures/symlink_dir_relative/all_tests.py')))
        self.assertTrue(
            self.filesystem.exists(
                os.path.join(self.root_path, 'pyfakefs', 'tests',
                             'fixtures/symlink_file_relative')))

        # absolute
        self.assertTrue(
            self.filesystem.exists(
                os.path.join(self.root_path, 'pyfakefs', 'tests',
                             'fixtures/symlink_dir_absolute')))
        self.assertTrue(
            self.filesystem.exists(
                os.path.join(self.root_path, 'pyfakefs', 'tests',
                             'fixtures/symlink_dir_absolute/all_tests.py')))
        self.assertTrue(
            self.filesystem.exists(
                os.path.join(self.root_path, 'pyfakefs', 'tests',
                             'fixtures/symlink_file_absolute')))

        # outside
        self.assertTrue(
            self.filesystem.exists(
                os.path.join(self.root_path, 'pyfakefs', 'tests',
                             'fixtures/symlink_file_absolute_outside')))
        self.assertEqual(
            fake_open(os.path.join(
                self.root_path, 'pyfakefs', 'tests',
                'fixtures/symlink_file_absolute_outside')).read(),
            'good morning'
        )

    def test_add_existing_real_directory_symlink_target_path(self):
        self.skip_if_symlink_not_supported(force_real_fs=True)
        real_directory = os.path.join(self.root_path, 'pyfakefs', 'tests')
        symlinks = [
            ('..', os.path.join(
                real_directory, 'fixtures', 'symlink_dir_relative')),
            ('../all_tests.py', os.path.join(
                real_directory, 'fixtures', 'symlink_file_relative')),
        ]

        with self.create_symlinks(symlinks):
            self.filesystem.add_real_directory(
                real_directory, target_path='/path', lazy_read=False)

        self.assertTrue(self.filesystem.exists(
            '/path/fixtures/symlink_dir_relative'))
        self.assertTrue(self.filesystem.exists(
            '/path/fixtures/symlink_dir_relative/all_tests.py'))
        self.assertTrue(self.filesystem.exists(
            '/path/fixtures/symlink_file_relative'))

    def test_add_existing_real_directory_symlink_lazy_read(self):
        self.skip_if_symlink_not_supported(force_real_fs=True)
        real_directory = os.path.join(self.root_path, 'pyfakefs', 'tests')
        symlinks = [
            ('..', os.path.join(
                real_directory, 'fixtures', 'symlink_dir_relative')),
            ('../all_tests.py', os.path.join(
                real_directory, 'fixtures', 'symlink_file_relative')),
        ]

        with self.create_symlinks(symlinks):
            self.filesystem.add_real_directory(
                real_directory, target_path='/path', lazy_read=True)

            self.assertTrue(self.filesystem.exists(
                '/path/fixtures/symlink_dir_relative'))
            self.assertTrue(self.filesystem.exists(
                '/path/fixtures/symlink_dir_relative/all_tests.py'))
            self.assertTrue(self.filesystem.exists(
                '/path/fixtures/symlink_file_relative'))

    def test_add_existing_real_directory_tree_to_existing_path(self):
        self.filesystem.create_dir('/foo/bar')
        with self.raises_os_error(errno.EEXIST):
            self.filesystem.add_real_directory(
                self.root_path, target_path='/foo/bar')

    def test_add_existing_real_directory_tree_to_other_path(self):
        self.filesystem.add_real_directory(self.root_path,
                                           target_path='/foo/bar')
        self.assertFalse(
            self.filesystem.exists(
                os.path.join(self.pyfakefs_path, 'tests',
                             'fake_filesystem_test.py')))
        self.assertTrue(
            self.filesystem.exists(
                os.path.join('foo', 'bar', 'pyfakefs', 'tests',
                             'fake_filesystem_test.py')))
        self.assertFalse(
            self.filesystem.exists(
                os.path.join(self.root_path, 'pyfakefs',
                             'fake_filesystem.py')))
        self.assertTrue(
            self.filesystem.exists(
                os.path.join('foo', 'bar', 'pyfakefs', '__init__.py')))

    def test_get_object_from_lazily_added_real_directory(self):
        self.filesystem.is_case_sensitive = True
        self.filesystem.add_real_directory(self.root_path)
        self.assertTrue(self.filesystem.get_object(
            os.path.join(self.root_path, 'pyfakefs', 'fake_filesystem.py')))
        self.assertTrue(
            self.filesystem.get_object(
                os.path.join(self.root_path, 'pyfakefs', '__init__.py')))

    def test_add_existing_real_directory_lazily(self):
        disk_size = 1024 * 1024 * 1024
        real_dir_path = os.path.join(self.root_path, 'pyfakefs')
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
        self.filesystem.set_disk_usage(disk_size, self.pyfakefs_path)
        self.filesystem.add_real_directory(self.pyfakefs_path, lazy_read=False)

        # the directory has been read, so the file sizes have
        # been subtracted from the free space
        self.assertGreater(disk_size, self.filesystem.get_disk_usage(
            self.pyfakefs_path).free)

    def test_add_existing_real_directory_read_write(self):
        self.filesystem.add_real_directory(self.pyfakefs_path, read_only=False)
        self.assertTrue(self.filesystem.exists(self.pyfakefs_path))
        self.assertTrue(self.filesystem.exists(
            os.path.join(self.pyfakefs_path, 'fake_filesystem.py')))
        self.assertTrue(self.filesystem.exists(
            os.path.join(self.pyfakefs_path, 'fake_pathlib.py')))

        file_path = os.path.join(self.pyfakefs_path, 'pytest_plugin.py')
        fake_file = self.filesystem.resolve(file_path)
        self.check_fake_file_stat(fake_file, file_path)
        self.check_writable_file(fake_file, file_path)

    def test_add_existing_real_paths_read_only(self):
        real_file_path = os.path.realpath(__file__)
        fixture_path = os.path.join(self.pyfakefs_path, 'tests', 'fixtures')
        self.filesystem.add_real_paths([real_file_path, fixture_path])

        fake_file = self.filesystem.resolve(real_file_path)
        self.check_fake_file_stat(fake_file, real_file_path)
        self.check_read_only_file(fake_file, real_file_path)

        real_file_path = os.path.join(fixture_path,
                                      'module_with_attributes.py')
        fake_file = self.filesystem.resolve(real_file_path)
        self.check_fake_file_stat(fake_file, real_file_path)
        self.check_read_only_file(fake_file, real_file_path)

    def test_add_existing_real_paths_read_write(self):
        real_file_path = os.path.realpath(__file__)
        fixture_path = os.path.join(self.pyfakefs_path, 'tests', 'fixtures')
        self.filesystem.add_real_paths([real_file_path, fixture_path],
                                       read_only=False)

        fake_file = self.filesystem.resolve(real_file_path)
        self.check_fake_file_stat(fake_file, real_file_path)
        self.check_writable_file(fake_file, real_file_path)

        real_file_path = os.path.join(fixture_path,
                                      'module_with_attributes.py')
        fake_file = self.filesystem.resolve(real_file_path)
        self.check_fake_file_stat(fake_file, real_file_path)
        self.check_writable_file(fake_file, real_file_path)


class FileSideEffectTests(TestCase):
    def side_effect(self):
        test_case = self
        test_case.side_effect_called = False

        def __side_effect(file_object):
            test_case.side_effect_called = True
            test_case.side_effect_file_object_content = file_object.contents
        return __side_effect

    def setUp(self):
        # use the real path separator to work with the real file system
        self.filesystem = fake_filesystem.FakeFilesystem()
        self.filesystem.create_file('/a/b/file_one',
                                    side_effect=self.side_effect())

    def test_side_effect_called(self):
        fake_open = fake_filesystem.FakeFileOpen(self.filesystem)
        self.side_effect_called = False
        with fake_open('/a/b/file_one', 'w') as handle:
            handle.write('foo')
        self.assertTrue(self.side_effect_called)

    def test_side_effect_file_object(self):
        fake_open = fake_filesystem.FakeFileOpen(self.filesystem)
        self.side_effect_called = False
        with fake_open('/a/b/file_one', 'w') as handle:
            handle.write('foo')
        self.assertEqual(self.side_effect_file_object_content, 'foo')


if __name__ == '__main__':
    unittest.main()
