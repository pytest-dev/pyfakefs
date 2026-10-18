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

"""Deterministic controls for the opt-in setup benchmark."""

import builtins
import unittest
from contextlib import contextmanager
from unittest import mock

from pyfakefs.fake_filesystem_unittest import Patcher
from pyfakefs.tests import performance_test


class SetupMeasurementTest(unittest.TestCase):
    def test_uses_cpu_time_per_iteration(self):
        with (
            mock.patch.object(performance_test, "Patcher"),
            mock.patch.object(
                performance_test.time, "time", side_effect=(10.0, 70.0)
            ) as wall_clock,
            mock.patch.object(
                performance_test.time, "process_time", side_effect=(1.0, 1.5)
            ),
        ):
            self.assertAlmostEqual(
                performance_test._measure_setup_cpu_time(use_cache=True, iterations=5),
                0.1,
            )
        wall_clock.assert_not_called()

    def test_warmup_is_excluded_and_cleanup_is_included(self):
        cpu_time = 0.0
        calls = 0

        @contextmanager
        def patcher(*, use_cache):
            nonlocal cpu_time, calls
            calls += 1
            cpu_time += 100 if calls == 1 else 2
            yield
            cpu_time += 3

        with (
            mock.patch.object(performance_test, "Patcher", side_effect=patcher),
            mock.patch.object(
                performance_test.time, "process_time", side_effect=lambda: cpu_time
            ),
        ):
            self.assertEqual(
                performance_test._measure_setup_cpu_time(use_cache=True, iterations=3),
                5,
            )

    def test_each_cycle_has_a_fresh_filesystem_and_restores_patching(self):
        original_open = builtins.open
        for use_cache in (True, False):
            with self.subTest(use_cache=use_cache):
                patchers = []

                def recording_patcher(patchers=patchers, **kwargs):
                    patcher = Patcher(**kwargs)
                    patchers.append(patcher)
                    return patcher

                with mock.patch.object(
                    performance_test, "Patcher", side_effect=recording_patcher
                ):
                    performance_test._measure_setup_cpu_time(
                        use_cache=use_cache, iterations=2
                    )

                self.assertEqual(len(patchers), 3)  # warmup and two measured cycles
                self.assertEqual(len({id(patcher.fs) for patcher in patchers}), 3)
                for patcher in patchers:
                    self.assertIsNotNone(patcher.fs)
                    self.assertEqual(patcher.use_cache, use_cache)
                    self.assertFalse(patcher.is_patching)
                self.assertIsNone(Patcher.PATCHER)
                self.assertIs(builtins.open, original_open)

    def test_rejects_nonpositive_iterations(self):
        for iterations in (0, -1):
            with self.subTest(iterations=iterations):
                with (
                    mock.patch.object(performance_test, "Patcher") as patcher,
                    self.assertRaisesRegex(ValueError, "iterations must be positive"),
                ):
                    performance_test._measure_setup_cpu_time(
                        use_cache=True, iterations=iterations
                    )
                patcher.assert_not_called()


if __name__ == "__main__":
    unittest.main()
