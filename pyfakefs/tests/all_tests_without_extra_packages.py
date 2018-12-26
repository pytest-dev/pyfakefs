#! /usr/bin/env python
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
Excludes tests using external pathlib2 and scandir packages."""

import sys
import unittest

from pyfakefs import extra_packages

if extra_packages.pathlib2:
    extra_packages.pathlib = None
    extra_packages.pathlib2 = None

if extra_packages.use_scandir_package:
    extra_packages.use_scandir = False
    extra_packages.use_scandir_package = False

from pyfakefs.tests.all_tests import AllTests  # noqa: E402


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(AllTests().suite())
    sys.exit(int(not result.wasSuccessful()))
