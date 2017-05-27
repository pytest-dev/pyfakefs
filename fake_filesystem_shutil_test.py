#! /usr/bin/env python
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

"""Tests for `fake_filesystem_shutil` if used in
`fake_filesystem_unittest.TestCase`.
Note that almost all of the functionality is delegated to the real `shutil`
and works correctly with the fake filesystem because of the faked `os` module.
"""
import os
import shutil
import sys
import unittest

from fake_filesystem_test import RealFsTestMixin
from pyfakefs import fake_filesystem_unittest


class RealFsTestCase(fake_filesystem_unittest.TestCase, RealFsTestMixin):
    def __init__(self, methodName='runTest'):
        fake_filesystem_unittest.TestCase.__init__(self, methodName)
        RealFsTestMixin.__init__(self)

    def setUp(self):
        if not self.useRealFs():
            self.setUpPyfakefs()
            self.filesystem = self.fs
            self.os = os
            self.open = open
            self.fs.set_disk_usage(1000)
            self.fs.create_dir(self.base_path)

    def tearDown(self):
        if self.useRealFs():
            self.os.chdir(os.path.dirname(self.base_path))
            shutil.rmtree(self.base_path, ignore_errors=True)

    @property
    def is_windows_fs(self):
        if self.useRealFs():
            return sys.platform == 'win32'
        return self.filesystem.is_windows_fs


