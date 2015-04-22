# Copyright 2014 Altera Corporation. All Rights Reserved.
# Author: John McGehee
#
# Copyright 2014 John McGehee.  All Rights Reserved.
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
import inspect
import fake_filesystem
import fake_filesystem_glob
import fake_filesystem_shutil
import fake_tempfile

import mock

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
    def patches(self):
        return self.stubber.patches
        
    def setUpPyfakefs(self):
        '''Bind the file-related modules to the :py:class:`pyfakefs` fake file
        system instead of the real file system.  Also bind the fake `file()` and
        `open()` functions.
        
        Invoke this at the beginning of the `setUp()` method in your unit test
        class.
        '''
        self.stubber.setUp()
    
    def tearDownPyfakefs(self):
        '''Clear the fake file system bindings created by `setUp()`.
        
        Invoke this at the end of the `tearDown()` method in your unit test
        class.
        '''
        self.stubber.tearDown()

class Stubber(object):
    '''
    Instantiate a stub creator to bind and un-bind the file-related modules to
    the :py:module:`pyfakefs` fake modules.
    '''
    SKIPMODULES = set([None, fake_filesystem, fake_filesystem_glob,
                      fake_filesystem_shutil, fake_tempfile, unittest,
                      sys])
    '''Stub nothing that is imported within these modules.
    `sys` is included to prevent `sys.path` from being stubbed with the fake
    `os.path`.
    '''
    assert None in SKIPMODULES, "sys.modules contains 'None' values; must skip them."
    
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
            if module in self.SKIPMODULES or name in self.SKIPNAMES or (not inspect.ismodule(module)):
                continue
            if 'os' in module.__dict__ and inspect.ismodule(module.__dict__['os']):
                self._osModules.add(name + '.os')
            if 'glob' in module.__dict__:
                self._globModules.add(name + '.glob')
            if 'path' in module.__dict__:
                self._pathModules.add(name + '.path')
            if 'shutil' in module.__dict__:
                self._shutilModules.add(name + '.shutil')
            if 'tempfile' in module.__dict__:
                self._tempfileModules.add(name + '.tempfile')
            
    def refresh(self):
        '''Renew the fake file system and set the _isStale flag to `False`.'''
        self._stopAllPatches()
        
        self.fs = fake_filesystem.FakeFilesystem()
        self.fake_os = fake_filesystem.FakeOsModule(self.fs)
        self.fake_glob = fake_filesystem_glob.FakeGlobModule(self.fs)
        self.fake_path = fake_filesystem.FakePathModule(self.fs)
        self.fake_shutil = fake_filesystem_shutil.FakeShutilModule(self.fs)
        self.fake_tempfile_ = fake_tempfile.FakeTempfileModule(self.fs)
        self.fake_open = fake_filesystem.FakeFileOpen(self.fs)

        self._isStale = False

    def _stopAllPatches(self):
        '''Stop (undo) all active patches.'''
        mock.patch.stopall()

    def setUp(self, doctester=None):
        '''Bind the file-related modules to the :py:class:`pyfakefs` fake
        modules real ones.  Also bind the fake `file()` and `open()` functions.
        '''
        if self._isStale:
            self.refresh()
        
        if doctester is not None:
            doctester.globs = self.replaceGlobs(doctester.globs)
            
        def startPatch(self, realModuleName, fakeModule):
            if realModuleName == 'unittest.main.os':
                # Known issue with unittest.main resolving to unittest.main.TestProgram
                # See mock module bug 250, https://code.google.com/p/mock/issues/detail?id=250.
                return
            patch = mock.patch(realModuleName, new=fakeModule)
            try:
                patch.start()
            except:
                target, attribute = realModuleName.rsplit('.', 1)
                print("Warning: Could not patch '{}' on module '{}' because '{}' resolves to {}".format(attribute, target, target, patch.getter()))
                print("         See mock module bug 250, https://code.google.com/p/mock/issues/detail?id=250")
            
        startPatch(self, '__builtin__.file', self.fake_open)
        startPatch(self, '__builtin__.open', self.fake_open)

        for module in self._osModules:
            startPatch(self, module, self.fake_os)
        for module in self._globModules:
            startPatch(self, module, self.fake_glob)
        for module in self._pathModules:
            startPatch(self, module, self.fake_path)
        for module in self._shutilModules:
            startPatch(self, module, self.fake_shutil)
        for module in self._tempfileModules:
            startPatch(self, module, self.fake_tempfile_)
    
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
        self._stopAllPatches()
