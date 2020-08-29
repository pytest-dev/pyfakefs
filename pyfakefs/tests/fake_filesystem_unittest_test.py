# Copyright 2014 Altera Corporation. All Rights Reserved.
# Copyright 2015-2017 John McGehee
# Author: John McGehee
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

"""
Test the :py:class`pyfakefs.fake_filesystem_unittest.TestCase` base class.
"""
import glob
import io
import multiprocessing
import os
import shutil
import sys
import tempfile
import unittest
import warnings
from distutils.dir_util import copy_tree, remove_tree
from unittest import TestCase

import pyfakefs.tests.import_as_example
from pyfakefs import fake_filesystem_unittest, fake_filesystem
from pyfakefs.extra_packages import pathlib
from pyfakefs.fake_filesystem_unittest import Patcher, Pause, patchfs
from pyfakefs.tests.fixtures import module_with_attributes


class TestPatcher(TestCase):
    def test_context_manager(self):
        with Patcher() as patcher:
            patcher.fs.create_file('/foo/bar', contents='test')
            with open('/foo/bar') as f:
                contents = f.read()
            self.assertEqual('test', contents)

    @patchfs
    def test_context_decorator(self, fs):
        fs.create_file('/foo/bar', contents='test')
        with open('/foo/bar') as f:
            contents = f.read()
        self.assertEqual('test', contents)


class TestPyfakefsUnittestBase(fake_filesystem_unittest.TestCase):
    def setUp(self):
        """Set up the fake file system"""
        self.setUpPyfakefs()


class TestPyfakefsUnittest(TestPyfakefsUnittestBase):  # pylint: disable=R0904
    """Test the `pyfakefs.fake_filesystem_unittest.TestCase` base class."""

    def test_open(self):
        """Fake `open()` function is bound"""
        self.assertFalse(os.path.exists('/fake_file.txt'))
        with open('/fake_file.txt', 'w') as f:
            f.write("This test file was created using the open() function.\n")
        self.assertTrue(self.fs.exists('/fake_file.txt'))
        with open('/fake_file.txt') as f:
            content = f.read()
        self.assertEqual(content, 'This test file was created using the '
                                  'open() function.\n')

    def test_io_open(self):
        """Fake io module is bound"""
        self.assertFalse(os.path.exists('/fake_file.txt'))
        with io.open('/fake_file.txt', 'w') as f:
            f.write("This test file was created using the"
                    " io.open() function.\n")
        self.assertTrue(self.fs.exists('/fake_file.txt'))
        with open('/fake_file.txt') as f:
            content = f.read()
        self.assertEqual(content, 'This test file was created using the '
                                  'io.open() function.\n')

    def test_os(self):
        """Fake os module is bound"""
        self.assertFalse(self.fs.exists('/test/dir1/dir2'))
        os.makedirs('/test/dir1/dir2')
        self.assertTrue(self.fs.exists('/test/dir1/dir2'))

    def test_glob(self):
        """Fake glob module is bound"""
        is_windows = sys.platform.startswith('win')
        self.assertEqual(glob.glob('/test/dir1/dir*'),
                         [])
        self.fs.create_dir('/test/dir1/dir2a')
        matching_paths = glob.glob('/test/dir1/dir*')
        if is_windows:
            self.assertEqual(matching_paths, [r'\test\dir1\dir2a'])
        else:
            self.assertEqual(matching_paths, ['/test/dir1/dir2a'])
        self.fs.create_dir('/test/dir1/dir2b')
        matching_paths = sorted(glob.glob('/test/dir1/dir*'))
        if is_windows:
            self.assertEqual(matching_paths,
                             [r'\test\dir1\dir2a', r'\test\dir1\dir2b'])
        else:
            self.assertEqual(matching_paths,
                             ['/test/dir1/dir2a', '/test/dir1/dir2b'])

    def test_shutil(self):
        """Fake shutil module is bound"""
        self.fs.create_dir('/test/dir1/dir2a')
        self.fs.create_dir('/test/dir1/dir2b')
        self.assertTrue(self.fs.exists('/test/dir1/dir2b'))
        self.assertTrue(self.fs.exists('/test/dir1/dir2a'))

        shutil.rmtree('/test/dir1')
        self.assertFalse(self.fs.exists('/test/dir1'))

    def test_fakepathlib(self):
        with pathlib.Path('/fake_file.txt') as p:
            with p.open('w') as f:
                f.write('text')
        is_windows = sys.platform.startswith('win')
        if is_windows:
            self.assertTrue(self.fs.exists(r'\fake_file.txt'))
        else:
            self.assertTrue(self.fs.exists('/fake_file.txt'))


