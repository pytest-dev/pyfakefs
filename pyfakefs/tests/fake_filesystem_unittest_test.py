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
import importlib.util
import io
import multiprocessing
import os
import pathlib
import runpy
import shutil
import sys
import tempfile
import unittest
import warnings
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import TestCase, mock

import pyfakefs.tests.import_as_example
import pyfakefs.tests.logsio
from pyfakefs import fake_filesystem_unittest, fake_filesystem
from pyfakefs.fake_filesystem import OSType
from pyfakefs.fake_filesystem_unittest import (
    Patcher,
    Pause,
    patchfs,
    PatchMode,
)
from pyfakefs.tests.fixtures import module_with_attributes

if sys.version_info < (3, 12):
    # distutils removed in Python 3.12
    from distutils.dir_util import copy_tree, remove_tree


# Work around pyupgrade auto-rewriting `io.open()` to `open()`.
io_open = io.open


class TestPatcher(TestCase):
    def test_context_manager(self):
        with Patcher() as patcher:
            patcher.fs.create_file("/foo/bar", contents="test")
            with open("/foo/bar", encoding="utf8") as f:
                contents = f.read()
            self.assertEqual("test", contents)

    @patchfs
    def test_context_decorator(self, fake_fs):
        fake_fs.create_file("/foo/bar", contents="test")
        with open("/foo/bar", encoding="utf8") as f:
            contents = f.read()
        self.assertEqual("test", contents)

    def test_nested_invocation(self):
        with Patcher() as patcher:
            patcher.fs.create_file("/foo/bar", contents="test")
            self.assertTrue(patcher.fs.exists("/foo/bar"))
            with Patcher() as patcher1:
                self.assertTrue(patcher1.fs.exists("/foo/bar"))
                patcher1.fs.create_file("/foo/baz", contents="test")
                self.assertTrue(patcher1.fs.exists("/foo/baz"))
            self.assertTrue(patcher.fs.exists("/foo/baz"))

    def test_nested_invocation_with_args(self):
        with Patcher() as patcher:
            patcher.fs.create_file("/foo/bar", contents="test")
            with self.assertWarnsRegex(
                UserWarning, "Nested fake filesystem invocation using custom arguments"
            ):
                with Patcher(allow_root_user=False):
                    pass


class TestPatchfsArgumentOrder(TestCase):
    @patchfs
    @mock.patch("os.system")
    def test_argument_order1(self, fake_fs, patched_system):
        fake_fs.create_file("/foo/bar", contents="test")
        with open("/foo/bar", encoding="utf8") as f:
            contents = f.read()
        self.assertEqual("test", contents)
        os.system("foo")
        patched_system.assert_called_with("foo")

    @mock.patch("os.system")
    @patchfs
    def test_argument_order2(self, patched_system, fake_fs):
        fake_fs.create_file("/foo/bar", contents="test")
        with open("/foo/bar", encoding="utf8") as f:
            contents = f.read()
        self.assertEqual("test", contents)
        os.system("foo")
        patched_system.assert_called_with("foo")


class TestPyfakefsUnittestBase(fake_filesystem_unittest.TestCase):
    def setUp(self):
        """Set up the fake file system"""
        self.setUpPyfakefs()


