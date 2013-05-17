#!/usr/bin/python2.4
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

"""Test that FakeFilesystem calls work identically to a real filesystem."""

import os
import os.path
import shutil
import tempfile
import time
import unittest

import fake_filesystem


class FakeFilesystemVsRealTest(unittest.TestCase):
  _FAKE_FS_BASE = '/fakefs'

  def _Paths(self, path):
    """For a given path, return paths in the real and fake filesystems."""
    if not path:
      return (None, None)
    return (os.path.join(self.real_base, path),
            os.path.join(self.fake_base, path))

  def _CreateTestFile(self, file_type, path, contents=None):
    """Create a dir, file, or link in both the real fs and the fake."""
    self._created_files.append([file_type, path, contents])
    real_path, fake_path = self._Paths(path)
    if file_type == 'd':
      os.mkdir(real_path)
      self.fake_os.mkdir(fake_path)
    if file_type == 'f':
      fh = open(real_path, 'w')
      fh.write(contents or '')
      fh.close()
      fh = self.fake_open(fake_path, 'w')
      fh.write(contents or '')
      fh.close()
    # l for symlink, h for hard link
    if file_type in ('l', 'h'):
      real_target, fake_target = (contents, contents)
      # If it begins with '/', make it relative to the base.  You can't go
      # creating files in / for the real file system.
      if contents.startswith('/'):
        real_target, fake_target = self._Paths(contents[1:])
      if file_type == 'l':
        os.symlink(real_target, real_path)
        self.fake_os.symlink(fake_target, fake_path)
      elif file_type == 'h':
        os.link(real_target, real_path)
        self.fake_os.link(fake_target, fake_path)

  def setUp(self):
    # Base paths in the real and test file systems.   We keep them different
    # so that missing features in the fake don't fall through to the base
    # operations and magically succeed.
    tsname = 'fakefs.%s' % time.time()
    # Fully expand the base_path - required on OS X.
    self.real_base = os.path.realpath(
        os.path.join(tempfile.gettempdir(), tsname))
    os.mkdir(self.real_base)
    self.fake_base = self._FAKE_FS_BASE

    # Make sure we can write to the physical testing temp directory.
    self.assert_(self.real_base.startswith('/'))
    self.assert_(os.access(self.real_base, os.W_OK))

    self.fake_filesystem = fake_filesystem.FakeFilesystem()
    self.fake_filesystem.CreateDirectory(self.fake_base)
    self.fake_os = fake_filesystem.FakeOsModule(self.fake_filesystem)
    self.fake_open = fake_filesystem.FakeFileOpen(self.fake_filesystem)
    self._created_files = []

    os.chdir(self.real_base)
    self.fake_os.chdir(self.fake_base)

  def tearDown(self):
    # We have to remove all the files from the real FS. Doing the same for the
    # fake FS is optional, but doing it is an extra sanity check.
    try:
      rev_files = self._created_files[:]
      rev_files.reverse()
      for info in rev_files:
        real_path, fake_path = self._Paths(info[1])
        if info[0] == 'd':
          try:
            os.rmdir(real_path)
          except OSError, e:
            if 'Directory not empty' in e:
              self.fail('Real path %s not empty: %s : %s' % (
                  real_path, e, os.listdir(real_path)))
            else:
              raise
          self.fake_os.rmdir(fake_path)
        if info[0] == 'f' or info[0] == 'l':
          os.remove(real_path)
          self.fake_os.remove(fake_path)
    finally:
      shutil.rmtree(self.real_base)

  def _GetErrno(self, raised_error):
    try:
      return (raised_error and raised_error.errno) or None
    except AttributeError:
      return None

  def _CompareBehaviors(self, method_name, path, real_method, fake_method,
                        method_returns_path=False):
    """Invoke an os method in both real and fake contexts and compare results.

    Invoke a real filesystem method with a path to a real file and invoke a fake
    filesystem method with a path to a fake file and compare the results.  We
    expect some calls to throw Exceptions, so we catch those and compare them.

    Args:
      method_name: Name of method being tested, for use in error messages.
      path: potential path to a file in the real and fake file systems
      real_method: method from the built-in system library which takes a path
        as an arg and returns some value.
      fake_method: method from the fake_filesystem library which takes a path
        as an arg and returns some value.
      method_returns_path: True if the method returns a path, and thus we must
        compensate for expected difference between real and fake.

    Returns:
      A description of the difference in behavior, or None.
    """

    def _ErrorClass(e):
      return (e and e.__class__.__name__) or 'None'

    errs = 0
    real_value = None
    fake_value = None
    real_err = None
    fake_err = None
    # Catching Exception below gives a lint warning, but it's what we need.
    try:
      real_value = real_method(path)
    except Exception, real_err:  # pylint: disable-msg=W0703
      errs += 1
    try:
      fake_value = fake_method(path)
    except Exception, fake_err:  # pylint: disable-msg=W0703
      errs += 1
    # We only compare on the error class because the acutal error contents
    # is almost always different because of the file paths.
    if _ErrorClass(real_err) != _ErrorClass(fake_err):
      if real_err is None:
        return '%s(%s): real version returned %s, fake raised %s' % (
            method_name, path, real_value, _ErrorClass(fake_err))
      if fake_err is None:
        return '%s(%s): real version raised %s, fake returned %s' % (
            method_name, path, _ErrorClass(real_err), fake_value)
      return '%s(%s): real version raised %s, fake raised %s' % (
          method_name, path, _ErrorClass(real_err), _ErrorClass(fake_err))
    real_errno = self._GetErrno(real_err)
    fake_errno = self._GetErrno(fake_err)
    if real_errno != fake_errno:
      return '%s(%s): both raised %s, real errno %s, fake errno %s' % (
          method_name, path, _ErrorClass(real_err), real_errno, fake_errno)
    # If the method is supposed to return a full path AND both values
    # begin with the expected full path, then trim it off.
    if method_returns_path:
      if (real_value and fake_value
          and real_value.startswith(self.real_base)
          and fake_value.startswith(self.fake_base)):
        real_value = real_value[len(self.real_base):]
        fake_value = fake_value[len(self.fake_base):]
    if real_value != fake_value:
      return '%s(%s): real return %s, fake returned %s' % (
          method_name, path, real_value, fake_value)
    return None

  def assertOsMethodBehaviorMatches(self, method_name, path,
                                    method_returns_path=False):
    """Invoke an os method in both real and fake contexts and compare.

    For a given method name (from the os module) and a path, compare the
    behavior of the system provided module against the fake_filesytem module.
    We expect results and/or Exceptions raised to be identical.

    Args:
      method_name: Name of method being tested.
      path: potential path to a file in the real and fake file systems.
      method_returns_path: True if the method returns a path, and thus we must
        compensate for expected difference between real and fake.

    Returns:
      A description of the difference in behavior, or None.
    """

    def _BindToModule(method):
      """Bind a method to the fake os module."""

      def _Call(path):
        return method(self.fake_os, path)
      return _Call

    real_method = os.__dict__[method_name]
    fake_method = _BindToModule(self.fake_os.__class__.__dict__[method_name])
    return self._CompareBehaviors(method_name, path, real_method, fake_method,
                                  method_returns_path)

  def DiffOsPathMethodBehavior(self, method_name, path,
                               method_returns_path=False):
    """Invoke an os.path method in both real and fake contexts and compare.

    For a given method name (from the os.path module) and a path, compare the
    behavior of the system provided module against the fake_filesytem module.
    We expect results and/or Exceptions raised to be identical.

    Args:
      method_name: Name of method being tested.
      path: potential path to a file in the real and fake file systems.
      method_returns_path: True if the method returns a path, and thus we must
        compensate for expected difference between real and fake.

    Returns:
      A description of the difference in behavior, or None.
    """

    def _BindToModule(method):
      """Bind a method to the fake os.path module."""

      def _Call(path):
        return method(self.fake_os.path, path)
      return _Call

    real_method = os.path.__dict__[method_name]
    fake_method = _BindToModule(
        self.fake_os.path.__class__.__dict__[method_name])
    return self._CompareBehaviors(method_name, path, real_method, fake_method,
                                  method_returns_path)

  def assertOsPathMethodBehaviorMatches(self, method_name, path,
                                        method_returns_path=False):
    """Assert that an os.path behaves the same in both real and fake contexts.

    Wraps DiffOsPathMethodBehavior, raising AssertionError if any differences
    are reported.

    Args:
      method_name: Name of method being tested.
      path: potential path to a file in the real and fake file systems.
      method_returns_path: True if the method returns a path, and thus we must
        compensate for expected difference between real and fake.

    Raises:
      AssertionError if there is any difference in behavior.
    """
    diff = self.DiffOsPathMethodBehavior(method_name, path, method_returns_path)
    if diff:
      self.fail(diff)

  def assertAllBehaviorsMatch(self, path):
    os_method_names = ['readlink']
    os_method_names_returning_paths = ['getcwd',
                                       'getcwdu',
                                      ]
    os_path_method_names = ['isabs',
                            'isdir',
                            'isfile',
                            'islink',
                            'exists',
                            'lexists',
                           ]
    wrapped_methods = [['access', self._AccessReal, self._AccessFake],
                       ['stat.size', self._StatSizeReal, self._StatSizeFake],
                       ['lstat.size', self._LstatSizeReal, self._LstatSizeFake]
                      ]

    differences = []
    for method_name in os_method_names:
      diff = self.assertOsMethodBehaviorMatches(method_name, path)
      if diff:
        differences.append(diff)
    for method_name in os_method_names_returning_paths:
      diff = self.assertOsMethodBehaviorMatches(method_name, path,
                                                method_returns_path=True)
      if diff:
        differences.append(diff)
    for method_name in os_path_method_names:
      diff = self.DiffOsPathMethodBehavior(method_name, path)
      if diff:
        differences.append(diff)
    for m in wrapped_methods:
      diff = self._CompareBehaviors(m[0], path, m[1], m[2])
      if diff:
        differences.append(diff)
    if differences:
      self.fail('Behaviors do not match for %s:\n  %s' %
                (path, '\n  '.join(differences)))

  # Helpers for checks which are not straight method calls.

  def _AccessReal(self, path):
    return os.access(path, 0777777)

  def _AccessFake(self, path):
    return self.fake_os.access(path, 0777777)

  def _StatSizeReal(self, path):
    real_path, unused_fake_path = self._Paths(path)
    # fake_filesystem.py does not implement stat().st_size for directories
    if os.path.isdir(real_path):
      return None
    return os.stat(real_path).st_size

  def _StatSizeFake(self, path):
    unused_real_path, fake_path = self._Paths(path)
    # fake_filesystem.py does not implement stat().st_size for directories
    if self.fake_os.path.isdir(fake_path):
      return None
    return self.fake_os.stat(fake_path).st_size

  def _LstatSizeReal(self, path):
    real_path, unused_fake_path = self._Paths(path)
    if os.path.isdir(real_path):
      return None
    size = os.lstat(real_path).st_size
    # Account for the difference in the lengths of the absolute paths.
    if os.path.islink(real_path):
      if os.readlink(real_path).startswith('/'):
        size -= len(self.real_base)
    return size

  def _LstatSizeFake(self, path):
    unused_real_path, fake_path = self._Paths(path)
    size = 0
    if self.fake_os.path.isdir(fake_path):
      return None
    size = self.fake_os.lstat(fake_path).st_size
    # Account for the difference in the lengths of the absolute paths.
    if self.fake_os.path.islink(fake_path):
      if self.fake_os.readlink(fake_path).startswith('/'):
        size -= len(self.fake_base)
    return size

  def testIsabs(self):
    # We do not have to create any files for isabs.
    self.assertOsPathMethodBehaviorMatches('isabs', None)
    self.assertOsPathMethodBehaviorMatches('isabs', '')
    self.assertOsPathMethodBehaviorMatches('isabs', '/')
    self.assertOsPathMethodBehaviorMatches('isabs', '/a')
    self.assertOsPathMethodBehaviorMatches('isabs', 'a')

  def testNonePath(self):
    self.assertAllBehaviorsMatch(None)

  def testEmptyPath(self):
    self.assertAllBehaviorsMatch('')

  def testRootPath(self):
    self.assertAllBehaviorsMatch('/')

  def testNonExistantFile(self):
    self.assertAllBehaviorsMatch('foo')

  def testEmptyFile(self):
    self._CreateTestFile('f', 'aFile')
    self.assertAllBehaviorsMatch('aFile')

  def testFileWithContents(self):
    self._CreateTestFile('f', 'aFile', 'some contents')
    self.assertAllBehaviorsMatch('aFile')

  def testSymLinkToEmptyFile(self):
    self._CreateTestFile('f', 'aFile')
    self._CreateTestFile('l', 'link_to_empty', 'aFile')
    self.assertAllBehaviorsMatch('link_to_empty')

  def TBD_testHardLinkToEmptyFile(self):
    self._CreateTestFile('f', 'aFile')
    self._CreateTestFile('h', 'link_to_empty', 'aFile')
    self.assertAllBehaviorsMatch('link_to_empty')

  def testSymLinkToRealFile(self):
    self._CreateTestFile('f', 'aFile', 'some contents')
    self._CreateTestFile('l', 'link_to_file', 'aFile')
    self.assertAllBehaviorsMatch('link_to_file')

  def TBD_testHardLinkToRealFile(self):
    self._CreateTestFile('f', 'aFile', 'some contents')
    self._CreateTestFile('h', 'link_to_file', 'aFile')
    self.assertAllBehaviorsMatch('link_to_file')

  def testBrokenSymLink(self):
    self._CreateTestFile('l', 'broken_link', 'broken')
    self.assertAllBehaviorsMatch('broken_link')

  def testFileInAFolder(self):
    self._CreateTestFile('d', 'a')
    self._CreateTestFile('d', 'a/b')
    self._CreateTestFile('f', 'a/b/file', 'contents')
    self.assertAllBehaviorsMatch('a/b/file')

  def testAbsoluteSymLinkToFolder(self):
    self._CreateTestFile('d', 'a')
    self._CreateTestFile('d', 'a/b')
    self._CreateTestFile('f', 'a/b/file', 'contents')
    self._CreateTestFile('l', 'a/link', '/a/b')
    self.assertAllBehaviorsMatch('a/link/file')

  def testLinkToFolderAfterChdir(self):
    self._CreateTestFile('d', 'a')
    self._CreateTestFile('d', 'a/b')
    self._CreateTestFile('f', 'a/b/file', 'contents')
    self._CreateTestFile('l', 'a/link', '/a/b')

    real_dir, fake_dir = self._Paths('a/b')
    os.chdir(real_dir)
    self.fake_os.chdir(fake_dir)
    self.assertAllBehaviorsMatch('file')

  def testRelativeSymLinkToFolder(self):
    self._CreateTestFile('d', 'a')
    self._CreateTestFile('d', 'a/b')
    self._CreateTestFile('f', 'a/b/file', 'contents')
    self._CreateTestFile('l', 'a/link', 'b')
    self.assertAllBehaviorsMatch('a/link/file')

  def testSymLinkToParent(self):
    # Soft links on HFS+ / OS X behave differently.
    if os.uname()[0] != 'Darwin':
      self._CreateTestFile('d', 'a')
      self._CreateTestFile('d', 'a/b')
      self._CreateTestFile('l', 'a/b/c', '..')
      self.assertAllBehaviorsMatch('a/b/c')

  def testPathThroughSymLinkToParent(self):
    self._CreateTestFile('d', 'a')
    self._CreateTestFile('f', 'a/target', 'contents')
    self._CreateTestFile('d', 'a/b')
    self._CreateTestFile('l', 'a/b/c', '..')
    self.assertAllBehaviorsMatch('a/b/c/target')

  def testSymLinkToSiblingDirectory(self):
    self._CreateTestFile('d', 'a')
    self._CreateTestFile('d', 'a/b')
    self._CreateTestFile('d', 'a/sibling_of_b')
    self._CreateTestFile('f', 'a/sibling_of_b/target', 'contents')
    self._CreateTestFile('l', 'a/b/c', '../sibling_of_b')
    self.assertAllBehaviorsMatch('a/b/c/target')

  def testSymLinkToSiblingDirectoryNonExistantFile(self):
    self._CreateTestFile('d', 'a')
    self._CreateTestFile('d', 'a/b')
    self._CreateTestFile('d', 'a/sibling_of_b')
    self._CreateTestFile('f', 'a/sibling_of_b/target', 'contents')
    self._CreateTestFile('l', 'a/b/c', '../sibling_of_b')
    self.assertAllBehaviorsMatch('a/b/c/file_does_not_exist')

  def testBrokenSymLinkToSiblingDirectory(self):
    self._CreateTestFile('d', 'a')
    self._CreateTestFile('d', 'a/b')
    self._CreateTestFile('d', 'a/sibling_of_b')
    self._CreateTestFile('f', 'a/sibling_of_b/target', 'contents')
    self._CreateTestFile('l', 'a/b/c', '../broken_sibling_of_b')
    self.assertAllBehaviorsMatch('a/b/c/target')

  def testRelativePath(self):
    self._CreateTestFile('d', 'a')
    self._CreateTestFile('d', 'a/b')
    self._CreateTestFile('d', 'a/sibling_of_b')
    self._CreateTestFile('f', 'a/sibling_of_b/target', 'contents')
    self.assertAllBehaviorsMatch('a/b/../sibling_of_b/target')

  def testBrokenRelativePath(self):
    self._CreateTestFile('d', 'a')
    self._CreateTestFile('d', 'a/b')
    self._CreateTestFile('d', 'a/sibling_of_b')
    self._CreateTestFile('f', 'a/sibling_of_b/target', 'contents')
    self.assertAllBehaviorsMatch('a/b/../broken/target')

  def TBD_testBadRelativePath(self):
    self._CreateTestFile('d', 'a')
    self._CreateTestFile('f', 'a/target', 'contents')
    self._CreateTestFile('d', 'a/b')
    self._CreateTestFile('d', 'a/sibling_of_b')
    self._CreateTestFile('f', 'a/sibling_of_b/target', 'contents')
    self.assertAllBehaviorsMatch('a/b/../broken/../target')

  def testGetmtimeNonexistantPath(self):
    self.assertOsPathMethodBehaviorMatches('getmtime', 'no/such/path')


def main(unused_argv):
  unittest.main()


if __name__ == '__main__':
  unittest.main()
