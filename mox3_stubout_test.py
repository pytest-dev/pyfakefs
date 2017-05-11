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
from os import path

import sys

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mox3_stubout_example
from pyfakefs import mox3_stubout


class NoPanicMath(object):
    real_math = math

    @staticmethod
    def fabs(x):
        return 42

    def __getattr__(self, name):
        """Forwards any unfaked calls to the standard module."""
        return getattr(self.real_math, name)


class ExistingPath(object):
    real_path = path

    @staticmethod
    def exists(path):
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

    def testStuboutMethodWithSet(self):
        non_existing_path = 'non_existing_path'
        self.assertFalse(mox3_stubout_example.check_if_exists(non_existing_path))
        self.stubber.Set(os.path, 'exists', lambda x: True)
        self.assertTrue(mox3_stubout_example.check_if_exists(non_existing_path))
        self.stubber.UnsetAll()
        self.assertFalse(mox3_stubout_example.check_if_exists(non_existing_path))

    def testStuboutClassWithSet(self):
        self.assertGreater(mox3_stubout_example.tomorrow().year, 2000)

        self.stubber.Set(datetime, 'date', GroundhogDate)
        self.assertEqual(mox3_stubout_example.tomorrow(), datetime.date(1993, 2, 3))

        self.stubber.UnsetAll()
        self.assertGreater(mox3_stubout_example.tomorrow().year, 2000)

    def testStuboutModuleWithSet(self):
        self.assertEqual(10, mox3_stubout_example.fabs(-10))

        self.stubber.Set(mox3_stubout_example, 'math', NoPanicMath)
        self.assertEqual(42, mox3_stubout_example.fabs(-10))

        self.stubber.UnsetAll()
        self.assertEqual(10, mox3_stubout_example.fabs(-10))

    def testSetRaiseIfUnknownAttribute(self):
        self.assertRaises(AttributeError, self.stubber.Set, os.path, 'exists_not', lambda x: True)
        self.assertRaises(AttributeError, self.stubber.Set, datetime, 'tomorrow', GroundhogDate)
        self.assertRaises(AttributeError, self.stubber.Set, mox3_stubout_example, 'math1', NoPanicMath)

    def testStuboutMethodWithSmartSet(self):
        non_existing_path = 'non_existing_path'
        self.stubber.SmartSet(os.path, 'exists', lambda x: True)
        self.assertTrue(mox3_stubout_example.check_if_exists(non_existing_path))
        self.stubber.SmartUnsetAll()
        self.assertFalse(mox3_stubout_example.check_if_exists(non_existing_path))

    def testStuboutClassWithSmartSet(self):
        self.stubber.SmartSet(datetime, 'date', GroundhogDate)
        self.assertEqual(mox3_stubout_example.tomorrow(), datetime.date(1993, 2, 3))

        self.stubber.SmartUnsetAll()
        self.assertGreater(mox3_stubout_example.tomorrow().year, 2000)

    def testStuboutModuleWithSmartSet(self):
        self.assertEqual(10, mox3_stubout_example.fabs(-10))

        self.stubber.SmartSet(mox3_stubout_example, 'math', NoPanicMath)
        self.assertEqual(42, mox3_stubout_example.fabs(-10))

        self.stubber.SmartUnsetAll()
        self.assertEqual(10, mox3_stubout_example.fabs(-10))

    def testStuboutSubModuleWithSmartSet(self):
        # this one does not work with Set
        non_existing_path = 'non_existing_path'
        self.assertFalse(mox3_stubout_example.check_if_exists(non_existing_path))
        self.stubber.SmartSet(os, 'path', ExistingPath)
        self.assertTrue(mox3_stubout_example.check_if_exists(non_existing_path))
        self.stubber.SmartUnsetAll()
        self.assertFalse(mox3_stubout_example.check_if_exists(non_existing_path))

    def testSmartSetRaiseIfUnknownAttribute(self):
        self.assertRaises(AttributeError, self.stubber.SmartSet, os.path, 'exists_not', lambda x: True)
        self.assertRaises(AttributeError, self.stubber.SmartSet, datetime, 'tomorrow', GroundhogDate)
        self.assertRaises(AttributeError, self.stubber.SmartSet, mox3_stubout_example, 'math1', NoPanicMath)


if __name__ == '__main__':
    unittest.main()