class TestPyfakefsUnittest(TestPyfakefsUnittestBase):  # pylint: disable=R0904
    """Test the `pyfakefs.fake_filesystem_unittest.TestCase` base class."""

    def test_open(self):
        """Fake `open()` function is bound"""
        self.assertFalse(os.path.exists("/fake_file.txt"))
        with open("/fake_file.txt", "w", encoding="utf8") as f:
            f.write("This test file was created using the open() function.\n")
        self.assertTrue(self.fs.exists("/fake_file.txt"))
        with open("/fake_file.txt", encoding="utf8") as f:
            content = f.read()
        self.assertEqual(
            "This test file was created using the open() function.\n",
            content,
        )

    def test_io_open(self):
        """Fake io module is bound"""
        self.assertFalse(os.path.exists("/fake_file.txt"))
        with io_open("/fake_file.txt", "w", encoding="utf8") as f:
            f.write("This test file was created using the io.open() function.\n")
        self.assertTrue(self.fs.exists("/fake_file.txt"))
        with open("/fake_file.txt", encoding="utf8") as f:
            content = f.read()
        self.assertEqual(
            "This test file was created using the io.open() function.\n",
            content,
        )

    def test_os(self):
        """Fake os module is bound"""
        self.assertFalse(self.fs.exists("/test/dir1/dir2"))
        os.makedirs("/test/dir1/dir2")
        self.assertTrue(self.fs.exists("/test/dir1/dir2"))

    def test_glob(self):
        """Fake glob module is bound"""
        is_windows = sys.platform.startswith("win")
        self.assertEqual([], glob.glob("/test/dir1/dir*"))
        self.fs.create_dir("/test/dir1/dir2a")
        matching_paths = glob.glob("/test/dir1/dir*")
        if is_windows:
            self.assertEqual([r"/test/dir1\dir2a"], matching_paths)
        else:
            self.assertEqual(["/test/dir1/dir2a"], matching_paths)
        self.fs.create_dir("/test/dir1/dir2b")
        matching_paths = sorted(glob.glob("/test/dir1/dir*"))
        if is_windows:
            self.assertEqual([r"/test/dir1\dir2a", r"/test/dir1\dir2b"], matching_paths)
        else:
            self.assertEqual(["/test/dir1/dir2a", "/test/dir1/dir2b"], matching_paths)

    def test_shutil(self):
        """Fake shutil module is bound"""
        self.fs.create_dir("/test/dir1/dir2a")
        self.fs.create_dir("/test/dir1/dir2b")
        self.assertTrue(self.fs.exists("/test/dir1/dir2b"))
        self.assertTrue(self.fs.exists("/test/dir1/dir2a"))

        shutil.rmtree("/test/dir1")
        self.assertFalse(self.fs.exists("/test/dir1"))

    def test_fakepathlib(self):
        p = pathlib.Path("/fake_file.txt")
        with p.open("w", encoding="utf8") as f:
            f.write("text")
        is_windows = sys.platform.startswith("win")
        if is_windows:
            self.assertTrue(self.fs.exists(r"\fake_file.txt"))
        else:
            self.assertTrue(self.fs.exists("/fake_file.txt"))


class TestPatchingImports(TestPyfakefsUnittestBase):
    def test_import_as_other_name(self):
        file_path = "/foo/bar/baz"
        self.fs.create_file(file_path)
        self.assertTrue(self.fs.exists(file_path))
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_exists1(file_path))

    def test_import_path_from_os(self):
        """Make sure `from os import path` patches `path`."""
        file_path = "/foo/bar/baz"
        self.fs.create_file(file_path)
        self.assertTrue(self.fs.exists(file_path))
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_exists2(file_path))

    def test_import_path_from_pathlib(self):
        file_path = "/foo/bar"
        self.fs.create_dir(file_path)
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_exists3(file_path))

    def test_import_exists_from_os_path(self):
        file_path = "/foo/bar"
        self.fs.create_dir(file_path)
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_exists5(file_path))

    def test_import_isfile_from_os_path(self):
        file_path = "/foo/bar"
        self.fs.create_file(file_path)
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_isfile(file_path))

    def test_import_isdir_from_os_path(self):
        file_path = "/foo/bar"
        self.fs.create_dir(file_path)
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_isdir(file_path))

    def test_import_islink_from_os_path(self):
        file_path = "/foo/bar"
        link_path = "/foo/link"
        self.fs.create_file(file_path)
        self.fs.create_symlink(link_path, file_path)
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_islink(link_path))

    def test_import_function_from_os_path_as_other_name(self):
        file_path = "/foo/bar"
        self.fs.create_dir(file_path)
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_exists6(file_path))

    def test_import_pathlib_path(self):
        file_path = "/foo/bar"
        self.fs.create_dir(file_path)
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_exists7(file_path))

    def test_import_function_from_os(self):
        file_path = "/foo/bar"
        self.fs.create_file(file_path, contents=b"abc")
        stat_result = pyfakefs.tests.import_as_example.file_stat1(file_path)
        self.assertEqual(3, stat_result.st_size)

    def test_import_function_from_os_as_other_name(self):
        file_path = "/foo/bar"
        self.fs.create_file(file_path, contents=b"abc")
        stat_result = pyfakefs.tests.import_as_example.file_stat2(file_path)
        self.assertEqual(3, stat_result.st_size)

    def test_import_open_as_other_name(self):
        file_path = "/foo/bar"
        self.fs.create_file(file_path, contents=b"abc")
        contents = pyfakefs.tests.import_as_example.file_contents1(file_path)
        self.assertEqual("abc", contents)

    def test_import_io_open_as_other_name(self):
        file_path = "/foo/bar"
        self.fs.create_file(file_path, contents=b"abc")
        contents = pyfakefs.tests.import_as_example.file_contents2(file_path)
        self.assertEqual("abc", contents)