class TestPatchingImports(TestPyfakefsUnittestBase):
    def test_import_as_other_name(self):
        file_path = '/foo/bar/baz'
        self.fs.create_file(file_path)
        self.assertTrue(self.fs.exists(file_path))
        self.assertTrue(
            pyfakefs.tests.import_as_example.check_if_exists1(file_path))

    def test_import_path_from_os(self):
        """Make sure `from os import path` patches `path`."""
        file_path = '/foo/bar/baz'
        self.fs.create_file(file_path)
        self.assertTrue(self.fs.exists(file_path))
        self.assertTrue(
            pyfakefs.tests.import_as_example.check_if_exists2(file_path))

    def test_import_path_from_pathlib(self):
        file_path = '/foo/bar'
        self.fs.create_dir(file_path)
        self.assertTrue(
            pyfakefs.tests.import_as_example.check_if_exists3(file_path))

    def test_import_function_from_os_path(self):
        file_path = '/foo/bar'
        self.fs.create_dir(file_path)
        self.assertTrue(
            pyfakefs.tests.import_as_example.check_if_exists5(file_path))

    def test_import_function_from_os_path_as_other_name(self):
        file_path = '/foo/bar'
        self.fs.create_dir(file_path)
        self.assertTrue(
            pyfakefs.tests.import_as_example.check_if_exists6(file_path))

    def test_import_function_from_os(self):
        file_path = '/foo/bar'
        self.fs.create_file(file_path, contents=b'abc')
        stat_result = pyfakefs.tests.import_as_example.file_stat1(file_path)
        self.assertEqual(3, stat_result.st_size)

    def test_import_function_from_os_as_other_name(self):
        file_path = '/foo/bar'
        self.fs.create_file(file_path, contents=b'abc')
        stat_result = pyfakefs.tests.import_as_example.file_stat2(file_path)
        self.assertEqual(3, stat_result.st_size)

    def test_import_open_as_other_name(self):
        file_path = '/foo/bar'
        self.fs.create_file(file_path, contents=b'abc')
        contents = pyfakefs.tests.import_as_example.file_contents1(file_path)
        self.assertEqual('abc', contents)

    def test_import_io_open_as_other_name(self):
        file_path = '/foo/bar'
        self.fs.create_file(file_path, contents=b'abc')
        contents = pyfakefs.tests.import_as_example.file_contents2(file_path)
        self.assertEqual('abc', contents)


class TestPatchingDefaultArgs(TestPyfakefsUnittestBase):
    def test_path_exists_as_default_arg_in_function(self):
        file_path = '/foo/bar'
        self.fs.create_dir(file_path)
        self.assertTrue(
            pyfakefs.tests.import_as_example.check_if_exists4(file_path))

    def test_path_exists_as_default_arg_in_method(self):
        file_path = '/foo/bar'
        self.fs.create_dir(file_path)
        sut = pyfakefs.tests.import_as_example.TestDefaultArg()
        self.assertTrue(sut.check_if_exists(file_path))


class TestAttributesWithFakeModuleNames(TestPyfakefsUnittestBase):
    """Test that module attributes with names like `path` or `io` are not
    stubbed out.
    """

    def test_attributes(self):
        """Attributes of module under test are not patched"""
        self.assertEqual(module_with_attributes.os, 'os attribute value')
        self.assertEqual(module_with_attributes.path, 'path attribute value')
        self.assertEqual(module_with_attributes.pathlib,
                         'pathlib attribute value')
        self.assertEqual(module_with_attributes.shutil,
                         'shutil attribute value')
        self.assertEqual(module_with_attributes.io, 'io attribute value')


import math as path  # noqa: E402 wanted import not at top


class TestPathNotPatchedIfNotOsPath(TestPyfakefsUnittestBase):
    """Tests that `path` is not patched if it is not `os.path`.
       An own path module (in this case an alias to math) can be imported
       and used.
    """

    def test_own_path_module(self):
        self.assertEqual(2, path.floor(2.5))


