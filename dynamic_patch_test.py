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
Tests for patching modules loaded after `setupPyfakefs()`.
"""
import sys
import unittest

from pyfakefs import fake_filesystem_unittest


class TestPyfakefsUnittestBase(fake_filesystem_unittest.TestCase):
    def setUp(self):
        """Set up the fake file system"""
        self.setUpPyfakefs()


@unittest.skipIf((3, ) < sys.version_info < (3, 3),
                 'Does not work with Python 3 < 3.3, including Pypy3 2.4')
class DynamicImportPatchTest(TestPyfakefsUnittestBase):
    def __init__(self, methodName='runTest'):
        super(DynamicImportPatchTest, self).__init__(methodName,
            use_dynamic_patch=True)

    def testOsPatch(self):
        import os

        os.mkdir('test')
        self.assertTrue(self.fs.exists('test'))
        self.assertTrue(os.path.exists('test'))

    def testOsImportAsPatch(self):
        import os as _os

        _os.mkdir('test')
        self.assertTrue(self.fs.exists('test'))
        self.assertTrue(_os.path.exists('test'))

    def testOsPathPatch(self):
        import os.path

        os.mkdir('test')
        self.assertTrue(self.fs.exists('test'))
        self.assertTrue(os.path.exists('test'))

    @unittest.skipIf(sys.version_info < (3, 3), 'disk_usage new in Python 3.3')
    def testShutilPatch(self):
        import shutil

        self.fs.set_disk_usage(100)
        self.assertEqual(100, shutil.disk_usage('/').total)

    @unittest.skipIf(sys.version_info < (3, 4), 'pathlib new in Python 3.4')
    def testPathlibPatch(self):
        import pathlib

        file_path = 'test.txt'
        path = pathlib.Path(file_path)
        with path.open('w') as f:
            f.write('test')

        self.assertTrue(self.fs.exists(file_path))
        file_object = self.fs.get_object(file_path)
        self.assertEqual('test', file_object.contents)


if __name__ == "__main__":
    unittest.main()
