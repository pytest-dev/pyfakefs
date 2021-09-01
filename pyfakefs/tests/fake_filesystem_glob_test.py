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

"""Test for glob using fake_filesystem."""

import glob
import os
import unittest

from pyfakefs import fake_filesystem_unittest


class FakeGlobUnitTest(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        directory = './xyzzy'
        self.fs.create_dir(directory)
        self.fs.create_dir('%s/subdir' % directory)
        self.fs.create_dir('%s/subdir2' % directory)
        self.fs.create_file('%s/subfile' % directory)
        self.fs.create_file('[Temp]')

    def test_glob_empty(self):
        self.assertEqual(glob.glob(''), [])

    def test_glob_star(self):
        basedir = '/xyzzy'
        self.assertEqual([os.path.join(basedir, 'subdir'),
                          os.path.join(basedir, 'subdir2'),
                          os.path.join(basedir, 'subfile')],
                         sorted(glob.glob('/xyzzy/*')))

    def test_glob_exact(self):
        self.assertEqual(['/xyzzy'], glob.glob('/xyzzy'))
        self.assertEqual(['/xyzzy/subfile'], glob.glob('/xyzzy/subfile'))

    def test_glob_question(self):
        basedir = '/xyzzy'
        self.assertEqual([os.path.join(basedir, 'subdir'),
                          os.path.join(basedir, 'subdir2'),
                          os.path.join(basedir, 'subfile')],
                         sorted(glob.glob('/x?zz?/*')))

    def test_glob_no_magic(self):
        self.assertEqual(['/xyzzy'], glob.glob('/xyzzy'))
        self.assertEqual(['/xyzzy/subdir'], glob.glob('/xyzzy/subdir'))

    def test_non_existent_path(self):
        self.assertEqual([], glob.glob('nonexistent'))

    def test_magic_dir(self):
        self.assertEqual(['/[Temp]'], glob.glob('/*emp*'))

    def test_glob1(self):
        self.assertEqual(['[Temp]'], glob.glob1('/', '*Tem*'))

    def test_has_magic(self):
        self.assertTrue(glob.has_magic('['))
        self.assertFalse(glob.has_magic('a'))


if __name__ == '__main__':
    unittest.main()
