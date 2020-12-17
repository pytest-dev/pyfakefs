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
import os
import time
import unittest

from pyfakefs.fake_filesystem_unittest import TestCase
from pyfakefs.helpers import IS_PYPY

if os.environ.get('TEST_PERFORMANCE'):

    class SetupPerformanceTest(TestCase):
        @classmethod
        def setUpClass(cls) -> None:
            cls.start_time = time.time()

        @classmethod
        def tearDownClass(cls) -> None:
            cls.elapsed_time = time.time() - cls.start_time
            print('Elapsed time per test for cached setup: {:.3f} ms'.format(
                cls.elapsed_time * 10))

        def setUp(self) -> None:
            self.setUpPyfakefs()

    class SetupNoCachePerformanceTest(TestCase):
        @classmethod
        def setUpClass(cls) -> None:
            cls.start_time = time.time()

        @classmethod
        def tearDownClass(cls) -> None:
            cls.elapsed_time = time.time() - cls.start_time
            print('Elapsed time per test for uncached setup: {:.3f} ms'.format(
                cls.elapsed_time * 10))

        def setUp(self) -> None:
            self.setUpPyfakefs(use_cache=False)

    @unittest.skipIf(IS_PYPY, 'PyPy times are not comparable')
    class TimePerformanceTest(TestCase):
        """Make sure performance degradation in setup is noticed.
        The numbers are related to the CI builds and may fail in local builds.
        """

        def test_cached_time(self):
            self.assertLess(SetupPerformanceTest.elapsed_time, 0.4)

        def test_uncached_time(self):
            self.assertLess(SetupNoCachePerformanceTest.elapsed_time, 6)

    def test_setup(self):
        pass

    for n in range(100):
        test_name = "test_" + str(n)
        setattr(SetupPerformanceTest, test_name, test_setup)
        test_name = "test_nocache" + str(n)
        setattr(SetupNoCachePerformanceTest, test_name, test_setup)

    if __name__ == "__main__":
        unittest.main()
