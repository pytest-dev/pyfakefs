# Copyright 2014 Altera Corporation. All Rights Reserved.
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
Test the :py:class`pyfakefs.example` module to demonstrate the usage of the
:py:class`pyfakefs.fake_filesystem_unittest.TestCase` base class.

Fake filesystem functions like `create_file()`, `create_dir()` or
`create_symlink()` are often used to set up file structures at the beginning
of a test.
While you could also use the familiar `open()`, `os.mkdirs()` and similar
functions, these functions can make the test code shorter and more readable.
`create_file()` is particularly convenient because it creates all parent
directories and allows you to specify the contents or the size of the file.
"""

import io
import os
import sys
import unittest

from pyfakefs import fake_filesystem_unittest
from pyfakefs.extra_packages import use_scandir_package
from pyfakefs.tests import example  # The module under test


def load_tests(loader, tests, ignore):
    """Load the pyfakefs/example.py doctest tests into unittest."""
    return fake_filesystem_unittest.load_doctests(
        loader, tests, ignore, example)


class TestExample(fake_filesystem_unittest.TestCase):  # pylint: disable=R0904
    """Test the example module.
       The os and shutil modules have been replaced with the fake modules,
       so that all of the calls to os and shutil in the tested example code
       occur in the fake filesystem.
    """

    def setUp(self):
        """Invoke the :py:class:`pyfakefs.fake_filesystem_unittest.TestCase`
        `self.setUp()` method.  This defines:

        * Attribute `self.fs`, an instance of
          :py:class:`pyfakefs.fake_filesystem.FakeFilesystem`. This is useful
          for creating test files.
        * Attribute `self.stubs`, an instance of
          :py:class:`pyfakefs.mox3_stubout.StubOutForTesting`. Use this if
          you need to define additional stubs.
        """

        # This is before setUpPyfakefs(), so still using the real file system
        self.filepath = os.path.realpath(__file__)
        with io.open(self.filepath, 'rb') as f:
            self.real_contents = f.read()

        self.setUpPyfakefs()

    def tearDown(self):
        # No longer need self.tearDownPyfakefs()
        pass

    def test_create_file(self):
        """Test example.create_file() which uses `open()` and `file.write()`.
        """
        self.assertFalse(os.path.isdir('/test'))
        os.mkdir('/test')
        self.assertTrue(os.path.isdir('/test'))

        self.assertFalse(os.path.exists('/test/file.txt'))
        example.create_file('/test/file.txt')
        self.assertTrue(os.path.exists('/test/file.txt'))

    def test_delete_file(self):
        """Test example.delete_file() which uses `os.remove()`."""
        self.fs.create_file('/test/full.txt',
                            contents='First line\n'
                                     'Second Line\n')
        self.assertTrue(os.path.exists('/test/full.txt'))
        example.delete_file('/test/full.txt')
        self.assertFalse(os.path.exists('/test/full.txt'))

    def test_file_exists(self):
        """Test example.path_exists() which uses `os.path.exists()`."""
        self.assertFalse(example.path_exists('/test/empty.txt'))
        self.fs.create_file('/test/empty.txt')
        self.assertTrue(example.path_exists('/test/empty.txt'))

    def test_get_globs(self):
        """Test example.get_glob()."""
        self.assertFalse(os.path.isdir('/test'))
        self.fs.create_dir('/test/dir1/dir2a')
        self.assertTrue(os.path.isdir('/test/dir1/dir2a'))
        # os.mkdirs() works, too.
        os.makedirs('/test/dir1/dir2b')
        self.assertTrue(os.path.isdir('/test/dir1/dir2b'))

        self.assertEqual(example.get_glob('/test/dir1/nonexistent*'),
                         [])
        is_windows = sys.platform.startswith('win')
        matching_paths = sorted(example.get_glob('/test/dir1/dir*'))
        if is_windows:
            self.assertEqual(matching_paths,
                             [r'/test/dir1\dir2a', r'/test/dir1\dir2b'])
        else:
            self.assertEqual(matching_paths,
                             ['/test/dir1/dir2a', '/test/dir1/dir2b'])

    def test_rm_tree(self):
        """Test example.rm_tree() using `shutil.rmtree()`."""
        self.fs.create_dir('/test/dir1/dir2a')
        # os.mkdirs() works, too.
        os.makedirs('/test/dir1/dir2b')
        self.assertTrue(os.path.isdir('/test/dir1/dir2b'))
        self.assertTrue(os.path.isdir('/test/dir1/dir2a'))

        example.rm_tree('/test/dir1')
        self.assertFalse(os.path.exists('/test/dir1'))

    def test_os_scandir(self):
        """Test example.scandir() which uses `os.scandir()`.

        The os module has been replaced with the fake os module so the
        fake filesystem path entries are returned instead of `os.DirEntry`
        objects.
        """
        self.fs.create_file('/test/text.txt')
        self.fs.create_dir('/test/dir')
        self.fs.create_file('/linktest/linked')
        self.fs.create_symlink('/test/linked_file', '/linktest/linked')

        entries = sorted(example.scan_dir('/test'), key=lambda e: e.name)
        self.assertEqual(3, len(entries))
        self.assertEqual('linked_file', entries[1].name)
        self.assertTrue(entries[0].is_dir())
        self.assertTrue(entries[1].is_symlink())
        self.assertTrue(entries[2].is_file())

    @unittest.skipIf(not use_scandir_package,
                     'Testing only if scandir module is installed')
    def test_scandir_scandir(self):
        """Test example.scandir() which uses `scandir.scandir()`.

        The scandir module has been replaced with the fake_scandir module so
        the fake filesystem path entries are returned instead of
        `scandir.DirEntry` objects.
        """
        self.fs.create_file('/test/text.txt')
        self.fs.create_dir('/test/dir')

        entries = sorted(example.scan_dir('/test'), key=lambda e: e.name)
        self.assertEqual(2, len(entries))
        self.assertEqual('text.txt', entries[1].name)
        self.assertTrue(entries[0].is_dir())
        self.assertTrue(entries[1].is_file())

    def test_real_file_access(self):
        """Test `example.file_contents()` for a real file after adding it using
         `add_real_file()`."""
        with self.assertRaises(OSError):
            example.file_contents(self.filepath)
        self.fs.add_real_file(self.filepath)
        self.assertEqual(example.file_contents(self.filepath),
                         self.real_contents)


if __name__ == "__main__":
    unittest.main()
