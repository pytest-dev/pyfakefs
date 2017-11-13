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

"""Tests that ensure that the `tempfile` module works with `fake_filesystem`
if using `Patcher` (via `fake_filesystem_unittest`).
"""

import os
import stat
import sys
import tempfile
import unittest

from pyfakefs import fake_filesystem_unittest


class FakeTempfileModuleTest(fake_filesystem_unittest.TestCase):
    """Test the 'tempfile' module with the fake file system."""

    def setUp(self):
        self.setUpPyfakefs()

    def testNamedTemporaryFile(self):
        obj = tempfile.NamedTemporaryFile()
        self.assertTrue(self.fs.GetObject(obj.name))
        obj.close()
        self.assertRaises(IOError, self.fs.GetObject, obj.name)

    def testNamedTemporaryFileNoDelete(self):
        obj = tempfile.NamedTemporaryFile(delete=False)
        obj.write(b'foo')
        obj.close()
        file_obj = self.fs.GetObject(obj.name)
        contents = file_obj.contents
        self.assertEqual('foo', contents)
        obj = tempfile.NamedTemporaryFile(mode='w', delete=False)
        obj.write('foo')
        obj.close()
        file_obj = self.fs.GetObject(obj.name)
        self.assertEqual('foo', file_obj.contents)

    def testMkstemp(self):
        next_fd = len(self.fs.open_files)
        temporary = tempfile.mkstemp()
        self.assertEqual(2, len(temporary))
        self.assertTrue(temporary[1].startswith(os.path.join(tempfile.gettempdir(), 'tmp')))
        self.assertEqual(next_fd, temporary[0])
        self.assertTrue(self.fs.Exists(temporary[1]))
        mode = 0o666 if self.fs.is_windows_fs else 0o600
        self.assertEqual(self.fs.GetObject(temporary[1]).st_mode,
                         stat.S_IFREG | mode)
        fh = os.fdopen(temporary[0], 'w+b')
        self.assertEqual(temporary[0], fh.fileno())

    def testMkstempDir(self):
        """test tempfile.mkstemp(dir=)."""
        # expect fail: /dir does not exist
        self.assertRaises(OSError, tempfile.mkstemp, dir='/dir')
        # expect pass: /dir exists
        self.fs.CreateDirectory('/dir')
        next_fd = len(self.fs.open_files)
        temporary = tempfile.mkstemp(dir='/dir')
        self.assertEqual(2, len(temporary))
        self.assertEqual(next_fd, temporary[0])
        self.assertTrue(temporary[1].startswith(os.path.join(os.sep, 'dir', 'tmp')))
        self.assertTrue(self.fs.Exists(temporary[1]))
        mode = 0o666 if self.fs.is_windows_fs else 0o600
        self.assertEqual(self.fs.GetObject(temporary[1]).st_mode,
                         stat.S_IFREG | mode)

    def testMkdtemp(self):
        dirname = tempfile.mkdtemp()
        self.assertTrue(dirname)
        self.assertTrue(self.fs.Exists(dirname))
        self.assertEqual(self.fs.GetObject(dirname).st_mode,
                         stat.S_IFDIR | 0o700)

    @unittest.skipIf(sys.version_info < (3, 0), "TemporaryDirectory showed up in 3")
    def testTemporaryDirectory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertTrue(tmpdir)
            self.assertTrue(self.fs.Exists(tmpdir))
            self.assertEqual(self.fs.GetObject(tmpdir).st_mode,
                             stat.S_IFDIR | 0o700)


if __name__ == '__main__':
    unittest.main()
