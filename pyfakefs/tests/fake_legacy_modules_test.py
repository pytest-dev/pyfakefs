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

import unittest

from pyfakefs.fake_filesystem_unittest import TestCase
from pyfakefs.fake_legacy_modules import FakeScanDirModule, FakePathlib2Module
from pyfakefs.legacy_packages import pathlib2, scandir
from pyfakefs.tests.fake_os_test import FakeScandirTest
from pyfakefs.tests.fake_pathlib_test import (
    FakePathlibInitializationTest,
    FakePathlibPathFileOperationTest,
    FakePathlibFileObjectPropertyTest,
    FakePathlibUsageInOsFunctionsTest,
)


class DeprecationWarningTest(TestCase):
    def setUp(self):
        self.setUpPyfakefs()

    @unittest.skipIf(scandir is None, "The scandir package is not installed")
    def test_scandir_warning(self):
        FakeScanDirModule.has_warned = False
        with self.assertWarns(DeprecationWarning):
            scandir.scandir("/")

    @unittest.skipIf(pathlib2 is None, "The pathlib2 package is not installed")
    def test_pathlib2_warning(self):
        FakePathlib2Module.has_warned = False
        with self.assertWarns(DeprecationWarning):
            pathlib2.Path("/foo")


@unittest.skipIf(scandir is None, "The scandir package is not installed")
class FakeScandirPackageTest(FakeScandirTest):
    def used_scandir(self):
        import pyfakefs.fake_legacy_modules

        def fake_scan_dir(p):
            return pyfakefs.fake_legacy_modules.FakeScanDirModule(
                self.filesystem
            ).scandir(p)

        return fake_scan_dir

    def test_path_like(self):
        unittest.skip("Path-like objects not available in scandir package")


class RealScandirPackageTest(FakeScandirPackageTest):
    def used_scandir(self):
        from scandir import scandir

        return scandir

    def use_real_fs(self):
        return True


@unittest.skipIf(pathlib2 is None, "The pathlib2 package is not installed")
class FakePathlib2InitializationTest(FakePathlibInitializationTest):
    def used_pathlib(self):
        return pathlib2


class RealPathlib2InitializationTest(FakePathlib2InitializationTest):
    def use_real_fs(self):
        return True


@unittest.skipIf(pathlib2 is None, "The pathlib2 package is not installed")
class FakePathlib2FileObjectPropertyTest(FakePathlibFileObjectPropertyTest):
    def used_pathlib(self):
        return pathlib2


class RealPathlib2FileObjectPropertyTest(FakePathlib2FileObjectPropertyTest):
    def use_real_fs(self):
        return True


@unittest.skipIf(pathlib2 is None, "The pathlib2 package is not installed")
class FakePathlib2PathFileOperationTest(FakePathlibPathFileOperationTest):
    def used_pathlib(self):
        return pathlib2

    def test_is_junction(self):
        unittest.skip("is_junction not available in pathlib2")


class RealPathlibPath2FileOperationTest(FakePathlib2PathFileOperationTest):
    def use_real_fs(self):
        return True


@unittest.skipIf(pathlib2 is None, "The pathlib2 package is not installed")
class FakePathlib2UsageInOsFunctionsTest(FakePathlibUsageInOsFunctionsTest):
    def used_pathlib(self):
        return pathlib2


class RealPathlib2UsageInOsFunctionsTest(FakePathlib2UsageInOsFunctionsTest):
    def use_real_fs(self):
        return True


if __name__ == "__main__":
    unittest.main(verbosity=2)
