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
"""Shall provide tests to check performance overhead of pyfakefs."""

import unittest

from pyfakefs.fake_filesystem_unittest import TestCase


class SetupPerformanceTest(TestCase):
    def setUp(self) -> None:
        self.setUpPyfakefs()


class SetupNoCachePerformanceTest(TestCase):
    def setUp(self) -> None:
        self.setUpPyfakefs(use_cache=False)


def test_setup(self):
    pass


for n in range(100):
    test_name = "test_" + str(n)
    setattr(SetupPerformanceTest, test_name, test_setup)
    test_name = "test_nocache" + str(n)
    setattr(SetupNoCachePerformanceTest, test_name, test_setup)

if __name__ == "__main__":
    unittest.main()