class FakeShutilModuleTest(RealFsTestCase):
    def testRmtree(self):
        directory = self.makePath('xyzzy')
        dir_path = os.path.join(directory, 'subdir')
        self.createDirectory(dir_path)
        file_path = os.path.join(directory, 'subfile')
        self.createFile(file_path)
        self.assertTrue(os.path.exists(directory))
        shutil.rmtree(directory)
        self.assertFalse(os.path.exists(directory))
        self.assertFalse(os.path.exists(dir_path))
        self.assertFalse(os.path.exists(file_path))

    def testRmtreeWithTrailingSlash(self):
        directory = self.makePath('xyzzy')
        dir_path = os.path.join(directory, 'subdir')
        self.createDirectory(dir_path)
        file_path = os.path.join(directory, 'subfile')
        self.createFile(file_path)
        shutil.rmtree(directory + '/')
        self.assertFalse(os.path.exists(directory))
        self.assertFalse(os.path.exists(dir_path))
        self.assertFalse(os.path.exists(file_path))

    def testRmtreeWithoutPermissionForAFileInWindows(self):
        self.checkWindowsOnly()
        dir_path = self.makePath('foo')
        self.createFile(os.path.join(dir_path, 'bar'))
        file_path = os.path.join(dir_path, 'baz')
        self.createFile(file_path)
        self.os.chmod(file_path, 0o444)
        self.assertRaises(OSError, shutil.rmtree, dir_path)
        self.assertTrue(os.path.exists(file_path))
        self.os.chmod(file_path, 0o666)

    def testRmtreeWithoutPermissionForADirInPosix(self):
        self.checkPosixOnly()
        dir_path = self.makePath('foo')
        self.createFile(os.path.join(dir_path, 'bar'))
        file_path = os.path.join(dir_path, 'baz')
        self.createFile(file_path)
        self.os.chmod(dir_path, 0o555)
        self.assertRaises(OSError, shutil.rmtree, dir_path)
        self.assertTrue(os.path.exists(file_path))
        self.os.chmod(dir_path, 0o777)

    def testRmtreeWithOpenFilePosix(self):
        self.checkPosixOnly()
        dir_path = self.makePath('foo')
        self.createFile(os.path.join(dir_path, 'bar'))
        file_path = os.path.join(dir_path, 'baz')
        self.createFile(file_path)
        with open(file_path):
            shutil.rmtree(dir_path)
        self.assertFalse(os.path.exists(file_path))

    def testRmtreeWithOpenFileFailsUnderWindows(self):
        self.checkWindowsOnly()
        dir_path = self.makePath('foo')
        self.createFile(os.path.join(dir_path, 'bar'))
        file_path = os.path.join(dir_path, 'baz')
        self.createFile(file_path)
        with open(file_path):
            self.assertRaises(OSError, shutil.rmtree, dir_path)
        self.assertTrue(os.path.exists(dir_path))

    def testRmtreeNonExistingDir(self):
        directory = 'nonexisting'
        self.assertRaises(OSError, shutil.rmtree, directory)
        try:
            shutil.rmtree(directory, ignore_errors=True)
        except OSError:
            self.fail('rmtree raised despite ignore_errors True')

    def testRmtreeNonExistingDirWithHandler(self):
        class NonLocal:
            pass

        def error_handler(_, path, error_info):
            NonLocal.errorHandled = True
            NonLocal.errorPath = path

        directory = self.makePath('nonexisting')
        NonLocal.errorHandled = False
        NonLocal.errorPath = ''
        try:
            shutil.rmtree(directory, onerror=error_handler)
        except IOError:
            self.fail('rmtree raised exception despite onerror defined')
        self.assertTrue(NonLocal.errorHandled)
        self.assertEqual(NonLocal.errorPath, directory)

        NonLocal.errorHandled = False
        NonLocal.errorPath = ''
        try:
            shutil.rmtree(directory, ignore_errors=True, onerror=error_handler)
        except IOError:
            self.fail('rmtree raised exception despite ignore_errors True')
        # ignore_errors is True, so the onerror() error handler was not executed
        self.assertFalse(NonLocal.errorHandled)
        self.assertEqual(NonLocal.errorPath, '')

    def testCopy(self):
        src_file = self.makePath('xyzzy')
        dst_file = self.makePath('xyzzy_copy')
        self.createFile(src_file)
        os.chmod(src_file, 0o750)
        self.assertTrue(os.path.exists(src_file))
        self.assertFalse(os.path.exists(dst_file))
        shutil.copy(src_file, dst_file)
        self.assertTrue(os.path.exists(dst_file))
        self.assertEqual(os.stat(src_file).st_mode, os.stat(dst_file).st_mode)

    def testCopyDirectory(self):
        src_file = self.makePath('xyzzy')
        parent_directory = self.makePath('parent')
        dst_file = os.path.join(parent_directory, 'xyzzy')
        self.createFile(src_file)
        self.createDirectory(parent_directory)
        os.chmod(src_file, 0o750)
        self.assertTrue(os.path.exists(src_file))
        self.assertTrue(os.path.exists(parent_directory))
        self.assertFalse(os.path.exists(dst_file))
        shutil.copy(src_file, parent_directory)
        self.assertTrue(os.path.exists(dst_file))
        self.assertEqual(os.stat(src_file).st_mode, os.stat(dst_file).st_mode)

    def testCopystat(self):
        src_file = self.makePath('xyzzy')
        self.createFile(src_file)
        os.chmod(src_file, 0o750)
        dst_file = self.makePath('xyzzy_copy')
        self.createFile(dst_file)
        self.assertTrue(os.path.exists(src_file))
        self.assertTrue(os.path.exists(dst_file))
        shutil.copystat(src_file, dst_file)
        src_stat = os.stat(src_file)
        dst_stat = os.stat(dst_file)
        self.assertEqual(src_stat.st_mode, dst_stat.st_mode)
        self.assertAlmostEqual(src_stat.st_atime, dst_stat.st_atime, places=2)
        self.assertAlmostEqual(src_stat.st_mtime, dst_stat.st_mtime, places=2)

    def testCopy2(self):
        src_file = self.makePath('xyzzy')
        self.createFile(src_file)
        os.chmod(src_file, 0o750)
        dst_file = self.makePath('xyzzy_copy')
        self.assertTrue(os.path.exists(src_file))
        self.assertFalse(os.path.exists(dst_file))
        shutil.copy2(src_file, dst_file)
        self.assertTrue(os.path.exists(dst_file))
        src_stat = os.stat(src_file)
        dst_stat = os.stat(dst_file)
        self.assertEqual(src_stat.st_mode, dst_stat.st_mode)
        self.assertAlmostEqual(src_stat.st_atime, dst_stat.st_atime, places=2)
        self.assertAlmostEqual(src_stat.st_mtime, dst_stat.st_mtime, places=2)

    def testCopy2Directory(self):
        src_file = self.makePath('xyzzy')
        parent_directory = self.makePath('parent')
        dst_file = os.path.join(parent_directory, 'xyzzy')
        self.createFile(src_file)
        self.createDirectory(parent_directory)
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

    def testCopytree(self):
        src_directory = self.makePath('xyzzy')
        dst_directory = self.makePath('xyzzy_copy')
        self.createDirectory(src_directory)
        self.createDirectory('%s/subdir' % src_directory)
        self.createFile(os.path.join(src_directory, 'subfile'))
        self.assertTrue(os.path.exists(src_directory))
        self.assertFalse(os.path.exists(dst_directory))
        shutil.copytree(src_directory, dst_directory)
        self.assertTrue(os.path.exists(dst_directory))
        self.assertTrue(os.path.exists(os.path.join(dst_directory, 'subdir')))
        self.assertTrue(os.path.exists(os.path.join(dst_directory, 'subfile')))

    def testCopytreeSrcIsFile(self):
        src_file = self.makePath('xyzzy')
        dst_directory = self.makePath('xyzzy_copy')
        self.createFile(src_file)
        self.assertTrue(os.path.exists(src_file))
        self.assertFalse(os.path.exists(dst_directory))
        self.assertRaises(OSError,
                          shutil.copytree,
                          src_file,
                          dst_directory)

    def testMoveFileInSameFilesystem(self):
        self.skipRealFs()
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

    def testMoveFileIntoOtherFilesystem(self):
        self.skipRealFs()
        self.fs.add_mount_point('/mount')
        src_file = '/original_xyzzy'
        dst_file = '/mount/moved_xyzzy'
        src_object = self.fs.create_file(src_file)
        src_ino = src_object.st_ino
        src_dev = src_object.st_dev

        shutil.move(src_file, dst_file)
        self.assertTrue(os.path.exists(dst_file))
        self.assertFalse(os.path.exists(src_file))

        dst_object = self.fs.get_object(dst_file)
        self.assertNotEqual(src_ino, dst_object.st_ino)
        self.assertNotEqual(src_dev, dst_object.st_dev)

    def testMoveFileIntoDirectory(self):
        src_file = self.makePath('xyzzy')
        dst_directory = self.makePath('directory')
        dst_file = os.path.join(dst_directory, 'xyzzy')
        self.createFile(src_file)
        self.createDirectory(dst_directory)
        self.assertTrue(os.path.exists(src_file))
        self.assertFalse(os.path.exists(dst_file))
        shutil.move(src_file, dst_directory)
        self.assertTrue(os.path.exists(dst_file))
        self.assertFalse(os.path.exists(src_file))

    def testMoveDirectory(self):
        src_directory = self.makePath('original_xyzzy')
        dst_directory = self.makePath('moved_xyzzy')
        self.createDirectory(src_directory)
        self.createFile(os.path.join(src_directory, 'subfile'))
        self.createDirectory(os.path.join(src_directory, 'subdir'))
        self.assertTrue(os.path.exists(src_directory))
        self.assertFalse(os.path.exists(dst_directory))
        shutil.move(src_directory, dst_directory)
        self.assertTrue(os.path.exists(dst_directory))
        self.assertTrue(os.path.exists(os.path.join(dst_directory, 'subfile')))
        self.assertTrue(os.path.exists(os.path.join(dst_directory, 'subdir')))
        self.assertFalse(os.path.exists(src_directory))

    @unittest.skipIf(sys.version_info < (3, 3), 'New in Python 3.3')
    def testDiskUsage(self):
        self.skipRealFs()
        self.fs.create_file('/foo/bar', st_size=400)
        disk_usage = shutil.disk_usage('/')
        self.assertEqual(1000, disk_usage.total)
        self.assertEqual(400, disk_usage.used)
        self.assertEqual(600, disk_usage.free)
        self.assertEqual((1000, 400, 600), disk_usage)

        self.fs.add_mount_point('/mount', total_size=500)
        self.fs.create_file('/mount/foo/bar', st_size=400)
        disk_usage = shutil.disk_usage('/mount/foo/')
        self.assertEqual((500, 400, 100), disk_usage)


