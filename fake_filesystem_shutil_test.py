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

"""Tests for `fake_filesystem_shutil` if used in `fake_filesystem_unittest.TestCase`.
Note that almost all of the functionality is delegated to the real `shutil`
and works correctly with the fake filesystem because of the faked `os` module.
"""

import shutil
import stat
import sys
import time

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from pyfakefs import fake_filesystem
from pyfakefs import fake_filesystem_unittest


class FakeShutilModuleTest(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        self.fs.SetDiskUsage(1000)

    def testRmtree(self):
        directory = 'xyzzy'
        self.fs.CreateDirectory(directory)
        self.fs.CreateDirectory('%s/subdir' % directory)
        self.fs.CreateFile('%s/subfile' % directory)
        self.assertTrue(self.fs.Exists(directory))
        shutil.rmtree(directory)
        self.assertFalse(self.fs.Exists(directory))
        self.assertFalse(self.fs.Exists('%s/subdir' % directory))
        self.assertFalse(self.fs.Exists('%s/subfile' % directory))

    def testRmtreeWithTrailingSlash(self):
        directory = 'xyzzy'
        self.fs.CreateDirectory(directory)
        self.fs.CreateDirectory('%s/subdir' % directory)
        self.fs.CreateFile('%s/subfile' % directory)
        shutil.rmtree(directory + '/')
        self.assertFalse(self.fs.Exists(directory))
        self.assertFalse(self.fs.Exists('%s/subdir' % directory))
        self.assertFalse(self.fs.Exists('%s/subfile' % directory))

    def testRmtreeWithoutPermissionForAFile(self):
        self.fs.CreateFile('/foo/bar')
        self.fs.CreateFile('/foo/baz', st_mode=stat.S_IFREG | 0o444)
        self.assertRaises(OSError, shutil.rmtree, '/foo')
        self.assertTrue(self.fs.Exists('/foo/baz'))

    def testRmtreeWithOpenFilePosix(self):
        self.fs.is_windows_fs = False
        fake_open = fake_filesystem.FakeFileOpen(self.fs)
        self.fs.CreateFile('/foo/bar')
        self.fs.CreateFile('/foo/baz')
        fake_open('/foo/baz', 'r')
        shutil.rmtree('/foo')
        self.assertFalse(self.fs.Exists('/foo/baz'))

    def testRmtreeWithOpenFileFailsUnderWindows(self):
        self.fs.is_windows_fs = True
        fake_open = fake_filesystem.FakeFileOpen(self.fs)
        self.fs.CreateFile('/foo/bar')
        self.fs.CreateFile('/foo/baz')
        fake_open('/foo/baz', 'r')
        self.assertRaises(OSError, shutil.rmtree, '/foo')
        self.assertTrue(self.fs.Exists('/foo/baz'))

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

        directory = 'nonexisting'
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
        src_file = 'xyzzy'
        dst_file = 'xyzzy_copy'
        src_obj = self.fs.CreateFile(src_file)
        src_obj.st_mode = ((src_obj.st_mode & ~0o7777) | 0o750)
        self.assertTrue(self.fs.Exists(src_file))
        self.assertFalse(self.fs.Exists(dst_file))
        shutil.copy(src_file, dst_file)
        self.assertTrue(self.fs.Exists(dst_file))
        dst_obj = self.fs.GetObject(dst_file)
        self.assertEqual(src_obj.st_mode, dst_obj.st_mode)

    def testCopyDirectory(self):
        src_file = 'xyzzy'
        parent_directory = 'parent'
        dst_file = '%s/%s' % (parent_directory, src_file)
        src_obj = self.fs.CreateFile(src_file)
        self.fs.CreateDirectory(parent_directory)
        src_obj.st_mode = ((src_obj.st_mode & ~0o7777) | 0o750)
        self.assertTrue(self.fs.Exists(src_file))
        self.assertTrue(self.fs.Exists(parent_directory))
        self.assertFalse(self.fs.Exists(dst_file))
        shutil.copy(src_file, parent_directory)
        self.assertTrue(self.fs.Exists(dst_file))
        dst_obj = self.fs.GetObject(dst_file)
        self.assertEqual(src_obj.st_mode, dst_obj.st_mode)

    def testCopystat(self):
        src_file = 'xyzzy'
        dst_file = 'xyzzy_copy'
        src_obj = self.fs.CreateFile(src_file)
        dst_obj = self.fs.CreateFile(dst_file)
        src_obj.st_mode = ((src_obj.st_mode & ~0o7777) | 0o750)
        src_obj.st_atime = time.time()
        src_obj.st_mtime = time.time()
        self.assertTrue(self.fs.Exists(src_file))
        self.assertTrue(self.fs.Exists(dst_file))
        shutil.copystat(src_file, dst_file)
        self.assertEqual(src_obj.st_mode, dst_obj.st_mode)
        self.assertEqual(src_obj.st_atime, dst_obj.st_atime)
        self.assertEqual(src_obj.st_mtime, dst_obj.st_mtime)

    def testCopy2(self):
        src_file = 'xyzzy'
        dst_file = 'xyzzy_copy'
        src_obj = self.fs.CreateFile(src_file)
        src_obj.st_mode = ((src_obj.st_mode & ~0o7777) | 0o750)
        src_obj.st_atime = time.time()
        src_obj.st_mtime = time.time()
        self.assertTrue(self.fs.Exists(src_file))
        self.assertFalse(self.fs.Exists(dst_file))
        shutil.copy2(src_file, dst_file)
        self.assertTrue(self.fs.Exists(dst_file))
        dst_obj = self.fs.GetObject(dst_file)
        self.assertEqual(src_obj.st_mode, dst_obj.st_mode)
        self.assertEqual(src_obj.st_atime, dst_obj.st_atime)
        self.assertEqual(src_obj.st_mtime, dst_obj.st_mtime)

    def testCopy2Directory(self):
        src_file = 'xyzzy'
        parent_directory = 'parent'
        dst_file = '%s/%s' % (parent_directory, src_file)
        src_obj = self.fs.CreateFile(src_file)
        self.fs.CreateDirectory(parent_directory)
        src_obj.st_mode = ((src_obj.st_mode & ~0o7777) | 0o750)
        src_obj.st_atime = time.time()
        src_obj.st_mtime = time.time()
        self.assertTrue(self.fs.Exists(src_file))
        self.assertTrue(self.fs.Exists(parent_directory))
        self.assertFalse(self.fs.Exists(dst_file))
        shutil.copy2(src_file, parent_directory)
        self.assertTrue(self.fs.Exists(dst_file))
        dst_obj = self.fs.GetObject(dst_file)
        self.assertEqual(src_obj.st_mode, dst_obj.st_mode)
        self.assertEqual(src_obj.st_atime, dst_obj.st_atime)
        self.assertEqual(src_obj.st_mtime, dst_obj.st_mtime)

    def testCopytree(self):
        src_directory = 'xyzzy'
        dst_directory = 'xyzzy_copy'
        self.fs.CreateDirectory(src_directory)
        self.fs.CreateDirectory('%s/subdir' % src_directory)
        self.fs.CreateFile('%s/subfile' % src_directory)
        self.assertTrue(self.fs.Exists(src_directory))
        self.assertFalse(self.fs.Exists(dst_directory))
        shutil.copytree(src_directory, dst_directory)
        self.assertTrue(self.fs.Exists(dst_directory))
        self.assertTrue(self.fs.Exists('%s/subdir' % dst_directory))
        self.assertTrue(self.fs.Exists('%s/subfile' % dst_directory))

    def testCopytreeSrcIsFile(self):
        src_file = 'xyzzy'
        dst_directory = 'xyzzy_copy'
        self.fs.CreateFile(src_file)
        self.assertTrue(self.fs.Exists(src_file))
        self.assertFalse(self.fs.Exists(dst_directory))
        self.assertRaises(OSError,
                          shutil.copytree,
                          src_file,
                          dst_directory)

    def testMoveFileInSameFilesystem(self):
        src_file = '/original_xyzzy'
        dst_file = '/moved_xyzzy'
        src_object = self.fs.CreateFile(src_file)
        src_ino = src_object.st_ino
        src_dev = src_object.st_dev

        self.assertTrue(self.fs.Exists(src_file))
        self.assertFalse(self.fs.Exists(dst_file))
        shutil.move(src_file, dst_file)
        self.assertTrue(self.fs.Exists(dst_file))
        self.assertFalse(self.fs.Exists(src_file))

        dst_object = self.fs.GetObject(dst_file)
        self.assertEqual(src_ino, dst_object.st_ino)
        self.assertEqual(src_dev, dst_object.st_dev)

    def testMoveFileIntoOtherFilesystem(self):
        self.fs.AddMountPoint('/mount')
        src_file = '/original_xyzzy'
        dst_file = '/mount/moved_xyzzy'
        src_object = self.fs.CreateFile(src_file)
        src_ino = src_object.st_ino
        src_dev = src_object.st_dev

        shutil.move(src_file, dst_file)
        self.assertTrue(self.fs.Exists(dst_file))
        self.assertFalse(self.fs.Exists(src_file))

        dst_object = self.fs.GetObject(dst_file)
        self.assertNotEqual(src_ino, dst_object.st_ino)
        self.assertNotEqual(src_dev, dst_object.st_dev)

    def testMoveFileIntoDirectory(self):
        src_file = 'xyzzy'
        dst_directory = 'directory'
        dst_file = '%s/%s' % (dst_directory, src_file)
        self.fs.CreateFile(src_file)
        self.fs.CreateDirectory(dst_directory)
        self.assertTrue(self.fs.Exists(src_file))
        self.assertFalse(self.fs.Exists(dst_file))
        shutil.move(src_file, dst_directory)
        self.assertTrue(self.fs.Exists(dst_file))
        self.assertFalse(self.fs.Exists(src_file))

    def testMoveDirectory(self):
        src_directory = 'original_xyzzy'
        dst_directory = 'moved_xyzzy'
        self.fs.CreateDirectory(src_directory)
        self.fs.CreateFile('%s/subfile' % src_directory)
        self.fs.CreateDirectory('%s/subdir' % src_directory)
        self.assertTrue(self.fs.Exists(src_directory))
        self.assertFalse(self.fs.Exists(dst_directory))
        shutil.move(src_directory, dst_directory)
        self.assertTrue(self.fs.Exists(dst_directory))
        self.assertTrue(self.fs.Exists('%s/subfile' % dst_directory))
        self.assertTrue(self.fs.Exists('%s/subdir' % dst_directory))
        self.assertFalse(self.fs.Exists(src_directory))

    @unittest.skipIf(sys.version_info < (3, 3), 'New in Python 3.3')
    def testDiskUsage(self):
        self.fs.CreateFile('/foo/bar', st_size=400)
        disk_usage = shutil.disk_usage('/')
        self.assertEqual(1000, disk_usage.total)
        self.assertEqual(400, disk_usage.used)
        self.assertEqual(600, disk_usage.free)
        self.assertEqual((1000, 400, 600), disk_usage)

        self.fs.AddMountPoint('/mount', total_size=500)
        self.fs.CreateFile('/mount/foo/bar', st_size=400)
        disk_usage = shutil.disk_usage('/mount/foo/')
        self.assertEqual((500, 400, 100), disk_usage)


class CopyFileTest(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()

    def testCommonCase(self):
        src_file = 'xyzzy'
        dst_file = 'xyzzy_copy'
        contents = 'contents of file'
        self.fs.CreateFile(src_file, contents=contents)
        self.assertTrue(self.fs.Exists(src_file))
        self.assertFalse(self.fs.Exists(dst_file))
        shutil.copyfile(src_file, dst_file)
        self.assertTrue(self.fs.Exists(dst_file))
        self.assertEqual(contents, self.fs.GetObject(dst_file).contents)

    def testRaisesIfSourceAndDestAreTheSameFile(self):
        src_file = 'xyzzy'
        dst_file = src_file
        contents = 'contents of file'
        self.fs.CreateFile(src_file, contents=contents)
        self.assertTrue(self.fs.Exists(src_file))
        self.assertRaises(shutil.Error,
                          shutil.copyfile, src_file, dst_file)

    @unittest.skipIf(sys.platform.startswith('win') and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def testRaisesIfDestIsASymlinkToSrc(self):
        src_file = '/tmp/foo'
        dst_file = '/tmp/bar'
        contents = 'contents of file'
        self.fs.CreateFile(src_file, contents=contents)
        self.fs.CreateLink(dst_file, src_file)
        self.assertTrue(self.fs.Exists(src_file))
        self.assertRaises(shutil.Error,
                          shutil.copyfile, src_file, dst_file)

    def testSucceedsIfDestExistsAndIsWritable(self):
        src_file = 'xyzzy'
        dst_file = 'xyzzy_copy'
        src_contents = 'contents of source file'
        dst_contents = 'contents of dest file'
        self.fs.CreateFile(src_file, contents=src_contents)
        self.fs.CreateFile(dst_file, contents=dst_contents)
        self.assertTrue(self.fs.Exists(src_file))
        self.assertTrue(self.fs.Exists(dst_file))
        shutil.copyfile(src_file, dst_file)
        self.assertTrue(self.fs.Exists(dst_file))
        self.assertEqual(src_contents,
                         self.fs.GetObject(dst_file).contents)

    def testRaisesIfDestExistsAndIsNotWritable(self):
        src_file = 'xyzzy'
        dst_file = 'xyzzy_copy'
        src_contents = 'contents of source file'
        dst_contents = 'contents of dest file'
        self.fs.CreateFile(src_file, contents=src_contents)
        self.fs.CreateFile(dst_file,
                                   st_mode=stat.S_IFREG | 0o400,
                                   contents=dst_contents)
        self.assertTrue(self.fs.Exists(src_file))
        self.assertTrue(self.fs.Exists(dst_file))
        self.assertRaises(IOError, shutil.copyfile, src_file, dst_file)

    def testRaisesIfDestDirIsNotWritableUnderPosix(self):
        self.fs.is_windows_fs = False
        src_file = 'xyzzy'
        dst_dir = '/tmp/foo'
        dst_file = '%s/%s' % (dst_dir, src_file)
        src_contents = 'contents of source file'
        self.fs.CreateFile(src_file, contents=src_contents)
        self.fs.CreateDirectory(dst_dir, perm_bits=0o555)
        self.assertTrue(self.fs.Exists(src_file))
        self.assertTrue(self.fs.Exists(dst_dir))
        self.assertRaises(OSError, shutil.copyfile, src_file, dst_file)

    def testRaisesIfSrcDoesntExist(self):
        src_file = 'xyzzy'
        dst_file = 'xyzzy_copy'
        self.assertFalse(self.fs.Exists(src_file))
        self.assertRaises(IOError, shutil.copyfile, src_file, dst_file)

    def testRaisesIfSrcNotReadable(self):
        src_file = 'xyzzy'
        dst_file = 'xyzzy_copy'
        src_contents = 'contents of source file'
        self.fs.CreateFile(src_file,
                                   st_mode=stat.S_IFREG | 0o000,
                                   contents=src_contents)
        self.assertTrue(self.fs.Exists(src_file))
        self.assertRaises(IOError, shutil.copyfile, src_file, dst_file)

    def testRaisesIfSrcIsADirectory(self):
        src_file = 'xyzzy'
        dst_file = 'xyzzy_copy'
        self.fs.CreateDirectory(src_file)
        self.assertTrue(self.fs.Exists(src_file))
        if self.fs.is_windows_fs:
            self.assertRaises(OSError, shutil.copyfile, src_file, dst_file)
        else:
            self.assertRaises(IOError, shutil.copyfile, src_file, dst_file)

    def testRaisesIfDestIsADirectory(self):
        src_file = 'xyzzy'
        dst_dir = '/tmp/foo'
        src_contents = 'contents of source file'
        self.fs.CreateFile(src_file, contents=src_contents)
        self.fs.CreateDirectory(dst_dir)
        self.assertTrue(self.fs.Exists(src_file))
        self.assertTrue(self.fs.Exists(dst_dir))
        if self.fs.is_windows_fs:
            self.assertRaises(OSError, shutil.copyfile, src_file, dst_dir)
        else:
            self.assertRaises(IOError, shutil.copyfile, src_file, dst_dir)


if __name__ == '__main__':
    unittest.main()