class FailedPatchingTest(TestPyfakefsUnittestBase):
    """Negative tests: make sure the tests for `modules_to_reload` and
    `modules_to_patch` fail if not providing the arguments.
    """

    @unittest.expectedFailure
    def test_system_stat(self):
        file_path = '/foo/bar'
        self.fs.create_file(file_path, contents=b'test')
        self.assertEqual(
            4, pyfakefs.tests.import_as_example.system_stat(file_path).st_size)


class ReloadModuleTest(fake_filesystem_unittest.TestCase):
    """Make sure that reloading a module allows patching of classes not
    patched automatically.
    """

    def setUp(self):
        """Set up the fake file system"""
        self.setUpPyfakefs(
            modules_to_reload=[pyfakefs.tests.import_as_example])


class NoSkipNamesTest(fake_filesystem_unittest.TestCase):
    """Reference test for additional_skip_names tests:
     make sure that the module is patched by default."""

    def test_path_exists(self):
        self.assertTrue(
            pyfakefs.tests.import_as_example.exists_this_file())


class AdditionalSkipNamesTest(fake_filesystem_unittest.TestCase):
    """Make sure that modules in additional_skip_names are not patched.
    Passes module name to `additional_skip_names`."""

    def setUp(self):
        self.setUpPyfakefs(
            additional_skip_names=['pyfakefs.tests.import_as_example'])

    def test_path_exists(self):
        self.assertFalse(
            pyfakefs.tests.import_as_example.exists_this_file())


class AdditionalSkipNamesModuleTest(fake_filesystem_unittest.TestCase):
    """Make sure that modules in additional_skip_names are not patched.
    Passes module to `additional_skip_names`."""

    def setUp(self):
        self.setUpPyfakefs(
            additional_skip_names=[pyfakefs.tests.import_as_example])

    def test_path_exists(self):
        self.assertFalse(
            pyfakefs.tests.import_as_example.exists_this_file())


class FakeExampleModule:
    """Used to patch a function that uses system-specific functions that
    cannot be patched automatically."""
    _orig_module = pyfakefs.tests.import_as_example

    def __init__(self, fs):
        pass

    def system_stat(self, filepath):
        return os.stat(filepath)

    def __getattr__(self, name):
        """Forwards any non-faked calls to the standard module."""
        return getattr(self._orig_module, name)


class PatchModuleTest(fake_filesystem_unittest.TestCase):
    """Make sure that reloading a module allows patching of classes not
    patched automatically.
    """

    def setUp(self):
        """Set up the fake file system"""
        self.setUpPyfakefs(
            modules_to_patch={
                'pyfakefs.tests.import_as_example': FakeExampleModule})

    def test_system_stat(self):
        file_path = '/foo/bar'
        self.fs.create_file(file_path, contents=b'test')
        self.assertEqual(
            4, pyfakefs.tests.import_as_example.system_stat(file_path).st_size)


class PatchModuleTestUsingDecorator(unittest.TestCase):
    """Make sure that reloading a module allows patching of classes not
    patched automatically - use patchfs decorator with parameter.
    """

    @patchfs
    @unittest.expectedFailure
    def test_system_stat_failing(self, fs):
        file_path = '/foo/bar'
        fs.create_file(file_path, contents=b'test')
        self.assertEqual(
            4, pyfakefs.tests.import_as_example.system_stat(file_path).st_size)

    @patchfs(modules_to_patch={
        'pyfakefs.tests.import_as_example': FakeExampleModule})
    def test_system_stat(self, fs):
        file_path = '/foo/bar'
        fs.create_file(file_path, contents=b'test')
        self.assertEqual(
            4, pyfakefs.tests.import_as_example.system_stat(file_path).st_size)


class NoRootUserTest(fake_filesystem_unittest.TestCase):
    """Test allow_root_user argument to setUpPyfakefs."""

    def setUp(self):
        self.setUpPyfakefs(allow_root_user=False)

    def test_non_root_behavior(self):
        """Check that fs behaves as non-root user regardless of actual
        user rights.
        """
        self.fs.is_windows_fs = False
        dir_path = '/foo/bar'
        self.fs.create_dir(dir_path, perm_bits=0o555)
        file_path = dir_path + 'baz'
        with self.assertRaises(OSError):
            self.fs.create_file(file_path)

        file_path = '/baz'
        self.fs.create_file(file_path)
        os.chmod(file_path, 0o400)
        with self.assertRaises(OSError):
            open(file_path, 'w')


