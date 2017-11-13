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

"""Test for glob using fake_filesystem."""

import glob
import os
import unittest

from pyfakefs import fake_filesystem_unittest


class FakeGlobUnitTest(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        directory = './xyzzy'
        self.fs.CreateDirectory(directory)
        self.fs.CreateDirectory('%s/subdir' % directory)
        self.fs.CreateDirectory('%s/subdir2' % directory)
        self.fs.CreateFile('%s/subfile' % directory)
        self.fs.CreateFile('[Temp]')

    def testGlobEmpty(self):
        self.assertEqual(glob.glob(''), [])

    def testGlobStar(self):
        basedir = os.sep + 'xyzzy'
        self.assertEqual([os.path.join(basedir, 'subdir'),
                          os.path.join(basedir, 'subdir2'),
                          os.path.join(basedir, 'subfile')],
                         sorted(glob.glob('/xyzzy/*')))

    def testGlobExact(self):
        self.assertEqual(['/xyzzy'], glob.glob('/xyzzy'))
        self.assertEqual(['/xyzzy/subfile'], glob.glob('/xyzzy/subfile'))

    def testGlobQuestion(self):
        basedir = os.sep + 'xyzzy'
        self.assertEqual([os.path.join(basedir, 'subdir'),
                          os.path.join(basedir, 'subdir2'),
                          os.path.join(basedir, 'subfile')],
                         sorted(glob.glob('/x?zz?/*')))

    def testGlobNoMagic(self):
        self.assertEqual(['/xyzzy'], glob.glob('/xyzzy'))
        self.assertEqual(['/xyzzy/subdir'], glob.glob('/xyzzy/subdir'))

    def testNonExistentPath(self):
        self.assertEqual([], glob.glob('nonexistent'))

    def testMagicDir(self):
        self.assertEqual([os.sep + '[Temp]'], glob.glob('/*emp*'))

    def testGlob1(self):
        self.assertEqual(['[Temp]'], glob.glob1('/', '*Tem*'))

    def testHasMagic(self):
        self.assertTrue(glob.has_magic('['))
        self.assertFalse(glob.has_magic('a'))


if __name__ == '__main__':
    unittest.main()
