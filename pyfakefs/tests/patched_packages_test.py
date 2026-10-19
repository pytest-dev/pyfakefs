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
from pathlib import Path

from pyfakefs import fake_filesystem_unittest

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

try:
    from typer.testing import CliRunner

    from pyfakefs.tests.fixtures import typer_deferred_example, typer_eager_example
except ImportError:
    CliRunner = None


class TestPatchedPackages(fake_filesystem_unittest.TestCase):
    def setUp(self):
        self.setUpPyfakefs()

    if pd is not None:

        def test_read_csv(self):
            path = "/foo/bar.csv"
            self.fs.create_file(path, contents="1,2,3,4")
            df = pd.read_csv(path)
            assert (df.columns == ["1", "2", "3", "4"]).all()

        def test_read_table(self):
            path = "/foo/bar.csv"
            self.fs.create_file(path, contents="1|2|3|4")
            df = pd.read_table(path, delimiter="|")
            assert (df.columns == ["1", "2", "3", "4"]).all()

    if pd is not None and xlrd is not None:

        def test_read_excel(self):
            path = "/foo/bar.xlsx"
            src_path = os.path.dirname(os.path.abspath(__file__))
            src_path = os.path.join(src_path, "fixtures", "excel_test.xlsx")
            # map the file into another location to be sure that
            # the real fs is not used
            self.fs.add_real_file(src_path, target_path=path)
            df = pd.read_excel(path)
            assert (df.columns == [1, 2, 3, 4]).all()

    if pd is not None and openpyxl is not None:

        def test_write_excel(self):
            self.fs.create_dir("/foo")
            path = "/foo/bar.xlsx"
            df = pd.DataFrame([[0, 1, 2, 3]])
            with pd.ExcelWriter(path) as writer:
                df.to_excel(writer)
            df = pd.read_excel(path)
            assert (df.columns == ["Unnamed: 0", 0, 1, 2, 3]).all()


@unittest.skipIf(CliRunner is None, "Typer is not installed")
class TestTyperPathAnnotations(unittest.TestCase):
    def check_copy_commands(self, fs, module):
        fs.create_file("/input.txt", contents="synthetic input")
        runner = CliRunner()
        for app_name in ("direct_app", "module_app"):
            with self.subTest(app=app_name):
                app = getattr(module, app_name)
                target = f"/{app_name}.txt"
                result = runner.invoke(app, ["/input.txt", target])
                self.assertEqual(result.exit_code, 0, result.exception)
                self.assertEqual(result.stdout, "synthetic input\n")
                self.assertEqual(
                    Path(target).read_text(encoding="utf8"), "synthetic input"
                )

                result = runner.invoke(app, ["/missing.txt", target])
                self.assertEqual(result.exit_code, 2, result.exception)
                self.assertIn("does not exist", result.output)

    def test_postponed_annotations(self):
        with fake_filesystem_unittest.Patcher() as patcher:
            self.check_copy_commands(patcher.fs, typer_deferred_example)

    def test_eager_annotations_in_reloaded_module(self):
        original_path = Path
        # Materialize the annotations before patching on Python 3.14 as well.
        self.assertIs(
            typer_eager_example.copy_direct.__annotations__["target"], original_path
        )
        with fake_filesystem_unittest.Patcher(
            modules_to_reload=[typer_eager_example]
        ) as patcher:
            self.check_copy_commands(patcher.fs, typer_eager_example)
        # Reloading on teardown must restore the real class in annotations.
        self.assertIs(
            typer_eager_example.copy_direct.__annotations__["target"], original_path
        )
