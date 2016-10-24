#! /usr/bin/env python
#
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
Test the :py:class`pyfakefs.fake_filesystem_unittest.TestCase` base class.
"""
import io
import os
import glob
import shutil
import tempfile
import sys

if sys.version_info >= (3, 4):
    import pathlib

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest
from pyfakefs import fake_filesystem_unittest


class TestPyfakefsUnittestBase(fake_filesystem_unittest.TestCase):
    def setUp(self):
        """Set up the fake file system"""
        self.setUpPyfakefs()

    def tearDown(self):
        """Tear down the fake file system"""
        self.tearDownPyfakefs()


class TestPyfakefsUnittest(TestPyfakefsUnittestBase):  # pylint: disable=R0904
    """Test the `pyfakefs.fake_filesystem_unittest.TestCase` base class."""

    @unittest.skipIf(sys.version_info > (2,), "file() was removed in Python 3")
    def test_file(self):
        """Fake `file()` function is bound"""
        self.assertFalse(os.path.exists('/fake_file.txt'))
        with file('/fake_file.txt', 'w') as f:
            f.write("This test file was created using the file() function.\n")
        self.assertTrue(self.fs.Exists('/fake_file.txt'))
        with file('/fake_file.txt') as f:
            content = f.read()
        self.assertEqual(content,
                         'This test file was created using the file() function.\n')

    def test_open(self):
        """Fake `open()` function is bound"""
        self.assertFalse(os.path.exists('/fake_file.txt'))
        with open('/fake_file.txt', 'w') as f:
            f.write("This test file was created using the open() function.\n")
        self.assertTrue(self.fs.Exists('/fake_file.txt'))
        with open('/fake_file.txt') as f:
            content = f.read()
        self.assertEqual(content,
                         'This test file was created using the open() function.\n')

    def test_io_open(self):
        """Fake io module is bound"""
        self.assertFalse(os.path.exists('/fake_file.txt'))
        with io.open('/fake_file.txt', 'w') as f:
            f.write("This test file was created using the io.open() function.\n")
        self.assertTrue(self.fs.Exists('/fake_file.txt'))
        with open('/fake_file.txt') as f:
            content = f.read()
        self.assertEqual(content,
                         'This test file was created using the io.open() function.\n')

    def test_os(self):
        """Fake os module is bound"""
        self.assertFalse(self.fs.Exists('/test/dir1/dir2'))
        os.makedirs('/test/dir1/dir2')
        self.assertTrue(self.fs.Exists('/test/dir1/dir2'))

    def test_glob(self):
        """Fake glob module is bound"""
        is_windows = sys.platform.startswith('win')
        self.assertEqual(glob.glob('/test/dir1/dir*'),
                         [])
        self.fs.CreateDirectory('/test/dir1/dir2a')
        matching_paths = glob.glob('/test/dir1/dir*')
        if is_windows:
            self.assertEqual(matching_paths, [r'\test\dir1\dir2a'])
        else:
            self.assertEqual(matching_paths, ['/test/dir1/dir2a'])
        self.fs.CreateDirectory('/test/dir1/dir2b')
        matching_paths = glob.glob('/test/dir1/dir*')
        if is_windows:
            self.assertEqual(matching_paths, [r'\test\dir1\dir2a', r'\test\dir1\dir2b'])
        else:
            self.assertEqual(matching_paths, ['/test/dir1/dir2a', '/test/dir1/dir2b'])

    def test_shutil(self):
        """Fake shutil module is bound"""
        self.fs.CreateDirectory('/test/dir1/dir2a')
        self.fs.CreateDirectory('/test/dir1/dir2b')
        self.assertTrue(self.fs.Exists('/test/dir1/dir2b'))
        self.assertTrue(self.fs.Exists('/test/dir1/dir2a'))

        shutil.rmtree('/test/dir1')
        self.assertFalse(self.fs.Exists('/test/dir1'))

    def test_tempfile(self):
        """Fake tempfile module is bound"""
        with tempfile.NamedTemporaryFile() as tf:
            tf.write(b'Temporary file contents\n')
            name = tf.name
            self.assertTrue(self.fs.Exists(tf.name))

    @unittest.skipIf(sys.version_info < (3, 0), "TemporaryDirectory new in Python3")
    def test_tempdirectory(self):
        """Fake TemporaryDirectory class is bound"""
        with tempfile.TemporaryDirectory() as td:
            with open('%s/fake_file.txt' % td, 'w') as f:
                self.assertTrue(self.fs.Exists(td))

    @unittest.skipIf(sys.version_info < (3, 4), "pathlib new in Python 3.4")
    def test_fakepathlib(self):
        with pathlib.Path('/fake_file.txt') as p:
            with p.open('w') as f:
                f.write('text')
        is_windows = sys.platform.startswith('win')
        if is_windows:
            self.assertTrue(self.fs.Exists(r'\fake_file.txt'))
        else:
            self.assertTrue(self.fs.Exists('/fake_file.txt'))

import math as path


class TestPatchPathUnittestFailing(TestPyfakefsUnittestBase):
    """Tests the default behavior regarding the argument patch_path:
       An own path module (in this case an alias to math) cannot be imported,
       because it is faked by FakePathModule
    """

    def __init__(self, methodName='runTest'):
        super(TestPatchPathUnittestFailing, self).__init__(methodName, patch_path=True)

    @unittest.expectedFailure
    def test_own_path_module(self):
        self.assertEqual(2, path.floor(2.5))


class TestPatchPathUnittestPassing(TestPyfakefsUnittestBase):
    """Tests the behavior with patch_path set to False:
       An own path module (in this case an alias to math) can be imported and used
    """

    def __init__(self, methodName='runTest'):
        super(TestPatchPathUnittestPassing, self).__init__(methodName, patch_path=False)

    def test_own_path_module(self):
        self.assertEqual(2, path.floor(2.5))


if __name__ == "__main__":
    unittest.main()
