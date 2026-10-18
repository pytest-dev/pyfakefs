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
"""Report setup/cleanup CPU time with ``TEST_PERFORMANCE=1``.

The measurements are observations, not machine-independent pass/fail limits.
Run with ``python -m pyfakefs.tests.performance_test`` as before.
"""

import os
import time
import unittest

from pyfakefs.fake_filesystem_unittest import Patcher


def _measure_setup_cpu_time(use_cache: bool, iterations: int = 100) -> float:
    """Return mean CPU seconds for a patcher setup and cleanup cycle.

    Warm up imports and, when enabled, the module cache before measuring.
    An uncached patcher still clears the module cache on every iteration.
    """
    if iterations < 1:
        raise ValueError("iterations must be positive")

    with Patcher(use_cache=use_cache):
        pass

    start_time = time.process_time()
    for _ in range(iterations):
        with Patcher(use_cache=use_cache):
            pass
    return (time.process_time() - start_time) / iterations


if os.environ.get("TEST_PERFORMANCE"):

    class SetupPerformanceTest(unittest.TestCase):
        """Report cached and uncached setup costs without host-specific limits."""

        def test_cached_setup(self):
            cpu_time = _measure_setup_cpu_time(use_cache=True)
            print(f"CPU time per cached setup/cleanup cycle: {cpu_time * 1000:.3f} ms")

        def test_uncached_setup(self):
            cpu_time = _measure_setup_cpu_time(use_cache=False)
            print(
                f"CPU time per uncached setup/cleanup cycle: {cpu_time * 1000:.3f} ms"
            )

    if __name__ == "__main__":
        unittest.main()
