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
Tests for patching modules loaded after `setUpPyfakefs()`.
"""
import pathlib
import unittest

from pyfakefs import fake_filesystem_unittest


class TestPyfakefsUnittestBase(fake_filesystem_unittest.TestCase):
    def setUp(self):
        """Set up the fake file system"""
        self.setUpPyfakefs()


class DynamicImportPatchTest(TestPyfakefsUnittestBase):
    def __init__(self, methodName='runTest'):
        super(DynamicImportPatchTest, self).__init__(methodName)

    def test_os_patch(self):
        import os

        os.mkdir('test')
        self.assertTrue(self.fs.exists('test'))
        self.assertTrue(os.path.exists('test'))

    def test_os_import_as_patch(self):
        import os as _os

        _os.mkdir('test')
        self.assertTrue(self.fs.exists('test'))
        self.assertTrue(_os.path.exists('test'))

    def test_os_path_patch(self):
        import os.path

        os.mkdir('test')
        self.assertTrue(self.fs.exists('test'))
        self.assertTrue(os.path.exists('test'))

    def test_shutil_patch(self):
        import shutil

        self.fs.set_disk_usage(100)
        self.assertEqual(100, shutil.disk_usage('/').total)

    def test_pathlib_path_patch(self):
        file_path = 'test.txt'
        path = pathlib.Path(file_path)
        with path.open('w') as f:
            f.write('test')

        self.assertTrue(self.fs.exists(file_path))
        file_object = self.fs.get_object(file_path)
        self.assertEqual('test', file_object.contents)


if __name__ == "__main__":
    unittest.main()
