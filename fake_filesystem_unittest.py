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

The `setUp()` method binds these modules to the corresponding fake
modules from `pyfakefs`.  Further, the built in functions `file()` and
`open()` are bound to fake functions.

The `tearDownPyfakefs()` method returns the module bindings to their original
state.

It is expected that `setUp()` be invoked at the beginning of the derived
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
import doctest
import fake_filesystem
import fake_filesystem_glob
import fake_filesystem_shutil
import fake_tempfile

import mox
import __builtin__

def load_doctests(loader, tests, ignore, module):
    '''Load the doctest tests for the specified module into unittest.'''
    stubber = Stubber()
    globs = stubber.replaceGlobs(vars(module))
    tests.addTests(doctest.DocTestSuite(module,
                                        globs=globs,
                                        setUp=stubber.setUp,
                                        tearDown=stubber.tearDown))
    return tests


class TestCase(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super(TestCase, self).__init__(methodName)
        self.stubber = Stubber()
        
    @property
    def fs(self):
        return self.stubber.fs
    
    @property
    def stubs(self):
        return self.stubber.stubs
        
    def setUpPyfakefs(self):
        '''Bind the file-related modules to the :py:class:`pyfakefs` fake file
        system instead of the real file system.  Also bind the fake `file()` and
        `open()` functions.
        
        Invoke this at the beginning of the `setUp()` method in your unit test
        class.
        '''
        self.stubber.setUp()
    
    def tearDownPyfakefs(self):
        '''Clear the fake filesystem bindings created by `setUp()`.
        
        Invoke this at the end of the `tearDown()` method in your unit test
        class.
        '''
        self.stubber.tearDown()

class Stubber(object):
    '''
    Instantiate a stub creator to bind and un-bind the file-related modules to
    the :py:class:`pyfakefs` fake modules.
    '''
    SKIPMODULES = set([None, fake_filesystem, fake_filesystem_glob,
                      fake_filesystem_shutil, fake_tempfile, sys])
    '''Stub nothing that is imported within these modules.
    
    `sys` is included to prevent `sys.path` from being stubbed with the fake
    `os.path`.
    '''
    SKIPNAMES = set(['os', 'glob', 'path', 'shutil', 'tempfile'])
        
    def __init__(self):
        # Attributes set by _findModules()
        self._osModules = None
        self._globModules = None
        self._pathModules = None
        self._shutilModules = None
        self._tempfileModules = None
        self._findModules()
        assert None not in vars(self).values(), \
                "_findModules() missed the initialization of an instance variable"
        
        # Attributes set by refresh()
        self.fs = None
        self.fake_os = None
        self.fake_glob = None
        self.fake_path = None
        self.fake_shutil = None
        self.fake_tempfile_ = None
        self.fake_open = None
        self.stubs = None
        # _isStale is set by tearDown(), reset by refresh()
        self._isStale = True
        self.refresh()
        assert None not in vars(self).values(), \
                "refresh() missed the initialization of an instance variable"
        assert self._isStale == False, "refresh() did not reset _isStale"
        
    def _findModules(self):
        '''Find and cache all modules that import file system modules.
        Later, `setUp()` will stub these with the fake file system
        modules.
        '''
        self._osModules = set()
        self._globModules = set()
        self._pathModules = set()
        self._shutilModules = set()
        self._tempfileModules = set()
        for name, module in set(sys.modules.items()):
            if module in self.SKIPMODULES or name in self.SKIPNAMES:
                continue
            if 'os' in module.__dict__:
                self._osModules.add(module)
            if 'glob' in module.__dict__:
                self._globModules.add(module)
            if 'path' in module.__dict__:
                self._pathModules.add(module)
            if 'shutil' in module.__dict__:
                self._shutilModules.add(module)
            if 'tempfile' in module.__dict__:
                self._tempfileModules.add(module)

    def refresh(self):
        '''Renew the fake file system and set the _isStale flag to `False`.'''
        if self.stubs is not None:
            self.stubs.SmartUnsetAll()
        self.stubs = mox.stubout.StubOutForTesting()

        self.fs = fake_filesystem.FakeFilesystem()
        self.fake_os = fake_filesystem.FakeOsModule(self.fs)
        self.fake_glob = fake_filesystem_glob.FakeGlobModule(self.fs)
        self.fake_path = fake_filesystem.FakePathModule(self.fs)
        self.fake_shutil = fake_filesystem_shutil.FakeShutilModule(self.fs)
        self.fake_tempfile_ = fake_tempfile.FakeTempfileModule(self.fs)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fs)

        self._isStale = False

    def setUp(self, doctester=None):
        '''Bind the file-related modules to the :py:class:`pyfakefs` fake
        modules real ones.  Also bind the fake `file()` and `open()` functions.
        
        Invoke this at the beginning of the `setUp()` method in your unit test
        class.
        '''
        if self._isStale:
            self.refresh()
        
        if doctester is not None:
            doctester.globs = self.replaceGlobs(doctester.globs)
            
        self.stubs.SmartSet(__builtin__, 'file', self.fake_open)
        self.stubs.SmartSet(__builtin__, 'open', self.fake_open)
        
        for module in self._osModules:
            self.stubs.SmartSet(module,  'os', self.fake_os)
        for module in self._globModules:
            self.stubs.SmartSet(module,  'glob', self.fake_glob)
        for module in self._pathModules:
            self.stubs.SmartSet(module,  'path', self.fake_path)
        for module in self._shutilModules:
            self.stubs.SmartSet(module,  'shutil', self.fake_shutil)
        for module in self._tempfileModules:
            self.stubs.SmartSet(module,  'tempfile', self.fake_tempfile_)
    
    def replaceGlobs(self, globs_):
        globs = globs_.copy()
        if self._isStale:
            self.refresh()
        if 'os' in globs:
            globs['os'] = fake_filesystem.FakeOsModule(self.fs)
        if 'glob' in globs:
            globs['glob'] = fake_filesystem_glob.FakeGlobModule(self.fs)
        if 'path' in globs:
            globs['path'] =  fake_filesystem.FakePathModule(self.fs)
        if 'shutil' in globs:
            globs['shutil'] = fake_filesystem_shutil.FakeShutilModule(self.fs)
        if 'tempfile' in globs:
            globs['tempfile'] = fake_tempfile.FakeTempfileModule(self.fs)
        return globs
    
    def tearDown(self, doctester=None):
        '''Clear the fake filesystem bindings created by `setUp()`.
        
        Invoke this at the end of the `tearDown()` method in your unit test
        class.
        '''
        self._isStale = True
        self.stubs.SmartUnsetAll()

if __name__ == '__main__':
    unittest.main()
