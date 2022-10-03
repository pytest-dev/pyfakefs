# -*- coding: utf-8 -*-
#
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

"""Unit tests for fake_filesystem.FakeOpen."""

import errno
import os
import stat
import sys
import unittest

from pyfakefs.helpers import IN_DOCKER, IS_PYPY

from pyfakefs import fake_filesystem
from pyfakefs.fake_filesystem import (
    FakeFileOpen, is_root, USER_ID, set_uid, GROUP_ID, set_gid
)
from pyfakefs.extra_packages import (
    use_scandir, use_scandir_package, use_builtin_scandir
)

from pyfakefs.tests.test_utils import TestCase, RealFsTestCase


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
        self.assert_raises_os_error(errno.ENOTDIR, self.os.chdir, filename)

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
        self.assertEqual(self.filesystem.root_dir_name, self.os.getcwd())
        self.os.chdir(dirname)
        self.assertEqual(dirname, self.os.getcwd())

    def test_listdir(self):
        self.assert_raises_os_error(
            errno.ENOENT, self.os.listdir, 'non_existing/fake_dir')
        directory = self.make_path('xyzzy', 'plugh')
        files = ['foo', 'bar', 'baz']
        for f in files:
            self.create_file(self.os.path.join(directory, f))
        files.sort()
        self.assertEqual(files, sorted(self.os.listdir(directory)))

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
        self.assert_raises_os_error(errno.ENOTDIR, self.os.listdir, file_path)

    def test_exists_current_dir(self):
        self.assertTrue(self.os.path.exists('.'))

    def test_listdir_current(self):
        files = ['foo', 'bar', 'baz']
        for f in files:
            self.create_file(self.make_path(f))
        files.sort()
        self.assertEqual(files, sorted(self.os.listdir(self.base_path)))

    def test_fdopen(self):
        file_path1 = self.make_path('some_file1')
        self.create_file(file_path1, contents='contents here1')
        with self.open(file_path1, 'r') as fake_file1:
            fileno = fake_file1.fileno()
            fake_file2 = self.os.fdopen(fileno)
            self.assertNotEqual(fake_file2, fake_file1)

        with self.assertRaises(TypeError):
            self.os.fdopen(None)
        with self.assertRaises(TypeError):
            self.os.fdopen('a string')

    def test_out_of_range_fdopen(self):
        # test some file descriptor that is clearly out of range
        self.assert_raises_os_error(errno.EBADF, self.os.fdopen, 500)

    def test_closed_file_descriptor(self):
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
        if not is_root():
            with self.assertRaises(OSError):
                self.os.fdopen(fileno1, 'w')
        else:
            self.os.fdopen(fileno1, 'w')
            self.os.close(fileno1)

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

    def test_st_blocks(self):
        self.check_posix_only()
        file_path = self.make_path('foo1')
        self.create_file(file_path, contents=b"")
        self.assertEqual(0, self.os.stat(file_path).st_blocks)
        file_path = self.make_path('foo2')
        self.create_file(file_path, contents=b"t")
        self.assertEqual(8, self.os.stat(file_path).st_blocks)
        file_path = self.make_path('foo3')
        self.create_file(file_path, contents=b"t" * 4095)
        self.assertEqual(8, self.os.stat(file_path).st_blocks)
        file_path = self.make_path('foo4')
        self.create_file(file_path, contents=b"t" * 4096)
        self.assertEqual(8, self.os.stat(file_path).st_blocks)
        file_path = self.make_path('foo5')
        self.create_file(file_path, contents=b"t" * 4097)
        self.assertEqual(16, self.os.stat(file_path).st_blocks)

    def test_no_st_blocks_in_windows(self):
        self.check_windows_only()
        file_path = self.make_path('foo')
        self.create_file(file_path, contents=b"")
        with self.assertRaises(AttributeError):
            self.os.stat(file_path).st_blocks

    def test_stat_with_unc_path(self):
        self.skip_real_fs()
        self.check_windows_only()
        directory = '//root/share/dir'
        file_path = self.os.path.join(directory, 'plugh')
        self.create_file(file_path, contents='ABCDE')
        self.assertTrue(stat.S_IFDIR & self.os.stat(directory)[stat.ST_MODE])
        self.assertTrue(stat.S_IFREG & self.os.stat(file_path)[stat.ST_MODE])
        self.assertTrue(stat.S_IFREG & self.os.stat(file_path).st_mode)
        self.assertEqual(5, self.os.stat(file_path)[stat.ST_SIZE])

    def test_stat_with_drive(self):
        self.skip_real_fs()
        self.check_windows_only()
        directory = 'C:/foo/dir'
        file_path = self.os.path.join(directory, 'plugh')
        self.create_file(file_path, contents='ABCDE')
        self.assertTrue(stat.S_IFDIR & self.os.stat(directory)[stat.ST_MODE])
        self.assertTrue(stat.S_IFREG & self.os.stat(file_path)[stat.ST_MODE])
        self.assertTrue(stat.S_IFREG & self.os.stat(file_path).st_mode)
        self.assertEqual(5, self.os.stat(file_path)[stat.ST_SIZE])

    def test_stat_uses_open_fd_as_path(self):
        self.skip_real_fs()
        self.assert_raises_os_error(errno.EBADF, self.os.stat, 5)
        file_path = self.make_path('foo', 'bar')
        self.create_file(file_path)

        with self.open(file_path) as f:
            self.assertTrue(
                stat.S_IFREG & self.os.stat(f.filedes)[stat.ST_MODE])

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

    def test_lstat_trailing_sep(self):
        # regression test for #342
        stat_result = self.os.lstat(self.base_path)
        self.assertEqual(stat_result,
                         self.os.lstat(self.base_path + self.path_separator()))
        self.assertEqual(stat_result, self.os.lstat(
            self.base_path + self.path_separator() + self.path_separator()))

    def test_stat_with_byte_string(self):
        stat_str = self.os.stat(self.base_path)
        base_path_bytes = self.base_path.encode('utf8')
        stat_bytes = self.os.stat(base_path_bytes)
        self.assertEqual(stat_bytes, stat_str)

    def test_lstat_with_byte_string(self):
        stat_str = self.os.lstat(self.base_path)
        base_path_bytes = self.base_path.encode('utf8')
        stat_bytes = self.os.lstat(base_path_bytes)
        self.assertEqual(stat_bytes, stat_str)

    def test_stat_with_current_dir(self):
        # regression test for #516
        stat_result = self.os.stat('.')
        lstat_result = self.os.lstat('.')
        self.assertEqual(stat_result, lstat_result)

    def test_exists_with_trailing_sep(self):
        # regression test for #364
        file_path = self.make_path('alpha')
        self.create_file(file_path)
        self.assertFalse(self.os.path.exists(file_path + self.os.sep))

    def test_mkdir_with_trailing_sep(self):
        # regression test for #367
        dir_path = self.make_path('foo')
        self.os.mkdir(dir_path + self.os.sep + self.os.sep)
        self.assertTrue(self.os.path.exists(dir_path))

    def test_readlink_empty_path(self):
        self.check_posix_only()
        self.assert_raises_os_error(errno.ENOENT,
                                    self.os.readlink, '')

    def test_readlink_ending_with_sep_posix(self):
        # regression test for #359
        self.check_posix_only()
        link_path = self.make_path('foo')
        self.os.symlink(self.base_path, link_path)
        self.assert_raises_os_error(errno.EINVAL,
                                    self.os.readlink, link_path + self.os.sep)

    def test_lstat_symlink_with_trailing_sep_linux(self):
        # regression test for #366
        self.check_linux_only()
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('foo')
        self.os.symlink(self.base_path, link_path)
        # used to raise
        self.assertTrue(self.os.lstat(link_path + self.os.sep).st_mode)

    def test_lstat_symlink_with_trailing_sep_macos(self):
        # regression test for #366
        self.check_macos_only()
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('foo')
        self.os.symlink(self.base_path, link_path)
        # used to raise
        self.assertTrue(self.os.lstat(link_path + self.os.sep).st_mode)

    def test_readlink_ending_with_sep_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('foo')
        self.os.symlink(self.base_path, link_path)
        self.assert_equal_paths(self.base_path,
                                self.os.readlink(link_path + self.os.sep))

    def test_islink_with_trailing_sep_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('foo')
        self.os.symlink(self.base_path, link_path)
        self.assertTrue(self.os.path.islink(link_path + self.os.path.sep))

    def test_islink_with_trailing_sep_linux(self):
        self.check_linux_only()
        link_path = self.make_path('foo')
        self.os.symlink(self.base_path, link_path)
        self.assertFalse(self.os.path.islink(link_path + self.os.sep))

    def test_islink_with_trailing_sep_macos(self):
        self.check_macos_only()
        link_path = self.make_path('foo')
        self.os.symlink(self.base_path, link_path)
        self.assertFalse(self.os.path.islink(link_path + self.os.sep))

    def check_getsize_raises_with_trailing_separator(self, error_nr):
        file_path = self.make_path('bar')
        self.create_file(file_path)
        self.assert_raises_os_error(error_nr, self.os.path.getsize,
                                    file_path + self.os.sep)

    def test_getsize_raises_with_trailing_separator_posix(self):
        self.check_posix_only()
        self.check_getsize_raises_with_trailing_separator(errno.ENOTDIR)

    def test_getsize_raises_with_trailing_separator_windows(self):
        self.check_windows_only()
        self.check_getsize_raises_with_trailing_separator(errno.EINVAL)

    def check_remove_link_ending_with_sep(self, error_nr):
        # regression test for #360
        link_path = self.make_path('foo')
        self.os.symlink(self.base_path, link_path)
        self.assert_raises_os_error(error_nr,
                                    self.os.remove, link_path + self.os.sep)

    def test_remove_link_ending_with_sep_linux(self):
        self.check_linux_only()
        self.check_remove_link_ending_with_sep(errno.ENOTDIR)

    def test_remove_link_ending_with_sep_macos(self):
        self.check_macos_only()
        self.check_remove_link_ending_with_sep(errno.EPERM)

    def test_remove_link_ending_with_sep_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        self.check_remove_link_ending_with_sep(errno.EACCES)

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

    def check_open_raises_with_trailing_separator(self, error_nr):
        file_path = self.make_path('bar') + self.os.sep
        self.assert_raises_os_error(error_nr, self.os.open,
                                    file_path,
                                    os.O_CREAT | os.O_WRONLY | os.O_TRUNC)

    def test_open_raises_with_trailing_separator_linux(self):
        self.check_linux_only()
        self.check_open_raises_with_trailing_separator(errno.EISDIR)

    def test_open_raises_with_trailing_separator_macos(self):
        self.check_macos_only()
        self.check_open_raises_with_trailing_separator(errno.ENOENT)

    def test_open_raises_with_trailing_separator_windows(self):
        self.check_windows_only()
        self.check_open_raises_with_trailing_separator(errno.EINVAL)

    def test_lexists_with_trailing_separator_linux_windows(self):
        self.check_linux_and_windows()
        self.skip_if_symlink_not_supported()
        file_path = self.make_path('foo')
        self.os.symlink(file_path, file_path)
        self.assertFalse(self.os.path.lexists(file_path + self.os.sep))

    def test_lexists_with_trailing_separator_macos(self):
        # regression test for #373
        self.check_macos_only()
        file_path = self.make_path('foo')
        self.os.symlink(file_path, file_path)
        self.assertTrue(self.os.path.lexists(file_path + self.os.sep))

    def test_islink_with_trailing_separator_linux_windows(self):
        self.check_linux_and_windows()
        self.skip_if_symlink_not_supported()
        file_path = self.make_path('foo')
        self.os.symlink(file_path, file_path)
        self.assertFalse(self.os.path.islink(file_path + self.os.sep))

    def test_islink_with_trailing_separator_macos(self):
        # regression test for #373
        self.check_macos_only()
        file_path = self.make_path('foo')
        self.os.symlink(file_path, file_path)
        self.assertTrue(self.os.path.islink(file_path + self.os.sep))

    def test_isfile_with_trailing_separator_linux_windows(self):
        self.check_linux_and_windows()
        file_path = self.make_path('foo')
        self.create_file(file_path)
        self.assertFalse(self.os.path.isfile(file_path + self.os.sep))

    def test_isfile_with_trailing_separator_macos(self):
        # regression test for #374
        self.check_macos_only()
        file_path = self.make_path('foo')
        self.create_file(file_path)
        self.assertFalse(self.os.path.isfile(file_path + self.os.sep))

    def test_isfile_not_readable_file(self):
        file_path = self.make_path('foo')
        self.create_file(file_path, perm=0)
        self.assertTrue(self.os.path.isfile(file_path))

    def check_stat_with_trailing_separator(self, error_nr):
        # regression test for #376
        file_path = self.make_path('foo')
        self.create_file(file_path)
        self.assert_raises_os_error(error_nr, self.os.stat,
                                    file_path + self.os.sep)

    def test_stat_with_trailing_separator_posix(self):
        self.check_posix_only()
        self.check_stat_with_trailing_separator(errno.ENOTDIR)

    def test_stat_with_trailing_separator_windows(self):
        self.check_windows_only()
        self.check_stat_with_trailing_separator(errno.EINVAL)

    def check_remove_with_trailing_separator(self, error_nr):
        # regression test for #377
        file_path = self.make_path('foo')
        self.create_file(file_path)
        self.assert_raises_os_error(error_nr, self.os.remove,
                                    file_path + self.os.sep)

    def test_remove_with_trailing_separator_posix(self):
        self.check_posix_only()
        self.check_remove_with_trailing_separator(errno.ENOTDIR)

    def test_remove_with_trailing_separator_windows(self):
        self.check_windows_only()
        self.check_remove_with_trailing_separator(errno.EINVAL)

    def test_readlink(self):
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('foo', 'bar', 'baz')
        target = self.make_path('tarJAY')
        self.create_symlink(link_path, target)
        self.assert_equal_paths(self.os.readlink(link_path), target)

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
        with self.assertRaises(TypeError):
            self.os.readlink(None)

    def test_broken_symlink_with_trailing_separator_linux(self):
        self.check_linux_only()
        file_path = self.make_path('foo')
        link_path = self.make_path('link')
        self.os.symlink(file_path, link_path)
        self.assert_raises_os_error(errno.EEXIST, self.os.symlink,
                                    link_path + self.os.sep,
                                    link_path + self.os.sep)

    def test_broken_symlink_with_trailing_separator_macos(self):
        # regression test for #371
        self.check_macos_only()
        file_path = self.make_path('foo')
        link_path = self.make_path('link')
        self.os.symlink(file_path, link_path)
        self.os.symlink(link_path + self.os.sep, link_path + self.os.sep)

    def test_broken_symlink_with_trailing_separator_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        file_path = self.make_path('foo')
        link_path = self.make_path('link')
        self.os.symlink(file_path, link_path)
        self.assert_raises_os_error(errno.EINVAL, self.os.symlink,
                                    link_path + self.os.sep,
                                    link_path + self.os.sep)

    def test_circular_readlink_with_trailing_separator_linux(self):
        # Regression test for #372
        self.check_linux_only()
        file_path = self.make_path('foo')
        self.os.symlink(file_path, file_path)
        self.assert_raises_os_error(errno.ELOOP, self.os.readlink,
                                    file_path + self.os.sep)

    def test_circular_readlink_with_trailing_separator_macos(self):
        # Regression test for #372
        self.check_macos_only()
        file_path = self.make_path('foo')
        self.os.symlink(file_path, file_path)
        self.os.readlink(file_path + self.os.sep)

    def test_circular_readlink_with_trailing_separator_windows(self):
        # Regression test for #372
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        file_path = self.make_path('foo')
        self.os.symlink(file_path, file_path)
        self.assert_raises_os_error(errno.EINVAL, self.os.readlink,
                                    file_path + self.os.sep)

    def test_readlink_with_links_in_path(self):
        self.skip_if_symlink_not_supported()
        self.create_symlink(self.make_path('meyer', 'lemon', 'pie'),
                            self.make_path('yum'))
        self.create_symlink(self.make_path('geo', 'metro'),
                            self.make_path('meyer'))
        self.assert_equal_paths(self.make_path('yum'),
                                self.os.readlink(
                                    self.make_path('geo', 'metro',
                                                   'lemon', 'pie')))

    def test_readlink_with_chained_links_in_path(self):
        self.skip_if_symlink_not_supported()
        self.create_symlink(self.make_path(
            'eastern', 'european', 'wolfhounds', 'chase'),
            self.make_path('cats'))
        self.create_symlink(self.make_path('russian'),
                            self.make_path('eastern', 'european'))
        self.create_symlink(self.make_path('dogs'),
                            self.make_path('russian', 'wolfhounds'))
        self.assert_equal_paths(self.make_path('cats'),
                                self.os.readlink(
                                    self.make_path('dogs', 'chase')))

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

    def test_remove_dir_with_drive(self):
        # regression test for issue #337
        self.check_windows_only()
        self.skip_real_fs()
        dir_path = self.os.path.join('C:', 'test')
        self.filesystem.create_dir(dir_path)
        self.assert_raises_os_error(errno.EACCES, self.os.remove, dir_path)

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
        if not is_root():
            self.assert_raises_os_error(errno.EACCES, self.os.remove, path)
        else:
            self.os.remove(path)
            self.assertFalse(self.os.path.exists(path))
            self.create_file(path)
        self.os.chmod(parent_dir, 0o555)  # missing write permission
        if not is_root():
            self.assert_raises_os_error(errno.EACCES, self.os.remove, path)
        else:
            self.os.remove(path)
            self.assertFalse(self.os.path.exists(path))
            self.create_file(path)
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

    def check_rename_case_with_symlink(self, result):
        self.skip_if_symlink_not_supported()
        self.check_case_insensitive_fs()
        dir_path_lower = self.make_path('beta')
        self.create_dir(dir_path_lower)
        link_path = self.make_path('b')
        self.os.symlink(self.base_path, link_path)
        path1 = self.os.path.join(link_path, 'Beta')
        dir_path_upper = self.make_path('Beta')
        self.os.rename(path1, dir_path_upper)
        self.assertEqual(result, sorted(self.os.listdir(self.base_path)))

    def test_rename_case_with_symlink_mac(self):
        # Regression test for #322
        self.check_macos_only()
        self.check_rename_case_with_symlink(['b', 'beta'])

    def test_rename_case_with_symlink_windows(self):
        self.check_windows_only()
        self.check_rename_case_with_symlink(['Beta', 'b'])

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
        self.skip_if_symlink_not_supported()
        base_path = self.make_path('foo')
        self.create_dir(base_path)
        symlink_path = self.os.path.join(base_path, 'slink')
        self.os.symlink(base_path, symlink_path)
        file_path = self.os.path.join(base_path, 'slink', 'beta')
        self.create_file(file_path)
        link_path = self.os.path.join(base_path, 'slink', 'gamma')
        self.os.link(file_path, link_path)
        self.assertTrue(self.os.path.exists(link_path))
        self.assertFalse(self.os.path.islink(link_path))

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

    def test_rename_to_existing_dir_under_posix_raises_if_not_empty(self):
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
        with self.assertRaises(OSError):
            self.os.rename(old_path, new_path)

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
        self.assert_raises_os_error(
            errno.EEXIST, self.os.rename, old_file_path, new_file_path)

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
        self.assert_raises_os_error(
            errno.ENOENT, self.os.rename, old_file_path, new_file_path)
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

    def check_append_mode_tell_after_truncate(self, tell_result):
        file_path = self.make_path('baz')
        with self.open(file_path, 'w') as f0:
            with self.open(file_path, 'a') as f1:
                f1.write('abcde')
                f0.seek(2)
                f0.truncate()
                self.assertEqual(tell_result, f1.tell())
        with self.open(file_path, mode='rb') as f:
            self.assertEqual(b'\0\0abcde', f.read())

    def test_append_mode_tell_linux_windows(self):
        # Regression test for #300
        self.check_linux_and_windows()
        self.check_append_mode_tell_after_truncate(7)

    def test_append_mode_tell_macos(self):
        # Regression test for #300
        self.check_macos_only()
        self.check_append_mode_tell_after_truncate(7)

    def test_tell_after_seek_in_append_mode(self):
        # Regression test for #363
        file_path = self.make_path('foo')
        with self.open(file_path, 'a') as f:
            f.seek(1)
            self.assertEqual(1, f.tell())

    def test_tell_after_seekback_in_append_mode(self):
        # Regression test for #414
        file_path = self.make_path('foo')
        with self.open(file_path, 'a') as f:
            f.write('aa')
            f.seek(1)
            self.assertEqual(1, f.tell())

    def test_dir_with_trailing_sep_is_dir(self):
        # regression test for #387
        self.assertTrue(self, self.os.path.isdir(self.base_path + self.os.sep))

    def check_rename_dir_with_trailing_sep(self, error):
        dir_path = self.make_path('dir') + self.os.sep
        self.os.mkdir(dir_path)
        self.assert_raises_os_error(error,
                                    self.os.rename, dir_path, self.base_path)

    def test_rename_dir_with_trailing_sep_posix(self):
        # regression test for #406
        self.check_posix_only()
        self.check_rename_dir_with_trailing_sep(errno.ENOTEMPTY)

    def test_rename_dir_with_trailing_sep_windows(self):
        self.check_windows_only()
        self.check_rename_dir_with_trailing_sep(errno.EEXIST)

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
        old_file.st_mtime = old_file.st_mtime - 3600
        self.os.chown(old_file_path, 200, 200)
        self.os.chmod(old_file_path, 0o222)
        self.create_file(new_file_path)
        new_file = self.filesystem.get_object(new_file_path)
        self.assertNotEqual(new_file.st_mtime, old_file.st_mtime)
        self.os.rename(old_file_path, new_file_path)
        new_file = self.filesystem.get_object(
            new_file_path, check_read_perm=False)
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
        self.assert_raises_os_error(errno.ENOTDIR, self.os.rmdir, file_path)
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
        self.assertTrue(
            self.remove_dirs_check(self.make_path('test1', 'test2')))
        self.assertFalse(self.os.path.exists(self.make_path('test1', 'test2')))
        self.assertFalse(self.os.path.exists(self.make_path('test1')))

    def test_removedirs_raises_if_removing_root(self):
        """Raises exception if asked to remove '/'."""
        self.skip_real_fs()
        self.os.rmdir(self.base_path)
        directory = self.os.path.splitdrive(
            self.base_path)[0] + self.os.path.sep
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
        while self.os.path.splitdrive(head)[1] != self.os.path.sep:
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
        self.assert_raises_os_error(errno.ENOTDIR,
                                    self.os.removedirs, dir_link)

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
        if not is_root():
            self.assert_raises_os_error(errno.EACCES, self.os.mkdir, directory)
        else:
            self.os.mkdir(directory)
            self.assertTrue(self.os.path.exists(directory))

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
        self.os.makedirs(name=new_dir)
        self.assertTrue(self.os.path.exists(new_dir))

    def test_makedirs_raises_if_access_denied(self):
        """makedirs raises exception if access denied."""
        self.check_posix_only()
        directory = self.make_path('a')
        self.os.mkdir(directory)

        # Change directory permissions to be read only.
        self.os.chmod(directory, 0o400)

        directory = self.make_path('a', 'b')
        if not is_root():
            with self.assertRaises(Exception):
                self.os.makedirs(directory)
        else:
            self.os.makedirs(directory)
            self.assertTrue(self.os.path.exists(directory))

    def test_makedirs_exist_ok(self):
        """makedirs uses the exist_ok argument"""
        directory = self.make_path('xyzzy', 'foo')
        self.create_dir(directory)
        self.assertTrue(self.os.path.exists(directory))

        self.assert_raises_os_error(errno.EEXIST, self.os.makedirs, directory)
        self.os.makedirs(directory, exist_ok=True)
        self.assertTrue(self.os.path.exists(directory))

    def test_makedirs_in_write_protected_dir(self):
        self.check_posix_only()
        directory = self.make_path('foo')
        self.os.mkdir(directory, mode=0o555)
        subdir = self.os.path.join(directory, 'bar')
        if not is_root():
            self.assert_raises_os_error(errno.EACCES, self.os.makedirs,
                                        subdir, exist_ok=True)
            self.assert_raises_os_error(errno.EACCES, self.os.makedirs,
                                        subdir, exist_ok=False)
        else:
            self.os.makedirs(subdir)
            self.assertTrue(self.os.path.exists(subdir))

    def test_makedirs_raises_on_empty_path(self):
        self.assert_raises_os_error(
            errno.ENOENT, self.os.makedirs, '', exist_ok=False)
        self.assert_raises_os_error(
            errno.ENOENT, self.os.makedirs, '', exist_ok=True)

    # test fsync and fdatasync
    def test_fsync_raises_on_non_int(self):
        with self.assertRaises(TypeError):
            self.os.fsync("zero")

    def test_fdatasync_raises_on_non_int(self):
        self.check_linux_only()
        self.assertRaises(TypeError, self.os.fdatasync, "zero")

    def test_fsync_raises_on_invalid_fd(self):
        self.assert_raises_os_error(errno.EBADF, self.os.fsync, 500)

    def test_fdatasync_raises_on_invalid_fd(self):
        # No open files yet
        self.check_linux_only()
        self.assert_raises_os_error(errno.EINVAL, self.os.fdatasync, 0)
        self.assert_raises_os_error(errno.EBADF, self.os.fdatasync, 500)

    def test_fsync_pass_posix(self):
        self.check_posix_only()
        test_file_path = self.make_path('test_file')
        self.create_file(test_file_path, contents='dummy file contents')
        with self.open(test_file_path, 'r') as test_file:
            test_fd = test_file.fileno()
            # Test that this doesn't raise anything
            self.os.fsync(test_fd)
            # And just for sanity, double-check that this still raises
            self.assert_raises_os_error(errno.EBADF,
                                        self.os.fsync, test_fd + 500)

    def test_fsync_pass_windows(self):
        self.check_windows_only()
        test_file_path = self.make_path('test_file')
        self.create_file(test_file_path, contents='dummy file contents')
        with self.open(test_file_path, 'r+') as test_file:
            test_fd = test_file.fileno()
            # Test that this doesn't raise anything
            self.os.fsync(test_fd)
            # And just for sanity, double-check that this still raises
            self.assert_raises_os_error(errno.EBADF,
                                        self.os.fsync, test_fd + 500)
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
        self.assert_raises_os_error(errno.EBADF,
                                    self.os.fdatasync, test_fd + 500)

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
        self.assertFalse(self.os.access(path, self.os.X_OK))
        self.assertFalse(self.os.access(path, self.rwx))
        if is_root():
            self.assertTrue(self.os.access(path, self.os.W_OK))
            self.assertTrue(self.os.access(path, self.rw))
        else:
            self.assertFalse(self.os.access(path, self.os.W_OK))
            self.assertFalse(self.os.access(path, self.rw))

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
        if is_root():
            self.assertTrue(self.os.access(link_path, self.os.W_OK))
            self.assertTrue(self.os.access(link_path, self.rw))
        else:
            self.assertFalse(self.os.access(link_path, self.os.W_OK))
            self.assertFalse(self.os.access(link_path, self.rw))
        self.assertFalse(self.os.access(link_path, self.os.X_OK))
        self.assertFalse(self.os.access(link_path, self.rwx))

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

    def test_effective_ids_not_supported_under_windows(self):
        self.check_windows_only()
        path = self.make_path('foo', 'bar')
        with self.assertRaises(NotImplementedError):
            self.os.access(path, self.os.F_OK, effective_ids=True)

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

    def test_chmod_follow_symlink(self):
        self.check_posix_only()
        path = self.make_path('some_file')
        self.createTestFile(path)
        link_path = self.make_path('link_to_some_file')
        self.create_symlink(link_path, path)
        self.os.chmod(link_path, 0o6543)

        st = self.os.stat(link_path)
        self.assert_mode_equal(0o6543, st.st_mode)
        st = self.os.stat(link_path, follow_symlinks=False)
        # the exact mode depends on OS and Python version
        self.assertEqual(stat.S_IMODE(0o700), stat.S_IMODE(st.st_mode) & 0o700)

    def test_chmod_no_follow_symlink(self):
        self.check_posix_only()
        path = self.make_path('some_file')
        self.createTestFile(path)
        link_path = self.make_path('link_to_some_file')
        self.create_symlink(link_path, path)
        if os.chmod not in os.supports_follow_symlinks or IS_PYPY:
            with self.assertRaises(NotImplementedError):
                self.os.chmod(link_path, 0o6543, follow_symlinks=False)
        else:
            self.os.chmod(link_path, 0o6543, follow_symlinks=False)
            st = self.os.stat(link_path)
            self.assert_mode_equal(0o666, st.st_mode)
            st = self.os.stat(link_path, follow_symlinks=False)
            self.assert_mode_equal(0o6543, st.st_mode)

    def test_lchmod(self):
        """lchmod shall behave like chmod with follow_symlinks=True."""
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
        self.os.chmod(path, 0o1434)
        st = self.os.stat(path)
        self.assert_mode_equal(0o1434, st.st_mode)
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
        self.assert_raises_os_error(
            errno.ENOENT, self.os.chown, file_path, 100, 100)

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
        # behavior seems to have changed in ubuntu-20.04, version 20210606.1
        # skipping real fs tests for now
        self.skip_real_fs()
        filename = 'abcde'
        if not is_root():
            self.assert_raises_os_error(errno.EPERM, self.os.mknod, filename,
                                        stat.S_IFCHR)
        else:
            self.os.mknod(filename, stat.S_IFCHR)
            self.os.remove(filename)

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
        dir_path = self.make_path('dir')
        self.create_dir(dir_path)
        self.assert_raises_os_error(errno.EEXIST, self.os.symlink,
                                    self.base_path, dir_path + self.os.sep)

        dir_path = self.make_path('bar')
        self.assert_raises_os_error(errno.ENOENT, self.os.symlink,
                                    self.base_path, dir_path + self.os.sep)

    def test_symlink_with_path_ending_with_sep_in_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        dir_path = self.make_path('dir')
        self.create_dir(dir_path)
        self.assert_raises_os_error(errno.EEXIST, self.os.symlink,
                                    self.base_path, dir_path + self.os.sep)

        dir_path = self.make_path('bar')
        # does not raise under Windows
        self.os.symlink(self.base_path, dir_path + self.os.sep)

    def test_broken_symlink_with_trailing_sep_posix(self):
        # Regression test for #390
        self.check_linux_only()
        path0 = self.make_path('foo') + self.os.sep
        self.assert_raises_os_error(
            errno.ENOENT, self.os.symlink, path0, path0)

    def test_broken_symlink_with_trailing_sep_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        path0 = self.make_path('foo') + self.os.sep
        self.assert_raises_os_error(
            errno.EINVAL, self.os.symlink, path0, path0)

    def test_rename_symlink_with_trailing_sep_linux(self):
        # Regression test for #391
        self.check_linux_only()
        path = self.make_path('foo')
        self.os.symlink(self.base_path, path)
        self.assert_raises_os_error(errno.ENOTDIR, self.os.rename,
                                    path + self.os.sep, self.base_path)

    def test_rename_symlink_with_trailing_sep_macos(self):
        # Regression test for #391
        self.check_macos_only()
        path = self.make_path('foo')
        self.os.symlink(self.base_path, path)
        self.os.rename(path + self.os.sep, self.base_path)

    def test_rename_symlink_with_trailing_sep_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        path = self.make_path('foo')
        self.os.symlink(self.base_path, path)
        self.assert_raises_os_error(errno.EEXIST, self.os.rename,
                                    path + self.os.sep, self.base_path)

    def test_rename_symlink_to_other_case(self):
        # Regression test for #389
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('foo')
        self.os.symlink(self.base_path, link_path)
        link_to_link_path = self.make_path('BAR')
        self.os.symlink(link_path, link_to_link_path)
        new_link_to_link_path = self.os.path.join(link_path, 'bar')
        self.os.rename(link_to_link_path, new_link_to_link_path)
        self.assertEqual(['bar', 'foo'],
                         sorted(self.os.listdir(new_link_to_link_path)))

    def create_broken_link_path_with_trailing_sep(self):
        # Regression tests for #396
        self.skip_if_symlink_not_supported()
        link_path = self.make_path('link')
        target_path = self.make_path('target')
        self.os.symlink(target_path, link_path)
        link_path += self.os.sep
        return link_path

    def test_lstat_broken_link_with_trailing_sep_linux(self):
        self.check_linux_only()
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.assert_raises_os_error(errno.ENOENT, self.os.lstat, link_path)

    def test_lstat_broken_link_with_trailing_sep_macos(self):
        self.check_macos_only()
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.assert_raises_os_error(errno.ENOENT, self.os.lstat, link_path)

    def test_lstat_broken_link_with_trailing_sep_windows(self):
        self.check_windows_only()
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.assert_raises_os_error(errno.EINVAL, self.os.lstat, link_path)

    def test_mkdir_broken_link_with_trailing_sep_linux_windows(self):
        self.check_linux_and_windows()
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.assert_raises_os_error(errno.EEXIST, self.os.mkdir, link_path)
        self.assert_raises_os_error(errno.EEXIST, self.os.makedirs, link_path)

    def test_mkdir_broken_link_with_trailing_sep_macos(self):
        self.check_macos_only()
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.os.mkdir(link_path)  # no error

    def test_makedirs_broken_link_with_trailing_sep_macos(self):
        self.check_macos_only()
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.os.makedirs(link_path)  # no error

    def test_remove_broken_link_with_trailing_sep_linux(self):
        self.check_linux_only()
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.assert_raises_os_error(errno.ENOTDIR, self.os.remove, link_path)

    def test_remove_broken_link_with_trailing_sep_macos(self):
        self.check_macos_only()
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.assert_raises_os_error(errno.ENOENT, self.os.remove, link_path)

    def test_remove_broken_link_with_trailing_sep_windows(self):
        self.check_windows_only()
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.assert_raises_os_error(errno.EINVAL, self.os.remove, link_path)

    def test_rename_broken_link_with_trailing_sep_linux(self):
        self.check_linux_only()
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.assert_raises_os_error(
            errno.ENOTDIR, self.os.rename, link_path, self.make_path('target'))

    def test_rename_broken_link_with_trailing_sep_macos(self):
        self.check_macos_only()
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.assert_raises_os_error(
            errno.ENOENT, self.os.rename, link_path, self.make_path('target'))

    def test_rename_broken_link_with_trailing_sep_windows(self):
        self.check_windows_only()
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.assert_raises_os_error(
            errno.EINVAL, self.os.rename, link_path, self.make_path('target'))

    def test_readlink_broken_link_with_trailing_sep_posix(self):
        self.check_posix_only()
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.assert_raises_os_error(errno.ENOENT, self.os.readlink, link_path)

    def test_readlink_broken_link_with_trailing_sep_windows(self):
        self.check_windows_only()
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.assert_raises_os_error(errno.EINVAL, self.os.readlink, link_path)

    def test_islink_broken_link_with_trailing_sep(self):
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.assertFalse(self.os.path.islink(link_path))

    def test_lexists_broken_link_with_trailing_sep(self):
        link_path = self.create_broken_link_path_with_trailing_sep()
        self.assertFalse(self.os.path.lexists(link_path))

    def test_rename_link_with_trailing_sep_to_self_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        path = self.make_path('foo')
        self.os.symlink(self.base_path, path)
        self.os.rename(path + self.os.sep, path)  # no error

    def test_rename_link_with_trailing_sep_to_self_posix(self):
        # Regression test for #395
        self.check_posix_only()
        path = self.make_path('foo')
        self.os.symlink(self.base_path, path)
        self.assert_raises_os_error(
            errno.ENOTDIR, self.os.rename, path + self.os.sep, path)

    def check_open_broken_symlink_to_path_with_trailing_sep(self, error):
        # Regression tests for #397
        self.skip_if_symlink_not_supported()
        target_path = self.make_path('target') + self.os.sep
        link_path = self.make_path('link')
        self.os.symlink(target_path, link_path)
        self.assert_raises_os_error(error, self.open, link_path, 'a')
        self.assert_raises_os_error(error, self.open, link_path, 'w')

    def test_open_broken_symlink_to_path_with_trailing_sep_linux(self):
        self.check_linux_only()
        self.check_open_broken_symlink_to_path_with_trailing_sep(errno.EISDIR)

    def test_open_broken_symlink_to_path_with_trailing_sep_macos(self):
        self.check_macos_only()
        self.check_open_broken_symlink_to_path_with_trailing_sep(errno.ENOENT)

    def test_open_broken_symlink_to_path_with_trailing_sep_windows(self):
        self.check_windows_only()
        self.check_open_broken_symlink_to_path_with_trailing_sep(errno.EINVAL)

    def check_link_path_ending_with_sep(self, error):
        # Regression tests for #399
        self.skip_if_symlink_not_supported()
        file_path = self.make_path('foo')
        link_path = self.make_path('link')
        with self.open(file_path, 'w'):
            self.assert_raises_os_error(
                error, self.os.link, file_path + self.os.sep, link_path)

    def test_link_path_ending_with_sep_posix(self):
        self.check_posix_only()
        self.check_link_path_ending_with_sep(errno.ENOTDIR)

    def test_link_path_ending_with_sep_windows(self):
        self.check_windows_only()
        self.check_link_path_ending_with_sep(errno.EINVAL)

    def test_link_to_path_ending_with_sep_posix(self):
        # regression test for #407
        self.check_posix_only()
        path0 = self.make_path('foo') + self.os.sep
        path1 = self.make_path('bar')
        with self.open(path1, 'w'):
            self.assert_raises_os_error(errno.ENOENT,
                                        self.os.link, path1, path0)

    def test_link_to_path_ending_with_sep_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        path0 = self.make_path('foo') + self.os.sep
        path1 = self.make_path('bar')
        with self.open(path1, 'w'):
            self.os.link(path1, path0)
            self.assertTrue(self.os.path.exists(path1))

    def check_rename_to_path_ending_with_sep(self, error):
        # Regression tests for #400
        file_path = self.make_path('foo')
        with self.open(file_path, 'w'):
            self.assert_raises_os_error(
                error, self.os.rename, file_path + self.os.sep, file_path)

    def test_rename_to_path_ending_with_sep_posix(self):
        self.check_posix_only()
        self.check_rename_to_path_ending_with_sep(errno.ENOTDIR)

    def test_rename_to_path_ending_with_sep_windows(self):
        self.check_windows_only()
        self.check_rename_to_path_ending_with_sep(errno.EINVAL)

    def test_rmdir_link_with_trailing_sep_linux(self):
        self.check_linux_only()
        dir_path = self.make_path('foo')
        self.os.mkdir(dir_path)
        link_path = self.make_path('link')
        self.os.symlink(dir_path, link_path)
        self.assert_raises_os_error(
            errno.ENOTDIR, self.os.rmdir, link_path + self.os.sep)

    def test_rmdir_link_with_trailing_sep_macos(self):
        # Regression test for #398
        self.check_macos_only()
        dir_path = self.make_path('foo')
        self.os.mkdir(dir_path)
        link_path = self.make_path('link')
        self.os.symlink(dir_path, link_path)
        self.os.rmdir(link_path + self.os.sep)
        self.assertFalse(self.os.path.exists(link_path))

    def test_rmdir_link_with_trailing_sep_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        dir_path = self.make_path('foo')
        self.os.mkdir(dir_path)
        link_path = self.make_path('link')
        self.os.symlink(dir_path, link_path)
        self.os.rmdir(link_path + self.os.sep)
        self.assertFalse(self.os.path.exists(link_path))

    def test_readlink_circular_link_with_trailing_sep_linux(self):
        self.check_linux_only()
        path1 = self.make_path('foo')
        path0 = self.make_path('bar')
        self.os.symlink(path0, path1)
        self.os.symlink(path1, path0)
        self.assert_raises_os_error(
            errno.ELOOP, self.os.readlink, path0 + self.os.sep)

    def test_readlink_circular_link_with_trailing_sep_macos(self):
        # Regression test for #392
        self.check_macos_only()
        path1 = self.make_path('foo')
        path0 = self.make_path('bar')
        self.os.symlink(path0, path1)
        self.os.symlink(path1, path0)
        self.assertEqual(path0, self.os.readlink(path0 + self.os.sep))

    def test_readlink_circular_link_with_trailing_sep_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        path1 = self.make_path('foo')
        path0 = self.make_path('bar')
        self.os.symlink(path0, path1)
        self.os.symlink(path1, path0)
        self.assert_raises_os_error(
            errno.EINVAL, self.os.readlink, path0 + self.os.sep)

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
        self.assert_raises_os_error(
            errno.ENOENT, self.os.link, file1_path, breaking_link_path)

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
        self.assert_mode_equal(
            0o755, self.os.stat(self.make_path('p1')).st_mode)
        self.assert_mode_equal(
            0o755, self.os.stat(self.make_path('p1', 'dir1')).st_mode)
        self.os.umask(0o67)
        self.os.makedirs(self.make_path('p2', 'dir2'))
        self.assert_mode_equal(
            0o710, self.os.stat(self.make_path('p2')).st_mode)
        self.assert_mode_equal(
            0o710, self.os.stat(self.make_path('p2', 'dir2')).st_mode)

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

    def test_open_pipe(self):
        read_fd, write_fd = self.os.pipe()
        self.os.close(read_fd)
        self.os.close(write_fd)

    def test_open_pipe_with_existing_fd(self):
        file1 = self.make_path('file1')
        fd = self.os.open(file1, os.O_CREAT)
        read_fd, write_fd = self.os.pipe()
        self.assertGreater(read_fd, fd)
        self.os.close(fd)
        self.os.close(read_fd)
        self.os.close(write_fd)

    def test_open_file_with_existing_pipe(self):
        read_fd, write_fd = self.os.pipe()
        file1 = self.make_path('file1')
        fd = self.os.open(file1, os.O_CREAT)
        self.assertGreater(fd, write_fd)
        self.os.close(read_fd)
        self.os.close(write_fd)
        self.os.close(fd)

    def test_read_write_pipe(self):
        read_fd, write_fd = self.os.pipe()
        self.assertEqual(4, self.os.write(write_fd, b'test'))
        self.assertEqual(b'test', self.os.read(read_fd, 4))
        self.os.close(read_fd)
        self.os.close(write_fd)

    def test_open_existing_pipe(self):
        # create some regular files to ensure that real and fake fd
        # are out of sync (see #581)
        fds = []
        for i in range(5):
            path = self.make_path('file' + str(i))
            fds.append(self.os.open(path, os.O_CREAT))
        file_path = self.make_path('file.txt')
        self.create_file(file_path)
        with self.open(file_path):
            read_fd, write_fd = self.os.pipe()
            with self.open(write_fd, 'wb') as f:
                self.assertEqual(4, f.write(b'test'))
            with self.open(read_fd, 'rb') as f:
                self.assertEqual(b'test', f.read())
        for fd in fds:
            self.os.close(fd)

    def test_write_to_pipe(self):
        read_fd, write_fd = self.os.pipe()
        self.os.write(write_fd, b'test')
        self.assertEqual(b'test', self.os.read(read_fd, 4))
        self.os.close(read_fd)
        self.os.close(write_fd)

    def test_write_to_read_fd(self):
        read_fd, write_fd = self.os.pipe()
        self.assert_raises_os_error(errno.EBADF,
                                    self.os.write, read_fd, b'test')
        self.os.close(read_fd)
        self.os.close(write_fd)

    def test_truncate(self):
        file_path = self.make_path('foo', 'bar')
        self.create_file(file_path, contents='012345678901234567')
        self.os.truncate(file_path, 10)
        with self.open(file_path) as f:
            self.assertEqual('0123456789', f.read())

    def test_truncate_non_existing(self):
        self.assert_raises_os_error(errno.ENOENT, self.os.truncate, 'foo', 10)

    def test_truncate_to_larger(self):
        file_path = self.make_path('foo', 'bar')
        self.create_file(file_path, contents='0123456789')
        fd = self.os.open(file_path, os.O_RDWR)
        self.os.truncate(fd, 20)
        self.assertEqual(20, self.os.stat(file_path).st_size)
        with self.open(file_path) as f:
            self.assertEqual('0123456789' + '\0' * 10, f.read())

    def test_truncate_with_fd(self):
        if os.truncate not in os.supports_fd:
            self.skip_real_fs()
        self.assert_raises_os_error(errno.EBADF, self.os.ftruncate, 50, 10)
        file_path = self.make_path('some_file')
        self.create_file(file_path, contents='01234567890123456789')

        fd = self.os.open(file_path, os.O_RDWR)
        self.os.truncate(fd, 10)
        self.assertEqual(10, self.os.stat(file_path).st_size)
        with self.open(file_path) as f:
            self.assertEqual('0123456789', f.read())

    def test_ftruncate(self):
        if self.is_pypy:
            # not correctly supported
            self.skip_real_fs()
        self.assert_raises_os_error(errno.EBADF, self.os.ftruncate, 50, 10)
        file_path = self.make_path('some_file')
        self.create_file(file_path, contents='0123456789012345')

        fd = self.os.open(file_path, os.O_RDWR)
        self.os.truncate(fd, 10)
        self.assertEqual(10, self.os.stat(file_path).st_size)
        with self.open(file_path) as f:
            self.assertEqual('0123456789', f.read())


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
        self.assert_raises_os_error(errno.ENOTDIR, self.os.chdir, filename1)

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
        if not is_root():
            self.assertRaises(OSError, self.os.fdopen, fileno1, 'w')
        else:
            self.os.fdopen(fileno1, 'w')

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
        self.assertEqual(len(file_contents), self.os.stat(
            file_path.upper(), follow_symlinks=False)[stat.ST_SIZE])
        self.assertEqual(len(base_name), self.os.stat(
            link_path.upper(), follow_symlinks=False)[stat.ST_SIZE])

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
        self.assert_equal_paths(self.os.readlink(link_path.upper()), target)

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
        self.assert_equal_paths(self.make_path('yum'),
                                self.os.readlink(
                                    self.make_path('Geo', 'Metro',
                                                   'Lemon', 'Pie')))

    def test_readlink_with_chained_links_in_path(self):
        self.skip_if_symlink_not_supported()
        self.create_symlink(self.make_path(
            'eastern', 'european', 'wolfhounds', 'chase'),
            self.make_path('cats'))
        self.create_symlink(self.make_path('russian'),
                            self.make_path('Eastern', 'European'))
        self.create_symlink(self.make_path('dogs'),
                            self.make_path('Russian', 'Wolfhounds'))
        self.assert_equal_paths(self.make_path('cats'),
                                self.os.readlink(
                                    self.make_path('DOGS', 'Chase')))

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
        # seems to behave differently under different MacOS versions
        self.skip_real_fs()
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
        self.assert_raises_os_error(
            errno.EACCES, self.os.rename, file_path,
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

    def test_renames_creates_missing_dirs(self):
        old_path = self.make_path("foo.txt")
        self.create_file(old_path)
        new_path = self.make_path("new", "dir", "bar.txt")
        self.os.renames(old_path, new_path)
        self.assertTrue(self.os.path.exists(new_path))
        self.assertFalse(self.os.path.exists(old_path))

    def test_renames_removes_empty_dirs(self):
        old_base_path = self.make_path("old")
        old_path = self.make_path("old", "dir1", "dir2", "foo.txt")
        other_file = self.os.path.join(old_base_path, "foo.png")
        self.create_file(old_path)
        self.create_file(other_file)
        new_path = self.make_path("new", "bar.txt")
        self.os.renames(old_path, new_path)
        self.assertTrue(self.os.path.exists(new_path))
        self.assertFalse(self.os.path.exists(old_path))
        self.assertTrue(self.os.path.exists(old_base_path))
        removed_path = self.os.path.join(old_base_path, "dir1")
        self.assertFalse(self.os.path.exists(removed_path))

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
        self.skip_if_symlink_not_supported()
        base_path = self.make_path('foo')
        self.create_dir(base_path)
        symlink_path = self.os.path.join(base_path, 'slink')
        self.os.symlink(base_path.upper(), symlink_path)
        file_path = self.os.path.join(base_path, 'slink', 'beta')
        self.create_file(file_path)
        link_path = self.os.path.join(base_path, 'Slink', 'gamma')
        self.os.link(file_path, link_path)
        self.assertTrue(self.os.path.exists(link_path))

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

    def check_rename_case_only_with_symlink_parent(self):
        # Regression test for #319
        self.os.symlink(self.base_path, self.make_path('link'))
        dir_upper = self.make_path('link', 'Alpha')
        self.os.mkdir(dir_upper)
        dir_lower = self.make_path('alpha')
        self.os.rename(dir_upper, dir_lower)
        self.assertEqual(['alpha', 'link'],
                         sorted(self.os.listdir(self.base_path)))

    def test_rename_case_only_with_symlink_parent_windows(self):
        self.check_windows_only()
        self.skip_if_symlink_not_supported()
        self.check_rename_case_only_with_symlink_parent()

    def test_rename_case_only_with_symlink_parent_macos(self):
        self.check_macos_only()
        self.check_rename_case_only_with_symlink_parent()

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
        self.assert_raises_os_error(errno.EBADF, self.os.fsync, test_fd + 10)
        test_file.close()

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
    def test_chmod_st_ctime(self):
        with self.mock_time(start=200):
            file_path = 'some_file'
            self.filesystem.create_file(file_path)
            self.assertTrue(self.os.path.exists(file_path))

            st = self.os.stat(file_path)
            self.assertEqual(200, st.st_ctime)
            # tests
            self.os.chmod(file_path, 0o765)
            st = self.os.stat(file_path)
            self.assertEqual(220, st.st_ctime)

    def test_utime_sets_current_time_if_args_is_none(self):
        path = self.make_path('some_file')
        self.createTestFile(path)

        with self.mock_time(start=200):
            self.os.utime(path, times=None)
            st = self.os.stat(path)
            self.assertEqual(200, st.st_atime)
            self.assertEqual(200, st.st_mtime)

    def test_utime_sets_specified_time(self):
        # set up
        path = self.make_path('some_file')
        self.createTestFile(path)
        self.os.stat(path)
        # actual tests
        self.os.utime(path, times=(1, 2))
        st = self.os.stat(path)
        self.assertEqual(1, st.st_atime)
        self.assertEqual(2, st.st_mtime)

    def test_utime_dir(self):
        # set up
        path = '/some_dir'
        self.createTestDirectory(path)
        # actual tests
        self.os.utime(path, times=(1.0, 2.0))
        st = self.os.stat(path)
        self.assertEqual(1.0, st.st_atime)
        self.assertEqual(2.0, st.st_mtime)

    def test_utime_follow_symlinks(self):
        path = self.make_path('some_file')
        self.createTestFile(path)
        link_path = '/link_to_some_file'
        self.filesystem.create_symlink(link_path, path)

        self.os.utime(link_path, times=(1, 2))
        st = self.os.stat(link_path)
        self.assertEqual(1, st.st_atime)
        self.assertEqual(2, st.st_mtime)

    def test_utime_no_follow_symlinks(self):
        path = self.make_path('some_file')
        self.createTestFile(path)
        link_path = '/link_to_some_file'
        self.filesystem.create_symlink(link_path, path)

        self.os.utime(link_path, times=(1, 2), follow_symlinks=False)
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

    def test_utime_sets_specified_time_in_ns(self):
        # set up
        path = self.make_path('some_file')
        self.createTestFile(path)

        self.os.stat(path)
        # actual tests
        self.os.utime(path, ns=(200000000, 400000000))
        st = self.os.stat(path)
        self.assertEqual(0.2, st.st_atime)
        self.assertEqual(0.4, st.st_mtime)

    def test_utime_incorrect_ns_argument_raises(self):
        file_path = 'some_file'
        self.filesystem.create_file(file_path)

        self.assertRaises(TypeError, self.os.utime, file_path, ns=200000000)
        self.assertRaises(TypeError, self.os.utime, file_path, ns=('a', 'b'))
        self.assertRaises(ValueError, self.os.utime, file_path, times=(1, 2),
                          ns=(100, 200))

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

    def setUp(self):
        os.umask(0o022)
        super(FakeOsModuleLowLevelFileOpTest, self).setUp()

    def test_open_read_only(self):
        file_path = self.make_path('file1')
        self.create_file(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_RDONLY)
        self.assertEqual(b'contents', self.os.read(file_des, 8))
        self.assert_raises_os_error(errno.EBADF,
                                    self.os.write, file_des, b'test')
        self.os.close(file_des)

    def test_open_read_only_write_zero_bytes_posix(self):
        self.check_posix_only()
        file_path = self.make_path('file1')
        self.create_file(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_RDONLY)
        self.assert_raises_os_error(errno.EBADF,
                                    self.os.write, file_des, b'test')
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
        self.create_file(file_path, contents=b'contents')

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
        self.assert_raises_os_error(errno.EBADF,
                                    self.os.write, file_des, b'foo')
        self.os.close(file_des)

    def test_open_create_truncate_is_read_only(self):
        file_path = self.make_path('file1')
        file_des = self.os.open(file_path, os.O_CREAT | os.O_TRUNC)
        self.assertEqual(b'', self.os.read(file_des, 1))
        self.assert_raises_os_error(errno.EBADF,
                                    self.os.write, file_des, b'foo')
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
        self.os.chmod(file_path, 0o666)

    def testOpenCreateMode666Windows(self):
        self.check_windows_only()
        file_path = self.make_path('file1')
        file_des = self.os.open(file_path, os.O_WRONLY | os.O_CREAT, 0o224)
        self.assert_mode_equal(0o666, self.os.stat(file_path).st_mode)
        self.os.close(file_des)

    def test_open_exclusive(self):
        file_path = self.make_path('file1')
        file_des = self.os.open(file_path, os.O_RDWR | os.O_EXCL | os.O_CREAT)
        self.assertTrue(self.os.path.exists(file_path))
        self.os.close(file_des)

    def test_open_exclusive_raises_if_file_exists(self):
        file_path = self.make_path('file1')
        self.create_file(file_path, contents=b'contents')
        self.assert_raises_os_error(errno.EEXIST, self.os.open, file_path,
                                    os.O_RDWR | os.O_EXCL | os.O_CREAT)
        self.assert_raises_os_error(errno.EEXIST, self.os.open, file_path,
                                    os.O_RDWR | os.O_EXCL | os.O_CREAT)

    def test_open_exclusive_raises_if_symlink_exists_in_posix(self):
        self.check_posix_only()
        link_path = self.make_path('link')
        link_target = self.make_path('link_target')
        self.os.symlink(link_target, link_path)
        self.assert_raises_os_error(
            errno.EEXIST, self.os.open, link_path,
            os.O_CREAT | os.O_WRONLY | os.O_TRUNC | os.O_EXCL)

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
        self.os.close(file_des)

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
        file_des = self.os.open(file_path,
                                os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
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

    def test_write_from_different_fds_with_append(self):
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

    def test_devnull_posix(self):
        self.check_posix_only()
        self.assertTrue(self.os.path.exists(self.os.devnull))

    def test_devnull_windows(self):
        self.check_windows_only()
        if sys.version_info < (3, 8):
            self.assertFalse(self.os.path.exists(self.os.devnull))
        else:
            self.assertTrue(self.os.path.exists(self.os.devnull))

    def test_write_devnull(self):
        fd = self.os.open(self.os.devnull, os.O_RDWR)
        self.assertEqual(4, self.os.write(fd, b'test'))
        self.assertEqual(b'', self.os.read(fd, 4))
        self.os.close(fd)
        fd = self.os.open(self.os.devnull, os.O_RDONLY)
        self.assertEqual(b'', self.os.read(fd, 4))
        self.os.close(fd)

    def test_sendfile_with_invalid_fd(self):
        self.check_linux_only()
        self.assert_raises_os_error(errno.EBADF, self.os.sendfile,
                                    100, 101, 0, 100)
        src_file_path = self.make_path('foo')
        dst_file_path = self.make_path('bar')
        self.create_file(src_file_path, 'testcontent')
        self.create_file(dst_file_path)
        fd1 = self.os.open(src_file_path, os.O_RDONLY)
        fd2 = self.os.open(dst_file_path, os.O_RDONLY)
        self.assert_raises_os_error(errno.EBADF, self.os.sendfile,
                                    fd2, fd1, 0, 4)

    def test_sendfile_no_offset(self):
        self.check_linux_only()
        src_file_path = self.make_path('foo')
        dst_file_path = self.make_path('bar')
        self.create_file(src_file_path, 'testcontent')
        self.create_file(dst_file_path)
        fd1 = self.os.open(src_file_path, os.O_RDONLY)
        fd2 = self.os.open(dst_file_path, os.O_RDWR)
        self.os.sendfile(fd2, fd1, 0, 3)
        self.os.close(fd2)
        self.os.close(fd1)
        with self.open(dst_file_path) as f:
            self.assertEqual('tes', f.read())

    def test_sendfile_with_offset(self):
        self.check_linux_only()
        src_file_path = self.make_path('foo')
        dst_file_path = self.make_path('bar')
        self.create_file(src_file_path, 'testcontent')
        self.create_file(dst_file_path)
        fd1 = self.os.open(src_file_path, os.O_RDONLY)
        fd2 = self.os.open(dst_file_path, os.O_RDWR)
        self.os.sendfile(fd2, fd1, 4, 4)
        self.os.close(fd2)
        self.os.close(fd1)
        with self.open(dst_file_path) as f:
            self.assertEqual('cont', f.read())

    def test_sendfile_twice(self):
        self.check_linux_only()
        src_file_path = self.make_path('foo')
        dst_file_path = self.make_path('bar')
        self.create_file(src_file_path, 'testcontent')
        self.create_file(dst_file_path)
        fd1 = self.os.open(src_file_path, os.O_RDONLY)
        fd2 = self.os.open(dst_file_path, os.O_RDWR)
        self.os.sendfile(fd2, fd1, 4, 4)
        self.os.sendfile(fd2, fd1, 4, 4)
        self.os.close(fd2)
        self.os.close(fd1)
        with self.open(dst_file_path) as f:
            self.assertEqual('contcont', f.read())

    def test_sendfile_offset_none(self):
        self.check_linux_only()
        src_file_path = self.make_path('foo')
        dst_file_path = self.make_path('bar')
        self.create_file(src_file_path, 'testcontent')
        self.create_file(dst_file_path)
        fd1 = self.os.open(src_file_path, os.O_RDONLY)
        fd2 = self.os.open(dst_file_path, os.O_RDWR)
        self.os.sendfile(fd2, fd1, None, 4)
        self.os.sendfile(fd2, fd1, None, 3)
        self.os.close(fd2)
        self.os.close(fd1)
        with self.open(dst_file_path) as f:
            self.assertEqual('testcon', f.read())

    @unittest.skipIf(not TestCase.is_macos, 'Testing MacOs only behavior')
    def test_no_sendfile_to_regular_file_under_macos(self):
        src_file_path = self.make_path('foo')
        dst_file_path = self.make_path('bar')
        self.create_file(src_file_path, 'testcontent')
        self.create_file(dst_file_path)
        fd1 = self.os.open(src_file_path, os.O_RDONLY)
        fd2 = self.os.open(dst_file_path, os.O_RDWR)
        # raises socket operation on non-socket
        self.assertRaises(OSError, self.os.sendfile, fd2, fd1, 0, 3)
        self.os.close(fd2)
        self.os.close(fd1)


class RealOsModuleLowLevelFileOpTest(FakeOsModuleLowLevelFileOpTest):
    def use_real_fs(self):
        return True


class FakeOsModuleWalkTest(FakeOsModuleTestBase):
    def assertWalkResults(self, expected, top, topdown=True,
                          followlinks=False):
        # as the result of walk is unsorted, we have to check against
        # sorted results
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
        for _ in self.os.walk(directory, onerror=self.StoreErrno):
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
        for _ in self.os.walk(filename, onerror=self.StoreErrno):
            pass
        self.assertTrue(self.GetErrno() in (errno.ENOTDIR, errno.EACCES))

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
        self.create_symlink(
            self.os.path.join(base_dir, 'created_link'), link_dir)

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

    def test_walk_linked_file_in_subdir(self):
        # regression test for #559 (tested for link on incomplete path)
        self.check_posix_only()
        # need to have a top-level link to reproduce the bug - skip real fs
        self.skip_real_fs()
        file_path = '/foo/bar/baz'
        self.create_file(file_path)
        self.create_symlink('bar', file_path)
        expected = [
            ('/foo', ['bar'], []),
            ('/foo/bar', [], ['baz'])
        ]
        self.assertWalkResults(expected, '/foo')

    def test_base_dirpath(self):
        # regression test for #512
        file_path = self.make_path('foo', 'bar', 'baz')
        self.create_file(file_path)
        variants = [
            self.make_path('foo', 'bar'),
            self.make_path('foo', '..', 'foo', 'bar'),
            self.make_path('foo', '..', 'foo', 'bar') +
            self.os.path.sep * 3,
            self.make_path('foo') + self.os.path.sep * 3 + 'bar'
        ]
        for base_dir in variants:
            for dirpath, dirnames, filenames in self.os.walk(base_dir):
                self.assertEqual(dirpath, base_dir)

        file_path = self.make_path('foo', 'bar', 'dir', 'baz')
        self.create_file(file_path)
        for base_dir in variants:
            for dirpath, dirnames, filenames in self.os.walk(base_dir):
                self.assertTrue(dirpath.startswith(base_dir))


class RealOsModuleWalkTest(FakeOsModuleWalkTest):
    def use_real_fs(self):
        return True


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

    def test_link_src_fd(self):
        self.assertRaises(
            NotImplementedError, self.os.link, 'baz', '/bat',
            src_dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.link)
        self.os.link('baz', '/bat', src_dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/bat'))

    def test_link_dst_fd(self):
        self.assertRaises(
            NotImplementedError, self.os.link, 'baz', '/bat',
            dst_dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.link)
        self.os.link('/foo/baz', 'bat', dst_dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/foo/bat'))

    def test_symlink(self):
        self.assertRaises(
            NotImplementedError, self.os.symlink, 'baz', '/bat',
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.symlink)
        self.os.symlink('baz', '/bat', dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/bat'))

    def test_readlink(self):
        self.skip_if_symlink_not_supported()
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

    def test_rename_src_fd(self):
        self.assertRaises(
            NotImplementedError, self.os.rename, 'baz', '/foo/batz',
            src_dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.rename)
        self.os.rename('bar', '/foo/batz', src_dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/foo/batz'))

    def test_rename_dst_fd(self):
        self.assertRaises(
            NotImplementedError, self.os.rename, 'baz', '/foo/batz',
            dst_dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.rename)
        self.os.rename('/foo/bar', 'batz', dst_dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/foo/batz'))

    def test_replace_src_fd(self):
        self.assertRaises(
            NotImplementedError, self.os.rename, 'baz', '/foo/batz',
            src_dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.rename)
        self.os.replace('bar', '/foo/batz', src_dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/foo/batz'))

    def test_replace_dst_fd(self):
        self.assertRaises(
            NotImplementedError, self.os.rename, 'baz', '/foo/batz',
            dst_dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.rename)
        self.os.replace('/foo/bar', 'batz', dst_dir_fd=self.dir_fd)
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
        self.os.utime('baz', times=(1, 2), dir_fd=self.dir_fd)
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
        # The file has size, but no content. When the file is opened for
        # reading, its size should be preserved.
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


@unittest.skipIf(not use_scandir, 'only run if scandir is available')
class FakeScandirTest(FakeOsModuleTestBase):
    FILE_SIZE = 50
    LINKED_FILE_SIZE = 10

    def setUp(self):
        super(FakeScandirTest, self).setUp()
        self.supports_symlinks = (not self.is_windows or
                                  not self.use_real_fs())

        if use_scandir_package:
            if self.use_real_fs():
                from scandir import scandir
            else:
                import pyfakefs.fake_scandir

                def fake_scan_dir(p):
                    return pyfakefs.fake_scandir.scandir(self.filesystem, p)

                scandir = fake_scan_dir
        else:
            scandir = self.os.scandir
        self.scandir = scandir

        self.directory = self.make_path('xyzzy', 'plugh')
        link_dir = self.make_path('linked', 'plugh')
        self.linked_file_path = self.os.path.join(link_dir, 'file')
        self.linked_dir_path = self.os.path.join(link_dir, 'dir')
        self.rel_linked_dir_path = (
            self.os.path.join('..', '..', 'linked', 'plugh', 'dir'))
        self.rel_linked_file_path = (
            self.os.path.join('..', '..', 'linked', 'plugh', 'file'))
        self.dir_path = self.os.path.join(self.directory, 'dir')
        self.file_path = self.os.path.join(self.directory, 'file')
        self.file_link_path = self.os.path.join(self.directory, 'link_file')
        self.dir_link_path = self.os.path.join(self.directory, 'link_dir')
        self.file_rel_link_path = self.os.path.join(self.directory,
                                                    'rel_link_file')
        self.dir_rel_link_path = self.os.path.join(self.directory,
                                                   'rel_link_dir')

        self.create_dir(self.dir_path)
        self.create_file(self.file_path, contents=b'b' * self.FILE_SIZE)
        if self.supports_symlinks:
            self.create_dir(self.linked_dir_path)
            self.create_file(self.linked_file_path,
                             contents=b'a' * self.LINKED_FILE_SIZE),
            self.create_symlink(self.dir_link_path, self.linked_dir_path)
            self.create_symlink(self.file_link_path, self.linked_file_path)
            self.create_symlink(self.dir_rel_link_path,
                                self.rel_linked_dir_path)
            self.create_symlink(self.file_rel_link_path,
                                self.rel_linked_file_path)

        # Changing the working directory below is to make sure relative paths
        # to the files and directories created above are reasonable.
        # Corner-cases about relative paths are better checked in tests created
        # for that purpose.
        #
        # WARNING: This is self.pretest_cwd and not self.cwd as the latter is
        # used by superclass RealFsTestCase.
        self.pretest_cwd = self.os.getcwd()
        self.os.chdir(self.base_path)

        self.dir_entries = list(self.do_scandir())
        self.dir_entries.sort(key=lambda entry: entry.name)

    def tearDown(self):
        self.os.chdir(self.pretest_cwd)
        super().tearDown()

    def do_scandir(self):
        """Hook to override how scandir is called."""
        return self.scandir(self.directory)

    def scandir_path(self):
        """Hook to override the expected scandir() path in DirEntry.path."""
        return self.directory

    def test_paths(self):
        sorted_names = ['dir', 'file']
        if self.supports_symlinks:
            sorted_names.extend(['link_dir', 'link_file', 'rel_link_dir',
                                 'rel_link_file'])

        self.assertEqual(len(sorted_names), len(self.dir_entries))
        self.assertEqual(sorted_names,
                         [entry.name for entry in self.dir_entries])
        sorted_paths = [self.os.path.join(self.scandir_path(), name)
                        for name in sorted_names]
        self.assertEqual(sorted_paths,
                         [entry.path for entry in self.dir_entries])

    def test_isfile(self):
        self.assertFalse(self.dir_entries[0].is_file())
        self.assertTrue(self.dir_entries[1].is_file())
        if self.supports_symlinks:
            self.assertFalse(self.dir_entries[2].is_file())
            self.assertFalse(
                self.dir_entries[2].is_file(follow_symlinks=False))
            self.assertTrue(self.dir_entries[3].is_file())
            self.assertFalse(
                self.dir_entries[3].is_file(follow_symlinks=False))
            self.assertFalse(self.dir_entries[4].is_file())
            self.assertFalse(
                self.dir_entries[4].is_file(follow_symlinks=False))
            self.assertTrue(self.dir_entries[5].is_file())
            self.assertFalse(
                self.dir_entries[5].is_file(follow_symlinks=False))

    def test_isdir(self):
        self.assertTrue(self.dir_entries[0].is_dir())
        self.assertFalse(self.dir_entries[1].is_dir())
        if self.supports_symlinks:
            self.assertTrue(self.dir_entries[2].is_dir())
            self.assertFalse(self.dir_entries[2].is_dir(follow_symlinks=False))
            self.assertFalse(self.dir_entries[3].is_dir())
            self.assertFalse(self.dir_entries[3].is_dir(follow_symlinks=False))
            self.assertTrue(self.dir_entries[4].is_dir())
            self.assertFalse(self.dir_entries[4].is_dir(follow_symlinks=False))
            self.assertFalse(self.dir_entries[5].is_dir())
            self.assertFalse(self.dir_entries[5].is_dir(follow_symlinks=False))

    def test_is_link(self):
        if self.supports_symlinks:
            self.assertFalse(self.dir_entries[0].is_symlink())
            self.assertFalse(self.dir_entries[1].is_symlink())
            self.assertTrue(self.dir_entries[2].is_symlink())
            self.assertTrue(self.dir_entries[3].is_symlink())
            self.assertTrue(self.dir_entries[4].is_symlink())
            self.assertTrue(self.dir_entries[5].is_symlink())

    def test_path_links_not_resolved(self):
        # regression test for #350
        self.skip_if_symlink_not_supported()
        dir_path = self.make_path('A', 'B', 'C')
        self.os.makedirs(self.os.path.join(dir_path, 'D'))
        link_path = self.make_path('A', 'C')
        self.os.symlink(dir_path, link_path)
        self.assertEqual([self.os.path.join(link_path, 'D')],
                         [f.path for f in self.scandir(link_path)])

    def test_inode(self):
        if use_scandir and self.use_real_fs():
            if self.is_windows:
                self.skipTest(
                    'inode seems not to work in scandir module under Windows')
            if IN_DOCKER:
                self.skipTest(
                    'inode seems not to work in a Docker container')
        self.assertEqual(self.os.stat(self.dir_path).st_ino,
                         self.dir_entries[0].inode())
        self.assertEqual(self.os.stat(self.file_path).st_ino,
                         self.dir_entries[1].inode())
        if self.supports_symlinks:
            self.assertEqual(self.os.lstat(self.dir_link_path).st_ino,
                             self.dir_entries[2].inode())
            self.assertEqual(self.os.lstat(self.file_link_path).st_ino,
                             self.dir_entries[3].inode())
            self.assertEqual(self.os.lstat(self.dir_rel_link_path).st_ino,
                             self.dir_entries[4].inode())
            self.assertEqual(self.os.lstat(self.file_rel_link_path).st_ino,
                             self.dir_entries[5].inode())

    def test_scandir_stat_nlink(self):
        # regression test for #350
        stat_nlink = self.os.stat(self.file_path).st_nlink
        self.assertEqual(1, stat_nlink)
        dir_iter = self.scandir(self.directory)
        for item in dir_iter:
            if item.path == self.file_path:
                scandir_stat_nlink = item.stat().st_nlink
                if self.is_windows_fs:
                    self.assertEqual(0, scandir_stat_nlink)
                else:
                    self.assertEqual(1, scandir_stat_nlink)
                self.assertEqual(1, self.os.stat(self.file_path).st_nlink)

    @unittest.skipIf(not hasattr(os, 'O_DIRECTORY'),
                     "opening directory not supported")
    @unittest.skipIf(sys.version_info < (3, 7),
                     "fd not supported for scandir")
    def test_scandir_with_fd(self):
        # regression test for #723
        temp_dir = self.make_path('tmp', 'dir')
        self.create_dir(temp_dir)
        self.create_file(self.os.path.join(temp_dir, 'file1'))
        self.create_file(self.os.path.join(temp_dir, 'file2'))
        self.create_dir(self.os.path.join(temp_dir, 'subdir'))
        self.os.chdir(temp_dir)
        fd = self.os.open(temp_dir, flags=os.O_RDONLY | os.O_DIRECTORY)
        children = [dir_entry.name for dir_entry in self.os.scandir(fd)]
        assert sorted(children) == ['file1', 'file2', 'subdir']

    def check_stat(self, absolute_symlink_expected_size,
                   relative_symlink_expected_size):
        self.assertEqual(self.FILE_SIZE, self.dir_entries[1].stat().st_size)
        self.assertEqual(
            int(self.os.stat(self.dir_path).st_ctime),
            int(self.dir_entries[0].stat().st_ctime))

        if self.supports_symlinks:
            self.assertEqual(self.LINKED_FILE_SIZE,
                             self.dir_entries[3].stat().st_size)
            self.assertEqual(absolute_symlink_expected_size,
                             self.dir_entries[3].stat(
                                 follow_symlinks=False).st_size)
            self.assertEqual(
                int(self.os.stat(self.linked_dir_path).st_mtime),
                int(self.dir_entries[2].stat().st_mtime))
            self.assertEqual(self.LINKED_FILE_SIZE,
                             self.dir_entries[5].stat().st_size)
            self.assertEqual(relative_symlink_expected_size,
                             self.dir_entries[5].stat(
                                 follow_symlinks=False).st_size)
            self.assertEqual(
                int(self.os.stat(self.linked_dir_path).st_mtime),
                int(self.dir_entries[4].stat().st_mtime))

    @unittest.skipIf(TestCase.is_windows, 'POSIX specific behavior')
    def test_stat_posix(self):
        self.check_stat(len(self.linked_file_path),
                        len(self.rel_linked_file_path))

    @unittest.skipIf(not TestCase.is_windows, 'Windows specific behavior')
    def test_stat_windows(self):
        self.check_stat(0, 0)

    def test_index_access_to_stat_times_returns_int(self):
        self.assertEqual(self.os.stat(self.dir_path)[stat.ST_CTIME],
                         int(self.dir_entries[0].stat().st_ctime))
        if self.supports_symlinks:
            self.assertEqual(self.os.stat(self.linked_dir_path)[stat.ST_MTIME],
                             int(self.dir_entries[2].stat().st_mtime))
            self.assertEqual(self.os.stat(self.linked_dir_path)[stat.ST_MTIME],
                             int(self.dir_entries[4].stat().st_mtime))

    def test_stat_ino_dev(self):
        if self.supports_symlinks:
            file_stat = self.os.stat(self.linked_file_path)
            self.assertEqual(file_stat.st_ino,
                             self.dir_entries[3].stat().st_ino)
            self.assertEqual(file_stat.st_dev,
                             self.dir_entries[3].stat().st_dev)
            self.assertEqual(file_stat.st_ino,
                             self.dir_entries[5].stat().st_ino)
            self.assertEqual(file_stat.st_dev,
                             self.dir_entries[5].stat().st_dev)

    @unittest.skipIf(sys.version_info < (3, 6) or not use_builtin_scandir,
                     'Path-like objects have been introduced in Python 3.6')
    def test_path_like(self):
        self.assertTrue(isinstance(self.dir_entries[0], os.PathLike))
        self.assertEqual(self.os.path.join(self.scandir_path(), 'dir'),
                         os.fspath(self.dir_entries[0]))
        self.assertEqual(self.os.path.join(self.scandir_path(), 'file'),
                         os.fspath(self.dir_entries[1]))

    def test_non_existing_dir(self):
        # behaves differently in different systems, so we skip the real fs test
        self.skip_real_fs()
        self.assert_raises_os_error(
            errno.ENOENT, self.scandir, 'non_existing/fake_dir')


class RealScandirTest(FakeScandirTest):
    def use_real_fs(self):
        return True


class FakeScandirRelTest(FakeScandirTest):
    def scandir_path(self):
        # When scandir is called with a relative path, that relative path is
        # used in the path attribute of the DirEntry objects.
        return self.os.path.relpath(self.directory)

    def do_scandir(self):
        return self.scandir(self.os.path.relpath(self.directory))


class RealScandirRelTest(FakeScandirRelTest):
    def use_real_fs(self):
        return True


@unittest.skipIf(TestCase.is_windows,
                 'dir_fd not supported for os.scandir in Windows')
@unittest.skipIf(use_scandir_package,
                 'no dir_fd support for scandir package')
class FakeScandirFdTest(FakeScandirTest):
    def tearDown(self):
        self.os.close(self.dir_fd)
        super(FakeScandirFdTest, self).tearDown()

    def scandir_path(self):
        # When scandir is called with a filedescriptor, only the name of the
        # entry is returned in the path attribute of the DirEntry objects.
        return ''

    def do_scandir(self):
        self.dir_fd = self.os.open(self.directory, os.O_RDONLY)
        return self.scandir(self.dir_fd)


class RealScandirFdTest(FakeScandirFdTest):
    def use_real_fs(self):
        return True


class FakeScandirFdRelTest(FakeScandirFdTest):
    def do_scandir(self):
        self.dir_fd = self.os.open(self.os.path.relpath(self.directory),
                                   os.O_RDONLY)
        return self.scandir(self.dir_fd)


class RealScandirFdRelTest(FakeScandirFdRelTest):
    def use_real_fs(self):
        return True


class FakeExtendedAttributeTest(FakeOsModuleTestBase):
    def setUp(self):
        super(FakeExtendedAttributeTest, self).setUp()
        self.check_linux_only()
        self.dir_path = self.make_path('foo')
        self.file_path = self.os.path.join(self.dir_path, 'bar')
        self.create_file(self.file_path)

    def test_empty_xattr(self):
        self.assertEqual([], self.os.listxattr(self.dir_path))
        self.assertEqual([], self.os.listxattr(self.file_path))

    def test_setxattr(self):
        self.assertRaises(TypeError, self.os.setxattr,
                          self.file_path, 'test', 'value')
        self.assert_raises_os_error(errno.EEXIST, self.os.setxattr,
                                    self.file_path, 'test', b'value',
                                    self.os.XATTR_REPLACE)
        self.os.setxattr(self.file_path, 'test', b'value')
        self.assertEqual(b'value', self.os.getxattr(self.file_path, 'test'))
        self.assert_raises_os_error(errno.ENODATA, self.os.setxattr,
                                    self.file_path, 'test', b'value',
                                    self.os.XATTR_CREATE)

    def test_removeattr(self):
        self.os.removexattr(self.file_path, 'test')
        self.assertEqual([], self.os.listxattr(self.file_path))
        self.os.setxattr(self.file_path, b'test', b'value')
        self.assertEqual(['test'], self.os.listxattr(self.file_path))
        self.assertEqual(b'value', self.os.getxattr(self.file_path, 'test'))
        self.os.removexattr(self.file_path, 'test')
        self.assertEqual([], self.os.listxattr(self.file_path))
        self.assertIsNone(self.os.getxattr(self.file_path, 'test'))

    def test_default_path(self):
        self.os.chdir(self.dir_path)
        self.os.setxattr(self.dir_path, b'test', b'value')
        self.assertEqual(['test'], self.os.listxattr())
        self.assertEqual(b'value', self.os.getxattr(self.dir_path, 'test'))


class FakeOsUnreadableDirTest(FakeOsModuleTestBase):
    def setUp(self):
        if self.use_real_fs():
            # make sure no dir is created if skipped
            self.check_posix_only()
        super(FakeOsUnreadableDirTest, self).setUp()
        self.check_posix_only()
        self.dir_path = self.make_path('some_dir')
        self.file_path = self.os.path.join(self.dir_path, 'some_file')
        self.create_file(self.file_path)
        self.os.chmod(self.dir_path, 0o000)

    def test_listdir_unreadable_dir(self):
        if not is_root():
            self.assert_raises_os_error(
                errno.EACCES, self.os.listdir, self.dir_path)
        else:
            self.assertEqual(['some_file'], self.os.listdir(self.dir_path))

    def test_listdir_user_readable_dir(self):
        self.os.chmod(self.dir_path, 0o600)
        self.assertEqual(['some_file'], self.os.listdir(self.dir_path))
        self.os.chmod(self.dir_path, 0o000)

    def test_listdir_user_readable_dir_from_other_user(self):
        self.skip_real_fs()  # won't change user in real fs
        user_id = USER_ID
        set_uid(user_id + 1)
        dir_path = self.make_path('dir1')
        self.create_dir(dir_path, perm=0o600)
        self.assertTrue(self.os.path.exists(dir_path))
        set_uid(user_id)
        if not is_root():
            with self.assertRaises(PermissionError):
                self.os.listdir(dir_path)
        else:
            self.assertEqual(['some_file'], self.os.listdir(self.dir_path))

    def test_listdir_group_readable_dir_from_other_user(self):
        self.skip_real_fs()  # won't change user in real fs
        user_id = USER_ID
        set_uid(user_id + 1)
        dir_path = self.make_path('dir1')
        self.create_dir(dir_path, perm=0o660)
        self.assertTrue(self.os.path.exists(dir_path))
        set_uid(user_id)
        self.assertEqual([], self.os.listdir(dir_path))

    def test_listdir_group_readable_dir_from_other_group(self):
        self.skip_real_fs()  # won't change user in real fs
        group_id = GROUP_ID
        set_gid(group_id + 1)
        dir_path = self.make_path('dir1')
        self.create_dir(dir_path, perm=0o060)
        self.assertTrue(self.os.path.exists(dir_path))
        set_gid(group_id)
        if not is_root():
            with self.assertRaises(PermissionError):
                self.os.listdir(dir_path)
        else:
            self.assertEqual([], self.os.listdir(dir_path))

    def test_listdir_other_readable_dir_from_other_group(self):
        self.skip_real_fs()  # won't change user in real fs
        group_id = GROUP_ID
        set_gid(group_id + 1)
        dir_path = self.make_path('dir1')
        self.create_dir(dir_path, perm=0o004)
        self.assertTrue(self.os.path.exists(dir_path))
        set_gid(group_id)
        self.assertEqual([], self.os.listdir(dir_path))

    def test_stat_unreadable_dir(self):
        self.assertEqual(0, self.os.stat(self.dir_path).st_mode & 0o666)

    def test_chmod_unreadable_dir(self):
        self.os.chmod(self.dir_path, 0o666)
        self.assertEqual(0o666, self.os.stat(self.dir_path).st_mode & 0o666)
        self.os.chmod(self.dir_path, 0o000)
        self.assertEqual(0, self.os.stat(self.dir_path).st_mode & 0o666)

    def test_stat_file_in_unreadable_dir(self):
        if not is_root():
            self.assert_raises_os_error(
                errno.EACCES, self.os.stat, self.file_path)
        else:
            self.assertEqual(0, self.os.stat(self.file_path).st_size)

    def test_remove_unreadable_dir(self):
        dir_path = self.make_path('dir1')
        self.create_dir(dir_path, perm=0o000)
        self.assertTrue(self.os.path.exists(dir_path))
        self.os.rmdir(dir_path)
        self.assertFalse(self.os.path.exists(dir_path))

    def test_remove_unreadable_dir_from_other_user(self):
        self.skip_real_fs()  # won't change user in real fs
        user_id = USER_ID
        set_uid(user_id + 1)
        dir_path = self.make_path('dir1')
        self.create_dir(dir_path, perm=0o000)
        self.assertTrue(self.os.path.exists(dir_path))
        set_uid(user_id)
        if not is_root():
            with self.assertRaises(PermissionError):
                self.os.rmdir(dir_path)
            self.assertTrue(self.os.path.exists(dir_path))
        else:
            self.os.rmdir(dir_path)
            self.assertFalse(self.os.path.exists(dir_path))


class RealOsUnreadableDirTest(FakeOsUnreadableDirTest):
    def use_real_fs(self):
        return True