class TestPatchingDefaultArgs(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs(patch_default_args=True)

    def test_path_exists_as_default_arg_in_function(self):
        file_path = "/foo/bar"
        self.fs.create_dir(file_path)
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_exists4(file_path))

    def test_path_exists_as_default_arg_in_method(self):
        file_path = "/foo/bar"
        self.fs.create_dir(file_path)
        sut = pyfakefs.tests.import_as_example.TestDefaultArg()
        self.assertTrue(sut.check_if_exists(file_path))

    def test_fake_path_exists4(self):
        self.fs.create_file("foo")
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_exists4("foo"))


class TestAttributesWithFakeModuleNames(TestPyfakefsUnittestBase):
    """Test that module attributes with names like `path` or `io` are not
    stubbed out.
    """

    def test_attributes(self):
        """Attributes of module under test are not patched"""
        self.assertEqual(module_with_attributes.os, "os attribute value")
        self.assertEqual(module_with_attributes.path, "path attribute value")
        self.assertEqual(module_with_attributes.pathlib, "pathlib attribute value")
        self.assertEqual(module_with_attributes.shutil, "shutil attribute value")
        self.assertEqual(module_with_attributes.io, "io attribute value")


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
        file_path = "/foo/bar"
        self.fs.create_file(file_path, contents=b"test")
        self.assertEqual(
            4, pyfakefs.tests.import_as_example.system_stat(file_path).st_size
        )


class ReloadModuleTest(fake_filesystem_unittest.TestCase):
    """Make sure that reloading a module allows patching of classes not
    patched automatically.
    """

    def setUp(self):
        """Set up the fake file system"""
        self.setUpPyfakefs(modules_to_reload=[pyfakefs.tests.import_as_example])


class NoSkipNamesTest(fake_filesystem_unittest.TestCase):
    """Reference test for additional_skip_names tests:
    make sure that the module is patched by default."""

    def setUp(self):
        self.setUpPyfakefs()

    def test_path_exists(self):
        self.assertFalse(pyfakefs.tests.import_as_example.exists_this_file())

    def test_fake_path_exists1(self):
        self.fs.create_file("foo")
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_exists1("foo"))

    def test_fake_path_exists2(self):
        self.fs.create_file("foo")
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_exists2("foo"))

    def test_fake_path_exists3(self):
        self.fs.create_file("foo")
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_exists3("foo"))

    def test_fake_path_exists5(self):
        self.fs.create_file("foo")
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_exists5("foo"))

    def test_fake_path_exists6(self):
        self.fs.create_file("foo")
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_exists6("foo"))

    def test_fake_path_exists7(self):
        self.fs.create_file("foo")
        self.assertTrue(pyfakefs.tests.import_as_example.check_if_exists7("foo"))

    def test_open_fails(self):
        with self.assertRaises(OSError):
            pyfakefs.tests.import_as_example.open_this_file()

    def test_open_patched_in_module_ending_with_io(self):
        # regression test for #569
        file_path = "/foo/bar"
        self.fs.create_file(file_path, contents=b"abc")
        contents = pyfakefs.tests.logsio.file_contents(file_path)
        self.assertEqual(b"abc", contents)


class AdditionalSkipNamesTest(fake_filesystem_unittest.TestCase):
    """Make sure that modules in additional_skip_names are not patched.
    Passes module name to `additional_skip_names`."""

    def setUp(self):
        self.setUpPyfakefs(additional_skip_names=["pyfakefs.tests.import_as_example"])

    def test_path_exists(self):
        self.assertTrue(pyfakefs.tests.import_as_example.exists_this_file())

    def test_fake_path_does_not_exist1(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists1("foo"))

    def test_fake_path_does_not_exist2(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists2("foo"))

    def test_fake_path_does_not_exist3(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists3("foo"))

    def test_fake_path_does_not_exist4(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists4("foo"))

    def test_fake_path_does_not_exist5(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists5("foo"))

    def test_fake_path_does_not_exist6(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists6("foo"))

    def test_fake_path_does_not_exist7(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists7("foo"))

    def test_open_succeeds(self):
        pyfakefs.tests.import_as_example.open_this_file()

    def test_path_succeeds(self):
        pyfakefs.tests.import_as_example.return_this_file_path()


