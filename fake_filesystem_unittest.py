#!/usr/bin/python2.7.1
#
# Copyright 2014 Altera Corporation. All Rights Reserved.
# Author: John McGehee
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

"""A base class for unit tests using the :py:class:`pyfakefs` module.

This class searches `sys.modules` for modules that import the `os`, `glob`,
`shutil`, and `tempfile` modules.

The `setUpPyfakefs()` method binds these modules to the corresponding fake
modules from `pyfakefs`.  Further, the built in functions `file()` and
`open()` are bound to fake functions.

The `tearDownPyfakefs()` method returns the module bindings to their original
state.

It is expected that `setUpPyfakefs()` be invoked at the beginning of the derived
class' `setUp()` method, and `tearDownPyfakefs()` be invoked at the end of the
derived class' `tearDown()` method.

During the test, everything uses the fake file system and modules.  This means
that even in your test, you can use familiar functions like `open()` and
`os.makedirs()` to manipulate the fake file system.

This also means existing unit tests that use the real file system can be
retro-fitted to use `pyfakefs` by simply changing their base class from
`:py:class`unittest.TestCase` to
`:py:class`pyfakefs.fake_filesystem_unittest.TestCase`.
"""

import sys
import unittest
import fake_filesystem
import fake_filesystem_glob
import fake_filesystem_shutil
import fake_tempfile

import mox.stubout
import __builtin__

class TestCase(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super(TestCase, self).__init__(methodName)
        self._osModules = set()
        self._globModules = set()
        self._shutilModules = set()
        self._tempfileModules = set()
        self._findModules()
        self.fs = None
        self.stubs = None
        
    def _findModules(self):
        '''Find and cache all modules that import fake file system modules.
        Later, `setUpPyfakefs()` will stub these with the fake file system
        modules.
        ''' 
        for module in set(sys.modules.values()):
            if module is None:
                continue
            if 'os' in module.__dict__:
                self._osModules.add(module)
            if 'glob' in module.__dict__:
                self._globModules.add(module)
            if 'shutil' in module.__dict__:
                self._shutilModules.add(module)
            if 'tempfile' in module.__dict__:
                self._tempfileModules.add(module)

    def setUpPyfakefs(self):
        '''Bind the file-related modules to the :py:class:`pyfakefs` fake file
        system instead of the real file system.  Also bind the fake `file()` and
        `open()` functions.
        
        Invoke this at the beginning of the `setUp()` method in your unit test
        class.
        '''
        self.fs = fake_filesystem.FakeFilesystem()
        fake_os = fake_filesystem.FakeOsModule(self.fs)
        fake_glob = fake_filesystem_glob.FakeGlobModule(self.fs)
        fake_shutil = fake_filesystem_shutil.FakeShutilModule(self.fs)
        fake_tempfile_ = fake_tempfile.FakeTempfileModule(self.fs)
        fake_open = fake_filesystem.FakeFileOpen(self.fs)
        self.stubs = mox.stubout.StubOutForTesting()
        
        self.stubs.SmartSet(__builtin__, 'file', fake_open)
        self.stubs.SmartSet(__builtin__, 'open', fake_open)
        
        for module in self._osModules:
            self.stubs.SmartSet(module,  'os', fake_os)
        for module in self._globModules:
            self.stubs.SmartSet(module,  'glob', fake_glob)
        for module in self._shutilModules:
            self.stubs.SmartSet(module,  'shutil', fake_shutil)
        for module in self._tempfileModules:
            self.stubs.SmartSet(module,  'tempfile', fake_tempfile_)
    
    def teardownPyfakefs(self):
        '''Clear the fake filesystem bindings created by `setUpPyfakefs()`.
        
        Invoke this at the end of the `tearDown()` method in your unit test
        class.
        '''
        self.stubs.SmartUnsetAll()

if __name__ == '__main__':
  unittest.main()