class RealShutilModuleTest(FakeShutilModuleTest):
    def useRealFs(self):
        return True


class FakeCopyFileTest(RealFsTestCase):
    def testCommonCase(self):
        src_file = self.makePath('xyzzy')
        dst_file = self.makePath('xyzzy_copy')
        contents = 'contents of file'
        self.createFile(src_file, contents=contents)
        self.assertTrue(os.path.exists(src_file))
        self.assertFalse(os.path.exists(dst_file))
        shutil.copyfile(src_file, dst_file)
        self.assertTrue(os.path.exists(dst_file))
        self.checkContents(dst_file, contents)

    def testRaisesIfSourceAndDestAreTheSameFile(self):
        src_file = self.makePath('xyzzy')
        dst_file = src_file
        contents = 'contents of file'
        self.createFile(src_file, contents=contents)
        self.assertTrue(os.path.exists(src_file))
        self.assertRaises(shutil.Error,
                          shutil.copyfile, src_file, dst_file)

    def testRaisesIfDestIsASymlinkToSrc(self):
        self.skipIfSymlinkNotSupported()
        src_file = self.makePath('foo')
        dst_file = self.makePath('bar')
        contents = 'contents of file'
        self.createFile(src_file, contents=contents)
        self.createLink(dst_file, src_file)
        self.assertTrue(os.path.exists(src_file))
        self.assertRaises(shutil.Error,
                          shutil.copyfile, src_file, dst_file)

    def testSucceedsIfDestExistsAndIsWritable(self):
        src_file = self.makePath('xyzzy')
        dst_file = self.makePath('xyzzy_copy')
        src_contents = 'contents of source file'
        dst_contents = 'contents of dest file'
        self.createFile(src_file, contents=src_contents)
        self.createFile(dst_file, contents=dst_contents)
        self.assertTrue(os.path.exists(src_file))
        self.assertTrue(os.path.exists(dst_file))
        shutil.copyfile(src_file, dst_file)
        self.assertTrue(os.path.exists(dst_file))
        self.checkContents(dst_file, src_contents)

    def testRaisesIfDestExistsAndIsNotWritable(self):
        src_file = self.makePath('xyzzy')
        dst_file = self.makePath('xyzzy_copy')
        src_contents = 'contents of source file'
        dst_contents = 'contents of dest file'
        self.createFile(src_file, contents=src_contents)
        self.createFile(dst_file, contents=dst_contents)
        os.chmod(dst_file, 0o400)
        self.assertTrue(os.path.exists(src_file))
        self.assertTrue(os.path.exists(dst_file))
        self.assertRaises(IOError, shutil.copyfile, src_file, dst_file)
        os.chmod(dst_file, 0o666)

    def testRaisesIfDestDirIsNotWritableUnderPosix(self):
        self.checkPosixOnly()
        src_file = self.makePath('xyzzy')
        dst_dir = self.makePath('tmp', 'foo')
        dst_file = os.path.join(dst_dir, 'xyzzy')
        src_contents = 'contents of source file'
        self.createFile(src_file, contents=src_contents)
        self.createDirectory(dst_dir)
        os.chmod(dst_dir, 0o555)
        self.assertTrue(os.path.exists(src_file))
        self.assertTrue(os.path.exists(dst_dir))
        exception = OSError if sys.version_info[0] > 2 else IOError
        self.assertRaises(exception, shutil.copyfile, src_file, dst_file)

    def testRaisesIfSrcDoesntExist(self):
        src_file = self.makePath('xyzzy')
        dst_file = self.makePath('xyzzy_copy')
        self.assertFalse(os.path.exists(src_file))
        self.assertRaises(IOError, shutil.copyfile, src_file, dst_file)

    def testRaisesIfSrcNotReadable(self):
        self.checkPosixOnly()
        src_file = self.makePath('xyzzy')
        dst_file = self.makePath('xyzzy_copy')
        src_contents = 'contents of source file'
        self.createFile(src_file, contents=src_contents)
        os.chmod(src_file, 0o000)
        self.assertTrue(os.path.exists(src_file))
        self.assertRaises(IOError, shutil.copyfile, src_file, dst_file)

    def testRaisesIfSrcIsADirectory(self):
        src_file = self.makePath('xyzzy')
        dst_file = self.makePath('xyzzy_copy')
        self.createDirectory(src_file)
        self.assertTrue(os.path.exists(src_file))
        if self.is_windows_fs and not self.is_python2:
            self.assertRaises(OSError, shutil.copyfile, src_file, dst_file)
        else:
            self.assertRaises(IOError, shutil.copyfile, src_file, dst_file)

    def testRaisesIfDestIsADirectory(self):
        src_file = self.makePath('xyzzy')
        dst_dir = self.makePath('tmp', 'foo')
        src_contents = 'contents of source file'
        self.createFile(src_file, contents=src_contents)
        self.createDirectory(dst_dir)
        self.assertTrue(os.path.exists(src_file))
        self.assertTrue(os.path.exists(dst_dir))
        if self.is_windows_fs and not self.is_python2:
            self.assertRaises(OSError, shutil.copyfile, src_file, dst_dir)
        else:
            self.assertRaises(IOError, shutil.copyfile, src_file, dst_dir)


class RealCopyFileTest(FakeCopyFileTest):
    def useRealFs(self):
        return True


if __name__ == '__main__':
    unittest.main()
