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

    def assertModeEqual(self, expected, actual):
        return self.assertEqual(stat.S_IMODE(expected), stat.S_IMODE(actual))

    def assertRaisesIOError(self, subtype, expression, *args, **kwargs):
        try:
            expression(*args, **kwargs)
            self.fail('No exception was raised, IOError expected')
        except IOError as exc:
            self.assertEqual(exc.errno, subtype)

    def assertRaisesOSError(self, subtype, expression, *args, **kwargs):
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
        if self.useRealFs():
            self.base_path = tempfile.mkdtemp()
        else:
            self.base_path = self.pathSeparator() + 'basepath'

    @property
    def is_windows_fs(self):
        return TestCase.is_windows

    @property
    def is_macos(self):
        return TestCase.is_macos

    @property
    def is_pypy(self):
        return platform.python_implementation() == 'PyPy'

    def useRealFs(self):
        return False

    def pathSeparator(self):
        return '/'

    def checkWindowsOnly(self):
        if self.useRealFs():
            if not TestCase.is_windows:
                raise unittest.SkipTest(
                    'Testing Windows specific functionality')
        else:
            self.filesystem.is_windows_fs = True
            self.filesystem.is_macos = False

    def checkLinuxOnly(self):
        if self.useRealFs():
            if TestCase.is_macos or TestCase.is_windows:
                raise unittest.SkipTest(
                    'Testing Linux specific functionality')
        else:
            self.filesystem.is_windows_fs = False
            self.filesystem.is_macos = False

    def checkMacOsOnly(self):
        if self.useRealFs():
            if not TestCase.is_macos:
                raise unittest.SkipTest(
                    'Testing MacOS specific functionality')
        else:
            self.filesystem.is_windows_fs = False
            self.filesystem.is_macos = True

    def checkLinuxAndWindows(self):
        if self.useRealFs():
            if TestCase.is_macos:
                raise unittest.SkipTest(
                    'Testing non-MacOs functionality')
        else:
            self.filesystem.is_macos = False

    def checkCaseInsensitiveFs(self):
        if self.useRealFs():
            if not TestCase.is_macos and not TestCase.is_windows:
                raise unittest.SkipTest(
                    'Testing case insensitive specific functionality')
        else:
            self.filesystem.is_case_sensitive = False

    def checkCaseSensitiveFs(self):
        if self.useRealFs():
            if TestCase.is_macos or TestCase.is_windows:
                raise unittest.SkipTest(
                    'Testing case sensitive specific functionality')
        else:
            self.filesystem.is_case_sensitive = True

    def checkPosixOnly(self):
        if self.useRealFs():
            if TestCase.is_windows:
                raise unittest.SkipTest(
                    'Testing Posix specific functionality')
        else:
            self.filesystem.is_windows_fs = False

    def skipRealFs(self):
        if self.useRealFs():
            raise unittest.SkipTest('Only tests fake FS')

    def skipRealFsFailure(self, skipWindows=True, skipPosix=True,
                          skipMacOs=True, skipLinux=True,
                          skipPython2=True, skipPython3=True):
        if True:
            if (self.useRealFs() and
                    (TestCase.is_windows and skipWindows or
                             not TestCase.is_windows
                             and skipMacOs and skipLinux or
                             TestCase.is_macos and skipMacOs or
                                 not TestCase.is_windows and
                                 not TestCase.is_macos and skipLinux) and
                    (TestCase.is_python2 and skipPython2 or
                             not TestCase.is_python2 and skipPython3)):
                raise unittest.SkipTest(
                    'Skipping because FakeFS does not match real FS')

    def symlinksCanBeTested(self):
        if not TestCase.is_windows or not self.useRealFs():
            return True
        if TestCase.symlinks_can_be_tested is None:
            link_path = self.makePath('link')
            try:
                self.os.symlink(self.base_path, link_path)
                TestCase.symlinks_can_be_tested = True
                self.os.remove(link_path)
            except OSError:
                TestCase.symlinks_can_be_tested = False
        return TestCase.symlinks_can_be_tested

    def skipIfSymlinkNotSupported(self):
        if (self.useRealFs() and TestCase.is_windows or
                    not self.useRealFs() and self.filesystem.is_windows_fs):
            if sys.version_info < (3, 3):
                raise unittest.SkipTest(
                    'Symlinks are not supported under Windows '
                    'before Python 3.3')
        if not self.symlinksCanBeTested():
            raise unittest.SkipTest(
                'Symlinks under Windows need admin privileges')

    def makePath(self, *args):
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


    def createDirectory(self, dir_path):
        existing_path = dir_path
        components = []
        while existing_path and not self.os.path.exists(existing_path):
            existing_path, component = self.os.path.split(existing_path)
            components.insert(0, component)
        for component in components:
            existing_path = self.os.path.join(existing_path, component)
            self.os.mkdir(existing_path)
            self.os.chmod(existing_path, 0o777)

    def createFile(self, file_path, contents=None, encoding=None):
        self.createDirectory(self.os.path.dirname(file_path))
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

    def createLink(self, link_path, target_path):
        self.createDirectory(self.os.path.dirname(link_path))
        self.os.symlink(target_path, link_path)

    def checkContents(self, file_path, contents):
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
        if not self.useRealFs():
            self.filesystem = fake_filesystem.FakeFilesystem(
                path_separator=self.pathSeparator())
            self.open = fake_filesystem.FakeFileOpen(self.filesystem)
            self.os = fake_filesystem.FakeOsModule(self.filesystem)
            self.filesystem.CreateDirectory(self.base_path)

    @property
    def is_windows_fs(self):
        if self.useRealFs():
            return self.is_windows
        return self.filesystem.is_windows_fs

    @property
    def is_macos(self):
        if self.useRealFs():
            return TestCase.is_macos
        return self.filesystem.is_macos

    def tearDown(self):
        if self.useRealFs():
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

    def testNewFileAndDirectory(self):
        self.assertTrue(stat.S_IFREG & self.fake_file.st_mode)
        self.assertTrue(stat.S_IFDIR & self.fake_dir.st_mode)
        self.assertEqual({}, self.fake_dir.contents)
        self.assertEqual(10, self.fake_file.st_ctime)

    def testAddEntry(self):
        self.fake_dir.AddEntry(self.fake_file)
        self.assertEqual({'foobar': self.fake_file}, self.fake_dir.contents)

    def testGetEntry(self):
        self.fake_dir.AddEntry(self.fake_file)
        self.assertEqual(self.fake_file, self.fake_dir.GetEntry('foobar'))

    def testGetPath(self):
        self.filesystem.root.AddEntry(self.fake_dir)
        self.fake_dir.AddEntry(self.fake_file)
        self.assertEqual('/somedir/foobar', self.fake_file.GetPath())

    def testRemoveEntry(self):
        self.fake_dir.AddEntry(self.fake_file)
        self.assertEqual(self.fake_file, self.fake_dir.GetEntry('foobar'))
        self.fake_dir.RemoveEntry('foobar')
        self.assertRaises(KeyError, self.fake_dir.GetEntry, 'foobar')

    def testShouldThrowIfSetSizeIsNotInteger(self):
        self.assertRaisesIOError(errno.ENOSPC, self.fake_file.SetSize, 0.1)

    def testShouldThrowIfSetSizeIsNegative(self):
        self.assertRaisesIOError(errno.ENOSPC, self.fake_file.SetSize, -1)

    def testProduceEmptyFileIfSetSizeIsZero(self):
        self.fake_file.SetSize(0)
        self.assertEqual('', self.fake_file.contents)

    def testSetsContentEmptyIfSetSizeIsZero(self):
        self.fake_file.SetSize(0)
        self.assertEqual('', self.fake_file.contents)

    def testTruncateFileIfSizeIsSmallerThanCurrentSize(self):
        self.fake_file.SetSize(6)
        self.assertEqual('dummy_', self.fake_file.contents)

    def testLeaveFileUnchangedIfSizeIsEqualToCurrentSize(self):
        self.fake_file.SetSize(10)
        self.assertEqual('dummy_file', self.fake_file.contents)

    def testSetContentsToDirRaises(self):
        # Regression test for #276
        self.filesystem.is_windows_fs = True
        error_check = (self.assertRaisesIOError if self.is_python2
                       else self.assertRaisesOSError)
        error_check(errno.EISDIR, self.fake_dir.SetContents, 'a')
        self.filesystem.is_windows_fs = False
        self.assertRaisesIOError(errno.EISDIR, self.fake_dir.SetContents, 'a')

    def testPadsFileContentWithNullBytesIfSizeIsGreaterThanCurrentSize(self):
        self.fake_file.SetSize(13)
        self.assertEqual('dummy_file\0\0\0', self.fake_file.contents)

    def testSetMTime(self):
        self.assertEqual(10, self.fake_file.st_mtime)
        self.fake_file.SetMTime(13)
        self.assertEqual(13, self.fake_file.st_mtime)
        self.fake_file.SetMTime(131)
        self.assertEqual(131, self.fake_file.st_mtime)

    def testFileInode(self):
        filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        fake_os = fake_filesystem.FakeOsModule(filesystem)
        file_path = 'some_file1'
        filesystem.CreateFile(file_path, contents='contents here1')
        self.assertLess(0, fake_os.stat(file_path)[stat.ST_INO])

        file_obj = filesystem.GetObject(file_path)
        file_obj.SetIno(43)
        self.assertEqual(43, fake_os.stat(file_path)[stat.ST_INO])

    def testDirectoryInode(self):
        filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        fake_os = fake_filesystem.FakeOsModule(filesystem)
        dirpath = 'testdir'
        filesystem.CreateDirectory(dirpath)
        self.assertLess(0, fake_os.stat(dirpath)[stat.ST_INO])

        dir_obj = filesystem.GetObject(dirpath)
        dir_obj.SetIno(43)
        self.assertEqual(43, fake_os.stat(dirpath)[stat.ST_INO])

    def testOrderedDirs(self):
        filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        filesystem.CreateDirectory('/foo')
        filesystem.CreateFile('/foo/2')
        filesystem.CreateFile('/foo/4')
        filesystem.CreateFile('/foo/1')
        filesystem.CreateFile('/foo/3')
        fake_dir = filesystem.GetObject('/foo')
        self.assertEqual(['2', '4', '1', '3'], fake_dir.ordered_dirs)


class SetLargeFileSizeTest(TestCase):
    def setUp(self):
        filesystem = fake_filesystem.FakeFilesystem()
        self.fake_file = fake_filesystem.FakeFile('foobar',
                                                  filesystem=filesystem)

    def testShouldThrowIfSizeIsNotInteger(self):
        self.assertRaisesIOError(errno.ENOSPC, self.fake_file.SetLargeFileSize,
                                 0.1)

    def testShouldThrowIfSizeIsNegative(self):
        self.assertRaisesIOError(errno.ENOSPC, self.fake_file.SetLargeFileSize,
                                 -1)

    def testSetsContentNoneIfSizeIsNonNegativeInteger(self):
        self.fake_file.SetLargeFileSize(1000000000)
        self.assertEqual(None, self.fake_file.contents)
        self.assertEqual(1000000000, self.fake_file.st_size)


class NormalizePathTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.root_name = '/'

    def testEmptyPathShouldGetNormalizedToRootPath(self):
        self.assertEqual(self.root_name, self.filesystem.NormalizePath(''))

    def testRootPathRemainsUnchanged(self):
        self.assertEqual(self.root_name,
                         self.filesystem.NormalizePath(self.root_name))

    def testRelativePathForcedToCwd(self):
        path = 'bar'
        self.filesystem.cwd = '/foo'
        self.assertEqual('/foo/bar', self.filesystem.NormalizePath(path))

    def testAbsolutePathRemainsUnchanged(self):
        path = '/foo/bar'
        self.assertEqual(path, self.filesystem.NormalizePath(path))

    def testDottedPathIsNormalized(self):
        path = '/foo/..'
        self.assertEqual('/', self.filesystem.NormalizePath(path))
        path = 'foo/../bar'
        self.assertEqual('/bar', self.filesystem.NormalizePath(path))

    def testDotPathIsNormalized(self):
        path = '.'
        self.assertEqual('/', self.filesystem.NormalizePath(path))


class GetPathComponentsTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.root_name = '/'

    def testRootPathShouldReturnEmptyList(self):
        self.assertEqual([], self.filesystem.GetPathComponents(self.root_name))

    def testEmptyPathShouldReturnEmptyList(self):
        self.assertEqual([], self.filesystem.GetPathComponents(''))

    def testRelativePathWithOneComponentShouldReturnComponent(self):
        self.assertEqual(['foo'], self.filesystem.GetPathComponents('foo'))

    def testAbsolutePathWithOneComponentShouldReturnComponent(self):
        self.assertEqual(['foo'], self.filesystem.GetPathComponents('/foo'))

    def testTwoLevelRelativePathShouldReturnComponents(self):
        self.assertEqual(['foo', 'bar'],
                         self.filesystem.GetPathComponents('foo/bar'))

    def testTwoLevelAbsolutePathShouldReturnComponents(self):
        self.assertEqual(['foo', 'bar'],
                         self.filesystem.GetPathComponents('/foo/bar'))


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

    def testNewFilesystem(self):
        self.assertEqual('/', self.filesystem.path_separator)
        self.assertTrue(stat.S_IFDIR & self.filesystem.root.st_mode)
        self.assertEqual(self.root_name, self.filesystem.root.name)
        self.assertEqual({}, self.filesystem.root.contents)

    def testNoneRaisesTypeError(self):
        self.assertRaises(TypeError, self.filesystem.Exists, None)

    def testEmptyStringDoesNotExist(self):
        self.assertFalse(self.filesystem.Exists(''))

    def testExistsRoot(self):
        self.assertTrue(self.filesystem.Exists(self.root_name))

    def testExistsUnaddedFile(self):
        self.assertFalse(self.filesystem.Exists(self.fake_file.name))

    def testNotExistsSubpathNamedLikeFileContents(self):
        # Regression test for #219
        file_path = "/foo/bar"
        self.filesystem.CreateFile(file_path, contents='baz')
        self.assertFalse(self.filesystem.Exists(file_path + "/baz"))

    def testGetRootObject(self):
        self.assertEqual(self.filesystem.root,
                         self.filesystem.GetObject(self.root_name))

    def testAddObjectToRoot(self):
        self.filesystem.AddObject(self.root_name, self.fake_file)
        self.assertEqual({'foobar': self.fake_file},
                         self.filesystem.root.contents)

    def testExistsAddedFile(self):
        self.filesystem.AddObject(self.root_name, self.fake_file)
        self.assertTrue(self.filesystem.Exists(self.fake_file.name))

    def testExistsRelativePathPosix(self):
        self.filesystem.is_windows_fs = False
        self.filesystem.CreateFile('/a/b/file_one')
        self.filesystem.CreateFile('/a/c/file_two')
        self.assertTrue(self.filesystem.Exists('a/b/../c/file_two'))
        self.assertTrue(self.filesystem.Exists('/a/c/../b/file_one'))
        self.assertTrue(self.filesystem.Exists('/a/c/../../a/b/file_one'))
        self.assertFalse(self.filesystem.Exists('a/b/../z/d'))
        self.assertFalse(self.filesystem.Exists('a/b/../z/../c/file_two'))
        self.filesystem.cwd = '/a/c'
        self.assertTrue(self.filesystem.Exists('../b/file_one'))
        self.assertTrue(self.filesystem.Exists('../../a/b/file_one'))
        self.assertTrue(self.filesystem.Exists('../../a/b/../../a/c/file_two'))
        self.assertFalse(self.filesystem.Exists('../z/file_one'))
        self.assertFalse(self.filesystem.Exists('../z/../c/file_two'))

    def testExistsRelativePathWindows(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.is_macos = False
        self.filesystem.CreateFile('/a/b/file_one')
        self.filesystem.CreateFile('/a/c/file_two')
        self.assertTrue(self.filesystem.Exists('a/b/../c/file_two'))
        self.assertTrue(self.filesystem.Exists('/a/c/../b/file_one'))
        self.assertTrue(self.filesystem.Exists('/a/c/../../a/b/file_one'))
        self.assertFalse(self.filesystem.Exists('a/b/../z/d'))
        self.assertTrue(self.filesystem.Exists('a/b/../z/../c/file_two'))
        self.filesystem.cwd = '/a/c'
        self.assertTrue(self.filesystem.Exists('../b/file_one'))
        self.assertTrue(self.filesystem.Exists('../../a/b/file_one'))
        self.assertTrue(self.filesystem.Exists('../../a/b/../../a/c/file_two'))
        self.assertFalse(self.filesystem.Exists('../z/file_one'))
        self.assertTrue(self.filesystem.Exists('../z/../c/file_two'))

    def testGetObjectFromRoot(self):
        self.filesystem.AddObject(self.root_name, self.fake_file)
        self.assertEqual(self.fake_file, self.filesystem.GetObject('foobar'))

    def testGetNonexistentObjectFromRootError(self):
        self.filesystem.AddObject(self.root_name, self.fake_file)
        self.assertEqual(self.fake_file, self.filesystem.GetObject('foobar'))
        self.assertRaisesIOError(errno.ENOENT, self.filesystem.GetObject,
                                 'some_bogus_filename')

    def testRemoveObjectFromRoot(self):
        self.filesystem.AddObject(self.root_name, self.fake_file)
        self.filesystem.RemoveObject(self.fake_file.name)
        self.assertRaisesIOError(errno.ENOENT, self.filesystem.GetObject,
                                 self.fake_file.name)

    def testRemoveNonexistenObjectFromRootError(self):
        self.assertRaisesIOError(errno.ENOENT, self.filesystem.RemoveObject,
                                 'some_bogus_filename')

    def testExistsRemovedFile(self):
        self.filesystem.AddObject(self.root_name, self.fake_file)
        self.filesystem.RemoveObject(self.fake_file.name)
        self.assertFalse(self.filesystem.Exists(self.fake_file.name))

    def testAddObjectToChild(self):
        self.filesystem.AddObject(self.root_name, self.fake_child)
        self.filesystem.AddObject(self.fake_child.name, self.fake_file)
        self.assertEqual(
            {self.fake_file.name: self.fake_file},
            self.filesystem.root.GetEntry(self.fake_child.name).contents)

    def testAddObjectToRegularFileErrorPosix(self):
        self.filesystem.is_windows_fs = False
        self.filesystem.AddObject(self.root_name, self.fake_file)
        self.assertRaisesOSError(errno.ENOTDIR,
                                 self.filesystem.AddObject,
                                 self.fake_file.name, self.fake_file)

    def testAddObjectToRegularFileErrorWindows(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.AddObject(self.root_name, self.fake_file)
        self.assertRaisesOSError(errno.ENOENT,
                                 self.filesystem.AddObject,
                                 self.fake_file.name, self.fake_file)

    def testExistsFileAddedToChild(self):
        self.filesystem.AddObject(self.root_name, self.fake_child)
        self.filesystem.AddObject(self.fake_child.name, self.fake_file)
        path = self.filesystem.JoinPaths(self.fake_child.name,
                                         self.fake_file.name)
        self.assertTrue(self.filesystem.Exists(path))

    def testGetObjectFromChild(self):
        self.filesystem.AddObject(self.root_name, self.fake_child)
        self.filesystem.AddObject(self.fake_child.name, self.fake_file)
        self.assertEqual(self.fake_file,
                         self.filesystem.GetObject(
                             self.filesystem.JoinPaths(self.fake_child.name,
                                                       self.fake_file.name)))

    def testGetNonexistentObjectFromChildError(self):
        self.filesystem.AddObject(self.root_name, self.fake_child)
        self.filesystem.AddObject(self.fake_child.name, self.fake_file)
        self.assertRaisesIOError(errno.ENOENT, self.filesystem.GetObject,
                                 self.filesystem.JoinPaths(
                                     self.fake_child.name,
                                     'some_bogus_filename'))

    def testRemoveObjectFromChild(self):
        self.filesystem.AddObject(self.root_name, self.fake_child)
        self.filesystem.AddObject(self.fake_child.name, self.fake_file)
        target_path = self.filesystem.JoinPaths(self.fake_child.name,
                                                self.fake_file.name)
        self.filesystem.RemoveObject(target_path)
        self.assertRaisesIOError(errno.ENOENT, self.filesystem.GetObject,
                                 target_path)

    def testRemoveObjectFromChildError(self):
        self.filesystem.AddObject(self.root_name, self.fake_child)
        self.assertRaisesIOError(errno.ENOENT, self.filesystem.RemoveObject,
                                 self.filesystem.JoinPaths(
                                     self.fake_child.name,
                                     'some_bogus_filename'))

    def testRemoveObjectFromNonDirectoryError(self):
        self.filesystem.AddObject(self.root_name, self.fake_file)
        self.assertRaisesIOError(errno.ENOTDIR, self.filesystem.RemoveObject,
                                 self.filesystem.JoinPaths(
                                     '%s' % self.fake_file.name,
                                     'file_does_not_matter_since_parent_not_a_directory'))

    def testExistsFileRemovedFromChild(self):
        self.filesystem.AddObject(self.root_name, self.fake_child)
        self.filesystem.AddObject(self.fake_child.name, self.fake_file)
        path = self.filesystem.JoinPaths(self.fake_child.name,
                                         self.fake_file.name)
        self.filesystem.RemoveObject(path)
        self.assertFalse(self.filesystem.Exists(path))

    def testOperateOnGrandchildDirectory(self):
        self.filesystem.AddObject(self.root_name, self.fake_child)
        self.filesystem.AddObject(self.fake_child.name, self.fake_grandchild)
        grandchild_directory = self.filesystem.JoinPaths(self.fake_child.name,
                                                         self.fake_grandchild.name)
        grandchild_file = self.filesystem.JoinPaths(grandchild_directory,
                                                    self.fake_file.name)
        self.assertRaises(IOError, self.filesystem.GetObject, grandchild_file)
        self.filesystem.AddObject(grandchild_directory, self.fake_file)
        self.assertEqual(self.fake_file,
                         self.filesystem.GetObject(grandchild_file))
        self.assertTrue(self.filesystem.Exists(grandchild_file))
        self.filesystem.RemoveObject(grandchild_file)
        self.assertRaises(IOError, self.filesystem.GetObject, grandchild_file)
        self.assertFalse(self.filesystem.Exists(grandchild_file))

    def testCreateDirectoryInRootDirectory(self):
        path = 'foo'
        self.filesystem.CreateDirectory(path)
        new_dir = self.filesystem.GetObject(path)
        self.assertEqual(os.path.basename(path), new_dir.name)
        self.assertTrue(stat.S_IFDIR & new_dir.st_mode)

    def testCreateDirectoryInRootDirectoryAlreadyExistsError(self):
        path = 'foo'
        self.filesystem.CreateDirectory(path)
        self.assertRaisesOSError(errno.EEXIST, self.filesystem.CreateDirectory,
                                 path)

    def testCreateDirectory(self):
        path = 'foo/bar/baz'
        self.filesystem.CreateDirectory(path)
        new_dir = self.filesystem.GetObject(path)
        self.assertEqual(os.path.basename(path), new_dir.name)
        self.assertTrue(stat.S_IFDIR & new_dir.st_mode)

        # Create second directory to make sure first is OK.
        path = '%s/quux' % path
        self.filesystem.CreateDirectory(path)
        new_dir = self.filesystem.GetObject(path)
        self.assertEqual(os.path.basename(path), new_dir.name)
        self.assertTrue(stat.S_IFDIR & new_dir.st_mode)

    def testCreateDirectoryAlreadyExistsError(self):
        path = 'foo/bar/baz'
        self.filesystem.CreateDirectory(path)
        self.assertRaisesOSError(errno.EEXIST, self.filesystem.CreateDirectory,
                                 path)

    def testCreateFileInReadOnlyDirectoryRaisesInPosix(self):
        self.filesystem.is_windows_fs = False
        dir_path = '/foo/bar'
        self.filesystem.CreateDirectory(dir_path, perm_bits=0o555)
        file_path = dir_path + '/baz'
        if sys.version_info[0] < 3:
            self.assertRaisesIOError(errno.EACCES, self.filesystem.CreateFile,
                                     file_path)
        else:
            self.assertRaisesOSError(errno.EACCES, self.filesystem.CreateFile,
                                     file_path)


    def testCreateFileInReadOnlyDirectoryPossibleInWindows(self):
        self.filesystem.is_windows_fs = True
        dir_path = 'C:/foo/bar'
        self.filesystem.CreateDirectory(dir_path, perm_bits=0o555)
        file_path = dir_path + '/baz'
        self.filesystem.CreateFile(file_path)
        self.assertTrue(self.filesystem.Exists(file_path))

    def testCreateFileInCurrentDirectory(self):
        path = 'foo'
        contents = 'dummy data'
        self.filesystem.CreateFile(path, contents=contents)
        self.assertTrue(self.filesystem.Exists(path))
        self.assertFalse(self.filesystem.Exists(os.path.dirname(path)))
        path = './%s' % path
        self.assertTrue(self.filesystem.Exists(os.path.dirname(path)))

    def testCreateFileInRootDirectory(self):
        path = '/foo'
        contents = 'dummy data'
        self.filesystem.CreateFile(path, contents=contents)
        new_file = self.filesystem.GetObject(path)
        self.assertTrue(self.filesystem.Exists(path))
        self.assertTrue(self.filesystem.Exists(os.path.dirname(path)))
        self.assertEqual(os.path.basename(path), new_file.name)
        self.assertTrue(stat.S_IFREG & new_file.st_mode)
        self.assertEqual(contents, new_file.contents)

    def testCreateFileWithSizeButNoContentCreatesLargeFile(self):
        path = 'large_foo_bar'
        self.filesystem.CreateFile(path, st_size=100000000)
        new_file = self.filesystem.GetObject(path)
        self.assertEqual(None, new_file.contents)
        self.assertEqual(100000000, new_file.st_size)

    def testCreateFileInRootDirectoryAlreadyExistsError(self):
        path = 'foo'
        self.filesystem.CreateFile(path)
        self.assertRaisesOSError(errno.EEXIST, self.filesystem.CreateFile,
                                 path)

    def testCreateFile(self):
        path = 'foo/bar/baz'
        retval = self.filesystem.CreateFile(path, contents='dummy_data')
        self.assertTrue(self.filesystem.Exists(path))
        self.assertTrue(self.filesystem.Exists(os.path.dirname(path)))
        new_file = self.filesystem.GetObject(path)
        self.assertEqual(os.path.basename(path), new_file.name)
        self.assertTrue(stat.S_IFREG & new_file.st_mode)
        self.assertEqual(new_file, retval)

    def testCreateFileWithIncorrectModeType(self):
        self.assertRaises(TypeError, self.filesystem.CreateFile, 'foo', 'bar')

    def testCreateFileAlreadyExistsError(self):
        path = 'foo/bar/baz'
        self.filesystem.CreateFile(path, contents='dummy_data')
        self.assertRaisesOSError(errno.EEXIST, self.filesystem.CreateFile,
                                 path)

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def testCreateLink(self):
        path = 'foo/bar/baz'
        target_path = 'foo/bar/quux'
        new_file = self.filesystem.CreateLink(path, 'quux')
        # Neither the path not the final target exists before we actually write to
        # one of them, even though the link appears in the file system.
        self.assertFalse(self.filesystem.Exists(path))
        self.assertFalse(self.filesystem.Exists(target_path))
        self.assertTrue(stat.S_IFLNK & new_file.st_mode)

        # but once we write the linked to file, they both will exist.
        self.filesystem.CreateFile(target_path)
        self.assertTrue(self.filesystem.Exists(path))
        self.assertTrue(self.filesystem.Exists(target_path))

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def testResolveObject(self):
        target_path = 'dir/target'
        target_contents = '0123456789ABCDEF'
        link_name = 'x'
        self.filesystem.CreateDirectory('dir')
        self.filesystem.CreateFile('dir/target', contents=target_contents)
        self.filesystem.CreateLink(link_name, target_path)
        obj = self.filesystem.ResolveObject(link_name)
        self.assertEqual('target', obj.name)
        self.assertEqual(target_contents, obj.contents)

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def checkLresolveObject(self):
        target_path = 'dir/target'
        target_contents = '0123456789ABCDEF'
        link_name = 'x'
        self.filesystem.CreateDirectory('dir')
        self.filesystem.CreateFile('dir/target', contents=target_contents)
        self.filesystem.CreateLink(link_name, target_path)
        obj = self.filesystem.LResolveObject(link_name)
        self.assertEqual(link_name, obj.name)
        self.assertEqual(target_path, obj.contents)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def testLresolveObjectWindows(self):
        self.filesystem.is_windows_fs = True
        self.checkLresolveObject()

    def testLresolveObjectPosix(self):
        self.filesystem.is_windows_fs = False
        self.checkLresolveObject()

    def checkDirectoryAccessOnFile(self, error_subtype):
        self.filesystem.CreateFile('not_a_dir')
        self.assertRaisesIOError(error_subtype, self.filesystem.ResolveObject,
                                 'not_a_dir/foo')
        self.assertRaisesIOError(error_subtype, self.filesystem.ResolveObject,
                                 'not_a_dir/foo/bar')
        self.assertRaisesIOError(error_subtype, self.filesystem.LResolveObject,
                                 'not_a_dir/foo')
        self.assertRaisesIOError(error_subtype,
                                 self.filesystem.LResolveObject,
                                 'not_a_dir/foo/bar')

    def testDirectoryAccessOnFileWindows(self):
        self.filesystem.is_windows_fs = True
        self.checkDirectoryAccessOnFile(errno.ENOENT)

    def testDirectoryAccessOnFilePosix(self):
        self.filesystem.is_windows_fs = False
        self.checkDirectoryAccessOnFile(errno.ENOTDIR)


class CaseInsensitiveFakeFilesystemTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.filesystem.is_case_sensitive = False
        self.os = fake_filesystem.FakeOsModule(self.filesystem)
        self.path = self.os.path

    def testGetObject(self):
        self.filesystem.CreateDirectory('/foo/bar')
        self.filesystem.CreateFile('/foo/bar/baz')
        self.assertTrue(self.filesystem.GetObject('/Foo/Bar/Baz'))

    def testRemoveObject(self):
        self.filesystem.CreateDirectory('/foo/bar')
        self.filesystem.CreateFile('/foo/bar/baz')
        self.filesystem.RemoveObject('/Foo/Bar/Baz')
        self.assertFalse(self.filesystem.Exists('/foo/bar/baz'))

    def testExists(self):
        self.filesystem.CreateDirectory('/Foo/Bar')
        self.assertTrue(self.filesystem.Exists('/Foo/Bar'))
        self.assertTrue(self.filesystem.Exists('/foo/bar'))

        self.filesystem.CreateFile('/foo/Bar/baz')
        self.assertTrue(self.filesystem.Exists('/Foo/bar/BAZ'))
        self.assertTrue(self.filesystem.Exists('/foo/bar/baz'))

    def testCreateDirectoryWithDifferentCaseRoot(self):
        self.filesystem.CreateDirectory('/Foo/Bar')
        self.filesystem.CreateDirectory('/foo/bar/baz')
        dir1 = self.filesystem.GetObject('/Foo/Bar')
        dir2 = self.filesystem.GetObject('/foo/bar')
        self.assertEqual(dir1, dir2)

    def testCreateFileWithDifferentCaseDir(self):
        self.filesystem.CreateDirectory('/Foo/Bar')
        self.filesystem.CreateFile('/foo/bar/baz')
        dir1 = self.filesystem.GetObject('/Foo/Bar')
        dir2 = self.filesystem.GetObject('/foo/bar')
        self.assertEqual(dir1, dir2)

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def testResolvePath(self):
        self.filesystem.CreateDirectory('/foo/baz')
        self.filesystem.CreateLink('/Foo/Bar', './baz/bip')
        self.assertEqual('/foo/baz/bip',
                         self.filesystem.ResolvePath('/foo/bar'))

    def testIsdirIsfile(self):
        self.filesystem.CreateFile('foo/bar')
        self.assertTrue(self.path.isdir('Foo'))
        self.assertFalse(self.path.isfile('Foo'))
        self.assertTrue(self.path.isfile('Foo/Bar'))
        self.assertFalse(self.path.isdir('Foo/Bar'))

    def testGetsize(self):
        file_path = 'foo/bar/baz'
        self.filesystem.CreateFile(file_path, contents='1234567')
        self.assertEqual(7, self.path.getsize('FOO/BAR/BAZ'))

    def testGetsizeWithLoopingSymlink(self):
        self.filesystem.is_windows_fs = False
        dir_path = '/foo/bar'
        self.filesystem.CreateDirectory(dir_path)
        link_path = dir_path + "/link"
        link_target = link_path + "/link"
        self.os.symlink(link_target, link_path)
        self.assertRaisesOSError(errno.ELOOP, self.os.path.getsize, link_path)

    def testGetMtime(self):
        test_file = self.filesystem.CreateFile('foo/bar1.txt')
        test_file.SetMTime(24)
        self.assertEqual(24, self.path.getmtime('Foo/Bar1.TXT'))

    def testGetObjectWithFileSize(self):
        self.filesystem.CreateFile('/Foo/Bar', st_size=10)
        self.assertTrue(self.filesystem.GetObject('/foo/bar'))


class CaseSensitiveFakeFilesystemTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.filesystem.is_case_sensitive = True
        self.os = fake_filesystem.FakeOsModule(self.filesystem)
        self.path = self.os.path

    def testGetObject(self):
        self.filesystem.CreateDirectory('/foo/bar')
        self.filesystem.CreateFile('/foo/bar/baz')
        self.assertRaises(IOError, self.filesystem.GetObject, '/Foo/Bar/Baz')

    def testRemoveObject(self):
        self.filesystem.CreateDirectory('/foo/bar')
        self.filesystem.CreateFile('/foo/bar/baz')
        self.assertRaises(IOError, self.filesystem.RemoveObject,
                          '/Foo/Bar/Baz')
        self.assertTrue(self.filesystem.Exists('/foo/bar/baz'))

    def testExists(self):
        self.filesystem.CreateDirectory('/Foo/Bar')
        self.assertTrue(self.filesystem.Exists('/Foo/Bar'))
        self.assertFalse(self.filesystem.Exists('/foo/bar'))

        self.filesystem.CreateFile('/foo/Bar/baz')
        self.assertFalse(self.filesystem.Exists('/Foo/bar/BAZ'))
        self.assertFalse(self.filesystem.Exists('/foo/bar/baz'))

    def testCreateDirectoryWithDifferentCaseRoot(self):
        self.filesystem.CreateDirectory('/Foo/Bar')
        self.filesystem.CreateDirectory('/foo/bar/baz')
        dir1 = self.filesystem.GetObject('/Foo/Bar')
        dir2 = self.filesystem.GetObject('/foo/bar')
        self.assertNotEqual(dir1, dir2)

    def testCreateFileWithDifferentCaseDir(self):
        self.filesystem.CreateDirectory('/Foo/Bar')
        self.filesystem.CreateFile('/foo/bar/baz')
        dir1 = self.filesystem.GetObject('/Foo/Bar')
        dir2 = self.filesystem.GetObject('/foo/bar')
        self.assertNotEqual(dir1, dir2)

    def testIsdirIsfile(self):
        self.filesystem.CreateFile('foo/bar')
        self.assertFalse(self.path.isdir('Foo'))
        self.assertFalse(self.path.isfile('Foo'))
        self.assertFalse(self.path.isfile('Foo/Bar'))
        self.assertFalse(self.path.isdir('Foo/Bar'))

    def testGetsize(self):
        file_path = 'foo/bar/baz'
        self.filesystem.CreateFile(file_path, contents='1234567')
        self.assertRaises(os.error, self.path.getsize, 'FOO/BAR/BAZ')

    def testGetMtime(self):
        test_file = self.filesystem.CreateFile('foo/bar1.txt')
        test_file.SetMTime(24)
        self.assertRaisesOSError(errno.ENOENT, self.path.getmtime,
                                 'Foo/Bar1.TXT')


class FakeOsModuleTestBase(RealFsTestCase):
    def createTestFile(self, path):
        self.createFile(path)
        self.assertTrue(self.os.path.exists(path))
        st = self.os.stat(path)
        self.assertEqual(0o666, stat.S_IMODE(st.st_mode))
        self.assertTrue(st.st_mode & stat.S_IFREG)
        self.assertFalse(st.st_mode & stat.S_IFDIR)

    def createTestDirectory(self, path):
        self.createDirectory(path)
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

    def testChdir(self):
        """chdir should work on a directory."""
        directory = self.makePath('foo')
        self.createDirectory(directory)
        self.os.chdir(directory)

    def testChdirFailsNonExist(self):
        """chdir should raise OSError if the target does not exist."""
        directory = self.makePath('no', 'such', 'directory')
        self.assertRaisesOSError(errno.ENOENT, self.os.chdir, directory)

    def testChdirFailsNonDirectory(self):
        """chdir should raise OSError if the target is not a directory."""
        filename = self.makePath('foo', 'bar')
        self.createFile(filename)
        self.assertRaisesOSError(self.not_dir_error(), self.os.chdir, filename)

    def testConsecutiveChdir(self):
        """Consecutive relative chdir calls should work."""
        dir1 = self.makePath('foo')
        dir2 = 'bar'
        full_dirname = self.os.path.join(dir1, dir2)
        self.createDirectory(full_dirname)
        self.os.chdir(dir1)
        self.os.chdir(dir2)
        # use real path to handle symlink /var to /private/var in MacOs
        self.assertEqual(os.path.realpath(self.os.getcwd()),
                         os.path.realpath(full_dirname))

    def testBackwardsChdir(self):
        """chdir into '..' should behave appropriately."""
        # skipping real fs test - can't test root dir
        self.skipRealFs()
        rootdir = self.os.getcwd()
        dirname = 'foo'
        abs_dirname = self.os.path.abspath(dirname)
        self.filesystem.CreateDirectory(dirname)
        self.os.chdir(dirname)
        self.assertEqual(abs_dirname, self.os.getcwd())
        self.os.chdir('..')
        self.assertEqual(rootdir, self.os.getcwd())
        self.os.chdir(self.os.path.join(dirname, '..'))
        self.assertEqual(rootdir, self.os.getcwd())

    def testGetCwd(self):
        # skipping real fs test - can't test root dir
        self.skipRealFs()
        dirname = self.makePath('foo', 'bar')
        self.createDirectory(dirname)
        self.assertEqual(self.os.getcwd(), self.os.path.sep)
        self.os.chdir(dirname)
        self.assertEqual(self.os.getcwd(), dirname)

    def testListdir(self):
        directory = self.makePath('xyzzy', 'plugh')
        files = ['foo', 'bar', 'baz']
        for f in files:
            self.createFile(self.os.path.join(directory, f))
        files.sort()
        self.assertEqual(files, sorted(self.os.listdir(directory)))

    @unittest.skipIf(sys.version_info < (3, 3),
                     'file descriptor as path new in Python 3.3')
    def testListdirUsesOpenFdAsPath(self):
        self.checkPosixOnly()
        if os.listdir not in os.supports_fd:
            self.skipRealFs()
        self.assertRaisesOSError(errno.EBADF, self.os.listdir, 500)
        dir_path = self.makePath('xyzzy', 'plugh')
        files = ['foo', 'bar', 'baz']
        for f in files:
            self.createFile(self.os.path.join(dir_path, f))
        files.sort()

        path_des = self.os.open(dir_path, os.O_RDONLY)
        self.assertEqual(files, sorted(self.os.listdir(path_des)))

    def testListdirReturnsList(self):
        directory_root = self.makePath('xyzzy')
        self.os.mkdir(directory_root)
        directory = self.os.path.join(directory_root, 'bug')
        self.os.mkdir(directory)
        self.createFile(self.makePath(directory, 'foo'))
        self.assertEqual(['foo'], self.os.listdir(directory))

    def testListdirOnSymlink(self):
        self.skipIfSymlinkNotSupported()
        directory = self.makePath('xyzzy')
        files = ['foo', 'bar', 'baz']
        for f in files:
            self.createFile(self.makePath(directory, f))
        self.createLink(self.makePath('symlink'), self.makePath('xyzzy'))
        files.sort()
        self.assertEqual(files,
                         sorted(self.os.listdir(self.makePath('symlink'))))

    def testListdirError(self):
        file_path = self.makePath('foo', 'bar', 'baz')
        self.createFile(file_path)
        self.assertRaisesOSError(self.not_dir_error(),
                                 self.os.listdir, file_path)

    def testExistsCurrentDir(self):
        self.assertTrue(self.os.path.exists('.'))

    def testListdirCurrent(self):
        files = ['foo', 'bar', 'baz']
        for f in files:
            self.createFile(self.makePath(f))
        files.sort()
        self.assertEqual(files, sorted(self.os.listdir(self.base_path)))

    def testFdopen(self):
        # under Windows and Python2, hangs in closing file
        self.skipRealFsFailure(skipPosix=False, skipPython3=False)
        file_path1 = self.makePath('some_file1')
        self.createFile(file_path1, contents='contents here1')
        with self.open(file_path1, 'r') as fake_file1:
            fileno = fake_file1.fileno()
            fake_file2 = self.os.fdopen(fileno)
            self.assertNotEqual(fake_file2, fake_file1)

        self.assertRaises(TypeError, self.os.fdopen, None)
        self.assertRaises(TypeError, self.os.fdopen, 'a string')

    def testOutOfRangeFdopen(self):
        # test some file descriptor that is clearly out of range
        self.assertRaisesOSError(errno.EBADF, self.os.fdopen, 100)

    def testClosedFileDescriptor(self):
        # under Windows and Python2, hangs in tearDown
        self.skipRealFsFailure(skipPosix=False, skipPython3=False)
        first_path = self.makePath('some_file1')
        second_path = self.makePath('some_file2')
        third_path = self.makePath('some_file3')
        self.createFile(first_path, contents='contents here1')
        self.createFile(second_path, contents='contents here2')
        self.createFile(third_path, contents='contents here3')

        fake_file1 = self.open(first_path, 'r')
        fake_file2 = self.open(second_path, 'r')
        fake_file3 = self.open(third_path, 'r')
        fileno1 = fake_file1.fileno()
        fileno2 = fake_file2.fileno()
        fileno3 = fake_file3.fileno()

        self.os.close(fileno2)
        self.assertRaisesOSError(errno.EBADF, self.os.close, fileno2)
        self.assertEqual(fileno1, fake_file1.fileno())
        self.assertEqual(fileno3, fake_file3.fileno())

        with self.os.fdopen(fileno1) as f:
            self.assertFalse(f is fake_file1)
        with self.os.fdopen(fileno3) as f:
            self.assertFalse(f is fake_file3)
        self.assertRaisesOSError(errno.EBADF, self.os.fdopen, fileno2)

    def testFdopenMode(self):
        self.skipRealFs()
        file_path1 = self.makePath('some_file1')
        self.createFile(file_path1, contents='contents here1')
        self.os.chmod(file_path1, (stat.S_IFREG | 0o666) ^ stat.S_IWRITE)

        fake_file1 = self.open(file_path1, 'r')
        fileno1 = fake_file1.fileno()
        self.os.fdopen(fileno1)
        self.os.fdopen(fileno1, 'r')
        exception = OSError if self.is_python2 else IOError
        self.assertRaises(exception, self.os.fdopen, fileno1, 'w')

    def testFstat(self):
        directory = self.makePath('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.createFile(file_path, contents='ABCDE')
        with self.open(file_path) as file_obj:
            fileno = file_obj.fileno()
            self.assertTrue(stat.S_IFREG & self.os.fstat(fileno)[stat.ST_MODE])
            self.assertTrue(stat.S_IFREG & self.os.fstat(fileno).st_mode)
            self.assertEqual(5, self.os.fstat(fileno)[stat.ST_SIZE])

    def testStat(self):
        directory = self.makePath('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.createFile(file_path, contents='ABCDE')
        self.assertTrue(stat.S_IFDIR & self.os.stat(directory)[stat.ST_MODE])
        self.assertTrue(stat.S_IFREG & self.os.stat(file_path)[stat.ST_MODE])
        self.assertTrue(stat.S_IFREG & self.os.stat(file_path).st_mode)
        self.assertEqual(5, self.os.stat(file_path)[stat.ST_SIZE])

    @unittest.skipIf(sys.version_info < (3, 3),
                     'file descriptor as path new in Python 3.3')
    def testStatUsesOpenFdAsPath(self):
        self.skipRealFs()
        self.assertRaisesOSError(errno.EBADF, self.os.stat, 5)
        file_path = self.makePath('foo', 'bar')
        self.createFile(file_path)

        with self.open(file_path) as f:
            self.assertTrue(
                stat.S_IFREG & self.os.stat(f.filedes)[stat.ST_MODE])

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def testStatNoFollowSymlinksPosix(self):
        """Test that stat with follow_symlinks=False behaves like lstat."""
        self.checkPosixOnly()
        directory = self.makePath('xyzzy')
        base_name = 'plugh'
        file_contents = 'frobozz'
        # Just make sure we didn't accidentally make our test data meaningless.
        self.assertNotEqual(len(base_name), len(file_contents))
        file_path = self.os.path.join(directory, base_name)
        link_path = self.os.path.join(directory, 'link')
        self.createFile(file_path, contents=file_contents)
        self.createLink(link_path, base_name)
        self.assertEqual(len(file_contents),
                         self.os.stat(file_path, follow_symlinks=False)[
                             stat.ST_SIZE])
        self.assertEqual(len(base_name),
                         self.os.stat(link_path, follow_symlinks=False)[
                             stat.ST_SIZE])

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def testStatNoFollowSymlinksWindows(self):
        """Test that stat with follow_symlinks=False behaves like lstat."""
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        directory = self.makePath('xyzzy')
        base_name = 'plugh'
        file_contents = 'frobozz'
        # Just make sure we didn't accidentally make our test data meaningless.
        self.assertNotEqual(len(base_name), len(file_contents))
        file_path = self.os.path.join(directory, base_name)
        link_path = self.os.path.join(directory, 'link')
        self.createFile(file_path, contents=file_contents)
        self.createLink(link_path, base_name)
        self.assertEqual(len(file_contents),
                         self.os.stat(file_path, follow_symlinks=False)[
                             stat.ST_SIZE])
        self.assertEqual(0,
                         self.os.stat(link_path, follow_symlinks=False)[
                             stat.ST_SIZE])

    def testLstatSizePosix(self):
        self.checkPosixOnly()
        directory = self.makePath('xyzzy')
        base_name = 'plugh'
        file_contents = 'frobozz'
        # Just make sure we didn't accidentally make our test data meaningless.
        self.assertNotEqual(len(base_name), len(file_contents))
        file_path = self.os.path.join(directory, base_name)
        link_path = self.os.path.join(directory, 'link')
        self.createFile(file_path, contents=file_contents)
        self.createLink(link_path, base_name)
        self.assertEqual(len(file_contents),
                         self.os.lstat(file_path)[stat.ST_SIZE])
        self.assertEqual(len(base_name),
                         self.os.lstat(link_path)[stat.ST_SIZE])

    def testLstatSizeWindows(self):
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        directory = self.makePath('xyzzy')
        base_name = 'plugh'
        file_contents = 'frobozz'
        # Just make sure we didn't accidentally make our test data meaningless.
        self.assertNotEqual(len(base_name), len(file_contents))
        file_path = self.os.path.join(directory, base_name)
        link_path = self.os.path.join(directory, 'link')
        self.createFile(file_path, contents=file_contents)
        self.createLink(link_path, base_name)
        self.assertEqual(len(file_contents),
                         self.os.lstat(file_path)[stat.ST_SIZE])
        self.assertEqual(0,
                         self.os.lstat(link_path)[stat.ST_SIZE])


    @unittest.skipIf(sys.version_info < (3, 3),
                     'file descriptor as path new in Python 3.3')
    def testLstatUsesOpenFdAsPath(self):
        self.skipIfSymlinkNotSupported()
        if os.lstat not in os.supports_fd:
            self.skipRealFs()
        self.assertRaisesOSError(errno.EBADF, self.os.lstat, 5)
        file_path = self.makePath('foo', 'bar')
        link_path = self.makePath('foo', 'link')
        file_contents = b'contents'
        self.createFile(file_path, contents=file_contents)
        self.createLink(link_path, file_path)

        with self.open(file_path) as f:
            self.assertEqual(len(file_contents),
                             self.os.lstat(f.filedes)[stat.ST_SIZE])

    def testStatNonExistentFile(self):
        # set up
        file_path = self.makePath('non', 'existent', 'file')
        self.assertFalse(self.os.path.exists(file_path))
        # actual tests
        try:
            # Use try-catch to check exception attributes.
            self.os.stat(file_path)
            self.fail('Exception is expected.')  # COV_NF_LINE
        except OSError as os_error:
            self.assertEqual(errno.ENOENT, os_error.errno)
            self.assertEqual(file_path, os_error.filename)

    def testReadlink(self):
        self.skipIfSymlinkNotSupported()
        link_path = self.makePath('foo', 'bar', 'baz')
        target = self.makePath('tarJAY')
        self.createLink(link_path, target)
        self.assertEqual(self.os.readlink(link_path), target)

    def checkReadlinkRaisesIfPathIsNotALink(self):
        file_path = self.makePath('foo', 'bar', 'eleventyone')
        self.createFile(file_path)
        self.assertRaisesOSError(errno.EINVAL, self.os.readlink, file_path)

    def testReadlinkRaisesIfPathIsNotALinkWindows(self):
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        self.checkReadlinkRaisesIfPathIsNotALink()

    def testReadlinkRaisesIfPathIsNotALinkPosix(self):
        self.checkPosixOnly()
        self.checkReadlinkRaisesIfPathIsNotALink()

    def checkReadlinkRaisesIfPathHasFile(self, error_subtype):
        self.createFile(self.makePath('a_file'))
        file_path = self.makePath('a_file', 'foo')
        self.assertRaisesOSError(error_subtype, self.os.readlink, file_path)
        file_path = self.makePath('a_file', 'foo', 'bar')
        self.assertRaisesOSError(error_subtype, self.os.readlink, file_path)

    def testReadlinkRaisesIfPathHasFileWindows(self):
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        self.checkReadlinkRaisesIfPathHasFile(errno.ENOENT)

    def testReadlinkRaisesIfPathHasFilePosix(self):
        self.checkPosixOnly()
        self.checkReadlinkRaisesIfPathHasFile(errno.ENOTDIR)

    def testReadlinkRaisesIfPathDoesNotExist(self):
        self.skipIfSymlinkNotSupported()
        self.assertRaisesOSError(errno.ENOENT, self.os.readlink,
                                 '/this/path/does/not/exist')

    def testReadlinkRaisesIfPathIsNone(self):
        self.skipIfSymlinkNotSupported()
        self.assertRaises(TypeError, self.os.readlink, None)

    def testReadlinkWithLinksInPath(self):
        self.skipIfSymlinkNotSupported()
        self.createLink(self.makePath('meyer', 'lemon', 'pie'),
                        self.makePath('yum'))
        self.createLink(self.makePath('geo', 'metro'),
                        self.makePath('meyer'))
        self.assertEqual(self.makePath('yum'),
                         self.os.readlink(
                             self.makePath('geo', 'metro', 'lemon', 'pie')))

    def testReadlinkWithChainedLinksInPath(self):
        self.skipIfSymlinkNotSupported()
        self.createLink(self.makePath(
            'eastern', 'european', 'wolfhounds', 'chase'),
            self.makePath('cats'))
        self.createLink(self.makePath('russian'),
                        self.makePath('eastern', 'european'))
        self.createLink(self.makePath('dogs'),
                        self.makePath('russian', 'wolfhounds'))
        self.assertEqual(self.makePath('cats'),
                         self.os.readlink(self.makePath('dogs', 'chase')))

    def checkRemoveDir(self, dir_error):
        directory = self.makePath('xyzzy')
        dir_path = self.os.path.join(directory, 'plugh')
        self.createDirectory(dir_path)
        self.assertTrue(self.os.path.exists(dir_path))
        self.assertRaisesOSError(dir_error, self.os.remove, dir_path)
        self.assertTrue(self.os.path.exists(dir_path))
        self.os.chdir(directory)
        self.assertRaisesOSError(dir_error, self.os.remove, dir_path)
        self.assertTrue(self.os.path.exists(dir_path))
        self.assertRaisesOSError(errno.ENOENT, self.os.remove, '/plugh')

    def testRemoveDirLinux(self):
        self.checkLinuxOnly()
        self.checkRemoveDir(errno.EISDIR)

    def testRemoveDirMacOs(self):
        self.checkMacOsOnly()
        self.checkRemoveDir(errno.EPERM)

    def testRemoveDirWindows(self):
        self.checkWindowsOnly()
        self.checkRemoveDir(errno.EACCES)

    def testRemoveFile(self):
        directory = self.makePath('zzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.createFile(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.os.remove(file_path)
        self.assertFalse(self.os.path.exists(file_path))

    def testRemoveFileNoDirectory(self):
        directory = self.makePath('zzy')
        file_name = 'plugh'
        file_path = self.os.path.join(directory, file_name)
        self.createFile(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.os.chdir(directory)
        self.os.remove(file_name)
        self.assertFalse(self.os.path.exists(file_path))

    def testRemoveFileWithReadPermissionRaisesInWindows(self):
        self.checkWindowsOnly()
        path = self.makePath('foo', 'bar')
        self.createFile(path)
        self.os.chmod(path, 0o444)
        self.assertRaisesOSError(errno.EACCES, self.os.remove, path)
        self.os.chmod(path, 0o666)

    def testRemoveFileWithReadPermissionShallSucceedInPosix(self):
        self.checkPosixOnly()
        path = self.makePath('foo', 'bar')
        self.createFile(path)
        self.os.chmod(path, 0o444)
        self.os.remove(path)
        self.assertFalse(self.os.path.exists(path))

    def testRemoveFileWithoutParentPermissionRaisesInPosix(self):
        self.checkPosixOnly()
        parent_dir = self.makePath('foo')
        path = self.os.path.join(parent_dir, 'bar')
        self.createFile(path)
        self.os.chmod(parent_dir, 0o666)  # missing execute permission
        self.assertRaisesOSError(errno.EACCES, self.os.remove, path)
        self.os.chmod(parent_dir, 0o555)  # missing write permission
        self.assertRaisesOSError(errno.EACCES, self.os.remove, path)
        self.os.chmod(parent_dir, 0o333)
        self.os.remove(path)
        self.assertFalse(self.os.path.exists(path))

    def testRemoveOpenFileFailsUnderWindows(self):
        self.checkWindowsOnly()
        path = self.makePath('foo', 'bar')
        self.createFile(path)
        with self.open(path, 'r'):
            self.assertRaisesOSError(errno.EACCES, self.os.remove, path)
        self.assertTrue(self.os.path.exists(path))

    def testRemoveOpenFilePossibleUnderPosix(self):
        self.checkPosixOnly()
        path = self.makePath('foo', 'bar')
        self.createFile(path)
        self.open(path, 'r')
        self.os.remove(path)
        self.assertFalse(self.os.path.exists(path))

    def testRemoveFileRelativePath(self):
        self.skipRealFs()
        original_dir = self.os.getcwd()
        directory = self.makePath('zzy')
        subdirectory = self.os.path.join(directory, 'zzy')
        file_name = 'plugh'
        file_path = self.os.path.join(directory, file_name)
        file_path_relative = self.os.path.join('..', file_name)
        self.createFile(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.createDirectory(subdirectory)
        self.assertTrue(self.os.path.exists(subdirectory))
        self.os.chdir(subdirectory)
        self.os.remove(file_path_relative)
        self.assertFalse(self.os.path.exists(file_path_relative))
        self.os.chdir(original_dir)
        self.assertFalse(self.os.path.exists(file_path))

    def checkRemoveDirRaisesError(self, dir_error):
        directory = self.makePath('zzy')
        self.createDirectory(directory)
        self.assertRaisesOSError(dir_error, self.os.remove, directory)

    def testRemoveDirRaisesErrorLinux(self):
        self.checkLinuxOnly()
        self.checkRemoveDirRaisesError(errno.EISDIR)

    def testRemoveDirRaisesErrorMacOs(self):
        self.checkMacOsOnly()
        self.checkRemoveDirRaisesError(errno.EPERM)

    def testRemoveDirRaisesErrorWindows(self):
        self.checkWindowsOnly()
        self.checkRemoveDirRaisesError(errno.EACCES)

    def testRemoveSymlinkToDir(self):
        self.skipIfSymlinkNotSupported()
        directory = self.makePath('zzy')
        link = self.makePath('link_to_dir')
        self.createDirectory(directory)
        self.os.symlink(directory, link)
        self.assertTrue(self.os.path.exists(directory))
        self.assertTrue(self.os.path.exists(link))
        self.os.remove(link)
        self.assertTrue(self.os.path.exists(directory))
        self.assertFalse(self.os.path.exists(link))

    def testUnlinkRaisesIfNotExist(self):
        file_path = self.makePath('file', 'does', 'not', 'exist')
        self.assertFalse(self.os.path.exists(file_path))
        self.assertRaisesOSError(errno.ENOENT, self.os.unlink, file_path)

    def testRenameToNonexistentFile(self):
        """Can rename a file to an unused name."""
        directory = self.makePath('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.createFile(old_file_path, contents='test contents')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertFalse(self.os.path.exists(new_file_path))
        self.os.rename(old_file_path, new_file_path)
        self.assertFalse(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.checkContents(new_file_path, 'test contents')

    def testRenameDirToSymlinkPosix(self):
        self.checkPosixOnly()
        link_path = self.makePath('link')
        dir_path = self.makePath('dir')
        link_target = self.os.path.join(dir_path, 'link_target')
        self.createDirectory(dir_path)
        self.os.symlink(link_target, link_path)
        self.assertRaisesOSError(errno.ENOTDIR, self.os.rename, dir_path,
                                 link_path)

    def testRenameDirToSymlinkWindows(self):
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        link_path = self.makePath('link')
        dir_path = self.makePath('dir')
        link_target = self.os.path.join(dir_path, 'link_target')
        self.createDirectory(dir_path)
        self.os.symlink(link_target, link_path)
        self.assertRaisesOSError(errno.EEXIST, self.os.rename, dir_path,
                                 link_path)

    def testRenameFileToSymlink(self):
        self.checkPosixOnly()
        link_path = self.makePath('file_link')
        file_path = self.makePath('file')
        self.os.symlink(file_path, link_path)
        self.createFile(file_path)
        self.os.rename(file_path, link_path)
        self.assertFalse(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.exists(link_path))
        self.assertTrue(self.os.path.isfile(link_path))

    def testRenameSymlinkToSymlink(self):
        self.checkPosixOnly()
        base_path = self.makePath('foo', 'bar')
        self.createDirectory(base_path)
        link_path1 = self.os.path.join(base_path, 'link1')
        link_path2 = self.os.path.join(base_path, 'link2')
        self.os.symlink(base_path, link_path1)
        self.os.symlink(base_path, link_path2)
        self.os.rename(link_path1, link_path2)
        self.assertFalse(self.os.path.exists(link_path1))
        self.assertTrue(self.os.path.exists(link_path2))

    def testRenameSymlinkToSymlinkForParentRaises(self):
        self.checkPosixOnly()
        dir_link = self.makePath('dir_link')
        dir_path = self.makePath('dir')
        dir_in_dir_path = self.os.path.join(dir_link, 'inner_dir')
        self.createDirectory(dir_path)
        self.os.symlink(dir_path, dir_link)
        self.createDirectory(dir_in_dir_path)
        self.assertRaisesOSError(errno.EINVAL, self.os.rename, dir_path,
                                 dir_in_dir_path)

    def testRecursiveRenameRaises(self):
        self.checkPosixOnly()
        base_path = self.makePath('foo', 'bar')
        self.createDirectory(base_path)
        new_path = self.os.path.join(base_path, 'new_dir')
        self.assertRaisesOSError(errno.EINVAL, self.os.rename, base_path,
                                 new_path)

    def testRenameFileToParentDirFile(self):
        # Regression test for issue 230
        dir_path = self.makePath('dir')
        self.createDirectory(dir_path)
        file_path = self.makePath('old_file')
        new_file_path = self.os.path.join(dir_path, 'new_file')
        self.createFile(file_path)
        self.os.rename(file_path, new_file_path)

    def testRenameWithTargetParentFileRaisesPosix(self):
        self.checkPosixOnly()
        file_path = self.makePath('foo', 'baz')
        self.createFile(file_path)
        self.assertRaisesOSError(errno.ENOTDIR, self.os.rename, file_path,
                                 file_path + '/new')

    def testRenameWithTargetParentFileRaisesWindows(self):
        self.checkWindowsOnly()
        file_path = self.makePath('foo', 'baz')
        self.createFile(file_path)
        self.assertRaisesOSError(errno.EACCES, self.os.rename, file_path,
                                 self.os.path.join(file_path, 'new'))

    def testRenameSymlinkToSource(self):
        self.checkPosixOnly()
        base_path = self.makePath('foo')
        link_path = self.os.path.join(base_path, 'slink')
        file_path = self.os.path.join(base_path, 'file')
        self.createFile(file_path)
        self.os.symlink(file_path, link_path)
        self.os.rename(link_path, file_path)
        self.assertFalse(self.os.path.exists(file_path))

    def testRenameSymlinkToDirRaises(self):
        self.checkPosixOnly()
        base_path = self.makePath('foo', 'bar')
        link_path = self.os.path.join(base_path, 'dir_link')
        dir_path = self.os.path.join(base_path, 'dir')
        self.createDirectory(dir_path)
        self.os.symlink(dir_path, link_path)
        self.assertRaisesOSError(errno.EISDIR, self.os.rename, link_path,
                                 dir_path)

    def testRenameBrokenSymlink(self):
        self.checkPosixOnly()
        base_path = self.makePath('foo')
        self.createDirectory(base_path)
        link_path = self.os.path.join(base_path, 'slink')
        file_path = self.os.path.join(base_path, 'file')
        self.os.symlink(file_path, link_path)
        self.os.rename(link_path, file_path)
        self.assertFalse(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.lexists(file_path))
        self.assertFalse(self.os.path.exists(link_path))

    def testRenameDirectory(self):
        """Can rename a directory to an unused name."""
        for old_path, new_path in [('wxyyw', 'xyzzy'), ('abccb', 'cdeed')]:
            old_path = self.makePath(old_path)
            new_path = self.makePath(new_path)
            self.createFile(self.os.path.join(old_path, 'plugh'),
                            contents='test')
            self.assertTrue(self.os.path.exists(old_path))
            self.assertFalse(self.os.path.exists(new_path))
            self.os.rename(old_path, new_path)
            self.assertFalse(self.os.path.exists(old_path))
            self.assertTrue(self.os.path.exists(new_path))
            self.checkContents(self.os.path.join(new_path, 'plugh'), 'test')
            if not self.useRealFs():
                self.assertEqual(3,
                                 self.filesystem.GetObject(new_path).st_nlink)

    def checkRenameDirectoryToExistingFileRaises(self, error_nr):
        dir_path = self.makePath('dir')
        file_path = self.makePath('file')
        self.createDirectory(dir_path)
        self.createFile(file_path)
        self.assertRaisesOSError(error_nr, self.os.rename, dir_path,
                                 file_path)

    def testRenameDirectoryToExistingFileRaisesPosix(self):
        self.checkPosixOnly()
        self.checkRenameDirectoryToExistingFileRaises(errno.ENOTDIR)

    def testRenameDirectoryToExistingFileRaisesWindows(self):
        self.checkWindowsOnly()
        self.checkRenameDirectoryToExistingFileRaises(errno.EEXIST)

    def testRenameToExistingDirectoryShouldRaiseUnderWindows(self):
        """Renaming to an existing directory raises OSError under Windows."""
        self.checkWindowsOnly()
        old_path = self.makePath('foo', 'bar')
        new_path = self.makePath('foo', 'baz')
        self.createDirectory(old_path)
        self.createDirectory(new_path)
        self.assertRaisesOSError(errno.EEXIST, self.os.rename, old_path,
                                 new_path)

    def testRenameToAHardlinkOfSameFileShouldDoNothing(self):
        self.skipRealFsFailure(skipPosix=False)
        self.skipIfSymlinkNotSupported()
        file_path = self.makePath('dir', 'file')
        self.createFile(file_path)
        link_path = self.makePath('link')
        self.os.link(file_path, link_path)
        self.os.rename(file_path, link_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.exists(link_path))

    def testHardlinkWorksWithSymlink(self):
        self.checkPosixOnly()
        base_path = self.makePath('foo')
        self.createDirectory(base_path)
        symlink_path = self.os.path.join(base_path, 'slink')
        self.os.symlink(base_path, symlink_path)
        file_path = self.os.path.join(base_path, 'slink', 'beta')
        self.createFile(file_path)
        link_path = self.os.path.join(base_path, 'slink', 'gamma')
        self.os.link(file_path, link_path)
        self.assertTrue(self.os.path.exists(link_path))

    @unittest.skipIf(sys.version_info < (3, 3), 'replace is new in Python 3.3')
    def testReplaceExistingDirectoryShouldRaiseUnderWindows(self):
        """Renaming to an existing directory raises OSError under Windows."""
        self.checkWindowsOnly()
        old_path = self.makePath('foo', 'bar')
        new_path = self.makePath('foo', 'baz')
        self.createDirectory(old_path)
        self.createDirectory(new_path)
        self.assertRaisesOSError(errno.EACCES, self.os.replace, old_path,
                                 new_path)

    def testRenameToExistingDirectoryUnderPosix(self):
        """Renaming to an existing directory changes the existing directory
        under Posix."""
        self.checkPosixOnly()
        old_path = self.makePath('foo', 'bar')
        new_path = self.makePath('xyzzy')
        self.createDirectory(self.os.path.join(old_path, 'sub'))
        self.createDirectory(new_path)
        self.os.rename(old_path, new_path)
        self.assertTrue(
            self.os.path.exists(self.os.path.join(new_path, 'sub')))
        self.assertFalse(self.os.path.exists(old_path))

    def testRenameFileToExistingDirectoryRaisesUnderPosix(self):
        self.checkPosixOnly()
        file_path = self.makePath('foo', 'bar', 'baz')
        new_path = self.makePath('xyzzy')
        self.createFile(file_path)
        self.createDirectory(new_path)
        self.assertRaisesOSError(errno.EISDIR, self.os.rename, file_path,
                                 new_path)

    def testRenameToExistingDirectoryUnderPosixRaisesIfNotEmpty(self):
        """Renaming to an existing directory changes the existing directory
        under Posix."""
        self.checkPosixOnly()
        old_path = self.makePath('foo', 'bar')
        new_path = self.makePath('foo', 'baz')
        self.createDirectory(self.os.path.join(old_path, 'sub'))
        self.createDirectory(self.os.path.join(new_path, 'sub'))
        
        # not testing specific subtype:
        # raises errno.ENOTEMPTY under Ubuntu 16.04, MacOS and pyfakefs
        # but raises errno.EEXIST at least under Ubunto 14.04
        self.assertRaises(OSError, self.os.rename, old_path, new_path)

    def testRenameToAnotherDeviceShouldRaise(self):
        """Renaming to another filesystem device raises OSError."""
        self.skipRealFs()
        self.filesystem.AddMountPoint('/mount')
        old_path = '/foo/bar'
        new_path = '/mount/bar'
        self.filesystem.CreateFile(old_path)
        self.assertRaisesOSError(errno.EXDEV, self.os.rename, old_path,
                                 new_path)

    def testRenameToExistentFilePosix(self):
        """Can rename a file to a used name under Unix."""
        self.checkPosixOnly()
        directory = self.makePath('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.createFile(old_file_path, contents='test contents 1')
        self.createFile(new_file_path, contents='test contents 2')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.os.rename(old_file_path, new_file_path)
        self.assertFalse(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.checkContents(new_file_path, 'test contents 1')

    def testRenameToExistentFileWindows(self):
        """Renaming a file to a used name raises OSError under Windows."""
        self.checkWindowsOnly()
        directory = self.makePath('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.createFile(old_file_path, contents='test contents 1')
        self.createFile(new_file_path, contents='test contents 2')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.assertRaisesOSError(errno.EEXIST, self.os.rename, old_file_path,
                                 new_file_path)

    @unittest.skipIf(sys.version_info < (3, 3), 'replace is new in Python 3.3')
    def testReplaceToExistentFile(self):
        """Replaces an existing file (does not work with `rename()` under
        Windows)."""
        directory = self.makePath('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.createFile(old_file_path, contents='test contents 1')
        self.createFile(new_file_path, contents='test contents 2')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.os.replace(old_file_path, new_file_path)
        self.assertFalse(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.checkContents(new_file_path, 'test contents 1')

    def testRenameToNonexistentDir(self):
        """Can rename a file to a name in a nonexistent dir."""
        directory = self.makePath('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(
            directory, 'no_such_path', 'plugh_new')
        self.createFile(old_file_path, contents='test contents')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertFalse(self.os.path.exists(new_file_path))
        self.assertRaisesOSError(errno.ENOENT, self.os.rename, old_file_path,
                                 new_file_path)
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertFalse(self.os.path.exists(new_file_path))
        self.checkContents(old_file_path, 'test contents')

    def testRenameNonexistentFileShouldRaiseError(self):
        """Can't rename a file that doesn't exist."""
        self.assertRaisesOSError(errno.ENOENT, self.os.rename,
                                 'nonexistent-foo', 'doesn\'t-matter-bar')

    def testRenameEmptyDir(self):
        """Test a rename of an empty directory."""
        directory = self.makePath('xyzzy')
        before_dir = self.os.path.join(directory, 'empty')
        after_dir = self.os.path.join(directory, 'unused')
        self.createDirectory(before_dir)
        self.assertTrue(
            self.os.path.exists(self.os.path.join(before_dir, '.')))
        self.assertFalse(self.os.path.exists(after_dir))
        self.os.rename(before_dir, after_dir)
        self.assertFalse(self.os.path.exists(before_dir))
        self.assertTrue(self.os.path.exists(self.os.path.join(after_dir, '.')))

    def testRenameSymlink(self):
        self.checkPosixOnly()
        base_path = self.makePath('foo', 'bar')
        self.createDirectory(base_path)
        link_path = self.os.path.join(base_path, 'link')
        self.os.symlink(base_path, link_path)
        file_path = self.os.path.join(link_path, 'file')
        new_file_path = self.os.path.join(link_path, 'new')
        self.createFile(file_path)
        self.os.rename(file_path, new_file_path)
        self.assertFalse(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.exists(new_file_path))

    def testRenameDir(self):
        """Test a rename of a directory."""
        directory = self.makePath('xyzzy')
        before_dir = self.os.path.join(directory, 'before')
        before_file = self.os.path.join(directory, 'before', 'file')
        after_dir = self.os.path.join(directory, 'after')
        after_file = self.os.path.join(directory, 'after', 'file')
        self.createDirectory(before_dir)
        self.createFile(before_file, contents='payload')
        self.assertTrue(self.os.path.exists(before_dir))
        self.assertTrue(self.os.path.exists(before_file))
        self.assertFalse(self.os.path.exists(after_dir))
        self.assertFalse(self.os.path.exists(after_file))
        self.os.rename(before_dir, after_dir)
        self.assertFalse(self.os.path.exists(before_dir))
        self.assertFalse(self.os.path.exists(before_file))
        self.assertTrue(self.os.path.exists(after_dir))
        self.assertTrue(self.os.path.exists(after_file))
        self.checkContents(after_file, 'payload')

    def testRenamePreservesStat(self):
        """Test if rename preserves mtime."""
        self.checkPosixOnly()
        self.skipRealFs()
        directory = self.makePath('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.createFile(old_file_path)
        old_file = self.filesystem.GetObject(old_file_path)
        old_file.SetMTime(old_file.st_mtime - 3600)
        self.os.chown(old_file_path, 200, 200)
        self.os.chmod(old_file_path, 0o222)
        self.createFile(new_file_path)
        new_file = self.filesystem.GetObject(new_file_path)
        self.assertNotEqual(new_file.st_mtime, old_file.st_mtime)
        self.os.rename(old_file_path, new_file_path)
        new_file = self.filesystem.GetObject(new_file_path)
        self.assertEqual(new_file.st_mtime, old_file.st_mtime)
        self.assertEqual(new_file.st_mode, old_file.st_mode)
        self.assertEqual(new_file.st_uid, old_file.st_uid)
        self.assertEqual(new_file.st_gid, old_file.st_gid)

    def testRenameSameFilenames(self):
        """Test renaming when old and new names are the same."""
        directory = self.makePath('xyzzy')
        file_contents = 'Spam eggs'
        file_path = self.os.path.join(directory, 'eggs')
        self.createFile(file_path, contents=file_contents)
        self.os.rename(file_path, file_path)
        self.checkContents(file_path, file_contents)

    def testRmdir(self):
        """Can remove a directory."""
        directory = self.makePath('xyzzy')
        sub_dir = self.makePath('xyzzy', 'abccd')
        other_dir = self.makePath('xyzzy', 'cdeed')
        self.createDirectory(directory)
        self.assertTrue(self.os.path.exists(directory))
        self.os.rmdir(directory)
        self.assertFalse(self.os.path.exists(directory))
        self.createDirectory(sub_dir)
        self.createDirectory(other_dir)
        self.os.chdir(sub_dir)
        self.os.rmdir('../cdeed')
        self.assertFalse(self.os.path.exists(other_dir))
        self.os.chdir('..')
        self.os.rmdir('abccd')
        self.assertFalse(self.os.path.exists(sub_dir))

    def testRmdirRaisesIfNotEmpty(self):
        """Raises an exception if the target directory is not empty."""
        directory = self.makePath('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.createFile(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.assertRaisesOSError(errno.ENOTEMPTY, self.os.rmdir, directory)

    def checkRmdirRaisesIfNotDirectory(self, error_nr):
        """Raises an exception if the target is not a directory."""
        directory = self.makePath('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.createFile(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.assertRaisesOSError(self.not_dir_error(),
                                 self.os.rmdir, file_path)
        self.assertRaisesOSError(error_nr, self.os.rmdir, '.')

    def testRmdirRaisesIfNotDirectoryPosix(self):
        self.checkPosixOnly()
        self.checkRmdirRaisesIfNotDirectory(errno.EINVAL)

    def testRmdirRaisesIfNotDirectoryWindows(self):
        self.checkWindowsOnly()
        self.checkRmdirRaisesIfNotDirectory(errno.EACCES)

    def testRmdirRaisesIfNotExist(self):
        """Raises an exception if the target does not exist."""
        directory = self.makePath('xyzzy')
        self.assertFalse(self.os.path.exists(directory))
        self.assertRaisesOSError(errno.ENOENT, self.os.rmdir, directory)

    def testRmdirViaSymlink(self):
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        base_path = self.makePath('foo', 'bar')
        dir_path = self.os.path.join(base_path, 'alpha')
        self.createDirectory(dir_path)
        link_path = self.os.path.join(base_path, 'beta')
        self.os.symlink(base_path, link_path)
        self.os.rmdir(link_path + '/alpha')
        self.assertFalse(self.os.path.exists(dir_path))

    def RemovedirsCheck(self, directory):
        self.assertTrue(self.os.path.exists(directory))
        self.os.removedirs(directory)
        return not self.os.path.exists(directory)

    def testRemovedirs(self):
        # no exception raised
        self.skipRealFs()
        data = ['test1', ('test1', 'test2'), ('test1', 'extra'),
                ('test1', 'test2', 'test3')]
        for directory in data:
            self.createDirectory(self.makePath(directory))
            self.assertTrue(self.os.path.exists(self.makePath(directory)))
        self.assertRaisesOSError(errno.ENOTEMPTY, self.RemovedirsCheck,
                                 self.makePath(data[0]))
        self.assertRaisesOSError(errno.ENOTEMPTY, self.RemovedirsCheck,
                                 self.makePath(data[1]))

        self.assertTrue(self.RemovedirsCheck(self.makePath(data[3])))
        self.assertTrue(self.os.path.exists(self.makePath(data[0])))
        self.assertFalse(self.os.path.exists(self.makePath(data[1])))
        self.assertTrue(self.os.path.exists(self.makePath(data[2])))

        # Should raise because '/test1/extra' is all that is left, and
        # removedirs('/test1/extra') will eventually try to rmdir('/').
        self.assertRaisesOSError(errno.EBUSY, self.RemovedirsCheck,
                                 self.makePath(data[2]))

        # However, it will still delete '/test1') in the process.
        self.assertFalse(self.os.path.exists(self.makePath(data[0])))

        self.createDirectory(self.makePath('test1', 'test2'))
        # Add this to the root directory to avoid raising an exception.
        self.filesystem.CreateDirectory(self.makePath('test3'))
        self.assertTrue(self.RemovedirsCheck(self.makePath('test1', 'test2')))
        self.assertFalse(self.os.path.exists(self.makePath('test1', 'test2')))
        self.assertFalse(self.os.path.exists(self.makePath('test1')))

    def testRemovedirsRaisesIfRemovingRoot(self):
        """Raises exception if asked to remove '/'."""
        self.skipRealFs()
        self.os.rmdir(self.base_path)
        directory = self.os.path.sep
        self.assertTrue(self.os.path.exists(directory))
        self.assertRaisesOSError(errno.EBUSY, self.os.removedirs, directory)

    def testRemovedirsRaisesIfCascadeRemovingRoot(self):
        """Raises exception if asked to remove '/' as part of a
        larger operation.

        All of other directories should still be removed, though.
        """
        self.skipRealFs()
        directory = self.makePath('foo', 'bar')
        self.createDirectory(directory)
        self.assertTrue(self.os.path.exists(directory))
        self.assertRaisesOSError(errno.EBUSY, self.os.removedirs, directory)
        head, unused_tail = self.os.path.split(directory)
        while head != self.os.path.sep:
            self.assertFalse(self.os.path.exists(directory))
            head, unused_tail = self.os.path.split(head)

    def testRemovedirsWithTrailingSlash(self):
        """removedirs works on directory names with trailing slashes."""
        # separate this case from the removing-root-directory case
        self.createDirectory(self.makePath('baz'))
        directory = self.makePath('foo', 'bar')
        self.createDirectory(directory)
        self.assertTrue(self.os.path.exists(directory))
        self.os.removedirs(directory)
        self.assertFalse(self.os.path.exists(directory))

    def testRemoveDirsWithTopSymlinkFails(self):
        self.checkPosixOnly()
        dir_path = self.makePath('dir')
        dir_link = self.makePath('dir_link')
        self.createDirectory(dir_path)
        self.os.symlink(dir_path, dir_link)
        self.assertRaisesOSError(errno.ENOTDIR, self.os.removedirs, dir_link)

    def testRemoveDirsWithNonTopSymlinkSucceeds(self):
        self.checkPosixOnly()
        dir_path = self.makePath('dir')
        dir_link = self.makePath('dir_link')
        self.createDirectory(dir_path)
        self.os.symlink(dir_path, dir_link)
        dir_in_dir = self.os.path.join(dir_link, 'dir2')
        self.createDirectory(dir_in_dir)
        self.os.removedirs(dir_in_dir)
        self.assertFalse(self.os.path.exists(dir_in_dir))
        # ensure that the symlink is not removed
        self.assertTrue(self.os.path.exists(dir_link))

    def testMkdir(self):
        """mkdir can create a relative directory."""
        self.skipRealFs()
        directory = 'xyzzy'
        self.assertFalse(self.filesystem.Exists(directory))
        self.os.mkdir(directory)
        self.assertTrue(self.filesystem.Exists('/%s' % directory))
        self.os.chdir(directory)
        self.os.mkdir(directory)
        self.assertTrue(
            self.filesystem.Exists('/%s/%s' % (directory, directory)))
        self.os.chdir(directory)
        self.os.mkdir('../abccb')
        self.assertTrue(self.os.path.exists('/%s/abccb' % directory))

    def testMkdirWithTrailingSlash(self):
        """mkdir can create a directory named with a trailing slash."""
        directory = self.makePath('foo')
        self.assertFalse(self.os.path.exists(directory))
        self.os.mkdir(directory)
        self.assertTrue(self.os.path.exists(directory))
        self.assertTrue(self.os.path.exists(self.makePath('foo')))

    def testMkdirRaisesIfEmptyDirectoryName(self):
        """mkdir raises exeption if creating directory named ''."""
        directory = ''
        self.assertRaisesOSError(errno.ENOENT, self.os.mkdir, directory)

    def testMkdirRaisesIfNoParent(self):
        """mkdir raises exception if parent directory does not exist."""
        parent = 'xyzzy'
        directory = '%s/foo' % (parent,)
        self.assertFalse(self.os.path.exists(parent))
        self.assertRaisesOSError(errno.ENOENT, self.os.mkdir, directory)

    def testMkdirRaisesOnSymlinkInPosix(self):
        self.checkPosixOnly()
        base_path = self.makePath('foo', 'bar')
        link_path = self.os.path.join(base_path, 'link_to_dir')
        dir_path = self.os.path.join(base_path, 'dir')
        self.createDirectory(dir_path)
        self.os.symlink(dir_path, link_path)
        self.assertRaisesOSError(errno.ENOTDIR, self.os.rmdir, link_path)

    def testMkdirRemovesSymlinkInWindows(self):
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        base_path = self.makePath('foo', 'bar')
        link_path = self.os.path.join(base_path, 'link_to_dir')
        dir_path = self.os.path.join(base_path, 'dir')
        self.createDirectory(dir_path)
        self.os.symlink(dir_path, link_path)
        self.os.rmdir(link_path)
        self.assertFalse(self.os.path.exists(link_path))
        self.assertTrue(self.os.path.exists(dir_path))

    def testMkdirRaisesIfDirectoryExists(self):
        """mkdir raises exception if directory already exists."""
        directory = self.makePath('xyzzy')
        self.createDirectory(directory)
        self.assertTrue(self.os.path.exists(directory))
        self.assertRaisesOSError(errno.EEXIST, self.os.mkdir, directory)

    def testMkdirRaisesIfFileExists(self):
        """mkdir raises exception if name already exists as a file."""
        directory = self.makePath('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.createFile(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.assertRaisesOSError(errno.EEXIST, self.os.mkdir, file_path)

    def checkMkdirRaisesIfParentIsFile(self, error_type):
        """mkdir raises exception if name already exists as a file."""
        directory = self.makePath('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.createFile(file_path)
        self.assertRaisesOSError(error_type, self.os.mkdir,
                                 self.os.path.join(file_path, 'ff'))

    def testMkdirRaisesIfParentIsFilePosix(self):
        self.checkPosixOnly()
        self.checkMkdirRaisesIfParentIsFile(errno.ENOTDIR)

    def testMkdirRaisesIfParentIsFileWindows(self):
        self.checkWindowsOnly()
        self.checkMkdirRaisesIfParentIsFile(errno.ENOENT)

    def testMkdirRaisesWithSlashDotPosix(self):
        """mkdir raises exception if mkdir foo/. (trailing /.)."""
        self.checkPosixOnly()
        self.assertRaisesOSError(errno.EEXIST,
                                 self.os.mkdir, self.os.sep + '.')
        directory = self.makePath('xyzzy', '.')
        self.assertRaisesOSError(errno.ENOENT, self.os.mkdir, directory)
        self.createDirectory(self.makePath('xyzzy'))
        self.assertRaisesOSError(errno.EEXIST, self.os.mkdir, directory)

    def testMkdirRaisesWithSlashDotWindows(self):
        """mkdir raises exception if mkdir foo/. (trailing /.)."""
        self.checkWindowsOnly()
        self.assertRaisesOSError(errno.EACCES,
                                 self.os.mkdir, self.os.sep + '.')
        directory = self.makePath('xyzzy', '.')
        self.os.mkdir(directory)
        self.createDirectory(self.makePath('xyzzy'))
        self.assertRaisesOSError(errno.EEXIST, self.os.mkdir, directory)

    def testMkdirRaisesWithDoubleDotsPosix(self):
        """mkdir raises exception if mkdir foo/foo2/../foo3."""
        self.checkPosixOnly()
        self.assertRaisesOSError(errno.EEXIST,
                                 self.os.mkdir, self.os.sep + '..')
        directory = self.makePath('xyzzy', 'dir1', 'dir2', '..', '..', 'dir3')
        self.assertRaisesOSError(errno.ENOENT, self.os.mkdir, directory)
        self.createDirectory(self.makePath('xyzzy'))
        self.assertRaisesOSError(errno.ENOENT, self.os.mkdir, directory)
        self.createDirectory(self.makePath('xyzzy', 'dir1'))
        self.assertRaisesOSError(errno.ENOENT, self.os.mkdir, directory)
        self.createDirectory(self.makePath('xyzzy', 'dir1', 'dir2'))
        self.os.mkdir(directory)
        self.assertTrue(self.os.path.exists(directory))
        directory = self.makePath('xyzzy', 'dir1', '..')
        self.assertRaisesOSError(errno.EEXIST, self.os.mkdir, directory)

    def testMkdirRaisesWithDoubleDotsWindows(self):
        """mkdir raises exception if mkdir foo/foo2/../foo3."""
        self.checkWindowsOnly()
        self.assertRaisesOSError(errno.EACCES,
                                 self.os.mkdir, self.os.sep + '..')
        directory = self.makePath(
            'xyzzy', 'dir1', 'dir2', '..', '..', 'dir3')
        self.assertRaisesOSError(errno.ENOENT, self.os.mkdir, directory)
        self.createDirectory(self.makePath('xyzzy'))
        self.os.mkdir(directory)
        self.assertTrue(self.os.path.exists(directory))
        directory = self.makePath('xyzzy', 'dir1', '..')
        self.assertRaisesOSError(errno.EEXIST, self.os.mkdir, directory)

    def testMkdirRaisesIfParentIsReadOnly(self):
        """mkdir raises exception if parent is read only."""
        self.checkPosixOnly()
        directory = self.makePath('a')
        self.os.mkdir(directory)

        # Change directory permissions to be read only.
        self.os.chmod(directory, 0o400)

        directory = self.makePath('a', 'b')
        self.assertRaisesOSError(errno.EACCES, self.os.mkdir, directory)

    def testMkdirWithWithSymlinkParent(self):
        self.checkPosixOnly()
        dir_path = self.makePath('foo', 'bar')
        self.createDirectory(dir_path)
        link_path = self.makePath('foo', 'link')
        self.os.symlink(dir_path, link_path)
        new_dir = self.os.path.join(link_path, 'new_dir')
        self.os.mkdir(new_dir)
        self.assertTrue(self.os.path.exists(new_dir))

    def testMakedirs(self):
        """makedirs can create a directory even if parent does not exist."""
        parent = self.makePath('xyzzy')
        directory = self.os.path.join(parent, 'foo')
        self.assertFalse(self.os.path.exists(parent))
        self.os.makedirs(directory)
        self.assertTrue(self.os.path.exists(directory))

    def checkMakedirsRaisesIfParentIsFile(self, error_type):
        """makedirs raises exception if a parent component exists as a file."""
        file_path = self.makePath('xyzzy')
        directory = self.os.path.join(file_path, 'plugh')
        self.createFile(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.assertRaisesOSError(error_type, self.os.makedirs, directory)

    def testMakedirsRaisesIfParentIsFilePosix(self):
        self.checkPosixOnly()
        self.checkMakedirsRaisesIfParentIsFile(errno.ENOTDIR)

    def testMakedirsRaisesIfParentIsFileWindows(self):
        self.checkWindowsOnly()
        self.checkMakedirsRaisesIfParentIsFile(errno.ENOENT)

    def testMakedirsRaisesIfParentIsBrokenLink(self):
        self.checkPosixOnly()
        link_path = self.makePath('broken_link')
        self.os.symlink(self.makePath('bogus'), link_path)
        self.assertRaisesOSError(errno.ENOENT, self.os.makedirs,
                                 self.os.path.join(link_path, 'newdir'))

    def testMakedirsRaisesIfParentIsLoopingLink(self):
        self.skipIfSymlinkNotSupported()
        link_path = self.makePath('link')
        link_target = self.os.path.join(link_path, 'link')
        self.os.symlink(link_target, link_path)
        self.assertRaisesOSError(errno.EEXIST, self.os.makedirs, link_path)

    def testMakedirsIfParentIsSymlink(self):
        self.checkPosixOnly()
        base_dir = self.makePath('foo', 'bar')
        self.createDirectory(base_dir)
        link_dir = self.os.path.join(base_dir, 'linked')
        self.os.symlink(base_dir, link_dir)
        new_dir = self.os.path.join(link_dir, 'f')
        self.os.makedirs(new_dir)
        self.assertTrue(self.os.path.exists(new_dir))

    def testMakedirsRaisesIfAccessDenied(self):
        """makedirs raises exception if access denied."""
        self.checkPosixOnly()
        directory = self.makePath('a')
        self.os.mkdir(directory)

        # Change directory permissions to be read only.
        self.os.chmod(directory, 0o400)

        directory = self.makePath('a', 'b')
        self.assertRaises(Exception, self.os.makedirs, directory)

    @unittest.skipIf(sys.version_info < (3, 2),
                     'os.makedirs(exist_ok) argument new in version 3.2')
    def testMakedirsExistOk(self):
        """makedirs uses the exist_ok argument"""
        directory = self.makePath('xyzzy', 'foo')
        self.createDirectory(directory)
        self.assertTrue(self.os.path.exists(directory))

        self.assertRaisesOSError(errno.EEXIST, self.os.makedirs, directory)
        self.os.makedirs(directory, exist_ok=True)
        self.assertTrue(self.os.path.exists(directory))

    # test fsync and fdatasync

    def testFsyncRaisesOnNonInt(self):
        self.assertRaises(TypeError, self.os.fsync, "zero")

    def testFdatasyncRaisesOnNonInt(self):
        self.checkLinuxOnly()
        self.assertRaises(TypeError, self.os.fdatasync, "zero")

    def testFsyncRaisesOnInvalidFd(self):
        self.assertRaisesOSError(errno.EBADF, self.os.fsync, 100)

    def testFdatasyncRaisesOnInvalidFd(self):
        # No open files yet
        self.checkLinuxOnly()
        self.assertRaisesOSError(errno.EINVAL, self.os.fdatasync, 0)
        self.assertRaisesOSError(errno.EBADF, self.os.fdatasync, 100)

    def testFsyncPassPosix(self):
        self.checkPosixOnly()
        test_file_path = self.makePath('test_file')
        self.createFile(test_file_path, contents='dummy file contents')
        with self.open(test_file_path, 'r') as test_file:
            test_fd = test_file.fileno()
            # Test that this doesn't raise anything
            self.os.fsync(test_fd)
            # And just for sanity, double-check that this still raises
            self.assertRaisesOSError(errno.EBADF, self.os.fsync, test_fd + 1)

    def testFsyncPassWindows(self):
        self.checkWindowsOnly()
        test_file_path = self.makePath('test_file')
        self.createFile(test_file_path, contents='dummy file contents')
        with self.open(test_file_path, 'r+') as test_file:
            test_fd = test_file.fileno()
            # Test that this doesn't raise anything
            self.os.fsync(test_fd)
            # And just for sanity, double-check that this still raises
            self.assertRaisesOSError(errno.EBADF, self.os.fsync, test_fd + 1)
        with self.open(test_file_path, 'r') as test_file:
            test_fd = test_file.fileno()
            self.assertRaisesOSError(errno.EBADF, self.os.fsync, test_fd)

    def testFdatasyncPass(self):
        # setup
        self.checkLinuxOnly()
        test_file_path = self.makePath('test_file')
        self.createFile(test_file_path, contents='dummy file contents')
        test_file = self.open(test_file_path, 'r')
        test_fd = test_file.fileno()
        # Test that this doesn't raise anything
        self.os.fdatasync(test_fd)
        # And just for sanity, double-check that this still raises
        self.assertRaisesOSError(errno.EBADF, self.os.fdatasync, test_fd + 1)

    def testAccess700(self):
        # set up
        self.checkPosixOnly()
        path = self.makePath('some_file')
        self.createTestFile(path)
        self.os.chmod(path, 0o700)
        self.assertModeEqual(0o700, self.os.stat(path).st_mode)
        # actual tests
        self.assertTrue(self.os.access(path, self.os.F_OK))
        self.assertTrue(self.os.access(path, self.os.R_OK))
        self.assertTrue(self.os.access(path, self.os.W_OK))
        self.assertTrue(self.os.access(path, self.os.X_OK))
        self.assertTrue(self.os.access(path, self.rwx))

    def testAccess600(self):
        # set up
        self.checkPosixOnly()
        path = self.makePath('some_file')
        self.createTestFile(path)
        self.os.chmod(path, 0o600)
        self.assertModeEqual(0o600, self.os.stat(path).st_mode)
        # actual tests
        self.assertTrue(self.os.access(path, self.os.F_OK))
        self.assertTrue(self.os.access(path, self.os.R_OK))
        self.assertTrue(self.os.access(path, self.os.W_OK))
        self.assertFalse(self.os.access(path, self.os.X_OK))
        self.assertFalse(self.os.access(path, self.rwx))
        self.assertTrue(self.os.access(path, self.rw))

    def testAccess400(self):
        # set up
        self.checkPosixOnly()
        path = self.makePath('some_file')
        self.createTestFile(path)
        self.os.chmod(path, 0o400)
        self.assertModeEqual(0o400, self.os.stat(path).st_mode)
        # actual tests
        self.assertTrue(self.os.access(path, self.os.F_OK))
        self.assertTrue(self.os.access(path, self.os.R_OK))
        self.assertFalse(self.os.access(path, self.os.W_OK))
        self.assertFalse(self.os.access(path, self.os.X_OK))
        self.assertFalse(self.os.access(path, self.rwx))
        self.assertFalse(self.os.access(path, self.rw))

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def testAccessSymlink(self):
        self.skipIfSymlinkNotSupported()
        self.skipRealFs()
        path = self.makePath('some_file')
        self.createTestFile(path)
        link_path = self.makePath('link_to_some_file')
        self.createLink(link_path, path)
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

    def testAccessNonExistentFile(self):
        # set up
        path = self.makePath('non', 'existent', 'file')
        self.assertFalse(self.os.path.exists(path))
        # actual tests
        self.assertFalse(self.os.access(path, self.os.F_OK))
        self.assertFalse(self.os.access(path, self.os.R_OK))
        self.assertFalse(self.os.access(path, self.os.W_OK))
        self.assertFalse(self.os.access(path, self.os.X_OK))
        self.assertFalse(self.os.access(path, self.rwx))
        self.assertFalse(self.os.access(path, self.rw))

    def testChmod(self):
        # set up
        self.checkPosixOnly()
        self.skipRealFs()
        path = self.makePath('some_file')
        self.createTestFile(path)
        # actual tests
        self.os.chmod(path, 0o6543)
        st = self.os.stat(path)
        self.assertModeEqual(0o6543, st.st_mode)
        self.assertTrue(st.st_mode & stat.S_IFREG)
        self.assertFalse(st.st_mode & stat.S_IFDIR)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'file descriptor as path new in Python 3.3')
    def testChmodUsesOpenFdAsPath(self):
        self.checkPosixOnly()
        self.skipRealFs()
        self.assertRaisesOSError(errno.EBADF, self.os.chmod, 5, 0o6543)
        path = self.makePath('some_file')
        self.createTestFile(path)

        with self.open(path) as f:
            self.os.chmod(f.filedes, 0o6543)
            st = self.os.stat(path)
            self.assertModeEqual(0o6543, st.st_mode)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def testChmodFollowSymlink(self):
        self.checkPosixOnly()
        if self.useRealFs() and not 'chmod' in os.supports_follow_symlinks:
            raise unittest.SkipTest('follow_symlinks not available')
        path = self.makePath('some_file')
        self.createTestFile(path)
        link_path = self.makePath('link_to_some_file')
        self.createLink(link_path, path)
        self.os.chmod(link_path, 0o6543)

        st = self.os.stat(link_path)
        self.assertModeEqual(0o6543, st.st_mode)
        st = self.os.stat(link_path, follow_symlinks=False)
        self.assertModeEqual(0o777, st.st_mode)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def testChmodNoFollowSymlink(self):
        self.checkPosixOnly()
        if self.useRealFs() and not 'chmod' in os.supports_follow_symlinks:
            raise unittest.SkipTest('follow_symlinks not available')
        path = self.makePath('some_file')
        self.createTestFile(path)
        link_path = self.makePath('link_to_some_file')
        self.createLink(link_path, path)
        self.os.chmod(link_path, 0o6543, follow_symlinks=False)

        st = self.os.stat(link_path)
        self.assertModeEqual(0o666, st.st_mode)
        st = self.os.stat(link_path, follow_symlinks=False)
        self.assertModeEqual(0o6543, st.st_mode)

    def testLchmod(self):
        """lchmod shall behave like chmod with follow_symlinks=True
        since Python 3.3"""
        self.checkPosixOnly()
        self.skipRealFs()
        path = self.makePath('some_file')
        self.createTestFile(path)
        link_path = self.makePath('link_to_some_file')
        self.createLink(link_path, path)
        self.os.lchmod(link_path, 0o6543)

        st = self.os.stat(link_path)
        self.assertModeEqual(0o666, st.st_mode)
        st = self.os.lstat(link_path)
        self.assertModeEqual(0o6543, st.st_mode)

    def testChmodDir(self):
        # set up
        self.checkPosixOnly()
        self.skipRealFs()
        path = self.makePath('some_dir')
        self.createTestDirectory(path)
        # actual tests
        self.os.chmod(path, 0o1234)
        st = self.os.stat(path)
        self.assertModeEqual(0o1234, st.st_mode)
        self.assertFalse(st.st_mode & stat.S_IFREG)
        self.assertTrue(st.st_mode & stat.S_IFDIR)

    def testChmodNonExistent(self):
        # set up
        path = self.makePath('non', 'existent', 'file')
        self.assertFalse(self.os.path.exists(path))
        # actual tests
        try:
            # Use try-catch to check exception attributes.
            self.os.chmod(path, 0o777)
            self.fail('Exception is expected.')  # COV_NF_LINE
        except OSError as os_error:
            self.assertEqual(errno.ENOENT, os_error.errno)
            self.assertEqual(path, os_error.filename)

    def testChownExistingFile(self):
        # set up
        self.skipRealFs()
        file_path = self.makePath('some_file')
        self.createFile(file_path)
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
    def testChownUsesOpenFdAsPath(self):
        self.checkPosixOnly()
        self.skipRealFs()
        self.assertRaisesOSError(errno.EBADF, self.os.chown, 5, 100, 101)
        file_path = self.makePath('foo', 'bar')
        self.createFile(file_path)

        with self.open(file_path) as f:
            self.os.chown(f.filedes, 100, 101)
            st = self.os.stat(file_path)
            self.assertEqual(st[stat.ST_UID], 100)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def testChownFollowSymlink(self):
        self.skipRealFs()
        file_path = self.makePath('some_file')
        self.createFile(file_path)
        link_path = self.makePath('link_to_some_file')
        self.createLink(link_path, file_path)

        self.os.chown(link_path, 100, 101)
        st = self.os.stat(link_path)
        self.assertEqual(st[stat.ST_UID], 100)
        self.assertEqual(st[stat.ST_GID], 101)
        st = self.os.stat(link_path, follow_symlinks=False)
        self.assertNotEqual(st[stat.ST_UID], 100)
        self.assertNotEqual(st[stat.ST_GID], 101)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def testChownNoFollowSymlink(self):
        self.skipRealFs()
        file_path = self.makePath('some_file')
        self.createFile(file_path)
        link_path = self.makePath('link_to_some_file')
        self.createLink(link_path, file_path)

        self.os.chown(link_path, 100, 101, follow_symlinks=False)
        st = self.os.stat(link_path)
        self.assertNotEqual(st[stat.ST_UID], 100)
        self.assertNotEqual(st[stat.ST_GID], 101)
        st = self.os.stat(link_path, follow_symlinks=False)
        self.assertEqual(st[stat.ST_UID], 100)
        self.assertEqual(st[stat.ST_GID], 101)

    def testChownBadArguments(self):
        """os.chown() with bad args (Issue #30)"""
        self.checkPosixOnly()
        file_path = self.makePath('some_file')
        self.createFile(file_path)
        self.assertRaises(TypeError, self.os.chown, file_path, 'username', -1)
        self.assertRaises(TypeError, self.os.chown, file_path, -1, 'groupname')

    def testChownNonexistingFileShouldRaiseOsError(self):
        self.checkPosixOnly()
        file_path = self.makePath('some_file')
        self.assertFalse(self.os.path.exists(file_path))
        self.assertRaisesOSError(errno.ENOENT, self.os.chown, file_path, 100,
                                 100)

    def testClassifyDirectoryContents(self):
        """Directory classification should work correctly."""
        root_directory = self.makePath('foo')
        test_directories = ['bar1', 'baz2']
        test_files = ['baz1', 'bar2', 'baz3']
        self.createDirectory(root_directory)
        for directory in test_directories:
            directory = self.os.path.join(root_directory, directory)
            self.createDirectory(directory)
        for test_file in test_files:
            test_file = self.os.path.join(root_directory, test_file)
            self.createFile(test_file)

        test_directories.sort()
        test_files.sort()
        generator = self.os.walk(root_directory)
        root, dirs, files = next(generator)
        dirs.sort()
        files.sort()
        self.assertEqual(root_directory, root)
        self.assertEqual(test_directories, dirs)
        self.assertEqual(test_files, files)

    def testClassifyDoesNotHideExceptions(self):
        """_ClassifyDirectoryContents should not hide exceptions."""
        self.skipRealFs()
        directory = self.makePath('foo')
        self.assertEqual(False, self.os.path.exists(directory))
        self.assertRaisesOSError(errno.ENOENT,
                                 self.os._ClassifyDirectoryContents, directory)

    # os.mknod does not work under MacOS due to permission issues
    # so we test it under Linux only

    def testMkNodCanCreateAFile(self):
        self.checkLinuxOnly()
        filename = self.makePath('foo')
        self.assertFalse(self.os.path.exists(filename))
        self.os.mknod(filename)
        self.assertTrue(self.os.path.exists(filename))
        self.assertEqual(stat.S_IFREG | 0o600, self.os.stat(filename).st_mode)

    def testMkNodRaisesIfEmptyFileName(self):
        self.checkLinuxOnly()
        filename = ''
        self.assertRaisesOSError(errno.ENOENT, self.os.mknod, filename)

    def testMkNodRaisesIfParentDirDoesntExist(self):
        self.checkLinuxOnly()
        parent = self.makePath('xyzzy')
        filename = self.os.path.join(parent, 'foo')
        self.assertFalse(self.os.path.exists(parent))
        self.assertRaisesOSError(errno.ENOENT, self.os.mknod, filename)

    def testMkNodRaisesIfFileExists(self):
        self.checkLinuxOnly()
        filename = self.makePath('tmp', 'foo')
        self.createFile(filename)
        self.assertTrue(self.os.path.exists(filename))
        self.assertRaisesOSError(errno.EEXIST, self.os.mknod, filename)

    def testMkNodRaisesIfFilenameIsDot(self):
        self.checkLinuxOnly()
        filename = self.makePath('tmp', '.')
        self.assertRaisesOSError(errno.ENOENT, self.os.mknod, filename)

    def testMkNodRaisesIfFilenameIsDoubleDot(self):
        self.checkLinuxOnly()
        filename = self.makePath('tmp', '..')
        self.assertRaisesOSError(errno.ENOENT, self.os.mknod, filename)

    def testMknodEmptyTailForExistingFileRaises(self):
        self.checkLinuxOnly()
        filename = self.makePath('foo')
        self.createFile(filename)
        self.assertTrue(self.os.path.exists(filename))
        self.assertRaisesOSError(errno.EEXIST, self.os.mknod, filename)

    def testMknodEmptyTailForNonexistentFileRaises(self):
        self.checkLinuxOnly()
        filename = self.makePath('tmp', 'foo')
        self.assertRaisesOSError(errno.ENOENT, self.os.mknod, filename)

    def testMknodRaisesIfFilenameIsEmptyString(self):
        self.checkLinuxOnly()
        filename = ''
        self.assertRaisesOSError(errno.ENOENT, self.os.mknod, filename)

    def testMknodRaisesIfUnsupportedOptions(self):
        self.checkPosixOnly()
        filename = 'abcde'
        self.assertRaisesOSError(errno.EPERM, self.os.mknod, filename,
                                 stat.S_IFCHR)

    def testMknodRaisesIfParentIsNotADirectory(self):
        self.checkLinuxOnly()
        filename1 = self.makePath('foo')
        self.createFile(filename1)
        self.assertTrue(self.os.path.exists(filename1))
        filename2 = self.makePath('foo', 'bar')
        self.assertRaisesOSError(errno.ENOTDIR, self.os.mknod, filename2)

    def testSymlink(self):
        self.skipIfSymlinkNotSupported()
        file_path = self.makePath('foo', 'bar', 'baz')
        self.createDirectory(self.makePath('foo', 'bar'))
        self.os.symlink('bogus', file_path)
        self.assertTrue(self.os.path.lexists(file_path))
        self.assertFalse(self.os.path.exists(file_path))
        self.createFile(self.makePath('foo', 'bar', 'bogus'))
        self.assertTrue(self.os.path.lexists(file_path))
        self.assertTrue(self.os.path.exists(file_path))

    def testSymlinkOnNonexistingPathRaises(self):
        self.checkPosixOnly()
        dir_path = self.makePath('bar')
        link_path = self.os.path.join(dir_path, 'bar')
        self.assertRaisesOSError(errno.ENOENT, self.os.symlink, link_path,
                                 link_path)
        self.assertRaisesOSError(errno.ENOENT, self.os.symlink, dir_path,
                                 link_path)

    def testSymlinkWithPathEndingWithSepInPosix(self):
        self.checkPosixOnly()
        dirPath = self.makePath('dir')
        self.createDirectory(dirPath)
        self.assertRaisesOSError(errno.EEXIST, self.os.symlink,
                                 self.base_path, dirPath + self.os.sep)

        dirPath = self.makePath('bar')
        self.assertRaisesOSError(errno.ENOENT, self.os.symlink,
                                 self.base_path, dirPath + self.os.sep)

    def testSymlinkWithPathEndingWithSepInWindows(self):
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        dirPath = self.makePath('dir')
        self.createDirectory(dirPath)
        self.assertRaisesOSError(errno.EEXIST, self.os.symlink,
                                 self.base_path, dirPath + self.os.sep)

        dirPath = self.makePath('bar')
        # does not raise under Windows
        self.os.symlink(self.base_path, dirPath + self.os.sep)


    # hard link related tests

    def testLinkBogus(self):
        # trying to create a link from a non-existent file should fail
        self.skipIfSymlinkNotSupported()
        self.assertRaisesOSError(errno.ENOENT,
                                 self.os.link, '/nonexistent_source',
                                 '/link_dest')

    def testLinkDelete(self):
        self.skipIfSymlinkNotSupported()

        file1_path = self.makePath('test_file1')
        file2_path = self.makePath('test_file2')
        contents1 = 'abcdef'
        # Create file
        self.createFile(file1_path, contents=contents1)
        # link to second file
        self.os.link(file1_path, file2_path)
        # delete first file
        self.os.unlink(file1_path)
        # assert that second file exists, and its contents are the same
        self.assertTrue(self.os.path.exists(file2_path))
        with self.open(file2_path) as f:
            self.assertEqual(f.read(), contents1)

    def testLinkUpdate(self):
        self.skipIfSymlinkNotSupported()

        file1_path = self.makePath('test_file1')
        file2_path = self.makePath('test_file2')
        contents1 = 'abcdef'
        contents2 = 'ghijkl'
        # Create file and link
        self.createFile(file1_path, contents=contents1)
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

    def testLinkNonExistentParent(self):
        self.skipIfSymlinkNotSupported()
        file1_path = self.makePath('test_file1')
        breaking_link_path = self.makePath('nonexistent', 'test_file2')
        contents1 = 'abcdef'
        # Create file and link
        self.createFile(file1_path, contents=contents1)

        # trying to create a link under a non-existent directory should fail
        self.assertRaisesOSError(errno.ENOENT,
                                 self.os.link, file1_path, breaking_link_path)

    def testLinkIsExistingFile(self):
        self.skipIfSymlinkNotSupported()
        file_path = self.makePath('foo', 'bar')
        self.createFile(file_path)
        self.assertRaisesOSError(errno.EEXIST, self.os.link, file_path,
                                 file_path)

    def testLinkTargetIsDirWindows(self):
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        dir_path = self.makePath('foo', 'bar')
        link_path = self.os.path.join(dir_path, 'link')
        self.createDirectory(dir_path)
        self.assertRaisesOSError(errno.EACCES, self.os.link, dir_path,
                                 link_path)

    def testLinkTargetIsDirPosix(self):
        self.checkPosixOnly()
        dir_path = self.makePath('foo', 'bar')
        link_path = self.os.path.join(dir_path, 'link')
        self.createDirectory(dir_path)
        self.assertRaisesOSError(errno.EPERM, self.os.link, dir_path,
                                 link_path)

    def testLinkCount1(self):
        """Test that hard link counts are updated correctly."""
        self.skipIfSymlinkNotSupported()
        file1_path = self.makePath('test_file1')
        file2_path = self.makePath('test_file2')
        file3_path = self.makePath('test_file3')
        self.createFile(file1_path)
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

    def testNLinkForDirectories(self):
        self.skipRealFs()
        self.createDirectory(self.makePath('foo', 'bar'))
        self.createFile(self.makePath('foo', 'baz'))
        self.assertEqual(2, self.filesystem.GetObject(
            self.makePath('foo', 'bar')).st_nlink)
        self.assertEqual(4, self.filesystem.GetObject(
            self.makePath('foo')).st_nlink)
        self.createFile(self.makePath('foo', 'baz2'))
        self.assertEqual(5, self.filesystem.GetObject(
            self.makePath('foo')).st_nlink)

    def testUMask(self):
        self.checkPosixOnly()
        umask = os.umask(0o22)
        os.umask(umask)
        self.assertEqual(umask, self.os.umask(0o22))

    def testMkdirUmaskApplied(self):
        """mkdir creates a directory with umask applied."""
        self.checkPosixOnly()
        self.os.umask(0o22)
        dir1 = self.makePath('dir1')
        self.os.mkdir(dir1)
        self.assertModeEqual(0o755, self.os.stat(dir1).st_mode)
        self.os.umask(0o67)
        dir2 = self.makePath('dir2')
        self.os.mkdir(dir2)
        self.assertModeEqual(0o710, self.os.stat(dir2).st_mode)

    def testMakedirsUmaskApplied(self):
        """makedirs creates a directories with umask applied."""
        self.checkPosixOnly()
        self.os.umask(0o22)
        self.os.makedirs(self.makePath('p1', 'dir1'))
        self.assertModeEqual(0o755, self.os.stat(self.makePath('p1')).st_mode)
        self.assertModeEqual(0o755,
                             self.os.stat(self.makePath('p1', 'dir1')).st_mode)
        self.os.umask(0o67)
        self.os.makedirs(self.makePath('p2', 'dir2'))
        self.assertModeEqual(0o710, self.os.stat(self.makePath('p2')).st_mode)
        self.assertModeEqual(0o710,
                             self.os.stat(self.makePath('p2', 'dir2')).st_mode)

    def testMknodUmaskApplied(self):
        """mkdir creates a device with umask applied."""
        # skipping MacOs due to mknod permission issues
        self.checkLinuxOnly()
        self.os.umask(0o22)
        node1 = self.makePath('nod1')
        self.os.mknod(node1, stat.S_IFREG | 0o666)
        self.assertModeEqual(0o644, self.os.stat(node1).st_mode)
        self.os.umask(0o27)
        node2 = self.makePath('nod2')
        self.os.mknod(node2, stat.S_IFREG | 0o666)
        self.assertModeEqual(0o640, self.os.stat(node2).st_mode)

    def testOpenUmaskApplied(self):
        """open creates a file with umask applied."""
        self.checkPosixOnly()
        self.os.umask(0o22)
        file1 = self.makePath('file1')
        self.open(file1, 'w').close()
        self.assertModeEqual(0o644, self.os.stat(file1).st_mode)
        self.os.umask(0o27)
        file2 = self.makePath('file2')
        self.open(file2, 'w').close()
        self.assertModeEqual(0o640, self.os.stat(file2).st_mode)


class RealOsModuleTest(FakeOsModuleTest):
    def useRealFs(self):
        return True


class FakeOsModuleTestCaseInsensitiveFS(FakeOsModuleTestBase):
    def setUp(self):
        super(FakeOsModuleTestCaseInsensitiveFS, self).setUp()
        self.checkCaseInsensitiveFs()
        self.rwx = self.os.R_OK | self.os.W_OK | self.os.X_OK
        self.rw = self.os.R_OK | self.os.W_OK

    def testChdirFailsNonDirectory(self):
        """chdir should raise OSError if the target is not a directory."""
        filename = self.makePath('foo', 'bar')
        self.createFile(filename)
        filename1 = self.makePath('Foo', 'Bar')
        self.assertRaisesOSError(self.not_dir_error(), self.os.chdir, filename1)

    def testListdirReturnsList(self):
        directory_root = self.makePath('xyzzy')
        self.os.mkdir(directory_root)
        directory = self.os.path.join(directory_root, 'bug')
        self.os.mkdir(directory)
        directory_upper = self.makePath('XYZZY', 'BUG')
        self.createFile(self.makePath(directory, 'foo'))
        self.assertEqual(['foo'], self.os.listdir(directory_upper))

    def testListdirOnSymlink(self):
        self.skipIfSymlinkNotSupported()
        directory = self.makePath('xyzzy')
        files = ['foo', 'bar', 'baz']
        for f in files:
            self.createFile(self.makePath(directory, f))
        self.createLink(self.makePath('symlink'), self.makePath('xyzzy'))
        files.sort()
        self.assertEqual(files,
                         sorted(self.os.listdir(self.makePath('SymLink'))))

    def testFdopenMode(self):
        self.skipRealFs()
        file_path1 = self.makePath('some_file1')
        file_path2 = self.makePath('Some_File1')
        file_path3 = self.makePath('SOME_file1')
        self.createFile(file_path1, contents='contents here1')
        self.os.chmod(file_path2, (stat.S_IFREG | 0o666) ^ stat.S_IWRITE)

        fake_file1 = self.open(file_path3, 'r')
        fileno1 = fake_file1.fileno()
        self.os.fdopen(fileno1)
        self.os.fdopen(fileno1, 'r')
        exception = OSError if self.is_python2 else IOError
        self.assertRaises(exception, self.os.fdopen, fileno1, 'w')

    def testStat(self):
        directory = self.makePath('xyzzy')
        directory1 = self.makePath('XYZZY')
        file_path = self.os.path.join(directory, 'plugh')
        self.createFile(file_path, contents='ABCDE')
        self.assertTrue(stat.S_IFDIR & self.os.stat(directory1)[stat.ST_MODE])
        file_path1 = self.os.path.join(directory1, 'Plugh')
        self.assertTrue(stat.S_IFREG & self.os.stat(file_path1)[stat.ST_MODE])
        self.assertTrue(stat.S_IFREG & self.os.stat(file_path1).st_mode)
        self.assertEqual(5, self.os.stat(file_path1)[stat.ST_SIZE])

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def testStatNoFollowSymlinksPosix(self):
        """Test that stat with follow_symlinks=False behaves like lstat."""
        self.checkPosixOnly()
        directory = self.makePath('xyzzy')
        base_name = 'plugh'
        file_contents = 'frobozz'
        # Just make sure we didn't accidentally make our test data meaningless.
        self.assertNotEqual(len(base_name), len(file_contents))
        file_path = self.os.path.join(directory, base_name)
        link_path = self.os.path.join(directory, 'link')
        self.createFile(file_path, contents=file_contents)
        self.createLink(link_path, base_name)
        self.assertEqual(len(file_contents),
                         self.os.stat(file_path.upper(), follow_symlinks=False)[
                             stat.ST_SIZE])
        self.assertEqual(len(base_name),
                         self.os.stat(link_path.upper(), follow_symlinks=False)[
                             stat.ST_SIZE])

    def testLstatPosix(self):
        self.checkPosixOnly()
        directory = self.makePath('xyzzy')
        base_name = 'plugh'
        file_contents = 'frobozz'
        # Just make sure we didn't accidentally make our test data meaningless.
        self.assertNotEqual(len(base_name), len(file_contents))
        file_path = self.os.path.join(directory, base_name)
        link_path = self.os.path.join(directory, 'link')
        self.createFile(file_path, contents=file_contents)
        self.createLink(link_path, base_name)
        self.assertEqual(len(file_contents),
                         self.os.lstat(file_path.upper())[stat.ST_SIZE])
        self.assertEqual(len(base_name),
                         self.os.lstat(link_path.upper())[stat.ST_SIZE])

    def testReadlink(self):
        self.skipIfSymlinkNotSupported()
        link_path = self.makePath('foo', 'bar', 'baz')
        target = self.makePath('tarJAY')
        self.createLink(link_path, target)
        self.assertEqual(self.os.readlink(link_path.upper()), target)

    def checkReadlinkRaisesIfPathIsNotALink(self):
        file_path = self.makePath('foo', 'bar', 'eleventyone')
        self.createFile(file_path)
        self.assertRaisesOSError(errno.EINVAL,
                                 self.os.readlink, file_path.upper())

    def testReadlinkRaisesIfPathIsNotALinkWindows(self):
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        self.checkReadlinkRaisesIfPathIsNotALink()

    def testReadlinkRaisesIfPathIsNotALinkPosix(self):
        self.checkPosixOnly()
        self.checkReadlinkRaisesIfPathIsNotALink()

    def checkReadlinkRaisesIfPathHasFile(self, error_subtype):
        self.createFile(self.makePath('a_file'))
        file_path = self.makePath('a_file', 'foo')
        self.assertRaisesOSError(error_subtype,
                                 self.os.readlink, file_path.upper())
        file_path = self.makePath('a_file', 'foo', 'bar')
        self.assertRaisesOSError(error_subtype,
                                 self.os.readlink, file_path.upper())

    def testReadlinkRaisesIfPathHasFileWindows(self):
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        self.checkReadlinkRaisesIfPathHasFile(errno.ENOENT)

    def testReadlinkRaisesIfPathHasFilePosix(self):
        self.checkPosixOnly()
        self.checkReadlinkRaisesIfPathHasFile(errno.ENOTDIR)

    def testReadlinkWithLinksInPath(self):
        self.skipIfSymlinkNotSupported()
        self.createLink(self.makePath('meyer', 'lemon', 'pie'),
                        self.makePath('yum'))
        self.createLink(self.makePath('geo', 'metro'),
                        self.makePath('Meyer'))
        self.assertEqual(self.makePath('yum'),
                         self.os.readlink(
                             self.makePath('Geo', 'Metro', 'Lemon', 'Pie')))

    def testReadlinkWithChainedLinksInPath(self):
        self.skipIfSymlinkNotSupported()
        self.createLink(self.makePath(
            'eastern', 'european', 'wolfhounds', 'chase'),
            self.makePath('cats'))
        self.createLink(self.makePath('russian'),
                        self.makePath('Eastern', 'European'))
        self.createLink(self.makePath('dogs'),
                        self.makePath('Russian', 'Wolfhounds'))
        self.assertEqual(self.makePath('cats'),
                         self.os.readlink(self.makePath('DOGS', 'Chase')))

    def checkRemoveDir(self, dir_error):
        directory = self.makePath('xyzzy')
        dir_path = self.os.path.join(directory, 'plugh')
        self.createDirectory(dir_path)
        dir_path = dir_path.upper()
        self.assertTrue(self.os.path.exists(dir_path.upper()))
        self.assertRaisesOSError(dir_error, self.os.remove, dir_path)
        self.assertTrue(self.os.path.exists(dir_path))
        self.os.chdir(directory)
        self.assertRaisesOSError(dir_error, self.os.remove, dir_path)
        self.assertTrue(self.os.path.exists(dir_path))
        self.assertRaisesOSError(errno.ENOENT, self.os.remove, '/Plugh')

    def testRemoveDirMacOs(self):
        self.checkMacOsOnly()
        self.checkRemoveDir(errno.EPERM)

    def testRemoveDirWindows(self):
        self.checkWindowsOnly()
        self.checkRemoveDir(errno.EACCES)

    def testRemoveFile(self):
        directory = self.makePath('zzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.createFile(file_path)
        self.assertTrue(self.os.path.exists(file_path.upper()))
        self.os.remove(file_path.upper())
        self.assertFalse(self.os.path.exists(file_path))

    def testRemoveFileNoDirectory(self):
        directory = self.makePath('zzy')
        file_name = 'plugh'
        file_path = self.os.path.join(directory, file_name)
        self.createFile(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.os.chdir(directory.upper())
        self.os.remove(file_name.upper())
        self.assertFalse(self.os.path.exists(file_path))

    def testRemoveOpenFileFailsUnderWindows(self):
        self.checkWindowsOnly()
        path = self.makePath('foo', 'bar')
        self.createFile(path)
        with self.open(path, 'r'):
            self.assertRaisesOSError(errno.EACCES,
                                     self.os.remove, path.upper())
        self.assertTrue(self.os.path.exists(path))

    def testRemoveOpenFilePossibleUnderPosix(self):
        self.checkPosixOnly()
        path = self.makePath('foo', 'bar')
        self.createFile(path)
        self.open(path, 'r')
        self.os.remove(path.upper())
        self.assertFalse(self.os.path.exists(path))

    def testRemoveFileRelativePath(self):
        self.skipRealFs()
        original_dir = self.os.getcwd()
        directory = self.makePath('zzy')
        subdirectory = self.os.path.join(directory, 'zzy')
        file_name = 'plugh'
        file_path = self.os.path.join(directory, file_name)
        file_path_relative = self.os.path.join('..', file_name)
        self.createFile(file_path.upper())
        self.assertTrue(self.os.path.exists(file_path))
        self.createDirectory(subdirectory)
        self.assertTrue(self.os.path.exists(subdirectory))
        self.os.chdir(subdirectory.upper())
        self.os.remove(file_path_relative.upper())
        self.assertFalse(self.os.path.exists(file_path_relative))
        self.os.chdir(original_dir.upper())
        self.assertFalse(self.os.path.exists(file_path))

    def checkRemoveDirRaisesError(self, dir_error):
        directory = self.makePath('zzy')
        self.createDirectory(directory)
        self.assertRaisesOSError(dir_error,
                                 self.os.remove, directory.upper())

    def testRemoveDirRaisesErrorMacOs(self):
        self.checkMacOsOnly()
        self.checkRemoveDirRaisesError(errno.EPERM)

    def testRemoveDirRaisesErrorWindows(self):
        self.checkWindowsOnly()
        self.checkRemoveDirRaisesError(errno.EACCES)

    def testRemoveSymlinkToDir(self):
        self.skipIfSymlinkNotSupported()
        directory = self.makePath('zzy')
        link = self.makePath('link_to_dir')
        self.createDirectory(directory)
        self.os.symlink(directory, link)
        self.assertTrue(self.os.path.exists(directory))
        self.assertTrue(self.os.path.exists(link))
        self.os.remove(link.upper())
        self.assertTrue(self.os.path.exists(directory))
        self.assertFalse(self.os.path.exists(link))

    def testRenameDirToSymlinkPosix(self):
        self.checkPosixOnly()
        link_path = self.makePath('link')
        dir_path = self.makePath('dir')
        link_target = self.os.path.join(dir_path, 'link_target')
        self.createDirectory(dir_path)
        self.os.symlink(link_target.upper(), link_path.upper())
        self.assertRaisesOSError(errno.ENOTDIR, self.os.rename, dir_path,
                                 link_path)

    def testRenameDirToSymlinkWindows(self):
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        link_path = self.makePath('link')
        dir_path = self.makePath('dir')
        link_target = self.os.path.join(dir_path, 'link_target')
        self.createDirectory(dir_path)
        self.os.symlink(link_target.upper(), link_path.upper())
        self.assertRaisesOSError(errno.EEXIST, self.os.rename, dir_path,
                                 link_path)

    def testRenameDirToExistingDir(self):
        # Regression test for #317
        self.checkPosixOnly()
        dest_dir_path = self.makePath('Dest')
        new_dest_dir_path = self.makePath('dest')
        self.os.mkdir(dest_dir_path)
        source_dir_path = self.makePath('src')
        self.os.mkdir(source_dir_path)
        self.os.rename(source_dir_path, new_dest_dir_path)
        self.assertEqual(['dest'], self.os.listdir(self.base_path))

    def testRenameFileToSymlink(self):
        self.checkPosixOnly()
        link_path = self.makePath('file_link')
        file_path = self.makePath('file')
        self.os.symlink(file_path, link_path)
        self.createFile(file_path)
        self.os.rename(file_path.upper(), link_path)
        self.assertFalse(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.exists(link_path.upper()))
        self.assertTrue(self.os.path.isfile(link_path.upper()))

    def testRenameSymlinkToSymlink(self):
        self.checkPosixOnly()
        base_path = self.makePath('foo', 'bar')
        self.createDirectory(base_path)
        link_path1 = self.os.path.join(base_path, 'link1')
        link_path2 = self.os.path.join(base_path, 'link2')
        self.os.symlink(base_path.upper(), link_path1)
        self.os.symlink(base_path, link_path2)
        self.os.rename(link_path1.upper(), link_path2.upper())
        self.assertFalse(self.os.path.exists(link_path1))
        self.assertTrue(self.os.path.exists(link_path2))

    def testRenameSymlinkToSymlinkForParentRaises(self):
        self.checkPosixOnly()
        dir_link = self.makePath('dir_link')
        dir_path = self.makePath('dir')
        dir_in_dir_path = self.os.path.join(dir_link, 'inner_dir')
        self.createDirectory(dir_path)
        self.os.symlink(dir_path.upper(), dir_link)
        self.createDirectory(dir_in_dir_path)
        self.assertRaisesOSError(errno.EINVAL, self.os.rename, dir_path,
                                 dir_in_dir_path.upper())

    def testRenameDirectoryToLinkedDir(self):
        # Regression test for #314
        self.skipIfSymlinkNotSupported()
        link_path = self.makePath('link')
        self.os.symlink(self.base_path, link_path)
        link_subdir = self.os.path.join(link_path, 'dir')
        dir_path = self.makePath('Dir')
        self.os.mkdir(dir_path)
        self.os.rename(dir_path, link_subdir)
        self.assertEqual(['dir', 'link'],
                         sorted(self.os.listdir(self.base_path)))

    def testRecursiveRenameRaises(self):
        self.checkPosixOnly()
        base_path = self.makePath('foo', 'bar')
        self.createDirectory(base_path)
        new_path = self.os.path.join(base_path, 'new_dir')
        self.assertRaisesOSError(errno.EINVAL, self.os.rename,
                                 base_path.upper(), new_path)

    def testRenameWithTargetParentFileRaisesPosix(self):
        self.checkPosixOnly()
        file_path = self.makePath('foo', 'baz')
        self.createFile(file_path)
        self.assertRaisesOSError(errno.ENOTDIR, self.os.rename, file_path,
                                 file_path.upper() + '/new')

    def testRenameWithTargetParentFileRaisesWindows(self):
        self.checkWindowsOnly()
        file_path = self.makePath('foo', 'baz')
        self.createFile(file_path)
        self.assertRaisesOSError(errno.EACCES, self.os.rename, file_path,
                                 self.os.path.join(file_path.upper(), 'new'))

    def testRenameLoopingSymlink(self):
        # Regression test for #315
        self.skipIfSymlinkNotSupported()
        path_lower = self.makePath('baz')
        path_upper = self.makePath('BAZ')
        self.os.symlink(path_lower, path_upper)
        self.os.rename(path_upper, path_lower)
        self.assertEqual(['baz'], self.os.listdir(self.base_path))


    def testRenameSymlinkToSource(self):
        self.checkPosixOnly()
        base_path = self.makePath('foo')
        link_path = self.os.path.join(base_path, 'slink')
        file_path = self.os.path.join(base_path, 'file')
        self.createFile(file_path)
        self.os.symlink(file_path, link_path)
        self.os.rename(link_path.upper(), file_path.upper())
        self.assertFalse(self.os.path.exists(file_path))

    def testRenameSymlinkToDirRaises(self):
        self.checkPosixOnly()
        base_path = self.makePath('foo', 'bar')
        link_path = self.os.path.join(base_path, 'dir_link')
        dir_path = self.os.path.join(base_path, 'dir')
        self.createDirectory(dir_path)
        self.os.symlink(dir_path, link_path.upper())
        self.assertRaisesOSError(errno.EISDIR, self.os.rename, link_path,
                                 dir_path.upper())

    def testRenameBrokenSymlink(self):
        self.checkPosixOnly()
        base_path = self.makePath('foo')
        self.createDirectory(base_path)
        link_path = self.os.path.join(base_path, 'slink')
        file_path = self.os.path.join(base_path, 'file')
        self.os.symlink(file_path.upper(), link_path)
        self.os.rename(link_path.upper(), file_path)
        self.assertFalse(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.lexists(file_path))
        self.assertFalse(self.os.path.exists(link_path))

    def testChangeCaseInCaseInsensitiveFileSystem(self):
        """Can use `rename()` to change filename case in a case-insensitive
         file system."""
        old_file_path = self.makePath('fileName')
        new_file_path = self.makePath('FileNAME')
        self.createFile(old_file_path, contents='test contents')
        self.assertEqual(['fileName'], self.os.listdir(self.base_path))
        self.os.rename(old_file_path, new_file_path)
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.assertEqual(['FileNAME'], self.os.listdir(self.base_path))

    def testRenameSymlinkWithChangedCase(self):
        # Regression test for #313
        self.skipIfSymlinkNotSupported()
        link_path = self.makePath('link')
        self.os.symlink(self.base_path, link_path)
        link_path = self.os.path.join(link_path, 'link')
        link_path_upper = self.makePath('link', 'LINK')
        self.os.rename(link_path_upper, link_path)

    def testRenameDirectory(self):
        """Can rename a directory to an unused name."""
        for old_path, new_path in [('wxyyw', 'xyzzy'), ('abccb', 'cdeed')]:
            old_path = self.makePath(old_path)
            new_path = self.makePath(new_path)
            self.createFile(self.os.path.join(old_path, 'plugh'),
                            contents='test')
            self.assertTrue(self.os.path.exists(old_path))
            self.assertFalse(self.os.path.exists(new_path))
            self.os.rename(old_path.upper(), new_path.upper())
            self.assertFalse(self.os.path.exists(old_path))
            self.assertTrue(self.os.path.exists(new_path))
            self.checkContents(self.os.path.join(new_path, 'plugh'), 'test')
            if not self.useRealFs():
                self.assertEqual(3,
                                 self.filesystem.GetObject(new_path).st_nlink)

    def checkRenameDirectoryToExistingFileRaises(self, error_nr):
        dir_path = self.makePath('dir')
        file_path = self.makePath('file')
        self.createDirectory(dir_path)
        self.createFile(file_path)
        self.assertRaisesOSError(error_nr, self.os.rename, dir_path,
                                 file_path.upper())

    def testRenameDirectoryToExistingFileRaisesPosix(self):
        self.checkPosixOnly()
        self.checkRenameDirectoryToExistingFileRaises(errno.ENOTDIR)

    def testRenameDirectoryToExistingFileRaisesWindows(self):
        self.checkWindowsOnly()
        self.checkRenameDirectoryToExistingFileRaises(errno.EEXIST)

    def testRenameToExistingDirectoryShouldRaiseUnderWindows(self):
        """Renaming to an existing directory raises OSError under Windows."""
        self.checkWindowsOnly()
        old_path = self.makePath('foo', 'bar')
        new_path = self.makePath('foo', 'baz')
        self.createDirectory(old_path)
        self.createDirectory(new_path)
        self.assertRaisesOSError(errno.EEXIST, self.os.rename,
                                 old_path.upper(),
                                 new_path.upper())

    def testRenameToAHardlinkOfSameFileShouldDoNothing(self):
        self.skipRealFsFailure(skipPosix=False)
        self.skipIfSymlinkNotSupported()
        file_path = self.makePath('dir', 'file')
        self.createFile(file_path)
        link_path = self.makePath('link')
        self.os.link(file_path.upper(), link_path)
        self.os.rename(file_path, link_path.upper())
        self.assertTrue(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.exists(link_path))

    def testRenameWithIncorrectSourceCase(self):
        # Regression test for #308
        base_path = self.makePath('foo')
        path0 = self.os.path.join(base_path, 'bar')
        path1 = self.os.path.join(base_path, 'Bar')
        self.createDirectory(path0)
        self.os.rename(path1, path0)
        self.assertTrue(self.os.path.exists(path0))

    def testRenameSymlinkToOtherCaseDoesNothingInMacOs(self):
        # Regression test for #318
        self.checkMacOsOnly()
        path0 = self.makePath("beta")
        self.os.symlink(self.base_path, path0)
        path0 = self.makePath("beta", "Beta")
        path1 = self.makePath("Beta")
        self.os.rename(path0, path1)
        self.assertEqual(['beta'], sorted(self.os.listdir(path0)))

    def testRenameSymlinkToOtherCaseWorksInWindows(self):
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        path0 = self.makePath("beta")
        self.os.symlink(self.base_path, path0)
        path0 = self.makePath("beta", "Beta")
        path1 = self.makePath("Beta")
        self.os.rename(path0, path1)
        self.assertEqual(['Beta'], sorted(self.os.listdir(path0)))

    def testStatWithMixedCase(self):
        # Regression test for #310
        self.skipIfSymlinkNotSupported()
        base_path = self.makePath('foo')
        path = self.os.path.join(base_path, 'bar')
        self.createDirectory(path)
        path = self.os.path.join(path, 'Bar')
        self.os.symlink(base_path, path)
        path = self.os.path.join(path, 'Bar')
        # used to raise
        self.os.stat(path)

    def testHardlinkWorksWithSymlink(self):
        self.checkPosixOnly()
        base_path = self.makePath('foo')
        self.createDirectory(base_path)
        symlink_path = self.os.path.join(base_path, 'slink')
        self.os.symlink(base_path.upper(), symlink_path)
        file_path = self.os.path.join(base_path, 'slink', 'beta')
        self.createFile(file_path)
        link_path = self.os.path.join(base_path, 'Slink', 'gamma')
        self.os.link(file_path, link_path)
        self.assertTrue(self.os.path.exists(link_path))

    @unittest.skipIf(sys.version_info < (3, 3), 'replace is new in Python 3.3')
    def testReplaceExistingDirectoryShouldRaiseUnderWindows(self):
        """Renaming to an existing directory raises OSError under Windows."""
        self.checkWindowsOnly()
        old_path = self.makePath('foo', 'bar')
        new_path = self.makePath('foo', 'baz')
        self.createDirectory(old_path)
        self.createDirectory(new_path)
        self.assertRaisesOSError(errno.EACCES, self.os.replace, old_path,
                                 new_path.upper())

    def testRenameToExistingDirectoryUnderPosix(self):
        """Renaming to an existing directory changes the existing directory
        under Posix."""
        self.checkPosixOnly()
        old_path = self.makePath('foo', 'bar')
        new_path = self.makePath('xyzzy')
        self.createDirectory(self.os.path.join(old_path, 'sub'))
        self.createDirectory(new_path)
        self.os.rename(old_path.upper(), new_path.upper())
        self.assertTrue(
            self.os.path.exists(self.os.path.join(new_path, 'sub')))
        self.assertFalse(self.os.path.exists(old_path))

    def testRenameFileToExistingDirectoryRaisesUnderPosix(self):
        self.checkPosixOnly()
        file_path = self.makePath('foo', 'bar', 'baz')
        new_path = self.makePath('xyzzy')
        self.createFile(file_path)
        self.createDirectory(new_path)
        self.assertRaisesOSError(errno.EISDIR, self.os.rename,
                                 file_path.upper(),
                                 new_path.upper())

    def testRenameToExistentFilePosix(self):
        """Can rename a file to a used name under Unix."""
        self.checkPosixOnly()
        directory = self.makePath('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.createFile(old_file_path, contents='test contents 1')
        self.createFile(new_file_path, contents='test contents 2')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.os.rename(old_file_path.upper(), new_file_path.upper())
        self.assertFalse(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.checkContents(new_file_path, 'test contents 1')

    def testRenameToExistentFileWindows(self):
        """Renaming a file to a used name raises OSError under Windows."""
        self.checkWindowsOnly()
        directory = self.makePath('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.createFile(old_file_path, contents='test contents 1')
        self.createFile(new_file_path, contents='test contents 2')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.assertRaisesOSError(errno.EEXIST, self.os.rename,
                                 old_file_path.upper(),
                                 new_file_path.upper())

    @unittest.skipIf(sys.version_info < (3, 3), 'replace is new in Python 3.3')
    def testReplaceToExistentFile(self):
        """Replaces an existing file (does not work with `rename()` under
        Windows)."""
        directory = self.makePath('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(directory, 'plugh_new')
        self.createFile(old_file_path, contents='test contents 1')
        self.createFile(new_file_path, contents='test contents 2')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.os.replace(old_file_path.upper(), new_file_path.upper())
        self.assertFalse(self.os.path.exists(old_file_path))
        self.assertTrue(self.os.path.exists(new_file_path))
        self.checkContents(new_file_path, 'test contents 1')

    def testRenameToNonexistentDir(self):
        """Can rename a file to a name in a nonexistent dir."""
        directory = self.makePath('xyzzy')
        old_file_path = self.os.path.join(directory, 'plugh_old')
        new_file_path = self.os.path.join(
            directory, 'no_such_path', 'plugh_new')
        self.createFile(old_file_path, contents='test contents')
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertFalse(self.os.path.exists(new_file_path))
        self.assertRaisesOSError(errno.ENOENT, self.os.rename,
                                 old_file_path.upper(),
                                 new_file_path.upper())
        self.assertTrue(self.os.path.exists(old_file_path))
        self.assertFalse(self.os.path.exists(new_file_path))
        self.checkContents(old_file_path, 'test contents')

    def testRenameCaseOnlyWithSymlinkParent(self):
        # Regression test for #319
        self.skipIfSymlinkNotSupported()
        self.os.symlink(self.base_path, self.makePath('link'))
        dir_upper = self.makePath('link', 'Alpha')
        self.os.mkdir(dir_upper)
        dir_lower = self.makePath('alpha')
        self.os.rename(dir_upper, dir_lower)
        self.assertEqual(['alpha', 'link'],
                         sorted(self.os.listdir(self.base_path)))

    def testRenameDir(self):
        """Test a rename of a directory."""
        directory = self.makePath('xyzzy')
        before_dir = self.os.path.join(directory, 'before')
        before_file = self.os.path.join(directory, 'before', 'file')
        after_dir = self.os.path.join(directory, 'after')
        after_file = self.os.path.join(directory, 'after', 'file')
        self.createDirectory(before_dir)
        self.createFile(before_file, contents='payload')
        self.assertTrue(self.os.path.exists(before_dir.upper()))
        self.assertTrue(self.os.path.exists(before_file.upper()))
        self.assertFalse(self.os.path.exists(after_dir.upper()))
        self.assertFalse(self.os.path.exists(after_file.upper()))
        self.os.rename(before_dir.upper(), after_dir)
        self.assertFalse(self.os.path.exists(before_dir.upper()))
        self.assertFalse(self.os.path.exists(before_file.upper()))
        self.assertTrue(self.os.path.exists(after_dir.upper()))
        self.assertTrue(self.os.path.exists(after_file.upper()))
        self.checkContents(after_file, 'payload')

    def testRenameSameFilenames(self):
        """Test renaming when old and new names are the same."""
        directory = self.makePath('xyzzy')
        file_contents = 'Spam eggs'
        file_path = self.os.path.join(directory, 'eggs')
        self.createFile(file_path, contents=file_contents)
        self.os.rename(file_path, file_path.upper())
        self.checkContents(file_path, file_contents)

    def testRmdir(self):
        """Can remove a directory."""
        directory = self.makePath('xyzzy')
        sub_dir = self.makePath('xyzzy', 'abccd')
        other_dir = self.makePath('xyzzy', 'cdeed')
        self.createDirectory(directory)
        self.assertTrue(self.os.path.exists(directory))
        self.os.rmdir(directory)
        self.assertFalse(self.os.path.exists(directory))
        self.createDirectory(sub_dir)
        self.createDirectory(other_dir)
        self.os.chdir(sub_dir)
        self.os.rmdir('../CDEED')
        self.assertFalse(self.os.path.exists(other_dir))
        self.os.chdir('..')
        self.os.rmdir('AbcCd')
        self.assertFalse(self.os.path.exists(sub_dir))

    def testRmdirViaSymlink(self):
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        base_path = self.makePath('foo', 'bar')
        dir_path = self.os.path.join(base_path, 'alpha')
        self.createDirectory(dir_path)
        link_path = self.os.path.join(base_path, 'beta')
        self.os.symlink(base_path, link_path)
        self.os.rmdir(link_path + '/Alpha')
        self.assertFalse(self.os.path.exists(dir_path))

    def testRemoveDirsWithNonTopSymlinkSucceeds(self):
        self.checkPosixOnly()
        dir_path = self.makePath('dir')
        dir_link = self.makePath('dir_link')
        self.createDirectory(dir_path)
        self.os.symlink(dir_path, dir_link)
        dir_in_dir = self.os.path.join(dir_link, 'dir2')
        self.createDirectory(dir_in_dir)
        self.os.removedirs(dir_in_dir.upper())
        self.assertFalse(self.os.path.exists(dir_in_dir))
        # ensure that the symlink is not removed
        self.assertTrue(self.os.path.exists(dir_link))

    def testMkdirRaisesOnSymlinkInPosix(self):
        self.checkPosixOnly()
        base_path = self.makePath('foo', 'bar')
        link_path = self.os.path.join(base_path, 'link_to_dir')
        dir_path = self.os.path.join(base_path, 'dir')
        self.createDirectory(dir_path)
        self.os.symlink(dir_path.upper(), link_path.upper())
        self.assertRaisesOSError(errno.ENOTDIR, self.os.rmdir, link_path)

    def testMkdirRemovesSymlinkInWindows(self):
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        base_path = self.makePath('foo', 'bar')
        link_path = self.os.path.join(base_path, 'link_to_dir')
        dir_path = self.os.path.join(base_path, 'dir')
        self.createDirectory(dir_path)
        self.os.symlink(dir_path.upper(), link_path.upper())
        self.os.rmdir(link_path)
        self.assertFalse(self.os.path.exists(link_path))
        self.assertTrue(self.os.path.exists(dir_path))

    def testMkdirRaisesIfDirectoryExists(self):
        """mkdir raises exception if directory already exists."""
        directory = self.makePath('xyzzy')
        self.createDirectory(directory)
        self.assertTrue(self.os.path.exists(directory))
        self.assertRaisesOSError(errno.EEXIST,
                                 self.os.mkdir, directory.upper())

    def testMkdirRaisesIfFileExists(self):
        """mkdir raises exception if name already exists as a file."""
        directory = self.makePath('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.createFile(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.assertRaisesOSError(errno.EEXIST,
                                 self.os.mkdir, file_path.upper())

    def testMkdirRaisesIfSymlinkExists(self):
        # Regression test for #309
        self.skipIfSymlinkNotSupported()
        path1 = self.makePath('baz')
        self.os.symlink(path1, path1)
        path2 = self.makePath('Baz')
        self.assertRaisesOSError(errno.EEXIST, self.os.mkdir, path2)

    def checkMkdirRaisesIfParentIsFile(self, error_type):
        """mkdir raises exception if name already exists as a file."""
        directory = self.makePath('xyzzy')
        file_path = self.os.path.join(directory, 'plugh')
        self.createFile(file_path)
        self.assertRaisesOSError(error_type, self.os.mkdir,
                                 self.os.path.join(file_path.upper(),
                                                   'ff'))
    def testMkdirRaisesIfParentIsFilePosix(self):
        self.checkPosixOnly()
        self.checkMkdirRaisesIfParentIsFile(errno.ENOTDIR)

    def testMkdirRaisesIfParentIsFileWindows(self):
        self.checkWindowsOnly()
        self.checkMkdirRaisesIfParentIsFile(errno.ENOENT)

    def testMakedirs(self):
        """makedirs can create a directory even if parent does not exist."""
        parent = self.makePath('xyzzy')
        directory = self.os.path.join(parent, 'foo')
        self.assertFalse(self.os.path.exists(parent))
        self.os.makedirs(directory.upper())
        self.assertTrue(self.os.path.exists(directory))

    def checkMakedirsRaisesIfParentIsFile(self, error_type):
        """makedirs raises exception if a parent component exists as a file."""
        file_path = self.makePath('xyzzy')
        directory = self.os.path.join(file_path, 'plugh')
        self.createFile(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.assertRaisesOSError(error_type, self.os.makedirs,
                                 directory.upper())

    def testMakedirsRaisesIfParentIsFilePosix(self):
        self.checkPosixOnly()
        self.checkMakedirsRaisesIfParentIsFile(errno.ENOTDIR)

    def testMakedirsRaisesIfParentIsFileWindows(self):
        self.checkWindowsOnly()
        self.checkMakedirsRaisesIfParentIsFile(errno.ENOENT)

    def testMakedirsRaisesIfParentIsBrokenLink(self):
        self.checkPosixOnly()
        link_path = self.makePath('broken_link')
        self.os.symlink(self.makePath('bogus'), link_path)
        self.assertRaisesOSError(errno.ENOENT, self.os.makedirs,
                                 self.os.path.join(link_path.upper(),
                                                   'newdir'))

    @unittest.skipIf(sys.version_info < (3, 2),
                     'os.makedirs(exist_ok) argument new in version 3.2')
    def testMakedirsExistOk(self):
        """makedirs uses the exist_ok argument"""
        directory = self.makePath('xyzzy', 'foo')
        self.createDirectory(directory)
        self.assertTrue(self.os.path.exists(directory))

        self.assertRaisesOSError(errno.EEXIST, self.os.makedirs,
                                 directory.upper())
        self.os.makedirs(directory.upper(), exist_ok=True)
        self.assertTrue(self.os.path.exists(directory))

    # test fsync and fdatasync

    def testFsyncPass(self):
        test_file_path = self.makePath('test_file')
        self.createFile(test_file_path, contents='dummy file contents')
        test_file = self.open(test_file_path.upper(), 'r+')
        test_fd = test_file.fileno()
        # Test that this doesn't raise anything
        self.os.fsync(test_fd)
        # And just for sanity, double-check that this still raises
        self.assertRaisesOSError(errno.EBADF, self.os.fsync, test_fd + 1)

    def testChmod(self):
        # set up
        self.checkPosixOnly()
        self.skipRealFs()
        path = self.makePath('some_file')
        self.createTestFile(path)
        # actual tests
        self.os.chmod(path.upper(), 0o6543)
        st = self.os.stat(path)
        self.assertModeEqual(0o6543, st.st_mode)
        self.assertTrue(st.st_mode & stat.S_IFREG)
        self.assertFalse(st.st_mode & stat.S_IFDIR)

    def testSymlink(self):
        self.skipIfSymlinkNotSupported()
        file_path = self.makePath('foo', 'bar', 'baz')
        self.createDirectory(self.makePath('foo', 'bar'))
        self.os.symlink('bogus', file_path.upper())
        self.assertTrue(self.os.path.lexists(file_path))
        self.assertFalse(self.os.path.exists(file_path))
        self.createFile(self.makePath('Foo', 'Bar', 'Bogus'))
        self.assertTrue(self.os.path.lexists(file_path))
        self.assertTrue(self.os.path.exists(file_path))

    # hard link related tests

    def testLinkDelete(self):
        self.skipIfSymlinkNotSupported()

        file1_path = self.makePath('test_file1')
        file2_path = self.makePath('test_file2')
        contents1 = 'abcdef'
        # Create file
        self.createFile(file1_path, contents=contents1)
        # link to second file
        self.os.link(file1_path.upper(), file2_path)
        # delete first file
        self.os.unlink(file1_path)
        # assert that second file exists, and its contents are the same
        self.assertTrue(self.os.path.exists(file2_path))
        with self.open(file2_path.upper()) as f:
            self.assertEqual(f.read(), contents1)

    def testLinkIsExistingFile(self):
        self.skipIfSymlinkNotSupported()
        file_path = self.makePath('foo', 'bar')
        self.createFile(file_path)
        self.assertRaisesOSError(errno.EEXIST, self.os.link,
                                 file_path.upper(), file_path.upper())

    def testLinkIsBrokenSymlink(self):
        # Regression test for #311
        self.skipIfSymlinkNotSupported()
        self.checkCaseInsensitiveFs()
        file_path = self.makePath('baz')
        self.createFile(file_path)
        path_lower = self.makePath('foo')
        self.os.symlink(path_lower, path_lower)
        path_upper = self.makePath('Foo')
        self.assertRaisesOSError(errno.EEXIST,
                                 self.os.link, file_path, path_upper)

    def testLinkWithChangedCase(self):
        # Regression test for #312
        self.skipIfSymlinkNotSupported()
        self.checkCaseInsensitiveFs()
        link_path = self.makePath('link')
        self.os.symlink(self.base_path, link_path)
        link_path = self.os.path.join(link_path, 'Link')
        self.assertTrue(self.os.lstat(link_path))


class RealOsModuleTestCaseInsensitiveFS(FakeOsModuleTestCaseInsensitiveFS):
    def useRealFs(self):
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

    def testChmodStCtime(self):
        # set up
        file_path = 'some_file'
        self.filesystem.CreateFile(file_path)
        self.assertTrue(self.os.path.exists(file_path))
        self.dummy_time.start()

        st = self.os.stat(file_path)
        self.assertEqual(200, st.st_ctime)
        # tests
        self.os.chmod(file_path, 0o765)
        st = self.os.stat(file_path)
        self.assertEqual(220, st.st_ctime)

    def testUtimeSetsCurrentTimeIfArgsIsNone(self):
        # set up
        path = self.makePath('some_file')
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

    def testUtimeSetsCurrentTimeIfArgsIsNoneWithFloats(self):
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

    def testUtimeSetsCurrentTimeIfArgsIsNoneWithFloatsNSec(self):
        fake_filesystem.FakeOsModule.stat_float_times(False)

        self.setDummyTime(200.9123)
        path = self.makePath('some_file')
        self.createTestFile(path)
        test_file = self.filesystem.GetObject(path)

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

    def testUtimeSetsSpecifiedTime(self):
        # set up
        path = self.makePath('some_file')
        self.createTestFile(path)
        st = self.os.stat(path)
        # actual tests
        self.os.utime(path, (1, 2))
        st = self.os.stat(path)
        self.assertEqual(1, st.st_atime)
        self.assertEqual(2, st.st_mtime)

    def testUtimeDir(self):
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
    def testUtimeFollowSymlinks(self):
        path = self.makePath('some_file')
        self.createTestFile(path)
        link_path = '/link_to_some_file'
        self.filesystem.CreateLink(link_path, path)

        self.os.utime(link_path, (1, 2))
        st = self.os.stat(link_path)
        self.assertEqual(1, st.st_atime)
        self.assertEqual(2, st.st_mtime)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'follow_symlinks new in Python 3.3')
    def testUtimeNoFollowSymlinks(self):
        path = self.makePath('some_file')
        self.createTestFile(path)
        link_path = '/link_to_some_file'
        self.filesystem.CreateLink(link_path, path)

        self.os.utime(link_path, (1, 2), follow_symlinks=False)
        st = self.os.stat(link_path)
        self.assertNotEqual(1, st.st_atime)
        self.assertNotEqual(2, st.st_mtime)
        st = self.os.stat(link_path, follow_symlinks=False)
        self.assertEqual(1, st.st_atime)
        self.assertEqual(2, st.st_mtime)

    def testUtimeNonExistent(self):
        path = '/non/existent/file'
        self.assertFalse(self.os.path.exists(path))
        self.assertRaisesOSError(errno.ENOENT, self.os.utime, path, (1, 2))

    def testUtimeInvalidTimesArgRaises(self):
        path = '/some_dir'
        self.createTestDirectory(path)

        # the error message differs with different Python versions
        # we don't expect the same message here
        self.assertRaises(TypeError, self.os.utime, path, (1, 2, 3))
        self.assertRaises(TypeError, self.os.utime, path, (1, 'str'))

    @unittest.skipIf(sys.version_info < (3, 3), 'ns new in Python 3.3')
    def testUtimeSetsSpecifiedTimeInNs(self):
        # set up
        path = self.makePath('some_file')
        self.createTestFile(path)
        self.dummy_time.start()

        st = self.os.stat(path)
        # actual tests
        self.os.utime(path, ns=(200000000, 400000000))
        st = self.os.stat(path)
        self.assertEqual(0.2, st.st_atime)
        self.assertEqual(0.4, st.st_mtime)

    @unittest.skipIf(sys.version_info < (3, 3), 'ns new in Python 3.3')
    def testUtimeIncorrectNsArgumentRaises(self):
        file_path = 'some_file'
        self.filesystem.CreateFile(file_path)

        self.assertRaises(TypeError, self.os.utime, file_path, ns=(200000000))
        self.assertRaises(TypeError, self.os.utime, file_path, ns=('a', 'b'))
        self.assertRaises(ValueError, self.os.utime, file_path, times=(1, 2),
                          ns=(100, 200))

    @unittest.skipIf(sys.version_info < (3, 3),
                     'file descriptor as path new in Python 3.3')
    def testUtimeUsesOpenFdAsPath(self):
        if os.utime not in os.supports_fd:
            self.skipRealFs()
        self.assertRaisesOSError(errno.EBADF, self.os.utime, 5, (1, 2))
        path = self.makePath('some_file')
        self.createTestFile(path)

        with FakeFileOpen(self.filesystem)(path) as f:
            self.os.utime(f.filedes, times=(1, 2))
            st = self.os.stat(path)
            self.assertEqual(1, st.st_atime)
            self.assertEqual(2, st.st_mtime)


class FakeOsModuleLowLevelFileOpTest(FakeOsModuleTestBase):
    """Test low level functions `os.open()`, `os.read()` and `os.write()`."""

    def testOpenReadOnly(self):
        file_path = self.makePath('file1')
        self.createFile(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_RDONLY)
        self.assertEqual(b'contents', self.os.read(file_des, 8))
        self.assertRaisesOSError(errno.EBADF, self.os.write, file_des, b'test')
        self.os.close(file_des)

    def testOpenReadOnlyWriteZeroBytesPosix(self):
        self.checkPosixOnly()
        file_path = self.makePath('file1')
        self.createFile(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_RDONLY)
        self.assertRaisesOSError(errno.EBADF, self.os.write, file_des, b'test')
        self.os.close(file_des)

    def testOpenReadOnlyWriteZeroBytesWindows(self):
        # under Windows, writing an empty string to a read only file
        # is not an error
        self.checkWindowsOnly()
        file_path = self.makePath('file1')
        self.createFile(file_path, contents=b'contents')
        file_des = self.os.open(file_path, os.O_RDONLY)
        self.assertEqual(0, self.os.write(file_des, b''))
        self.os.close(file_des)

    def testOpenWriteOnly(self):
        file_path = self.makePath('file1')
        file_obj = self.createFile(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_WRONLY)
        self.assertEqual(4, self.os.write(file_des, b'test'))
        self.checkContents(file_path, b'testents')
        self.os.close(file_des)

    def testOpenWriteOnlyRaisesOnRead(self):
        file_path = self.makePath('file1')
        self.createFile(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_WRONLY)
        self.assertRaisesOSError(errno.EBADF, self.os.read, file_des, 5)
        self.os.close(file_des)
        file_des = self.os.open(file_path, os.O_WRONLY | os.O_TRUNC)
        self.assertRaisesOSError(errno.EBADF, self.os.read, file_des, 5)
        self.os.close(file_des)
        file_path2 = self.makePath('file2')
        file_des = self.os.open(file_path2, os.O_CREAT | os.O_WRONLY)
        self.assertRaisesOSError(errno.EBADF, self.os.read, file_des, 5)
        self.os.close(file_des)
        file_des = self.os.open(file_path2,
                                os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        self.assertRaisesOSError(errno.EBADF, self.os.read, file_des, 5)
        self.os.close(file_des)

    def testOpenWriteOnlyReadZeroBytesPosix(self):
        self.checkPosixOnly()
        file_path = self.makePath('file1')
        file_des = self.os.open(file_path, os.O_CREAT | os.O_WRONLY)
        self.assertRaisesOSError(errno.EBADF, self.os.read, file_des, 0)
        self.os.close(file_des)

    def testOpenWriteOnlyReadZeroBytesWindows(self):
        # under Windows, reading 0 bytes from a write only file is not an error
        self.checkWindowsOnly()
        file_path = self.makePath('file1')
        file_des = self.os.open(file_path, os.O_CREAT | os.O_WRONLY)
        self.assertEqual(b'', self.os.read(file_des, 0))
        self.os.close(file_des)

    def testOpenReadWrite(self):
        file_path = self.makePath('file1')
        self.createFile(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_RDWR)
        self.assertEqual(4, self.os.write(file_des, b'test'))
        self.checkContents(file_path, b'testents')
        self.os.close(file_des)

    def testOpenCreateIsReadOnly(self):
        file_path = self.makePath('file1')
        file_des = self.os.open(file_path, os.O_CREAT)
        self.assertEqual(b'', self.os.read(file_des, 1))
        self.assertRaisesOSError(errno.EBADF, self.os.write, file_des, b'foo')
        self.os.close(file_des)

    def testOpenCreateTruncateIsReadOnly(self):
        file_path = self.makePath('file1')
        file_des = self.os.open(file_path, os.O_CREAT | os.O_TRUNC)
        self.assertEqual(b'', self.os.read(file_des, 1))
        self.assertRaisesOSError(errno.EBADF, self.os.write, file_des, b'foo')
        self.os.close(file_des)

    def testOpenRaisesIfDoesNotExist(self):
        file_path = self.makePath('file1')
        self.assertRaisesOSError(errno.ENOENT, self.os.open, file_path,
                                 os.O_RDONLY)
        self.assertRaisesOSError(errno.ENOENT, self.os.open, file_path,
                                 os.O_WRONLY)
        self.assertRaisesOSError(errno.ENOENT, self.os.open, file_path,
                                 os.O_RDWR)

    def testExclusiveOpenRaisesWithoutCreateMode(self):
        self.skipRealFs()
        file_path = self.makePath('file1')
        self.assertRaises(NotImplementedError, self.os.open, file_path,
                          os.O_EXCL)
        self.assertRaises(NotImplementedError, self.os.open, file_path,
                          os.O_EXCL | os.O_WRONLY)
        self.assertRaises(NotImplementedError, self.os.open, file_path,
                          os.O_EXCL | os.O_RDWR)
        self.assertRaises(NotImplementedError, self.os.open, file_path,
                          os.O_EXCL | os.O_TRUNC | os.O_APPEND)

    def testOpenRaisesIfParentDoesNotExist(self):
        path = self.makePath('alpha', 'alpha')
        self.assertRaisesOSError(errno.ENOENT, self.os.open, path,
                                 os.O_CREAT | os.O_WRONLY | os.O_TRUNC)

    def testOpenTruncate(self):
        file_path = self.makePath('file1')
        self.createFile(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_RDWR | os.O_TRUNC)
        self.assertEqual(b'', self.os.read(file_des, 8))
        self.assertEqual(4, self.os.write(file_des, b'test'))
        self.checkContents(file_path, b'test')
        self.os.close(file_des)

    @unittest.skipIf(not TestCase.is_windows,
                     'O_TEMPORARY only present in Windows')
    def testTempFile(self):
        file_path = self.makePath('file1')
        fd = self.os.open(file_path, os.O_CREAT | os.O_RDWR | os.O_TEMPORARY)
        self.assertTrue(self.os.path.exists(file_path))
        self.os.close(fd)
        self.assertFalse(self.os.path.exists(file_path))

    def testOpenAppend(self):
        file_path = self.makePath('file1')
        self.createFile(file_path, contents=b'contents')

        file_des = self.os.open(file_path, os.O_WRONLY | os.O_APPEND)
        self.assertEqual(4, self.os.write(file_des, b'test'))
        self.checkContents(file_path, b'contentstest')
        self.os.close(file_des)

    def testOpenCreate(self):
        file_path = self.makePath('file1')
        file_des = self.os.open(file_path, os.O_RDWR | os.O_CREAT)
        self.assertTrue(self.os.path.exists(file_path))
        self.assertEqual(4, self.os.write(file_des, b'test'))
        self.checkContents(file_path, 'test')
        self.os.close(file_des)

    def testCanReadAfterCreateExclusive(self):
        self.checkPosixOnly()
        path1 = self.makePath('alpha')
        file_des = self.os.open(path1, os.O_CREAT | os.O_EXCL)
        self.assertEqual(b'', self.os.read(file_des, 0))
        self.assertRaisesOSError(errno.EBADF, self.os.write, file_des, b'')
        self.os.close(file_des)

    def testOpenCreateModePosix(self):
        self.checkPosixOnly()
        file_path = self.makePath('file1')
        file_des = self.os.open(file_path, os.O_WRONLY | os.O_CREAT, 0o700)
        self.assertTrue(self.os.path.exists(file_path))
        self.assertRaisesOSError(errno.EBADF, self.os.read, file_des, 5)
        self.assertEqual(4, self.os.write(file_des, b'test'))
        self.assertModeEqual(0o700, self.os.stat(file_path).st_mode)
        self.os.close(file_des)

    def testOpenCreateModeWindows(self):
        self.checkWindowsOnly()
        file_path = self.makePath('file1')
        file_des = self.os.open(file_path, os.O_WRONLY | os.O_CREAT, 0o700)
        self.assertTrue(self.os.path.exists(file_path))
        self.assertRaisesOSError(errno.EBADF, self.os.read, file_des, 5)
        self.assertEqual(4, self.os.write(file_des, b'test'))
        self.assertModeEqual(0o666, self.os.stat(file_path).st_mode)
        self.os.close(file_des)

    def testOpenCreateMode444Windows(self):
        self.checkWindowsOnly()
        file_path = self.makePath('file1')
        file_des = self.os.open(file_path, os.O_WRONLY | os.O_CREAT, 0o442)
        self.assertModeEqual(0o444, self.os.stat(file_path).st_mode)
        self.os.close(file_des)

    def testOpenCreateMode666Windows(self):
        self.checkWindowsOnly()
        file_path = self.makePath('file1')
        file_des = self.os.open(file_path, os.O_WRONLY | os.O_CREAT, 0o224)
        self.assertModeEqual(0o666, self.os.stat(file_path).st_mode)
        self.os.close(file_des)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Exclusive mode new in Python 3.3')
    def testOpenExclusive(self):
        file_path = self.makePath('file1')
        file_des = self.os.open(file_path, os.O_RDWR | os.O_EXCL | os.O_CREAT)
        self.assertTrue(self.os.path.exists(file_path))
        self.os.close(file_des)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Exclusive mode new in Python 3.3')
    def testOpenExclusiveRaisesIfFileExists(self):
        file_path = self.makePath('file1')
        self.createFile(file_path, contents=b'contents')
        self.assertRaisesIOError(errno.EEXIST, self.os.open, file_path,
                                 os.O_RDWR | os.O_EXCL | os.O_CREAT)
        self.assertRaisesIOError(errno.EEXIST, self.os.open, file_path,
                                 os.O_RDWR | os.O_EXCL | os.O_CREAT)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Exclusive mode new in Python 3.3')
    def testOpenExclusiveRaisesIfSymlinkExistsInPosix(self):
        self.checkPosixOnly()
        link_path = self.makePath('link')
        link_target = self.makePath('link_target')
        self.os.symlink(link_target, link_path)
        self.assertRaisesOSError(
            errno.EEXIST, self.os.open, link_path,
            os.O_CREAT | os.O_WRONLY | os.O_TRUNC | os.O_EXCL)

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Exclusive mode new in Python 3.3')
    def testOpenExclusiveIfSymlinkExistsWorksInWindows(self):
        self.checkWindowsOnly()
        self.skipIfSymlinkNotSupported()
        link_path = self.makePath('link')
        link_target = self.makePath('link_target')
        self.os.symlink(link_target, link_path)
        fd = self.os.open(link_path,
                          os.O_CREAT | os.O_WRONLY | os.O_TRUNC | os.O_EXCL)
        self.os.close(fd)

    def testOpenDirectoryRaisesUnderWindows(self):
        self.checkWindowsOnly()
        dir_path = self.makePath('dir')
        self.createDirectory(dir_path)
        self.assertRaisesOSError(errno.EACCES, self.os.open, dir_path,
                                 os.O_RDONLY)
        self.assertRaisesOSError(errno.EACCES, self.os.open, dir_path,
                                 os.O_WRONLY)
        self.assertRaisesOSError(errno.EACCES, self.os.open, dir_path,
                                 os.O_RDWR)

    def testOpenDirectoryForWritingRaisesUnderPosix(self):
        self.checkPosixOnly()
        dir_path = self.makePath('dir')
        self.createDirectory(dir_path)
        self.assertRaisesOSError(errno.EISDIR, self.os.open, dir_path,
                                 os.O_WRONLY)
        self.assertRaisesOSError(errno.EISDIR, self.os.open, dir_path,
                                 os.O_RDWR)

    def testOpenDirectoryReadOnlyUnderPosix(self):
        self.checkPosixOnly()
        self.skipRealFs()
        dir_path = self.makePath('dir')
        self.createDirectory(dir_path)
        file_des = self.os.open(dir_path, os.O_RDONLY)
        self.assertEqual(3, file_des)

    def testOpeningExistingDirectoryInCreationMode(self):
        self.checkLinuxOnly()
        dir_path = self.makePath("alpha")
        self.os.mkdir(dir_path)
        self.assertRaisesOSError(errno.EISDIR,
                                 self.os.open, dir_path, os.O_CREAT)

    def testWritingToExistingDirectory(self):
        self.checkMacOsOnly()
        dir_path = self.makePath("alpha")
        self.os.mkdir(dir_path)
        fd = self.os.open(dir_path, os.O_CREAT)
        self.assertRaisesOSError(errno.EBADF, self.os.write, fd, b'')

    def testOpeningExistingDirectoryInWriteMode(self):
        self.checkPosixOnly()
        dir_path = self.makePath("alpha")
        self.os.mkdir(dir_path)
        self.assertRaisesOSError(errno.EISDIR,
                                 self.os.open, dir_path, os.O_WRONLY)

    def testOpenModePosix(self):
        self.checkPosixOnly()
        self.skipRealFs()
        file_path = self.makePath('baz')
        file_des = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        stat0 = self.os.fstat(file_des)
        # not a really good test as this replicates the code,
        # but we don't know the umask at the test system
        self.assertEqual(0o100777 & ~self.os._umask(), stat0.st_mode)
        self.os.close(file_des)

    def testOpenModeWindows(self):
        self.checkWindowsOnly()
        file_path = self.makePath('baz')
        file_des = self.os.open(file_path,
                                os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        stat0 = self.os.fstat(file_des)
        self.assertEqual(0o100666, stat0.st_mode)
        self.os.close(file_des)

    def testWriteRead(self):
        file_path = self.makePath('file1')
        self.createFile(file_path, contents=b'orig contents')
        new_contents = b'1234567890abcdef'

        with self.open(file_path, 'wb') as fh:
            fileno = fh.fileno()
            self.assertEqual(len(new_contents),
                             self.os.write(fileno, new_contents))
            self.checkContents(file_path, new_contents)

        with self.open(file_path, 'rb') as fh:
            fileno = fh.fileno()
            self.assertEqual(b'', self.os.read(fileno, 0))
            self.assertEqual(new_contents[0:2], self.os.read(fileno, 2))
            self.assertEqual(new_contents[2:10], self.os.read(fileno, 8))
            self.assertEqual(new_contents[10:], self.os.read(fileno, 100))
            self.assertEqual(b'', self.os.read(fileno, 10))

        self.assertRaisesOSError(errno.EBADF, self.os.write, fileno,
                                 new_contents)
        self.assertRaisesOSError(errno.EBADF, self.os.read, fileno, 10)

    def testWriteFromDifferentFDs(self):
        # Regression test for #211
        file_path = self.makePath('baz')
        fd0 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        fd1 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        self.os.write(fd0, b'aaaa')
        self.os.write(fd1, b'bb')
        self.assertEqual(4, self.os.path.getsize(file_path))
        self.checkContents(file_path, b'bbaa')
        self.os.close(fd1)
        self.os.close(fd0)

    def testWriteFromDifferentFDsWithAppend(self):
        # Regression test for #268
        file_path = self.makePath('baz')
        fd0 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        fd1 = self.os.open(file_path, os.O_WRONLY | os.O_APPEND)
        self.os.write(fd0, b'aaa')
        self.os.write(fd1, b'bbb')
        self.assertEqual(6, self.os.path.getsize(file_path))
        self.checkContents(file_path, b'aaabbb')
        self.os.close(fd1)
        self.os.close(fd0)

    def testReadOnlyReadAfterWrite(self):
        # Regression test for #269
        self.checkPosixOnly()
        file_path = self.makePath('foo', 'bar', 'baz')
        self.createFile(file_path, contents=b'test')
        fd0 = self.os.open(file_path, os.O_CREAT)
        fd1 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        self.assertEqual(b'', self.os.read(fd0, 0))
        self.os.close(fd1)
        self.os.close(fd0)

    def testReadAfterClosingWriteDescriptor(self):
        # Regression test for #271
        file_path = self.makePath('baz')
        fd0 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        fd1 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        fd2 = self.os.open(file_path, os.O_CREAT)
        self.os.write(fd1, b'abc')
        self.os.close(fd0)
        self.assertEqual(b'abc', self.os.read(fd2, 3))
        self.os.close(fd2)
        self.os.close(fd1)

    def testWritingBehindEndOfFile(self):
        # Regression test for #273
        file_path = self.makePath('baz')
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
    def useRealFs(self):
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

    def testWalkTopDown(self):
        """Walk down ordering is correct."""
        base_dir = self.makePath('foo')
        self.createFile(self.os.path.join(base_dir, '1.txt'))
        self.createFile(self.os.path.join(base_dir, 'bar1', '2.txt'))
        self.createFile(self.os.path.join(base_dir, 'bar1', 'baz', '3.txt'))
        self.createFile(self.os.path.join(base_dir, 'bar2', '4.txt'))
        expected = [
            (base_dir, ['bar1', 'bar2'], ['1.txt']),
            (self.os.path.join(base_dir, 'bar1'), ['baz'], ['2.txt']),
            (self.os.path.join(base_dir, 'bar1', 'baz'), [], ['3.txt']),
            (self.os.path.join(base_dir, 'bar2'), [], ['4.txt']),
        ]
        self.assertWalkResults(expected, base_dir)

    def testWalkBottomUp(self):
        """Walk up ordering is correct."""
        base_dir = self.makePath('foo')
        self.createFile(self.os.path.join(base_dir, 'bar1', 'baz', '1.txt'))
        self.createFile(self.os.path.join(base_dir, 'bar1', '2.txt'))
        self.createFile(self.os.path.join(base_dir, 'bar2', '3.txt'))
        self.createFile(self.os.path.join(base_dir, '4.txt'))

        expected = [
            (self.os.path.join(base_dir, 'bar1', 'baz'), [], ['1.txt']),
            (self.os.path.join(base_dir, 'bar1'), ['baz'], ['2.txt']),
            (self.os.path.join(base_dir, 'bar2'), [], ['3.txt']),
            (base_dir, ['bar1', 'bar2'], ['4.txt']),
        ]
        self.assertWalkResults(expected, self.makePath('foo'), topdown=False)

    def testWalkRaisesIfNonExistent(self):
        """Raises an exception when attempting to walk
         non-existent directory."""
        directory = self.makePath('foo', 'bar')
        self.assertEqual(False, self.os.path.exists(directory))
        generator = self.os.walk(directory)
        self.assertRaises(StopIteration, next, generator)

    def testWalkRaisesIfNotDirectory(self):
        """Raises an exception when attempting to walk a non-directory."""
        filename = self.makePath('foo', 'bar')
        self.createFile(filename)
        generator = self.os.walk(filename)
        self.assertRaises(StopIteration, next, generator)

    def testWalkCallsOnErrorIfNonExistent(self):
        """Calls onerror with correct errno when walking
        non-existent directory."""
        self.ResetErrno()
        directory = self.makePath('foo', 'bar')
        self.assertEqual(False, self.os.path.exists(directory))
        # Calling os.walk on a non-existent directory should trigger
        # a call to the onerror method.
        # We do not actually care what, if anything, is returned.
        for unused_entry in self.os.walk(directory, onerror=self.StoreErrno):
            pass
        self.assertTrue(self.GetErrno() in (errno.ENOTDIR, errno.ENOENT))

    def testWalkCallsOnErrorIfNotDirectory(self):
        """Calls onerror with correct errno when walking non-directory."""
        self.ResetErrno()
        filename = self.makePath('foo' 'bar')
        self.createFile(filename)
        self.assertEqual(True, self.os.path.exists(filename))
        # Calling `os.walk` on a file should trigger a call to the
        # `onerror` method.
        # We do not actually care what, if anything, is returned.
        for unused_entry in self.os.walk(filename, onerror=self.StoreErrno):
            pass
        self.assertTrue(self.GetErrno() in (self.not_dir_error(),
                                            errno.EACCES))

    def testWalkSkipsRemovedDirectories(self):
        """Caller can modify list of directories to visit while walking."""
        root = self.makePath('foo')
        visit = 'visit'
        no_visit = 'no_visit'
        self.createFile(self.os.path.join(root, 'bar'))
        self.createFile(self.os.path.join(root, visit, '1.txt'))
        self.createFile(self.os.path.join(root, visit, '2.txt'))
        self.createFile(self.os.path.join(root, no_visit, '3.txt'))
        self.createFile(self.os.path.join(root, no_visit, '4.txt'))

        generator = self.os.walk(self.makePath('foo'))
        root_contents = next(generator)
        root_contents[1].remove(no_visit)

        visited_visit_directory = False

        for root, _dirs, _files in iter(generator):
            self.assertEqual(False, root.endswith(self.os.path.sep + no_visit))
            if root.endswith(self.os.path.sep + visit):
                visited_visit_directory = True

        self.assertEqual(True, visited_visit_directory)

    def testWalkFollowsymlinkDisabled(self):
        self.checkPosixOnly()
        base_dir = self.makePath('foo')
        link_dir = self.makePath('linked')
        self.createFile(self.os.path.join(link_dir, 'subfile'))
        self.createFile(self.os.path.join(base_dir, 'bar', 'baz'))
        self.createFile(self.os.path.join(base_dir, 'bar', 'xyzzy', 'plugh'))
        self.createLink(self.os.path.join(base_dir, 'created_link'), link_dir)

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

    def testWalkFollowsymlinkEnabled(self):
        self.checkPosixOnly()
        base_dir = self.makePath('foo')
        link_dir = self.makePath('linked')
        self.createFile(self.os.path.join(link_dir, 'subfile'))
        self.createFile(self.os.path.join(base_dir, 'bar', 'baz'))
        self.createFile(self.os.path.join(base_dir, 'bar', 'xyzzy', 'plugh'))
        self.createLink(self.os.path.join(base_dir, 'created_link'),
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
    def useRealFs(self):
        return True


@unittest.skipIf(sys.version_info < (3, 3),
                 'dir_fd argument was introduced in Python 3.3')
class FakeOsModuleDirFdTest(FakeOsModuleTestBase):
    def setUp(self):
        super(FakeOsModuleDirFdTest, self).setUp()
        self.os.supports_dir_fd = set()
        self.filesystem.is_windows_fs = False
        self.filesystem.CreateDirectory('/foo/bar')
        self.dir_fd = self.os.open('/foo', os.O_RDONLY)
        self.filesystem.CreateFile('/foo/baz')

    def testAccess(self):
        self.assertRaises(
            NotImplementedError, self.os.access, 'baz', self.os.F_OK,
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.access)
        self.assertTrue(
            self.os.access('baz', self.os.F_OK, dir_fd=self.dir_fd))

    def testChmod(self):
        self.assertRaises(
            NotImplementedError, self.os.chmod, 'baz', 0o6543,
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.chmod)
        self.os.chmod('baz', 0o6543, dir_fd=self.dir_fd)
        st = self.os.stat('/foo/baz')
        self.assertModeEqual(0o6543, st.st_mode)

    @unittest.skipIf(not hasattr(os, 'chown'),
                     'chown not on all platforms available')
    def testChown(self):
        self.assertRaises(
            NotImplementedError, self.os.chown, 'baz', 100, 101,
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.chown)
        self.os.chown('baz', 100, 101, dir_fd=self.dir_fd)
        st = self.os.stat('/foo/baz')
        self.assertEqual(st[stat.ST_UID], 100)
        self.assertEqual(st[stat.ST_GID], 101)

    def testLink(self):
        self.assertRaises(
            NotImplementedError, self.os.link, 'baz', '/bat',
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.link)
        self.os.link('baz', '/bat', dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/bat'))

    def testSymlink(self):
        self.assertRaises(
            NotImplementedError, self.os.symlink, 'baz', '/bat',
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.symlink)
        self.os.symlink('baz', '/bat', dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/bat'))

    def testReadlink(self):
        self.filesystem.CreateLink('/meyer/lemon/pie', '/foo/baz')
        self.filesystem.CreateLink('/geo/metro', '/meyer')
        self.assertRaises(
            NotImplementedError, self.os.readlink, '/geo/metro/lemon/pie',
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.readlink)
        self.assertEqual('/foo/baz', self.os.readlink(
            '/geo/metro/lemon/pie', dir_fd=self.dir_fd))

    def testStat(self):
        self.assertRaises(
            NotImplementedError, self.os.stat, 'baz', dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.stat)
        st = self.os.stat('baz', dir_fd=self.dir_fd)
        self.assertEqual(st.st_mode, 0o100666)

    def testLstat(self):
        self.assertRaises(
            NotImplementedError, self.os.lstat, 'baz', dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.lstat)
        st = self.os.lstat('baz', dir_fd=self.dir_fd)
        self.assertEqual(st.st_mode, 0o100666)

    def testMkdir(self):
        self.assertRaises(
            NotImplementedError, self.os.mkdir, 'newdir', dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.mkdir)
        self.os.mkdir('newdir', dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/foo/newdir'))

    def testRmdir(self):
        self.assertRaises(
            NotImplementedError, self.os.rmdir, 'bar', dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.rmdir)
        self.os.rmdir('bar', dir_fd=self.dir_fd)
        self.assertFalse(self.os.path.exists('/foo/bar'))

    @unittest.skipIf(not hasattr(os, 'mknod'),
                     'mknod not on all platforms available')
    def testMknod(self):
        self.assertRaises(
            NotImplementedError, self.os.mknod, 'newdir', dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.mknod)
        self.os.mknod('newdir', dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/foo/newdir'))

    def testRename(self):
        self.assertRaises(
            NotImplementedError, self.os.rename, 'baz', '/foo/batz',
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.rename)
        self.os.rename('bar', '/foo/batz', dir_fd=self.dir_fd)
        self.assertTrue(self.os.path.exists('/foo/batz'))

    def testRemove(self):
        self.assertRaises(
            NotImplementedError, self.os.remove, 'baz', dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.remove)
        self.os.remove('baz', dir_fd=self.dir_fd)
        self.assertFalse(self.os.path.exists('/foo/baz'))

    def testUnlink(self):
        self.assertRaises(
            NotImplementedError, self.os.unlink, 'baz', dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.unlink)
        self.os.unlink('baz', dir_fd=self.dir_fd)
        self.assertFalse(self.os.path.exists('/foo/baz'))

    def testUtime(self):
        self.assertRaises(
            NotImplementedError, self.os.utime, 'baz', (1, 2),
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.utime)
        self.os.utime('baz', (1, 2), dir_fd=self.dir_fd)
        st = self.os.stat('/foo/baz')
        self.assertEqual(1, st.st_atime)
        self.assertEqual(2, st.st_mtime)

    def testOpen(self):
        self.assertRaises(
            NotImplementedError, self.os.open, 'baz', os.O_RDONLY,
            dir_fd=self.dir_fd)
        self.os.supports_dir_fd.add(os.open)
        fd = self.os.open('baz', os.O_RDONLY, dir_fd=self.dir_fd)
        self.assertLess(0, fd)


@unittest.skipIf(sys.version_info < (3, 5),
                 'os.scandir was introduced in Python 3.5')
class FakeScandirTest(FakeOsModuleTestBase):
    def setUp(self):
        super(FakeScandirTest, self).setUp()
        self.skipIfSymlinkNotSupported()
        directory = self.makePath('xyzzy', 'plugh')
        link_dir = self.makePath('linked', 'plugh')
        self.linked_file_path = self.os.path.join(link_dir, 'file')
        self.linked_dir_path = self.os.path.join(link_dir, 'dir')

        self.createDirectory(self.linked_dir_path)
        self.createFile(self.linked_file_path, contents=b'a' * 10)
        self.dir_path = self.os.path.join(directory, 'dir')
        self.createDirectory(self.dir_path)
        self.file_path = self.os.path.join(directory, 'file')
        self.createFile(self.file_path, contents=b'b' * 50)
        self.file_link_path = self.os.path.join(directory, 'link_file')
        self.createLink(self.file_link_path, self.linked_file_path)
        self.dir_link_path = self.os.path.join(directory, 'link_dir')
        self.createLink(self.dir_link_path, self.linked_dir_path)

        self.dir_entries = [entry for entry in self.os.scandir(directory)]
        self.dir_entries = sorted(self.dir_entries,
                                  key=lambda entry: entry.name)

    def testPaths(self):
        self.assertEqual(4, len(self.dir_entries))
        sorted_names = ['dir', 'file', 'link_dir', 'link_file']
        self.assertEqual(sorted_names,
                         [entry.name for entry in self.dir_entries])
        self.assertEqual(self.dir_path, self.dir_entries[0].path)

    def testIsfile(self):
        self.assertFalse(self.dir_entries[0].is_file())
        self.assertTrue(self.dir_entries[1].is_file())
        self.assertFalse(self.dir_entries[2].is_file())
        self.assertFalse(self.dir_entries[2].is_file(follow_symlinks=False))
        self.assertTrue(self.dir_entries[3].is_file())
        self.assertFalse(self.dir_entries[3].is_file(follow_symlinks=False))

    def testIsdir(self):
        self.assertTrue(self.dir_entries[0].is_dir())
        self.assertFalse(self.dir_entries[1].is_dir())
        self.assertTrue(self.dir_entries[2].is_dir())
        self.assertFalse(self.dir_entries[2].is_dir(follow_symlinks=False))
        self.assertFalse(self.dir_entries[3].is_dir())
        self.assertFalse(self.dir_entries[3].is_dir(follow_symlinks=False))

    def testIsLink(self):
        self.assertFalse(self.dir_entries[0].is_symlink())
        self.assertFalse(self.dir_entries[1].is_symlink())
        self.assertTrue(self.dir_entries[2].is_symlink())
        self.assertTrue(self.dir_entries[3].is_symlink())

    def testInode(self):
        self.assertEqual(self.os.stat(self.dir_path).st_ino,
                         self.dir_entries[0].inode())
        self.assertEqual(self.os.stat(self.file_path).st_ino,
                         self.dir_entries[1].inode())
        self.assertEqual(self.os.lstat(self.dir_link_path).st_ino,
                         self.dir_entries[2].inode())
        self.assertEqual(self.os.lstat(self.file_link_path).st_ino,
                         self.dir_entries[3].inode())

    def checkStat(self, expected_size):
        self.assertEqual(50, self.dir_entries[1].stat().st_size)
        self.assertEqual(10, self.dir_entries[3].stat().st_size)
        self.assertEqual(expected_size,
                         self.dir_entries[3].stat(
                             follow_symlinks=False).st_size)
        self.assertEqual(
            self.os.stat(self.dir_path).st_ctime,
            self.dir_entries[0].stat().st_ctime)
        self.assertEqual(
            self.os.stat(self.linked_dir_path).st_mtime,
            self.dir_entries[2].stat().st_mtime)

    @unittest.skipIf(TestCase.is_windows, 'POSIX specific behavior')
    def testStatPosix(self):
        self.checkStat(len(self.linked_file_path))

    @unittest.skipIf(not TestCase.is_windows, 'Windows specific behavior')
    def testStatWindows(self):
        self.checkStat(0)

    def testIndexAccessToStatTimesReturnsInt(self):
        self.assertEqual(self.os.stat(self.dir_path)[stat.ST_CTIME],
                         int(self.dir_entries[0].stat().st_ctime))
        self.assertEqual(self.os.stat(self.linked_dir_path)[stat.ST_MTIME],
                         int(self.dir_entries[2].stat().st_mtime))

    def testStatInoDev(self):
        file_stat = self.os.stat(self.linked_file_path)
        self.assertEqual(file_stat.st_ino, self.dir_entries[3].stat().st_ino)
        self.assertEqual(file_stat.st_dev, self.dir_entries[3].stat().st_dev)


class RealScandirTest(FakeScandirTest):
    def useRealFs(self):
        return True


class StatPropagationTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.os = fake_filesystem.FakeOsModule(self.filesystem)
        self.open = fake_filesystem.FakeFileOpen(self.filesystem)

    def testFileSizeUpdatedViaClose(self):
        """test that file size gets updated via close()."""
        file_dir = 'xyzzy'
        file_path = 'xyzzy/close'
        content = 'This is a test.'
        self.os.mkdir(file_dir)
        fh = self.open(file_path, 'w')
        self.assertEqual(0, self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual('', self.filesystem.GetObject(file_path).contents)
        fh.write(content)
        self.assertEqual(0, self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual('', self.filesystem.GetObject(file_path).contents)
        fh.close()
        self.assertEqual(len(content), self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual(content,
                         self.filesystem.GetObject(file_path).contents)

    def testFileSizeNotResetAfterClose(self):
        file_dir = 'xyzzy'
        file_path = 'xyzzy/close'
        self.os.mkdir(file_dir)
        size = 1234
        # The file has size, but no content. When the file is opened
        # for reading, its size should be preserved.
        self.filesystem.CreateFile(file_path, st_size=size)
        fh = self.open(file_path, 'r')
        fh.close()
        self.assertEqual(size, self.open(file_path, 'r').Size())

    def testFileSizeAfterWrite(self):
        file_path = 'test_file'
        original_content = 'abcdef'
        original_size = len(original_content)
        self.filesystem.CreateFile(file_path, contents=original_content)
        added_content = 'foo bar'
        expected_size = original_size + len(added_content)
        fh = self.open(file_path, 'a')
        fh.write(added_content)
        self.assertEqual(original_size, fh.Size())
        fh.close()
        self.assertEqual(expected_size, self.open(file_path, 'r').Size())

    def testLargeFileSizeAfterWrite(self):
        file_path = 'test_file'
        original_content = 'abcdef'
        original_size = len(original_content)
        self.filesystem.CreateFile(file_path, st_size=original_size)
        added_content = 'foo bar'
        fh = self.open(file_path, 'a')
        self.assertRaises(fake_filesystem.FakeLargeFileIoException,
                          lambda: fh.write(added_content))

    def testFileSizeUpdatedViaFlush(self):
        """test that file size gets updated via flush()."""
        file_dir = 'xyzzy'
        file_name = 'flush'
        file_path = self.os.path.join(file_dir, file_name)
        content = 'This might be a test.'
        self.os.mkdir(file_dir)
        fh = self.open(file_path, 'w')
        self.assertEqual(0, self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual('', self.filesystem.GetObject(file_path).contents)
        fh.write(content)
        self.assertEqual(0, self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual('', self.filesystem.GetObject(file_path).contents)
        fh.flush()
        self.assertEqual(len(content), self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual(content,
                         self.filesystem.GetObject(file_path).contents)
        fh.close()
        self.assertEqual(len(content), self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual(content,
                         self.filesystem.GetObject(file_path).contents)

    def testFileSizeTruncation(self):
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
                         self.filesystem.GetObject(file_path).contents)

        # test file truncation
        fh = self.open(file_path, 'w')
        self.assertEqual(0, self.os.stat(file_path)[stat.ST_SIZE])
        self.assertEqual('', self.filesystem.GetObject(file_path).contents)
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

    def testCreateTopLevelDirectory(self):
        top_level_dir = '/x'
        self.assertFalse(self.filesystem.Exists(top_level_dir))
        self.filesystem.CreateDirectory(top_level_dir)
        self.assertTrue(self.filesystem.Exists('/'))
        self.assertTrue(self.filesystem.Exists(top_level_dir))
        self.filesystem.CreateDirectory('%s/po' % top_level_dir)
        self.filesystem.CreateFile('%s/po/control' % top_level_dir)
        self.filesystem.CreateFile('%s/po/experiment' % top_level_dir)
        self.filesystem.CreateDirectory('%s/gv' % top_level_dir)
        self.filesystem.CreateFile('%s/gv/control' % top_level_dir)

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

    def checkAbspath(self, is_windows):
        # the implementation differs in Windows and Posix, so test both
        self.filesystem.is_windows_fs = is_windows
        filename = u'foo'
        abspath = u'!%s' % filename
        self.filesystem.CreateFile(abspath)
        self.assertEqual(abspath, self.path.abspath(abspath))
        self.assertEqual(abspath, self.path.abspath(filename))
        self.assertEqual(abspath, self.path.abspath(u'..!%s' % filename))

    def testAbspathWindows(self):
        self.checkAbspath(is_windows=True)

    def testAbspathPosix(self):
        """abspath should return a consistent representation of a file."""
        self.checkAbspath(is_windows=False)

    def checkAbspathBytes(self, is_windows):
        """abspath should return a consistent representation of a file."""
        self.filesystem.is_windows_fs = is_windows
        filename = b'foo'
        abspath = b'!' + filename
        self.filesystem.CreateFile(abspath)
        self.assertEqual(abspath, self.path.abspath(abspath))
        self.assertEqual(abspath, self.path.abspath(filename))
        self.assertEqual(abspath, self.path.abspath(b'..!' + filename))

    def testAbspathBytesWindows(self):
        self.checkAbspathBytes(is_windows=True)

    def testAbspathBytesPosix(self):
        self.checkAbspathBytes(is_windows=False)

    def testAbspathDealsWithRelativeNonRootPath(self):
        """abspath should correctly handle relative paths from a non-! directory.

    This test is distinct from the basic functionality test because
    fake_filesystem has historically been based in !.
    """
        filename = '!foo!bar!baz'
        file_components = filename.split(self.path.sep)
        basedir = '!%s' % (file_components[0],)
        self.filesystem.CreateFile(filename)
        self.os.chdir(basedir)
        self.assertEqual(basedir, self.path.abspath(self.path.curdir))
        self.assertEqual('!', self.path.abspath('..'))
        self.assertEqual(self.path.join(basedir, file_components[1]),
                         self.path.abspath(file_components[1]))

    def testAbsPathWithDriveComponent(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.cwd = 'C:!foo'
        self.assertEqual('C:!foo!bar', self.path.abspath('bar'))
        self.assertEqual('C:!foo!bar', self.path.abspath('C:bar'))
        self.assertEqual('C:!foo!bar', self.path.abspath('!foo!bar'))

    def testIsabsWithDriveComponent(self):
        self.filesystem.is_windows_fs = False
        self.assertFalse(self.path.isabs('C:!foo'))
        self.assertTrue(self.path.isabs('!'))
        self.filesystem.is_windows_fs = True
        self.assertTrue(self.path.isabs('C:!foo'))
        self.assertTrue(self.path.isabs('!'))

    def testRelpath(self):
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

    def testRealpathVsAbspath(self):
        self.filesystem.is_windows_fs = False
        self.filesystem.CreateFile('!george!washington!bridge')
        self.filesystem.CreateLink('!first!president', '!george!washington')
        self.assertEqual('!first!president!bridge',
                         self.os.path.abspath('!first!president!bridge'))
        self.assertEqual('!george!washington!bridge',
                         self.os.path.realpath('!first!president!bridge'))
        self.os.chdir('!first!president')
        self.assertEqual('!george!washington!bridge',
                         self.os.path.realpath('bridge'))

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 2),
                     'No Windows support before 3.2')
    def testSamefile(self):
        file_path1 = '!foo!bar!baz'
        file_path2 = '!foo!bar!boo'
        self.filesystem.CreateFile(file_path1)
        self.filesystem.CreateFile(file_path2)
        self.assertTrue(self.path.samefile(file_path1, file_path1))
        self.assertFalse(self.path.samefile(file_path1, file_path2))
        self.assertTrue(
            self.path.samefile(file_path1, '!foo!..!foo!bar!..!bar!baz'))

    def testExists(self):
        file_path = 'foo!bar!baz'
        self.filesystem.CreateFile(file_path)
        self.assertTrue(self.path.exists(file_path))
        self.assertFalse(self.path.exists('!some!other!bogus!path'))

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def testLexists(self):
        file_path = 'foo!bar!baz'
        self.filesystem.CreateDirectory('foo!bar')
        self.filesystem.CreateLink(file_path, 'bogus')
        self.assertTrue(self.path.lexists(file_path))
        self.assertFalse(self.path.exists(file_path))
        self.filesystem.CreateFile('foo!bar!bogus')
        self.assertTrue(self.path.exists(file_path))

    def testDirname(self):
        dirname = 'foo!bar'
        self.assertEqual(dirname, self.path.dirname('%s!baz' % dirname))

    def testJoinStrings(self):
        components = [u'foo', u'bar', u'baz']
        self.assertEqual(u'foo!bar!baz', self.path.join(*components))

    def testJoinBytes(self):
        components = [b'foo', b'bar', b'baz']
        self.assertEqual(b'foo!bar!baz', self.path.join(*components))

    def testExpandUser(self):
        if self.is_windows:
            self.assertEqual(self.path.expanduser('~'),
                             self.os.environ['USERPROFILE'].replace('\\', '!'))
        else:
            self.assertEqual(self.path.expanduser('~'),
                             self.os.environ['HOME'].replace('/', '!'))

    @unittest.skipIf(TestCase.is_windows or TestCase.is_cygwin,
                     'only tested on unix systems')
    def testExpandRoot(self):
        if sys.platform == 'darwin':
            roothome = '!var!root'
        else:
            roothome = '!root'
        self.assertEqual(self.path.expanduser('~root'), roothome)

    def testGetsizePathNonexistent(self):
        file_path = 'foo!bar!baz'
        self.assertRaises(os.error, self.path.getsize, file_path)

    def testGetsizeFileEmpty(self):
        file_path = 'foo!bar!baz'
        self.filesystem.CreateFile(file_path)
        self.assertEqual(0, self.path.getsize(file_path))

    def testGetsizeFileNonZeroSize(self):
        file_path = 'foo!bar!baz'
        self.filesystem.CreateFile(file_path, contents='1234567')
        self.assertEqual(7, self.path.getsize(file_path))

    def testGetsizeDirEmpty(self):
        # For directories, only require that the size is non-negative.
        dir_path = 'foo!bar'
        self.filesystem.CreateDirectory(dir_path)
        size = self.path.getsize(dir_path)
        self.assertFalse(int(size) < 0,
                         'expected non-negative size; actual: %s' % size)

    def testGetsizeDirNonZeroSize(self):
        # For directories, only require that the size is non-negative.
        dir_path = 'foo!bar'
        self.filesystem.CreateFile(self.filesystem.JoinPaths(dir_path, 'baz'))
        size = self.path.getsize(dir_path)
        self.assertFalse(int(size) < 0,
                         'expected non-negative size; actual: %s' % size)

    def testIsdir(self):
        self.filesystem.CreateFile('foo!bar')
        self.assertTrue(self.path.isdir('foo'))
        self.assertFalse(self.path.isdir('foo!bar'))
        self.assertFalse(self.path.isdir('it_dont_exist'))

    def testIsdirWithCwdChange(self):
        self.filesystem.CreateFile('!foo!bar!baz')
        self.assertTrue(self.path.isdir('!foo'))
        self.assertTrue(self.path.isdir('!foo!bar'))
        self.assertTrue(self.path.isdir('foo'))
        self.assertTrue(self.path.isdir('foo!bar'))
        self.filesystem.cwd = '!foo'
        self.assertTrue(self.path.isdir('!foo'))
        self.assertTrue(self.path.isdir('!foo!bar'))
        self.assertTrue(self.path.isdir('bar'))

    def testIsfile(self):
        self.filesystem.CreateFile('foo!bar')
        self.assertFalse(self.path.isfile('foo'))
        self.assertTrue(self.path.isfile('foo!bar'))
        self.assertFalse(self.path.isfile('it_dont_exist'))

    def testGetMtime(self):
        test_file = self.filesystem.CreateFile('foo!bar1.txt')
        time.time.start()
        self.assertEqual(10, test_file.st_mtime)
        test_file.SetMTime(24)
        self.assertEqual(24, self.path.getmtime('foo!bar1.txt'))

    def testGetMtimeRaisesOSError(self):
        self.assertFalse(self.path.exists('it_dont_exist'))
        self.assertRaisesOSError(errno.ENOENT, self.path.getmtime,
                                 'it_dont_exist')

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def testIslink(self):
        self.filesystem.CreateDirectory('foo')
        self.filesystem.CreateFile('foo!regular_file')
        self.filesystem.CreateLink('foo!link_to_file', 'regular_file')
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
    def testIsLinkCaseSensitive(self):
        # Regression test for #306
        self.filesystem.is_case_sensitive = False
        self.filesystem.CreateDirectory('foo')
        self.filesystem.CreateLink('foo!bar', 'foo')
        self.assertTrue(self.path.islink('foo!Bar'))

    def testIsmount(self):
        self.assertFalse(self.path.ismount(''))
        self.assertTrue(self.path.ismount('!'))
        self.assertFalse(self.path.ismount('!mount!'))
        self.filesystem.AddMountPoint('!mount')
        self.assertTrue(self.path.ismount('!mount'))
        self.assertTrue(self.path.ismount('!mount!'))

    def testIsmountWithDriveLetters(self):
        self.filesystem.is_windows_fs = True
        self.assertTrue(self.path.ismount('!'))
        self.assertTrue(self.path.ismount('c:!'))
        self.assertFalse(self.path.ismount('c:'))
        self.assertTrue(self.path.ismount('z:!'))
        self.filesystem.AddMountPoint('!mount')
        self.assertTrue(self.path.ismount('!mount'))
        self.assertTrue(self.path.ismount('!mount!'))

    @unittest.skipIf(sys.version_info < (2, 7, 8),
                     'UNC path support since Python 2.7.8')
    def testIsmountWithUncPaths(self):
        self.filesystem.is_windows_fs = True
        self.assertTrue(self.path.ismount('!!a!'))
        self.assertTrue(self.path.ismount('!!a!b'))
        self.assertTrue(self.path.ismount('!!a!b!'))
        self.assertFalse(self.path.ismount('!a!b!'))
        self.assertFalse(self.path.ismount('!!a!b!c'))

    def testIsmountWithAlternatePathSeparator(self):
        self.filesystem.alternative_path_separator = '!'
        self.filesystem.AddMountPoint('!mount')
        self.assertTrue(self.path.ismount('!mount'))
        self.assertTrue(self.path.ismount('!mount!'))
        self.assertTrue(self.path.ismount('!mount!!'))
        self.filesystem.is_windows_fs = True
        self.assertTrue(self.path.ismount('Z:!'))

    @unittest.skipIf(sys.version_info >= (3, 0),
                     'os.path.walk removed in Python 3')
    def testWalk(self):
        self.filesystem.CreateFile('!foo!bar!baz')
        self.filesystem.CreateFile('!foo!bar!xyzzy!plugh')
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
    def testWalkFromNonexistentTopDoesNotThrow(self):
        visited_nodes = []

        def RecordVisitedNodes(visited, dirname, fnames):
            visited.extend(((dirname, fname) for fname in fnames))

        self.path.walk('!foo', RecordVisitedNodes, visited_nodes)
        self.assertEqual([], visited_nodes)

    def testGetattrForwardToRealOsPath(self):
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
    def pathSeparator(self):
        return '!'


class FakeFileOpenTest(FakeFileOpenTestBase):
    def setUp(self):
        super(FakeFileOpenTest, self).setUp()
        self.orig_time = time.time

    def tearDown(self):
        super(FakeFileOpenTest, self).tearDown()
        time.time = self.orig_time

    def testOpenNoParentDir(self):
        """Expect raise when opening a file in a missing directory."""
        file_path = self.makePath('foo', 'bar.txt')
        self.assertRaisesIOError(errno.ENOENT, self.open, file_path, 'w')

    def testDeleteOnClose(self):
        self.skipRealFs()
        file_dir = 'boo'
        file_path = 'boo!far'
        self.os.mkdir(file_dir)
        self.open = fake_filesystem.FakeFileOpen(self.filesystem,
                                                 delete_on_close=True)
        with self.open(file_path, 'w'):
            self.assertTrue(self.filesystem.Exists(file_path))
        self.assertFalse(self.filesystem.Exists(file_path))

    def testNoDeleteOnCloseByDefault(self):
        file_path = self.makePath('czar')
        with self.open(file_path, 'w'):
            self.assertTrue(self.os.path.exists(file_path))
        self.assertTrue(self.os.path.exists(file_path))

    def testCompatibilityOfWithStatement(self):
        self.skipRealFs()
        self.open = fake_filesystem.FakeFileOpen(self.filesystem,
                                                 delete_on_close=True)
        file_path = 'foo'
        self.assertFalse(self.os.path.exists(file_path))
        with self.open(file_path, 'w') as _:
            self.assertTrue(self.os.path.exists(file_path))
        # After the 'with' statement, the close() method should have been called.
        self.assertFalse(self.os.path.exists(file_path))

    def testUnicodeContents(self):
        file_path = self.makePath('foo')
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
        file_path = self.makePath('foo')
        byte_fractions = b'\xe2\x85\x93 \xe2\x85\x94 \xe2\x85\x95 \xe2\x85\x96'
        with self.open(file_path, 'w') as f:
            f.write(byte_fractions)
        with self.open(file_path) as f:
            contents = f.read()
        self.assertEqual(contents, byte_fractions)

    @unittest.skipIf(sys.version_info < (3, 0),
                     'Python3 specific string handling')
    def testByteContentsPy3(self):
        file_path = self.makePath('foo')
        byte_fractions = b'\xe2\x85\x93 \xe2\x85\x94 \xe2\x85\x95 \xe2\x85\x96'
        with self.open(file_path, 'wb') as f:
            f.write(byte_fractions)
        # the encoding has to be specified, otherwise the locale default
        # is used which can be different on different systems
        with self.open(file_path, encoding='utf-8') as f:
            contents = f.read()
        self.assertEqual(contents, byte_fractions.decode('utf-8'))

    def testWriteStrReadBytes(self):
        file_path = self.makePath('foo')
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

    def testByteContents(self):
        file_path = self.makePath('foo')
        byte_fractions = b'\xe2\x85\x93 \xe2\x85\x94 \xe2\x85\x95 \xe2\x85\x96'
        with self.open(file_path, 'wb') as f:
            f.write(byte_fractions)
        with self.open(file_path, 'rb') as f:
            contents = f.read()
        self.assertEqual(contents, byte_fractions)

    def testOpenValidFile(self):
        contents = [
            'I am he as\n',
            'you are he as\n',
            'you are me and\n',
            'we are all together\n'
        ]
        file_path = self.makePath('bar.txt')
        self.createFile(file_path, contents=''.join(contents))
        with self.open(file_path) as fake_file:
            self.assertEqual(contents, fake_file.readlines())

    def testOpenValidArgs(self):
        # FIXME: under Windows, line endings are not handled correctly
        self.skipRealFsFailure(skipPosix=False, skipPython2=False)
        contents = [
            "Bang bang Maxwell's silver hammer\n",
            'Came down on her head',
        ]
        file_path = self.makePath('abbey_road', 'maxwell')
        self.createFile(file_path, contents=''.join(contents))

        self.assertEqual(
            contents, self.open(file_path, mode='r', buffering=1).readlines())
        if sys.version_info >= (3, 0):
            self.assertEqual(
                contents, self.open(file_path, mode='r', buffering=1,
                                    errors='strict', newline='\n',
                                    opener=None).readlines())

    @unittest.skipIf(sys.version_info < (3, 0),
                     'only tested on 3.0 or greater')
    def testOpenNewlineArg(self):
        # FIXME: line endings are not handled correctly in pyfakefs
        self.skipRealFsFailure()
        file_path = self.makePath('some_file')
        file_contents = b'two\r\nlines'
        self.createFile(file_path, contents=file_contents)
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

    def testOpenValidFileWithCwd(self):
        contents = [
            'I am he as\n',
            'you are he as\n',
            'you are me and\n',
            'we are all together\n'
        ]
        file_path = self.makePath('bar.txt')
        self.createFile(file_path, contents=''.join(contents))
        self.os.chdir(self.base_path)
        self.assertEqual(contents, self.open(file_path).readlines())

    def testIterateOverFile(self):
        contents = [
            "Bang bang Maxwell's silver hammer",
            'Came down on her head',
        ]
        file_path = self.makePath('abbey_road', 'maxwell')
        self.createFile(file_path, contents='\n'.join(contents))
        with self.open(file_path) as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    def testOpenDirectoryError(self):
        directory_path = self.makePath('foo')
        self.os.mkdir(directory_path)
        if self.is_windows:
            if self.is_python2:
                self.assertRaisesIOError(errno.EACCES, self.open.__call__,
                                         directory_path)
            else:
                self.assertRaisesOSError(errno.EACCES, self.open.__call__,
                                         directory_path)
        else:
            self.assertRaisesIOError(errno.EISDIR, self.open.__call__,
                                     directory_path)

    def testCreateFileWithWrite(self):
        contents = [
            "Here comes the sun, little darlin'",
            'Here comes the sun, and I say,',
            "It's alright",
        ]
        file_dir = self.makePath('abbey_road')
        file_path = self.os.path.join(file_dir, 'here_comes_the_sun')
        self.os.mkdir(file_dir)
        with self.open(file_path, 'w') as fake_file:
            for line in contents:
                fake_file.write(line + '\n')
        with self.open(file_path) as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    def testCreateFileWithAppend(self):
        contents = [
            "Here comes the sun, little darlin'",
            'Here comes the sun, and I say,',
            "It's alright",
        ]
        file_dir = self.makePath('abbey_road')
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
        file_path = self.makePath('bar')
        self.assertRaises(ValueError, self.open, file_path, 'x')
        self.assertRaises(ValueError, self.open, file_path, 'xb')

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Exclusive mode new in Python 3.3')
    def testExclusiveCreateFileFailure(self):
        self.skipIfSymlinkNotSupported()
        file_path = self.makePath('bar')
        self.createFile(file_path)
        self.assertRaisesIOError(errno.EEXIST, self.open, file_path, 'x')
        self.assertRaisesIOError(errno.EEXIST, self.open, file_path, 'xb')

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Exclusive mode new in Python 3.3')
    def testExclusiveCreateFile(self):
        file_dir = self.makePath('foo')
        file_path = self.os.path.join(file_dir, 'bar')
        self.os.mkdir(file_dir)
        contents = 'String contents'
        with self.open(file_path, 'x') as fake_file:
            fake_file.write(contents)
        with self.open(file_path) as fake_file:
            self.assertEqual(contents, fake_file.read())

    @unittest.skipIf(sys.version_info < (3, 3),
                     'Exclusive mode new in Python 3.3')
    def testExclusiveCreateBinaryFile(self):
        file_dir = self.makePath('foo')
        file_path = self.os.path.join(file_dir, 'bar')
        self.os.mkdir(file_dir)
        contents = b'Binary contents'
        with self.open(file_path, 'xb') as fake_file:
            fake_file.write(contents)
        with self.open(file_path, 'rb') as fake_file:
            self.assertEqual(contents, fake_file.read())

    def testOverwriteExistingFile(self):
        file_path = self.makePath('overwite')
        self.createFile(file_path, contents='To disappear')
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

    def testAppendExistingFile(self):
        file_path = self.makePath('appendfile')
        contents = [
            'Contents of original file'
            'Appended contents',
        ]

        self.createFile(file_path, contents=contents[0])
        with self.open(file_path, 'a') as fake_file:
            for line in contents[1:]:
                fake_file.write(line + '\n')
        with self.open(file_path) as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    def testOpenWithWplus(self):
        # set up
        file_path = self.makePath('wplus_file')
        self.createFile(file_path, contents='old contents')
        self.assertTrue(self.os.path.exists(file_path))
        with self.open(file_path, 'r') as fake_file:
            self.assertEqual('old contents', fake_file.read())
        # actual tests
        with self.open(file_path, 'w+') as fake_file:
            fake_file.write('new contents')
            fake_file.seek(0)
            self.assertTrue('new contents', fake_file.read())

    def testOpenWithWplusTruncation(self):
        # set up
        file_path = self.makePath('wplus_file')
        self.createFile(file_path, contents='old contents')
        self.assertTrue(self.os.path.exists(file_path))
        with self.open(file_path, 'r') as fake_file:
            self.assertEqual('old contents', fake_file.read())
        # actual tests
        with self.open(file_path, 'w+') as fake_file:
            fake_file.seek(0)
            self.assertEqual('', fake_file.read())

    def testOpenWithAppendFlag(self):
        # FIXME: under Windows, line endings are not handled correctly
        self.skipRealFsFailure(skipPosix=False)
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
        file_path = self.makePath('appendfile')
        self.createFile(file_path, contents=''.join(contents))
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

    def checkAppendWithAplus(self):
        file_path = self.makePath('aplus_file')
        self.createFile(file_path, contents='old contents')
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

    def testAppendWithAplusMacOs(self):
        self.checkMacOsOnly()
        self.checkAppendWithAplus()

    def testAppendWithAplusLinuxWindows(self):
        self.checkLinuxAndWindows()
        self.checkAppendWithAplus()

    def testAppendWithAplusReadWithLoop(self):
        # set up
        file_path = self.makePath('aplus_file')
        self.createFile(file_path, contents='old contents')
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

    def testReadEmptyFileWithAplus(self):
        file_path = self.makePath('aplus_file')
        with self.open(file_path, 'a+') as fake_file:
            self.assertEqual('', fake_file.read())

    def testReadWithRplus(self):
        # set up
        file_path = self.makePath('rplus_file')
        self.createFile(file_path, contents='old contents here')
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

    def testOpenStCtime(self):
        # set up
        self.skipRealFs()
        time.time = _DummyTime(100, 10)
        file_path = self.makePath('some_file')
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
        self.createFile(file_path)
        self.os.chmod(file_path, perm_bits)
        st = self.os.stat(file_path)
        self.assertModeEqual(perm_bits, st.st_mode)
        self.assertTrue(st.st_mode & stat.S_IFREG)
        self.assertFalse(st.st_mode & stat.S_IFDIR)

    def testOpenFlags700(self):
        # set up
        self.checkPosixOnly()
        file_path = self.makePath('target_file')
        self._CreateWithPermission(file_path, 0o700)
        # actual tests
        self.open(file_path, 'r').close()
        self.open(file_path, 'w').close()
        self.open(file_path, 'w+').close()
        self.assertRaises(ValueError, self.open, file_path, 'INV')

    def testOpenFlags400(self):
        # set up
        self.checkPosixOnly()
        file_path = self.makePath('target_file')
        self._CreateWithPermission(file_path, 0o400)
        # actual tests
        self.open(file_path, 'r').close()
        self.assertRaisesIOError(errno.EACCES, self.open, file_path, 'w')
        self.assertRaisesIOError(errno.EACCES, self.open, file_path, 'w+')

    def testOpenFlags200(self):
        # set up
        self.checkPosixOnly()
        file_path = self.makePath('target_file')
        self._CreateWithPermission(file_path, 0o200)
        # actual tests
        self.assertRaises(IOError, self.open, file_path, 'r')
        self.open(file_path, 'w').close()
        self.assertRaises(IOError, self.open, file_path, 'w+')

    def testOpenFlags100(self):
        # set up
        self.checkPosixOnly()
        file_path = self.makePath('target_file')
        self._CreateWithPermission(file_path, 0o100)
        # actual tests 4
        self.assertRaises(IOError, self.open, file_path, 'r')
        self.assertRaises(IOError, self.open, file_path, 'w')
        self.assertRaises(IOError, self.open, file_path, 'w+')

    def testFollowLinkRead(self):
        self.skipIfSymlinkNotSupported()
        link_path = self.makePath('foo', 'bar', 'baz')
        target = self.makePath('tarJAY')
        target_contents = 'real baz contents'
        self.createFile(target, contents=target_contents)
        self.createLink(link_path, target)
        self.assertEqual(target, self.os.readlink(link_path))
        fh = self.open(link_path, 'r')
        got_contents = fh.read()
        fh.close()
        self.assertEqual(target_contents, got_contents)

    def testFollowLinkWrite(self):
        self.skipIfSymlinkNotSupported()
        link_path = self.makePath('foo', 'bar', 'TBD')
        target = self.makePath('tarJAY')
        target_contents = 'real baz contents'
        self.createLink(link_path, target)
        self.assertFalse(self.os.path.exists(target))

        with self.open(link_path, 'w') as fh:
            fh.write(target_contents)
        with self.open(target, 'r') as fh:
            got_contents = fh.read()
        self.assertEqual(target_contents, got_contents)

    def testFollowIntraPathLinkWrite(self):
        # Test a link in the middle of of a file path.
        self.skipIfSymlinkNotSupported()
        link_path = self.os.path.join(
            self.base_path, 'foo', 'build', 'local_machine', 'output', '1')
        target = self.makePath('tmp', 'output', '1')
        self.createDirectory(self.makePath('tmp', 'output'))
        self.createLink(self.os.path.join(
            self.base_path, 'foo', 'build', 'local_machine'),
            self.makePath('tmp'))

        self.assertFalse(self.os.path.exists(link_path))
        self.assertFalse(self.os.path.exists(target))

        target_contents = 'real baz contents'
        with self.open(link_path, 'w') as fh:
            fh.write(target_contents)
        with self.open(target, 'r') as fh:
            got_contents = fh.read()
        self.assertEqual(target_contents, got_contents)

    def testOpenRaisesOnSymlinkLoop(self):
        # Regression test for #274
        self.checkPosixOnly()
        file_dir = self.makePath('foo')
        self.os.mkdir(file_dir)
        file_path = self.os.path.join(file_dir, 'baz')
        self.os.symlink(file_path, file_path)
        self.assertRaisesIOError(errno.ELOOP, self.open, file_path)

    def testFileDescriptorsForDifferentFiles(self):
        first_path = self.makePath('some_file1')
        self.createFile(first_path, contents='contents here1')
        second_path = self.makePath('some_file2')
        self.createFile(second_path, contents='contents here2')
        third_path = self.makePath('some_file3')
        self.createFile(third_path, contents='contents here3')

        with self.open(first_path) as fake_file1:
            with self.open(second_path) as fake_file2:
                with self.open(third_path) as fake_file3:
                    fileno2 = fake_file2.fileno()
                    self.assertGreater(fileno2, fake_file1.fileno())
                    self.assertGreater(fake_file3.fileno(), fileno2)

    def testFileDescriptorsForTheSameFileAreDifferent(self):
        first_path = self.makePath('some_file1')
        self.createFile(first_path, contents='contents here1')
        second_path = self.makePath('some_file2')
        self.createFile(second_path, contents='contents here2')
        with self.open(first_path) as fake_file1:
            with self.open(second_path) as fake_file2:
                with self.open(first_path) as fake_file1a:
                    fileno2 = fake_file2.fileno()
                    self.assertGreater(fileno2, fake_file1.fileno())
                    self.assertGreater(fake_file1a.fileno(), fileno2)

    def testReusedFileDescriptorsDoNotAffectOthers(self):
        first_path = self.makePath('some_file1')
        self.createFile(first_path, contents='contents here1')
        second_path = self.makePath('some_file2')
        self.createFile(second_path, contents='contents here2')
        third_path = self.makePath('some_file3')
        self.createFile(third_path, contents='contents here3')

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

    def testIntertwinedReadWrite(self):
        file_path = self.makePath('some_file')
        self.createFile(file_path)

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
        file_path = self.makePath('some_file')
        self.createFile(file_path)

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

    def testOpenIoErrors(self):
        file_path = self.makePath('some_file')
        self.createFile(file_path)

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

    def testOpenRaisesIOErrorIfParentIsFilePosix(self):
        self.checkPosixOnly()
        file_path = self.makePath('bar')
        self.createFile(file_path)
        file_path = self.os.path.join(file_path, 'baz')
        self.assertRaisesIOError(errno.ENOTDIR, self.open, file_path, 'w')

    def testOpenRaisesIOErrorIfParentIsFileWindows(self):
        self.checkWindowsOnly()
        file_path = self.makePath('bar')
        self.createFile(file_path)
        file_path = self.os.path.join(file_path, 'baz')
        self.assertRaisesIOError(errno.ENOENT, self.open, file_path, 'w')

    def testCanReadFromBlockDevice(self):
        self.skipRealFs()
        device_path = 'device'
        self.filesystem.CreateFile(device_path, stat.S_IFBLK
                                   | fake_filesystem.PERM_ALL)
        with self.open(device_path, 'r') as fh:
            self.assertEqual('', fh.read())

    def testTruncateFlushesContents(self):
        # Regression test for #285
        file_path = self.makePath('baz')
        self.createFile(file_path)
        with self.open(file_path, 'w') as f0:
            f0.write('test')
            f0.truncate()
            self.assertEqual(4, self.os.path.getsize(file_path))

    def testThatReadOverEndDoesNotResetPosition(self):
        # Regression test for #286
        file_path = self.makePath('baz')
        self.createFile(file_path)
        with self.open(file_path) as f0:
            f0.seek(2)
            f0.read()
            self.assertEqual(2, f0.tell())

    def testAccessingClosedFileRaises(self):
        # Regression test for #275, #280
        if self.is_pypy:
            raise unittest.SkipTest('Different exceptions with PyPy')
        file_path = self.makePath('foo')
        self.createFile(file_path, contents=b'test')
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
    def testNextRaisesOnClosedFile(self):
        # Regression test for #284
        file_path = self.makePath('foo')
        with self.open(file_path, 'w') as f0:
            f0.write('test')
            f0.seek(0)
            self.assertRaises(IOError, lambda: f0.next())

    def testAccessingOpenFileWithAnotherHandleRaises(self):
        # Regression test for #282
        if self.is_pypy:
            raise unittest.SkipTest('Different exceptions with PyPy')
        file_path = self.makePath('foo')
        f0 = self.os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        fake_file = self.open(file_path, 'r')
        fake_file.close()
        self.assertRaises(ValueError, lambda: fake_file.read(1))
        self.assertRaises(ValueError, lambda: fake_file.write('a'))
        self.os.close(f0)

    def testTellFlushesUnderMacOs(self):
        # Regression test for #288
        self.checkMacOsOnly()
        file_path = self.makePath('foo')
        with self.open(file_path, 'w') as f0:
            f0.write('test')
            self.assertEqual(4, f0.tell())
            self.assertEqual(4, self.os.path.getsize(file_path))

    def testTellFlushesInPython3(self):
        # Regression test for #288
        self.checkLinuxAndWindows()
        file_path = self.makePath('foo')
        with self.open(file_path, 'w') as f0:
            f0.write('test')
            self.assertEqual(4, f0.tell())
            expected = 0 if sys.version_info < (3,) else 4
            self.assertEqual(expected, self.os.path.getsize(file_path))

    def testReadFlushesUnderPosix(self):
        # Regression test for #278
        self.checkPosixOnly()
        file_path = self.makePath('foo')
        with self.open(file_path, 'a+') as f0:
            f0.write('test')
            self.assertEqual('', f0.read())
            self.assertEqual(4, self.os.path.getsize(file_path))

    def testReadFlushesUnderWindowsInPython3(self):
        # Regression test for #278
        self.checkWindowsOnly()
        file_path = self.makePath('foo')
        with self.open(file_path, 'w+') as f0:
            f0.write('test')
            f0.read()
            expected = 0 if sys.version_info[0] < 3 else 4
            self.assertEqual(expected, self.os.path.getsize(file_path))

    def testSeekFlushes(self):
        # Regression test for #290
        file_path = self.makePath('foo')
        with self.open(file_path, 'w') as f0:
            f0.write('test')
            self.assertEqual(0, self.os.path.getsize(file_path))
            f0.seek(3)
            self.assertEqual(4, self.os.path.getsize(file_path))

    def testTruncateFlushes(self):
        # Regression test for #291
        file_path = self.makePath('foo')
        with self.open(file_path, 'a') as f0:
            f0.write('test')
            self.assertEqual(0, self.os.path.getsize(file_path))
            f0.truncate()
            self.assertEqual(4, self.os.path.getsize(file_path))

    def checkSeekOutsideAndTruncateSetsSize(self, mode):
        # Regression test for #294 and #296
        file_path = self.makePath('baz')
        with self.open(file_path, mode) as f0:
            f0.seek(1)
            f0.truncate()
            self.assertEqual(1, f0.tell())
            self.assertEqual(1, self.os.path.getsize(file_path))
            f0.seek(1)
            self.assertEqual(1, self.os.path.getsize(file_path))
        self.assertEqual(1, self.os.path.getsize(file_path))

    def testSeekOutsideAndTruncateSetsSizeInWriteMode(self):
        # Regression test for #294
        self.checkSeekOutsideAndTruncateSetsSize('w')

    def testSeekOutsideAndTruncateSetsSizeInAppendMode(self):
        # Regression test for #295
        self.checkSeekOutsideAndTruncateSetsSize('a')

    def testClosingClosedFileDoesNothing(self):
        # Regression test for #299
        file_path = self.makePath('baz')
        f0 = self.open(file_path, 'w')
        f0.close()
        with self.open(file_path) as f1:
            # would close f1 if not handled
            f0.close()
            self.assertEqual('', f1.read())

    def testTruncateFlushesZeros(self):
        # Regression test for #301
        file_path = self.makePath('baz')
        with self.open(file_path, 'w') as f0:
            with self.open(file_path) as f1:
                f0.seek(1)
                f0.truncate()
                self.assertEqual('\0', f1.read())

    def testByteFilename(self):
        file_path = self.makePath(b'test')
        with self.open(file_path, 'wb') as f:
            f.write(b'test')
        with self.open(file_path, 'rb') as f:
            self.assertEqual(b'test', f.read())

    def testUnicodeFilename(self):
        file_path = self.makePath(u'тест')
        with self.open(file_path, 'wb') as f:
            f.write(b'test')
        with self.open(file_path, 'rb') as f:
            self.assertEqual(b'test', f.read())


class RealFileOpenTest(FakeFileOpenTest):
    def useRealFs(self):
        return True


class OpenFileWithEncodingTest(FakeFileOpenTestBase):
    """Tests that are similar to some open file tests above but using
    an explicit text encoding."""

    def setUp(self):
        super(OpenFileWithEncodingTest, self).setUp()
        if self.useRealFs():
            self.open = io.open
        else:
            self.open = fake_filesystem.FakeFileOpen(self.filesystem,
                                                     use_io=True)
        self.file_path = self.makePath('foo')

    def testWriteStrReadBytes(self):
        str_contents = u'علي بابا'
        with self.open(self.file_path, 'w', encoding='arabic') as f:
            f.write(str_contents)
        with self.open(self.file_path, 'rb') as f:
            contents = f.read()
        self.assertEqual(str_contents, contents.decode('arabic'))

    def testWriteStrErrorModes(self):
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

    def testReadStrErrorModes(self):
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

    def testWriteAndReadStr(self):
        str_contents = u'علي بابا'
        with self.open(self.file_path, 'w', encoding='arabic') as f:
            f.write(str_contents)
        with self.open(self.file_path, 'r', encoding='arabic') as f:
            contents = f.read()
        self.assertEqual(str_contents, contents)

    def testCreateFileWithAppend(self):
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

    def testAppendExistingFile(self):
        contents = [
            u'Оригинальное содержание'
            u'Дополнительное содержание',
        ]
        self.createFile(self.file_path, contents=contents[0],
                        encoding='cyrillic')
        with self.open(self.file_path, 'a', encoding='cyrillic') as fake_file:
            for line in contents[1:]:
                fake_file.write(line + '\n')
        with self.open(self.file_path, encoding='cyrillic') as fake_file:
            result = [line.rstrip() for line in fake_file]
        self.assertEqual(contents, result)

    def testOpenWithWplus(self):
        self.createFile(self.file_path,
                        contents=u'старое содержание',
                        encoding='cyrillic')
        with self.open(self.file_path, 'r', encoding='cyrillic') as fake_file:
            self.assertEqual(u'старое содержание', fake_file.read())

        with self.open(self.file_path, 'w+', encoding='cyrillic') as fake_file:
            fake_file.write(u'новое содержание')
            fake_file.seek(0)
            self.assertTrue(u'новое содержание', fake_file.read())

    def testOpenWithAppendFlag(self):
        # FIXME: under Windows, line endings are not handled correctly
        self.skipRealFsFailure(skipPosix=False)
        contents = [
            u'Калинка,\n',
            u'калинка,\n',
            u'калинка моя,\n'
        ]
        additional_contents = [
            u'В саду ягода-малинка,\n',
            u'малинка моя.\n'
        ]
        self.createFile(self.file_path, contents=''.join(contents),
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

    def testAppendWithAplus(self):
        self.createFile(self.file_path,
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

    def testReadWithRplus(self):
        self.createFile(self.file_path,
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
    def useRealFs(self):
        return True


class OpenWithFileDescriptorTest(FakeFileOpenTestBase):
    @unittest.skipIf(sys.version_info < (3, 0),
                     'only tested on 3.0 or greater')
    def testOpenWithFileDescriptor(self):
        file_path = self.makePath('this', 'file')
        self.createFile(file_path)
        fd = self.os.open(file_path, os.O_CREAT)
        self.assertEqual(fd, self.open(fd, 'r').fileno())

    @unittest.skipIf(sys.version_info < (3, 0),
                     'only tested on 3.0 or greater')
    def testClosefdWithFileDescriptor(self):
        file_path = self.makePath('this', 'file')
        self.createFile(file_path)
        fd = self.os.open(file_path, os.O_CREAT)
        fh = self.open(fd, 'r', closefd=False)
        fh.close()
        self.assertIsNotNone(self.filesystem.open_files[fd])
        fh = self.open(fd, 'r', closefd=True)
        fh.close()
        self.assertIsNone(self.filesystem.open_files[fd])


class OpenWithRealFileDescriptorTest(FakeFileOpenTestBase):
    def useRealFs(self):
        return True


class OpenWithBinaryFlagsTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='!')
        self.open = fake_filesystem.FakeFileOpen(self.filesystem)
        self.os = fake_filesystem.FakeOsModule(self.filesystem)
        self.file_path = 'some_file'
        self.file_contents = b'real binary contents: \x1f\x8b'
        self.filesystem.CreateFile(self.file_path, contents=self.file_contents)

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

    def testReadBinary(self):
        fake_file = self.OpenFakeFile('rb')
        self.assertEqual(self.file_contents, fake_file.read())

    def testWriteBinary(self):
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

    def testWriteAndReadBinary(self):
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
        self.filesystem.CreateFile(self.file_path, contents=self.file_contents)
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

    def testReadText(self):
        fake_file = self.OpenFakeFile('rt')
        self.assertEqual(self.read_contents, fake_file.read())

    def testReadUniversalNewlines(self):
        fake_file = self.OpenFakeFile('rU')
        self.assertEqual(self.read_contents, fake_file.read())

    def testUniversalNewlines(self):
        fake_file = self.OpenFakeFile('U')
        self.assertEqual(self.read_contents, fake_file.read())

    def testWriteText(self):
        fake_file = self.OpenFileAndSeek('wt')
        self.assertEqual(0, fake_file.tell())
        fake_file = self.WriteAndReopenFile(fake_file)
        self.assertEqual(self.read_contents, fake_file.read())

    def testWriteAndReadTextBinary(self):
        fake_file = self.OpenFileAndSeek('w+bt')
        self.assertEqual(0, fake_file.tell())
        if sys.version_info >= (3, 0):
            self.assertRaises(TypeError, fake_file.write, self.file_contents)
        else:
            fake_file = self.WriteAndReopenFile(fake_file, mode='rb')
            self.assertEqual(self.file_contents, fake_file.read())


class OpenWithInvalidFlagsTest(FakeFileOpenTestBase):
    def testCapitalR(self):
        self.assertRaises(ValueError, self.open, 'some_file', 'R')

    def testCapitalW(self):
        self.assertRaises(ValueError, self.open, 'some_file', 'W')

    def testCapitalA(self):
        self.assertRaises(ValueError, self.open, 'some_file', 'A')

    def testLowerU(self):
        self.assertRaises(ValueError, self.open, 'some_file', 'u')

    def testLowerRw(self):
        if self.is_python2 and sys.platform != 'win32':
            self.assertRaisesIOError(
                errno.ENOENT, self.open, 'some_file', 'rw')
        else:
            self.assertRaises(ValueError, self.open, 'some_file', 'rw')


class OpenWithInvalidFlagsRealFsTest(OpenWithInvalidFlagsTest):
    def useRealFs(self):
        return True


class ResolvePathTest(FakeFileOpenTestBase):
    def __WriteToFile(self, file_name):
        fh = self.open(file_name, 'w')
        fh.write('x')
        fh.close()

    def testNoneFilepathRaisesTypeError(self):
        self.assertRaises(TypeError, self.open, None, 'w')

    def testEmptyFilepathRaisesIOError(self):
        self.assertRaises(IOError, self.open, '', 'w')

    def testNormalPath(self):
        self.__WriteToFile('foo')
        self.assertTrue(self.filesystem.Exists('foo'))

    def testLinkWithinSameDirectory(self):
        self.skipIfSymlinkNotSupported()
        final_target = '!foo!baz'
        self.filesystem.CreateLink('!foo!bar', 'baz')
        self.__WriteToFile('!foo!bar')
        self.assertTrue(self.filesystem.Exists(final_target))
        self.assertEqual(1, self.os.stat(final_target)[stat.ST_SIZE])

    def testLinkToSubDirectory(self):
        self.skipIfSymlinkNotSupported()
        final_target = '!foo!baz!bip'
        self.filesystem.CreateDirectory('!foo!baz')
        self.filesystem.CreateLink('!foo!bar', 'baz!bip')
        self.__WriteToFile('!foo!bar')
        self.assertTrue(self.filesystem.Exists(final_target))
        self.assertEqual(1, self.os.stat(final_target)[stat.ST_SIZE])
        self.assertTrue(self.filesystem.Exists('!foo!baz'))
        # Make sure that intermediate directory got created.
        new_dir = self.filesystem.GetObject('!foo!baz')
        self.assertTrue(stat.S_IFDIR & new_dir.st_mode)

    def testLinkToParentDirectory(self):
        self.skipIfSymlinkNotSupported()
        final_target = '!baz!bip'
        self.filesystem.CreateDirectory('!foo')
        self.filesystem.CreateDirectory('!baz')
        self.filesystem.CreateLink('!foo!bar', '..!baz')
        self.__WriteToFile('!foo!bar!bip')
        self.assertTrue(self.filesystem.Exists(final_target))
        self.assertEqual(1, self.os.stat(final_target)[stat.ST_SIZE])
        self.assertTrue(self.filesystem.Exists('!foo!bar'))

    def testLinkToAbsolutePath(self):
        self.skipIfSymlinkNotSupported()
        final_target = '!foo!baz!bip'
        self.filesystem.CreateDirectory('!foo!baz')
        self.filesystem.CreateLink('!foo!bar', final_target)
        self.__WriteToFile('!foo!bar')
        self.assertTrue(self.filesystem.Exists(final_target))

    def testRelativeLinksWorkAfterChdir(self):
        self.skipIfSymlinkNotSupported()
        final_target = '!foo!baz!bip'
        self.filesystem.CreateDirectory('!foo!baz')
        self.filesystem.CreateLink('!foo!bar', '.!baz!bip')
        self.assertEqual(final_target,
                         self.filesystem.ResolvePath('!foo!bar'))

        self.assertTrue(self.os.path.islink('!foo!bar'))
        self.os.chdir('!foo')
        self.assertEqual('!foo', self.os.getcwd())
        self.assertTrue(self.os.path.islink('bar'))

        self.assertEqual('!foo!baz!bip',
                         self.filesystem.ResolvePath('bar'))

        self.__WriteToFile('!foo!bar')
        self.assertTrue(self.filesystem.Exists(final_target))

    def testAbsoluteLinksWorkAfterChdir(self):
        self.skipIfSymlinkNotSupported()
        final_target = '!foo!baz!bip'
        self.filesystem.CreateDirectory('!foo!baz')
        self.filesystem.CreateLink('!foo!bar', final_target)
        self.assertEqual(final_target,
                         self.filesystem.ResolvePath('!foo!bar'))

        os_module = fake_filesystem.FakeOsModule(self.filesystem)
        self.assertTrue(os_module.path.islink('!foo!bar'))
        os_module.chdir('!foo')
        self.assertEqual('!foo', os_module.getcwd())
        self.assertTrue(os_module.path.islink('bar'))

        self.assertEqual('!foo!baz!bip',
                         self.filesystem.ResolvePath('bar'))

        self.__WriteToFile('!foo!bar')
        self.assertTrue(self.filesystem.Exists(final_target))

    def testChdirThroughRelativeLink(self):
        self.skipIfSymlinkNotSupported()
        self.filesystem.CreateDirectory('!x!foo')
        self.filesystem.CreateDirectory('!x!bar')
        self.filesystem.CreateLink('!x!foo!bar', '..!bar')
        self.assertEqual('!x!bar', self.filesystem.ResolvePath('!x!foo!bar'))

        self.os.chdir('!x!foo')
        self.assertEqual('!x!foo', self.os.getcwd())
        self.assertEqual('!x!bar', self.filesystem.ResolvePath('bar'))

        self.os.chdir('bar')
        self.assertEqual('!x!bar', self.os.getcwd())

    @unittest.skipIf(sys.version_info < (3, 3),
                     'file descriptor as path new in Python 3.3')
    def testChdirUsesOpenFdAsPath(self):
        self.filesystem.is_windows_fs = False
        self.assertRaisesOSError(errno.EBADF, self.os.chdir, 5)
        dir_path = '!foo!bar'
        self.filesystem.CreateDirectory(dir_path)

        path_des = self.os.open(dir_path, os.O_RDONLY)
        self.os.chdir(path_des)
        self.os.close(path_des)
        self.assertEqual(dir_path, self.os.getcwd())

    def testReadLinkToLink(self):
        # Write into the final link target and read back from a file which will
        # point to that.
        self.skipIfSymlinkNotSupported()
        self.filesystem.CreateLink('!foo!bar', 'link')
        self.filesystem.CreateLink('!foo!link', 'baz')
        self.__WriteToFile('!foo!baz')
        fh = self.open('!foo!bar', 'r')
        self.assertEqual('x', fh.read())

    def testWriteLinkToLink(self):
        self.skipIfSymlinkNotSupported()
        final_target = '!foo!baz'
        self.filesystem.CreateLink('!foo!bar', 'link')
        self.filesystem.CreateLink('!foo!link', 'baz')
        self.__WriteToFile('!foo!bar')
        self.assertTrue(self.filesystem.Exists(final_target))

    def testMultipleLinks(self):
        self.skipIfSymlinkNotSupported()
        self.os.makedirs('!a!link1!c!link2')

        self.filesystem.CreateLink('!a!b', 'link1')
        self.assertEqual('!a!link1', self.filesystem.ResolvePath('!a!b'))
        self.assertEqual('!a!link1!c', self.filesystem.ResolvePath('!a!b!c'))

        self.filesystem.CreateLink('!a!link1!c!d', 'link2')
        self.assertTrue(self.filesystem.Exists('!a!link1!c!d'))
        self.assertTrue(self.filesystem.Exists('!a!b!c!d'))

        final_target = '!a!link1!c!link2!e'
        self.assertFalse(self.filesystem.Exists(final_target))
        self.__WriteToFile('!a!b!c!d!e')
        self.assertTrue(self.filesystem.Exists(final_target))

    def testUtimeLink(self):
        """os.utime() and os.stat() via symbolic link (issue #49)"""
        self.skipIfSymlinkNotSupported()
        self.filesystem.CreateDirectory('!foo!baz')
        self.__WriteToFile('!foo!baz!bip')
        link_name = '!foo!bar'
        self.filesystem.CreateLink(link_name, '!foo!baz!bip')

        self.os.utime(link_name, (1, 2))
        st = self.os.stat(link_name)
        self.assertEqual(1, st.st_atime)
        self.assertEqual(2, st.st_mtime)
        self.os.utime(link_name, (3, 4))
        st = self.os.stat(link_name)
        self.assertEqual(3, st.st_atime)
        self.assertEqual(4, st.st_mtime)

    def testTooManyLinks(self):
        self.filesystem.is_windows_fs = False
        self.filesystem.CreateLink('!a!loop', 'loop')
        self.assertFalse(self.filesystem.Exists('!a!loop'))

    def testThatDriveLettersArePreserved(self):
        self.filesystem.is_windows_fs = True
        self.assertEqual('c:!foo!bar',
                         self.filesystem.ResolvePath('c:!foo!!bar'))

    @unittest.skipIf(sys.version_info < (2, 7, 8),
                     'UNC path support since Python 2.7.8')
    def testThatUncPathsArePreserved(self):
        self.filesystem.is_windows_fs = True
        self.assertEqual('!!foo!bar!baz',
                         self.filesystem.ResolvePath('!!foo!bar!baz!!'))


class PathManipulationTestBase(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='|')


class CollapsePathPipeSeparatorTest(PathManipulationTestBase):
    """Tests CollapsePath (mimics os.path.normpath) using |
    as path separator."""

    def testEmptyPathBecomesDotPath(self):
        self.assertEqual('.', self.filesystem.CollapsePath(''))

    def testDotPathUnchanged(self):
        self.assertEqual('.', self.filesystem.CollapsePath('.'))

    def testSlashesAreNotCollapsed(self):
        """Tests that '/' is not treated specially if the
        path separator is '|'.

    In particular, multiple slashes should not be collapsed.
    """
        self.assertEqual('/', self.filesystem.CollapsePath('/'))
        self.assertEqual('/////', self.filesystem.CollapsePath('/////'))

    def testRootPath(self):
        self.assertEqual('|', self.filesystem.CollapsePath('|'))

    def testMultipleSeparatorsCollapsedIntoRootPath(self):
        self.assertEqual('|', self.filesystem.CollapsePath('|||||'))

    def testAllDotPathsRemovedButOne(self):
        self.assertEqual('.', self.filesystem.CollapsePath('.|.|.|.'))

    def testAllDotPathsRemovedIfAnotherPathComponentExists(self):
        self.assertEqual('|', self.filesystem.CollapsePath('|.|.|.|'))
        self.assertEqual('foo|bar',
                         self.filesystem.CollapsePath('foo|.|.|.|bar'))

    def testIgnoresUpLevelReferencesStartingFromRoot(self):
        self.assertEqual('|', self.filesystem.CollapsePath('|..|..|..|'))
        self.assertEqual(
            '|', self.filesystem.CollapsePath('|..|..|foo|bar|..|..|'))
        # shall not be handled as UNC path
        self.filesystem.is_windows_fs = False
        self.assertEqual('|', self.filesystem.CollapsePath('||..|.|..||'))

    def testConservesUpLevelReferencesStartingFromCurrentDirectory(self):
        self.assertEqual(
            '..|..', self.filesystem.CollapsePath('..|foo|bar|..|..|..'))

    def testCombineDotAndUpLevelReferencesInAbsolutePath(self):
        self.assertEqual(
            '|yes', self.filesystem.CollapsePath('|||||.|..|||yes|no|..|.|||'))

    def testDotsInPathCollapsesToLastPath(self):
        self.assertEqual(
            'bar', self.filesystem.CollapsePath('foo|..|bar'))
        self.assertEqual(
            'bar', self.filesystem.CollapsePath('foo|..|yes|..|no|..|bar'))


class SplitPathTest(PathManipulationTestBase):
    """Tests SplitPath (which mimics os.path.split)
    using | as path separator."""

    def testEmptyPath(self):
        self.assertEqual(('', ''), self.filesystem.SplitPath(''))

    def testNoSeparators(self):
        self.assertEqual(('', 'ab'), self.filesystem.SplitPath('ab'))

    def testSlashesDoNotSplit(self):
        """Tests that '/' is not treated specially if the
        path separator is '|'."""
        self.assertEqual(('', 'a/b'), self.filesystem.SplitPath('a/b'))

    def testEliminateTrailingSeparatorsFromHead(self):
        self.assertEqual(('a', 'b'), self.filesystem.SplitPath('a|b'))
        self.assertEqual(('a', 'b'), self.filesystem.SplitPath('a|||b'))
        self.assertEqual(('|a', 'b'), self.filesystem.SplitPath('|a||b'))
        self.assertEqual(('a|b', 'c'), self.filesystem.SplitPath('a|b|c'))
        self.assertEqual(('|a|b', 'c'), self.filesystem.SplitPath('|a|b|c'))

    def testRootSeparatorIsNotStripped(self):
        self.assertEqual(('|', ''), self.filesystem.SplitPath('|||'))
        self.assertEqual(('|', 'a'), self.filesystem.SplitPath('|a'))
        self.assertEqual(('|', 'a'), self.filesystem.SplitPath('|||a'))

    def testEmptyTailIfPathEndsInSeparator(self):
        self.assertEqual(('a|b', ''), self.filesystem.SplitPath('a|b|'))

    def testEmptyPathComponentsArePreservedInHead(self):
        self.assertEqual(('|a||b', 'c'), self.filesystem.SplitPath('|a||b||c'))


class JoinPathTest(PathManipulationTestBase):
    """Tests JoinPath (which mimics os.path.join) using | as path separator."""

    def testOneEmptyComponent(self):
        self.assertEqual('', self.filesystem.JoinPaths(''))

    def testMultipleEmptyComponents(self):
        self.assertEqual('', self.filesystem.JoinPaths('', '', ''))

    def testSeparatorsNotStrippedFromSingleComponent(self):
        self.assertEqual('||a||', self.filesystem.JoinPaths('||a||'))

    def testOneSeparatorAddedBetweenComponents(self):
        self.assertEqual('a|b|c|d',
                         self.filesystem.JoinPaths('a', 'b', 'c', 'd'))

    def testNoSeparatorAddedForComponentsEndingInSeparator(self):
        self.assertEqual('a|b|c', self.filesystem.JoinPaths('a|', 'b|', 'c'))
        self.assertEqual('a|||b|||c',
                         self.filesystem.JoinPaths('a|||', 'b|||', 'c'))

    def testComponentsPrecedingAbsoluteComponentAreIgnored(self):
        self.assertEqual('|c|d',
                         self.filesystem.JoinPaths('a', '|b', '|c', 'd'))

    def testOneSeparatorAddedForTrailingEmptyComponents(self):
        self.assertEqual('a|', self.filesystem.JoinPaths('a', ''))
        self.assertEqual('a|', self.filesystem.JoinPaths('a', '', ''))

    def testNoSeparatorAddedForLeadingEmptyComponents(self):
        self.assertEqual('a', self.filesystem.JoinPaths('', 'a'))

    def testInternalEmptyComponentsIgnored(self):
        self.assertEqual('a|b', self.filesystem.JoinPaths('a', '', 'b'))
        self.assertEqual('a|b|', self.filesystem.JoinPaths('a|', '', 'b|'))


class PathSeparatorTest(TestCase):
    def testOsPathSepMatchesFakeFilesystemSeparator(self):
        filesystem = fake_filesystem.FakeFilesystem(path_separator='!')
        fake_os = fake_filesystem.FakeOsModule(filesystem)
        self.assertEqual('!', fake_os.sep)
        self.assertEqual('!', fake_os.path.sep)


class NormalizeCaseTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.filesystem.is_case_sensitive = False

    def testNormalizeCase(self):
        self.filesystem.CreateFile('/Foo/Bar')
        self.assertEqual('/Foo/Bar', self.filesystem.NormalizeCase('/foo/bar'))
        self.assertEqual('/Foo/Bar', self.filesystem.NormalizeCase('/FOO/BAR'))

    def testNormalizeCaseForDrive(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.CreateFile('C:/Foo/Bar')
        self.assertEqual('C:/Foo/Bar',
                         self.filesystem.NormalizeCase('c:/foo/bar'))
        self.assertEqual('C:/Foo/Bar',
                         self.filesystem.NormalizeCase('C:/FOO/BAR'))

    def testNormalizeCaseForNonExistingFile(self):
        self.filesystem.CreateDirectory('/Foo/Bar')
        self.assertEqual('/Foo/Bar/baz',
                         self.filesystem.NormalizeCase('/foo/bar/baz'))
        self.assertEqual('/Foo/Bar/BAZ',
                         self.filesystem.NormalizeCase('/FOO/BAR/BAZ'))

    @unittest.skipIf(not TestCase.is_windows,
                     'Regression test for Windows problem only')
    def testNormalizeCaseForLazilyAddedEmptyFile(self):
        # regression test for specific issue with added empty real files
        filesystem = fake_filesystem.FakeFilesystem()
        real_dir_path = os.path.join(os.path.dirname(__file__), 'pyfakefs')
        filesystem.add_real_directory(real_dir_path)
        initPyPath = os.path.join(real_dir_path, '__init__.py')
        self.assertEqual(initPyPath,
                         filesystem.NormalizeCase(initPyPath.upper()))


class AlternativePathSeparatorTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='!')
        self.filesystem.alternative_path_separator = '?'

    def testInitialValue(self):
        filesystem = fake_filesystem.FakeFilesystem()
        if self.is_windows:
            self.assertEqual('/', filesystem.alternative_path_separator)
        else:
            self.assertIsNone(filesystem.alternative_path_separator)

        filesystem = fake_filesystem.FakeFilesystem(path_separator='/')
        self.assertIsNone(filesystem.alternative_path_separator)

    def testAltSep(self):
        fake_os = fake_filesystem.FakeOsModule(self.filesystem)
        self.assertEqual('?', fake_os.altsep)
        self.assertEqual('?', fake_os.path.altsep)

    def testCollapsePathWithMixedSeparators(self):
        self.assertEqual('!foo!bar', self.filesystem.CollapsePath('!foo??bar'))

    def testNormalizePathWithMixedSeparators(self):
        path = 'foo?..?bar'
        self.assertEqual('!bar', self.filesystem.NormalizePath(path))

    def testExistsWithMixedSeparators(self):
        self.filesystem.CreateFile('?foo?bar?baz')
        self.filesystem.CreateFile('!foo!bar!xyzzy!plugh')
        self.assertTrue(self.filesystem.Exists('!foo!bar!baz'))
        self.assertTrue(self.filesystem.Exists('?foo?bar?xyzzy?plugh'))


class DriveLetterSupportTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='!')
        self.filesystem.is_windows_fs = True

    def testInitialValue(self):
        filesystem = fake_filesystem.FakeFilesystem()
        if self.is_windows:
            self.assertTrue(filesystem.is_windows_fs)
        else:
            self.assertFalse(filesystem.is_windows_fs)

    def testCollapsePath(self):
        self.assertEqual('c:!foo!bar',
                         self.filesystem.CollapsePath('c:!!foo!!bar'))

    @unittest.skipIf(sys.version_info < (2, 7, 8),
                     'UNC path support since Python 2.7.8')
    def testCollapseUncPath(self):
        self.assertEqual('!!foo!bar!baz',
                         self.filesystem.CollapsePath('!!foo!bar!!baz!!'))

    def testNormalizePathStr(self):
        self.filesystem.cwd = u''
        self.assertEqual(u'c:!foo!bar',
                         self.filesystem.NormalizePath(u'c:!foo!!bar'))
        self.filesystem.cwd = u'c:!foo'
        self.assertEqual(u'c:!foo!bar', self.filesystem.NormalizePath(u'bar'))

    def testNormalizePathBytes(self):
        self.filesystem.cwd = b''
        self.assertEqual(b'c:!foo!bar',
                         self.filesystem.NormalizePath(b'c:!foo!!bar'))
        self.filesystem.cwd = b'c:!foo'
        self.assertEqual(b'c:!foo!bar', self.filesystem.NormalizePath(b'bar'))

    def testSplitPathStr(self):
        self.assertEqual((u'c:!foo', u'bar'),
                         self.filesystem.SplitPath(u'c:!foo!bar'))
        self.assertEqual((u'c:', u'foo'), self.filesystem.SplitPath(u'c:!foo'))

    def testSplitPathBytes(self):
        self.assertEqual((b'c:!foo', b'bar'),
                         self.filesystem.SplitPath(b'c:!foo!bar'))
        self.assertEqual((b'c:', b'foo'), self.filesystem.SplitPath(b'c:!foo'))

    def testCharactersBeforeRootIgnoredInJoinPaths(self):
        self.assertEqual('c:d', self.filesystem.JoinPaths('b', 'c:', 'd'))

    def testResolvePath(self):
        self.assertEqual('c:!foo!bar',
                         self.filesystem.ResolvePath('c:!foo!bar'))

    def testGetPathComponents(self):
        self.assertEqual(['c:', 'foo', 'bar'],
                         self.filesystem.GetPathComponents('c:!foo!bar'))
        self.assertEqual(['c:'], self.filesystem.GetPathComponents('c:'))

    def testSplitDriveStr(self):
        self.assertEqual((u'c:', u'!foo!bar'),
                         self.filesystem.SplitDrive(u'c:!foo!bar'))
        self.assertEqual((u'', u'!foo!bar'),
                         self.filesystem.SplitDrive(u'!foo!bar'))
        self.assertEqual((u'c:', u'foo!bar'),
                         self.filesystem.SplitDrive(u'c:foo!bar'))
        self.assertEqual((u'', u'foo!bar'),
                         self.filesystem.SplitDrive(u'foo!bar'))

    def testSplitDriveBytes(self):
        self.assertEqual((b'c:', b'!foo!bar'),
                         self.filesystem.SplitDrive(b'c:!foo!bar'))
        self.assertEqual((b'', b'!foo!bar'),
                         self.filesystem.SplitDrive(b'!foo!bar'))

    @unittest.skipIf(sys.version_info < (2, 7, 8),
                     'UNC path support since Python 2.7.8')
    def testSplitDriveWithUncPath(self):
        self.assertEqual(('!!foo!bar', '!baz'),
                         self.filesystem.SplitDrive('!!foo!bar!baz'))
        self.assertEqual(('', '!!foo'), self.filesystem.SplitDrive('!!foo'))
        self.assertEqual(('', '!!foo!!bar'),
                         self.filesystem.SplitDrive('!!foo!!bar'))
        self.assertEqual(('!!foo!bar', '!!'),
                         self.filesystem.SplitDrive('!!foo!bar!!'))


class DiskSpaceTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='!',
                                                         total_size=100)
        self.os = fake_filesystem.FakeOsModule(self.filesystem)

    def testDiskUsageOnFileCreation(self):
        fake_open = fake_filesystem.FakeFileOpen(self.filesystem)

        total_size = 100
        self.filesystem.AddMountPoint('mount', total_size)

        def create_too_large_file():
            with fake_open('!mount!file', 'w') as dest:
                dest.write('a' * (total_size + 1))

        self.assertRaises((OSError, IOError), create_too_large_file)

        self.assertEqual(0, self.filesystem.GetDiskUsage('!mount').used)

        with fake_open('!mount!file', 'w') as dest:
            dest.write('a' * total_size)

        self.assertEqual(total_size,
                         self.filesystem.GetDiskUsage('!mount').used)

    def testFileSystemSizeAfterLargeFileCreation(self):
        filesystem = fake_filesystem.FakeFilesystem(path_separator='!',
                                                    total_size=1024 * 1024 * 1024 * 100)
        filesystem.CreateFile('!foo!baz', st_size=1024 * 1024 * 1024 * 10)
        self.assertEqual((1024 * 1024 * 1024 * 100,
                          1024 * 1024 * 1024 * 10,
                          1024 * 1024 * 1024 * 90), filesystem.GetDiskUsage())

    def testFileSystemSizeAfterBinaryFileCreation(self):
        self.filesystem.CreateFile('!foo!bar', contents=b'xyzzy')
        self.assertEqual((100, 5, 95), self.filesystem.GetDiskUsage())

    def testFileSystemSizeAfterAsciiStringFileCreation(self):
        self.filesystem.CreateFile('!foo!bar', contents=u'complicated')
        self.assertEqual((100, 11, 89), self.filesystem.GetDiskUsage())

    def testFileSystemSizeAfter2ByteUnicodeStringFileCreation(self):
        self.filesystem.CreateFile('!foo!bar', contents=u'сложно',
                                   encoding='utf-8')
        self.assertEqual((100, 12, 88), self.filesystem.GetDiskUsage())

    def testFileSystemSizeAfter3ByteUnicodeStringFileCreation(self):
        self.filesystem.CreateFile('!foo!bar', contents=u'複雑',
                                   encoding='utf-8')
        self.assertEqual((100, 6, 94), self.filesystem.GetDiskUsage())

    def testFileSystemSizeAfterFileDeletion(self):
        self.filesystem.CreateFile('!foo!bar', contents=b'xyzzy')
        self.filesystem.CreateFile('!foo!baz', st_size=20)
        self.filesystem.RemoveObject('!foo!bar')
        self.assertEqual((100, 20, 80), self.filesystem.GetDiskUsage())

    def testFileSystemSizeAfterDirectoryRemoval(self):
        self.filesystem.CreateFile('!foo!bar', st_size=10)
        self.filesystem.CreateFile('!foo!baz', st_size=20)
        self.filesystem.CreateFile('!foo1!bar', st_size=40)
        self.filesystem.RemoveObject('!foo')
        self.assertEqual((100, 40, 60), self.filesystem.GetDiskUsage())

    def testCreatingFileWithFittingContent(self):
        initial_usage = self.filesystem.GetDiskUsage()

        try:
            self.filesystem.CreateFile('!foo!bar', contents=b'a' * 100)
        except IOError:
            self.fail(
                'File with contents fitting into disk space could not be written.')

        self.assertEqual(initial_usage.used + 100,
                         self.filesystem.GetDiskUsage().used)

    def testCreatingFileWithContentTooLarge(self):
        def create_large_file():
            self.filesystem.CreateFile('!foo!bar', contents=b'a' * 101)

        initial_usage = self.filesystem.GetDiskUsage()

        self.assertRaises(IOError, create_large_file)

        self.assertEqual(initial_usage, self.filesystem.GetDiskUsage())

    def testCreatingFileWithFittingSize(self):
        initial_usage = self.filesystem.GetDiskUsage()

        try:
            self.filesystem.CreateFile('!foo!bar', st_size=100)
        except IOError:
            self.fail(
                'File with size fitting into disk space could not be written.')

        self.assertEqual(initial_usage.used + 100,
                         self.filesystem.GetDiskUsage().used)

    def testCreatingFileWithSizeTooLarge(self):
        initial_usage = self.filesystem.GetDiskUsage()

        def create_large_file():
            self.filesystem.CreateFile('!foo!bar', st_size=101)

        self.assertRaises(IOError, create_large_file)

        self.assertEqual(initial_usage, self.filesystem.GetDiskUsage())

    def testResizeFileWithFittingSize(self):
        file_object = self.filesystem.CreateFile('!foo!bar', st_size=50)
        try:
            file_object.SetLargeFileSize(100)
            file_object.SetContents(b'a' * 100)
        except IOError:
            self.fail(
                'Resizing file failed although disk space was sufficient.')

    def testResizeFileWithSizeTooLarge(self):
        file_object = self.filesystem.CreateFile('!foo!bar', st_size=50)
        self.assertRaisesIOError(errno.ENOSPC, file_object.SetLargeFileSize,
                                 200)
        self.assertRaisesIOError(errno.ENOSPC, file_object.SetContents,
                                 'a' * 150)

    def testFileSystemSizeAfterDirectoryRename(self):
        self.filesystem.CreateFile('!foo!bar', st_size=20)
        self.os.rename('!foo', '!baz')
        self.assertEqual(20, self.filesystem.GetDiskUsage().used)

    def testFileSystemSizeAfterFileRename(self):
        self.filesystem.CreateFile('!foo!bar', st_size=20)
        self.os.rename('!foo!bar', '!foo!baz')
        self.assertEqual(20, self.filesystem.GetDiskUsage().used)

    @unittest.skipIf(TestCase.is_windows and sys.version_info < (3, 3),
                     'Links are not supported under Windows before Python 3.3')
    def testThatHardLinkDoesNotChangeUsedSize(self):
        file1_path = 'test_file1'
        file2_path = 'test_file2'
        self.filesystem.CreateFile(file1_path, st_size=20)
        self.assertEqual(20, self.filesystem.GetDiskUsage().used)
        # creating a hard link shall not increase used space
        self.os.link(file1_path, file2_path)
        self.assertEqual(20, self.filesystem.GetDiskUsage().used)
        # removing a file shall not decrease used space
        # if a hard link still exists
        self.os.unlink(file1_path)
        self.assertEqual(20, self.filesystem.GetDiskUsage().used)
        self.os.unlink(file2_path)
        self.assertEqual(0, self.filesystem.GetDiskUsage().used)

    def testThatTheSizeOfCorrectMountPointIsUsed(self):
        self.filesystem.AddMountPoint('!mount_limited', total_size=50)
        self.filesystem.AddMountPoint('!mount_unlimited')

        self.assertRaisesIOError(errno.ENOSPC,
                                 self.filesystem.CreateFile,
                                 '!mount_limited!foo', st_size=60)
        self.assertRaisesIOError(errno.ENOSPC, self.filesystem.CreateFile,
                                 '!bar', st_size=110)

        try:
            self.filesystem.CreateFile('!foo', st_size=60)
            self.filesystem.CreateFile('!mount_limited!foo', st_size=40)
            self.filesystem.CreateFile('!mount_unlimited!foo', st_size=1000000)
        except IOError:
            self.fail('File with contents fitting into '
                      'disk space could not be written.')

    def testThatDiskUsageOfCorrectMountPointIsUsed(self):
        self.filesystem.AddMountPoint('!mount1', total_size=20)
        self.filesystem.AddMountPoint('!mount1!bar!mount2', total_size=50)

        self.filesystem.CreateFile('!foo!bar', st_size=10)
        self.filesystem.CreateFile('!mount1!foo!bar', st_size=10)
        self.filesystem.CreateFile('!mount1!bar!mount2!foo!bar', st_size=10)

        self.assertEqual(90, self.filesystem.GetDiskUsage('!foo').free)
        self.assertEqual(10, self.filesystem.GetDiskUsage('!mount1!foo').free)
        self.assertEqual(40, self.filesystem.GetDiskUsage(
            '!mount1!bar!mount2').free)

    def testSetLargerDiskSize(self):
        self.filesystem.AddMountPoint('!mount1', total_size=20)
        self.assertRaisesIOError(errno.ENOSPC,
                                 self.filesystem.CreateFile, '!mount1!foo',
                                 st_size=100)
        self.filesystem.SetDiskUsage(total_size=200, path='!mount1')
        self.filesystem.CreateFile('!mount1!foo', st_size=100)
        self.assertEqual(100, self.filesystem.GetDiskUsage('!mount1!foo').free)

    def testSetSmallerDiskSize(self):
        self.filesystem.AddMountPoint('!mount1', total_size=200)
        self.filesystem.CreateFile('!mount1!foo', st_size=100)
        self.assertRaisesIOError(errno.ENOSPC,
                                 self.filesystem.SetDiskUsage, total_size=50,
                                 path='!mount1')
        self.filesystem.SetDiskUsage(total_size=150, path='!mount1')
        self.assertEqual(50, self.filesystem.GetDiskUsage('!mount1!foo').free)

    def testDiskSizeOnUnlimitedDisk(self):
        self.filesystem.AddMountPoint('!mount1')
        self.filesystem.CreateFile('!mount1!foo', st_size=100)
        self.filesystem.SetDiskUsage(total_size=1000, path='!mount1')
        self.assertEqual(900, self.filesystem.GetDiskUsage('!mount1!foo').free)

    def testDiskSizeOnAutoMountedDriveOnFileCreation(self):
        self.filesystem.is_windows_fs = True
        # drive d: shall be auto-mounted and the used size adapted
        self.filesystem.CreateFile('d:!foo!bar', st_size=100)
        self.filesystem.SetDiskUsage(total_size=1000, path='d:')
        self.assertEqual(self.filesystem.GetDiskUsage('d:!foo').free, 900)

    def testDiskSizeOnAutoMountedDriveOnDirectoryCreation(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.CreateDirectory('d:!foo!bar')
        self.filesystem.CreateFile('d:!foo!bar!baz', st_size=100)
        self.filesystem.CreateFile('d:!foo!baz', st_size=100)
        self.filesystem.SetDiskUsage(total_size=1000, path='d:')
        self.assertEqual(self.filesystem.GetDiskUsage('d:!foo').free, 800)

    @unittest.skipIf(sys.version_info < (3, 0),
                     'Tests byte contents in Python3')
    def testCopyingPreservesByteContents(self):
        source_file = self.filesystem.CreateFile('foo', contents=b'somebytes')
        dest_file = self.filesystem.CreateFile('bar')
        dest_file.SetContents(source_file.contents)
        self.assertEqual(dest_file.contents, source_file.contents)


class MountPointTest(TestCase):
    def setUp(self):
        self.filesystem = fake_filesystem.FakeFilesystem(path_separator='!',
                                                         total_size=100)
        self.filesystem.AddMountPoint('!foo')
        self.filesystem.AddMountPoint('!bar')
        self.filesystem.AddMountPoint('!foo!baz')

    def testThatNewMountPointsGetNewDeviceNumber(self):
        self.assertEqual(1, self.filesystem.GetObject('!').st_dev)
        self.assertEqual(2, self.filesystem.GetObject('!foo').st_dev)
        self.assertEqual(3, self.filesystem.GetObject('!bar').st_dev)
        self.assertEqual(4, self.filesystem.GetObject('!foo!baz').st_dev)

    def testThatNewDirectoriesGetCorrectDeviceNumber(self):
        self.assertEqual(1,
                         self.filesystem.CreateDirectory('!foo1!bar').st_dev)
        self.assertEqual(2, self.filesystem.CreateDirectory('!foo!bar').st_dev)
        self.assertEqual(4, self.filesystem.CreateDirectory(
            '!foo!baz!foo!bar').st_dev)

    def testThatNewFilesGetCorrectDeviceNumber(self):
        self.assertEqual(1, self.filesystem.CreateFile('!foo1!bar').st_dev)
        self.assertEqual(2, self.filesystem.CreateFile('!foo!bar').st_dev)
        self.assertEqual(4,
                         self.filesystem.CreateFile('!foo!baz!foo!bar').st_dev)

    def testThatMountPointCannotBeAddedTwice(self):
        self.assertRaisesOSError(errno.EEXIST, self.filesystem.AddMountPoint,
                                 '!foo')
        self.assertRaisesOSError(errno.EEXIST, self.filesystem.AddMountPoint,
                                 '!foo!')

    def testThatDrivesAreAutoMounted(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.CreateDirectory('d:!foo!bar')
        self.filesystem.CreateFile('d:!foo!baz')
        self.filesystem.CreateFile('z:!foo!baz')
        self.assertEqual(5, self.filesystem.GetObject('d:').st_dev)
        self.assertEqual(5, self.filesystem.GetObject('d:!foo!bar').st_dev)
        self.assertEqual(5, self.filesystem.GetObject('d:!foo!baz').st_dev)
        self.assertEqual(6, self.filesystem.GetObject('z:!foo!baz').st_dev)

    def testThatDrivesAreAutoMountedCaseInsensitive(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.is_case_sensitive = False
        self.filesystem.CreateDirectory('D:!foo!bar')
        self.filesystem.CreateFile('e:!foo!baz')
        self.assertEqual(5, self.filesystem.GetObject('D:').st_dev)
        self.assertEqual(5, self.filesystem.GetObject('d:!foo!bar').st_dev)
        self.assertEqual(6, self.filesystem.GetObject('e:!foo').st_dev)
        self.assertEqual(6, self.filesystem.GetObject('E:!Foo!Baz').st_dev)

    @unittest.skipIf(sys.version_info < (2, 7, 8),
                     'UNC path support since Python 2.7.8')
    def testThatUncPathsAreAutoMounted(self):
        self.filesystem.is_windows_fs = True
        self.filesystem.CreateDirectory('!!foo!bar!baz')
        self.filesystem.CreateFile('!!foo!bar!bip!bop')
        self.assertEqual(5, self.filesystem.GetObject('!!foo!bar').st_dev)
        self.assertEqual(5,
                         self.filesystem.GetObject('!!foo!bar!bip!bop').st_dev)


class RealFileSystemAccessTest(TestCase):
    def setUp(self):
        # use the real path separator to work with the real file system
        self.filesystem = fake_filesystem.FakeFilesystem()
        self.fake_open = fake_filesystem.FakeFileOpen(self.filesystem)

    def testAddNonExistingRealFileRaises(self):
        nonexisting_path = os.path.join('nonexisting', 'test.txt')
        self.assertRaises(OSError, self.filesystem.add_real_file,
                          nonexisting_path)
        self.assertFalse(self.filesystem.Exists(nonexisting_path))

    def testAddNonExistingRealDirectoryRaises(self):
        nonexisting_path = '/nonexisting'
        self.assertRaisesIOError(errno.ENOENT,
                                 self.filesystem.add_real_directory,
                                 nonexisting_path)
        self.assertFalse(self.filesystem.Exists(nonexisting_path))

    def testExistingFakeFileRaises(self):
        real_file_path = __file__
        self.filesystem.CreateFile(real_file_path)
        self.assertRaisesOSError(errno.EEXIST, self.filesystem.add_real_file,
                                 real_file_path)

    def testExistingFakeDirectoryRaises(self):
        real_dir_path = os.path.dirname(__file__)
        self.filesystem.CreateDirectory(real_dir_path)
        self.assertRaisesOSError(errno.EEXIST,
                                 self.filesystem.add_real_directory,
                                 real_dir_path)

    def checkFakeFileStat(self, fake_file, real_file_path):
        self.assertTrue(self.filesystem.Exists(real_file_path))
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

    def checkReadOnlyFile(self, fake_file, real_file_path):
        with open(real_file_path, 'rb') as f:
            real_contents = f.read()
        self.assertEqual(fake_file.byte_contents, real_contents)
        self.assertRaisesIOError(errno.EACCES, self.fake_open, real_file_path,
                                 'w')

    def checkWritableFile(self, fake_file, real_file_path):
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

    def testAddExistingRealFileReadOnly(self):
        real_file_path = __file__
        fake_file = self.filesystem.add_real_file(real_file_path)
        self.checkFakeFileStat(fake_file, real_file_path)
        self.assertEqual(fake_file.st_mode & 0o333, 0)
        self.checkReadOnlyFile(fake_file, real_file_path)

    def testAddExistingRealFileReadWrite(self):
        real_file_path = os.path.realpath(__file__)
        fake_file = self.filesystem.add_real_file(real_file_path,
                                                  read_only=False)

        self.checkFakeFileStat(fake_file, real_file_path)
        self.assertEqual(fake_file.st_mode, os.stat(real_file_path).st_mode)
        self.checkWritableFile(fake_file, real_file_path)

    def testAddExistingRealDirectoryReadOnly(self):
        real_dir_path = os.path.join(os.path.dirname(__file__), 'pyfakefs')
        self.filesystem.add_real_directory(real_dir_path)
        self.assertTrue(self.filesystem.Exists(real_dir_path))
        self.assertTrue(self.filesystem.Exists(
            os.path.join(real_dir_path, 'fake_filesystem.py')))
        self.assertTrue(self.filesystem.Exists(
            os.path.join(real_dir_path, 'fake_pathlib.py')))

        file_path = os.path.join(real_dir_path, 'fake_filesystem_shutil.py')
        fake_file = self.filesystem.ResolveObject(file_path)
        self.checkFakeFileStat(fake_file, file_path)
        self.checkReadOnlyFile(fake_file, file_path)

    def testAddExistingRealDirectoryTree(self):
        real_dir_path = os.path.dirname(__file__)
        self.filesystem.add_real_directory(real_dir_path)
        self.assertTrue(
            self.filesystem.Exists(
                os.path.join(real_dir_path, 'fake_filesystem_test.py')))
        self.assertTrue(
            self.filesystem.Exists(
                os.path.join(real_dir_path, 'pyfakefs', 'fake_filesystem.py')))
        self.assertTrue(
            self.filesystem.Exists(
                os.path.join(real_dir_path, 'pyfakefs', '__init__.py')))

    def testGetObjectFromLazilyAddedRealDirectory(self):
        self.filesystem.is_case_sensitive = True
        real_dir_path = os.path.dirname(__file__)
        self.filesystem.add_real_directory(real_dir_path)
        self.assertTrue(self.filesystem.GetObject(
            os.path.join(real_dir_path, 'pyfakefs', 'fake_filesystem.py')))
        self.assertTrue(
            self.filesystem.GetObject(
                os.path.join(real_dir_path, 'pyfakefs', '__init__.py')))

    def testAddExistingRealDirectoryLazily(self):
        disk_size = 1024 * 1024 * 1024
        real_dir_path = os.path.join(os.path.dirname(__file__), 'pyfakefs')
        self.filesystem.SetDiskUsage(disk_size, real_dir_path)
        self.filesystem.add_real_directory(real_dir_path)

        # the directory contents have not been read, the the disk usage
        # has not changed
        self.assertEqual(disk_size,
                         self.filesystem.GetDiskUsage(real_dir_path).free)
        # checking for existence shall read the directory contents
        self.assertTrue(
            self.filesystem.GetObject(
                os.path.join(real_dir_path, 'fake_filesystem.py')))
        # so now the free disk space shall have decreased
        self.assertGreater(disk_size,
                           self.filesystem.GetDiskUsage(real_dir_path).free)

    def testAddExistingRealDirectoryNotLazily(self):
        disk_size = 1024 * 1024 * 1024
        real_dir_path = os.path.join(os.path.dirname(__file__), 'pyfakefs')
        self.filesystem.SetDiskUsage(disk_size, real_dir_path)
        self.filesystem.add_real_directory(real_dir_path, lazy_read=False)

        # the directory has been read, so the file sizes have
        # been subtracted from the free space
        self.assertGreater(disk_size,
                           self.filesystem.GetDiskUsage(real_dir_path).free)

    def testAddExistingRealDirectoryReadWrite(self):
        real_dir_path = os.path.join(os.path.dirname(__file__), 'pyfakefs')
        self.filesystem.add_real_directory(real_dir_path, read_only=False)
        self.assertTrue(self.filesystem.Exists(real_dir_path))
        self.assertTrue(self.filesystem.Exists(
            os.path.join(real_dir_path, 'fake_filesystem.py')))
        self.assertTrue(self.filesystem.Exists(
            os.path.join(real_dir_path, 'fake_pathlib.py')))

        file_path = os.path.join(real_dir_path, 'pytest_plugin.py')
        fake_file = self.filesystem.ResolveObject(file_path)
        self.checkFakeFileStat(fake_file, file_path)
        self.checkWritableFile(fake_file, file_path)

    def testAddExistingRealPathsReadOnly(self):
        real_file_path = os.path.realpath(__file__)
        real_dir_path = os.path.join(os.path.dirname(__file__), 'pyfakefs')
        self.filesystem.add_real_paths([real_file_path, real_dir_path])

        fake_file = self.filesystem.ResolveObject(real_file_path)
        self.checkFakeFileStat(fake_file, real_file_path)
        self.checkReadOnlyFile(fake_file, real_file_path)

        real_file_path = os.path.join(real_dir_path,
                                      'fake_filesystem_shutil.py')
        fake_file = self.filesystem.ResolveObject(real_file_path)
        self.checkFakeFileStat(fake_file, real_file_path)
        self.checkReadOnlyFile(fake_file, real_file_path)

    def testAddExistingRealPathsReadWrite(self):
        real_file_path = os.path.realpath(__file__)
        real_dir_path = os.path.join(os.path.dirname(__file__), 'pyfakefs')
        self.filesystem.add_real_paths([real_file_path, real_dir_path],
                                       read_only=False)

        fake_file = self.filesystem.ResolveObject(real_file_path)
        self.checkFakeFileStat(fake_file, real_file_path)
        self.checkWritableFile(fake_file, real_file_path)

        real_file_path = os.path.join(real_dir_path, 'fake_pathlib.py')
        fake_file = self.filesystem.ResolveObject(real_file_path)
        self.checkFakeFileStat(fake_file, real_file_path)
        self.checkWritableFile(fake_file, real_file_path)


if __name__ == '__main__':
    unittest.main()
