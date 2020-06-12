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

"""A test suite that runs all tests for pyfakefs at once.
Includes tests with external pathlib2 and scandir packages if installed."""

import sys
import unittest

from pyfakefs.tests import (
    dynamic_patch_test,
    fake_stat_time_test,
    example_test,
    fake_filesystem_glob_test,
    fake_filesystem_shutil_test,
    fake_filesystem_test,
    fake_filesystem_unittest_test,
    fake_filesystem_vs_real_test,
    fake_open_test,
    fake_os_test,
    fake_pathlib_test,
    fake_tempfile_test,
    patched_packages_test,
    mox3_stubout_test
)


class AllTests(unittest.TestSuite):
    """A test suite that runs all tests for pyfakefs at once."""

    def suite(self):  # pylint: disable-msg=C6409
        loader = unittest.defaultTestLoader
        self.addTests([
            loader.loadTestsFromModule(fake_filesystem_test),
            loader.loadTestsFromModule(fake_filesystem_glob_test),
            loader.loadTestsFromModule(fake_filesystem_shutil_test),
            loader.loadTestsFromModule(fake_os_test),
            loader.loadTestsFromModule(fake_stat_time_test),
            loader.loadTestsFromModule(fake_open_test),
            loader.loadTestsFromModule(fake_tempfile_test),
            loader.loadTestsFromModule(fake_filesystem_vs_real_test),
            loader.loadTestsFromModule(fake_filesystem_unittest_test),
            loader.loadTestsFromModule(example_test),
            loader.loadTestsFromModule(mox3_stubout_test),
            loader.loadTestsFromModule(dynamic_patch_test),
            loader.loadTestsFromModule(fake_pathlib_test),
            loader.loadTestsFromModule(patched_packages_test)
        ])
        return self


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(AllTests().suite())
    sys.exit(int(not result.wasSuccessful()))
