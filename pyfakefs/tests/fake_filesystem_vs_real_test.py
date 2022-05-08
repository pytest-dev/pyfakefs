# Copyright 2009 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#            http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test that FakeFilesystem calls work identically to a real filesystem."""
# pylint: disable-all

import os
import shutil
import sys
import tempfile
import time
import unittest

from pyfakefs import fake_filesystem
from pyfakefs.helpers import IS_PYPY


def sep(path):
    """Converts slashes in the path to the architecture's path seperator."""
    if isinstance(path, str):
        return path.replace('/', os.sep)
    return path


def _get_errno(raised_error):
    if raised_error is not None:
        try:
            return raised_error.errno
        except AttributeError:
            pass


class TestCase(unittest.TestCase):
    is_windows = sys.platform.startswith('win')
    _FAKE_FS_BASE = 'C:\\fakefs' if is_windows else '/fakefs'


class FakeFilesystemVsRealTest(TestCase):
    def _paths(self, path):
        """For a given path, return paths in the real and fake filesystems."""
        if not path:
            return None, None
        return (os.path.join(self.real_base, path),
                os.path.join(self.fake_base, path))

    def _create_test_file(self, file_type, path, contents=None):
        """Create a dir, file, or link in both the real fs and the fake."""
        path = sep(path)
        self._created_files.append([file_type, path, contents])
        real_path, fake_path = self._paths(path)
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
        # b for binary file
        if file_type == 'b':
            fh = open(real_path, 'wb')
            fh.write(contents or '')
            fh.close()
            fh = self.fake_open(fake_path, 'wb')
            fh.write(contents or '')
            fh.close()
        # l for symlink, h for hard link
        if file_type in ('l', 'h'):
            real_target, fake_target = (contents, contents)
            # If it begins with '/', make it relative to the base. You can't go
            # creating files in / for the real file system.
            if contents.startswith(os.sep):
                real_target, fake_target = self._paths(contents[1:])
            if file_type == 'l':
                os.symlink(real_target, real_path)
                self.fake_os.symlink(fake_target, fake_path)
            elif file_type == 'h':
                os.link(real_target, real_path)
                self.fake_os.link(fake_target, fake_path)

    def setUp(self):
        # Base paths in the real and test file systems. We keep them different
        # so that missing features in the fake don't fall through to the base
        # operations and magically succeed.
        tsname = 'fakefs.%s' % time.time()
        self.cwd = os.getcwd()
        # Fully expand the base_path - required on OS X.
        self.real_base = os.path.realpath(
            os.path.join(tempfile.gettempdir(), tsname))
        os.chdir(tempfile.gettempdir())
        if os.path.isdir(self.real_base):
            shutil.rmtree(self.real_base)
        os.mkdir(self.real_base)
        self.fake_base = self._FAKE_FS_BASE

        # Make sure we can write to the physical testing temp directory.
        self.assertTrue(os.access(self.real_base, os.W_OK))

        self.fake_filesystem = fake_filesystem.FakeFilesystem()
        self.fake_filesystem.create_dir(self.fake_base)
        self.fake_os = fake_filesystem.FakeOsModule(self.fake_filesystem)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fake_filesystem)
        self._created_files = []

        os.chdir(self.real_base)
        self.fake_os.chdir(self.fake_base)

    def tearDown(self):
        # We have to remove all the files from the real FS. Doing the same for
        # the fake FS is optional, but doing it is an extra sanity check.
        os.chdir(tempfile.gettempdir())
        try:
            rev_files = self._created_files[:]
            rev_files.reverse()
            for info in rev_files:
                real_path, fake_path = self._paths(info[1])
                if info[0] == 'd':
                    try:
                        os.rmdir(real_path)
                    except OSError as e:
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
            os.chdir(self.cwd)

    def _compare_behaviors(self, method_name, path, real, fake,
                           method_returns_path=False):
        """Invoke an os method in both real and fake contexts and compare
        results.

        Invoke a real filesystem method with a path to a real file and invoke
        a fake filesystem method with a path to a fake file and compare the
        results. We expect some calls to throw Exceptions, so we catch those
        and compare them.

        Args:
            method_name: Name of method being tested, for use in
                error messages.
            path: potential path to a file in the real and fake file systems,
                passing an empty tuple indicates that no arguments to pass
                to method.
            real: built-in system library or method from the built-in system
                library which takes a path as an arg and returns some value.
            fake: fake_filsystem object or method from a fake_filesystem class
                which takes a path as an arg and returns some value.
            method_returns_path: True if the method returns a path, and thus we
                must compensate for expected difference between real and fake.

        Returns:
            A description of the difference in behavior, or None.
        """
        # pylint: disable=C6403

        def _error_class(exc):
            if exc:
                if hasattr(exc, 'errno'):
                    return '{}({})'.format(exc.__class__.__name__, exc.errno)
                return exc.__class__.__name__
            return 'None'

        real_err, real_value = self._get_real_value(method_name, path, real)
        fake_err, fake_value = self._get_fake_value(method_name, path, fake)

        method_call = f'{method_name}'
        method_call += '()' if path == () else '({path})'
        # We only compare on the error class because the acutal error contents
        # is almost always different because of the file paths.
        if _error_class(real_err) != _error_class(fake_err):
            if real_err is None:
                return '%s: real version returned %s, fake raised %s' % (
                    method_call, real_value, _error_class(fake_err))
            if fake_err is None:
                return '%s: real version raised %s, fake returned %s' % (
                    method_call, _error_class(real_err), fake_value)
            return '%s: real version raised %s, fake raised %s' % (
                method_call, _error_class(real_err), _error_class(fake_err))
        real_errno = _get_errno(real_err)
        fake_errno = _get_errno(fake_err)
        if real_errno != fake_errno:
            return '%s(%s): both raised %s, real errno %s, fake errno %s' % (
                method_name, path, _error_class(real_err),
                real_errno, fake_errno)
        # If the method is supposed to return a full path AND both values
        # begin with the expected full path, then trim it off.
        if method_returns_path:
            if (real_value and fake_value
                    and real_value.startswith(self.real_base)
                    and fake_value.startswith(self.fake_base)):
                real_value = real_value[len(self.real_base):]
                fake_value = fake_value[len(self.fake_base):]
        if real_value != fake_value:
            return '%s: real return %s, fake returned %s' % (
                method_call, real_value, fake_value)
        return None

    @staticmethod
    def _get_fake_value(method_name, path, fake):
        fake_value = None
        fake_err = None
        try:
            fake_method = fake
            if not callable(fake):
                fake_method = getattr(fake, method_name)
            args = [] if path == () else [path]
            result = fake_method(*args)
            if isinstance(result, bytes):
                fake_value = result.decode()
            else:
                fake_value = str(result)
        except Exception as e:  # pylint: disable-msg=W0703
            fake_err = e
        return fake_err, fake_value

    @staticmethod
    def _get_real_value(method_name, path, real):
        real_value = None
        real_err = None
        # Catching Exception below gives a lint warning, but it's what we need.
        try:
            args = [] if path == () else [path]
            real_method = real
            if not callable(real):
                real_method = getattr(real, method_name)
            result = real_method(*args)
            if isinstance(result, bytes):
                real_value = result.decode()
            else:
                real_value = str(result)
        except Exception as e:  # pylint: disable-msg=W0703
            real_err = e
        return real_err, real_value

    def assertOsMethodBehaviorMatches(self, method_name, path,
                                      method_returns_path=False):
        """Invoke an os method in both real and fake contexts and compare.

        For a given method name (from the os module) and a path, compare the
        behavior of the system provided module against the fake_filesystem
        module.
        We expect results and/or Exceptions raised to be identical.

        Args:
            method_name: Name of method being tested.
            path: potential path to a file in the real and fake file systems.
            method_returns_path: True if the method returns a path, and thus we
                must compensate for expected difference between real and fake.

        Returns:
            A description of the difference in behavior, or None.
        """
        path = sep(path)
        return self._compare_behaviors(method_name, path, os, self.fake_os,
                                       method_returns_path)

    def diff_open_method_behavior(self, method_name, path, mode, data,
                                  method_returns_data=True):
        """Invoke an open method in both real and fkae contexts and compare.

        Args:
            method_name: Name of method being tested.
            path: potential path to a file in the real and fake file systems.
            mode: how to open the file.
            data: any data to pass to the method.
            method_returns_data: True if a method returns some sort of data.

        For a given method name (from builtin open) and a path, compare the
        behavior of the system provided module against the fake_filesystem
        module.
        We expect results and/or Exceptions raised to be identical.

        Returns:
            A description of the difference in behavior, or None.
        """
        with open(path, mode) as real_fh:
            with self.fake_open(path, mode) as fake_fh:
                return self._compare_behaviors(
                    method_name, data, real_fh, fake_fh, method_returns_data)

    def diff_os_path_method_behavior(self, method_name, path,
                                     method_returns_path=False):
        """Invoke an os.path method in both real and fake contexts and compare.

        For a given method name (from the os.path module) and a path, compare
        the behavior of the system provided module against the
        fake_filesytem module.
        We expect results and/or Exceptions raised to be identical.

        Args:
            method_name: Name of method being tested.
            path: potential path to a file in the real and fake file systems.
            method_returns_path: True if the method returns a path, and thus we
                must compensate for expected difference between real and fake.

        Returns:
            A description of the difference in behavior, or None.
        """
        return self._compare_behaviors(method_name, path, os.path,
                                       self.fake_os.path,
                                       method_returns_path)

    def assertOsPathMethodBehaviorMatches(self, method_name, path,
                                          method_returns_path=False):
        """Assert that an os.path behaves the same in both real and
        fake contexts.

        Wraps DiffOsPathMethodBehavior, raising AssertionError if any
        differences are reported.

        Args:
            method_name: Name of method being tested.
            path: potential path to a file in the real and fake file systems.
            method_returns_path: True if the method returns a path, and thus we
                must compensate for expected difference between real and fake.

        Raises:
            AssertionError if there is any difference in behavior.
        """
        path = sep(path)
        diff = self.diff_os_path_method_behavior(
            method_name, path, method_returns_path)
        if diff:
            self.fail(diff)

    def assertAllOsBehaviorsMatch(self, path):
        path = sep(path)
        os_method_names = [] if self.is_windows else ['readlink']
        os_method_names_no_args = ['getcwd']
        os_path_method_names = ['isabs', 'isdir']
        if not self.is_windows:
            os_path_method_names += ['islink', 'lexists']
        if not self.is_windows or not IS_PYPY:
            os_path_method_names += ['isfile', 'exists']

        wrapped_methods = [
            ['access', self._access_real, self._access_fake],
            ['stat.size', self._stat_size_real, self._stat_size_fake],
            ['lstat.size', self._lstat_size_real, self._lstat_size_fake]
        ]

        differences = []
        for method_name in os_method_names:
            diff = self.assertOsMethodBehaviorMatches(method_name, path)
            if diff:
                differences.append(diff)
        for method_name in os_method_names_no_args:
            diff = self.assertOsMethodBehaviorMatches(method_name, (),
                                                      method_returns_path=True)
            if diff:
                differences.append(diff)
        for method_name in os_path_method_names:
            diff = self.diff_os_path_method_behavior(method_name, path)
            if diff:
                differences.append(diff)
        for m in wrapped_methods:
            diff = self._compare_behaviors(m[0], path, m[1], m[2])
            if diff:
                differences.append(diff)
        if differences:
            self.fail('Behaviors do not match for %s:\n    %s' %
                      (path, '\n    '.join(differences)))

    def assertFileHandleBehaviorsMatch(self, path, mode, data):
        path = sep(path)
        write_method_names = ['write', 'writelines']
        read_method_names = ['read', 'readlines']
        other_method_names = ['truncate', 'flush', 'close']
        differences = []
        for method_name in write_method_names:
            diff = self.diff_open_method_behavior(
                method_name, path, mode, data)
            if diff:
                differences.append(diff)
        for method_name in read_method_names + other_method_names:
            diff = self.diff_open_method_behavior(method_name, path, mode, ())
            if diff:
                differences.append(diff)
        if differences:
            self.fail('Behaviors do not match for %s:\n    %s' %
                      (path, '\n    '.join(differences)))

    def assertFileHandleOpenBehaviorsMatch(self, *args, **kwargs):
        """Compare open() function invocation between real and fake.

        Runs open(*args, **kwargs) on both real and fake.

        Args:
            *args: args to pass through to open()
            **kwargs: kwargs to pass through to open().

        Returns:
            None.

        Raises:
            AssertionError if underlying open() behavior differs from fake.
        """
        real_err = None
        fake_err = None
        try:
            with open(*args, **kwargs):
                pass
        except Exception as e:  # pylint: disable-msg=W0703
            real_err = e

        try:
            with self.fake_open(*args, **kwargs):
                pass
        except Exception as e:  # pylint: disable-msg=W0703
            fake_err = e

        # default equal in case one is None and other is not.
        is_exception_equal = (real_err == fake_err)
        if real_err and fake_err:
            # exception __eq__ doesn't evaluate equal ever, thus manual check.
            is_exception_equal = (type(real_err) is type(fake_err) and
                                  real_err.args == fake_err.args)

        if not is_exception_equal:
            msg = (
                "Behaviors don't match on open with args %s & kwargs %s.\n" %
                (args, kwargs))
            real_err_msg = 'Real open results in: %s\n' % repr(real_err)
            fake_err_msg = 'Fake open results in: %s\n' % repr(fake_err)
            self.fail(msg + real_err_msg + fake_err_msg)

    # Helpers for checks which are not straight method calls.
    @staticmethod
    def _access_real(path):
        return os.access(path, os.R_OK)

    def _access_fake(self, path):
        return self.fake_os.access(path, os.R_OK)

    def _stat_size_real(self, path):
        real_path, unused_fake_path = self._paths(path)
        # fake_filesystem.py does not implement stat().st_size for directories
        if os.path.isdir(real_path):
            return None
        return os.stat(real_path).st_size

    def _stat_size_fake(self, path):
        unused_real_path, fake_path = self._paths(path)
        # fake_filesystem.py does not implement stat().st_size for directories
        if self.fake_os.path.isdir(fake_path):
            return None
        return self.fake_os.stat(fake_path).st_size

    def _lstat_size_real(self, path):
        real_path, unused_fake_path = self._paths(path)
        if os.path.isdir(real_path):
            return None
        size = os.lstat(real_path).st_size
        # Account for the difference in the lengths of the absolute paths.
        if os.path.islink(real_path):
            if os.readlink(real_path).startswith(os.sep):
                size -= len(self.real_base)
        return size

    def _lstat_size_fake(self, path):
        unused_real_path, fake_path = self._paths(path)
        # size = 0
        if self.fake_os.path.isdir(fake_path):
            return None
        size = self.fake_os.lstat(fake_path).st_size
        # Account for the difference in the lengths of the absolute paths.
        if self.fake_os.path.islink(fake_path):
            if self.fake_os.readlink(fake_path).startswith(os.sep):
                size -= len(self.fake_base)
        return size

    def test_isabs(self):
        # We do not have to create any files for isabs.
        self.assertOsPathMethodBehaviorMatches('isabs', None)
        self.assertOsPathMethodBehaviorMatches('isabs', '')
        self.assertOsPathMethodBehaviorMatches('isabs', '/')
        self.assertOsPathMethodBehaviorMatches('isabs', '/a')
        self.assertOsPathMethodBehaviorMatches('isabs', 'a')

    def test_none_path(self):
        self.assertAllOsBehaviorsMatch(None)

    def test_empty_path(self):
        self.assertAllOsBehaviorsMatch('')

    def test_root_path(self):
        self.assertAllOsBehaviorsMatch('/')

    def test_non_existant_file(self):
        self.assertAllOsBehaviorsMatch('foo')

    def test_empty_file(self):
        self._create_test_file('f', 'aFile')
        self.assertAllOsBehaviorsMatch('aFile')

    def test_file_with_contents(self):
        self._create_test_file('f', 'aFile', 'some contents')
        self.assertAllOsBehaviorsMatch('aFile')

    def test_file_with_binary_contents(self):
        self._create_test_file('b', 'aFile', b'some contents')
        self.assertAllOsBehaviorsMatch('aFile')

    @unittest.skipIf(TestCase.is_windows, 'no symlink in Windows')
    def test_sym_link_to_empty_file(self):
        self._create_test_file('f', 'aFile')
        self._create_test_file('l', 'link_to_empty', 'aFile')
        self.assertAllOsBehaviorsMatch('link_to_empty')

    @unittest.skipIf(TestCase.is_windows, 'no symlink in Windows')
    def test_hard_link_to_empty_file(self):
        self._create_test_file('f', 'aFile')
        self._create_test_file('h', 'link_to_empty', 'aFile')
        self.assertAllOsBehaviorsMatch('link_to_empty')

    @unittest.skipIf(TestCase.is_windows, 'no symlink in Windows')
    def test_sym_link_to_real_file(self):
        self._create_test_file('f', 'aFile', 'some contents')
        self._create_test_file('l', 'link_to_file', 'aFile')
        self.assertAllOsBehaviorsMatch('link_to_file')

    @unittest.skipIf(TestCase.is_windows, 'no symlink in Windows')
    def test_hard_link_to_real_file(self):
        self._create_test_file('f', 'aFile', 'some contents')
        self._create_test_file('h', 'link_to_file', 'aFile')
        self.assertAllOsBehaviorsMatch('link_to_file')

    @unittest.skipIf(TestCase.is_windows, 'no symlink in Windows')
    def test_broken_sym_link(self):
        self._create_test_file('l', 'broken_link', 'broken')
        self._create_test_file('l', 'loop', '/a/loop')
        self.assertAllOsBehaviorsMatch('broken_link')

    def test_file_in_a_folder(self):
        self._create_test_file('d', 'a')
        self._create_test_file('d', 'a/b')
        self._create_test_file('f', 'a/b/file', 'contents')
        self.assertAllOsBehaviorsMatch('a/b/file')

    @unittest.skipIf(TestCase.is_windows, 'no symlink in Windows')
    def test_absolute_sym_link_to_folder(self):
        self._create_test_file('d', 'a')
        self._create_test_file('d', 'a/b')
        self._create_test_file('f', 'a/b/file', 'contents')
        self._create_test_file('l', 'a/link', '/a/b')
        self.assertAllOsBehaviorsMatch('a/link/file')

    @unittest.skipIf(TestCase.is_windows, 'no symlink in Windows')
    def test_link_to_folder_after_chdir(self):
        self._create_test_file('d', 'a')
        self._create_test_file('d', 'a/b')
        self._create_test_file('f', 'a/b/file', 'contents')
        self._create_test_file('l', 'a/link', '/a/b')

        real_dir, fake_dir = self._paths('a/b')
        os.chdir(real_dir)
        self.fake_os.chdir(fake_dir)
        self.assertAllOsBehaviorsMatch('file')

    @unittest.skipIf(TestCase.is_windows, 'no symlink in Windows')
    def test_relative_sym_link_to_folder(self):
        self._create_test_file('d', 'a')
        self._create_test_file('d', 'a/b')
        self._create_test_file('f', 'a/b/file', 'contents')
        self._create_test_file('l', 'a/link', 'b')
        self.assertAllOsBehaviorsMatch('a/link/file')

    @unittest.skipIf(TestCase.is_windows, 'no symlink in Windows')
    def test_sym_link_to_parent(self):
        # Soft links on HFS+ / OS X behave differently.
        if os.uname()[0] != 'Darwin':
            self._create_test_file('d', 'a')
            self._create_test_file('d', 'a/b')
            self._create_test_file('l', 'a/b/c', '..')
            self.assertAllOsBehaviorsMatch('a/b/c')

    @unittest.skipIf(TestCase.is_windows, 'no symlink in Windows')
    def test_path_through_sym_link_to_parent(self):
        self._create_test_file('d', 'a')
        self._create_test_file('f', 'a/target', 'contents')
        self._create_test_file('d', 'a/b')
        self._create_test_file('l', 'a/b/c', '..')
        self.assertAllOsBehaviorsMatch('a/b/c/target')

    @unittest.skipIf(TestCase.is_windows, 'no symlink in Windows')
    def test_sym_link_to_sibling_directory(self):
        self._create_test_file('d', 'a')
        self._create_test_file('d', 'a/b')
        self._create_test_file('d', 'a/sibling_of_b')
        self._create_test_file('f', 'a/sibling_of_b/target', 'contents')
        self._create_test_file('l', 'a/b/c', '../sibling_of_b')
        self.assertAllOsBehaviorsMatch('a/b/c/target')

    @unittest.skipIf(TestCase.is_windows, 'no symlink in Windows')
    def test_sym_link_to_sibling_directory_non_existant_file(self):
        self._create_test_file('d', 'a')
        self._create_test_file('d', 'a/b')
        self._create_test_file('d', 'a/sibling_of_b')
        self._create_test_file('f', 'a/sibling_of_b/target', 'contents')
        self._create_test_file('l', 'a/b/c', '../sibling_of_b')
        self.assertAllOsBehaviorsMatch('a/b/c/file_does_not_exist')

    @unittest.skipIf(TestCase.is_windows, 'no symlink in Windows')
    def test_broken_sym_link_to_sibling_directory(self):
        self._create_test_file('d', 'a')
        self._create_test_file('d', 'a/b')
        self._create_test_file('d', 'a/sibling_of_b')
        self._create_test_file('f', 'a/sibling_of_b/target', 'contents')
        self._create_test_file('l', 'a/b/c', '../broken_sibling_of_b')
        self.assertAllOsBehaviorsMatch('a/b/c/target')

    def test_relative_path(self):
        self._create_test_file('d', 'a')
        self._create_test_file('d', 'a/b')
        self._create_test_file('d', 'a/sibling_of_b')
        self._create_test_file('f', 'a/sibling_of_b/target', 'contents')
        self.assertAllOsBehaviorsMatch('a/b/../sibling_of_b/target')

    def test_broken_relative_path(self):
        self._create_test_file('d', 'a')
        self._create_test_file('d', 'a/b')
        self._create_test_file('d', 'a/sibling_of_b')
        self._create_test_file('f', 'a/sibling_of_b/target', 'contents')
        self.assertAllOsBehaviorsMatch('a/b/../broken/target')

    def test_bad_relative_path(self):
        self._create_test_file('d', 'a')
        self._create_test_file('f', 'a/target', 'contents')
        self._create_test_file('d', 'a/b')
        self._create_test_file('d', 'a/sibling_of_b')
        self._create_test_file('f', 'a/sibling_of_b/target', 'contents')
        self.assertAllOsBehaviorsMatch('a/b/../broken/../target')

    def test_getmtime_nonexistant_path(self):
        self.assertOsPathMethodBehaviorMatches('getmtime', 'no/such/path')

    def test_builtin_open_modes(self):
        self._create_test_file('f', 'read', 'some contents')
        self._create_test_file('f', 'write', 'some contents')
        self._create_test_file('f', 'append', 'some contents')
        self.assertFileHandleBehaviorsMatch('read', 'r', 'other contents')
        self.assertFileHandleBehaviorsMatch('write', 'w', 'other contents')
        self.assertFileHandleBehaviorsMatch('append', 'a', 'other contents')
        self._create_test_file('f', 'readplus', 'some contents')
        self._create_test_file('f', 'writeplus', 'some contents')
        self.assertFileHandleBehaviorsMatch(
            'readplus', 'r+', 'other contents')
        self.assertFileHandleBehaviorsMatch(
            'writeplus', 'w+', 'other contents')
        self._create_test_file('b', 'binaryread', b'some contents')
        self._create_test_file('b', 'binarywrite', b'some contents')
        self._create_test_file('b', 'binaryappend', b'some contents')
        self.assertFileHandleBehaviorsMatch(
            'binaryread', 'rb', b'other contents')
        self.assertFileHandleBehaviorsMatch(
            'binarywrite', 'wb', b'other contents')
        self.assertFileHandleBehaviorsMatch(
            'binaryappend', 'ab', b'other contents')
        self.assertFileHandleBehaviorsMatch('read', 'rb', 'other contents')
        self.assertFileHandleBehaviorsMatch('write', 'wb', 'other contents')
        self.assertFileHandleBehaviorsMatch('append', 'ab', 'other contents')

        # binary cannot have encoding
        self.assertFileHandleOpenBehaviorsMatch('read', 'rb', encoding='enc')
        self.assertFileHandleOpenBehaviorsMatch(
            'write', mode='wb', encoding='enc')
        self.assertFileHandleOpenBehaviorsMatch('append', 'ab', encoding='enc')

        # text can have encoding
        self.assertFileHandleOpenBehaviorsMatch('read', 'r', encoding='utf-8')
        self.assertFileHandleOpenBehaviorsMatch('write', 'w', encoding='utf-8')
        self.assertFileHandleOpenBehaviorsMatch(
            'append', 'a', encoding='utf-8')


def main(_):
    unittest.main()


if __name__ == '__main__':
    unittest.main()
