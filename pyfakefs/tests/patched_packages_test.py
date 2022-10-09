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
Provides patches for some commonly used modules that enable them to work
with pyfakefs.
"""
import os
import unittest

from pyfakefs import fake_filesystem_unittest
from pyfakefs.helpers import IS_PYPY

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import xlrd
except ImportError:
    xlrd = None

try:
    import openpyxl
except ImportError:
    openpyxl = None


@unittest.skipIf(IS_PYPY, "Has a problem with current PyPy")
class TestPatchedPackages(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()

    if pd is not None:
        def test_read_csv(self):
            path = '/foo/bar.csv'
            self.fs.create_file(path, contents='1,2,3,4')
            df = pd.read_csv(path)
            assert (df.columns == ['1', '2', '3', '4']).all()

        def test_read_table(self):
            path = '/foo/bar.csv'
            self.fs.create_file(path, contents='1|2|3|4')
            df = pd.read_table(path, delimiter='|')
            assert (df.columns == ['1', '2', '3', '4']).all()

    if pd is not None and xlrd is not None:
        def test_read_excel(self):
            path = '/foo/bar.xlsx'
            src_path = os.path.dirname(os.path.abspath(__file__))
            src_path = os.path.join(src_path, 'fixtures', 'excel_test.xlsx')
            # map the file into another location to be sure that
            # the real fs is not used
            self.fs.add_real_file(src_path, target_path=path)
            df = pd.read_excel(path)
            assert (df.columns == [1, 2, 3, 4]).all()

    if pd is not None and openpyxl is not None:
        def test_write_excel(self):
            self.fs.create_dir('/foo')
            path = '/foo/bar.xlsx'
            df = pd.DataFrame([[0, 1, 2, 3]])
            with pd.ExcelWriter(path) as writer:
                df.to_excel(writer)
            df = pd.read_excel(path)
            assert (df.columns == ['Unnamed: 0', 0, 1, 2, 3]).all()
