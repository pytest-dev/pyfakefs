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

"""Unit tests for mox3_stubout."""

import datetime
import math
import os
import unittest
from os import path

from pyfakefs import mox3_stubout
from pyfakefs.tests import mox3_stubout_example


class NoPanicMath:
    real_math = math

    @staticmethod
    def fabs(_x):
        return 42

    def __getattr__(self, name):
        """Forwards any unfaked calls to the standard module."""
        return getattr(self.real_math, name)


class ExistingPath:
    real_path = path

    @staticmethod
    def exists(_path):
        return True

    def __getattr__(self, name):
        """Forwards any unfaked calls to the standard module."""
        return getattr(self.real_path, name)


class GroundhogDate(datetime.date):
    @classmethod
    def today(cls):
        return datetime.date(1993, 2, 2)


class StubOutForTestingTest(unittest.TestCase):
    def setUp(self):
        super(StubOutForTestingTest, self).setUp()
        self.stubber = mox3_stubout.StubOutForTesting()

    def test_stubout_method_with_set(self):
        non_existing_path = 'non_existing_path'
        self.assertFalse(
            mox3_stubout_example.check_if_exists(non_existing_path))
        self.stubber.set(os.path, 'exists', lambda x: True)
        self.assertTrue(
            mox3_stubout_example.check_if_exists(non_existing_path))
        self.stubber.unset_all()
        self.assertFalse(
            mox3_stubout_example.check_if_exists(non_existing_path))

    def test_stubout_class_with_set(self):
        self.assertGreater(mox3_stubout_example.tomorrow().year, 2000)

        self.stubber.set(datetime, 'date', GroundhogDate)
        self.assertEqual(mox3_stubout_example.tomorrow(),
                         datetime.date(1993, 2, 3))

        self.stubber.unset_all()
        self.assertGreater(mox3_stubout_example.tomorrow().year, 2000)

    def test_stubout_module_with_set(self):
        self.assertEqual(10, mox3_stubout_example.fabs(-10))

        self.stubber.set(mox3_stubout_example, 'math', NoPanicMath)
        self.assertEqual(42, mox3_stubout_example.fabs(-10))

        self.stubber.unset_all()
        self.assertEqual(10, mox3_stubout_example.fabs(-10))

    def test_set_raise_if_unknown_attribute(self):
        self.assertRaises(AttributeError, self.stubber.set,
                          os.path, 'exists_not', lambda x: True)
        self.assertRaises(AttributeError, self.stubber.set,
                          datetime, 'tomorrow', GroundhogDate)
        self.assertRaises(AttributeError, self.stubber.set,
                          mox3_stubout_example, 'math1', NoPanicMath)

    def test_stubout_method_with_smart_set(self):
        non_existing_path = 'non_existing_path'
        self.stubber.smart_set(os.path, 'exists', lambda x: True)
        self.assertTrue(
            mox3_stubout_example.check_if_exists(non_existing_path))
        self.stubber.smart_unset_all()
        self.assertFalse(
            mox3_stubout_example.check_if_exists(non_existing_path))

    def test_stubout_class_with_smart_set(self):
        self.stubber.smart_set(datetime, 'date', GroundhogDate)
        self.assertEqual(mox3_stubout_example.tomorrow(),
                         datetime.date(1993, 2, 3))

        self.stubber.smart_unset_all()
        self.assertGreater(mox3_stubout_example.tomorrow().year, 2000)

    def test_stubout_module_with_smart_set(self):
        self.assertEqual(10, mox3_stubout_example.fabs(-10))

        self.stubber.smart_set(mox3_stubout_example, 'math', NoPanicMath)
        self.assertEqual(42, mox3_stubout_example.fabs(-10))

        self.stubber.smart_unset_all()
        self.assertEqual(10, mox3_stubout_example.fabs(-10))

    def test_stubout_submodule_with_smart_set(self):
        # this one does not work with Set
        non_existing_path = 'non_existing_path'
        self.assertFalse(
            mox3_stubout_example.check_if_exists(non_existing_path))
        self.stubber.smart_set(os, 'path', ExistingPath)
        self.assertTrue(
            mox3_stubout_example.check_if_exists(non_existing_path))
        self.stubber.smart_unset_all()
        self.assertFalse(
            mox3_stubout_example.check_if_exists(non_existing_path))

    def test_smart_set_raise_if_unknown_attribute(self):
        self.assertRaises(AttributeError, self.stubber.smart_set,
                          os.path, 'exists_not', lambda x: True)
        self.assertRaises(AttributeError, self.stubber.smart_set,
                          datetime, 'tomorrow', GroundhogDate)
        self.assertRaises(AttributeError, self.stubber.smart_set,
                          mox3_stubout_example, 'math1', NoPanicMath)


if __name__ == '__main__':
    unittest.main()