class PauseResumeTest(TestPyfakefsUnittestBase):
    def test_pause_resume(self):
        fake_temp_file = tempfile.NamedTemporaryFile()
        self.assertTrue(self.fs.exists(fake_temp_file.name))
        self.assertTrue(os.path.exists(fake_temp_file.name))
        self.pause()
        self.assertTrue(self.fs.exists(fake_temp_file.name))
        self.assertFalse(os.path.exists(fake_temp_file.name))
        real_temp_file = tempfile.NamedTemporaryFile()
        self.assertFalse(self.fs.exists(real_temp_file.name))
        self.assertTrue(os.path.exists(real_temp_file.name))
        self.resume()
        self.assertFalse(os.path.exists(real_temp_file.name))
        self.assertTrue(os.path.exists(fake_temp_file.name))

    def test_pause_resume_fs(self):
        fake_temp_file = tempfile.NamedTemporaryFile()
        self.assertTrue(self.fs.exists(fake_temp_file.name))
        self.assertTrue(os.path.exists(fake_temp_file.name))
        # resume does nothing if not paused
        self.fs.resume()
        self.assertTrue(os.path.exists(fake_temp_file.name))
        self.fs.pause()
        self.assertTrue(self.fs.exists(fake_temp_file.name))
        self.assertFalse(os.path.exists(fake_temp_file.name))
        real_temp_file = tempfile.NamedTemporaryFile()
        self.assertFalse(self.fs.exists(real_temp_file.name))
        self.assertTrue(os.path.exists(real_temp_file.name))
        # pause does nothing if already paused
        self.fs.pause()
        self.assertFalse(self.fs.exists(real_temp_file.name))
        self.assertTrue(os.path.exists(real_temp_file.name))
        self.fs.resume()
        self.assertFalse(os.path.exists(real_temp_file.name))
        self.assertTrue(os.path.exists(fake_temp_file.name))

    def test_pause_resume_contextmanager(self):
        fake_temp_file = tempfile.NamedTemporaryFile()
        self.assertTrue(self.fs.exists(fake_temp_file.name))
        self.assertTrue(os.path.exists(fake_temp_file.name))
        with Pause(self):
            self.assertTrue(self.fs.exists(fake_temp_file.name))
            self.assertFalse(os.path.exists(fake_temp_file.name))
            real_temp_file = tempfile.NamedTemporaryFile()
            self.assertFalse(self.fs.exists(real_temp_file.name))
            self.assertTrue(os.path.exists(real_temp_file.name))
        self.assertFalse(os.path.exists(real_temp_file.name))
        self.assertTrue(os.path.exists(fake_temp_file.name))

    def test_pause_resume_fs_contextmanager(self):
        fake_temp_file = tempfile.NamedTemporaryFile()
        self.assertTrue(self.fs.exists(fake_temp_file.name))
        self.assertTrue(os.path.exists(fake_temp_file.name))
        with Pause(self.fs):
            self.assertTrue(self.fs.exists(fake_temp_file.name))
            self.assertFalse(os.path.exists(fake_temp_file.name))
            real_temp_file = tempfile.NamedTemporaryFile()
            self.assertFalse(self.fs.exists(real_temp_file.name))
            self.assertTrue(os.path.exists(real_temp_file.name))
        self.assertFalse(os.path.exists(real_temp_file.name))
        self.assertTrue(os.path.exists(fake_temp_file.name))

    def test_pause_resume_without_patcher(self):
        fs = fake_filesystem.FakeFilesystem()
        with self.assertRaises(RuntimeError):
            fs.resume()


