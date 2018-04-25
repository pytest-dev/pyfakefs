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

"""A test suite that runs all tests for pyfakefs at once."""

import sys
import unittest

from pyfakefs.tests import dynamic_patch_test
from pyfakefs.tests import fake_open_test
from pyfakefs.tests import fake_os_test
from pyfakefs.tests import example_test
from pyfakefs.tests import fake_filesystem_glob_test
from pyfakefs.tests import fake_filesystem_shutil_test
from pyfakefs.tests import fake_filesystem_test
from pyfakefs.tests import fake_filesystem_unittest_test
from pyfakefs.tests import fake_tempfile_test
from pyfakefs.tests import fake_filesystem_vs_real_test
from pyfakefs.tests import mox3_stubout_test

if sys.version_info >= (3, 4):
    from pyfakefs.tests import fake_pathlib_test


class AllTests(unittest.TestSuite):
    """A test suite that runs all tests for pyfakefs at once."""

    def suite(self):  # pylint: disable-msg=C6409
        loader = unittest.defaultTestLoader
        self.addTests([
            loader.loadTestsFromModule(fake_filesystem_test),
            loader.loadTestsFromModule(fake_filesystem_glob_test),
            loader.loadTestsFromModule(fake_filesystem_shutil_test),
            loader.loadTestsFromModule(fake_os_test),
            loader.loadTestsFromModule(fake_open_test),
            loader.loadTestsFromModule(fake_tempfile_test),
            loader.loadTestsFromModule(fake_filesystem_vs_real_test),
            loader.loadTestsFromModule(fake_filesystem_unittest_test),
            loader.loadTestsFromModule(example_test),
            loader.loadTestsFromModule(mox3_stubout_test),
            loader.loadTestsFromModule(dynamic_patch_test),
        ])
        if sys.version_info >= (3, 4):
            self.addTests([
                loader.loadTestsFromModule(fake_pathlib_test)
            ])
        return self


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(AllTests().suite())
    sys.exit(int(not result.wasSuccessful()))