class AdditionalSkipNamesModuleTest(fake_filesystem_unittest.TestCase):
    """Make sure that modules in additional_skip_names are not patched.
    Passes module to `additional_skip_names`."""

    def setUp(self):
        self.setUpPyfakefs(additional_skip_names=[pyfakefs.tests.import_as_example])

    def test_path_exists(self):
        self.assertTrue(pyfakefs.tests.import_as_example.exists_this_file())

    def test_fake_path_does_not_exist1(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists1("foo"))

    def test_fake_path_does_not_exist2(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists2("foo"))

    def test_fake_path_does_not_exist3(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists3("foo"))

    def test_fake_path_does_not_exist4(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists4("foo"))

    def test_fake_path_does_not_exist5(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists5("foo"))

    def test_fake_path_does_not_exist6(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists6("foo"))

    def test_fake_path_does_not_exist7(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists7("foo"))

    def test_open_succeeds(self):
        pyfakefs.tests.import_as_example.open_this_file()

    def test_path_succeeds(self):
        pyfakefs.tests.import_as_example.return_this_file_path()


class RuntimeSkipModuleTest(fake_filesystem_unittest.TestCase):
    """Emulates skipping a module using RUNTIME_SKIPMODULES.
    Not all functionality implemented for skip modules will work here."""

    def setUp(self):
        Patcher.RUNTIME_SKIPMODULES.update(
            {"pyfakefs.tests.import_as_example": ["pyfakefs.tests.import_"]}
        )
        self.setUpPyfakefs()

    def tearDown(self):
        del self.patcher.RUNTIME_SKIPMODULES["pyfakefs.tests.import_as_example"]

    def test_fake_path_does_not_exist1(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists1("foo"))

    def test_fake_path_does_not_exist2(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists2("foo"))

    def test_fake_path_does_not_exist3(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists3("foo"))

    def test_fake_path_does_not_exist4(self):
        self.fs.create_file("foo")
        self.assertFalse(pyfakefs.tests.import_as_example.check_if_exists4("foo"))


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
            modules_to_patch={"pyfakefs.tests.import_as_example": FakeExampleModule}
        )

    def test_system_stat(self):
        file_path = "/foo/bar"
        self.fs.create_file(file_path, contents=b"test")
        self.assertEqual(
            4, pyfakefs.tests.import_as_example.system_stat(file_path).st_size
        )


class PatchModuleTestUsingDecorator(unittest.TestCase):
    """Make sure that reloading a module allows patching of classes not
    patched automatically - use patchfs decorator with parameter.
    """

    @patchfs
    @unittest.expectedFailure
    def test_system_stat_failing(self, fake_fs):
        file_path = "/foo/bar"
        fake_fs.create_file(file_path, contents=b"test")
        self.assertEqual(
            4, pyfakefs.tests.import_as_example.system_stat(file_path).st_size
        )

    @patchfs(modules_to_patch={"pyfakefs.tests.import_as_example": FakeExampleModule})
    def test_system_stat(self, fake_fs):
        file_path = "/foo/bar"
        fake_fs.create_file(file_path, contents=b"test")
        self.assertEqual(
            4, pyfakefs.tests.import_as_example.system_stat(file_path).st_size
        )


class NoRootUserTest(fake_filesystem_unittest.TestCase):
    """Test allow_root_user argument to setUpPyfakefs."""

    def setUp(self):
        self.setUpPyfakefs(allow_root_user=False)

    def test_non_root_behavior(self):
        """Check that fs behaves as non-root user regardless of actual
        user rights.
        """
        self.fs.is_windows_fs = False
        dir_path = "/foo/bar"
        self.fs.create_dir(dir_path, perm_bits=0o555)
        file_path = dir_path + "baz"
        with self.assertRaises(OSError):
            self.fs.create_file(file_path)

        file_path = "/baz"
        self.fs.create_file(file_path)
        os.chmod(file_path, 0o400)
        with self.assertRaises(OSError):
            open(file_path, "w", encoding="utf8")