class PauseResumePatcherTest(fake_filesystem_unittest.TestCase):
    def test_pause_resume(self):
        with Patcher() as p:
            fake_temp_file = tempfile.NamedTemporaryFile()
            self.assertTrue(p.fs.exists(fake_temp_file.name))
            self.assertTrue(os.path.exists(fake_temp_file.name))
            p.pause()
            self.assertTrue(p.fs.exists(fake_temp_file.name))
            self.assertFalse(os.path.exists(fake_temp_file.name))
            real_temp_file = tempfile.NamedTemporaryFile()
            self.assertFalse(p.fs.exists(real_temp_file.name))
            self.assertTrue(os.path.exists(real_temp_file.name))
            p.resume()
            self.assertFalse(os.path.exists(real_temp_file.name))
            self.assertTrue(os.path.exists(fake_temp_file.name))

    def test_pause_resume_contextmanager(self):
        with Patcher() as p:
            fake_temp_file = tempfile.NamedTemporaryFile()
            self.assertTrue(p.fs.exists(fake_temp_file.name))
            self.assertTrue(os.path.exists(fake_temp_file.name))
            with Pause(p):
                self.assertTrue(p.fs.exists(fake_temp_file.name))
                self.assertFalse(os.path.exists(fake_temp_file.name))
                real_temp_file = tempfile.NamedTemporaryFile()
                self.assertFalse(p.fs.exists(real_temp_file.name))
                self.assertTrue(os.path.exists(real_temp_file.name))
            self.assertFalse(os.path.exists(real_temp_file.name))
            self.assertTrue(os.path.exists(fake_temp_file.name))


class TestPyfakefsTestCase(unittest.TestCase):
    def setUp(self):
        class TestTestCase(fake_filesystem_unittest.TestCase):
            def runTest(self):
                pass

        self.test_case = TestTestCase('runTest')

    def test_test_case_type(self):
        self.assertIsInstance(self.test_case, unittest.TestCase)

        self.assertIsInstance(self.test_case,
                              fake_filesystem_unittest.TestCaseMixin)


class TestTempFileReload(unittest.TestCase):
    """Regression test for #356 to make sure that reloading the tempfile
    does not affect other tests."""

    def test_fakefs(self):
        with Patcher() as patcher:
            patcher.fs.create_file('/mytempfile', contents='abcd')

    def test_value(self):
        v = multiprocessing.Value('I', 0)
        self.assertEqual(v.value, 0)


class TestPyfakefsTestCaseMixin(unittest.TestCase,
                                fake_filesystem_unittest.TestCaseMixin):
    def test_set_up_pyfakefs(self):
        self.setUpPyfakefs()

        self.assertTrue(hasattr(self, 'fs'))
        self.assertIsInstance(self.fs, fake_filesystem.FakeFilesystem)


class TestShutilWithZipfile(fake_filesystem_unittest.TestCase):
    """Regression test for #427."""

    def setUp(self):
        self.setUpPyfakefs()
        self.fs.create_file('foo/bar')

    def test_a(self):
        shutil.make_archive('archive', 'zip', root_dir='foo')

    def test_b(self):
        # used to fail because 'bar' could not be found
        shutil.make_archive('archive', 'zip', root_dir='foo')


class TestDistutilsCopyTree(fake_filesystem_unittest.TestCase):
    """Regression test for #501."""

    def setUp(self):
        self.setUpPyfakefs()
        self.fs.create_dir("./test/subdir/")
        self.fs.create_dir("./test/subdir2/")
        self.fs.create_file("./test2/subdir/1.txt")

    def test_file_copied(self):
        copy_tree("./test2/", "./test/")
        remove_tree("./test2/")

        self.assertTrue(os.path.isfile('./test/subdir/1.txt'))
        self.assertFalse(os.path.isdir('./test2/'))

    def test_file_copied_again(self):
        # used to fail because 'test2' could not be found
        self.assertTrue(os.path.isfile('./test2/subdir/1.txt'))

        copy_tree("./test2/", "./test/")
        remove_tree("./test2/")

        self.assertTrue(os.path.isfile('./test/subdir/1.txt'))
        self.assertFalse(os.path.isdir('./test2/'))


class PathlibTest(TestCase):
    """Regression test for #527"""

    @patchfs
    def test_cwd(self, fs):
        """Make sure fake file system is used for os in pathlib"""
        self.assertEqual(os.path.sep, str(pathlib.Path.cwd()))
        dot_abs = pathlib.Path(".").absolute()
        self.assertEqual(os.path.sep, str(dot_abs))
        self.assertTrue(dot_abs.exists())


class TestDeprecationSuppression(fake_filesystem_unittest.TestCase):
    def test_no_deprecation_warning(self):
        """Ensures that deprecation warnings are suppressed during module
        lookup, see #542.
        """

        from pyfakefs.tests.fixtures.deprecated_property import \
            DeprecationTest  # noqa: F401

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("error", DeprecationWarning)
            self.setUpPyfakefs()
            self.assertEqual(0, len(w))


if __name__ == "__main__":
    unittest.main()
