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

"""Tests for `fake_filesystem_shutil` if used in
`fake_filesystem_unittest.TestCase`.
Note that almost all of the functionality is delegated to the real `shutil`
and works correctly with the fake filesystem because of the faked `os` module.
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from pyfakefs import fake_filesystem_unittest
from pyfakefs.fake_filesystem import is_root, set_uid, USER_ID
from pyfakefs.tests.test_utils import RealFsTestMixin

is_windows = sys.platform == 'win32'


class RealFsTestCase(fake_filesystem_unittest.TestCase, RealFsTestMixin):
    def __init__(self, methodName='runTest'):
        fake_filesystem_unittest.TestCase.__init__(self, methodName)
        RealFsTestMixin.__init__(self)

    def setUp(self):
        RealFsTestMixin.setUp(self)
        self.cwd = os.getcwd()
        self.uid = USER_ID
        set_uid(1000)
        if not self.use_real_fs():
            self.setUpPyfakefs()
            self.filesystem = self.fs
            self.os = os
            self.open = open
            self.create_basepath()
            self.fs.set_disk_usage(1000, self.base_path)

    def tearDown(self):
        set_uid(self.uid)
        RealFsTestMixin.tearDown(self)

    @property
    def is_windows_fs(self):
        if self.use_real_fs():
            return sys.platform == 'win32'
        return self.filesystem.is_windows_fs


class FakeShutilModuleTest(RealFsTestCase):
    @unittest.skipIf(is_windows, 'Posix specific behavior')
    def test_catch_permission_error(self):
        root_path = self.make_path('rootpath')
        self.create_dir(root_path)
        dir1_path = self.os.path.join(root_path, 'dir1')
        dir2_path = self.os.path.join(root_path, 'dir2')
        self.create_dir(dir1_path)
        self.os.chmod(dir1_path, 0o555)  # remove write permissions
        self.create_dir(dir2_path)
        old_file_path = self.os.path.join(dir2_path, 'f1.txt')
        new_file_path = self.os.path.join(dir1_path, 'f1.txt')
        self.create_file(old_file_path)

        with self.assertRaises(PermissionError):
            shutil.move(old_file_path, new_file_path)

    def test_rmtree(self):
        directory = self.make_path('xyzzy')
        dir_path = os.path.join(directory, 'subdir')
        self.create_dir(dir_path)
        file_path = os.path.join(directory, 'subfile')
        self.create_file(file_path)
        self.assertTrue(os.path.exists(directory))
        shutil.rmtree(directory)
        self.assertFalse(os.path.exists(directory))
        self.assertFalse(os.path.exists(dir_path))
        self.assertFalse(os.path.exists(file_path))

    def test_rmtree_with_trailing_slash(self):
        directory = self.make_path('xyzzy')
        dir_path = os.path.join(directory, 'subdir')
        self.create_dir(dir_path)
        file_path = os.path.join(directory, 'subfile')
        self.create_file(file_path)
        shutil.rmtree(directory + '/')
        self.assertFalse(os.path.exists(directory))
        self.assertFalse(os.path.exists(dir_path))
        self.assertFalse(os.path.exists(file_path))

    @unittest.skipIf(not is_windows, 'Windows specific behavior')
    def test_rmtree_without_permission_for_a_file_in_windows(self):
        self.check_windows_only()
        dir_path = self.make_path('foo')
        self.create_file(os.path.join(dir_path, 'bar'))
        file_path = os.path.join(dir_path, 'baz')
        self.create_file(file_path)
        self.os.chmod(file_path, 0o444)
        with self.assertRaises(OSError):
            shutil.rmtree(dir_path)
        self.assertTrue(os.path.exists(file_path))
        self.os.chmod(file_path, 0o666)

    @unittest.skipIf(is_windows, 'Posix specific behavior')
    def test_rmtree_without_permission_for_a_dir_in_posix(self):
        self.check_posix_only()
        dir_path = self.make_path('foo')
        self.create_file(os.path.join(dir_path, 'bar'))
        file_path = os.path.join(dir_path, 'baz')
        self.create_file(file_path)
        self.os.chmod(dir_path, 0o555)
        if not is_root():
            with self.assertRaises(OSError):
                shutil.rmtree(dir_path)
            self.assertTrue(os.path.exists(file_path))
            self.os.chmod(dir_path, 0o777)
        else:
            shutil.rmtree(dir_path)
            self.assertFalse(os.path.exists(file_path))

    @unittest.skipIf(is_windows, 'Posix specific behavior')
    def test_rmtree_with_open_file_posix(self):
        self.check_posix_only()
        dir_path = self.make_path('foo')
        self.create_file(os.path.join(dir_path, 'bar'))
        file_path = os.path.join(dir_path, 'baz')
        self.create_file(file_path)
        with open(file_path):
            shutil.rmtree(dir_path)
        self.assertFalse(os.path.exists(file_path))

    @unittest.skipIf(not is_windows, 'Windows specific behavior')
    def test_rmtree_with_open_file_fails_under_windows(self):
        self.check_windows_only()
        dir_path = self.make_path('foo')
        self.create_file(os.path.join(dir_path, 'bar'))
        file_path = os.path.join(dir_path, 'baz')
        self.create_file(file_path)
        with open(file_path):
            with self.assertRaises(OSError):
                shutil.rmtree(dir_path)
        self.assertTrue(os.path.exists(dir_path))

    def test_rmtree_non_existing_dir(self):
        directory = 'nonexisting'
        with self.assertRaises(OSError):
            shutil.rmtree(directory)
        try:
            shutil.rmtree(directory, ignore_errors=True)
        except OSError:
            self.fail('rmtree raised despite ignore_errors True')

    def test_rmtree_non_existing_dir_with_handler(self):
        class NonLocal:
            pass

        def error_handler(_, path, _error_info):
            NonLocal.errorHandled = True
            NonLocal.errorPath = path

        directory = self.make_path('nonexisting')
        NonLocal.errorHandled = False
        NonLocal.errorPath = ''
        try:
            shutil.rmtree(directory, onerror=error_handler)
        except OSError:
            self.fail('rmtree raised exception despite onerror defined')
        self.assertTrue(NonLocal.errorHandled)
        self.assertEqual(NonLocal.errorPath, directory)

        NonLocal.errorHandled = False
        NonLocal.errorPath = ''
        try:
            shutil.rmtree(directory, ignore_errors=True, onerror=error_handler)
        except OSError:
            self.fail('rmtree raised exception despite ignore_errors True')
        # ignore_errors is True, so the onerror() error handler was
        # not executed
        self.assertFalse(NonLocal.errorHandled)
        self.assertEqual(NonLocal.errorPath, '')

    def test_copy(self):
        src_file = self.make_path('xyzzy')
        dst_file = self.make_path('xyzzy_copy')
        self.create_file(src_file)
        os.chmod(src_file, 0o750)
        self.assertTrue(os.path.exists(src_file))
        self.assertFalse(os.path.exists(dst_file))
        shutil.copy(src_file, dst_file)
        self.assertTrue(os.path.exists(dst_file))
        self.assertEqual(os.stat(src_file).st_mode, os.stat(dst_file).st_mode)

    def test_copy_directory(self):
        src_file = self.make_path('xyzzy')
        parent_directory = self.make_path('parent')
        dst_file = os.path.join(parent_directory, 'xyzzy')
        self.create_file(src_file)
        self.create_dir(parent_directory)
        os.chmod(src_file, 0o750)
        self.assertTrue(os.path.exists(src_file))
        self.assertTrue(os.path.exists(parent_directory))
        self.assertFalse(os.path.exists(dst_file))
        shutil.copy(src_file, parent_directory)
        self.assertTrue(os.path.exists(dst_file))
        self.assertEqual(os.stat(src_file).st_mode, os.stat(dst_file).st_mode)

    def test_copystat(self):
        src_file = self.make_path('xyzzy')
        self.create_file(src_file)
        os.chmod(src_file, 0o750)
        dst_file = self.make_path('xyzzy_copy')
        self.create_file(dst_file)
        self.assertTrue(os.path.exists(src_file))
        self.assertTrue(os.path.exists(dst_file))
        shutil.copystat(src_file, dst_file)
        src_stat = os.stat(src_file)
        dst_stat = os.stat(dst_file)
        self.assertEqual(src_stat.st_mode, dst_stat.st_mode)
        self.assertAlmostEqual(src_stat.st_atime, dst_stat.st_atime, places=2)
        self.assertAlmostEqual(src_stat.st_mtime, dst_stat.st_mtime, places=2)

    def test_copy2(self):
        src_file = self.make_path('xyzzy')
        self.create_file(src_file)
        os.chmod(src_file, 0o750)
        dst_file = self.make_path('xyzzy_copy')
        self.assertTrue(os.path.exists(src_file))
        self.assertFalse(os.path.exists(dst_file))
        shutil.copy2(src_file, dst_file)
        self.assertTrue(os.path.exists(dst_file))
        src_stat = os.stat(src_file)
        dst_stat = os.stat(dst_file)
        self.assertEqual(src_stat.st_mode, dst_stat.st_mode)
        self.assertAlmostEqual(src_stat.st_atime, dst_stat.st_atime, places=2)
        self.assertAlmostEqual(src_stat.st_mtime, dst_stat.st_mtime, places=2)

    def test_copy2_directory(self):
        src_file = self.make_path('xyzzy')
        parent_directory = self.make_path('parent')
        dst_file = os.path.join(parent_directory, 'xyzzy')
        self.create_file(src_file)
        self.create_dir(parent_directory)
        os.chmod(src_file, 0o750)
        self.assertTrue(os.path.exists(src_file))
        self.assertTrue(os.path.exists(parent_directory))
        self.assertFalse(os.path.exists(dst_file))
        shutil.copy2(src_file, parent_directory)
        self.assertTrue(os.path.exists(dst_file))
        src_stat = os.stat(src_file)
        dst_stat = os.stat(dst_file)
        self.assertEqual(src_stat.st_mode, dst_stat.st_mode)
        self.assertAlmostEqual(src_stat.st_atime, dst_stat.st_atime, places=2)
        self.assertAlmostEqual(src_stat.st_mtime, dst_stat.st_mtime, places=2)

    def test_copytree(self):
        src_directory = self.make_path('xyzzy')
        dst_directory = self.make_path('xyzzy_copy')
        self.create_dir(src_directory)
        self.create_dir('%s/subdir' % src_directory)
        self.create_file(os.path.join(src_directory, 'subfile'))
        self.assertTrue(os.path.exists(src_directory))
        self.assertFalse(os.path.exists(dst_directory))
        shutil.copytree(src_directory, dst_directory)
        self.assertTrue(os.path.exists(dst_directory))
        self.assertTrue(os.path.exists(os.path.join(dst_directory, 'subdir')))
        self.assertTrue(os.path.exists(os.path.join(dst_directory, 'subfile')))

    def test_copytree_src_is_file(self):
        src_file = self.make_path('xyzzy')
        dst_directory = self.make_path('xyzzy_copy')
        self.create_file(src_file)
        self.assertTrue(os.path.exists(src_file))
        self.assertFalse(os.path.exists(dst_directory))
        with self.assertRaises(OSError):
            shutil.copytree(src_file, dst_directory)

    def test_move_file_in_same_filesystem(self):
        self.skip_real_fs()
        src_file = '/original_xyzzy'
        dst_file = '/moved_xyzzy'
        src_object = self.fs.create_file(src_file)
        src_ino = src_object.st_ino
        src_dev = src_object.st_dev

        self.assertTrue(os.path.exists(src_file))
        self.assertFalse(os.path.exists(dst_file))
        shutil.move(src_file, dst_file)
        self.assertTrue(os.path.exists(dst_file))
        self.assertFalse(os.path.exists(src_file))

        dst_object = self.fs.get_object(dst_file)
        self.assertEqual(src_ino, dst_object.st_ino)
        self.assertEqual(src_dev, dst_object.st_dev)

    def test_move_file_into_other_filesystem(self):
        self.skip_real_fs()
        mount_point = self.create_mount_point()

        src_file = self.make_path('original_xyzzy')
        dst_file = self.os.path.join(mount_point, 'moved_xyzzy')
        src_object = self.fs.create_file(src_file)
        src_ino = src_object.st_ino
        src_dev = src_object.st_dev

        shutil.move(src_file, dst_file)
        self.assertTrue(os.path.exists(dst_file))
        self.assertFalse(os.path.exists(src_file))

        dst_object = self.fs.get_object(dst_file)
        self.assertNotEqual(src_ino, dst_object.st_ino)
        self.assertNotEqual(src_dev, dst_object.st_dev)

    def test_move_file_into_directory(self):
        src_file = self.make_path('xyzzy')
        dst_directory = self.make_path('directory')
        dst_file = os.path.join(dst_directory, 'xyzzy')
        self.create_file(src_file)
        self.create_dir(dst_directory)
        self.assertTrue(os.path.exists(src_file))
        self.assertFalse(os.path.exists(dst_file))
        shutil.move(src_file, dst_directory)
        self.assertTrue(os.path.exists(dst_file))
        self.assertFalse(os.path.exists(src_file))

    def test_move_directory(self):
        src_directory = self.make_path('original_xyzzy')
        dst_directory = self.make_path('moved_xyzzy')
        self.create_dir(src_directory)
        self.create_file(os.path.join(src_directory, 'subfile'))
        self.create_dir(os.path.join(src_directory, 'subdir'))
        self.assertTrue(os.path.exists(src_directory))
        self.assertFalse(os.path.exists(dst_directory))
        shutil.move(src_directory, dst_directory)
        self.assertTrue(os.path.exists(dst_directory))
        self.assertTrue(os.path.exists(os.path.join(dst_directory, 'subfile')))
        self.assertTrue(os.path.exists(os.path.join(dst_directory, 'subdir')))
        self.assertFalse(os.path.exists(src_directory))

    def test_disk_usage(self):
        self.skip_real_fs()
        file_path = self.make_path('foo', 'bar')
        self.fs.create_file(file_path, st_size=400)
        disk_usage = shutil.disk_usage(file_path)
        self.assertEqual(1000, disk_usage.total)
        self.assertEqual(400, disk_usage.used)
        self.assertEqual(600, disk_usage.free)
        self.assertEqual((1000, 400, 600), disk_usage)

        mount_point = self.create_mount_point()
        dir_path = self.os.path.join(mount_point, 'foo')
        file_path = self.os.path.join(dir_path, 'bar')
        self.fs.create_file(file_path, st_size=400)
        disk_usage = shutil.disk_usage(dir_path)
        self.assertEqual((500, 400, 100), disk_usage)

    def test_disk_usage_with_path(self):
        self.skip_real_fs()
        file_path = self.make_path('foo', 'bar')
        self.fs.create_file(file_path, st_size=400)
        path = Path(file_path)
        disk_usage = shutil.disk_usage(path)
        self.assertEqual(1000, disk_usage.total)
        self.assertEqual(400, disk_usage.used)
        self.assertEqual(600, disk_usage.free)
        self.assertEqual((1000, 400, 600), disk_usage)

    def create_mount_point(self):
        mount_point = 'M:' if self.is_windows_fs else '/mount'
        self.fs.add_mount_point(mount_point, total_size=500)
        return mount_point


class RealShutilModuleTest(FakeShutilModuleTest):
    def use_real_fs(self):
        return True


class FakeCopyFileTest(RealFsTestCase):
    def tearDown(self):
        super(FakeCopyFileTest, self).tearDown()

    def test_common_case(self):
        src_file = self.make_path('xyzzy')
        dst_file = self.make_path('xyzzy_copy')
        contents = 'contents of file'
        self.create_file(src_file, contents=contents)
        self.assertTrue(os.path.exists(src_file))
        self.assertFalse(os.path.exists(dst_file))
        shutil.copyfile(src_file, dst_file)
        self.assertTrue(os.path.exists(dst_file))
        self.check_contents(dst_file, contents)

    def test_raises_if_source_and_dest_are_the_same_file(self):
        src_file = self.make_path('xyzzy')
        dst_file = src_file
        contents = 'contents of file'
        self.create_file(src_file, contents=contents)
        self.assertTrue(os.path.exists(src_file))
        with self.assertRaises(shutil.Error):
            shutil.copyfile(src_file, dst_file)

    def test_raises_if_dest_is_a_symlink_to_src(self):
        self.skip_if_symlink_not_supported()
        src_file = self.make_path('foo')
        dst_file = self.make_path('bar')
        contents = 'contents of file'
        self.create_file(src_file, contents=contents)
        self.create_symlink(dst_file, src_file)
        self.assertTrue(os.path.exists(src_file))
        with self.assertRaises(shutil.Error):
            shutil.copyfile(src_file, dst_file)

    def test_succeeds_if_dest_exists_and_is_writable(self):
        src_file = self.make_path('xyzzy')
        dst_file = self.make_path('xyzzy_copy')
        src_contents = 'contents of source file'
        dst_contents = 'contents of dest file'
        self.create_file(src_file, contents=src_contents)
        self.create_file(dst_file, contents=dst_contents)
        self.assertTrue(os.path.exists(src_file))
        self.assertTrue(os.path.exists(dst_file))
        shutil.copyfile(src_file, dst_file)
        self.assertTrue(os.path.exists(dst_file))
        self.check_contents(dst_file, src_contents)

    def test_raises_if_dest_exists_and_is_not_writable(self):
        src_file = self.make_path('xyzzy')
        dst_file = self.make_path('xyzzy_copy')
        src_contents = 'contents of source file'
        dst_contents = 'contents of dest file'
        self.create_file(src_file, contents=src_contents)
        self.create_file(dst_file, contents=dst_contents)
        os.chmod(dst_file, 0o400)
        self.assertTrue(os.path.exists(src_file))
        self.assertTrue(os.path.exists(dst_file))

        if is_root():
            shutil.copyfile(src_file, dst_file)
            self.assertTrue(self.os.path.exists(dst_file))
            with self.open(dst_file) as f:
                self.assertEqual('contents of source file', f.read())
        else:
            with self.assertRaises(OSError):
                shutil.copyfile(src_file, dst_file)

        os.chmod(dst_file, 0o666)

    @unittest.skipIf(is_windows, 'Posix specific behavior')
    def test_raises_if_dest_dir_is_not_writable_under_posix(self):
        self.check_posix_only()
        src_file = self.make_path('xyzzy')
        dst_dir = self.make_path('tmp', 'foo')
        dst_file = os.path.join(dst_dir, 'xyzzy')
        src_contents = 'contents of source file'
        self.create_file(src_file, contents=src_contents)
        self.create_dir(dst_dir)
        os.chmod(dst_dir, 0o555)
        self.assertTrue(os.path.exists(src_file))
        self.assertTrue(os.path.exists(dst_dir))
        if not is_root():
            with self.assertRaises(OSError):
                shutil.copyfile(src_file, dst_file)
        else:
            shutil.copyfile(src_file, dst_file)
            self.assertTrue(os.path.exists(dst_file))
            self.check_contents(dst_file, src_contents)

    def test_raises_if_src_doesnt_exist(self):
        src_file = self.make_path('xyzzy')
        dst_file = self.make_path('xyzzy_copy')
        self.assertFalse(os.path.exists(src_file))
        with self.assertRaises(OSError):
            shutil.copyfile(src_file, dst_file)

    @unittest.skipIf(is_windows, 'Posix specific behavior')
    def test_raises_if_src_not_readable(self):
        self.check_posix_only()
        src_file = self.make_path('xyzzy')
        dst_file = self.make_path('xyzzy_copy')
        src_contents = 'contents of source file'
        self.create_file(src_file, contents=src_contents)
        os.chmod(src_file, 0o000)
        self.assertTrue(os.path.exists(src_file))
        if not is_root():
            with self.assertRaises(OSError):
                shutil.copyfile(src_file, dst_file)
        else:
            shutil.copyfile(src_file, dst_file)
            self.assertTrue(os.path.exists(dst_file))
            self.check_contents(dst_file, src_contents)

    def test_raises_if_src_is_a_directory(self):
        src_file = self.make_path('xyzzy')
        dst_file = self.make_path('xyzzy_copy')
        self.create_dir(src_file)
        self.assertTrue(os.path.exists(src_file))
        with self.assertRaises(OSError):
            shutil.copyfile(src_file, dst_file)

    def test_raises_if_dest_is_a_directory(self):
        src_file = self.make_path('xyzzy')
        dst_dir = self.make_path('tmp', 'foo')
        src_contents = 'contents of source file'
        self.create_file(src_file, contents=src_contents)
        self.create_dir(dst_dir)
        self.assertTrue(os.path.exists(src_file))
        self.assertTrue(os.path.exists(dst_dir))
        with self.assertRaises(OSError):
            shutil.copyfile(src_file, dst_dir)

    def test_moving_dir_into_dir(self):
        # regression test for #515
        source_dir = tempfile.mkdtemp()
        target_dir = tempfile.mkdtemp()
        filename = 'foo.pdf'
        with open(os.path.join(source_dir, filename), 'wb') as fp:
            fp.write(b'stub')

        shutil.move(source_dir, target_dir)
        shutil.rmtree(target_dir)


class RealCopyFileTest(FakeCopyFileTest):
    def use_real_fs(self):
        return True


if __name__ == '__main__':
    unittest.main()