class PauseResumeTest(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()

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
        self.pause()
        real_temp_file.close()
        self.resume()

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
        self.fs.pause()
        real_temp_file.close()
        self.fs.resume()

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
            real_temp_file.close()
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
            real_temp_file.close()
        self.assertFalse(os.path.exists(real_temp_file.name))
        self.assertTrue(os.path.exists(fake_temp_file.name))

    def test_pause_resume_without_patcher(self):
        fs = fake_filesystem.FakeFilesystem()
        with self.assertRaises(RuntimeError):
            fs.resume()

    def test_that_tempfile_is_patched_after_resume(fs):
        """Regression test for #1098"""
        fs.pause()
        fs.resume()
        with tempfile.NamedTemporaryFile():
            pass


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
            fake_temp_file.close()
            p.pause()
            real_temp_file.close()
            p.resume()

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
                real_temp_file.close()
            self.assertFalse(os.path.exists(real_temp_file.name))
            self.assertTrue(os.path.exists(fake_temp_file.name))
            fake_temp_file.close()


class TestPyfakefsTestCase(unittest.TestCase):
    def setUp(self):
        class TestTestCase(fake_filesystem_unittest.TestCase):
            def runTest(self):
                pass

        self.test_case = TestTestCase("runTest")

    def test_test_case_type(self):
        self.assertIsInstance(self.test_case, unittest.TestCase)

        self.assertIsInstance(self.test_case, fake_filesystem_unittest.TestCaseMixin)


class TestTempDirCreation(fake_filesystem_unittest.TestCase):
    """Test that the temp directory exists at test start."""

    def setUp(self):
        self.setUpPyfakefs()

    def test_tempdir_exists(self):
        self.assertTrue(os.path.exists(tempfile.gettempdir()))

    @unittest.skipIf(sys.platform == "win32", "POSIX only test")
    def test_tmp_exists(self):
        # directory or link under Linux, link under macOS
        self.assertTrue(os.path.exists("/tmp"))


class TestTempFileReload(unittest.TestCase):
    """Regression test for #356 to make sure that reloading the tempfile
    does not affect other tests."""

    def test_fakefs(self):
        with Patcher() as patcher:
            patcher.fs.create_file("/mytempfile", contents="abcd")

    def test_value(self):
        v = multiprocessing.Value("I", 0)
        self.assertEqual(v.value, 0)


class TestPyfakefsTestCaseMixin(
    unittest.TestCase, fake_filesystem_unittest.TestCaseMixin
):
    def test_set_up_pyfakefs(self):
        self.setUpPyfakefs()

        self.assertTrue(hasattr(self, "fs"))
        self.assertIsInstance(self.fs, fake_filesystem.FakeFilesystem)


class TestShutilWithZipfile(fake_filesystem_unittest.TestCase):
    """Regression test for #427."""

    def setUp(self):
        self.setUpPyfakefs()
        self.fs.create_file("foo/bar")

    def test_a(self):
        shutil.make_archive("archive", "zip", root_dir="foo")

    def test_b(self):
        # used to fail because 'bar' could not be found
        shutil.make_archive("archive", "zip", root_dir="foo")


if sys.version_info < (3, 12):

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

            self.assertTrue(os.path.isfile("./test/subdir/1.txt"))
            self.assertFalse(os.path.isdir("./test2/"))

        def test_file_copied_again(self):
            # used to fail because 'test2' could not be found
            self.assertTrue(os.path.isfile("./test2/subdir/1.txt"))

            copy_tree("./test2/", "./test/")
            remove_tree("./test2/")

            self.assertTrue(os.path.isfile("./test/subdir/1.txt"))
            self.assertFalse(os.path.isdir("./test2/"))


class PathlibTest(TestCase):
    """Regression test for #527"""

    @patchfs
    def test_cwd(self, fs):
        """Make sure fake file system is used for os in pathlib"""
        is_windows = sys.platform.startswith("win")
        root_dir = "C:" + os.path.sep if is_windows else os.path.sep
        self.assertEqual(root_dir, str(pathlib.Path.cwd()))
        dot_abs = pathlib.Path(".").absolute()
        self.assertEqual(root_dir, str(dot_abs))
        self.assertTrue(dot_abs.exists())


class TestDeprecationSuppression(fake_filesystem_unittest.TestCase):
    def test_no_deprecation_warning(self):
        """Ensures that deprecation warnings are suppressed during module
        lookup, see #542.
        """

        from pyfakefs.tests.fixtures.deprecated_property import (  # noqa: F401
            DeprecationTest,
        )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("error", DeprecationWarning)
            self.setUpPyfakefs()
            self.assertEqual(0, len(w))


def load_configs(configs):
    """Helper code for patching open_code in auto mode, see issue #554."""
    retval = []
    for config in configs:
        if len(config) > 3 and config[-3:] == ".py":
            retval += runpy.run_path(config)
        else:
            retval += runpy.run_module(config)
    return retval


@unittest.skipIf(sys.version_info < (3, 8), "open_code new in Python 3.8")
class AutoPatchOpenCodeTestCase(fake_filesystem_unittest.TestCase):
    """Test patching open_code in auto mode, see issue #554."""

    def setUp(self):
        self.setUpPyfakefs(patch_open_code=PatchMode.AUTO)

        self.configpy = "configpy.py"
        self.fs.create_file(self.configpy, contents="configurable_value='yup'")
        self.config_module = "pyfakefs.tests.fixtures.config_module"

    def test_both(self):
        load_configs([self.configpy, self.config_module])

    def test_run_path(self):
        load_configs([self.configpy])

    def test_run_module(self):
        load_configs([self.config_module])

    def import_foo(self):
        spec = importlib.util.spec_from_file_location("bar", "/foo/bar.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

    def test_exec_module_in_fake_fs(self):
        self.fs.create_file("/foo/bar.py", contents="print('hello')")
        with redirect_stdout(StringIO()) as stdout:
            self.import_foo()
        assert stdout.getvalue() == "hello\n"

    def test_dynamic_import(self):
        # regression test for #1121
        self.fs.create_file("/foo.py")
        self.fs.create_file("/bar.py", contents="import foo")
        sys.path.insert(0, "")
        import foo  # noqa


class TestOtherFS(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()

    @mock.patch.dict(os.environ, {"HOME": "/home/john"})
    def test_real_file_with_home(self):
        """Regression test for #558"""
        self.fs.is_windows_fs = os.name != "nt"
        if self.fs.is_windows_fs:
            self.fs.is_macos = False
        self.fs.add_real_file(__file__)
        with open(__file__, encoding="utf8") as f:
            self.assertTrue(f.read())
        home = Path.home()
        os.chdir(home)
        with open(__file__, encoding="utf8") as f:
            self.assertTrue(f.read())

    def test_windows(self):
        self.fs.os = OSType.WINDOWS
        path = r"C:\foo\bar"
        self.assertEqual(path, os.path.join("C:\\", "foo", "bar"))
        self.assertEqual(("C:", r"\foo\bar"), os.path.splitdrive(path))
        self.fs.create_file(path)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.path.exists(path.upper()))
        self.assertTrue(os.path.ismount(r"\\share\foo"))
        self.assertTrue(os.path.ismount(r"C:"))
        self.assertEqual("\\", os.sep)
        self.assertEqual("\\", os.path.sep)
        self.assertEqual("/", os.altsep)
        self.assertEqual(";", os.pathsep)
        self.assertEqual("\r\n", os.linesep)
        self.assertEqual("NUL", os.devnull)

    def test_linux(self):
        self.fs.os = OSType.LINUX
        path = "/foo/bar"
        self.assertEqual(path, os.path.join("/", "foo", "bar"))
        self.assertEqual(("", "C:/foo/bar"), os.path.splitdrive("C:/foo/bar"))
        self.fs.create_file(path)
        self.assertTrue(os.path.exists(path))
        self.assertFalse(os.path.exists(path.upper()))
        self.assertTrue(os.path.ismount("/"))
        self.assertFalse(os.path.ismount("//share/foo"))
        self.assertEqual("/", os.sep)
        self.assertEqual("/", os.path.sep)
        self.assertEqual(None, os.altsep)
        self.assertEqual(":", os.pathsep)
        self.assertEqual("\n", os.linesep)
        self.assertEqual("/dev/null", os.devnull)

    def test_macos(self):
        self.fs.os = OSType.MACOS
        path = "/foo/bar"
        self.assertEqual(path, os.path.join("/", "foo", "bar"))
        self.assertEqual(("", "C:/foo/bar"), os.path.splitdrive("C:/foo/bar"))
        self.fs.create_file(path)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.path.exists(path.upper()))
        self.assertTrue(os.path.ismount("/"))
        self.assertFalse(os.path.ismount("//share/foo"))
        self.assertEqual("/", os.sep)
        self.assertEqual("/", os.path.sep)
        self.assertEqual(None, os.altsep)
        self.assertEqual(":", os.pathsep)
        self.assertEqual("\n", os.linesep)
        self.assertEqual("/dev/null", os.devnull)

    def test_drivelike_path(self):
        self.fs.os = OSType.LINUX
        folder = Path("/test")
        file_path = folder / "C:/testfile"
        file_path.parent.mkdir(parents=True)
        file_path.touch()
        os.chdir(folder)
        self.assertTrue(os.path.exists(str(file_path.relative_to(folder))))

    @unittest.skipIf(sys.platform != "win32", "Windows-specific test")
    def test_tempfile_access(self):
        # regression test for #912
        self.fs.os = OSType.LINUX
        tmp_file = tempfile.TemporaryFile()
        assert tmp_file


@unittest.skipIf(sys.platform != "win32", "Windows-specific behavior")
class TestAbsolutePathOnWindows(fake_filesystem_unittest.TestCase):
    @patchfs
    def test_is_absolute(self, fs):
        # regression test for #673
        self.assertTrue(pathlib.Path(".").absolute().is_absolute())


@unittest.skipIf(sys.version_info < (3, 8), "Not available before Python 3.8")
class TestClassSetup(fake_filesystem_unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.setUpClassPyfakefs()
        cls.fake_fs().create_file("foo/bar", contents="test")

    def test_using_fs_functions(self):
        self.assertTrue(os.path.exists("foo/bar"))
        with open("foo/bar", encoding="utf8") as f:
            contents = f.read()
        self.assertEqual("test", contents)

    def test_using_fakefs(self):
        self.assertTrue(self.fs.exists("foo/bar"))
        f = self.fs.get_object("foo/bar")
        self.assertEqual("test", f.contents)


class TestTempPathCreation(fake_filesystem_unittest.TestCase):
    """Regression test for #965. Checks that the temp file system
    is properly created with a root-owned root path.
    """

    def setUp(self):
        self.setUpPyfakefs()

    def check_write_tmp_after_reset(self, os_type):
        self.fs.os = os_type
        # Mark '/' to be modifiable by only root
        os.chown("/", 0, 0)
        os.chmod("/", 0b111_101_101)
        with tempfile.TemporaryFile("wb") as f:
            assert f.write(b"foo") == 3

    def test_write_tmp_linux(self):
        self.check_write_tmp_after_reset(OSType.LINUX)

    def test_write_tmp_macos(self):
        self.check_write_tmp_after_reset(OSType.MACOS)

    def test_write_tmp_windows(self):
        self.check_write_tmp_after_reset(OSType.WINDOWS)


@unittest.skipIf(sys.version_info < (3, 8), "Not available before Python 3.8")
class FakeImportTest(fake_filesystem_unittest.TestCase):
    """Checks that a fake module can be imported in AUTO patch mode."""

    def setUp(self):
        self.setUpPyfakefs(patch_open_code=PatchMode.AUTO)

    def test_simple_fake_import(self):
        fake_module_path = Path("/") / "site-packages" / "fake_module.py"
        self.fs.create_file(fake_module_path, contents="number = 42")
        sys.path.insert(0, str(fake_module_path.parent))
        module = importlib.import_module("fake_module")
        del sys.path[0]
        assert module.__name__ == "fake_module"
        assert module.number == 42

    def test_fake_import_dotted_module(self):
        fake_pkg_path = Path("/") / "site-packages"
        self.fs.create_file(fake_pkg_path / "fakepkg" / "__init__.py")
        fake_module_path = fake_pkg_path / "fakepkg" / "fake_module.py"
        self.fs.create_file(fake_module_path, contents="number = 42")
        sys.path.insert(0, str(fake_pkg_path))
        module = importlib.import_module("fakepkg.fake_module")
        del sys.path[0]
        assert module.__name__ == "fakepkg.fake_module"
        assert module.number == 42

    def test_fake_relative_import(self):
        fake_module_path = Path("site-packages") / "fake_module.py"
        self.fs.create_file(fake_module_path, contents="number = 42")
        sys.path.insert(0, str(fake_module_path.parent))
        module = importlib.import_module("fake_module")
        del sys.path[0]
        assert module.__name__ == "fake_module"
        assert module.number == 42


if __name__ == "__main__":
    unittest.main()
