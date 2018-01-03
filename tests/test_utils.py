# Copyright 2009 Google Inc. All Rights Reserved.
# Copyright 2015-2017 John McGehee
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

"""Common helper classes used in tests, or as test class base."""

import errno
import os
import platform
import shutil
import stat
import sys
import tempfile
import unittest

from pyfakefs import fake_filesystem


class DummyTime(object):
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
        self.base_path = None
        if self.use_real_fs():
            self.base_path = tempfile.mkdtemp()

    @property
    def is_windows_fs(self):
        return TestCase.is_windows

    def set_windows_fs(self, value):
        if self.filesystem is not None:
            self.filesystem.is_windows_fs = value
            if value:
                self.filesystem.is_macos = False
            self.create_basepath()

    @property
    def is_macos(self):
        return TestCase.is_macos

    @property
    def is_pypy(self):
        return platform.python_implementation() == 'PyPy'

    def use_real_fs(self):
        return False

    def path_separator(self):
        if self.use_real_fs():
            return os.path.sep
        return '/'

    def check_windows_only(self):
        if self.use_real_fs():
            if not TestCase.is_windows:
                raise unittest.SkipTest(
                    'Testing Windows specific functionality')
        else:
            self.set_windows_fs(True)

    def check_linux_only(self):
        if self.use_real_fs():
            if TestCase.is_macos or TestCase.is_windows:
                raise unittest.SkipTest(
                    'Testing Linux specific functionality')
        else:
            self.set_windows_fs(False)
            self.filesystem.is_macos = False

    def check_macos_only(self):
        if self.use_real_fs():
            if not TestCase.is_macos:
                raise unittest.SkipTest(
                    'Testing MacOS specific functionality')
        else:
            self.set_windows_fs(False)
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
            self.set_windows_fs(False)

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

    def create_basepath(self):
        if self.filesystem is not None:
            old_base_path = self.base_path
            self.base_path = self.filesystem.path_separator + 'basepath'
            if self.is_windows_fs:
                self.base_path = 'C:' + self.base_path
            if old_base_path != self.base_path:
                if not self.filesystem.exists(self.base_path):
                    self.filesystem.create_dir(self.base_path)
                if old_base_path is not None:
                    for entry in self.filesystem.listdir(old_base_path):
                        old_name = self.os.path.join(old_base_path, entry)
                        new_name = self.os.path.join(self.base_path, entry)
                        self.filesystem.rename(old_name, new_name)
                    self.os.removedirs(old_base_path)


class RealFsTestCase(TestCase, RealFsTestMixin):
    def __init__(self, methodName='runTest'):
        TestCase.__init__(self, methodName)
        RealFsTestMixin.__init__(self)

    def setUp(self):
        self.cwd = os.getcwd()
        if not self.use_real_fs():
            self.filesystem = fake_filesystem.FakeFilesystem(
                path_separator=self.path_separator())
            self.open = fake_filesystem.FakeFileOpen(self.filesystem)
            self.os = fake_filesystem.FakeOsModule(self.filesystem)
            self.create_basepath()

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
            self.os.chdir(self.cwd)
