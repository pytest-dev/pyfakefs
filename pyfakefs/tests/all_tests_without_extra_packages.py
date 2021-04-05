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
Excludes tests using external scandir package."""

import sys
import unittest

from pyfakefs import extra_packages

if extra_packages.use_scandir_package:
    extra_packages.use_scandir_package = False
    try:
        from os import scandir
    except ImportError:
        scandir = None
    extra_packages.scandir = scandir
    extra_packages.use_scandir = scandir

from pyfakefs.tests.all_tests import AllTests  # noqa: E402

if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(AllTests().suite())
    sys.exit(int(not result.wasSuccessful()))
